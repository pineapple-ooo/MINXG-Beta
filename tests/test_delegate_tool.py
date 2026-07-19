"""tests/test_delegate_tool.py — tools/delegate_tool.py.

Covers the real bug this pass fixed: `_create_subagent_handler`'s
returned handler used to fabricate a "completed" response without
ever calling a model or dispatching a single tool — `delegate_task`
and `delegate_batch` were already registered, chat-agent-callable
tools reporting fabricated success on every call. `NexusOrchestrator`
is mocked throughout (it would otherwise make a real network call to
an AI provider, which this sandbox can't do and a unit test shouldn't
depend on anyway) — what's under test is that delegate_tool actually
*drives* it correctly: fresh isolated instance per task, correct
goal/system_message/toolset wiring, and that concurrent tasks never
share a mutable orchestrator instance.
"""
from __future__ import annotations

import json
import time
from unittest import mock

import pytest

import tools.delegate_tool as dt


class _FakeOrchestrator:
    """Records how it was constructed and what chat() was called with."""
    instances = []

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.chat_calls = []
        _FakeOrchestrator.instances.append(self)

    def chat(self, message, system_message=None):
        self.chat_calls.append({"message": message, "system_message": system_message})
        return f"handled: {message[:40]}"


@pytest.fixture(autouse=True)
def _reset_fake_orchestrator():
    _FakeOrchestrator.instances = []
    yield
    _FakeOrchestrator.instances = []


@pytest.fixture(autouse=True)
def _fresh_pool():
    """Each test gets a clean, tiny subagent pool instead of the
    process-wide singleton (which would leak tasks between tests and
    keep unrelated tests' thread pools alive)."""
    pool = dt.SubagentPool(max_workers=4)
    with mock.patch.object(dt, "_subagent_pool", pool):
        yield pool
    pool.shutdown(wait=True)


def _patch_orchestrator():
    return mock.patch("multiling.orchestrator.NexusOrchestrator", _FakeOrchestrator)


class TestCreateSubagentHandler:
    def test_handler_calls_chat_with_the_goal(self):
        with _patch_orchestrator():
            handler = dt._create_subagent_handler(None)
            task = dt.SubagentTask(task_id="t1", goal="write a fibonacci function")
            result = json.loads(handler(task))

        assert result["status"] == "completed"
        assert "fibonacci" in result["result"]
        assert _FakeOrchestrator.instances[0].chat_calls[0]["message"] == "write a fibonacci function"

    def test_handler_builds_isolated_orchestrator_per_task(self):
        with _patch_orchestrator():
            handler = dt._create_subagent_handler(None)
            handler(dt.SubagentTask(task_id="t1", goal="a", toolsets=["file"]))
            handler(dt.SubagentTask(task_id="t2", goal="b", toolsets=["terminal"]))

        assert len(_FakeOrchestrator.instances) == 2
        assert _FakeOrchestrator.instances[0] is not _FakeOrchestrator.instances[1]
        assert _FakeOrchestrator.instances[0].init_kwargs["enabled_toolsets"] == ["file"]
        assert _FakeOrchestrator.instances[1].init_kwargs["enabled_toolsets"] == ["terminal"]

    def test_handler_uses_role_prompt_as_system_message(self):
        with _patch_orchestrator():
            handler = dt._create_subagent_handler(None)
            task = dt.SubagentTask(
                task_id="t1", goal="review this",
                context={"role_prompt": "You are a strict code reviewer."},
            )
            handler(task)

        call = _FakeOrchestrator.instances[0].chat_calls[0]
        assert call["system_message"] == "You are a strict code reviewer."

    def test_handler_appends_extra_context_to_goal(self):
        with _patch_orchestrator():
            handler = dt._create_subagent_handler(None)
            task = dt.SubagentTask(
                task_id="t1", goal="fix the bug",
                context={"extra_context": "Previous review found: off-by-one error"},
            )
            handler(task)

        call = _FakeOrchestrator.instances[0].chat_calls[0]
        assert "fix the bug" in call["message"]
        assert "off-by-one error" in call["message"]

    def test_handler_passes_max_iterations_from_task(self):
        with _patch_orchestrator():
            handler = dt._create_subagent_handler(None)
            handler(dt.SubagentTask(task_id="t1", goal="a", max_iterations=7))

        assert _FakeOrchestrator.instances[0].init_kwargs["max_iterations"] == 7

    def test_handler_inherits_provider_config_from_parent_orchestrator(self):
        parent = mock.Mock(
            ai_model="gpt-4o", ai_base_url="https://api.example.com/v1",
            ai_api_key="sk-parent", ai_provider="openai", config={"foo": "bar"},
        )
        with _patch_orchestrator():
            handler = dt._create_subagent_handler(parent)
            handler(dt.SubagentTask(task_id="t1", goal="a"))

        kwargs = _FakeOrchestrator.instances[0].init_kwargs
        assert kwargs["ai_model"] == "gpt-4o"
        assert kwargs["ai_base_url"] == "https://api.example.com/v1"
        assert kwargs["ai_provider"] == "openai"

    def test_handler_with_no_parent_does_not_pass_none_values(self):
        with _patch_orchestrator():
            handler = dt._create_subagent_handler(None)
            handler(dt.SubagentTask(task_id="t1", goal="a"))

        kwargs = _FakeOrchestrator.instances[0].init_kwargs
        assert "ai_model" not in kwargs  # falls through to NexusOrchestrator's own defaults


