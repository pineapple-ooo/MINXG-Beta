"""


  from multiligua_cli.logger import get_logger

  log = get_logger()
  log.tool("read_file", {"path": "/tmp/x"}, {"content": "..."}, 123)

"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


LOG_DIR = Path.home() / ".minxg" / "logs"
DEFAULT_ENABLED = True


def _today_log_path() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"chat_{date_str}.jsonl"




class ChatLogger:

    def __init__(self):
        self._session_id: Optional[str] = None
        self._enabled = DEFAULT_ENABLED
        self._buffer: list[dict] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        self._enabled = val
        if val:
            pass
        else:
            pass
    def session_start(self, session_id: str = ""):
        import uuid
        self._session_id = session_id or uuid.uuid4().hex[:12]
        self._buffer.clear()
        self._write({
            "type": "system",
            "action": "session_start",
            "session_id": self._session_id,
            "time": time.time(),
        })

    def session_end(self):
        self._write({
            "type": "system",
            "action": "session_end",
            "session_id": self._session_id,
            "time": time.time(),
        })

    def user(self, message: str):
        self._write({
            "type": "user",
            "message": message,
            "session_id": self._session_id,
            "time": time.time(),
        })

    def model(self, message: str, thinking: str = "", tool_cards: list = None):
        """
        Args:
            pass
        """
        entry = {
            "type": "model",
            "message": message,
            "session_id": self._session_id,
            "time": time.time(),
        }
        if thinking:
            entry["thinking"] = thinking
        if tool_cards:
            entry["tool_cards"] = tool_cards
        self._write(entry)

    def tool(self, name: str, args: dict, result: any = None, elapsed_ms: int = 0):
        self._write({
            "type": "tool",
            "name": name,
            "args": args,
            "result": _safe_serialize(result),
            "elapsed_ms": elapsed_ms,
            "session_id": self._session_id,
            "time": time.time(),
        })

    def system(self, message: str):
        self._write({
            "type": "system",
            "message": message,
            "session_id": self._session_id,
            "time": time.time(),
        })

    def error(self, message: str, details: str = ""):
        entry = {
            "type": "error",
            "message": message,
            "session_id": self._session_id,
            "time": time.time(),
        }
        if details:
            entry["details"] = details
        self._write(entry)

    def recent_logs(self, n: int = 20) -> list[dict]:
        return self._buffer[-n:]

    def _write(self, entry: dict):
        if not self._enabled:
            return

        self._buffer.append(entry)
        if len(self._buffer) > 500:
            self._buffer = self._buffer[-200:]

        try:
            line = json.dumps(entry, ensure_ascii=False, default=str)
            with open(_today_log_path(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
def _safe_serialize(obj, max_len: int = 500) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
        if len(s) > max_len:
            s = s[:max_len] + "...(truncated)"
        return s
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"



_logger: Optional[ChatLogger] = None


def get_logger() -> ChatLogger:
    global _logger
    if _logger is None:
        _logger = ChatLogger()
    return _logger


def is_logging_enabled() -> bool:
    return get_logger().enabled
