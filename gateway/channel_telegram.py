"""gateway/channel_telegram.py — Telegram Bot API channel adapter.

Implements :class:`gateway.channels.ChannelAdapter` against Telegram's
long-polling ``getUpdates``/``sendMessage`` REST endpoints
(https://core.telegram.org/bots/api). No public webhook or open port is
required — this fits the same local-first model as MINXG's other
channels: the gateway process reaches *out* to Telegram, nothing reaches
in.

Config (``config/gateway.yaml`` -> ``channels: [...]``)::

    channels:
      - name: telegram
        enabled: true
        adapter: telegram
        options:
          bot_token: "${TELEGRAM_BOT_TOKEN}"   # or set the env var directly
          allowed_chat_ids: [123456789]         # empty/omitted = allow all
          poll_timeout: 25                      # long-poll seconds

Honesty note: this was implemented against Telegram's publicly documented
Bot API and unit-tested with a mocked HTTP session (``tests/test_channel_telegram.py``).
It has not been exercised against a live bot token in this environment —
outbound network here is limited to a package/registry allowlist that does
not include ``api.telegram.org``. Smoke-test with a real token before
relying on it.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

from gateway.channels import ChannelAdapter, ChannelMessage

logger = logging.getLogger("gateway.channels.telegram")

API_ROOT = "https://api.telegram.org"


class TelegramChannel(ChannelAdapter):
    """Long-polls Telegram's ``getUpdates`` and replies via ``sendMessage``."""

    def __init__(
        self,
        name: str = "telegram",
        bot_token: str = "",
        allowed_chat_ids: Optional[List[int]] = None,
        poll_timeout: int = 25,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(name, enabled=True)
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.allowed_chat_ids = set(allowed_chat_ids or [])
        self.poll_timeout = poll_timeout
        self._offset = 0
        self._session = session
        self._owns_session = session is None

    @property
    def _base_url(self) -> str:
        return f"{API_ROOT}/bot{self.bot_token}"

    async def connect(self) -> None:
        if not self.bot_token:
            logger.warning(
                "TelegramChannel %r enabled but no bot_token configured — "
                "set TELEGRAM_BOT_TOKEN or channels[].options.bot_token; "
                "channel will stay idle.", self.name,
            )
            self._running = False
            return
        if self._session is None:
            self._session = aiohttp.ClientSession()
        self._running = True

    async def disconnect(self) -> None:
        await super().disconnect()
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def receive(self) -> Optional[ChannelMessage]:
        if not self._running or not self._session:
            return None
        try:
            resp = await self._session.get(
                f"{self._base_url}/getUpdates",
                params={
                    "offset": self._offset,
                    "timeout": self.poll_timeout,
                    "allowed_updates": '["message"]',
                },
                timeout=aiohttp.ClientTimeout(total=self.poll_timeout + 10),
            )
            data = await resp.json()
        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientError as exc:
            logger.warning("Telegram getUpdates failed: %s", exc)
            await asyncio.sleep(2.0)
            return None

        if not data.get("ok"):
            logger.warning("Telegram getUpdates error: %s", data.get("description"))
            await asyncio.sleep(2.0)
            return None

        for update in data.get("result", []):
            self._offset = max(self._offset, update.get("update_id", 0) + 1)
            msg = update.get("message")
            if not msg or "text" not in msg:
                continue
            chat_id = msg.get("chat", {}).get("id")
            if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
                logger.info("Telegram message from disallowed chat %s dropped", chat_id)
                continue
            sender = msg.get("from", {})
            return ChannelMessage(
                from_user=sender.get("username") or str(sender.get("id", "unknown")),
                content=msg["text"],
                channel=self.name,
                session_id=f"telegram_{chat_id}",
                metadata={"chat_id": chat_id, "message_id": msg.get("message_id")},
            )
        return None

    async def send(self, msg: ChannelMessage, content: str) -> None:
        if not self._session or not content:
            return
        chat_id = msg.metadata.get("chat_id")
        if chat_id is None:
            logger.warning("TelegramChannel.send: no chat_id in metadata, dropping reply")
            return
        try:
            resp = await self._session.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": chat_id, "text": content[:4096]},
            )
            data = await resp.json()
            if not data.get("ok"):
                logger.warning("Telegram sendMessage error: %s", data.get("description"))
        except aiohttp.ClientError as exc:
            logger.warning("Telegram sendMessage failed: %s", exc)


def build_from_options(name: str, options: Dict[str, Any]) -> TelegramChannel:
    """Factory used by :class:`gateway.channels.ChannelManager`."""
    return TelegramChannel(
        name=name,
        bot_token=str(options.get("bot_token", "") or ""),
        allowed_chat_ids=options.get("allowed_chat_ids") or [],
        poll_timeout=int(options.get("poll_timeout", 25)),
    )
