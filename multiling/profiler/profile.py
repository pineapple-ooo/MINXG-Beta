"""Profiler — see __init__.py."""
import cProfile
import pstats
import io

class Profiler:
    def __init__(self):
        self._p = cProfile.Profile()
    def start(self): self._p.enable()
    def stop(self): self._p.disable()
    def get_stats(self, sort="cumulative", limit=20):
        s = io.StringIO()
        pstats.Stats(self._p, stream=s).sort_stats(sort).print_stats(limit)
        return s.getvalue()

def profile(fn):
    p = Profiler()
    def wrapper(*a, **k):
        p.start()
        try: return fn(*a, **k)
        finally:
            p.stop()
            print(p.get_stats())
    return wrapper

get_stats = lambda: ""
