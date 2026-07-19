"""gateway/channel_discord.py — Discord bot channel adapter.

Implements :class:`gateway.channels.ChannelAdapter` against Discord's
Gateway websocket (receiving) and REST API (sending) —
https://discord.com/developers/docs/topics/gateway.

Only what's needed to receive plain text messages and reply is
implemented: Identify / Hello / Heartbeat / Dispatch(MESSAGE_CREATE).
On disconnect it reconnects with a fresh Identify rather than
implementing session Resume (opcode 6) — simpler, at the cost of
possibly missing messages sent during the reconnect window. That's a
deliberate scope cut, not an oversight.

Config::

    channels:
      - name: discord
        enabled: true
        adapter: discord
        options:
          bot_token: "${DISCORD_BOT_TOKEN}"
          allowed_channel_ids: [123456789012345]   # empty = allow all

Requires the "Message Content" privileged intent to be enabled for the
bot in the Discord Developer Portal, or ``message.content`` will always
be empty.

Honesty note: implemented from Discord's public Gateway v10 docs and
unit-tested with a mocked websocket (``tests/test_channel_discord.py``).
Not exercised against Discord's live servers in this environment — the
sandbox's outbound allowlist does not include ``discord.com`` /
``gateway.discord.gg``. Smoke-test with a real bot token before relying
on it in production.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

from gateway.channels import ChannelAdapter, ChannelMessage

logger = logging.getLogger("gateway.channels.discord")

API_ROOT = "https://discord.com/api/v10"

# GUILDS(1<<0) | GUILD_MESSAGES(1<<9) | MESSAGE_CONTENT(1<<15)
DEFAULT_INTENTS = (1 << 0) | (1 << 9) | (1 << 15)

OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11


class DiscordChannel(ChannelAdapter):
    """Reads MESSAGE_CREATE events off the Discord Gateway; replies via REST."""

    def __init__(
        self,
        name: str = "discord",
        bot_token: str = "",
        allowed_channel_ids: Optional[List[int]] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(name, enabled=True)
        self.bot_token = bot_token or os.getenv("DISCORD_BOT_TOKEN", "")
        self.allowed_channel_ids = set(allowed_channel_ids or [])
        self._session = session
        self._owns_session = session is None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._seq: Optional[int] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._inbox: "asyncio.Queue[ChannelMessage]" = asyncio.Queue()
        self._reader_task: Optional[asyncio.Task] = None
        self._own_user_id: Optional[str] = None

    @property
    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bot {self.bot_token}"}

    async def connect(self) -> None:
        if not self.bot_token:
            logger.warning(
                "DiscordChannel %r enabled but no bot_token configured — "
                "set DISCORD_BOT_TOKEN or channels[].options.bot_token; "
                "channel will stay idle.", self.name,
            )
            self._running = False
            return
        if self._session is None:
            self._session = aiohttp.ClientSession()
        self._running = True
        self._reader_task = asyncio.create_task(self._run_forever())

    async def disconnect(self) -> None:
        await super().disconnect()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._reader_task:
            self._reader_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _run_forever(self) -> None:
        """Reconnect loop: (re)Identify whenever the socket drops."""
        backoff = 1.0
        while self._running:
            try:
                await self._connect_once()
                backoff = 1.0  # clean session end resets backoff
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Discord gateway session ended: %s", exc)
            if not self._running:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    async def _gateway_url(self) -> str:
        try:
            resp = await self._session.get(f"{API_ROOT}/gateway", headers=self._auth_headers)
            data = await resp.json()
            return data.get("url", "wss://gateway.discord.gg") + "/?v=10&encoding=json"
        except Exception:
            return "wss://gateway.discord.gg/?v=10&encoding=json"

    async def _connect_once(self) -> None:
        url = await self._gateway_url()
        async with self._session.ws_connect(url, heartbeat=None) as ws:
            self._ws = ws
            hello = await ws.receive_json()
            if hello.get("op") != OP_HELLO:
                raise RuntimeError(f"expected HELLO, got op={hello.get('op')}")
            interval = hello["d"]["heartbeat_interval"] / 1000.0
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws, interval))

            await ws.send_json({
                "op": OP_IDENTIFY,
                "d": {
                    "token": self.bot_token,
                    "intents": DEFAULT_INTENTS,
                    "properties": {
                        "os": "linux", "browser": "minxg", "device": "minxg",
                    },
                },
            })

            async for raw in ws:
                if raw.type != aiohttp.WSMsgType.TEXT:
                    continue
                payload = raw.json()
                await self._handle_payload(payload)

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def _heartbeat_loop(self, ws: aiohttp.ClientWebSocketResponse, interval: float) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                await ws.send_json({"op": OP_HEARTBEAT, "d": self._seq})
        except asyncio.CancelledError:
            pass

    async def _handle_payload(self, payload: Dict[str, Any]) -> None:
        op = payload.get("op")
        if payload.get("s") is not None:
            self._seq = payload["s"]

        if op == OP_RECONNECT or op == OP_INVALID_SESSION:
            if self._ws and not self._ws.closed:
                await self._ws.close()
            return
        if op != OP_DISPATCH:
            return

        event_type = payload.get("t")
        data = payload.get("d") or {}

        if event_type == "READY":
            self._own_user_id = (data.get("user") or {}).get("id")
            logger.info("Discord gateway ready as %s", (data.get("user") or {}).get("username"))
            return

        if event_type != "MESSAGE_CREATE":
            return

        author = data.get("author") or {}
        if author.get("bot") or author.get("id") == self._own_user_id:
            return  # never react to bots (including ourselves)

        content = data.get("content", "")
        channel_id = data.get("channel_id")
        if not content or channel_id is None:
            return
        if self.allowed_channel_ids and int(channel_id) not in self.allowed_channel_ids:
            return

        await self._inbox.put(ChannelMessage(
            from_user=author.get("username") or str(author.get("id", "unknown")),
            content=content,
            channel=self.name,
            session_id=f"discord_{channel_id}",
            metadata={"channel_id": channel_id, "message_id": data.get("id")},
        ))

    async def receive(self) -> Optional[ChannelMessage]:
        if not self._running:
            return None
        try:
            return await asyncio.wait_for(self._inbox.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    async def send(self, msg: ChannelMessage, content: str) -> None:
        if not self._session or not content:
            return
        channel_id = msg.metadata.get("channel_id")
        if channel_id is None:
            logger.warning("DiscordChannel.send: no channel_id in metadata, dropping reply")
            return
        try:
            await self._session.post(
                f"{API_ROOT}/channels/{channel_id}/messages",
                headers=self._auth_headers,
                json={"content": content[:2000]},
            )
        except aiohttp.ClientError as exc:
            logger.warning("Discord sendMessage failed: %s", exc)


def build_from_options(name: str, options: Dict[str, Any]) -> DiscordChannel:
    """Factory used by :class:`gateway.channels.ChannelManager`."""
    return DiscordChannel(
        name=name,
        bot_token=str(options.get("bot_token", "") or ""),
        allowed_channel_ids=[int(x) for x in (options.get("allowed_channel_ids") or [])],
    )
