"""gateway/channel_slack.py — Slack channel adapter (Socket Mode).

Implements :class:`gateway.channels.ChannelAdapter` against Slack's
Socket Mode (receiving) and Web API ``chat.postMessage`` (sending) —
https://api.slack.com/apis/socket-mode. Socket Mode is deliberately
chosen over Events API webhooks: it needs an *app-level token* and an
outbound websocket connection only, no public HTTPS endpoint or open
port, which matches the local-first shape of every other channel here.

Config::

    channels:
      - name: slack
        enabled: true
        adapter: slack
        options:
          bot_token: "${SLACK_BOT_TOKEN}"    # xoxb-...  (chat.postMessage)
          app_token: "${SLACK_APP_TOKEN}"    # xapp-...  (Socket Mode)
          allowed_channel_ids: ["C0123456"]  # empty = allow all

Both tokens are required: the app-level token opens the socket, the bot
token is the one authorised to actually post messages.

Honesty note: implemented from Slack's public Socket Mode + Web API docs
and unit-tested with a mocked websocket/HTTP layer
(``tests/test_channel_slack.py``). Not exercised against Slack's live
servers in this environment — the sandbox's outbound allowlist does not
include ``slack.com``. Smoke-test with real tokens before relying on it.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

from gateway.channels import ChannelAdapter, ChannelMessage

logger = logging.getLogger("gateway.channels.slack")

WEB_API_ROOT = "https://slack.com/api"


class SlackChannel(ChannelAdapter):
    """Reads `message` events off a Slack Socket Mode connection; replies via Web API."""

    def __init__(
        self,
        name: str = "slack",
        bot_token: str = "",
        app_token: str = "",
        allowed_channel_ids: Optional[List[str]] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        super().__init__(name, enabled=True)
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN", "")
        self.app_token = app_token or os.getenv("SLACK_APP_TOKEN", "")
        self.allowed_channel_ids = set(allowed_channel_ids or [])
        self._session = session
        self._owns_session = session is None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._inbox: "asyncio.Queue[ChannelMessage]" = asyncio.Queue()
        self._reader_task: Optional[asyncio.Task] = None
        self._own_bot_id: Optional[str] = None

    async def connect(self) -> None:
        if not self.bot_token or not self.app_token:
            logger.warning(
                "SlackChannel %r enabled but bot_token/app_token missing — "
                "set SLACK_BOT_TOKEN + SLACK_APP_TOKEN or channels[].options; "
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
        if self._reader_task:
            self._reader_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def _run_forever(self) -> None:
        backoff = 1.0
        while self._running:
            try:
                await self._connect_once()
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Slack socket-mode session ended: %s", exc)
            if not self._running:
                return
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)

    async def _open_socket_url(self) -> str:
        resp = await self._session.post(
            f"{WEB_API_ROOT}/apps.connections.open",
            headers={"Authorization": f"Bearer {self.app_token}"},
        )
        data = await resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"apps.connections.open failed: {data.get('error')}")
        return data["url"]

    async def _connect_once(self) -> None:
        url = await self._open_socket_url()
        async with self._session.ws_connect(url, heartbeat=30) as ws:
            self._ws = ws
            async for raw in ws:
                if raw.type != aiohttp.WSMsgType.TEXT:
                    continue
                envelope = raw.json()
                await self._handle_envelope(ws, envelope)

    async def _handle_envelope(self, ws: aiohttp.ClientWebSocketResponse, envelope: Dict[str, Any]) -> None:
        etype = envelope.get("type")
        envelope_id = envelope.get("envelope_id")

        if etype == "hello":
            logger.info("Slack Socket Mode connection established")
            return
        if etype == "disconnect":
            await ws.close()
            return

        # Any event carrying an envelope_id must be ack'd within 3s,
        # regardless of whether we act on it.
        if envelope_id:
            await ws.send_json({"envelope_id": envelope_id})

        if etype != "events_api":
            return

        event = (envelope.get("payload") or {}).get("event") or {}
        if event.get("type") != "message":
            return
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return  # don't react to bots, including ourselves

        text = event.get("text", "")
        channel_id = event.get("channel")
        if not text or not channel_id:
            return
        if self.allowed_channel_ids and channel_id not in self.allowed_channel_ids:
            return

        await self._inbox.put(ChannelMessage(
            from_user=event.get("user", "unknown"),
            content=text,
            channel=self.name,
            session_id=f"slack_{channel_id}_{event.get('ts', '')}",
            metadata={"channel_id": channel_id, "thread_ts": event.get("thread_ts")},
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
            logger.warning("SlackChannel.send: no channel_id in metadata, dropping reply")
            return
        body = {"channel": channel_id, "text": content[:40000]}
        if msg.metadata.get("thread_ts"):
            body["thread_ts"] = msg.metadata["thread_ts"]
        try:
            resp = await self._session.post(
                f"{WEB_API_ROOT}/chat.postMessage",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                json=body,
            )
            data = await resp.json()
            if not data.get("ok"):
                logger.warning("Slack chat.postMessage error: %s", data.get("error"))
        except aiohttp.ClientError as exc:
            logger.warning("Slack chat.postMessage failed: %s", exc)


def build_from_options(name: str, options: Dict[str, Any]) -> SlackChannel:
    """Factory used by :class:`gateway.channels.ChannelManager`."""
    return SlackChannel(
        name=name,
        bot_token=str(options.get("bot_token", "") or ""),
        app_token=str(options.get("app_token", "") or ""),
        allowed_channel_ids=list(options.get("allowed_channel_ids") or []),
    )
