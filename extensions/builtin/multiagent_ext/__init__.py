"""extensions/builtin/multiagent_ext/__init__.py -- coding crew v0.1.0

Role-specialized multi-agent collaboration for coding tasks: a Planner
sub-agent breaks a goal into subtasks, Coder sub-agents implement them
in parallel, a Reviewer sub-agent checks the combined result, and
flagged subtasks get re-delegated with the review feedback attached
(bounded number of rounds). Built entirely on top of
`tools/delegate_tool.py`'s SubagentPool/SubagentTask — this module is
the *orchestration policy* on top of that execution primitive, not a
second implementation of it.

Ships **disabled by default** (`minxg ext add minxg-multiagent` to opt
in), same convention as adb_ext/root_ext: this spins up multiple real
sub-agent conversations (each one a real, potentially expensive AI
call once a provider is configured) and shouldn't fire without the
person asking for it.

Two ways to reach it:
  - CLI: `minxg ext multiagent run "<goal>"` — standalone, non-interactive.
  - Chat tool: `multi_agent_code_task` — reachable mid-conversation once
    enabled, wired up via `register_hooks()` (see
    `multiling/model_tools.py::ensure_tools_discovered` for why that
    now actually works — it didn't before this same pass).

Honesty note: the planner/coder/reviewer prompts and the JSON-array /
JSON-object extraction from model output are written defensively (LLMs
don't reliably emit bare JSON), and the coordination *logic* is fully
unit-tested with a fake handler (tests/test_multiagent_ext.py). What
isn't and can't be tested from this environment is real multi-round
output quality against an actual model — there's no AI provider
reachable from this sandbox. Try it against a real, configured
provider before leaning on it for anything important.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


EXTENSION_NAME = "minxg-multiagent"
EXTENSION_DESCRIPTION = (
    "Multi-agent coding crew: Planner -> parallel Coders -> Reviewer, "
    "with a bounded revise loop, built on tools/delegate_tool.py"
)
EXTENSION_VERSION = "0.1.0"
EXTENSION_PRIORITY = 50
EXTENSION_SOURCE = "builtin"
EXTENSION_ENABLED = False  # opt-in: spins up real, potentially costly sub-agent calls


PLANNER_SYSTEM_PROMPT = (
    "You are a technical planner. Given a coding goal, break it into "
    "2 to 5 concrete, largely-independent subtasks a coding agent could "
    "each implement on its own. Reply with ONLY a JSON array of short "
    "subtask description strings — no prose, no markdown fences, no "
    "explanation. Example: [\"Add input validation to parse_config()\", "
    "\"Write unit tests for parse_config()\"]"
)

CODER_SYSTEM_PROMPT = (
    "You are a focused coding agent. Implement exactly the subtask you "
    "are given, using the file and terminal tools available to you. "
    "Make the smallest correct change that accomplishes the subtask. "
    "When done, briefly summarize what you changed and why."
)

REVIEWER_SYSTEM_PROMPT = (
    "You are a strict code reviewer. You will be given the original "
    "goal and a set of subtask results from other agents. Check "
    "whether the combined work actually accomplishes the goal. Reply "
    "with ONLY a JSON object of the form "
    "{\"approved\": true|false, \"issues\": [\"<subtask text to redo, "
    "with what's wrong>\", ...]}. `issues` must be empty when "
    "`approved` is true. No prose, no markdown fences."
)


# ─────────────────────────────────────────────── tolerant model-output parsing

def _extract_json(text: str, opener: str, closer: str) -> Optional[Any]:
    """Find the first `opener...closer` span in `text` and json.loads it.
    Models routinely wrap JSON in markdown fences or add a sentence of
    preamble/trailing commentary even when told not to; search for the
    structural span instead of assuming the whole string is clean JSON."""
    if not text:
        return None
    start = text.find(opener)
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == opener:
            depth += 1
        elif text[i] == closer:
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def _parse_subtask_list(text: str) -> List[str]:
    data = _extract_json(text, "[", "]")
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if str(item).strip()]


def _parse_review(text: str) -> Dict[str, Any]:
    data = _extract_json(text, "{", "}")
    if not isinstance(data, dict) or "approved" not in data:
        # Model didn't follow the format — fail safe: treat as
        # not-approved-but-no-actionable-issues, so the pipeline stops
        # (bounded rounds) rather than looping on garbage forever.
        return {"approved": False, "issues": [], "unparsed": text[:500]}
    issues = data.get("issues") or []
    return {
        "approved": bool(data["approved"]),
        "issues": [str(i) for i in issues if str(i).strip()],
    }


# ─────────────────────────────────────────────────────── the actual pipeline

def run_coding_crew(
    goal: str,
    toolsets: Optional[List[str]] = None,
    max_revise_rounds: int = 1,
    task_timeout: float = 300.0,
    handler: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Run the Planner -> Coders -> Reviewer -> (revise)* pipeline.

    `handler` is injectable for testing: a callable(SubagentTask) -> str
    (json), same shape `tools.delegate_tool._create_subagent_handler`
    produces. Defaults to the real one (an actual sub-agent AI call)
    when not given — tests always pass a fake.
    """
    from tools.delegate_tool import SubagentTask, get_subagent_pool, _create_subagent_handler

    if not goal or not goal.strip():
        return {"error": "goal is required"}

    toolsets = toolsets or ["file", "terminal"]
    pool = get_subagent_pool()
    run_handler = handler or _create_subagent_handler(None)

    def _run_one(task_id: str, task_goal: str, role_prompt: str,
                 task_toolsets: List[str], extra_context: str = "") -> "SubagentTask":
        task = SubagentTask(
            task_id=task_id,
            goal=task_goal,
            context={"role_prompt": role_prompt, "extra_context": extra_context} if extra_context
                     else {"role_prompt": role_prompt},
            toolsets=task_toolsets,
            timeout=task_timeout,
        )
        pool.submit(task, run_handler)
        pool.wait_for([task_id], timeout=task_timeout)
        return pool.get_task(task_id)

    def _run_many(specs: List[Dict[str, Any]]) -> List["SubagentTask"]:
        submitted = []
        for spec in specs:
            task = SubagentTask(
                task_id=spec["task_id"],
                goal=spec["goal"],
                context={"role_prompt": CODER_SYSTEM_PROMPT, **({"extra_context": spec["extra_context"]}
                          if spec.get("extra_context") else {})},
                toolsets=toolsets,
                timeout=task_timeout,
            )
            pool.submit(task, run_handler)
            submitted.append(task)
        pool.wait_for([t.task_id for t in submitted], timeout=task_timeout * max(1, len(submitted)))
        return [pool.get_task(t.task_id) for t in submitted]

    # ---- Phase 1: plan ----
    plan_task = _run_one(
        f"plan_{uuid.uuid4().hex[:8]}",
        f"Goal: {goal}",
        PLANNER_SYSTEM_PROMPT,
        task_toolsets=[],
    )
    if plan_task is None or plan_task.status != "completed":
        return {"error": f"planning phase failed: {getattr(plan_task, 'error', 'unknown error')}"}

    plan_payload = json.loads(plan_task.result) if plan_task.result else {}
    subtasks = _parse_subtask_list(plan_payload.get("result", "") if isinstance(plan_payload, dict) else "")
    if not subtasks:
        return {"error": "planner did not return a usable subtask list",
                 "raw_plan_output": plan_payload}

    # ---- Phase 2: implement (parallel) ----
    coder_tasks = _run_many([
        {"task_id": f"code_{i}_{uuid.uuid4().hex[:6]}", "goal": st}
        for i, st in enumerate(subtasks)
    ])
    coder_results = _summarize_tasks(coder_tasks)

    # ---- Phase 3+: review, bounded revise loop ----
    review_history: List[Dict[str, Any]] = []
    round_num = 0
    for round_num in range(max_revise_rounds + 1):
        review_task = _run_one(
            f"review_{round_num}_{uuid.uuid4().hex[:6]}",
            f"Original goal: {goal}\n\nSubtask results:\n" +
            "\n".join(f"- {r['subtask']}: {r['summary']}" for r in coder_results),
            REVIEWER_SYSTEM_PROMPT,
            task_toolsets=[],
        )
        if review_task is None or review_task.status != "completed":
            review_history.append({"approved": False, "issues": [],
                                    "error": getattr(review_task, "error", "review failed")})
            break
        review_payload = json.loads(review_task.result) if review_task.result else {}
        review = _parse_review(review_payload.get("result", "") if isinstance(review_payload, dict) else "")
        review_history.append(review)

        if review["approved"] or round_num == max_revise_rounds or not review["issues"]:
            break

        coder_tasks = _run_many([
            {"task_id": f"revise_{round_num}_{i}_{uuid.uuid4().hex[:6]}",
             "goal": issue, "extra_context": f"Revision round {round_num + 1}. Original goal: {goal}"}
            for i, issue in enumerate(review["issues"])
        ])
        coder_results = _summarize_tasks(coder_tasks)

    return {
        "goal": goal,
        "subtasks": subtasks,
        "coder_results": coder_results,
        "review_rounds": review_history,
        "approved": bool(review_history) and review_history[-1].get("approved", False),
        "rounds_used": round_num + 1,
    }


