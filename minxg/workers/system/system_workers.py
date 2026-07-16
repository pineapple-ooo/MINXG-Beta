"""
MINXG System Workers — System information and process management.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional


class SystemInfoWorker:
    """Get system information."""
    worker_id = "system_info"
    version = "0.19.0"

    def execute(self) -> Dict[str, Any]:
        import platform
        import os
        import socket

        return {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
            "python_version": platform.python_version(),
            "os_name": os.name,
            "cwd": os.getcwd(),
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
        }


class ProcessWorker:
    """Process management."""
    worker_id = "process"
    version = "0.19.0"

    def execute(self, operation: str = "list", pid: Optional[int] = None,
                command: Optional[str] = None) -> Dict[str, Any]:
        import subprocess
        import os
        import signal

        if operation == "list":
            try:
                if os.name == "nt":
                    result = subprocess.run(["tasklist"], capture_output=True, text=True)
                else:
                    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                return {"processes": result.stdout[:50000]}
            except Exception as e:
                return {"error": str(e)}
        elif operation == "kill":
            if pid is None:
                return {"error": "pid required"}
            try:
                os.kill(pid, signal.SIGTERM)
                return {"killed": pid}
            except Exception as e:
                return {"error": str(e)}
        elif operation == "kill_force":
            if pid is None:
                return {"error": "pid required"}
            try:
                os.kill(pid, signal.SIGKILL)
                return {"killed": pid}
            except Exception as e:
                return {"error": str(e)}
        elif operation == "run":
            if command is None:
                return {"error": "command required"}
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                return {
                    "command": command,
                    "stdout": result.stdout[:10000],
                    "stderr": result.stderr[:5000],
                    "returncode": result.returncode,
                }
            except subprocess.TimeoutExpired:
                return {"error": "Command timed out"}
            except Exception as e:
                return {"error": str(e)}
        else:
            return {"error": f"Unsupported operation: {operation}"}


class DiskWorker:
    """Disk usage information."""
    worker_id = "disk"
    version = "0.19.0"

    def execute(self, path: str = "/") -> Dict[str, Any]:
        import os
        import shutil

        try:
            total, used, free = shutil.disk_usage(path)
            return {
                "path": path,
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "used_percent": (used / total) * 100,
                "free_percent": (free / total) * 100,
                "total_human": _human_size(total),
                "used_human": _human_size(used),
                "free_human": _human_size(free),
            }
        except Exception as e:
            return {"error": str(e)}


class MemoryInfoWorker:
    """Memory usage information."""
    worker_id = "memory_info"
    version = "0.19.0"

    def execute(self) -> Dict[str, Any]:
        import os

        try:
            # Try psutil first
            try:
                import psutil
                mem = psutil.virtual_memory()
                return {
                    "total": _human_size(mem.total),
                    "available": _human_size(mem.available),
                    "used": _human_size(mem.used),
                    "used_percent": mem.percent,
                    "free": _human_size(mem.free),
                }
            except ImportError:
                # Fallback for Linux
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                meminfo = {}
                for line in lines:
                    parts = line.split()
                    meminfo[parts[0].rstrip(":")] = int(parts[1]) * 1024  # Convert kB to bytes

                total = meminfo.get("MemTotal", 0)
                free = meminfo.get("MemFree", 0)
                available = meminfo.get("MemAvailable", free)
                used = total - available

                return {
                    "total": _human_size(total),
                    "available": _human_size(available),
                    "used": _human_size(used),
                    "used_percent": (used / total) * 100,
                    "free": _human_size(free),
                }
        except Exception as e:
            return {"error": str(e)}


class CPUInfoWorker:
    """CPU information."""
    worker_id = "cpu_info"
    version = "0.19.0"

    def execute(self) -> Dict[str, Any]:
        import os
        import platform

        try:
            try:
                import psutil
                cpu_count = psutil.cpu_count()
                cpu_freq = psutil.cpu_freq()
                cpu_percent = psutil.cpu_percent(interval=0.1)
                per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)

                return {
                    "physical_cores": psutil.cpu_count(logical=False),
                    "logical_cores": cpu_count,
                    "frequency_mhz": cpu_freq.current if cpu_freq else None,
                    "usage_percent": cpu_percent,
                    "per_cpu_usage": per_cpu,
                }
            except ImportError:
                # Fallback
                cpu_count = os.cpu_count() or 1
                return {
                    "physical_cores": cpu_count,
                    "logical_cores": cpu_count,
                    "note": "psutil not available",
                }
        except Exception as e:
            return {"error": str(e)}


class NetworkInterfacesWorker:
    """Network interface information."""
    worker_id = "network_interfaces"
    version = "0.19.0"

    def execute(self) -> Dict[str, Any]:
        import socket
        import struct

        try:
            import psutil
            interfaces = psutil.net_if_addrs()
            result = {}
            for iface_name, addrs in interfaces.items():
                result[iface_name] = []
                for addr in addrs:
                    result[iface_name].append({
                        "family": addr.family.name,
                        "address": addr.address,
                        "netmask": addr.netmask,
                    })
            return {"interfaces": result}
        except ImportError:
            # Fallback
            hostname = socket.gethostname()
            try:
                ip = socket.gethostbyname(hostname)
                return {"interfaces": {"default": [{"address": ip}]}}
            except Exception as e:
                return {"error": str(e)}


class EnvironmentWorker:
    """Environment variables."""
    worker_id = "environment"
    version = "0.19.0"

    def execute(self, name: Optional[str] = None) -> Dict[str, Any]:
        import os

        if name:
            value = os.environ.get(name)
            if value is None:
                return {"name": name, "set": False}
            return {"name": name, "value": value, "set": True}
        else:
            return {"variables": dict(os.environ)}


class UptimeWorker:
    """System uptime."""
    worker_id = "uptime"
    version = "0.19.0"

    def execute(self) -> Dict[str, Any]:
        import time

        try:
            import psutil
            boot_time = psutil.boot_time()
        except ImportError:
            # Fallback for Linux
            try:
                with open("/proc/uptime") as f:
                    uptime_seconds = float(f.readline().split()[0])
                boot_time = time.time() - uptime_seconds
            except Exception:
                boot_time = time.time() - 3600  # Assume 1 hour

        uptime_seconds = time.time() - boot_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)

        return {
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{days}d {hours}h {minutes}m",
            "boot_time": time.ctime(boot_time),
        }


class FileDescriptorWorker:
    """File descriptor information."""
    worker_id = "file_descriptors"
    version = "0.19.0"

    def execute(self) -> Dict[str, Any]:
        import os

        try:
            import psutil
            proc = psutil.Process()
            return {
                "open_files": [f.path for f in proc.open_files()],
                "connections": [(c.laddr, c.raddr, c.status) for c in proc.connections()],
                "num_fds": proc.num_fds() if hasattr(proc, "num_fds") else "N/A",
            }
        except ImportError:
            # Fallback
            try:
                fd_path = f"/proc/{os.getpid()}/fd"
                fds = os.listdir(fd_path)
                return {"num_fds": len(fds), "note": "psutil not available"}
            except Exception as e:
                return {"error": str(e)}


def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"
