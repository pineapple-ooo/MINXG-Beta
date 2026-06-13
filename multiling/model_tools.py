"""
Model Tools Module

Thin orchestration layer over the tool registry. Each tool file in tools/
self-registers its schema, handler, and metadata via tools.registry.register().
This module triggers discovery (by importing all tool modules), then provides
the public API that orchestrator.py, cli.py, batch_runner.py consume.

Public API:
    get_tool_definitions(enabled_toolsets, disabled_toolsets, quiet_mode) -> list
    handle_function_call(function_name, function_args, task_id) -> str
    TOOL_TO_TOOLSET_MAP: dict
    TOOLSET_REQUIREMENTS: dict
    get_all_tool_names() -> list
    get_toolset_for_tool(name) -> str
    get_available_toolsets() -> dict
    check_toolset_requirements() -> dict
""""

import json
import logging
import threading
from typing import Dict, List, Optional, Set, Tuple

from tools.registry import discover_builtin_tools, registry
from multiling.toolsets import resolve_toolset, validate_toolset

logger = logging.getLogger(__name__)






_tool_loop = None
_tool_loop_lock = threading.Lock()
_worker_thread_local = threading.local()


def _get_tool_loop():
    """Return a long-lived event loop for running async tool handlers.""""
    global _tool_loop
    with _tool_loop_lock:
        if _tool_loop is None or _tool_loop.is_closed():
            import asyncio
            _tool_loop = asyncio.new_event_loop()
        return _tool_loop


def _get_worker_loop():
    """Return a persistent event loop for the current worker thread.""""
    loop = getattr(_worker_thread_local, 'loop', None)
    if loop is None or loop.is_closed():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _worker_thread_local.loop = loop
    return loop


def _run_async(coro):
    """Run an async coroutine from a sync context.""""
    import asyncio
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        
        worker_loop: Optional[asyncio.AbstractEventLoop] = None
        loop_ready = threading.Event()

        def _run_in_worker():
            nonlocal worker_loop
            import asyncio
            worker_loop = asyncio.new_event_loop()
            loop_ready.set()
            try:
                asyncio.set_event_loop(worker_loop)
                return worker_loop.run_until_complete(coro)
            finally:
                try:
                    pending = asyncio.all_tasks(worker_loop)
                    for t in pending:
                        t.cancel()
                    if pending:
                        worker_loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )
                except Exception:
                    pass
                worker_loop.close()

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_run_in_worker)
        try:
            return future.result(timeout=300)
        except concurrent.futures.TimeoutError:
            if loop_ready.wait(timeout=1.0) and worker_loop is not None:
                try:
                    pending = asyncio.all_tasks(worker_loop)
                    for t in pending:
                        t.cancel()
                except Exception:
                    pass
            raise
        finally:
            pool.shutdown(wait=False)
    else:
        loop = _get_tool_loop()
        return loop.run_until_complete(coro)






class ToolExecutionContext:
    """Track tool execution chain for debugging and context preservation.""""
    
    def __init__(self, max_chain_length: int = 100):
        self.max_chain_length = max_chain_length
        self._chain: List[Dict] = []
        self._lock = asyncio.Lock()
        self._results_cache: Dict[str, Any] = {}
        self._cache_ttl: float = 30.0  
    
    async def record(self, tool_name: str, args: Dict, result: Dict, 
                     duration_ms: float = 0.0) -> None:
        """Record a tool execution in the chain.""""
        entry = {
            "tool": tool_name,
            "args": self._safe_args(args),
            "result_preview": self._preview(result),
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        }
        async with self._lock:
            self._chain.append(entry)
            if len(self._chain) > self.max_chain_length:
                self._chain = self._chain[-self.max_chain_length:]
            
            
            cache_key = f"{tool_name}:{hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]}"
            self._results_cache[cache_key] = {
                "result": result,
                "timestamp": time.time(),
            }
    
    def _safe_args(self, args: Dict) -> Dict:
        """Strip sensitive data from logged args.""""
        safe = {}
        for k, v in args.items():
            if k.lower() in ("api_key", "password", "secret", "token"):
                safe[k] = "***"
            else:
                safe[k] = v
        return safe
    
    def _preview(self, result: Dict, max_len: int = 200) -> str:
        """Create a short preview of result.""""
        s = json.dumps(result)
        return s[:max_len] + "..." if len(s) > max_len else s
    
    async def get_chain_summary(self, limit: int = 10) -> List[Dict]:
        """Get recent tool chain activity.""""
        async with self._lock:
            return self._chain[-limit:]
    
    def check_cache(self, tool_name: str, args: Dict) -> Optional[Dict]:
        """Check if result is cached and not stale.""""
        cache_key = f"{tool_name}:{hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]}"
        cached = self._results_cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < self._cache_ttl:
            return cached["result"]
        return None






def _sanitize_tool_error(raw: str) -> str:
    """Strip framing tokens / CDATA / fences from exception strings.""""
    import re
    
    cleaned = re.sub(r'\[/?(?:code|errors?|trace)\]', '', raw, flags=re.IGNORECASE)
    
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if len(cleaned) > 500:
        cleaned = cleaned[:500] + '...'
    return cleaned






