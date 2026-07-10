"""Platform-aware tools — adapt behavior based on device capabilities.

v0.16.0: Only android + windows are supported platforms.
All tool availability goes through the canonical platform_registry.
"""
from minxg.base import BaseWorker, tool
from minxg.five_pillars.dispatch.platform_registry import (
    CURRENT_PLATFORM,
    SUPPORTED_PLATFORMS,
    is_android,
    is_windows,
    is_root_available,
    is_adb_available,
    get_available_tools,
    get_tool_count,
    get_system_capabilities,
    is_tool_available,
)


class PlatformWorker(BaseWorker):
    facade_alias = "platform_worker"
    worker_id = "platform_worker"
    version = "0.17.0"

    @tool
    async def platform_info(self) -> dict:
        """Get detailed platform information (OS, CPU, RAM, GPU, etc.)."""
        import platform, os
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "hostname": platform.node(),
            "supported_platforms": sorted(SUPPORTED_PLATFORMS),
        }
        if is_android():
            info["runtime"] = "Termux"
            info["root_available"] = is_root_available()
            info["adb_available"] = is_adb_available()
        elif is_windows():
            info["runtime"] = "Windows"
        else:
            info["runtime"] = "unsupported"
            info["warning"] = f"Platform '{CURRENT_PLATFORM}' is not officially supported. Only android and windows are supported as of v0.16.0."
        return info

    @tool
    async def platform_capabilities(self) -> dict:
        """Get what this device can and cannot do."""
        return get_system_capabilities()

    @tool
    async def tool_availability(self, tool_name: str = "") -> dict:
        """Check if a tool is available on this platform. Empty = list all."""
        if tool_name:
            available = is_tool_available(tool_name)
            return {
                "tool": tool_name,
                "available": available,
                "platform": CURRENT_PLATFORM,
            }
        return {
            "available_count": get_tool_count(),
            "total": len(get_available_tools()),
            "platform": CURRENT_PLATFORM,
        }

    @tool
    async def device_class(self) -> dict:
        """Get device classification based on current platform capabilities."""
        import os
        cpu = os.cpu_count() or 1
        try:
            import subprocess
            mem_out = subprocess.run(["cat", "/proc/meminfo"], capture_output=True, text=True, timeout=2)
            mem_line = [l for l in mem_out.stdout.splitlines() if l.startswith("MemTotal")]
            mem_kb = int(mem_line[0].split()[1]) if mem_line else 0
            mem_gb = mem_kb / 1048576.0
        except Exception:
            mem_gb = 0

        if is_android():
            if cpu >= 8 and mem_gb >= 6:
                cls = "high"
            elif cpu >= 4 and mem_gb >= 3:
                cls = "mid"
            elif cpu >= 2 and mem_gb >= 1:
                cls = "low"
            else:
                cls = "minimal"
        elif is_windows():
            if cpu >= 8 and mem_gb >= 16:
                cls = "high"
            elif cpu >= 4 and mem_gb >= 8:
                cls = "mid"
            elif cpu >= 2:
                cls = "low"
            else:
                cls = "minimal"
        else:
            cls = "unknown"

        return {
            "device_class": cls,
            "cpu_count": cpu,
            "memory_gb": round(mem_gb, 1),
            "platform": CURRENT_PLATFORM,
        }
