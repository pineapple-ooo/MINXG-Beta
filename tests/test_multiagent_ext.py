"""tests/test_multiagent_ext.py — extensions/builtin/multiagent_ext.

The coordination pipeline (`run_coding_crew`) takes an injectable
`handler` — a fake stand-in for `tools.delegate_tool._create_subagent_handler`'s
real, AI-calling handler — so the planner/coder/reviewer/revise-loop
*logic* is fully testable without a live model. What real-model output
quality actually looks like isn't something this environment can test
(no AI provider reachable) — see the module's own "Honesty note".
"""
from __future__ import annotations

import json

import pytest

from extensions.builtin.multiagent_ext import (
    run_coding_crew, _extract_json, _parse_subtask_list, _parse_review,
    _handle_multi_agent_code_task, register_hooks,
    PLANNER_SYSTEM_PROMPT, REVIEWER_SYSTEM_PROMPT,
)


def _task_result(task_id, goal, result_text):
    return json.dumps({"task_id": task_id, "goal": goal, "status": "completed", "result": result_text})


class _ScriptedHandler:
    """Routes fake responses by role (planner/coder/reviewer), driven by
    each task's `context.role_prompt` — the same signal the real code
    uses to build the system message."""

    def __init__(self, plan_response, review_responses, coder_response="Implemented it."):
        self.plan_response = plan_response
        self.review_responses = list(review_responses)
        self.coder_response = coder_response
        self.calls = []

    def __call__(self, task):
        self.calls.append(task)
        role = (task.context or {}).get("role_prompt", "")
        if role == PLANNER_SYSTEM_PROMPT:
            return _task_result(task.task_id, task.goal, self.plan_response)
        if role == REVIEWER_SYSTEM_PROMPT:
            resp = self.review_responses.pop(0) if self.review_responses else '{"approved": true, "issues": []}'
            return _task_result(task.task_id, task.goal, resp)
        # coder
        return _task_result(task.task_id, task.goal, self.coder_response)


class TestJsonExtraction:
    def test_extracts_clean_array(self):
        assert _extract_json('["a", "b"]', "[", "]") == ["a", "b"]

    def test_extracts_array_with_markdown_fence(self):
        text = 'Sure, here:\n```json\n["a", "b"]\n```\nHope that helps!'
        assert _extract_json(text, "[", "]") == ["a", "b"]

    def test_extracts_object_with_preamble(self):
        text = 'Based on my review: {"approved": false, "issues": ["x"]}'
        assert _extract_json(text, "{", "}") == {"approved": False, "issues": ["x"]}

    def test_returns_none_for_garbage(self):
        assert _extract_json("no json here at all", "[", "]") is None

    def test_returns_none_for_empty_string(self):
        assert _extract_json("", "{", "}") is None

    def test_handles_nested_brackets(self):
        text = '{"approved": true, "issues": ["fix [the] thing"]}'
        assert _extract_json(text, "{", "}") == {"approved": True, "issues": ["fix [the] thing"]}


class TestParseSubtaskList:
    def test_parses_clean_list(self):
        assert _parse_subtask_list('["Add tests", "Fix bug"]') == ["Add tests", "Fix bug"]

    def test_strips_whitespace_and_drops_empties(self):
        assert _parse_subtask_list('[" Add tests ", "", "  "]') == ["Add tests"]

    def test_non_list_json_returns_empty(self):
        assert _parse_subtask_list('{"not": "a list"}') == []

    def test_garbage_returns_empty(self):
        assert _parse_subtask_list("I cannot help with that.") == []


class TestParseReview:
    def test_approved_true(self):
        assert _parse_review('{"approved": true, "issues": []}') == {"approved": True, "issues": []}

    def test_approved_false_with_issues(self):
        result = _parse_review('{"approved": false, "issues": ["redo X"]}')
        assert result == {"approved": False, "issues": ["redo X"]}

    def test_missing_approved_key_fails_safe(self):
        result = _parse_review('{"issues": ["x"]}')
        assert result["approved"] is False
        assert result["issues"] == []  # fail-safe: no actionable issues either

    def test_unparseable_fails_safe(self):
        result = _parse_review("the code looks fine to me")
        assert result["approved"] is False
        assert "unparsed" in result


