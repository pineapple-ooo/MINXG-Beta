"""scheduler.scheduler — Cron-flavoured interval scheduler with persistent state.

A `Job` is a callable + interval/expression condition. The scheduler
runs in a dedicated daemon thread, ticking every second. Each Job tracks
last-run timestamp and missed-run count.
""""
from __future__ import annotations
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class Job:
    name: str
    fn: Callable[[], None]
    interval_seconds: float = 60.0
    last_run_at: float = 0.0
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    enabled: bool = True
    metadata: dict = field(default_factory=dict)

    def is_due(self, now: float) -> bool:
        if not self.enabled:
            return False
        if self.last_run_at == 0.0:
            return True
        return (now - self.last_run_at) >= self.interval_seconds


class Scheduler:
    def __init__(self, tick_seconds: float = 1.0) -> None:
        self._jobs: List[Job] = []
        self._cv = threading.Condition()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tick = max(0.05, float(tick_seconds))
        self._history: List[tuple] = []

    def add_job(self, job: Job) -> Job:
        with self._cv:
            self._jobs.append(job)
            self._cv.notify()
        return job

    def remove_job(self, name: str) -> bool:
        with self._cv:
            before = len(self._jobs)
            self._jobs = [j for j in self._jobs if j.name != name]
            return len(self._jobs) != before

    def list_jobs(self) -> List[Job]:
        with self._cv:
            return list(self._jobs)

    def history(self, limit: int = 50) -> List[tuple]:
        with self._cv:
            return list(self._history[-limit:])

    def start(self) -> None:
        with self._cv:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._loop, name="minxg-scheduler", daemon=True)
            self._thread.start()

    def stop(self, join_timeout: float = 5.0) -> None:
        with self._cv:
            self._running = False
            self._cv.notify_all()
        if self._thread:
            self._thread.join(timeout=join_timeout)
            self._thread = None

    def _loop(self) -> None:
        while True:
            with self._cv:
                if not self._running:
                    return
                jobs = list(self._jobs)
            now = time.time()
            for job in jobs:
                if not job.is_due(now):
                    continue
                job.last_run_at = now
                job.run_count += 1
                thread = threading.Thread(target=self._safe_invoke, args=(job,), daemon=True)
                thread.start()
            time.sleep(self._tick)

    def _safe_invoke(self, job: Job) -> None:
        try:
            job.fn()
        except Exception as exc:
            job.error_count += 1
            job.last_error = f"{type(exc).__name__}: {exc}"
            with self._cv:
                self._history.append((time.time(), job.name, "ERROR", job.last_error, traceback.format_exc(limit=2)))
        else:
            with self._cv:
                self._history.append((time.time(), job.name, "OK", None, None))


_DEFAULT = Scheduler()


def get_default_scheduler() -> Scheduler:
    return _DEFAULT


def schedule(interval_seconds: float, fn: Callable[[], None], *, name: Optional[str] = None) -> Job:
    job = Job(name=name or fn.__name__, fn=fn, interval_seconds=interval_seconds)
    _DEFAULT.add_job(job)
    return job


def list_jobs() -> List[Job]:
    return _DEFAULT.list_jobs()


def start_scheduler() -> None:
    _DEFAULT.start()


def stop_scheduler() -> None:
    _DEFAULT.stop()
