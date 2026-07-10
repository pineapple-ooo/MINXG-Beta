"""
with_write_lock, create_semaphore, acquire, release, create_barrier, barrier_wait
"""
from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import Dict
from minxg.base import BaseWorker, tool


class _RWLock:
    def __init__(self):
        self._readers = 0
        self._write_lock = asyncio.Lock()
        self._reader_lock = asyncio.Lock()

    def read(self):
        return _ReaderGuard(self)

    def write(self):
        return _WriterGuard(self)


class _ReaderGuard:
    def __init__(self, rw: _RWLock):
        self.rw = rw

    async def __aenter__(self):
        await self.rw._reader_lock.acquire()
        self.rw._readers += 1
        if self.rw._readers == 1:
            await self.rw._write_lock.acquire()
        self.rw._reader_lock.release()
        return self

    async def __aexit__(self, *args):
        await self.rw._reader_lock.acquire()
        self.rw._readers -= 1
        if self.rw._readers == 0:
            self.rw._write_lock.release()
        self.rw._reader_lock.release()


class _WriterGuard(_ReaderGuard):
    async def __aenter__(self):
        await self.rw._write_lock.acquire()
        return self

    async def __aexit__(self, *args):
        self.rw._write_lock.release()


class _Barrier:
    def __init__(self, parties: int):
        self.parties = parties
        self.passes = 0
        self._arrived = 0
        self._cond = asyncio.Condition()

    async def wait(self):
        async with self._cond:
            self._arrived += 1
            if self._arrived >= self.parties:
                self.passes += 1
                self._arrived = 0
                self._cond.notify_all()
            else:
                await self._cond.wait_for(lambda: self._arrived == 0)


class LimitsLockWorker(BaseWorker):
    worker_id = "limits_lock"
    version = "0.16.0"

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._read_write_locks: Dict[str, _RWLock] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._barriers: Dict[str, _Barrier] = {}
        self.tools: Dict = {}
        self._register_tools()

    @tool(description="Get/create named mutex", category="lock")
    async def get_lock(self, name: str) -> Dict:
        if name not in self._locks:
            self._locks[name] = asyncio.Lock()
        return {"lock_id": name, "created": True}

    @tool(description="Execute with lock", category="lock")
    async def with_lock(self, lock_name: str, fn_name: str = "", args: dict = None) -> Dict:
        lock = self._locks.get(lock_name)
        if not lock:
            return {"error": f"lock not found: {lock_name}"}
        async with lock:
            return {"locked": True, "lock_name": lock_name, "fn": fn_name,
                    "args": args or {}, "executed_at": __import__("time").time()}

    @tool(description="Create read-write lock", category="lock")
    async def create_read_write_lock(self, name: str) -> Dict:
        if name not in self._read_write_locks:
            self._read_write_locks[name] = _RWLock()
        return {"rwlock_id": name, "created": True}

    @tool(description="Acquire read lock (concurrent reads supported)", category="lock")
    async def with_read_lock(self, lock_name: str, fn_name: str = "") -> Dict:
        rw = self._read_write_locks.get(lock_name)
        if not rw:
            return {"error": f"rwlock not found: {lock_name}"}
        async with rw.read():
            return {"locked": "read", "lock_name": lock_name, "fn": fn_name}

    @tool(description="Acquire write lock (exclusive)", category="lock")
    async def with_write_lock(self, lock_name: str, fn_name: str = "") -> Dict:
        rw = self._read_write_locks.get(lock_name)
        if not rw:
            return {"error": f"rwlock not found: {lock_name}"}
        async with rw.write():
            return {"locked": "write", "lock_name": lock_name, "fn": fn_name}

    @tool(description="Create semaphore (rate limiting)", category="semaphore")
    async def create_semaphore(self, name: str, permits: int = 1) -> Dict:
        if name in self._semaphores:
            return {"error": f"semaphore exists: {name}"}
        self._semaphores[name] = asyncio.Semaphore(permits)
        return {"semaphore_id": name, "permits": permits, "created": True}

    @tool(description="Acquire semaphore permit (blocks up to timeout)", category="semaphore")
    async def acquire(self, name: str, timeout: float = 5.0) -> Dict:
        sem = self._semaphores.get(name)
        if not sem:
            return {"error": f"semaphore not found: {name}"}
        try:
            await asyncio.wait_for(sem.acquire(), timeout=timeout)
            return {"acquired": True, "semaphore": name}
        except asyncio.TimeoutError:
            return {"acquired": False, "error": "timeout", "semaphore": name}

    @tool(description="Release semaphore permit", category="semaphore")
    async def release(self, name: str) -> Dict:
        sem = self._semaphores.get(name)
        if not sem:
            return {"error": f"semaphore not found: {name}"}
        sem.release()
        return {"released": True, "semaphore": name}

    @tool(description="Create CyclicBarrier", category="barrier")
    async def create_barrier(self, name: str, parties: int) -> Dict:
        if name in self._barriers:
            return {"error": f"barrier exists: {name}"}
        self._barriers[name] = _Barrier(parties)
        return {"barrier_id": name, "parties": parties}

    @tool(description="Barrier await", category="barrier")
    async def barrier_wait(self, name: str, timeout: float = 30.0) -> Dict:
        b = self._barriers.get(name)
        if not b:
            return {"error": f"barrier not found: {name}"}
        try:
            await asyncio.wait_for(b.wait(), timeout=timeout)
            return {"arrived": True, "barrier": name, "passes": b.passes}
        except asyncio.TimeoutError:
            return {"arrived": False, "error": "timeout"}
