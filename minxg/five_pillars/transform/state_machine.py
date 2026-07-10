"""
create_state_machine, add_transition, send_event, get_state_machine,
reset_state_machine, get_stats
"""
from __future__ import annotations
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Any, Callable, Optional
from minxg.base import BaseWorker, tool


@dataclass
class StateTransition:
    from_state: Any
    event: Any
    to_state: Any
    guard: Optional[Callable[[Any, Any], bool]] = None


class StateMachine:
    def __init__(self, name: str, initial: Any):
        self.name = name
        self.current = initial
        self.initial = initial
        self._transitions: List[StateTransition] = []
        self._listeners: List[Callable] = []
        self._history: List[Dict] = []

    def add_transition(self, from_state: Any, event: Any, to_state: Any) -> "StateMachine":
        self._transitions.append(StateTransition(from_state, event, to_state))
        return self

    def add_guarded_transition(self, from_state: Any, event: Any, to_state: Any,
                               guard: Callable[[Any, Any], bool]) -> "StateMachine":
        self._transitions.append(StateTransition(from_state, event, to_state, guard))
        return self

    def on_change(self, listener: Callable) -> "StateMachine":
        self._listeners.append(listener)
        return self

    def send(self, event: Any) -> bool:
        for t in self._transitions:
            if t.from_state == self.current and t.event == event:
                if t.guard and not t.guard(self.current, event):
                    return False
                old = self.current
                self.current = t.to_state
                rec = {"from": old, "event": event, "to": self.current, "at": time.time()}
                self._history.append(rec)
                for cb in self._listeners:
                    try: cb(rec)
                    except Exception: pass
                return True
        return False

    def reset(self):
        self.current = self.initial
        self._history.clear()

    def info(self) -> Dict:
        return {"name": self.name, "current": self.current, "initial": self.initial,
                "transitions": len(self._transitions), "history": self._history[-20:]}


class StateMachineWorker(BaseWorker):
    facade_alias = "state_machine"
    worker_id = "state_machine"
    version = "0.17.0"

    def __init__(self):
        self._semantic: Dict[str, Dict] = {}
        self._machines: Dict[str, StateMachine] = {}
        self._start_time = time.time()
        self.tools: Dict = {}
        self._register_tools()

    @tool(description="Store semantic memory (key/value/category/confidence/source/tags)", category="memory")
    async def store_semantic(self, key: str, value: str, category: str = "general",
                           confidence: float = 1.0, source: str = "",
                           tags: list = None) -> Dict:
        self._semantic[key] = {
            "value": value, "category": category, "confidence": confidence,
            "source": source, "tags": tags or [], "at": time.time(),
        }
        return {"key": key, "stored": True}

    @tool(description="Retrieve semantic memory", category="memory")
    async def recall_semantic(self, key: str) -> Dict:
        m = self._semantic.get(key)
        if not m:
            return {"key": key, "found": False}
        return {"key": key, "found": True, **m}

    @tool(description="List all semantic memories by category", category="memory")
    async def list_semantic(self, category: str = "") -> Dict:
        results = [{"key": k, **v} for k, v in self._semantic.items()
                   if not category or v.get("category") == category]
        return {"count": len(results), "items": results}

    @tool(description="Create state machine, return machine_id", category="statemachine")
    async def create_state_machine(self, name: str, initial: str) -> Dict:
        if name in self._machines:
            return {"error": f"machine exists: {name}"}
        self._machines[name] = StateMachine(name, initial)
        return {"machine_id": name, "initial": initial, "created": True}

    @tool(description="Add transition rule to state machine", category="statemachine")
    async def add_transition(self, machine_id: str, from_state: str,
                           event: str, to_state: str) -> Dict:
        m = self._machines.get(machine_id)
        if not m:
            return {"error": f"machine not found: {machine_id}"}
        m.add_transition(from_state, event, to_state)
        return {"machine_id": machine_id, "transitions": len(m._transitions)}

    @tool(description="Send event to state machine, trigger transition", category="statemachine")
    async def send_event(self, machine_id: str, event: str) -> Dict:
        m = self._machines.get(machine_id)
        if not m:
            return {"error": f"machine not found: {machine_id}"}
        ok = m.send(event)
        return {"machine_id": machine_id, "event": event, "accepted": ok, "current": m.current}

    @tool(description="View state machine details", category="statemachine")
    async def get_state_machine(self, machine_id: str) -> Dict:
        m = self._machines.get(machine_id)
        if not m:
            return {"error": f"machine not found: {machine_id}"}
        return m.info()

    @tool(description="Reset state machine to initial state", category="statemachine")
    async def reset_state_machine(self, machine_id: str) -> Dict:
        m = self._machines.get(machine_id)
        if not m:
            return {"error": f"machine not found: {machine_id}"}
        m.reset()
        return {"machine_id": machine_id, "reset": True, "current": m.current}

    @tool(description="Get worker statistics", category="info")
    async def get_stats(self) -> Dict:
        return {
            "semantic": len(self._semantic),
            "machines": len(self._machines),
            "uptime_sec": round(time.time() - self._start_time, 2),
        }
