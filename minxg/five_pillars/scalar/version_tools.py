"""Version management tools."""
from minxg.base import BaseWorker, tool

class VersionWorker(BaseWorker):
    worker_id = "version_worker"
    version = "0.0.1"

    @tool
    async def version_compare(self, v1: str = "0.0.1", v2: str = "0.0.2") -> dict:
        """Compare two semantic versions. Returns -1/0/1."""
        from packaging.version import Version
        a, b = Version(v1), Version(v2)
        if a < b: return {"comparison": -1, "message": f"{v1} < {v2}"}
        elif a > b: return {"comparison": 1, "message": f"{v1} > {v2}"}
        return {"comparison": 0, "message": f"{v1} == {v2}"}

    @tool
    async def version_bump(self, version: str = "0.0.1", level: str = "patch") -> dict:
        """Bump a semantic version (major/minor/patch)."""
        parts = version.split("-")[0].split(".")
        if level == "major": parts[0] = str(int(parts[0]) + 1); parts[1] = "0"; parts[2] = "0"
        elif level == "minor": parts[1] = str(int(parts[1]) + 1); parts[2] = "0"
        else: parts[2] = str(int(parts[2]) + 1)
        return {"old": version, "new": ".".join(parts), "level": level}

    @tool
    async def minxg_version(self) -> dict:
        """Get MINXG version info."""
        try:
            import sys; sys.path.insert(0, '.')
            from src.core.config._version import version_string, __version__, __build__, __codename__
            return {"version": __version__, "build": __build__, "codename": __codename__, "full": version_string()}
        except:
            return {"version": "1.0.0", "build": "?", "codename": "DeepAdapter"}

    @tool
    async def python_version_check(self) -> dict:
        """Check Python version and features."""
        import sys, platform
        return {
            "version": sys.version,
            "implementation": platform.python_implementation(),
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
            "is_64bit": sys.maxsize > 2**32,
        }

    @tool
    async def pip_list_outdated(self) -> dict:
        """List outdated pip packages."""
        import subprocess
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
                              capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                import json
                return {"outdated": json.loads(r.stdout), "count": len(json.loads(r.stdout))}
        except:
            pass
        return {"outdated": [], "error": "pip check failed"}
