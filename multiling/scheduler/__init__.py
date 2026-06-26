"""
scheduler.py - Advanced Task Scheduler

Provides:
  - ScheduledTask: Task with cron-like scheduling
  - TaskScheduler: Cron/interval/one-shot task scheduler
  - JobManager: Manage scheduled jobs lifecycle
  - Schedule types: cron, interval, date, recurring
"""

import asyncio
import croniter
import datetime
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum


class ScheduleType(Enum):
    INTERVAL = "interval"
    CRON = "cron"
    DATE = "date"
    RECURRING = "recurring"


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ScheduledTask:
    """A scheduled task definition"""
    id: str = field(default_factory=lambda: "job_" + uuid.uuid4().hex[:10])
    name: str = ""
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    func: Optional[Callable] = None
    args: tuple = ()
    kwargs: Dict[str, Any] = field(default_factory=dict)
    interval_seconds: float = 60.0
    cron_expression: str = ""
    run_date: Optional[float] = None
    repeat_count: int = 0          
    max_retries: int = 3
    timeout_seconds: float = 300.0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    
    status: JobStatus = JobStatus.PENDING
    next_run: float = 0.0
    last_run: float = 0.0
    run_count: int = 0
    error_count: int = 0
    last_result: Any = None
    last_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "type": self.schedule_type.value,
            "status": self.status.value,
            "enabled": self.enabled,
            "next_run": self.next_run,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "interval": self.interval_seconds,
            "cron": self.cron_expression,
            "created_at": self.created_at,
        }


