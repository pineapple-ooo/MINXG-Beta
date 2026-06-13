"""FIFO queue — see __init__.py."""
from collections import deque
class FIFOQueue:
    def __init__(self, max_size=0):
        self._q = deque()
        self._max = max_size
    def put(self, item):
        if self._max and len(self._q) >= self._max: return False
        self._q.append(item); return True
    def get(self):
        return self._q.popleft() if self._q else None
    def __len__(self): return len(self._q)
    def empty(self): return not self._q
