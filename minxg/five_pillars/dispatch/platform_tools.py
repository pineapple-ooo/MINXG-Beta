"""Platform-aware tools — adapt behavior based on device capabilities."""
from minxg.base import BaseWorker, tool

class PlatformWorker(BaseWorker):
    worker_id = "platform_worker"
    version = "0.0.1"

    @tool
    async def platform_info(self) -> dict:
        """Get detailed platform information (OS, CPU, RAM, GPU, etc.)."""
        import platform, os
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "hostname": platform.node(),
        }

    @tool
    async def platform_capabilities(self) -> dict:
        """Get what this device can and cannot do."""
        try:
            import sys; sys.path.insert(0, '.')
            from src.platform_adapters import adapter
            return adapter.json_profile()
        except:
            return {"error": "Platform adapter not available"}

    @tool
    async def tool_availability(self, tool_name: str = "") -> dict:
        """Check if a tool is available on this platform. Empty = list all."""
        try:
            import sys; sys.path.insert(0, '.')
            from src.platform_adapters import adapter
            if tool_name:
                ok, reason = adapter.check_tool_by_id(tool_name)
                return {"tool": tool_name, "available": ok, "reason": reason}
            return {"available_count": adapter.available_tool_count, "total": adapter.total_tools_defined}
        except:
            return {"error": "Platform adapter not available"}

    @tool
    async def device_class(self) -> dict:
        """Get device classification (high/mid/low/minimal)."""
        try:
            import sys; sys.path.insert(0, '.')
            from src.platform_adapters import adapter
            return {"device_class": adapter.device_class.value, "tier": adapter.tier.value, "mode": adapter.mode.value}
        except:
            return {"device_class": "unknown"}

    @tool
    async def ram_usage(self) -> dict:
        """Get current RAM usage."""
        try:
            import sys; sys.path.insert(0, '.')
            from src.platform_adapters import adapter
            return {"total_mb": adapter.ram_total_mb, "free_mb": adapter.ram_free_mb, "used_pct": round((1 - adapter.ram_free_mb/max(adapter.ram_total_mb,1))*100)}
        except:
            try:
                import psutil
                m = psutil.virtual_memory()
                return {"total_mb": m.total//(1024*1024), "free_mb": m.available//(1024*1024), "used_pct": m.percent}
            except:
                return {"error": "Cannot read memory"}

    @tool
    async def disk_usage(self) -> dict:
        """Get disk usage."""
        import shutil
        usage = shutil.disk_usage("/")
        return {"total_gb": round(usage.total/(1024**3),2), "free_gb": round(usage.free/(1024**3),2), "used_pct": round((1-usage.free/usage.total)*100)}

    @tool
    async def battery_status(self) -> dict:
        """Get battery status (mobile only)."""
        try:
            from pathlib import Path
            bats = list(Path("/sys/class/power_supply").glob("BAT*"))
            if bats:
                cap = int((bats[0]/"capacity").read_text().strip())
                status = (bats[0]/"status").read_text().strip()
                return {"percent": cap, "charging": status=="Charging", "present": True}
            return {"present": False}
        except:
            return {"present": False}

    @tool
    async def is_online(self) -> dict:
        """Check if device has internet connectivity."""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return {"online": True}
        except:
            return {"online": False}

    @tool
    async def optimization_hints(self) -> dict:
        """Get platform-specific optimization hints."""
        try:
            import sys; sys.path.insert(0, '.')
            from src.platform_adapters import adapter
            return {
                "parallel": adapter.should_parallelize(),
                "gpu": adapter.should_use_gpu(),
                "cache": adapter.should_cache(),
                "compress": adapter.should_compress(),
                "prefetch": adapter.should_prefetch(),
                "lazy_import": adapter.should_lazy_import(),
                "mmap": adapter.should_use_mmap(),
            }
        except:
            return {"hints": "default"}
