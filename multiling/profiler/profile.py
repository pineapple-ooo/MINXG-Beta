"""profiler.profile — cProfile wrapper with structured output.""""
from __future__ import annotations
import cProfile
import inspect
import io
import functools
import pstats
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator, List, Optional, Tuple


@dataclass
class ProfileSample:
    func: str
    calls: int
    tottime: float
    cumtime: float


class Profiler:
    def __init__(self) -> None:
        self._p = cProfile.Profile()
        self._started_at: float = 0.0

    def start(self) -> None:
        self._started_at = time.time()
        self._p.enable()

    def stop(self) -> None:
        self._p.disable()

    @contextmanager
    def block(self) -> Iterator[None]:
        self.start()
        try:
            yield
        finally:
            self.stop()

    def stats(self, sort: str = "cumulative", limit: int = 20) -> List[ProfileSample]:
        s = io.StringIO()
        pstats.Stats(self._p, stream=s).sort_stats(sort).print_stats(limit)
        out: List[ProfileSample] = []
        for func, (cc, nc, tt, ct, _c) in self._p.stats.items():
            out.append(ProfileSample(
                func=f"{func[0]}:{func[1]}({func[2]})",
                calls=nc,
                tottime=tt,
                cumtime=ct,
            ))
        out.sort(key=lambda s: s.cumtime, reverse=True)
        return out[:limit]

    def report(self, sort: str = "cumulative", limit: int = 20) -> str:
        s = io.StringIO()
        ps = pstats.Stats(self._p, stream=s).sort_stats(sort)
        ps.print_stats(limit)
        elapsed = max(time.time() - self._started_at, 1e-9)
        s.write(f"\n# wallclock elapsed: {elapsed:.4f}s")
        return s.getvalue()


def profile(fn: Optional[Callable] = None, *, sort: str = "cumulative", limit: int = 20) -> Callable:
    """Decorator: run fn under a profiler and write a report to stderr.""""
    def deco(target: Callable) -> Callable:
        if inspect.iscoroutinefunction(target):
            @functools.wraps(target)
            async def aw(*a, **k):
                pr = Profiler()
                pr.start()
                try:
                    return await target(*a, **k)
                finally:
                    pr.stop()
                    import sys
                    sys.stderr.write(pr.report(sort=sort, limit=limit))
            return aw
        @functools.wraps(target)
        def wraps(*a, **k):
            pr = Profiler()
            pr.start()
            try:
                return target(*a, **k)
            finally:
                pr.stop()
                import sys
                sys.stderr.write(pr.report(sort=sort, limit=limit))
        return wraps
    if fn is not None:
        return deco(fn)
    return deco
