"""queue.priority — Heap-based priority queue with insertion counter to
break ties and FIFO ordering for items of equal priority.
""""
from __future__ import annotations
import heapq
import itertools
from typing import Any, Iterator, List, Optional, Tuple


class PriorityQueue:
    def __init__(self) -> None:
        self._heap: List[Tuple[int, int, Any]] = []
        self._counter = itertools.count()

    def put(self, item: Any, priority: int = 0) -> None:
        heapq.heappush(self._heap, (int(priority), next(self._counter), item))

    def peek(self) -> Optional[Any]:
        return self._heap[0][2] if self._heap else None

    def get(self) -> Any:
        if not self._heap:
            return None
        _, _, item = heapq.heappop(self._heap)
        return item

    def drain(self) -> List[Any]:
        items = [it for _, _, it in sorted(self._heap)]
        self._heap.clear()
        return items

    def __len__(self) -> int:
        return len(self._heap)

    def __iter__(self) -> Iterator[Tuple[int, Any]]:
        for prio, _, item in sorted(self._heap):
            yield prio, item
