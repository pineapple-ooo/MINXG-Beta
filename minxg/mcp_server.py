"""
MINXG MCP Server — Expose MINXG workers as MCP tools

Connect Claude Code, Cursor, ChatGPT, and any MCP-compatible client
to MINXG's 70+ workers: file I/O, network, crypto, math, polyglot, and more.

Usage:
    # stdio (local agent)
    python -m minxg.mcp_server

    # HTTP (remote deployment)
    MCP_TRANSPORT=http python -m minxg.mcp_server

Install:
    pip install minxg-beta fastmcp
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# ─── MCP Framework ──────────────────────────────────────────────────────────

try:
    from fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None  # type: ignore[misc,assignment]

# ─── MINXG Workers ──────────────────────────────────────────────────────────

try:
    import minxg
    from minxg import (
        FsIoWorker, FsCopyWorker, FsSearchWorker,
        NetworkWorker, CryptoToolsWorker, MathToolsWorker,
        TextToolsWorker, DataToolsWorker, EncodingToolsWorker,
        TemplateToolsWorker, I18nWorker, MlToolsWorker,
        SystemWorker, ShExecWorker, ProcessToolsWorker,
        PlatformWorker, DevToolsWorker, SecurityToolsWorker,
        StateSessionWorker, PersistenceWorker, EventsWorker,
        AiToolsWorker, OperatorWorker,
    )
    _MINXG_AVAILABLE = True
except ImportError:
    _MINXG_AVAILABLE = False
    minxg = None  # type: ignore[assignment]

# ─── Worker Registry ────────────────────────────────────────────────────────

class WorkerRegistry:
    """Lazy-load MINXG workers and expose them as MCP tools."""

    WORKERS = [
        # File I/O
        ("fs_io", FsIoWorker),
        ("fs_copy", FsCopyWorker),
        ("fs_search", FsSearchWorker),
        # Network & System
        ("network", NetworkWorker),
        ("system", SystemWorker),
        ("sh_exec", ShExecWorker),
        ("process", ProcessToolsWorker),
        ("platform", PlatformWorker),
        ("dev_tools", DevToolsWorker),
        ("security", SecurityToolsWorker),
        # Data & Crypto
        ("crypto", CryptoToolsWorker),
        ("encoding", EncodingToolsWorker),
        ("data", DataToolsWorker),
        ("template", TemplateToolsWorker),
        ("math", MathToolsWorker),
        ("text", TextToolsWorker),
        ("i18n", I18nWorker),
        ("ml", MlToolsWorker),
        # State & AI
        ("state", StateSessionWorker),
        ("persistence", PersistenceWorker),
        ("events", EventsWorker),
        ("ai", AiToolsWorker),
        # Operator Engine
        ("operators", OperatorWorker),
    ]

    def __init__(self) -> None:
        self._workers: Dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded or not _MINXG_AVAILABLE:
            return
        self._loaded = True
        for key, cls in self.WORKERS:
            try:
                self._workers[key] = cls()
            except Exception as e:
                print(f"WARNING: Failed to load worker '{key}': {e}", file=sys.stderr)

    def get_tools(self) -> List[Dict[str, str]]:
        """Return all registered tools with metadata."""
        self.load()
        tools: List[Dict[str, str]] = []
        for worker_key, worker in self._workers.items():
            for tool_name, tool_def in getattr(worker, "tools", {}).items():
                tools.append({
                    "worker": worker_key,
                    "name": tool_name,
                    "description": getattr(tool_def, "description", ""),
                    "category": getattr(tool_def, "category", "general"),
                })
        return tools

    async def call_tool(self, worker_key: str, tool_name: str, params: dict) -> Dict[str, Any]:
        """Call a tool by worker + tool name."""
        self.load()
        worker = self._workers.get(worker_key)
        if not worker:
            return {"status": "error", "error": f"unknown worker: {worker_key}"}

        tool_def = worker.tools.get(tool_name)
        if not tool_def:
            return {
                "status": "error",
                "error": f"unknown tool: {tool_name}",
                "available": sorted(worker.tools.keys()),
            }

        try:
            result = await worker.call(tool_name, params)
            return {"status": "ok", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}


registry = WorkerRegistry()

# ─── MCP Server ─────────────────────────────────────────────────────────────

SERVER_NAME = "minxg"
SERVER_VERSION = os.getenv("MINXG_VERSION", "0.18.0")

if FastMCP is not None:
    mcp = FastMCP(
        name=SERVER_NAME,
        instructions=f"""
MINXG MCP Server v{SERVER_VERSION}

