#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
src.ai.memory.working_memory — short-horizon context buffer for active
turns.

Working memory sits above the entropic engine. It holds the
currently-unfolding conversation payload: the last user message, the
in-flight assistant message, the pending tool calls and their
results. Other code reads from it to prime the next prompt with
flawless context, even after arbitrary loops vanish from view.

Public surface:
    get_working_memory() -> WorkingMemory
    WorkingMemory.prime(text, role="user") -> None
    WorkingMemory.push_tool(name, args, result) -> None
    WorkingMemory.snapshot() -> dict
    WorkingMemory.turns_in_window -> int
"""
from __future__ import annotations

import collections
import dataclasses as dc
import json
import logging
import threading
import time
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("src.ai.memory.working")


@dc.dataclass
class Turn:
    role: str          # "user" | "assistant" | "tool" | "system"
    text: str
    ts: float
    meta: Dict[str, Any] = dc.field(default_factory=dict)


class WorkingMemory:
    """Thread-safe rolling buffer of the current conversation."""

    def __init__(self, *, capacity: int = 64) -> None:
        if capacity < 1:
            capacity = 1
        self._cap = capacity
        self._items: Deque[Turn] = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._pending_tool_calls: List[Dict[str, Any]] = []

    # -- mutations --

    def prime(self, text: str, *, role: str = "user",
              meta: Optional[Dict[str, Any]] = None) -> None:
        if text is None:
            return
        t = Turn(role=role, text=text, ts=time.time(), meta=dict(meta or {}))
        with self._lock:
            self._items.append(t)

    def push_tool(self, name: str, args: Dict[str, Any], result: Any) -> None:
        meta = {
            "name": name,
            "args": args if isinstance(args, dict) else {"_": args},
            "result": result,
            "ts": time.time(),
        }
        with self._lock:
            self._pending_tool_calls.append(meta)
            self._items.append(Turn(role="tool", text=f"tool:{name}", ts=time.time(),
                                     meta=meta))

    def mark_tool_call_started(self, name: str, args: Dict[str, Any]) -> None:
        with self._lock:
            self._pending_tool_calls.append({
                "name": name,
                "args": args if isinstance(args, dict) else {"_": args},
                "ts": time.time(),
                "result": None,
            })

    # -- reads --

    @property
    def turns_in_window(self) -> int:
        return len(self._items)

    @property
    def pending_tool_calls(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._pending_tool_calls)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "turns": [dc.asdict(t) for t in self._items],
                "pending_tools": list(self._pending_tool_calls),
                "capacity": self._cap,
            }

    def serialised_for_prompt(self, max_chars: int = 12_000) -> str:
        """Render the conversation as a flat prompt-friendly string."""
        with self._lock:
            turns = list(self._items)
        out: List[str] = []
        total = 0
        for t in turns:
            line = f"[{t.role}] {t.text}".strip()
            total += len(line)
            if total > max_chars:
                break
            out.append(line)
        return "\n".join(out)

    def reset(self) -> None:
        with self._lock:
            self._items.clear()
            self._pending_tool_calls.clear()


# ──────────────── singleton ────────────────────────────

_WM: Optional[WorkingMemory] = None
_WM_LOCK = threading.Lock()


def get_working_memory() -> WorkingMemory:
    global _WM
    with _WM_LOCK:
        if _WM is None:
            _WM = WorkingMemory()
        return _WM


def reset_working_memory_for_tests() -> None:
    """Drop the singleton — unit-test convenience."""
    global _WM
    with _WM_LOCK:
        _WM = None


# ──────────────── self-test ────────────────────────────


def _self_check() -> int:  # pragma: no cover — `python -m`
    w = WorkingMemory(capacity=8)
    w.prime("hello", role="user")
    w.prime("hi", role="assistant")
    w.mark_tool_call_started("shell", {"cmd": "ls"})
    w.push_tool("shell", {"cmd": "ls"}, {"out": "a\nb\n"})
    assert w.turns_in_window == 3, w.turns_in_window
    assert w.pending_tool_calls, w.pending_tool_calls
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_self_check())
