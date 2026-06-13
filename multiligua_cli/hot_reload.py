"""


  hot_reload:


CLI:
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple


MINXG_HOME = Path.home() / ".minxg"
UPDATE_READY = MINXG_HOME / "update_ready"
UPDATE_DONE = MINXG_HOME / "update_done"
UPDATE_LOCK = MINXG_HOME / "update_lock"
UPDATE_HISTORY = MINXG_HOME / "update_history.jsonl"
LOCK_TIMEOUT = 300

DEFAULT_REPO = "https://github.com/example/minxg.git"
DEFAULT_BRANCH = "main"


def _ensure_dirs():
    MINXG_HOME.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

def load_hotreload_config() -> dict:
    try:
        from multiligua_cli.utils import load_config
        cfg = load_config()
        return cfg.get("hot_reload", {})
    except Exception:
        return {}

def save_hotreload_config(updates: dict):
    try:
        from multiligua_cli.utils import load_config, get_project_root
        import yaml
        cfg = load_config()
        cfg.setdefault("hot_reload", {}).update(updates)
        config_path = get_project_root() / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        import logging

def is_enabled() -> bool:
    cfg = load_hotreload_config()
    return cfg.get("enabled", False)

def set_enabled(val: bool):
    save_hotreload_config({"enabled": val})

def get_repo_url() -> str:
    return load_hotreload_config().get("repo_url", DEFAULT_REPO)

def get_branch() -> str:
    return load_hotreload_config().get("branch", DEFAULT_BRANCH)


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_remote_tags(repo_url: str) -> List[Tuple[str, str]]:

    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "--sort=-version:refname", repo_url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []

        tags = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                hsh = parts[0]
                ref = parts[1]
                # refs/tags/v1.0.0 -> v1.0.0
                tag = ref.replace("refs/tags/", "")
                if "^{}" in tag:
                    continue
                tags.append((tag, hsh))
        return tags
    except Exception:
        return []


def _get_local_version() -> str:
    try:
        from multiligua_cli.utils import get_project_root
        root = get_project_root()
        toml_path = root / "pyproject.toml"
        if toml_path.exists():
            content = toml_path.read_text(encoding="utf-8")
            m = re.search(r'version[ \t]*=[ \t]*"([^"]+)"', content)
            if m:
                return m.group(1)
    except Exception:
        pass

    try:
        from multiligua_cli.utils import get_project_root
        root = get_project_root()
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=root, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().lstrip("v")
    except Exception:
        pass

    return "0.0.0"


def _parse_version(v: str) -> Tuple[int, ...]:
    v = v.strip().lstrip("v")
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except Exception:
        return (0, 0, 0)


def check_version_higher_than_local(repo_url: str = None) -> Optional[dict]:

    Returns:
    """
    if repo_url is None:
        repo_url = get_repo_url()

    local_ver = _get_local_version()
    local_tuple = _parse_version(local_ver)

    remote_tags = _fetch_remote_tags(repo_url)
    if not remote_tags:
        return None

    highest_tag, highest_hash = remote_tags[0]
    remote_tuple = _parse_version(highest_tag)

    if remote_tuple > local_tuple:
        return {
            "version": highest_tag.lstrip("v"),
            "tag": highest_tag,
            "commit": highest_hash[:8],
            "local_version": local_ver,
        }
    return None


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

def apply_update(force: bool = False) -> dict:
    """
    Returns:
      {success, message, old_version, new_version}
    """
    _ensure_dirs()

    if not is_enabled() and not force:
        pass
    repo_url = get_repo_url()
    branch = get_branch()

    info = check_version_higher_than_local(repo_url)
    if not info and not force:
        pass
    if not _acquire_lock():
        pass
    try:
        from multiligua_cli.utils import get_project_root
        root = get_project_root()

        old_ver = _get_local_version()

        if not (root / ".git").exists():
            pass
        # Step 1: fetch + prune
        result = subprocess.run(
            ["git", "fetch", "--prune", "origin", branch],
            cwd=root, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return {
                "success": False,
            }
            return {
                "success": False,
                "version": old_ver,
            }
        result = subprocess.run(
            ["git", "reset", "--hard", f"origin/{branch}"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {
                "success": False,
                "version": old_ver,
            }
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=root, capture_output=True, text=True, timeout=30,
        )

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
            cwd=root, capture_output=True, text=True, timeout=120,
        )

        new_ver = _get_local_version()

        result = {
            "success": True,
            "old_version": old_ver,
            "version": old_ver,
        }
    finally:
        _release_lock()

    _record_update(result)

    try:
        UPDATE_DONE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    try:
        UPDATE_READY.unlink()
    except OSError:
        pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

def _acquire_lock() -> bool:
    _ensure_dirs()
    if UPDATE_LOCK.exists():
        mtime = UPDATE_LOCK.stat().st_mtime
        if time.time() - mtime > LOCK_TIMEOUT:
            UPDATE_LOCK.unlink()
        else:
            return False
    UPDATE_LOCK.write_text(str(os.getpid()))
    return True

def _release_lock():
    try:
        UPDATE_LOCK.unlink()
    except OSError:
        pass

def _record_update(result: dict):
    _ensure_dirs()
    entry = {"timestamp": datetime.now().isoformat(), **result}
    try:
        with open(UPDATE_HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

class UpdateScheduler:

    def __init__(self):
        self._pending = False
        self._active = 0

    @property
    def active(self) -> bool:
        return self._active > 0

    def enter(self):
        self._active += 1

    def leave(self) -> bool:
        self._active = max(0, self._active - 1)
        if self._pending and self._active == 0:
            self._pending = False
            return True
        return False

    def defer(self):
        self._pending = True

    def has_pending(self) -> bool:
        return self._pending


_scheduler: Optional[UpdateScheduler] = None

def get_update_scheduler() -> UpdateScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = UpdateScheduler()
    return _scheduler


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════

def run_update_command(args) -> int:
    from multiligua_cli.utils import (
        HAS_RICH, console, print_info, print_success, print_error, print_warning,
    )

    if getattr(args, "disable", False):
        set_enabled(False)
        return 0

    if getattr(args, "enable", False):
        set_enabled(True)
        return 0

    if not is_enabled():
        return 0

    repo_url = get_repo_url()
    info = check_version_higher_than_local(repo_url)

    if info is None:
        return 0

    if HAS_RICH:
        from rich.panel import Panel
        from rich import box
        console.print(Panel.fit(
            border_style="yellow",
            box=box.ROUNDED,
        ))
    else:
        print()

    force = getattr(args, "force", False)
    result = apply_update(force=force)

    if result["success"]:
        print_success(result["message"])
        if "old_version" in result and result["version"] != result["old_version"]:
            pass
        else:
            print_error(result["message"])
            return 1