class TestDelegateTaskEndToEnd:
    def test_delegate_task_waits_and_returns_real_result(self):
        with _patch_orchestrator():
            result = json.loads(dt._handle_delegate_task({
                "goal": "implement quicksort", "wait": True, "timeout": 5,
            }))
        assert "quicksort" in result["result"]

    def test_delegate_task_requires_goal(self):
        result = json.loads(dt._handle_delegate_task({}))
        assert "error" in result

    def test_delegate_task_no_wait_returns_immediately(self):
        with _patch_orchestrator():
            result = json.loads(dt._handle_delegate_task({"goal": "slow task", "wait": False}))
        assert result["ok"] is True
        assert "task_id" in result


class TestDelegateBatch:
    def test_delegate_batch_runs_tasks_in_parallel(self):
        with _patch_orchestrator():
            result = json.loads(dt._handle_delegate_batch({
                "tasks": [
                    {"task_id": "a", "goal": "task A"},
                    {"task_id": "b", "goal": "task B"},
                    {"task_id": "c", "goal": "task C"},
                ],
                "wait": True,
            }))
        assert len(result["results"]) == 3
        for tid in ("a", "b", "c"):
            assert result["results"][tid]["status"] == "completed"

    def test_delegate_batch_requires_nonempty_tasks(self):
        result = json.loads(dt._handle_delegate_batch({"tasks": []}))
        assert "error" in result

    def test_concurrent_tasks_get_independent_orchestrators(self):
        """The bug this guards against: a shared, mutable orchestrator
        instance across concurrently-running tasks would let one
        task's toolset restriction (or worse, conversation state) leak
        into another's."""
        with _patch_orchestrator():
            dt._handle_delegate_batch({
                "tasks": [
                    {"task_id": "x", "goal": "a", "toolsets": ["file"]},
                    {"task_id": "y", "goal": "b", "toolsets": ["terminal", "web"]},
                ],
                "wait": True,
            })
        toolsets_seen = sorted(
            tuple(inst.init_kwargs["enabled_toolsets"])
            for inst in _FakeOrchestrator.instances
        )
        assert toolsets_seen == [("file",), ("terminal", "web")]


class TestSubagentPool:
    def test_task_status_transitions(self, _fresh_pool):
        task = dt.SubagentTask(task_id="p1", goal="do a thing")

        def slow_handler(t):
            time.sleep(0.05)
            return "done"

        _fresh_pool.submit(task, slow_handler)
        assert task.status in ("running", "completed")
        _fresh_pool.wait_for(["p1"], timeout=5)
        finished = _fresh_pool.get_task("p1")
        assert finished.status == "completed"
        assert finished.result == "done"

    def test_task_failure_is_captured_not_raised(self, _fresh_pool):
        task = dt.SubagentTask(task_id="p2", goal="boom")

        def bad_handler(t):
            raise ValueError("kaboom")

        _fresh_pool.submit(task, bad_handler)
        _fresh_pool.wait_for(["p2"], timeout=5)
        finished = _fresh_pool.get_task("p2")
        assert finished.status == "failed"
        assert "kaboom" in finished.error
