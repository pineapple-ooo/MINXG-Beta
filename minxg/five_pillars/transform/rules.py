"""

"""
from __future__ import annotations
import re
import time
import asyncio
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Any, Callable, Union
from minxg.base import BaseWorker, tool




def eq(field: str, value: Any) -> Callable[[Dict], bool]:
    return lambda ctx: ctx.get(field) == value

def ne(field: str, value: Any) -> Callable[[Dict], bool]:
    return lambda ctx: ctx.get(field) != value

def gt(field: str, value: Any) -> Callable[[Dict], bool]:
    return lambda ctx: ctx.get(field) is not None and ctx.get(field) > value

def lt(field: str, value: Any) -> Callable[[Dict], bool]:
    return lambda ctx: ctx.get(field) is not None and ctx.get(field) < value

def ge(field: str, value: Any) -> Callable[[Dict], bool]:
    return lambda ctx: ctx.get(field) is not None and ctx.get(field) >= value

def le(field: str, value: Any) -> Callable[[Dict], bool]:
    return lambda ctx: ctx.get(field) is not None and ctx.get(field) <= value

def in_(field: str, options: list) -> Callable[[Dict], bool]:
    s = set(options)
    return lambda ctx: ctx.get(field) in s

def regex(field: str, pattern: str, flags: int = 0) -> Callable[[Dict], bool]:
    rx = re.compile(pattern, flags)
    def _check(ctx) -> bool:
        v = ctx.get(field)
        return bool(v and rx.search(str(v)))
    return _check

def contains(field: str, substring: str) -> Callable[[Dict], bool]:
    return lambda ctx: substring in str(ctx.get(field, ""))

def all_(*conds: Callable) -> Callable[[Dict], bool]:
    def _check(ctx) -> bool:
        return all(c(ctx) for c in conds)
    return _check

def any_(*conds: Callable) -> Callable[[Dict], bool]:
    def _check(ctx) -> bool:
        return any(c(ctx) for c in conds)
    return _check

def not_(cond: Callable) -> Callable[[Dict], bool]:
    return lambda ctx: not cond(ctx)





