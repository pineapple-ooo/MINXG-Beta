"""
MINXG File Workers — Comprehensive file manipulation tools.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from minxg.core_ops.file_safety import is_blocked_path, check_readable_text_file


class FileReadWorker:
    """Read files with encoding detection."""
    worker_id = "file_read"
    version = "0.19.0"

    def execute(self, path: str, encoding: str = "auto", limit: int = 1000) -> Dict[str, Any]:
        p = Path(path)
        if is_blocked_path(path):
            return {"error": f"Cannot read blocked device path: {path}"}
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if not p.is_file():
            return {"error": f"Not a file: {path}"}
        ok, err = check_readable_text_file(p)
        if not ok:
            return {"error": err}

        if encoding == "auto":
            try:
                content = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = p.read_text(encoding="latin-1")
        else:
            content = p.read_text(encoding=encoding)

        lines = content.splitlines()
        return {
            "path": str(p),
            "size": p.stat().st_size,
            "lines": len(lines),
            "content": "\n".join(lines[:limit]),
            "truncated": len(lines) > limit,
        }


class FileWriteWorker:
    """Write content to files."""
    worker_id = "file_write"
    version = "0.19.0"

    def execute(self, path: str, content: str, append: bool = False, encoding: str = "utf-8") -> Dict[str, Any]:
        if is_blocked_path(path):
            return {"error": f"Cannot write to blocked device path: {path}"}
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding=encoding) as f:
            f.write(content)
        return {"path": str(p), "bytes": len(content.encode(encoding)), "appended": append}


class FileCopyWorker:
    """Copy files."""
    worker_id = "file_copy"
    version = "0.19.0"

    def execute(self, src: str, dst: str) -> Dict[str, Any]:
        if is_blocked_path(src) or is_blocked_path(dst):
            return {"error": "Cannot copy a blocked device path"}
        from shutil import copy2
        copy2(src, dst)
        return {"src": src, "dst": dst, "size": Path(dst).stat().st_size}


class FileMoveWorker:
    """Move/rename files."""
    worker_id = "file_move"
    version = "0.19.0"

    def execute(self, src: str, dst: str) -> Dict[str, Any]:
        if is_blocked_path(src) or is_blocked_path(dst):
            return {"error": "Cannot move a blocked device path"}
        from shutil import move
        move(src, dst)
        return {"src": src, "dst": dst}


class FileDeleteWorker:
    """Delete files."""
    worker_id = "file_delete"
    version = "0.19.0"

    def execute(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        if is_blocked_path(path):
            return {"error": f"Cannot delete blocked device path: {path}"}
        p = Path(path)
        if p.is_dir() and recursive:
            import shutil
            shutil.rmtree(p)
            return {"deleted": str(p), "type": "directory", "recursive": True}
        elif p.is_file():
            p.unlink()
            return {"deleted": str(p), "type": "file"}
        return {"error": f"Path not found or not a file: {path}"}


class FileSearchWorker:
    """Search files by pattern."""
    worker_id = "file_search"
    version = "0.19.0"

    def execute(self, directory: str, pattern: str = "*", recursive: bool = True, limit: int = 100) -> Dict[str, Any]:
        p = Path(directory)
        glob = p.rglob if recursive else p.glob
        matches = [str(m) for m in glob(pattern) if m.is_file()]
        return {"directory": str(p), "pattern": pattern, "matches": matches[:limit], "total": len(matches)}


class FileDiffWorker:
    """Compare two files."""
    worker_id = "file_diff"
    version = "0.19.0"

    def execute(self, file1: str, file2: str) -> Dict[str, Any]:
        import difflib
        with open(file1) as f1, open(file2) as f2:
            lines1, lines2 = f1.readlines(), f2.readlines()
        diff = list(difflib.unified_diff(lines1, lines2, fromfile=file1, tofile=file2, lineterm=""))
        return {"identical": len(diff) == 0, "diff_lines": len(diff), "diff": "".join(diff[:500])}


class FileHashWorker:
    """Compute file hashes."""
    worker_id = "file_hash"
    version = "0.19.0"

    def execute(self, path: str, algorithm: str = "sha256") -> Dict[str, Any]:
        import hashlib
        h = hashlib.new(algorithm)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return {"path": path, "algorithm": algorithm, "hash": h.hexdigest()}


class FileStatWorker:
    """Get file statistics."""
    worker_id = "file_stat"
    version = "0.19.0"

    def execute(self, path: str) -> Dict[str, Any]:
        import time
        p = Path(path)
        stat = p.stat()
        return {
            "path": str(p),
            "size": stat.st_size,
            "size_human": _human_size(stat.st_size),
            "created": time.ctime(stat.st_ctime),
            "modified": time.ctime(stat.st_mtime),
            "accessed": time.ctime(stat.st_atime),
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "is_symlink": p.is_symlink(),
        }


def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"
