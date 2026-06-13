"""
multiligua_cli/file_selector.py — Interactive terminal file selector v1.0.0

Provides directory browsing and multi-file selection via interactive terminal UI.
Non-interactive fallback supports glob patterns for scripting.
"""
from __future__ import annotations
import os
import sys
import glob
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _is_interactive() -> bool:
    """Check if we're in an interactive terminal session."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _get_file_info(path: str) -> Dict[str, Any]:
    """Get file metadata for display."""
    stat = os.stat(path)
    size = stat.st_size
    if size < 1024:
        size_str = f"{size}B"
    elif size < 1024 * 1024:
        size_str = f"{size/1024:.1f}KB"
    elif size < 1024 * 1024 * 1024:
        size_str = f"{size/(1024*1024):.1f}MB"
    else:
        size_str = f"{size/(1024*1024*1024):.1f}GB"

    import datetime
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    return {
        "name": os.path.basename(path),
        "path": path,
        "size": size,
        "size_str": size_str,
        "is_dir": os.path.isdir(path),
        "mtime": mtime,
        "permissions": oct(stat.st_mode)[-3:],
    }


def select_files_glob(patterns: List[str]) -> List[str]:
    """Non-interactive file selection via glob patterns."""
    results = []
    for pattern in patterns:
        expanded = os.path.expanduser(pattern)
        matches = glob.glob(expanded, recursive=True)
        results.extend(matches)
    return sorted(set(results))


def select_directory(start_path: str = ".") -> Optional[str]:
    """Simple interactive directory browser for choosing a directory."""
    current = os.path.abspath(os.path.expanduser(start_path))
    print(f"\n  Current directory: {current}")
    print(f"  Press Enter to select this directory, or type a new path.\n")

    try:
        user_input = input("  Directory path (Enter to confirm current): ").strip()
        if user_input:
            new_path = os.path.abspath(os.path.expanduser(user_input))
            if os.path.isdir(new_path):
                return new_path
            else:
                print(f"  Not a directory: {new_path}")
                return None
        return current
    except (EOFError, KeyboardInterrupt):
        return None


def select_files_in_directory(directory: str, pattern: str = "*",
                              allow_multiple: bool = True) -> List[str]:
    """
    Select files from a directory. Interactive mode: type selection numbers.
    Non-interactive mode: glob-based selection.

    Args:
        directory: Target directory
        pattern: File pattern (glob, e.g., '*.py', '*.log')
        allow_multiple: Whether to allow selecting multiple files

    Returns:
        List of selected absolute file paths
    """
    directory = os.path.abspath(os.path.expanduser(directory))
    if not os.path.isdir(directory):
        print(f"Error: Not a directory: {directory}")
        return []

    # Get all matching files
    all_files = []
    for f in os.listdir(directory):
        fp = os.path.join(directory, f)
        if pattern == "*" or fnmatch.fnmatch(f, pattern):
            all_files.append(fp)

    all_files.sort(key=lambda x: (not os.path.isdir(x), os.path.basename(x).lower()))

    if not all_files:
        print(f"No files matching '{pattern}' in {directory}")
        return []

    # Display files with info
    print(f"\n  Directory: {directory}")
    print(f"  Pattern: {pattern}")
    print(f"  Files found: {len(all_files)}")
    print(f"  {'#' :>4} {'Type':6} {'Size':>10} {'Modified':17} Name")
    print(f"  {'─'*4} {'─'*6} {'─'*10} {'─'*17} {'─'*40}")

    for i, fp in enumerate(all_files):
        info = _get_file_info(fp)
        ftype = "DIR" if info["is_dir"] else "FILE"
        print(f"  {i+1:>4} {ftype:6} {info['size_str']:>10} {info['mtime']:17} {info['name'][:40]}")

    if not _is_interactive():
        # Non-interactive: return all files
        return [f for f in all_files if not os.path.isdir(f)]

    # Interactive selection
    print(f"\n  Select files (enter numbers, separated by spaces/comma)")
    if allow_multiple:
        print(f"  Examples: '1 3 5', '1-10', 'all', '*.py'")
    else:
        print(f"  Enter a single number")

    try:
        user_input = input("  Selection: ").strip().lower()

        if user_input in ("", "q", "quit"):
            return []

        if user_input == "all":
            return [f for f in all_files if not os.path.isdir(f)]

        if user_input == "dirs":
            return [f for f in all_files if os.path.isdir(f)]

        if user_input.startswith("*"):
            return [f for f in all_files
                    if not os.path.isdir(f) and fnmatch.fnmatch(os.path.basename(f), user_input)]

        # Parse number ranges
        selected = set()
        parts = user_input.replace(",", " ").split()
        for part in parts:
            if "-" in part and part[0] != "-":
                try:
                    low, high = part.split("-", 1)
                    for n in range(int(low), int(high) + 1):
                        if 1 <= n <= len(all_files):
                            selected.add(n - 1)
                except ValueError:
                    pass
            else:
                try:
                    n = int(part)
                    if 1 <= n <= len(all_files):
                        selected.add(n - 1)
                except ValueError:
                    pass

        selected_files = [all_files[i] for i in sorted(selected)]

        if not selected_files:
            print("  No files selected.")
            return []

        print(f"\n  Selected {len(selected_files)} file(s):")
        for sf in selected_files[:10]:
            print(f"    {sf}")
        if len(selected_files) > 10:
            print(f"    ... and {len(selected_files) - 10} more")

        return selected_files

    except (EOFError, KeyboardInterrupt):
        return []


def file_selector_wizard(start_dir: str = ".", file_pattern: str = "*",
                         max_files: int = 0) -> Dict[str, Any]:
    """
    High-level file selection wizard.

    1. Let user pick a directory
    2. Let user pick files within that directory
    3. Return structured result

    Args:
        start_dir: Initial directory to browse
        file_pattern: Glob pattern to filter files
        max_files: Max files to select (0 = unlimited)

    Returns:
        Dict with selected files and metadata
    """
    # Step 1: Select directory
    directory = select_directory(start_dir)
    if not directory:
        return {"status": "cancelled", "reason": "No directory selected"}

    # Step 2: Select files
    files = select_files_in_directory(directory, file_pattern)

    if max_files and len(files) > max_files:
        files = files[:max_files]

    return {
        "status": "success",
        "directory": directory,
        "pattern": file_pattern,
        "files": files,
        "count": len(files),
        "file_info": [_get_file_info(f) for f in files[:20]] if files else [],
    }


# ── Backward-compatible simple API ──

def select_files(path: str = ".", glob_pattern: str = "*",
                 multiple: bool = True) -> List[str]:
    """
    Simple file selection. Auto-detects interactive vs non-interactive mode.

    - Interactive terminal: shows numbered list, user picks by number
    - Non-interactive (script/pipe): returns all files matching glob
    """
    path_expanded = os.path.expanduser(path)

    if os.path.isfile(path_expanded):
        return [path_expanded]

    if os.path.isdir(path_expanded):
        return select_files_in_directory(path_expanded, glob_pattern, multiple)

    # Treat as glob pattern
    return select_files_glob([path_expanded, glob_pattern.replace(".", path_expanded)])