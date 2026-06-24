"""

"""
from __future__ import annotations
import os
import sys
import platform
import subprocess
import asyncio
import shutil
import json
import time
import signal
import socket
import resource
from pathlib import Path
from typing import Dict, List, Optional
from minxg.base import BaseWorker, tool


class SystemWorker(BaseWorker):
    worker_id = "system"
    version = "1.0.0"

    @tool(description="Execute shell command, return stdout/stderr/exit_code", category="exec")
    async def execute_command(self, command: str, timeout: int = 60) -> Dict:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return {
                    "command": command, "exit_code": proc.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "timed_out": False,
                }
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"command": command, "exit_code": -1, "error": "timeout",
                        "timed_out": True, "timeout": timeout}
        except Exception as e:
            return {"command": command, "error": str(e), "error_type": type(e).__name__}

    @tool(description="Execute Python code (isolated subprocess)", category="exec")
    async def run_python(self, code: str, timeout: int = 30) -> Dict:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-I", "-u", "-c", "import sys, json; "
                "exec(json.load(sys.stdin)['code']); "
                "print('---DONE---', file=sys.stderr)",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            payload = json.dumps({"code": code})
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(payload.encode()), timeout=timeout)
                return {
                    "exit_code": proc.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "timed_out": False,
                }
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"error": "timeout", "timed_out": True, "timeout": timeout}
        except Exception as e:
            return {"error": str(e), "error_type": type(e).__name__}

    @tool(description="List processes (filter by name)", category="info")
    async def process_list(self, filter_name: str = "", max_count: int = 200) -> Dict:
        try:
            r = await self.execute_command("ps -eo pid,ppid,user,comm,args --no-headers", timeout=10)
            if r.get("exit_code") != 0:
                r = await self.execute_command("ps aux", timeout=10)
            lines = r.get("stdout", "").strip().split("\n")
            procs = []
            for line in lines:
                parts = line.split(None, 4)
                if len(parts) < 5:
                    continue
                pid, ppid, user, comm, args = parts
                if filter_name and (filter_name.lower() not in comm.lower() and filter_name.lower() not in args.lower()):
                    continue
                procs.append({"pid": int(pid), "ppid": int(ppid), "user": user,
                              "command": comm, "args": args})
                if len(procs) >= max_count:
                    break
            return {"count": len(procs), "filter": filter_name, "processes": procs}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="System info (detailed adds CPU/memory)", category="info")
    async def system_info(self, detailed: bool = False) -> Dict:
        info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": platform.node(),
            "python_version": sys.version.split()[0],
            "cpu_count": os.cpu_count(),
            "load_avg": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        }
        if detailed:
            try:
                import psutil  
                info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory()
                info["memory"] = {"total": mem.total, "available": mem.available,
                                  "percent": mem.percent}
            except ImportError:
                info["memory"] = _read_meminfo()
        return info

    @tool(description="CPU info", category="info")
    async def cpu_info(self) -> Dict:
        info = {"cpu_count": os.cpu_count()}
        try:
            with open("/proc/cpuinfo") as f:
                content = f.read()
            import re
            m = re.search(r"Hardware\s*:\s*(.+)", content) \
                or re.search(r"model name\s*:\s*(.+)", content) \
                or re.search(r"Processor\s*:\s*(.+)", content)
            if m:
                info["model"] = m.group(1).strip()
            m = re.search(r"BogoMIPS\s*:\s*([\d.]+)", content)
            if m:
                info["bogomips"] = float(m.group(1))
        except (OSError, FileNotFoundError):
            pass
        return info

    @tool(description="Memory info", category="info")
    async def memory_info(self) -> Dict:
        try:
            import psutil  
            m = psutil.virtual_memory()
            return {"total": m.total, "available": m.available, "percent": m.percent,
                    "used": m.used, "free": m.free,
                    "human_total": _human_size(m.total),
                    "human_available": _human_size(m.available)}
        except ImportError:
            data = _read_meminfo()
            if "error" in data:
                return data
            return {**data, "human_total": _human_size(data["total"]),
                    "human_available": _human_size(data["available"])}

    @tool(description="Disk usage (default current directory)", category="info")
    async def disk_usage(self, path: str = ".") -> Dict:
        try:
            usage = shutil.disk_usage(path)
            return {"path": path, "total": usage.total, "used": usage.used,
                    "free": usage.free, "percent": round(usage.used / usage.total * 100, 1),
                    "human_total": _human_size(usage.total),
                    "human_free": _human_size(usage.free)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Delayed command execution, returns task_id", category="exec")
    async def schedule_task(self, command: str, delay: float = 5.0, task_id: str = "") -> Dict:
        if not task_id:
            task_id = f"task-{int(time.time()*1000)}"
        async def _runner():
            await asyncio.sleep(delay)
            return await self.execute_command(command, timeout=3600)
        task = asyncio.create_task(_runner())
        return {"task_id": task_id, "command": command, "delay": delay,
                 "status": "scheduled"}

    @tool(description="Start TCP listener for debugging, return server info", category="network")
    async def start_tcp_server(self, port: int = 0) -> Dict:
        try:
            async def handler(reader, writer):
                data = await reader.read(1024)
                writer.write(b"HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nOK")
                await writer.drain()
                writer.close()
            server = await asyncio.start_server(handler, "127.0.0.1", port)
            actual_port = server.sockets[0].getsockname()[1]
            return {"host": "127.0.0.1", "port": actual_port, "status": "listening",
                "server_info": {"type": "tcp", "protocol": "http"}}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Get all IP addresses of this machine", category="info")
    async def network_info(self) -> Dict:
        info = {"hostname": socket.gethostname()}
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                info["primary_ip"] = s.getsockname()[0]
            finally:
                s.close()
        except OSError:
            info["primary_ip"] = "127.0.0.1"
        infos = []
        try:
            import psutil  
            for name, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET:
                        infos.append({"interface": name, "ip": a.address})
        except ImportError:
            infos.append({"interface": "default", "ip": info["primary_ip"]})
        info["interfaces"] = infos
        return info


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _read_meminfo() -> Dict:
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip().split()[0]
                    try:
                        info[k.lower()] = int(v) * 1024  
                    except ValueError:
                        info[k.lower()] = v
        if "memtotal" in info and "memavailable" in info:
            return {"total": info["memtotal"], "available": info["memavailable"],
                    "used": info["memtotal"] - info["memavailable"],
                    "free": info.get("memfree", 0),
                    "percent": round((info["memtotal"] - info["memavailable"])
                                     / info["memtotal"] * 100, 1)}
    except (OSError, FileNotFoundError) as e:
        return {"error": str(e)}
    return info
