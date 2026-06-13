"""Pipeline runner — see __init__.py."""
from typing import Any, Callable, List

class Stage:
    def __init__(self, name: str, process: Callable):
        self.name = name
        self.process = process
    def __call__(self, data): return self.process(data)

class Pipeline:
    def __init__(self, stages=None):
        self.stages = stages or []
    def add(self, stage): self.stages.append(stage)
    def run(self, data):
        for s in self.stages: data = s(data)
        return data

def run_pipeline(stages, data): return Pipeline(stages).run(data)
