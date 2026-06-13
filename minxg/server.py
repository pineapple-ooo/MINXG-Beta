"""
minxg/server.py — HTTP RPC server for minxg v1.0.0

  GET  /health       -> {"status":"ok", "version":"1.0.0", "registered_workers":[...]}
  GET  /tools        -> {"workers": {"fs_io": [...], ...}}
  POST /rpc          -> body: {"worker":"fs_io","tool":"read_file","params":{"path":"..."}}
"""
from __future__ import annotations
import os
import sys
import json
import asyncio
import logging
import argparse
import time
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s | %(levelname)-7s | %(message)s',
                    handlers=[logging.StreamHandler(sys.stderr)])
log = logging.getLogger("py_workers.server")

ALL_WORKERS: Dict[str, type] = {}


def _discover_workers():
    """Import and register all worker classes."""
    from .fs_io import FsIoWorker
    from .fs_copy import FsCopyWorker
    from .fs_search import FsSearchWorker
    from .system import SystemWorker
    from .network import NetworkWorker
    from .sh_query import ShQueryWorker
    from .sh_exec import ShExecWorker
    from .state_session import StateSessionWorker
    from .state_machine import StateMachineWorker
    from .limits_lock import LimitsLockWorker
    from .limits_break import LimitsBreakWorker
    from .persistence import PersistenceWorker
    from .rules import RulesWorker
    from .events import EventsWorker
    from .hotreload import HotReloadWorker
    from .text_tools import TextToolsWorker
    from .encoding_tools import EncodingToolsWorker
    from .math_tools import MathToolsWorker
    from .datetime_tools import DateTimeToolsWorker
    from .ai_tools import AiToolsWorker
    from .media_tools import MediaToolsWorker
    from .data_tools import DataToolsWorker
    from .crypto_tools import CryptoToolsWorker
    from .db_tools import DbToolsWorker
    from .web_tools import WebToolsWorker
    from .template_tools import TemplateToolsWorker
    from .benchmark_tools import BenchmarkToolsWorker
    from .cloud_tools import CloudToolsWorker
    from .security_tools import SecurityToolsWorker
    from .ml_tools import MlToolsWorker
    from .process_tools import ProcessToolsWorker
    from .platform_tools import PlatformWorker
    from .notify_tools import NotifyWorker
    from .i18n_tools import I18nWorker
    from .string_tools import StringWorker
    from .version_tools import VersionWorker
    from .color_tools import ColorWorker
    from .markdown_tools import MarkdownWorker
    from .archive_tools import ArchiveWorker
    from .network_adv import NetworkAdvWorker
    from .dev_tools import DevToolsWorker
    from .media_adv import MediaAdvWorker
    from .adb_tools import AdbWorker
    from .root_tools import RootWorker
    from .operators import OperatorWorker

    ALL_WORKERS.update({
        "fs_io": FsIoWorker, "fs_copy": FsCopyWorker, "fs_search": FsSearchWorker,
        "system": SystemWorker, "network": NetworkWorker,
        "sh_query": ShQueryWorker, "sh_exec": ShExecWorker,
        "state_session": StateSessionWorker, "state_machine": StateMachineWorker,
        "limits_lock": LimitsLockWorker, "limits_break": LimitsBreakWorker,
        "persistence": PersistenceWorker, "rules": RulesWorker,
        "events": EventsWorker, "hotreload": HotReloadWorker,
        "text_tools": TextToolsWorker, "encoding_tools": EncodingToolsWorker,
        "math_tools": MathToolsWorker, "datetime_tools": DateTimeToolsWorker,
        "ai_tools": AiToolsWorker, "media_tools": MediaToolsWorker,
        "data_tools": DataToolsWorker, "crypto_tools": CryptoToolsWorker,
        "db_tools": DbToolsWorker, "web_tools": WebToolsWorker,
        "template_tools": TemplateToolsWorker, "benchmark_tools": BenchmarkToolsWorker,
        "cloud_tools": CloudToolsWorker, "security_tools": SecurityToolsWorker,
        "ml_tools": MlToolsWorker, "process_tools": ProcessToolsWorker,
        "platform": PlatformWorker, "notify": NotifyWorker,
        "i18n": I18nWorker, "string": StringWorker,
        "version": VersionWorker, "color": ColorWorker,
        "markdown": MarkdownWorker,
        "archive": ArchiveWorker, "network_adv": NetworkAdvWorker,
        "dev_tools": DevToolsWorker, "media_adv": MediaAdvWorker,
        "adb": AdbWorker, "root": RootWorker, "operator": OperatorWorker,
    })


