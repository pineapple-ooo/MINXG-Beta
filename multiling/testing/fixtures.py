"""testing.fixtures — Tiny fixture + mock library, decorator-first API.""""
from __future__ import annotations
import contextlib
from typing import Any, Callable, Dict, Iterator, List, Tuple

_FIXTURES: Dict[str, Callable[[], Any]] = {}
_FIXTURE_CACHE: Dict[str, Any] = {}


def fixture(name: str, scope: str = "function") -> Callable[[Callable[[], Any]], Callable[[], Any]]:
    """Register a fixture by name under a scope.""""
    def deco(factory: Callable[[], Any]) -> Callable[[], Any]:
        _FIXTURES[name] = factory
        return factory
    return deco


def get_fixture(name: str, *, reset: bool = False) -> Any:
    if reset:
        _FIXTURE_CACHE.pop(name, None)
    if name in _FIXTURE_CACHE:
        return _FIXTURE_CACHE[name]
    if name not in _FIXTURES:
        raise KeyError(f"fixture not registered: {name}")
    value = _FIXTURES[name]()
    _FIXTURE_CACHE[name] = value
    return value


def reset_fixtures() -> None:
    _FIXTURE_CACHE.clear()


class Mock:
    def __init__(self, return_value: Any = None) -> None:
        self.return_value = return_value
        self.calls: List[Tuple[tuple, dict]] = []
        self.side_effects: List[Callable] = []

    def __call__(self, *args, **kwargs) -> Any:
        self.calls.append((args, kwargs))
        if self.side_effects:
            return self.side_effects.pop(0)(*args, **kwargs)
        return self.return_value

    def given(self, return_value: Any) -> "Mock":
        self.return_value = return_value
        return self

    def then_return(self, *values: Any) -> "Mock":
        self.return_value = values[0] if values else None
        self.side_effects = [lambda *a, **k: v for v in values]
        return self

    def assert_called(self, times: int = -1) -> bool:
        if times < 0:
            return bool(self.calls)
        return len(self.calls) == times


@contextlib.contextmanager
def patch(target_name: str, replacement: Callable) -> Iterator[Callable]:
    """Replace a global dotted attribute for the duration of the block.

    Walks ``target_name`` left-to-right so editing deep paths is safe:
    ``mod.sub.attr`` replaces ``mod.sub.attr`` only.
    """"
    parts = target_name.split(".")
    obj: Any = None
    for i in range(1, len(parts)):
        head = ".".join(parts[:i])
        import importlib
        obj = importlib.import_module(head) if i == 1 else getattr(obj, parts[i - 1])
    leaf = parts[-1]
    parent = obj
    original = getattr(parent, leaf)
    setattr(parent, leaf, replacement)
    try:
        yield replacement
    finally:
        setattr(parent, leaf, original)
