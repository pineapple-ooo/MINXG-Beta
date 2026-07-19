"""Delegate Tool - Subagent orchestration for parallel task execution.

This module implements the delegation system inspired by Hermes' delegate_tool.
It allows the orchestrator to spawn child agents with isolated context and
execute tasks in parallel.
"""

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


BLOCKED_TOOLS = frozenset({
    "delegate_task",
    "clarify",
    "skill_manage",
})


DEFAULT_SUBAGENT_CONFIG = {
    "max_iterations": 50,
    "timeout": 300,
    "auto_approve": False,
}


@dataclass
class SubagentTask:
    """A task to be executed by a subagent."""
    task_id: str
    goal: str
    context: Optional[Dict] = None
    toolsets: List[str] = field(default_factory=lambda: ["file", "terminal"])
    max_iterations: int = 50
    timeout: float = 300.0
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


class SubagentPool:
    """Thread-safe pool of subagent tasks."""
    
    def __init__(self, max_workers: int = 4):
        self._tasks: Dict[str, SubagentTask] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: Dict[str, Any] = {}
    
    def submit(self, task: SubagentTask, handler: Callable) -> SubagentTask:
        """Submit a task for execution."""
        with self._lock:
            task.status = "running"
            task.started_at = time.time()
            self._tasks[task.task_id] = task
            
            future = self._executor.submit(self._run_task, task, handler)
            self._futures[task.task_id] = future
        
        return task
    
    def _run_task(self, task: SubagentTask, handler: Callable) -> None:
        """Run a task with the provided handler."""
        try:
            logger.info(f"Subagent {task.task_id} started: {task.goal[:50]}...")
            result = handler(task)
            task.status = "completed"
            task.result = result
            logger.info(f"Subagent {task.task_id} completed")
        except FuturesTimeoutError:
            task.status = "timeout"
            task.error = f"Task timed out after {task.timeout}s"
            logger.warning(f"Subagent {task.task_id} timed out")
        except Exception as e:
            task.status = "failed"
            task.error = f"{type(e).__name__}: {e}"
            logger.error(f"Subagent {task.task_id} failed: {e}")
        finally:
            task.finished_at = time.time()
    
    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        """Get task status."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def list_tasks(self) -> List[SubagentTask]:
        """List all tasks."""
        with self._lock:
            return list(self._tasks.values())
    
    def wait_for(self, task_ids: List[str], timeout: float = None) -> Dict[str, SubagentTask]:
        """Wait for specific tasks to complete."""
        results = {}
        deadline = time.time() + timeout if timeout else None
        
        for tid in task_ids:
            remaining = deadline - time.time() if deadline else None
            future = self._futures.get(tid)
            if future:
                try:
                    future.result(timeout=remaining)
                except FuturesTimeoutError:
                    pass
            task = self.get_task(tid)
            if task:
                results[tid] = task
        
        return results
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the executor."""
        self._executor.shutdown(wait=wait)



_subagent_pool: Optional[SubagentPool] = None
_subagent_pool_lock = threading.Lock()


def get_subagent_pool() -> SubagentPool:
    """Get the global subagent pool."""
    global _subagent_pool
    with _subagent_pool_lock:
        if _subagent_pool is None:
            _subagent_pool = SubagentPool(max_workers=4)
        return _subagent_pool



DELEGATE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string", "description": "The task goal for the subagent"},
        "context": {"type": "object", "description": "Additional context for the task"},
        "toolsets": {"type": "array", "items": {"type": "string"}, "description": "Enabled toolsets for subagent"},
        "max_iterations": {"type": "integer", "description": "Max iterations for subagent", "default": 50},
        "timeout": {"type": "number", "description": "Timeout in seconds", "default": 300},
        "wait": {"type": "boolean", "description": "Wait for result before returning", "default": True},
    },
    "required": ["goal"],
}

DELEGATE_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "goal": {"type": "string"},
                    "context": {"type": "object"},
                    "toolsets": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["goal"],
            },
            "description": "List of tasks to execute in parallel",
        },
        "wait": {"type": "boolean", "description": "Wait for all tasks", "default": True},
    },
    "required": ["tasks"],
}


