"""


"""
from __future__ import annotations
import asyncio
import functools
import json
import logging
import time
from typing import Any, Dict, List, Optional

from gateway.config import GatewayConfig

logger = logging.getLogger("gateway.router")


class WorkerRoute:
    def __init__(self, name: str, url: str, lang: str = "py", enabled: bool = True):
        self.name = name
        self.url = url.rstrip("/")
        self.lang = lang
        self.enabled = enabled
        self._tools_cache: Optional[Dict[str, Any]] = None
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 30.0

    async def _fetch(self, session, method: str, path: str, json_body=None, timeout: float = None):
        import aiohttp
        timeout = timeout or (15 if method == "GET" else 65)
        try:
            if method == "GET":
                async with session.get(f"{self.url}{path}", timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                    return await r.json(), r.status
            else:
                async with session.post(f"{self.url}{path}", json=json_body,
                                        timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                    return await r.json(), r.status
        except Exception as e:
            logger.warning("[%s] %s %s failed: %s", self.name, method, path, e)
            return None, 0

    async def health(self, session) -> Dict[str, Any]:
        data, status = await self._fetch(session, "GET", "/health")
        return {"name": self.name, "status": status, "data": data or {}}

    async def tools(self, session) -> Dict[str, Any]:
        now = time.time()
        if self._tools_cache and (now - self._cache_ts) < self._cache_ttl:
            return self._tools_cache
        data, status = await self._fetch(session, "GET", "/tools")
        if status == 200 and data:
            self._tools_cache = data
            self._cache_ts = now
            return data
        return {}

    async def execute(self, session, worker: str, tool: str, params: Dict) -> Dict[str, Any]:
        timeout = float(params.pop("_timeout", 30) if isinstance(params, dict) else 30)
        payload = {"worker": worker, "tool": tool, "params": params, "timeout": timeout}
        data, status = await self._fetch(session, "POST", "/rpc", payload, timeout=timeout + 5)
        if status == 200 and data:
            return data
        if data and "error" in data:
            return {"status": "error", "error": data.get("error", "unknown"), "worker": worker, "tool": tool}
        return {"status": "error", "error": f"HTTP {status} from {self.name}", "worker": worker, "tool": tool}


class WorkerRouter:

    def __init__(self, py_url: str = "http://127.0.0.1:19001",
                 legacy_routes: List[Dict] = None,
                 enable_legacy: bool = False):
        self.routes: List[WorkerRoute] = []
        self.routes.append(WorkerRoute("py_workers", py_url, lang="py", enabled=True))

        if enable_legacy and legacy_routes:
            for r in legacy_routes:
                self.routes.append(WorkerRoute(
                    r.get("name", "legacy"),
                    r.get("url", ""),
                    lang=r.get("lang", "unknown"),
                    enabled=r.get("enabled", True),
                ))

        self._session: Optional[Any] = None
        self._worker_route_cache: Dict[str, WorkerRoute] = {}
        self._worker_tool_cache: Dict[str, set] = {}
        logger.info("WorkerRouter initialized: %d routes", len(self.routes))
        for r in self.routes:
            logger.info("  - %s (%s) @ %s [%s]", r.name, r.lang, r.url,
                       "enabled" if r.enabled else "disabled")

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def health_all(self) -> List[Dict]:
        session = await self._get_session()
        results = await asyncio.gather(*[r.health(session) for r in self.routes if r.enabled])
        return list(results)

    async def fetch_tools(self) -> List[Dict]:
        session = await self._get_session()
        schemas = []
        worker_route_cache: Dict[str, WorkerRoute] = {}
        worker_tool_cache: Dict[str, set] = {}
        for route in self.routes:
            if not route.enabled:
                continue
            data = await route.tools(session)
            workers = data.get("workers", {})
            for worker_id, tools in workers.items():
                worker_route_cache[worker_id] = route
                worker_tool_cache[worker_id] = {t.get("name", "") for t in tools}
                for t in tools:
                    fname = f"{worker_id}__{t['name']}"
                    params = t.get("params", {})
                    properties = {}
                    required = []
                    for pname, ptype in params.items():
                        json_type = {"string": "string", "integer": "integer", "int": "integer",
                                     "number": "number", "float": "number", "bool": "boolean",
                                     "boolean": "boolean", "dict": "object", "list": "array",
                                     "any": "string"}.get(ptype, "string")
                        properties[pname] = {"type": json_type}
                        required.append(pname)
                    schemas.append({
                        "type": "function",
                        "function": {
                            "name": fname,
                            "description": f"[{route.lang}/{worker_id}] {t.get('description', '')}",
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required,
                            },
                        },
                    })
        self._worker_route_cache = worker_route_cache
        self._worker_tool_cache = worker_tool_cache
        return schemas

    async def execute_tool(self, full_name: str, arguments: Dict) -> Dict[str, Any]:
        session = await self._get_session()

        if "__" in full_name:
            worker_id, tool_name = full_name.split("__", 1)
        else:
            worker_id = None
            for cached_worker, tool_names in self._worker_tool_cache.items():
                if full_name in tool_names:
                    worker_id = cached_worker
                    break
            for r in self.routes:
                if worker_id:
                    break
                if r.lang == "py" and r.enabled:
                    data = await r.tools(session)
                    for wname, tools in (data.get("workers", {})).items():
                        if any(t["name"] == full_name for t in tools):
                            worker_id = wname
                            break
                if worker_id:
                    break
            if not worker_id:
                return {"status": "error", "error": f"Cannot resolve tool: {full_name}"}
            tool_name = full_name

        cached_route = self._worker_route_cache.get(worker_id)
        if cached_route and cached_route.enabled:
            return await cached_route.execute(session, worker_id, tool_name, arguments)

        for route in self.routes:
            if not route.enabled:
                continue
            data = await route.tools(session)
            if worker_id in (data.get("workers", {})):
                return await route.execute(session, worker_id, tool_name, arguments)

        return {"status": "error", "error": f"No route for worker: {worker_id}"}

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def get_routes_summary(self) -> List[Dict]:
        return [{"name": r.name, "lang": r.lang, "url": r.url, "enabled": r.enabled}
                for r in self.routes]