async def start_server(host: str = "127.0.0.1", port: int = 19001,
                       workers: List[str] = None) -> None:
    """Start the HTTP RPC server."""
    from aiohttp import web
    from .base import WorkerRegistry

    if not ALL_WORKERS:
        _discover_workers()

    registry = WorkerRegistry()
    selected = workers or list(ALL_WORKERS.keys())
    for name in selected:
        if name not in ALL_WORKERS:
            continue
        registry.register(ALL_WORKERS[name]())

    async def health(req):
        total_tools = sum(len(w.tools) for w in registry.workers.values())
        return web.json_response({
            "status": "ok", "worker": "py", "version": "1.0.0",
            "registered_workers": list(registry.workers.keys()),
            "port": port, "total_tools": total_tools,
            "uptime_hint": "see /stats"
        })

    async def tools(req):
        worker_filter = req.match_info.get("worker") or req.query.get("worker")
        if worker_filter:
            w = registry.get(worker_filter)
            data = {worker_filter: w.list_tools() if w else []}
        else:
            data = {wid: w.list_tools() for wid, w in registry.workers.items()}
        return web.json_response({"workers": data})

    async def stats(req):
        worker_filter = req.match_info.get("worker")
        if worker_filter:
            w = registry.get(worker_filter)
            data = {worker_filter: w.statistics() if w else {}}
        else:
            data = {wid: w.statistics() for wid, w in registry.workers.items()}
        return web.json_response({"workers": data})

    async def rpc(req):
        t0 = time.time()
        try:
            body = await req.json()
        except json.JSONDecodeError as e:
            return web.json_response({"status": "error", "error": f"invalid JSON: {e}"}, status=400)
        wid = body.get("worker", "")
        tool_name = body.get("tool", "")
        params = body.get("params", {}) or {}
        timeout = float(body.get("timeout", 60))
        if not wid or not tool_name:
            return web.json_response({"status": "error", "error": "worker and tool required"}, status=400)
        try:
            result = await asyncio.wait_for(registry.call(wid, tool_name, params), timeout=timeout)
            elapsed = round((time.time() - t0) * 1000, 2)
            return web.json_response({
                "status": result.get("status", "success"),
                "worker": wid, "tool": tool_name,
                "elapsed_ms": elapsed,
                "result": {k: v for k, v in result.items() if k != "status"},
            })
        except asyncio.TimeoutError:
            return web.json_response({"status": "error", "worker": wid, "tool": tool_name,
                                     "error": f"timeout after {timeout}s"}, status=408)
        except Exception as e:
            return web.json_response({"status": "error", "worker": wid, "tool": tool_name,
                                     "error": str(e)}, status=500)

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/tools", tools)
    app.router.add_get("/tools/{worker}", tools)
    app.router.add_get("/stats", stats)
    app.router.add_get("/stats/{worker}", stats)
    app.router.add_post("/rpc", rpc)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port, reuse_address=True)
    try:
        await site.start()
    except OSError:
        log.error("Port %d already in use or permission denied", port)
        sys.exit(1)
    total_tools = sum(len(w.tools) for w in registry.workers.values())
    log.info("   workers (%d): %s", len(registry.workers), ", ".join(registry.workers.keys()))
    log.info("   total_tools: %d", total_tools)
    log.info("   endpoints: GET /health /tools /stats (/tools/{worker} /stats/{worker}), POST /rpc")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        await runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description="py_workers HTTP RPC server v1.0.0")
    parser.add_argument("--host", default=os.environ.get("WORKER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WORKER_PORT", "19001")))
    parser.add_argument("--workers", nargs="*", default=None,
                        help="Specific workers to start (default: all)")
    args = parser.parse_args()
    try:
        asyncio.run(start_server(args.host, args.port, args.workers))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()