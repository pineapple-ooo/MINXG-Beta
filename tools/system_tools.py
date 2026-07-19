"""System Tools - System information and management."""

import json
import logging
import os
import platform
import socket
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

logger = logging.getLogger(__name__)

SYSTEM_INFO_SCHEMA = {
    "type": "object",
    "properties": {},
}

PROCESS_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "description": "Max processes to return", "default": 20},
        "sort_by": {"type": "string", "description": "Sort by: cpu, memory, pid", "default": "cpu"},
    },
}

DISK_USAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to check disk usage", "default": "/"},
    },
}

NETWORK_INFO_SCHEMA = {
    "type": "object",
    "properties": {
        "interface": {"type": "string", "description": "Network interface to check"},
    },
}


def _handle_system_info(args: dict) -> str:
    """Get system information."""
    try:
        info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": socket.gethostname(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
        
        if HAS_PSUTIL:
            info.update({
                "cpu_count": psutil.cpu_count(logical=False),
                "cpu_count_logical": psutil.cpu_count(logical=True),
                "memory_total": psutil.virtual_memory().total,
                "memory_available": psutil.virtual_memory().available,
                "memory_percent": psutil.virtual_memory().percent,
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "uptime": f"{(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds():.0f}s",
            })
        else:
            info.update({
                "cpu_count": os.cpu_count(),
                "cpu_count_logical": os.cpu_count(),
                "note": "psutil not available, limited info",
            })
        
        return json.dumps(info)
    except Exception as e:
        return json.dumps({"error": f"system_info error: {e}"})


def _handle_process_list(args: dict) -> str:
    """List running processes."""
    try:
        limit = args.get("limit", 20)
        sort_by = args.get("sort_by", "cpu")
        
        if not HAS_PSUTIL:
            processes = []
            if os.name == "nt":
                try:
                    result = subprocess.run(
                        ["tasklist", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=10,
                    )
                    import csv
                    import io as _io
                    for row in csv.reader(_io.StringIO(result.stdout)):
                        if len(row) < 5:
                            continue
                        name, pid_s, _session, _sess_num, mem_s = row[:5]
                        try:
                            pid = int(pid_s)
                        except ValueError:
                            continue
                        # tasklist reports memory as e.g. "12,345 K"
                        mem_kb = 0
                        try:
                            mem_kb = int(mem_s.replace(",", "").replace(" K", "").strip())
                        except ValueError:
                            pass
                        processes.append({
                            "pid": pid, "name": name, "cpu": 0,
                            "memory": mem_kb, "user": "unknown",
                        })
                except Exception:
                    pass
            else:
                try:
                    for pid_dir in Path("/proc").iterdir():
                        if not pid_dir.name.isdigit():
                            continue
                        try:
                            pid = int(pid_dir.name)
                            comm = (pid_dir / "comm").read_text().strip()
                            processes.append({
                                "pid": pid,
                                "name": comm,
                                "cpu": 0,
                                "memory": 0,
                                "user": "unknown",
                            })
                        except:
                            pass
                except Exception:
                    pass
            
            if sort_by == "pid":
                processes.sort(key=lambda x: x["pid"])
            elif sort_by == "memory":
                processes.sort(key=lambda x: x["memory"], reverse=True)
            else:
                processes.sort(key=lambda x: x["name"].lower())
        else:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
                try:
                    info = proc.info
                    processes.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "cpu": info['cpu_percent'] or 0,
                        "memory": info['memory_percent'] or 0,
                        "user": info['username'],
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if sort_by == "memory":
                processes.sort(key=lambda x: x["memory"], reverse=True)
            elif sort_by == "pid":
                processes.sort(key=lambda x: x["pid"])
            else:
                processes.sort(key=lambda x: x["cpu"], reverse=True)
        
        return json.dumps({
            "processes": processes[:limit],
            "total": len(processes),
        })
    except Exception as e:
        return json.dumps({"error": f"process_list error: {e}"})


def _handle_disk_usage(args: dict) -> str:
    """Get disk usage information."""
    try:
        path = args.get("path", "/")
        
        if HAS_PSUTIL:
            usage = psutil.disk_usage(path)
            return json.dumps({
                "path": path,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        else:
            import shutil
            usage = shutil.disk_usage(path)
            return json.dumps({
                "path": path,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.used / usage.total * 100, 1),
            })
    except Exception as e:
        return json.dumps({"error": f"disk_usage error: {e}"})


def _handle_network_info(args: dict) -> str:
    """Get network information."""
    try:
        if HAS_PSUTIL:
            interfaces = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            
            result = {}
            for iface, addrs in interfaces.items():
                if args.get("interface") and iface != args["interface"]:
                    continue
                result[iface] = {
                    "addresses": [],
                    "is_up": stats.get(iface, None) and stats[iface].isup,
                }
                for addr in addrs:
                    result[iface]["addresses"].append({
                        "family": str(addr.family),
                        "address": addr.address,
                        "netmask": getattr(addr, 'netmask', None),
                    })
            
            io_counters = psutil.net_io_counters()
            result["_totals"] = {
                "bytes_sent": io_counters.bytes_sent,
                "bytes_recv": io_counters.bytes_recv,
                "packets_sent": io_counters.packets_sent,
                "packets_recv": io_counters.packets_recv,
            }
            
            return json.dumps(result)
        else:
            hostname = socket.gethostname()
            return json.dumps({
                "hostname": hostname,
                "note": "psutil not available, limited network info",
            })
    except Exception as e:
        return json.dumps({"error": f"network_info error: {e}"})


def _check_system_reqs() -> bool:
    """Check if system tools are available."""
    return True


from tools.registry import registry

registry.register(
    name="system_info",
    toolset="system",
    schema=SYSTEM_INFO_SCHEMA,
    handler=_handle_system_info,
    check_fn=_check_system_reqs,
    emoji="🖥️",
    max_result_size_chars=5000,
)

registry.register(
    name="process_list",
    toolset="system",
    schema=PROCESS_LIST_SCHEMA,
    handler=_handle_process_list,
    check_fn=_check_system_reqs,
    emoji="",
    max_result_size_chars=20000,
)

registry.register(
    name="disk_usage",
    toolset="system",
    schema=DISK_USAGE_SCHEMA,
    handler=_handle_disk_usage,
    check_fn=_check_system_reqs,
    emoji="",
    max_result_size_chars=5000,
)

registry.register(
    name="network_info",
    toolset="system",
    schema=NETWORK_INFO_SCHEMA,
    handler=_handle_network_info,
    check_fn=_check_system_reqs,
    emoji="🌐",
    max_result_size_chars=10000,
)
