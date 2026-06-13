"""Priority queue — see __init__.py."""
import heapq
class PriorityQueue:
    def __init__(self):
        self._h = []
        self._c = 0
    def put(self, item, priority=0):
        heapq.heappush(self._h, (priority, self._c, item))
        self._c += 1
    def get(self):
        return heapq.heappop(self._h)[2] if self._h else None
    def __len__(self): return len(self._h)
