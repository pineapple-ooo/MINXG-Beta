"""File Tools Module - LLM agent file manipulation tools."""

import errno
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

_DEFAULT_MAX_READ_CHARS = 100_000
_max_read_chars_cached: Optional[int] = None

_BLOCKED_DEVICE_PATHS = frozenset({
    "/dev/zero", "/dev/random", "/dev/urandom", "/dev/full",
    "/dev/stdin", "/dev/tty", "/dev/console",
    "/dev/stdout", "/dev/stderr",
    "/dev/fd/0", "/dev/fd/1", "/dev/fd/2",
})


def _get_max_read_chars() -> int:
    """Return the configured max characters per file read."""
    global _max_read_chars_cached
    if _max_read_chars_cached is not None:
        return _max_read_chars_cached
    
    config_path = Path(__file__).parent.parent / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            val = cfg.get("file_read_max_chars")
            if isinstance(val, (int, float)) and val > 0:
                _max_read_chars_cached = int(val)
                return _max_read_chars_cached
        except Exception:
            pass
    
    _max_read_chars_cached = _DEFAULT_MAX_READ_CHARS
    return _max_read_chars_cached


def _is_blocked_path(path: str) -> bool:
    """Check if path is a blocked device path."""
    resolved = Path(path).resolve()
    return str(resolved) in _BLOCKED_DEVICE_PATHS


def _is_binary_file(path: Path) -> bool:
    """Check if file appears to be binary."""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
        if b'\x00' in chunk:
            return True
        text_chars = bytes(range(32, 127)) + b'\n\r\t'
        non_text = sum(1 for b in chunk if b not in text_chars)
        return non_text / max(len(chunk), 1) > 0.3
    except Exception:
        return True


READ_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Absolute or relative file path"},
        "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)", "default": 1},
        "limit": {"type": "integer", "description": "Maximum number of lines to read", "default": 500},
    },
    "required": ["path"],
}

WRITE_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Absolute or relative file path"},
        "content": {"type": "string", "description": "Content to write"},
        "append": {"type": "boolean", "description": "Append to file instead of overwriting", "default": False},
    },
    "required": ["path", "content"],
}

PATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Absolute or relative file path"},
        "old_string": {"type": "string", "description": "String to find and replace"},
        "new_string": {"type": "string", "description": "Replacement string"},
        "replace_all": {"type": "boolean", "description": "Replace all occurrences", "default": False},
    },
    "required": ["path", "old_string", "new_string"],
}

SEARCH_FILES_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {"type": "string", "description": "Regex pattern to search for"},
        "path": {"type": "string", "description": "Directory to search in", "default": "."},
        "file_glob": {"type": "string", "description": "File pattern to match (e.g. *.py)"},
        "output_mode": {"type": "string", "description": "Output format: 'content', 'files_only', or 'count'", "default": "content"},
    },
    "required": ["pattern"],
}

LS_DIR_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Directory to list", "default": "."},
        "all": {"type": "boolean", "description": "Show hidden files", "default": False},
    },
}

FILE_INFO_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "File or directory path"},
    },
    "required": ["path"],
}


def _handle_read_file(args: dict) -> str:
    path = args.get("path", "")
    if not path:
        return json.dumps({"error": "path is required"})
    
    if _is_blocked_path(path):
        return json.dumps({"error": f"Cannot read blocked device path: {path}"})
    
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return json.dumps({"error": f"File not found: {path}"})
        
        if p.is_dir():
            return json.dumps({"error": f"Path is a directory, not a file: {path}"})
        
        if p.stat().st_size > 50 * 1024 * 1024:
            return json.dumps({"error": "File too large (>50MB)"})
        
        if _is_binary_file(p):
            return json.dumps({"error": f"Binary file, not readable as text: {path}"})
        
        offset = max(1, args.get("offset", 1))
        limit = args.get("limit", 500)
        
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        start = min(offset - 1, total_lines)
        end = min(start + limit, total_lines)
        
        content = ''.join(lines[start:end])
        max_chars = _get_max_read_chars()
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n... (truncated, {total_lines - end} more lines)"
        
        return json.dumps({
            "content": content,
            "total_lines": total_lines,
            "showing": f"lines {start + 1}-{end}",
            "path": str(p),
        })
    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"})
    except Exception as e:
        return json.dumps({"error": f"Read error: {e}"})


def _handle_write_file(args: dict) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    
    if not path:
        return json.dumps({"error": "path is required"})
    
    if _is_blocked_path(path):
        return json.dumps({"error": f"Cannot write to blocked device path: {path}"})
    
    try:
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if args.get("append") else "w"
        with open(p, mode, encoding='utf-8') as f:
            f.write(content)
        
        return json.dumps({
            "ok": True,
            "bytes_written": len(content),
            "path": str(p),
        })
    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"})
    except Exception as e:
        return json.dumps({"error": f"Write error: {e}"})


