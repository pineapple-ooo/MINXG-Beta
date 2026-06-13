"""Scheduler — see __init__.py."""
import time, threading
from typing import Callable

_jobs = []
_lock = threading.Lock()

def schedule(cron, fn, name=None):
    with _lock:
        _jobs.append({"cron": cron, "fn": fn, "name": name or fn.__name__, "last": 0})

def list_jobs():
    with _lock: return list(_jobs)

class Scheduler:
    def __init__(self): self._running = False
    def start(self):
        self._running = True
        while self._running:
            now = time.time()
            for j in _jobs:
                if now - j["last"] >= 60:
                    try: j["fn"](); j["last"] = now
                    except: pass
            time.sleep(1)
    def stop(self): self._running = False
