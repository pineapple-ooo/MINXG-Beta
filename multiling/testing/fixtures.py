"""Testing fixtures — see __init__.py."""
from typing import Callable, Any, Dict

_fixtures: Dict[str, Any] = {}

def fixture(name: str):
    def decorator(fn):
        _fixtures[name] = fn
        return fn
    return decorator

def mock(target: Callable) -> Callable:
    calls = []
    def fn(*args, **kwargs):
        calls.append((args, kwargs))
        return None
    fn.calls = calls
    return fn

def patch(target, replacement):
    from contextlib import contextmanager
    @contextmanager
    def _patch():
        yield replacement
    return _patch()
