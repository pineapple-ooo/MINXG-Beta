"""
time_diff, cron_next, sleep, timer_start, timer_stop, date_add
"""
from __future__ import annotations
import time
import asyncio
import datetime
from typing import Dict
from minxg.base import BaseWorker, tool


class DateTimeToolsWorker(BaseWorker):
    worker_id = "datetime_tools"
    version = "0.16.0"

    def __init__(self):
        self._timers: Dict[str, float] = {}
        self.tools: Dict = {}
        self._register_tools()

    @tool(description="Get current timestamp (seconds or milliseconds)", category="time")
    async def now_timestamp(self, unit: str = "s") -> Dict:
        if unit == "ms":
            return {"timestamp": int(time.time() * 1000), "unit": "ms"}
        return {"timestamp": time.time(), "unit": "s"}

    @tool(description="Format timestamp to string", category="time")
    async def format_time(self, timestamp: float = None, fmt: str = "%Y-%m-%d %H:%M:%S",
                         timezone_offset: int = 0) -> Dict:
        ts = timestamp if timestamp is not None else time.time()
        dt = datetime.datetime.utcfromtimestamp(ts) + datetime.timedelta(hours=timezone_offset)
        return {"formatted": dt.strftime(fmt), "timestamp": ts, "fmt": fmt}

    @tool(description="Parse time string to timestamp", category="time")
    async def parse_time(self, text: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> Dict:
        try:
            dt = datetime.datetime.strptime(text, fmt)
            return {"timestamp": dt.replace(tzinfo=datetime.timezone.utc).timestamp(),
                    "parsed": True, "fmt": fmt}
        except Exception as e:
            return {"error": str(e), "parsed": False}

    @tool(description="Timezone conversion", category="time")
    async def timezone_convert(self, timestamp: float, from_offset: int, to_offset: int) -> Dict:
        dt = datetime.datetime.utcfromtimestamp(timestamp)
        dt = dt - datetime.timedelta(hours=from_offset) + datetime.timedelta(hours=to_offset)
        return {"timestamp": dt.replace(tzinfo=datetime.timezone.utc).timestamp(),
                "from_offset": from_offset, "to_offset": to_offset,
                "formatted": dt.strftime("%Y-%m-%d %H:%M:%S")}

    @tool(description="Humanize time difference between timestamps", category="time")
    async def time_diff(self, start: float, end: float = None) -> Dict:
        end = end if end is not None else time.time()
        diff = abs(end - start)
        days = int(diff // 86400)
        hours = int((diff % 86400) // 3600)
        minutes = int((diff % 3600) // 60)
        seconds = round(diff % 60, 2)
        return {"diff_seconds": diff, "days": days, "hours": hours,
                "minutes": minutes, "seconds": seconds,
                "human": f"{days}d {hours}h {minutes}m {seconds}s"}

    @tool(description="Next cron execution time", category="time")
    async def cron_next(self, expression: str, now_timestamp: float = None) -> Dict:
        try:
            parts = expression.split()
            if len(parts) != 5:
                return {"error": "cron must have 5 fields: min hour day month weekday"}
            now = datetime.datetime.utcfromtimestamp(now_timestamp or time.time())
            minute_str, hour_str, day_str, month_str, weekday_str = parts
            if day_str != "*" or month_str != "*" or weekday_str != "*":
                return {"error": "only supports * for day/month/weekday in simple mode"}
            target = now.replace(second=0, microsecond=0)
            target += datetime.timedelta(minutes=1)
            m_ok = minute_str == "*" or target.minute == int(minute_str)
            h_ok = hour_str == "*" or target.hour == int(hour_str)
            if m_ok and h_ok:
                return {"next": target.timestamp(), "formatted": target.strftime("%Y-%m-%d %H:%M:%S")}
            return {"error": "no next occurrence found"}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Async sleep for delay seconds", category="time")
    async def sleep(self, delay: float = 1.0) -> Dict:
        await asyncio.sleep(delay)
        return {"slept": delay}

    @tool(description="Start named timer", category="time")
    async def timer_start(self, name: str) -> Dict:
        self._timers[name] = time.time()
        return {"timer": name, "started_at": self._timers[name]}

    @tool(description="Stop named timer and return elapsed time", category="time")
    async def timer_stop(self, name: str) -> Dict:
        start = self._timers.pop(name, None)
        if start is None:
            return {"error": f"timer not found: {name}"}
        elapsed = time.time() - start
        return {"timer": name, "elapsed_sec": round(elapsed, 4)}

    @tool(description="Date add/subtract", category="time")
    async def date_add(self, timestamp: float = None, days: int = 0, hours: int = 0,
                       minutes: int = 0) -> Dict:
        ts = timestamp if timestamp is not None else time.time()
        dt = datetime.datetime.utcfromtimestamp(ts)
        dt = dt + datetime.timedelta(days=days, hours=hours, minutes=minutes)
        return {"timestamp": dt.replace(tzinfo=datetime.timezone.utc).timestamp(),
                "formatted": dt.strftime("%Y-%m-%d %H:%M:%S")}
