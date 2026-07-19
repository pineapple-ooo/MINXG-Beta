"""gateway/channels.py — Multi-channel gateway manager.

Inspired by the channel/adapter pattern shown in
``/storage/emulated/0/文件/mmm/gateway/channel.py`` and
``/storage/emulated/0/文件/mmm/gateway/manager.py``, but reimplemented
natively for MINXG's aiohttp-based OpenHTTP gateway.

A *channel* is one inbound surface the gateway listens to. Two adapters
live in this file for tests / internal use: ``memory`` (in-process FIFO)
and ``http`` (webhook-style inbound POSTs). Three more live in their own
modules and are imported lazily by :class:`ChannelManager` so that
importing this file never requires the extra protocol code to be
present:

  - ``telegram`` -> :mod:`gateway.channel_telegram` (long-polling Bot API)
  - ``discord``  -> :mod:`gateway.channel_discord`  (Gateway websocket)
  - ``slack``    -> :mod:`gateway.channel_slack`    (Socket Mode)

See ``config/gateway.yaml`` for how to enable one, and each module's
docstring for exactly what was/wasn't live-tested against the real
platform.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from aiohttp import web

logger = logging.getLogger("gateway.channels")


@dataclass
class ChannelMessage:
    """Normalised message envelope carried between adapters and the gateway."""
    from_user: str
    content: str
    channel: str = "memory"
    msg_type: str = "text"
    session_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChannelAdapter(ABC):
    """Base class every inbound channel must implement."""

    def __init__(self, name: str, enabled: bool = False):
        self.name = name
        self.enabled = enabled
        self._running = False

    @abstractmethod
    async def connect(self) -> None:
        """Start any listener / consumer state."""

    @abstractmethod
    async def receive(self) -> Optional[ChannelMessage]:
        """Return one message, or ``None`` when the channel is idle."""

    @abstractmethod
    async def send(self, msg: ChannelMessage, content: str) -> None:
        """Deliver a reply back to the channel."""

    async def disconnect(self) -> None:
        """Release resources."""
        self._running = False


class MemoryChannel(ChannelAdapter):
    """In-memory FIFO channel for tests and intra-process messaging."""

    def __init__(self, name: str = "memory"):
        super().__init__(name, enabled=True)
        self._queue: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._replies: Dict[str, asyncio.Queue[str]] = {}

    async def connect(self) -> None:
        self._running = True

    def post(self, content: str, from_user: str = "user",
             session_id: str = "") -> str:
        """Thread-safe helper for producers to inject a message."""
        sid = session_id or f"mem_{uuid.uuid4().hex[:8]}"
        self._queue.put_nowait(ChannelMessage(
            from_user=from_user, content=content, channel=self.name,
            session_id=sid,
        ))
        self._replies[sid] = asyncio.Queue()
        return sid

    async def receive(self) -> Optional[ChannelMessage]:
        if not self._running:
            return None
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    async def send(self, msg: ChannelMessage, content: str) -> None:
        q = self._replies.get(msg.session_id)
        if q:
            await q.put(content)
        else:
            logger.debug("MemoryChannel reply for %s dropped", msg.session_id)

    async def get_reply(self, session_id: str, timeout: float = 30.0) -> Optional[str]:
        q = self._replies.get(session_id)
        if not q:
            return None
        try:
            return await asyncio.wait_for(q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._replies.pop(session_id, None)


class HTTPChannel(ChannelAdapter):
    """Webhook-style inbound channel mounted as an aiohttp sub-app."""

    def __init__(self, name: str = "http", path: str = "/channel/inbox"):
        super().__init__(name, enabled=True)
        self.path = path
        self._inbox: asyncio.Queue[ChannelMessage] = asyncio.Queue()
        self._pending: Dict[str, asyncio.Queue[str]] = {}

    async def connect(self) -> None:
        self._running = True

    async def receive(self) -> Optional[ChannelMessage]:
        if not self._running:
            return None
        try:
            return await asyncio.wait_for(self._inbox.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    async def send(self, msg: ChannelMessage, content: str) -> None:
        q = self._pending.get(msg.session_id)
        if q:
            await q.put(content)

    def add_routes(self, app: web.Application) -> None:
        async def inbox(req: web.Request) -> web.Response:
            try:
                body = await req.json()
            except json.JSONDecodeError:
                return web.json_response({"error": "invalid JSON"}, status=400)
            sid = body.get("session_id") or f"http_{uuid.uuid4().hex[:8]}"
            msg = ChannelMessage(
                from_user=body.get("from_user", "user"),
                content=body.get("content", ""),
                channel=self.name,
                session_id=sid,
                metadata=body.get("metadata", {}),
            )
            self._pending[sid] = asyncio.Queue()
            await self._inbox.put(msg)
            try:
                reply = await asyncio.wait_for(self._pending[sid].get(), timeout=60.0)
            except asyncio.TimeoutError:
                reply = ""
            finally:
                self._pending.pop(sid, None)
            return web.json_response({"session_id": sid, "reply": reply})

        app.router.add_post(self.path, inbox)


class ChannelManager:
    """Owns all configured inbound channels and wires them to the gateway."""

    def __init__(self, config_channels: List[Any],
                 message_handler: Callable[[ChannelMessage], Any]):
        self.channels: List[ChannelAdapter] = []
        self._handler = message_handler
        self._tasks: List[asyncio.Task] = []

        for cfg in config_channels:
            if not cfg.enabled:
                continue
            name = cfg.name
            adapter_id = cfg.adapter
            options = dict(cfg.options or {})
            if adapter_id == "memory":
                self.channels.append(MemoryChannel(name))
            elif adapter_id == "http":
                self.channels.append(HTTPChannel(
                    name, path=options.get("path", "/channel/inbox")))
            elif adapter_id == "telegram":
                from gateway.channel_telegram import build_from_options as _build_tg
                self.channels.append(_build_tg(name, options))
            elif adapter_id == "discord":
                from gateway.channel_discord import build_from_options as _build_dc
                self.channels.append(_build_dc(name, options))
            elif adapter_id == "slack":
                from gateway.channel_slack import build_from_options as _build_sl
                self.channels.append(_build_sl(name, options))
            else:
                # Unknown adapters are skipped rather than crash startup.
                logger.warning("Unknown channel adapter %r for %r; skipping",
                               adapter_id, name)

    def add_routes(self, app: web.Application) -> None:
        for ch in self.channels:
            if isinstance(ch, HTTPChannel):
                ch.add_routes(app)

    async def start(self) -> None:
        for ch in self.channels:
            await ch.connect()
            self._tasks.append(asyncio.create_task(self._run_channel(ch)))
        if self.channels:
            logger.info("ChannelManager started %d channel(s)", len(self.channels))

    async def _run_channel(self, ch: ChannelAdapter) -> None:
        try:
            while ch._running:
                msg = await ch.receive()
                if msg is None:
                    continue
                try:
                    reply = await self._handler(msg)
                    await ch.send(msg, reply or "")
                except Exception as exc:
                    logger.exception("Channel %s handler failed", ch.name)
                    await ch.send(msg, f"[error: {exc}]")
        except Exception as exc:
            logger.exception("Channel %s crashed", ch.name)

    async def stop(self) -> None:
        for ch in self.channels:
            await ch.disconnect()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