def _summarize_tasks(tasks: List["Any"]) -> List[Dict[str, Any]]:
    out = []
    for t in tasks:
        if t is None:
            continue
        summary = ""
        if t.status == "completed" and t.result:
            try:
                payload = json.loads(t.result)
                summary = payload.get("result", "") if isinstance(payload, dict) else str(payload)
            except json.JSONDecodeError:
                summary = t.result
        out.append({
            "subtask": t.goal, "task_id": t.task_id, "status": t.status,
            "summary": summary, "error": t.error,
        })
    return out


# ───────────────────────────────────────────────────────────── CLI surface

def handle_command(args) -> int:
    """CLI entry: `minxg ext multiagent <subcommand>`."""
    subcmd = getattr(args, "multiagent_subcommand", None)
    if subcmd == "run":
        return _cli_run(args)
    print("multiagent sub-commands:")
    print('  run "<goal>" [--max-revise-rounds N] [--toolsets file,terminal]')
    return 0


def _cli_run(args) -> int:
    goal = getattr(args, "goal", "") or ""
    if not goal.strip():
        print("error: goal is required")
        return 1
    toolsets = [t.strip() for t in getattr(args, "toolsets", "file,terminal").split(",") if t.strip()]
    max_rounds = getattr(args, "max_revise_rounds", 1)

    print(f"Planning: {goal}")
    result = run_coding_crew(goal, toolsets=toolsets, max_revise_rounds=max_rounds)
    if "error" in result:
        print(f"error: {result['error']}")
        return 1

    print(f"\nSubtasks ({len(result['subtasks'])}):")
    for st in result["subtasks"]:
        print(f"  - {st}")
    print(f"\nRounds used: {result['rounds_used']}  Approved: {result['approved']}")
    for r in result["coder_results"]:
        print(f"\n[{r['status']}] {r['subtask']}")
        if r["summary"]:
            print(f"  {r['summary'][:300]}")
        if r["error"]:
            print(f"  error: {r['error']}")
    return 0 if result["approved"] else 2