def _create_subagent_handler(orchestrator_ref) -> Callable:
    """Create a handler function for subagent execution.

    Builds a fresh, isolated NexusOrchestrator per task — its own
    session, its own conversation history, its own toolset restriction
    — rather than sharing `orchestrator_ref` directly. SubagentPool
    runs tasks concurrently on a thread pool, and `enabled_toolsets`
    lives on the orchestrator *instance*; sharing one mutable instance
    across concurrent tasks would let one task's toolset restriction
    leak into another's. `orchestrator_ref`, when given, is only used
    to inherit provider/model/config defaults — never shared execution
    state.

    This used to be a stub: `orchestrator_ref` was accepted and never
    read, and the returned handler fabricated a "completed" message
    without calling a model or running a single tool. `delegate_task`
    and `delegate_batch` — both already registered, chat-agent-callable
    tools — were reporting fabricated success on every call. This is
    the actual implementation.
    """
    inherited: Dict[str, Any] = {}
    if orchestrator_ref is not None:
        for attr in ("ai_model", "ai_base_url", "ai_api_key", "ai_provider", "config"):
            val = getattr(orchestrator_ref, attr, None)
            if val is not None:
                inherited[attr] = val

    def handler(task: SubagentTask) -> str:
        from multiling.orchestrator import NexusOrchestrator

        sub_orchestrator = NexusOrchestrator(
            max_iterations=task.max_iterations,
            enabled_toolsets=task.toolsets,
            session_id=f"subagent_{task.task_id}",
            **inherited,
        )

        goal = task.goal
        system_message = None
        if task.context:
            system_message = task.context.get("role_prompt") or None
            extra_context = task.context.get("extra_context")
            if extra_context:
                goal = f"{task.goal}\n\n---\nAdditional context:\n{extra_context}"

        result_text = sub_orchestrator.chat(goal, system_message=system_message)
        return json.dumps({
            "task_id": task.task_id,
            "goal": task.goal,
            "status": "completed",
            "result": result_text,
        })
    return handler


def _handle_delegate_task(args: dict) -> str:
    """Delegate a task to a subagent."""
    goal = args.get("goal", "")
    if not goal:
        return json.dumps({"error": "goal is required"})
    
    task_id = args.get("task_id") or f"subagent_{uuid.uuid4().hex[:8]}"
    context = args.get("context", {})
    toolsets = args.get("toolsets", ["file", "terminal"])
    max_iterations = args.get("max_iterations", 50)
    timeout = args.get("timeout", 300)
    wait = args.get("wait", True)
    
    task = SubagentTask(
        task_id=task_id,
        goal=goal,
        context=context,
        toolsets=toolsets,
        max_iterations=max_iterations,
        timeout=timeout,
    )
    
    pool = get_subagent_pool()
    handler = _create_subagent_handler(None)
    pool.submit(task, handler)
    
    if wait:
        pool.wait_for([task_id], timeout=timeout)
        task = pool.get_task(task_id)
        if task:
            if task.status == "completed":
                return task.result or json.dumps({"ok": True, "task_id": task_id})
            else:
                return json.dumps({"error": task.error or f"Task {task.status}"})
    
    return json.dumps({
        "ok": True,
        "task_id": task_id,
        "status": task.status,
        "message": f"Task {task_id} submitted and running",
    })


def _handle_delegate_batch(args: dict) -> str:
    """Delegate multiple tasks in parallel."""
    tasks_data = args.get("tasks", [])
    if not tasks_data:
        return json.dumps({"error": "tasks is required and must not be empty"})
    
    wait = args.get("wait", True)
    pool = get_subagent_pool()
    handler = _create_subagent_handler(None)
    task_ids = []
    
    for td in tasks_data:
        task_id = td.get("task_id") or f"subagent_{uuid.uuid4().hex[:8]}"
        task = SubagentTask(
            task_id=task_id,
            goal=td["goal"],
            context=td.get("context", {}),
            toolsets=td.get("toolsets", ["file", "terminal"]),
        )
        pool.submit(task, handler)
        task_ids.append(task_id)
    
    if wait:
        results = pool.wait_for(task_ids, timeout=600)
        return json.dumps({
            "ok": True,
            "results": {
                tid: {
                    "status": t.status,
                    "result": t.result,
                    "error": t.error,
                }
                for tid, t in results.items()
            },
        })
    
    return json.dumps({
        "ok": True,
        "task_ids": task_ids,
        "message": f"{len(task_ids)} tasks submitted",
    })


def _check_delegate_reqs() -> bool:
    """Check if delegation is available."""
    return True



from tools.registry import registry

registry.register(
    name="delegate_task",
    toolset="delegate",
    schema=DELEGATE_TASK_SCHEMA,
    handler=_handle_delegate_task,
    check_fn=_check_delegate_reqs,
    emoji="",
    max_result_size_chars=50000,
)

registry.register(
    name="delegate_batch",
    toolset="delegate",
    schema=DELEGATE_BATCH_SCHEMA,
    handler=_handle_delegate_batch,
    check_fn=_check_delegate_reqs,
    emoji="",
    max_result_size_chars=100000,
)
