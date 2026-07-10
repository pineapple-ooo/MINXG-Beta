"""
breaker_record_failure, breaker_info, breaker_reset, create_phaser,
phaser_arrive_and_await, counter_incr, counter_get, list_all
"""
from __future__ import annotations
import time
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict
from minxg.base import BaseWorker, tool


class CircuitBreaker:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout: float = 30.0, success_threshold: int = 2):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.state = self.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at = None
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0

    def allow(self) -> bool:
        self._total_calls += 1
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if self._opened_at and (time.time() - self._opened_at) >= self.recovery_timeout:
                self.state = self.HALF_OPEN
                self._successes = 0
                return True
            return False
        return True

    def record_success(self):
        self._total_successes += 1
        if self.state == self.HALF_OPEN:
            self._successes += 1
            if self._successes >= self.success_threshold:
                self.state = self.CLOSED
                self._failures = 0
        elif self.state == self.CLOSED:
            self._failures = max(0, self._failures - 1)

    def record_failure(self):
        self._total_failures += 1
        self._failures += 1
        if self.state == self.HALF_OPEN:
            self.state = self.OPEN
            self._opened_at = time.time()
        elif self.state == self.CLOSED and self._failures >= self.failure_threshold:
            self.state = self.OPEN
            self._opened_at = time.time()

    def reset(self):
        self.state = self.CLOSED
        self._failures = 0
        self._successes = 0
        self._opened_at = None

    def info(self) -> Dict:
        return {"name": self.name, "state": self.state, "failures": self._failures,
                "successes_in_half_open": self._successes,
                "opened_at": self._opened_at,
                "threshold": self.failure_threshold,
                "recovery_timeout": self.recovery_timeout,
                "stats": {"calls": self._total_calls,
                          "successes": self._total_successes,
                          "failures": self._total_failures}}


class _Phaser:
    def __init__(self, parties: int):
        self.parties = parties
        self.phase = 0
        self._arrived = 0
        self._cond = asyncio.Condition()

    async def arrive_and_wait(self):
        async with self._cond:
            self._arrived += 1
            if self._arrived >= self.parties:
                self.phase += 1
                self._arrived = 0
                self._cond.notify_all()
            else:
                await self._cond.wait_for(lambda: self._arrived == 0)


class LimitsBreakWorker(BaseWorker):
    worker_id = "limits_break"
    version = "0.16.0"

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._phasers: Dict[str, _Phaser] = {}
        self._counters: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()
        self.tools: Dict = {}
        self._register_tools()

    @tool(description="Create circuit breaker", category="breaker")
    async def create_breaker(self, name: str, failure_threshold: int = 5,
                            recovery_timeout: float = 30.0,
                            success_threshold: int = 2) -> Dict:
        if name in self._breakers:
            return {"error": f"breaker exists: {name}"}
        self._breakers[name] = CircuitBreaker(name, failure_threshold,
                                              recovery_timeout, success_threshold)
        return {"breaker_id": name, "created": True,
                "failure_threshold": failure_threshold,
                "recovery_timeout": recovery_timeout}

    @tool(description="Check if request allowed (not tripped)", category="breaker")
    async def breaker_allow(self, name: str) -> Dict:
        b = self._breakers.get(name)
        if not b:
            return {"error": f"breaker not found: {name}"}
        return {"allowed": b.allow(), "breaker": name, "state": b.state}

    @tool(description="Record success", category="breaker")
    async def breaker_record_success(self, name: str) -> Dict:
        b = self._breakers.get(name)
        if not b:
            return {"error": f"breaker not found: {name}"}
        b.record_success()
        return {"recorded": "success", "breaker": name, "state": b.state}

    @tool(description="Record failure", category="breaker")
    async def breaker_record_failure(self, name: str) -> Dict:
        b = self._breakers.get(name)
        if not b:
            return {"error": f"breaker not found: {name}"}
        b.record_failure()
        return {"recorded": "failure", "breaker": name, "state": b.state,
                "failures": b._failures}

    @tool(description="View circuit breaker status", category="breaker")
    async def breaker_info(self, name: str) -> Dict:
        b = self._breakers.get(name)
        if not b:
            return {"error": f"breaker not found: {name}"}
        return b.info()

    @tool(description="Reset circuit breaker", category="breaker")
    async def breaker_reset(self, name: str) -> Dict:
        b = self._breakers.get(name)
        if not b:
            return {"error": f"breaker not found: {name}"}
        b.reset()
        return {"reset": True, "breaker": name}

    @tool(description="Create Phaser (waits for all parties)", category="phaser")
    async def create_phaser(self, name: str, parties: int) -> Dict:
        if name in self._phasers:
            return {"error": f"phaser exists: {name}"}
        self._phasers[name] = _Phaser(parties)
        return {"phaser_id": name, "parties": parties, "created": True}

    @tool(description="Phaser await (wait for all parties)", category="phaser")
    async def phaser_arrive_and_await(self, name: str, timeout: float = 30.0) -> Dict:
        p = self._phasers.get(name)
        if not p:
            return {"error": f"phaser not found: {name}"}
        try:
            await asyncio.wait_for(p.arrive_and_wait(), timeout=timeout)
            return {"arrived": True, "phaser": name, "phase": p.phase}
        except asyncio.TimeoutError:
            return {"arrived": False, "error": "timeout", "phaser": name}

    @tool(description="Atomic counter increment", category="counter")
    async def counter_incr(self, name: str, delta: int = 1) -> Dict:
        self._counters[name] += delta
        return {"counter": name, "value": self._counters[name]}

    @tool(description="Read counter value", category="counter")
    async def counter_get(self, name: str) -> Dict:
        return {"counter": name, "value": self._counters.get(name, 0)}

    @tool(description="List all named primitives", category="info")
    async def list_all(self) -> Dict:
        return {
            "breakers": list(self._breakers.keys()),
            "phasers": list(self._phasers.keys()),
            "counters": dict(self._counters),
            "uptime_sec": round(time.time() - self._start_time, 2),
        }
