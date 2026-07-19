"""minxg.contracts.runtime._exec — shared polyglot execution utilities.

Every non-Python adapter calls into this tiny module for:

  * ``which(cmd)`` — locate an executable on PATH
  * ``run(cmd, input_text, timeout)`` — run a subprocess safely
  * ``sandbox_path(name, code)`` — write transient source files

Keeping the logic here avoids duplicating subprocess boilerplate across
seven language adapters and makes the adapters themselves easy to read.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def which(cmd: str) -> Optional[str]:
    """Return the absolute path of ``cmd`` on PATH, or ``None``."""
    return shutil.which(cmd)


def run(cmd: List[str], *, input_text: str = "", timeout: float = 15.0,
        cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Run ``cmd`` with STDIN=input_text and return a uniform envelope."""
    try:
        proc = subprocess.run(
            cmd,
            input=input_text.encode("utf-8") if input_text else None,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", errors="replace").strip(),
            "stderr": proc.stderr.decode("utf-8", errors="replace").strip(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": "timeout"}
    except Exception as exc:
        return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)}


def sandbox_path(name: str, code: str, suffix: str) -> Path:
    """Write ``code`` to a temp file with ``suffix`` and return its path."""
    tmp = Path(tempfile.gettempdir()) / f"minxg_{name}_{os.getpid()}{suffix}"
    tmp.write_text(code, encoding="utf-8")
    return tmp


def payload_code(payload: Dict[str, Any]) -> str:
    """Extract user code from a payload, with a tiny arithmetic default."""
    return str(payload.get("code", payload.get("script", "1 + 1")))


def asset_path(*parts: str) -> Path:
    """Return an absolute path inside ``minxg/contracts/runtime/assets``.

    Use this so every adapter ships real language-specific source files
    instead of embedding foreign code as Python strings.
    """
    here = Path(__file__).resolve().parent
    return here / "assets" / Path(*parts)
