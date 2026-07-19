"""
MINXG Worker Registry — Auto-discovery and registration of all workers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Optional, Type
import importlib
import inspect


class WorkerRegistry:
    """Central registry for all MINXG workers."""

    WORKERS: Dict[str, Dict[str, Any]] = {}
    _loaded = False

    @classmethod
    def register(cls, worker_id: str, worker_class: Type, category: str = "general") -> None:
        """Register a worker class."""
        cls.WORKERS[worker_id] = {
            "class": worker_class,
            "category": category,
            "version": getattr(worker_class, "version", "0.1.0"),
            "worker_id": worker_id,
        }

    @classmethod
    def get(cls, worker_id: str) -> Optional[Any]:
        """Get a worker instance by ID."""
        if worker_id not in cls.WORKERS:
            return None
        worker_info = cls.WORKERS[worker_id]
        worker_class = worker_info["class"]
        return worker_class()

    @classmethod
    def list_all(cls, category: Optional[str] = None) -> List[Dict[str, str]]:
        """List all registered workers."""
        result = []
        for wid, info in cls.WORKERS.items():
            if category and info.get("category") != category:
                continue
            result.append({
                "worker_id": wid,
                "category": info.get("category", "general"),
                "version": info.get("version", "0.1.0"),
            })
        return result

    @classmethod
    def load_from_directory(cls, directory: Path) -> int:
        """Auto-discover and load workers from a directory."""
        count = 0
        for py_file in directory.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                module_name = py_file.stem
                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find worker classes
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if hasattr(obj, "worker_id") and hasattr(obj, "execute"):
                            cls.register(obj.worker_id, obj)
                            count += 1
            except Exception:
                pass  # Skip files that can't be loaded

        cls._loaded = True
        return count

    @classmethod
    def execute(cls, worker_id: str, **kwargs) -> Dict[str, Any]:
        """Execute a worker by ID with given arguments."""
        worker = cls.get(worker_id)
        if worker is None:
            return {"error": f"Worker not found: {worker_id}"}
        if not hasattr(worker, "execute"):
            return {"error": f"Worker {worker_id} has no execute method"}
        return worker.execute(**kwargs)


# Auto-load workers from the workers directory
_WORKERS_DIR = Path(__file__).parent / "workers"
if _WORKERS_DIR.exists():
    WorkerRegistry.load_from_directory(_WORKERS_DIR)
