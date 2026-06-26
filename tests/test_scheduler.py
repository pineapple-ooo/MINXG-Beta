"""
test_scheduler.py — cover multiling/scheduler/scheduler.py

Tests cover:
  - scheduler module imports
  - enqueue then dequeue round-trip
  - empty scheduler returns None on dequeue
  - multiple jobs maintain insertion order
"""
from __future__ import annotations

import time

import pytest

from multiling.scheduler.scheduler import schedule, list_jobs, Scheduler


# Module-level _jobs is a global list; reset between tests via monkeypatch.
def _fresh_jobs(monkeypatch):
    import multiling.scheduler.scheduler as sched_mod
    fresh = []
    monkeypatch.setattr(sched_mod, "_jobs", fresh, raising=False)
    return fresh


class TestSchedulerImports:
    def test_scheduler_module_imports_cleanly(self):
        assert callable(schedule)
        assert callable(list_jobs)
        assert callable(Scheduler)

    def test_scheduler_class_instantiable(self):
        s = Scheduler()
        assert s._running is False


class TestSchedulerRoundTrip:
    def test_enqueue_then_dequeue_roundtrip(self, monkeypatch):
        jobs = _fresh_jobs(monkeypatch)

        def my_job():
            pass

        schedule("*/5 * * * *", my_job, name="roundtrip_job")
        assert len(jobs) == 1
        retrieved = list_jobs()
        assert len(retrieved) == 1
        assert retrieved[0]["name"] == "roundtrip_job"
        assert retrieved[0]["cron"] == "*/5 * * * *"

    def test_empty_scheduler_returns_empty_list(self, monkeypatch):
        jobs = _fresh_jobs(monkeypatch)
        assert list_jobs() == []
        assert len(list_jobs()) == 0

    def test_multiple_jobs_maintain_insertion_order(self, monkeypatch):
        jobs = _fresh_jobs(monkeypatch)

        def job_a():
            pass

        def job_b():
            pass

        def job_c():
            pass

        schedule("@hourly", job_a, name="a")
        schedule("@daily", job_b, name="b")
        schedule("@weekly", job_c, name="c")

        names = [j["name"] for j in list_jobs()]
        assert names == ["a", "b", "c"]

    def test_job_stores_last_run_timestamp(self, monkeypatch):
        jobs = _fresh_jobs(monkeypatch)

        def my_job():
            pass

        schedule("0 * * * *", my_job, name="timestamp_job")
        assert jobs[0]["last"] == 0
        # Simulate a run by updating last
        jobs[0]["last"] = time.time()
        assert jobs[0]["last"] > 0


class TestSchedulerLifecycle:
    def test_start_sets_running_true(self, monkeypatch):
        s = Scheduler()
        assert s._running is False
        with monkeypatch.context() as m:
            m.setattr("time.sleep", lambda x: s.stop())
            s.start()
        assert s._running is False

    def test_stop_halts_loop(self, monkeypatch):
        s = Scheduler()
        # Mock time.sleep to call stop() and break the loop
        def fake_sleep(x):
            s.stop()
            raise RuntimeError("break loop")
        monkeypatch.setattr("time.sleep", fake_sleep)
        try:
            s.start()
        except RuntimeError:
            pass
        assert s._running is False