class TaskScheduler:
    """
    Advanced task scheduler supporting cron, interval, and one-shot jobs

    Features:
    - Cron expression support (via croniter)
    - Interval-based scheduling
    - One-shot delayed execution
    - Automatic retry with backoff
    - Job lifecycle management
    - Async task execution
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._jobs: Dict[str, ScheduledTask] = {}
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._stats = {
            "total_scheduled": 0,
            "total_executed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
        }

    def schedule_interval(self, func: Callable, seconds: float,
                          name: str = None, **kwargs) -> str:
        """Schedule a function to run at fixed intervals"""
        name = name or func.__name__
        task = ScheduledTask(
            name=name, func=func,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=seconds,
            kwargs=kwargs,
            next_run=time.time() + seconds,
            enabled=True,
        )
        self._jobs[task.id] = task
        self._stats["total_scheduled"] += 1
        return task.id

    def schedule_cron(self, func: Callable, cron_expr: str,
                      name: str = None, **kwargs) -> str:
        """Schedule a function using cron expression"""
        name = name or func.__name__
        task = ScheduledTask(
            name=name, func=func,
            schedule_type=ScheduleType.CRON,
            cron_expression=cron_expr,
            kwargs=kwargs,
            next_run=self._next_cron_run(cron_expr),
            enabled=True,
        )
        self._jobs[task.id] = task
        self._stats["total_scheduled"] += 1
        return task.id

    def schedule_once(self, func: Callable, delay_seconds: float = 0,
                      name: str = None, **kwargs) -> str:
        """Schedule a one-shot task with optional delay"""
        name = name or func.__name__
        task = ScheduledTask(
            name=name, func=func,
            schedule_type=ScheduleType.DATE,
            run_date=time.time() + delay_seconds,
            kwargs=kwargs,
            next_run=time.time() + delay_seconds,
            repeat_count=1,
            enabled=True,
        )
        self._jobs[task.id] = task
        self._stats["total_scheduled"] += 1
        return task.id

    def schedule_recurring(self, func: Callable, interval_seconds: float,
                           repeat_count: int, name: str = None,
                           **kwargs) -> str:
        """Schedule a recurring task with limited repetitions"""
        task_id = self.schedule_interval(func, interval_seconds, name, **kwargs)
        task = self._jobs[task_id]
        task.schedule_type = ScheduleType.RECURRING
        task.repeat_count = repeat_count
        return task_id

    def cancel(self, job_id: str) -> bool:
        """Cancel a scheduled job"""
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.CANCELLED
            self._stats["total_cancelled"] += 1
            return True
        return False

    def pause(self, job_id: str) -> bool:
        """Pause a scheduled job"""
        if job_id in self._jobs:
            self._jobs[job_id].status = JobStatus.PAUSED
            return True
        return False

    def resume(self, job_id: str) -> bool:
        """Resume a paused job"""
        if job_id in self._jobs and self._jobs[job_id].status == JobStatus.PAUSED:
            self._jobs[job_id].status = JobStatus.PENDING
            job = self._jobs[job_id]
            if job.schedule_type == ScheduleType.INTERVAL:
                job.next_run = time.time() + job.interval_seconds
            elif job.schedule_type == ScheduleType.CRON:
                job.next_run = self._next_cron_run(job.cron_expression)
            return True
        return False

    def get_job(self, job_id: str) -> Optional[ScheduledTask]:
        return self._jobs.get(job_id)

    def list_jobs(self, status_filter: str = None) -> List[Dict]:
        """List all jobs, optionally filtered by status"""
        jobs = list(self._jobs.values())
        if status_filter:
            jobs = [j for j in jobs if j.status.value == status_filter]
        return [j.to_dict() for j in jobs]

    def on_complete(self, job_id: str, callback: Callable):
        """Register callback for job completion"""
        self._callbacks[job_id].append(callback)

    async def start(self):
        """Start the scheduler loop"""
        self._running = True
        self._loop = asyncio.get_event_loop()
        while self._running:
            try:
                await self._tick()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break

    def stop(self):
        """Stop the scheduler loop"""
        self._running = False

    async def _tick(self):
        """Process due jobs in one tick"""
        now = time.time()
        for job_id, job in self._jobs.items():
            if not job.enabled:
                continue
            if job.status not in (JobStatus.PENDING, JobStatus.RUNNING):
                continue
            if job.next_run > now:
                continue

            
            job.status = JobStatus.RUNNING
            job.last_run = now
            job.run_count += 1

            try:
                if asyncio.iscoroutinefunction(job.func):
                    result = await asyncio.wait_for(
                        job.func(*job.args, **job.kwargs),
                        timeout=job.timeout_seconds
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, job.func, *job.args, **job.kwargs),
                        timeout=job.timeout_seconds
                    )
                job.last_result = result
                job.status = JobStatus.PENDING if job.repeat_count == 0 else JobStatus.COMPLETED
                self._stats["total_executed"] += 1

                
                for cb in self._callbacks.get(job_id, []):
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            await cb(job_id, result)
                        else:
                            cb(job_id, result)
                    except Exception:
                        pass

            except asyncio.TimeoutError:
                job.error_count += 1
                job.last_error = "Timeout"
                job.status = JobStatus.PENDING
                self._stats["total_failed"] += 1
            except Exception as e:
                job.error_count += 1
                job.last_error = str(e)
                if job.error_count >= job.max_retries:
                    job.status = JobStatus.FAILED
                else:
                    job.status = JobStatus.PENDING
                self._stats["total_failed"] += 1

            
            if job.status == JobStatus.PENDING:
                if job.schedule_type == ScheduleType.INTERVAL:
                    job.next_run = now + job.interval_seconds
                elif job.schedule_type == ScheduleType.CRON:
                    job.next_run = self._next_cron_run(job.cron_expression, now)
                elif job.schedule_type == ScheduleType.RECURRING:
                    if job.run_count >= job.repeat_count:
                        job.status = JobStatus.COMPLETED
                    else:
                        job.next_run = now + job.interval_seconds

    def _next_cron_run(self, cron_expr: str, after: float = None) -> float:
        """Calculate next cron run time"""
        try:
            cron = croniter.croniter(cron_expr,
                                     datetime.datetime.fromtimestamp(after or time.time()))
            next_dt = cron.get_next(datetime.datetime)
            return next_dt.timestamp()
        except Exception:
            return time.time() + 60

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "jobs_count": len(self._jobs),
            **self._stats,
        }




_default_scheduler: Optional[TaskScheduler] = None


def get_default_scheduler() -> TaskScheduler:
    """Get global default scheduler instance"""
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = TaskScheduler("global")
    return _default_scheduler


def scheduled(seconds: float = 60, name: str = None):
    """Decorator to schedule a function at fixed intervals"""
    def decorator(func: Callable):
        scheduler = get_default_scheduler()
        job_id = scheduler.schedule_interval(func, seconds, name=name)
        func._scheduled_job_id = job_id
        return func
    return decorator


def cron_scheduled(cron_expr: str, name: str = None):
    """Decorator to schedule a function with cron expression"""
    def decorator(func: Callable):
        scheduler = get_default_scheduler()
        job_id = scheduler.schedule_cron(func, cron_expr, name=name)
        func._scheduled_job_id = job_id
        return func
    return decorator