def register_cli(subparsers) -> None:
    p = subparsers.add_parser(
        "multiagent",
        help="multi-agent coding crew (opt-in via `minxg ext add minxg-multiagent`)",
    )
    sp = p.add_subparsers(dest="multiagent_subcommand")
    run = sp.add_parser("run", help="run the planner/coder/reviewer pipeline on a goal")
    run.add_argument("goal", help="the coding goal to accomplish")
    run.add_argument("--toolsets", default="file,terminal",
                      help="comma-separated toolsets for coder sub-agents")
    run.add_argument("--max-revise-rounds", type=int, default=1,
                      help="bound on reviewer-triggered revise rounds")


# ─────────────────────────────────────────────────────────── chat-agent tool

MULTI_AGENT_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string", "description": "The coding goal to accomplish"},
        "toolsets": {"type": "array", "items": {"type": "string"},
                     "description": "Toolsets available to coder sub-agents", "default": ["file", "terminal"]},
        "max_revise_rounds": {"type": "integer", "default": 1,
                               "description": "Bound on reviewer-triggered revise rounds"},
    },
    "required": ["goal"],
}


def _handle_multi_agent_code_task(args: dict) -> str:
    result = run_coding_crew(
        args.get("goal", ""),
        toolsets=args.get("toolsets") or ["file", "terminal"],
        max_revise_rounds=args.get("max_revise_rounds", 1),
    )
    return json.dumps(result)


def register_hooks(registry) -> None:
    """Real tool registration — see the module docstring for why this
    is now actually reachable from a live chat session."""
    registry.register(
        name="multi_agent_code_task",
        toolset="multiagent",
        schema=MULTI_AGENT_TASK_SCHEMA,
        handler=_handle_multi_agent_code_task,
        check_fn=lambda: True,
        emoji="",
        max_result_size_chars=100000,
    )