A modular AI worker platform exposing 70+ tools for:
- File I/O: read, write, search, copy files
- Network: HTTP requests, DNS, ping, port scan
- Crypto: hash, encrypt, decrypt, sign, verify
- Math: 300+ mathematical operators across 6 pillars
- Text: formatting, templating, markdown
- Data: CSV, JSON, encoding, compression
- System: process management, platform detection
- AI: LLM integration, RAG, embeddings

All tools are pure Python (no compiled dependencies on install).
Android (Termux) + Windows + Linux supported.
""",
    )
else:
    mcp = None

# ─── MCP Tools ──────────────────────────────────────────────────────────────

_ERROR_MSG = {"error": "Install fastmcp or mcp package: pip install fastmcp"}

if mcp is not None:
    @mcp.tool()
    async def minxg_list_tools(category: Optional[str] = None) -> List[Dict[str, str]]:
        """List all available MINXG tools, optionally filtered by category."""
        tools = registry.get_tools()
        return [t for t in tools if not category or t.get("category") == category] if category else tools

    @mcp.tool()
    async def minxg_call_tool(worker: str, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a MINXG tool by worker key and tool name."""
        return await registry.call_tool(worker, tool, params)

    @mcp.tool()
    async def minxg_file_read(path: str, lines: int = 0, start: int = 0) -> Dict[str, Any]:
        """Read a file from disk."""
        return await registry.call_tool("fs_io", "read_file", {"path": path, "lines": lines, "start": start})

    @mcp.tool()
    async def minxg_file_write(path: str, content: str, append: bool = False) -> Dict[str, Any]:
        """Write content to a file."""
        return await registry.call_tool("fs_io", "write_file", {"path": path, "content": content, "append": append})

    @mcp.tool()
    async def minxg_list_dir(path: str = ".", show_hidden: bool = False) -> Dict[str, Any]:
        """List directory contents."""
        return await registry.call_tool("fs_io", "list_directory", {"path": path, "show_hidden": show_hidden})

    @mcp.tool()
    async def minxg_http_get(url: str, timeout: int = 30) -> Dict[str, Any]:
        """Make an HTTP GET request."""
        return await registry.call_tool("network", "http_get", {"url": url, "timeout": timeout})

    @mcp.tool()
    async def minxg_hash(data: str, algorithm: str = "sha256") -> Dict[str, Any]:
        """Hash data with various algorithms (md5, sha1, sha256, sha512, blake2b)."""
        return await registry.call_tool("crypto", "hash", {"data": data, "algorithm": algorithm})

    @mcp.tool()
    async def minxg_math_eval(expression: str) -> Dict[str, Any]:
        """Evaluate a mathematical expression safely."""
        return await registry.call_tool("math", "safe_eval", {"expression": expression})

    @mcp.tool()
    async def minxg_version() -> Dict[str, Any]:
        """Get MINXG version and platform info."""
        if _MINXG_AVAILABLE and minxg:
            return {
                "version": minxg.VERSION,
                "platform": minxg.detect_platform(),
                "workers": len(minxg.__all__),
            }
        return {"version": SERVER_VERSION, "platform": "unknown", "workers": 0}
else:
    # Fallback stubs when MCP framework is not installed
    async def minxg_list_tools(category: Optional[str] = None) -> List[Dict[str, str]]:
        return []

    async def minxg_call_tool(worker: str, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return _ERROR_MSG

    async def minxg_file_read(path: str, lines: int = 0, start: int = 0) -> Dict[str, Any]:
        return _ERROR_MSG

    async def minxg_file_write(path: str, content: str, append: bool = False) -> Dict[str, Any]:
        return _ERROR_MSG

    async def minxg_list_dir(path: str = ".", show_hidden: bool = False) -> Dict[str, Any]:
        return _ERROR_MSG

    async def minxg_http_get(url: str, timeout: int = 30) -> Dict[str, Any]:
        return _ERROR_MSG

    async def minxg_hash(data: str, algorithm: str = "sha256") -> Dict[str, Any]:
        return _ERROR_MSG

    async def minxg_math_eval(expression: str) -> Dict[str, Any]:
        return _ERROR_MSG

    async def minxg_version() -> Dict[str, Any]:
        return {"version": SERVER_VERSION, **_ERROR_MSG}

# ─── Entry Point ────────────────────────────────────────────────────────────

def main() -> None:
    """Run the MCP server."""
    if mcp is None:
        print("ERROR: fastmcp or mcp package required. Install with: pip install fastmcp", file=sys.stderr)
        sys.exit(1)

    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "http":
        host = os.getenv("MCP_HTTP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_HTTP_PORT", "8000"))
        print(f"Starting MINXG MCP Server on {host}:{port} (HTTP)")
        mcp.run(transport="streamable-http", host=host, port=port)
    else:
        print("Starting MINXG MCP Server (stdio)")
        mcp.run()


if __name__ == "__main__":
    main()