class RulesWorker(BaseWorker):
    facade_alias = "rules"
    worker_id = "rules"
    version = "0.17.1"

    def __init__(self):
        self._rules: Dict[str, Dict] = {}     
        self._groups: Dict[str, set] = defaultdict(set)
        self._history: List[Dict] = []
        self._max_iterations = 100
        self._stop_on_first = False
        self._execution_count = 0
        self._match_count = 0
        self._start_time = time.time()
        self.tools: Dict = {}
        self._register_tools()

        self.eq = eq
        self.ne = ne
        self.gt = gt
        self.lt = lt
        self.ge = ge
        self.le = le
        self.in_ = in_
        self.regex = regex
        self.contains = contains
        self.all_ = all_
        self.any_ = any_
        self.not_ = not_

    @tool(description="Register a rule (condition is Python expr, action is statement)",
          category="register")
    async def register(self, name: str, condition_expr: str = "True",
                      action_expr: str = "pass", priority: int = 100,
                      group: str = "default") -> Dict:
        """
          action_expr:    "ctx['hit'] = True; ctx['count'] = ctx.get('count', 0) + 1"
        """
        try:
            cond = compile(f"lambda ctx: bool({condition_expr})", f"<cond:{name}>", "eval")
            cond_fn = eval(cond)
        except Exception as e:
            return {"error": f"invalid condition_expr: {e}"}
        try:
            action_src = f"def _act(ctx):\n    {action_expr.replace(chr(10), chr(10) + '    ')}"
            exec_globals = {}
            exec(action_src, exec_globals)
            act_fn = exec_globals["_act"]
        except Exception as e:
            return {"error": f"invalid action_expr: {e}"}

        return await self._register_internal(name, cond_fn, act_fn, priority, group)

    async def _register_internal(self, name: str, condition_fn: Callable,
                                action_fn: Callable, priority: int = 100,
                                group: str = "default") -> Dict:
        rule_id = f"rule-{uuid.uuid4().hex[:8]}"
        self._rules[rule_id] = {
            "rule_id": rule_id, "name": name, "priority": priority,
            "condition": condition_fn, "action": action_fn,
            "enabled": True, "group": group, "hits": 0, "added_at": time.time(),
        }
        self._groups[group].add(rule_id)
        return {"rule_id": rule_id, "name": name, "group": group, "added": True}

    @tool(description="List all rules", category="info")
    async def list_rules(self, group: str = "") -> Dict:
        rules = []
        for rid, r in self._rules.items():
            if group and r["group"] != group:
                continue
            rules.append({"rule_id": rid, "name": r["name"], "priority": r["priority"],
                          "group": r["group"], "enabled": r["enabled"], "hits": r["hits"]})
        rules.sort(key=lambda x: -x["priority"])
        return {"count": len(rules), "rules": rules}

    @tool(description="Enable/disable rules", category="info")
    async def set_enabled(self, rule_id: str, enabled: bool) -> Dict:
        r = self._rules.get(rule_id)
        if not r:
            return {"error": f"rule not found: {rule_id}"}
        r["enabled"] = enabled
        return {"rule_id": rule_id, "enabled": enabled}

    @tool(description="Delete rules", category="info")
    async def remove_rule(self, rule_id: str) -> Dict:
        r = self._rules.pop(rule_id, None)
        if r:
            self._groups[r["group"]].discard(rule_id)
        return {"rule_id": rule_id, "deleted": r is not None}

    @tool(description="Clear all rules in a group", category="info")
    async def clear_group(self, group: str) -> Dict:
        n = len(self._groups[group])
        for rid in list(self._groups[group]):
            self._rules.pop(rid, None)
        self._groups[group].clear()
        return {"group": group, "removed": n}

    @tool(description="Execute rule engine: match context, trigger actions, return modified copy",
          category="execute")
    async def evaluate(self, context: dict, group: str = "default",
                     stop_on_first: bool = False, max_iterations: int = 100,
                     return_context: bool = True) -> Dict:
        rule_ids = self._groups.get(group, set())
        if not rule_ids:
            return {"matched": [], "actions_run": 0, "iterations": 0,
                    "context": context if return_context else None}

        rules = sorted([self._rules[rid] for rid in rule_ids if self._rules[rid]["enabled"]],
                       key=lambda r: -r["priority"])

        matched = []
        actions_run = 0
        for it in range(min(max_iterations, len(rules))):
            r = rules[it]
            try:
                cond = r["condition"]
                if asyncio.iscoroutinefunction(cond):
                    cond_ok = await cond(context)
                else:
                    cond_ok = cond(context)
                if cond_ok:
                    r["hits"] += 1
                    self._match_count += 1
                    matched.append({"rule_id": r["rule_id"], "name": r["name"]})
                    try:
                        act = r["action"]
                        if asyncio.iscoroutinefunction(act):
                            await act(context)
                        else:
                            act(context)
                    except Exception as e:
                        matched[-1]["action_error"] = str(e)
                    actions_run += 1
                    self._execution_count += 1
                    if stop_on_first:
                        break
            except Exception as e:
                self._history.append({"rule_id": r["rule_id"], "error": str(e),
                                      "at": time.time()})
        return {"matched": matched, "actions_run": actions_run,
                "iterations": it + 1 if rules else 0, "group": group,
                "context": context if return_context else None}

    @tool(description="Batch register rules from JSON schema",
          category="register")
    async def register_batch(self, rules: list, group: str = "default") -> Dict:
        """
        rules: [
          {"name": "...", "condition_expr": "ctx['x'] > 0",
           "action_expr": "ctx['result'] = 'matched'", "priority": 100},
          ...
        ]
        """
        added = []
        for r in rules:
            res = await self.register(
                name=r["name"],
                condition_expr=r.get("condition_expr", "True"),
                action_expr=r.get("action_expr", "None"),
                priority=r.get("priority", 100),
                group=group,
            )
            if "rule_id" in res:
                added.append(res["rule_id"])
        return {"count": len(added), "rule_ids": added, "group": group}

    @tool(description="Engine statistics", category="info")
    async def stats(self) -> Dict:
        return {
            "total_rules": len(self._rules),
            "groups": {g: len(rid_set) for g, rid_set in self._groups.items()},
            "total_executions": self._execution_count,
            "total_matches": self._match_count,
            "uptime_sec": round(time.time() - self._start_time, 2),
        }

    @tool(description="View recent N execution history (including errors)", category="info")
    async def history(self, limit: int = 20) -> Dict:
        return {"count": len(self._history), "items": self._history[-limit:]}
