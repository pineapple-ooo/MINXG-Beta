"""queue.fifo — Bounded FIFO queue with blocking/non-blocking APIs.""""
from __future__ import annotations
import threading
from collections import deque
from typing import Any, Iterator, List, Optional


class FIFOQueue:
    def __init__(self, max_size: int = 0) -> None:
        self._q: deque = deque()
        self._max = int(max_size)
        self._cv = threading.Condition()

    def put(self, item: Any, block: bool = True, timeout: Optional[float] = None) -> bool:
        with self._cv:
            if self._max and len(self._q) >= self._max:
                if not block:
                    return False
                if not self._cv.wait(timeout=timeout):
                    return False
            self._q.append(item)
            self._cv.notify()
            return True

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        with self._cv:
            while not self._q:
                if not block:
                    return None
                if not self._cv.wait(timeout=timeout):
                    return None
            item = self._q.popleft()
            self._cv.notify()
            return item

    def peek(self) -> Optional[Any]:
        with self._cv:
            return self._q[0] if self._q else None

    def drain(self) -> List[Any]:
        with self._cv:
            items = list(self._q)
            self._q.clear()
            self._cv.notify_all()
            return items

    def empty(self) -> bool:
        with self._cv:
            return not self._q

    def full(self) -> bool:
        with self._cv:
            return bool(self._max) and len(self._q) >= self._max

    def __len__(self) -> int:
        with self._cv:
            return len(self._q)

    def __iter__(self) -> Iterator[Any]:
        with self._cv:
            return iter(list(self._q))
