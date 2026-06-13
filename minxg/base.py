"""
minxg/base.py - Worker base class, tool decorator, registry.
""""
from __future__ import annotations
import asyncio
import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, get_type_hints

log = logging.getLogger("py_workers.base")


@dataclass
class ToolDef:
    """Metadata for a single tool.""""
    name: str
    description: str
    params: Dict[str, str]  
    category: str = "general"
    fn: Optional[Callable] = None
    call_count: int = 0
    error_count: int = 0
    total_time: float = 0.0
    call_budget: int = 20      
    budget_used: int = 0

    def budget_remaining(self) -> int:
        return max(0, self.call_budget - self.budget_used)

    def consume_budget(self) -> bool:
        """Try to consume one call from the budget. Returns False if exhausted.""""
        if self.budget_used >= self.call_budget:
            return False
        self.budget_used += 1
        return True

    def avg_time(self) -> float:
        return self.total_time / self.call_count if self.call_count else 0.0


class BaseWorker:
    """Base class for all py_workers. Provides tool registration, stats, health checks.""""
    worker_id: str = "base"
    version: str = "1.0.0"

    def __init__(self):
        self.tools: Dict[str, ToolDef] = {}
        self._start_time = time.time()
        self._register_tools()

    
    def _register_tools(self):
        """Subclass override: wrap methods into ToolDef and register in self.tools.""""
        for name in dir(self):
            if name.startswith("_"):
                continue
            fn = getattr(self, name, None)
            if not callable(fn):
                continue
            meta = getattr(fn, "_tool_meta", None)
            if not meta:
                continue
            meta["fn"] = fn
            self.tools[meta["name"]] = ToolDef(
                name=meta["name"],
                description=meta["description"],
                params=meta["params"],
                category=meta.get("category", "general"),
                fn=fn,
                call_budget=meta.get("call_budget", 20),
            )

    
    async def call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with unified error handling, statistics, and budget enforcement.""""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"status": "error", "error": f"unknown tool: {tool_name}",
                    "available": sorted(self.tools.keys())}

        
        if not tool.consume_budget():
            return {"status": "error", "error":
                    f"call budget exhausted for {tool_name} ({tool.call_budget} max)"}

        t0 = time.time()
        tool.call_count += 1
        try:
            if asyncio.iscoroutinefunction(tool.fn):
                result = await tool.fn(**(params or {}))
            else:
                result = tool.fn(**(params or {}))
            tool.total_time += time.time() - t0
            if isinstance(result, dict) and "status" not in result:
                result = {"status": "success", **result}
            return result
        except TypeError as e:
            tool.error_count += 1
            tool.total_time += time.time() - t0
            return {"status": "error", "error": f"parameter error: {e}",
                    "params_schema": tool.params}
        except Exception as e:
            tool.error_count += 1
            tool.total_time += time.time() - t0
            log.error("[%s/%s] %s", self.worker_id, tool_name, e)
            log.debug(traceback.format_exc())
            return {"status": "error", "error": str(e),
                    "error_type": type(e).__name__}

    async def health_check(self) -> bool:
        return True

    async def shutdown(self):
        pass

    def statistics(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "version": self.version,
            "uptime_sec": round(time.time() - self._start_time, 2),
            "tool_count": len(self.tools),
            "tools": {
                n: {"calls": t.call_count, "errors": t.error_count,
                    "avg_ms": round(t.avg_time() * 1000, 2)}
                for n, t in self.tools.items()
            },
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description,
             "params": t.params, "category": t.category}
            for t in self.tools.values()
        ]





def tool(name: str = None, description: str = "", category: str = "general",
         call_budget: int = 20):
    """
    Decorator: mark a method as a tool, auto-collect parameter schema.
    Usage:
        @tool                         # bare — no args
        @tool(description="...")      # with args
        @tool(call_budget=5)          # limit max calls
        async def read_file(self, path: str, lines: int = 0) -> Dict:
            ...
    """"
    
    if callable(name):
        fn = name
        hints = get_type_hints(fn)
        params = {k: _type_to_str(v) for k, v in hints.items() if k != "return"}
        fn._tool_meta = {
            "name": fn.__name__,
            "description": fn.__doc__ or "",
            "params": params,
            "category": category,
            "call_budget": call_budget,
        }
        return fn

    def decorator(fn):
        hints = get_type_hints(fn)
        params = {k: _type_to_str(v) for k, v in hints.items() if k != "return"}
        fn._tool_meta = {
            "name": name or fn.__name__,
            "description": description or fn.__doc__ or "",
            "params": params,
            "category": category,
            "call_budget": call_budget,
        }
        return fn
    return decorator


def _type_to_str(tp) -> str:
    """Convert Python type hint to schema string.""""
    import typing
    origin = typing.get_origin(tp)
    if origin is list:
        return "list"
    if origin is dict:
        return "dict"
    if origin is tuple:
        return "tuple"
    name = getattr(tp, "__name__", str(tp))
    return {
        "str": "string", "int": "integer", "float": "number",
        "bool": "boolean", "dict": "dict", "list": "list",
        "Any": "any", "NoneType": "null",
    }.get(name, name.lower())





class WorkerRegistry:
    """Manage all worker instances for HTTP server.""""
    def __init__(self):
        self.workers: Dict[str, BaseWorker] = {}

    def register(self, worker: BaseWorker):
        self.workers[worker.worker_id] = worker
        log.info("Registered worker: %s (%d tools)", worker.worker_id, len(worker.tools))

    def get(self, worker_id: str) -> Optional[BaseWorker]:
        return self.workers.get(worker_id)

    async def call(self, worker_id: str, tool: str, params: Dict) -> Dict:
        w = self.get(worker_id)
        if not w:
            return {"status": "error", "error": f"unknown worker: {worker_id}",
                    "available": sorted(self.workers.keys())}
        return await w.call(tool, params)

    def health(self) -> Dict:
        return {
            "status": "ok",
            "version": VERSION if (VERSION := __import__("py_workers").VERSION) else "?",
            "registered_workers": list(self.workers.keys()),
        }
