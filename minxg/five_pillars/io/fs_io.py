"""
file_info, list_directory, tree_directory, make_directory, delete_file, move_file
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List
from minxg.base import BaseWorker, tool


class FsIoWorker(BaseWorker):
    facade_alias = "fs_io"
    worker_id = "fs_io"
    tier = "user"  # v0.18.0 three-tier classification
    version = "0.17.1"

    @tool(description="Read file content (optional line count/offset)", category="read")
    async def read_file(self, path: str, lines: int = 0, start: int = 0) -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"file not found: {path}"}
        if p.is_dir():
            return {"error": f"is a directory: {path}"}
        try:
            if lines == 0:
                content = p.read_text(encoding="utf-8", errors="replace")
            else:
                with p.open(encoding="utf-8", errors="replace") as f:
                    for _ in range(start):
                        f.readline()
                    content = "".join([f.readline() for _ in range(lines)])
            return {"path": str(p), "content": content, "size": p.stat().st_size}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Write file (append=true to append)", category="write")
    async def write_file(self, path: str, content: str, append: bool = False) -> Dict:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with p.open(mode, encoding="utf-8") as f:
            n = f.write(content)
        return {"path": str(p), "bytes_written": n}

    @tool(description="Read last N lines of file", category="read")
    async def tail_file(self, path: str, lines: int = 20) -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"file not found: {path}"}
        try:
            with p.open("rb") as f:
                data = f.read().decode("utf-8", errors="replace")
            all_lines = data.splitlines()
            tail = all_lines[-lines:] if lines > 0 else all_lines
            return {"path": str(p), "content": "\n".join(tail), "total_lines": len(all_lines)}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Read first N lines of file", category="read")
    async def head_file(self, path: str, lines: int = 20) -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"file not found: {path}"}
        try:
            with p.open(encoding="utf-8", errors="replace") as f:
                content = "".join([f.readline() for _ in range(lines)])
            return {"path": str(p), "content": content}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Get file/directory metadata", category="info")
    async def file_info(self, path: str) -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"not found: {path}"}
        st = p.stat()
        return {
            "path": str(p), "exists": True, "is_file": p.is_file(), "is_dir": p.is_dir(),
            "size": st.st_size, "mode": oct(st.st_mode), "uid": st.st_uid, "gid": st.st_gid,
            "mtime": st.st_mtime, "ctime": st.st_ctime, "atime": st.st_atime,
        }

    @tool(description="List directory contents", category="list")
    async def list_directory(self, path: str = ".", long_format: bool = False,
                            show_hidden: bool = False, ignore: list = None) -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"path not found: {path}"}
        if not p.is_dir():
            return {"error": f"not a directory: {path}"}
        default_ignore = ['__pycache__', '.git', 'node_modules',
                          '.venv', 'venv', '.mypy_cache', '.pytest_cache', '.tox']
        ignore_set = set(ignore or default_ignore)
        try:
            entries = []
            for entry in sorted(p.iterdir()):
                if not show_hidden and entry.name.startswith('.'):
                    continue
                if entry.name in ignore_set:
                    continue
                try:
                    stat = entry.stat()
                    if long_format:
                        entries.append({
                            "name": entry.name, "type": "dir" if entry.is_dir() else "file",
                            "size": stat.st_size if entry.is_file() else 0,
                            "modified": stat.st_mtime, "mode": oct(stat.st_mode)[-3:],
                        })
                    else:
                        entries.append(entry.name + ("/" if entry.is_dir() else ""))
                except (PermissionError, OSError) as e:
                    entries.append({"name": entry.name, "error": str(e)})
            return {"path": str(p), "count": len(entries), "entries": entries,
                    "ignored": list(ignore_set) if ignore_set else []}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Recursively display directory tree", category="list")
    async def tree_directory(self, path: str = ".", max_depth: int = 3) -> Dict:
        p = Path(path).expanduser()
        if not p.is_dir():
            return {"error": f"not a directory: {path}"}
        lines = []
        def _walk(d: Path, prefix: str, depth: int):
            if depth > max_depth:
                return
            entries = sorted(d.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            for i, e in enumerate(entries):
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{e.name}{'/' if e.is_dir() else ''}")
                if e.is_dir():
                    extension = "    " if is_last else "│   "
                    _walk(e, prefix + extension, depth + 1)
        _walk(p, "", 0)
        return {"path": str(p), "tree": "\n".join(lines), "max_depth": max_depth}

    @tool(description="Create directory (supports nested)", category="write")
    async def make_directory(self, path: str, mode: int = 0o755) -> Dict:
        p = Path(path).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True, mode=mode)
            return {"path": str(p), "created": True}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Delete file or empty directory", category="write")
    async def delete_file(self, path: str) -> Dict:
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"not found: {path}"}
        try:
            if p.is_dir():
                p.rmdir()
            else:
                p.unlink()
            return {"path": str(p), "deleted": True}
        except Exception as e:
            return {"error": str(e)}

    @tool(description="Move/rename", category="write")
    async def move_file(self, source: str, dest: str) -> Dict:
        try:
            import shutil
            shutil.move(source, dest)
            return {"source": source, "dest": dest, "moved": True}
        except Exception as e:
            return {"error": str(e)}


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"
