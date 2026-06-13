"""workflow.engine — DAG-driven workflow executor with topological ordering.""""
from __future__ import annotations
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class Step:
    name: str
    action: Callable[[Any], Any]
    depends_on: List[str] = field(default_factory=list)
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __call__(self, state: Any) -> Any:
        return self.action(state)


@dataclass
class StepResult:
    name: str
    ok: bool
    value: Any = None
    error: Optional[str] = None


class Workflow:
    def __init__(self, name: str) -> None:
        self.name = name
        self._steps: Dict[str, Step] = {}
        self._start: Optional[str] = None

    def add_step(self, step: Step, *, is_start: bool = False) -> "Workflow":
        if step.name in self._steps:
            raise ValueError(f"step {step.name!r} already exists")
        self._steps[step.name] = step
        if is_start or self._start is None:
            self._start = step.name
        return self

    def start(self, name: str) -> "Workflow":
        if name not in self._steps:
            raise KeyError(name)
        self._start = name
        return self

    def steps(self) -> List[Step]:
        return list(self._steps.values())

    def validate(self) -> None:
        for step in self._steps.values():
            for dep in step.depends_on:
                if dep not in self._steps:
                    raise ValueError(f"step {step.name!r} depends on missing {dep!r}")

    def topological_order(self) -> List[str]:
        self.validate()
        in_deg: Dict[str, int] = {n: 0 for n in self._steps}
        children: Dict[str, List[str]] = defaultdict(list)
        for step in self._steps.values():
            for dep in step.depends_on:
                children[dep].append(step.name)
                in_deg[step.name] += 1
        ready: deque = deque(n for n, d in in_deg.items() if d == 0)
        order: List[str] = []
        while ready:
            node = ready.popleft()
            order.append(node)
            for ch in children[node]:
                in_deg[ch] -= 1
                if in_deg[ch] == 0:
                    ready.append(ch)
        if len(order) != len(self._steps):
            raise ValueError(f"cycle detected in workflow {self.name!r}")
        return order

    def run(self, state: Any) -> Dict[str, StepResult]:
        results: Dict[str, StepResult] = {}
        for name in self.topological_order():
            step = self._steps[name]
            attempt = 0
            while True:
                try:
                    value = step(state)
                    results[name] = StepResult(name, True, value=value)
                    break
                except Exception as exc:
                    attempt += 1
                    if attempt > step.retries:
                        results[name] = StepResult(name, False, error=f"{type(exc).__name__}: {exc}")
                        return results
        return results

    async def arun(self, state: Any) -> Dict[str, StepResult]:
        results: Dict[str, StepResult] = {}
        for name in self.topological_order():
            step = self._steps[name]
            attempt = 0
            while True:
                try:
                    value = step(state)
                    if asyncio.iscoroutine(value):
                        value = await value
                    results[name] = StepResult(name, True, value=value)
                    break
                except Exception as exc:
                    attempt += 1
                    if attempt > step.retries:
                        results[name] = StepResult(name, False, error=f"{type(exc).__name__}: {exc}")
                        return results
        return results
