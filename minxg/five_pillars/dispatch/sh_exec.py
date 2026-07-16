"""
network_ping, network_port_check, network_download, network_http
"""
from __future__ import annotations
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List
from minxg.base import BaseWorker, tool
from minxg.five_pillars.dispatch.system import SystemWorker
from minxg.five_pillars.io.network import NetworkWorker


class ShExecWorker(BaseWorker):
    worker_id = "sh_exec"
    tier = "code"  # v0.18.0 three-tier classification
    version = "0.17.1"

    def __init__(self):
        super().__init__()
        self._sys = SystemWorker()
        self._net = NetworkWorker()

    @tool(description="In-place text replacement (sed-style)", category="text")
    async def text_sed(self, path: str, find: str, replace: str,
                      regex: bool = False, limit: int = 0) -> Dict:
        p = Path(path)
        if not p.is_file():
            return {"error": f"not a file: {path}"}
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            if regex:
                if limit > 0:
                    new_text, n = re.subn(find, replace, text, count=limit)
                else:
                    new_text, n = re.subn(find, replace, text)
            else:
                if limit > 0:
                    new_text, n = text.replace(find, replace, limit), text.count(find)
                    n = min(n, limit)
                else:
                    n = text.count(find)
                    new_text = text.replace(find, replace)
            if n > 0:
                p.write_text(new_text, encoding="utf-8")
            return {"path": str(p), "replacements": n, "modified": n > 0}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Find command path", category="info")
    async def which(self, command: str) -> Dict:
        path = shutil.which(command)
        return {"command": command, "path": path, "found": path is not None}

    @tool(description="Execute shell command directly (escape hatch, use carefully)", category="exec")
    async def raw_execute(self, command: str, timeout: int = 60) -> Dict:
        return await self._sys.execute_command(command=command, timeout=timeout)

    @tool(description="List executables in PATH (limit 1000)", category="info")
    async def list_path_binaries(self) -> Dict:
        bins = []
        for d in os.environ.get("PATH", "").split(":"):
            if not d or not os.path.isdir(d):
                continue
            try:
                for f in os.listdir(d):
                    fp = os.path.join(d, f)
                    if os.path.isfile(fp) and os.access(fp, os.X_OK):
                        bins.append(f)
            except (PermissionError, OSError):
                pass
        bins = sorted(set(bins))
        return {"count": len(bins), "binaries": bins[:1000]}

    @tool(description="TCP port ping", category="network")
    async def network_ping(self, host: str, port: int = 80, count: int = 4) -> Dict:
        return await self._net.ping(host=host, port=port, count=count)

    @tool(description="Port check", category="network")
    async def network_port_check(self, host: str, port: int, timeout: float = 3.0) -> Dict:
        return await self._net.port_check(host=host, port=port, timeout=timeout)

    @tool(description="HTTP download", category="network")
    async def network_download(self, url: str, output_path: str) -> Dict:
        return await self._net.download_file(url=url, output_path=output_path)

    @tool(description="HTTP request", category="network")
    async def network_http(self, url: str, method: str = "GET", body: str = None) -> Dict:
        return await self._net.http_request(url=url, method=method, body=body)