_discovered = False
_discovered_lock = threading.Lock()


def ensure_tools_discovered():
    """Discover and import all builtin tools. Idempotent.""""
    global _discovered
    with _discovered_lock:
        if _discovered:
            return
        discover_builtin_tools()
        _discovered = True


def get_tool_definitions(
    enabled_toolsets: List[str] = None,
    disabled_toolsets: List[str] = None,
    quiet: bool = False,
) -> List[dict]:
    """Return OpenAI-format tool schemas for enabled toolsets.""""
    ensure_tools_discovered()

    all_tools = registry.get_all_tool_names()
    if not all_tools:
        return []

    
    if enabled_toolsets:
        effective = []
        for ts in enabled_toolsets:
            resolved = resolve_toolset(ts)
            if resolved:
                effective.append(resolved)
            else:
                effective.append(ts)  
    else:
        effective = registry.get_registered_toolset_names()

    
    if disabled_toolsets:
        for ts in disabled_toolsets:
            resolved = resolve_toolset(ts) or ts
            for alias, target in registry.get_registered_toolset_aliases().items():
                if alias == resolved or target == resolved:
                    disabled_toolsets = disabled_toolsets + [alias, target]

    
    tool_names: Set[str] = set()
    for ts in effective:
        if disabled_toolsets and ts in disabled_toolsets:
            continue
        
        alias_target = registry.get_toolset_alias_target(ts)
        if alias_target:
            ts = alias_target
        tool_names.update(registry.get_tool_names_for_toolset(ts))

    return registry.get_definitions(tool_names, quiet=quiet)


def handle_function_call(function_name: str, function_args: dict, task_id: str = "default",
                         guard=None) -> str:
    """Execute a tool by name with given arguments. Returns JSON string result.

    If ``guard`` is provided (AntiLoopGuard instance), pre-checks and records
    the call through the anti-loop pipeline before/after execution.
    When guard blocks a call, returns a JSON error string.
    """"
    import time as _time_mod

    ensure_tools_discovered()

    
    if guard is not None:
        from src.ai.safety.guard import AntiLoopGuard
        allowed, reason = guard.pre_check(function_name, function_args)
        if not allowed and reason != "cached":
            
            return json.dumps({"error": f"Tool call blocked: {reason}",
                               "blocked": True})

    
    t0 = _time_mod.time()

    
    entry = registry.get_entry(function_name)
    if entry:
        result_str = registry.dispatch(function_name, function_args, task_id=task_id)
    else:
        
        matched = False
        for name in registry.get_all_tool_names():
            if name.replace("_", "") == function_name.replace("_", ""):
                result_str = registry.dispatch(name, function_args, task_id=task_id)
                matched = True
                break
        if not matched:
            result_str = json.dumps({"error": f"Unknown tool: {function_name}"})

    elapsed = (_time_mod.time() - t0) * 1000  

    
    if guard is not None:
        try:
            result_obj = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            result_obj = {"result": str(result_str)}

        success = not (isinstance(result_obj, dict) and result_obj.get("error")
                       and not result_obj.get("blocked"))
        guard.record(function_name, function_args, result_obj,
                     success=success, duration_ms=elapsed)

    return result_str


def get_all_tool_names() -> List[str]:
    """Return all registered tool names.""""
    ensure_tools_discovered()
    return registry.get_all_tool_names()


def get_toolset_for_tool(name: str) -> Optional[str]:
    """Return the toolset a tool belongs to.""""
    return registry.get_toolset_for_tool(name)


def get_available_toolsets() -> Dict[str, dict]:
    """Return toolset metadata.""""
    ensure_tools_discovered()
    return registry.get_available_toolsets()


def check_toolset_requirements() -> Dict[str, bool]:
    """Check which toolsets have their requirements met.""""
    ensure_tools_discovered()
    return registry.check_toolset_requirements()



def _build_maps():
    ensure_tools_discovered()
    return registry.get_tool_to_toolset_map(), registry.check_toolset_requirements()


TOOL_TO_TOOLSET_MAP: Dict[str, str] = {}
TOOLSET_REQUIREMENTS: Dict[str, bool] = {}


def refresh_tool_maps():
    """Refresh the global tool->toolset map and requirements.""""
    global TOOL_TO_TOOLSET_MAP, TOOLSET_REQUIREMENTS
    TOOL_TO_TOOLSET_MAP, TOOLSET_REQUIREMENTS = _build_maps()


__all__ = [
    "get_tool_definitions",
    "handle_function_call",
    "get_all_tool_names",
    "get_toolset_for_tool",
    "get_available_toolsets",
    "check_toolset_requirements",
    "TOOL_TO_TOOLSET_MAP",
    "TOOLSET_REQUIREMENTS",
    "refresh_tool_maps",
    "_run_async",
    "_sanitize_tool_error",
]