def _handle_patch(args: dict) -> str:
    path = args.get("path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = args.get("replace_all", False)
    
    if not path or not old_string:
        return json.dumps({"error": "path and old_string are required"})
    
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return json.dumps({"error": f"File not found: {path}"})
        
        content = p.read_text(encoding='utf-8', errors='replace')
        
        if old_string not in content:
            return json.dumps({"error": f"String not found in file: {old_string[:50]}..."})
        
        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1
        
        p.write_text(new_content, encoding='utf-8')
        
        return json.dumps({
            "ok": True,
            "replacements": count,
            "path": str(p),
        })
    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"})
    except Exception as e:
        return json.dumps({"error": f"Patch error: {e}"})


def _handle_search_files(args: dict) -> str:
    pattern = args.get("pattern", "")
    path = args.get("path", ".")
    file_glob = args.get("file_glob")
    output_mode = args.get("output_mode", "content")
    
    if not pattern:
        return json.dumps({"error": "pattern is required"})
    
    try:
        search_path = Path(path).expanduser().resolve()
        if not search_path.exists():
            return json.dumps({"error": f"Search path not found: {path}"})
        
        regex = re.compile(pattern)
        matches = []
        files_checked = 0
        
        for p in search_path.rglob(file_glob or "*"):
            if p.is_file() and not any(part.startswith('.') for part in p.parts):
                try:
                    files_checked += 1
                    if p.stat().st_size > 5_000_000:
                        continue
                    
                    content = p.read_text(encoding='utf-8', errors='replace')
                    for i, line in enumerate(content.splitlines(), 1):
                        if regex.search(line):
                            if output_mode == "files_only":
                                if p not in matches:
                                    matches.append(p)
                            elif output_mode == "count":
                                matches.append((str(p), i))
                            else:
                                matches.append(f"{p}:{i}:{line.rstrip()}")
                except (PermissionError, UnicodeDecodeError):
                    continue
        
        if output_mode == "files_only":
            return json.dumps({"files": [str(m) for m in matches], "files_checked": files_checked})
        elif output_mode == "count":
            return json.dumps({"matches": len(matches), "files_checked": files_checked})
        else:
            return json.dumps({"matches": matches[:1000], "total": len(matches), "files_checked": files_checked})
    except Exception as e:
        return json.dumps({"error": f"Search error: {e}"})


def _handle_ls_dir(args: dict) -> str:
    path = args.get("path", ".")
    show_all = args.get("all", False)
    
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        
        if not p.is_dir():
            return json.dumps({"error": f"Path is not a directory: {path}"})
        
        entries = []
        for item in p.iterdir():
            if not show_all and item.name.startswith('.'):
                continue
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
            })
        
        entries.sort(key=lambda x: (x["type"] == "file", x["name"]))
        return json.dumps({"entries": entries, "path": str(p)})
    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"})
    except Exception as e:
        return json.dumps({"error": f"ls error: {e}"})


def _handle_file_info(args: dict) -> str:
    path = args.get("path", "")
    
    if not path:
        return json.dumps({"error": "path is required"})
    
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return json.dumps({"error": f"Path not found: {path}"})
        
        stat = p.stat()
        return json.dumps({
            "path": str(p),
            "name": p.name,
            "type": "dir" if p.is_dir() else "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "permissions": oct(stat.st_mode)[-3:],
            "is_readable": os.access(p, os.R_OK),
            "is_writable": os.access(p, os.W_OK),
            "is_executable": os.access(p, os.X_OK),
        })
    except Exception as e:
        return json.dumps({"error": f"file_info error: {e}"})


def _check_file_reqs() -> bool:
    """Check if file operations are available."""
    return True


from tools.registry import registry

registry.register(
    name="read_file",
    toolset="file",
    schema=READ_FILE_SCHEMA,
    handler=_handle_read_file,
    check_fn=_check_file_reqs,
    emoji="",
    max_result_size_chars=100_000,
)

registry.register(
    name="write_file",
    toolset="file",
    schema=WRITE_FILE_SCHEMA,
    handler=_handle_write_file,
    check_fn=_check_file_reqs,
    emoji="✍️",
    max_result_size_chars=100_000,
)

registry.register(
    name="patch",
    toolset="file",
    schema=PATCH_SCHEMA,
    handler=_handle_patch,
    check_fn=_check_file_reqs,
    emoji="",
    max_result_size_chars=100_000,
)

registry.register(
    name="search_files",
    toolset="file",
    schema=SEARCH_FILES_SCHEMA,
    handler=_handle_search_files,
    check_fn=_check_file_reqs,
    emoji="🔎",
    max_result_size_chars=100_000,
)

registry.register(
    name="ls_dir",
    toolset="file",
    schema=LS_DIR_SCHEMA,
    handler=_handle_ls_dir,
    check_fn=_check_file_reqs,
    emoji="📁",
    max_result_size_chars=50_000,
)

registry.register(
    name="file_info",
    toolset="file",
    schema=FILE_INFO_SCHEMA,
    handler=_handle_file_info,
    check_fn=_check_file_reqs,
    emoji="ℹ️",
    max_result_size_chars=10_000,
)
