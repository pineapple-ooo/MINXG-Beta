"""Workflow engine — see __init__.py."""
from typing import Any, Callable, Dict

class Step:
    def __init__(self, name, action, next_step=None):
        self.name = name
        self.action = action
        self.next_step = next_step
    def __call__(self, state): return self.action(state)

class Workflow:
    def __init__(self, name):
        self.name = name
        self.steps: Dict[str, Step] = {}
        self.start_step = None
    def add_step(self, step, is_start=False):
        self.steps[step.name] = step
        if is_start: self.start_step = step.name
    def run(self, initial):
        state = initial
        current = self.start_step
        while current:
            state = self.steps[current](state)
            current = self.steps[current].next_step
        return state

def run_workflow(w, s): return w.run(s)
