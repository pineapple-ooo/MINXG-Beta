"""Port — an asynchronous boundary between Cells and the outside world.

A Port wraps a callable and serialises/deserialises Request → Response
payloads. Ports add no shared mutable state to the Cells that use them:
two Cells that talk through the same Port remain independent.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional


class PortError(RuntimeError):
    pass


@dataclass
class Request:
    path: str
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Response:
    ok: bool = True
    value: Any = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


class Port:
    def __init__(self, name: str, handler: Callable[..., Awaitable[Any]]):
        self.name = name
        self._handler = handler

    async def __call__(self, request: Request) -> Response:
        if request.path != self.name:
            return Response(ok=False, error=f"port {self.name!r} got {request.path!r}")
        try:
            value = await self._handler(*request.args, **request.kwargs)
            return Response(ok=True, value=value)
        except Exception as exc:  
            return Response(ok=False, error=f"{type(exc).__name__}: {exc}")

    def bind(self, name: str) -> "Port":
        return Port(name, self._handler)


def port(name: str) -> Callable[[Callable[..., Awaitable[Any]]], Port]:
    def deco(fn: Callable[..., Awaitable[Any]]) -> Port:
        return Port(name, fn)
    return deco