class TestRunCodingCrew:
    def test_requires_goal(self):
        result = run_coding_crew("", handler=lambda t: "{}")
        assert "error" in result

    def test_happy_path_single_round_approved(self):
        handler = _ScriptedHandler(
            plan_response='["Write the function", "Write tests"]',
            review_responses=['{"approved": true, "issues": []}'],
        )
        result = run_coding_crew("build a thing", handler=handler)

        assert result["subtasks"] == ["Write the function", "Write tests"]
        assert result["approved"] is True
        assert result["rounds_used"] == 1
        assert len(result["coder_results"]) == 2
        assert all(r["status"] == "completed" for r in result["coder_results"])

    def test_planner_failure_short_circuits(self):
        handler = _ScriptedHandler(plan_response="not json at all", review_responses=[])
        result = run_coding_crew("build a thing", handler=handler)
        assert "error" in result
        assert "raw_plan_output" in result

    def test_revise_loop_runs_when_reviewer_rejects(self):
        handler = _ScriptedHandler(
            plan_response='["Do the thing"]',
            review_responses=[
                '{"approved": false, "issues": ["Do the thing (missing edge case)"]}',
                '{"approved": true, "issues": []}',
            ],
        )
        result = run_coding_crew("build a thing", handler=handler, max_revise_rounds=2)

        assert result["approved"] is True
        assert result["rounds_used"] == 2
        # 2 review calls happened
        review_calls = [t for t in handler.calls
                         if (t.context or {}).get("role_prompt") == REVIEWER_SYSTEM_PROMPT]
        assert len(review_calls) == 2
        # the revise-round coder task carried the flagged issue as its goal
        revise_calls = [t for t in handler.calls if t.task_id.startswith("revise_")]
        assert len(revise_calls) == 1
        assert "missing edge case" in revise_calls[0].goal

    def test_revise_loop_is_bounded(self):
        # reviewer NEVER approves — pipeline must still terminate
        handler = _ScriptedHandler(
            plan_response='["Do the thing"]',
            review_responses=[
                '{"approved": false, "issues": ["redo 1"]}',
                '{"approved": false, "issues": ["redo 2"]}',
                '{"approved": false, "issues": ["redo 3"]}',
            ],
        )
        result = run_coding_crew("build a thing", handler=handler, max_revise_rounds=2)
        assert result["approved"] is False
        assert result["rounds_used"] == 3  # initial + 2 revise rounds, then stop
        review_calls = [t for t in handler.calls
                         if (t.context or {}).get("role_prompt") == REVIEWER_SYSTEM_PROMPT]
        assert len(review_calls) == 3  # never a 4th — bound respected

    def test_reviewer_with_no_issues_but_not_approved_stops_early(self):
        handler = _ScriptedHandler(
            plan_response='["Do the thing"]',
            review_responses=['garbled non-json output from the model'],
        )
        result = run_coding_crew("build a thing", handler=handler, max_revise_rounds=5)
        assert result["rounds_used"] == 1  # stops immediately, no issues to act on
        assert result["approved"] is False

    def test_parallel_coder_tasks_all_get_dispatched(self):
        handler = _ScriptedHandler(
            plan_response='["A", "B", "C", "D"]',
            review_responses=['{"approved": true, "issues": []}'],
        )
        result = run_coding_crew("build a thing", handler=handler)
        coder_calls = [t for t in handler.calls if t.task_id.startswith("code_")]
        assert len(coder_calls) == 4
        assert {t.goal for t in coder_calls} == {"A", "B", "C", "D"}

    def test_custom_toolsets_propagate_to_coder_tasks(self):
        handler = _ScriptedHandler(
            plan_response='["A"]', review_responses=['{"approved": true, "issues": []}'],
        )
        run_coding_crew("build a thing", handler=handler, toolsets=["web"])
        coder_calls = [t for t in handler.calls if t.task_id.startswith("code_")]
        assert coder_calls[0].toolsets == ["web"]

    def test_planner_and_reviewer_get_no_toolsets(self):
        """Planner/reviewer only reason over text; they shouldn't be
        handed file/terminal access they have no use for."""
        handler = _ScriptedHandler(
            plan_response='["A"]', review_responses=['{"approved": true, "issues": []}'],
        )
        run_coding_crew("build a thing", handler=handler)
        planner_calls = [t for t in handler.calls
                          if (t.context or {}).get("role_prompt") == PLANNER_SYSTEM_PROMPT]
        reviewer_calls = [t for t in handler.calls
                           if (t.context or {}).get("role_prompt") == REVIEWER_SYSTEM_PROMPT]
        assert planner_calls[0].toolsets == []
        assert reviewer_calls[0].toolsets == []


class TestChatToolHandler:
    def test_handle_multi_agent_code_task_returns_json(self):
        """Patches tools.delegate_tool._create_subagent_handler (what
        run_coding_crew() actually calls internally when no handler is
        explicitly injected) rather than the extension module's
        run_coding_crew reference directly. extensions/loader.py loads
        builtin extensions through its own dynamic import machinery
        (`extensions._dynamic.*`), a *separate* module object from a
        plain `import extensions.builtin.multiagent_ext` — depending on
        which one happened to run first in a given test session, a
        patch on "the module this test imported" can silently miss the
        copy that's actually wired into the live handler. Patching the
        shared `tools.delegate_tool` dependency underneath both copies
        sidesteps that entirely.
        """
        from unittest import mock
        handler = _ScriptedHandler(
            plan_response='["A"]', review_responses=['{"approved": true, "issues": []}'],
        )
        with mock.patch("tools.delegate_tool._create_subagent_handler", return_value=handler):
            result = json.loads(_handle_multi_agent_code_task({"goal": "build a thing"}))

        assert result["approved"] is True


class TestRegisterHooks:
    def test_register_hooks_registers_real_callable_tool(self):
        from tools.registry import ToolRegistry
        fresh_registry = ToolRegistry()
        register_hooks(fresh_registry)
        assert "multi_agent_code_task" in fresh_registry.get_all_tool_names()
        entry = fresh_registry.get_entry("multi_agent_code_task")
        assert entry.handler is _handle_multi_agent_code_task


class TestExtensionMetadata:
    def test_disabled_by_default(self):
        import extensions.builtin.multiagent_ext as ext_mod
        assert ext_mod.EXTENSION_ENABLED is False

    def test_has_required_contract_attrs(self):
        import extensions.builtin.multiagent_ext as ext_mod
        assert ext_mod.EXTENSION_NAME == "minxg-multiagent"
        assert ext_mod.EXTENSION_DESCRIPTION
        assert callable(ext_mod.handle_command)
