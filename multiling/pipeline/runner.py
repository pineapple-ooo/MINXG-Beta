"""pipeline.runner — Composable stage pipelines with retry and cancel.

A Pipeline is an ordered list of Stage objects. Each Stage is any callable
that takes the running payload and returns a new payload. Add middleware
hooks (before/after) for observability without coupling to a Stage.
""""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional, Tuple, Union

SyncFn = Callable[[Any], Any]
AsyncFn = Callable[[Any], Awaitable[Any]]
StageFn = Union[SyncFn, AsyncFn]


@dataclass
class Stage:
    name: str
    process: StageFn
    retries: int = 0
    timeout: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    def __call__(self, data: Any) -> Any:
        return self.process(data)


class Pipeline:
    def __init__(self, name: str, stages: Optional[List[Stage]] = None) -> None:
        self.name = name
        self.stages: List[Stage] = list(stages or [])
        self._before: List[Callable[[str, Any], Any]] = []
        self._after: List[Callable[[str, Any], Any]] = []
        self._cancel = False

    def add(self, stage: Stage) -> "Pipeline":
        self.stages.append(stage)
        return self

    def before(self, fn: Callable[[str, Any], Any]) -> "Pipeline":
        self._before.append(fn)
        return self

    def after(self, fn: Callable[[str, Any], Any]) -> "Pipeline":
        self._after.append(fn)
        return self

    def cancel(self) -> None:
        self._cancel = True

    def run(self, data: Any) -> Any:
        payload = data
        for hook in self._before:
            hook(self.name, payload)
        for stage in self.stages:
            if self._cancel:
                raise PipelineCancelled(self.name, stage.name)
            payload = self._run_stage(stage, payload)
            for hook in self._after:
                hook(stage.name, payload)
        return payload

    async def arun(self, data: Any) -> Any:
        payload = data
        for hook in self._before:
            result = hook(self.name, payload)
            if asyncio.iscoroutine(result):
                await result
        for stage in self.stages:
            if self._cancel:
                raise PipelineCancelled(self.name, stage.name)
            payload = await self._arun_stage(stage, payload)
            for hook in self._after:
                result = hook(stage.name, payload)
                if asyncio.iscoroutine(result):
                    await result
        return payload

    def _run_stage(self, stage: Stage, payload: Any) -> Any:
        attempt = 0
        while True:
            try:
                return stage.process(payload)
            except Exception as exc:
                attempt += 1
                if attempt > stage.retries:
                    raise
                time.sleep(min(0.05 * attempt, 0.5))

    async def _arun_stage(self, stage: Stage, payload: Any) -> Any:
        attempt = 0
        while True:
            try:
                if asyncio.iscoroutinefunction(stage.process):
                    coro = stage.process(payload)
                else:
                    coro = asyncio.to_thread(stage.process, payload)
                if stage.timeout:
                    return await asyncio.wait_for(coro, timeout=stage.timeout)
                return await coro
            except Exception:
                attempt += 1
                if attempt > stage.retries:
                    raise
                await asyncio.sleep(min(0.05 * attempt, 0.5))


class PipelineCancelled(RuntimeError):
    def __init__(self, pipeline: str, stage: str) -> None:
        super().__init__(f"pipeline {pipeline!r} cancelled at stage {stage!r}")
        self.pipeline = pipeline
        self.stage = stage


def run_pipeline(stages: List[Stage], data: Any) -> Any:
    return Pipeline("ad-hoc", stages).run(data)


def parallel(stages: List[Stage]) -> Stage:
    """Build a single Stage that invokes the given stages concurrently.""""
    async def _runner(data: Any) -> List[Any]:
        return await asyncio.gather(*[asyncio.to_thread(s, data) for s in stages])
    return Stage("parallel", _runner)
