"""tests/test_channel_slack.py — SlackChannel against a mocked Socket Mode connection.

We can't reach slack.com from this sandbox, so these tests fake the
aiohttp session/websocket and assert on: apps.connections.open request
shape, envelope ack behaviour, message-event parsing, bot-message
filtering, the channel allowlist, and chat.postMessage calls.
"""
from __future__ import annotations

import asyncio

import aiohttp
import pytest

from gateway.channel_slack import SlackChannel, build_from_options
from gateway.channels import ChannelMessage


def _run(coro):
    return asyncio.run(coro)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class _FakeWS:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True


class _FakeSession:
    def __init__(self):
        self.post_calls = []

    async def post(self, url, headers=None, json=None):
        self.post_calls.append({"url": url, "headers": headers, "json": json})
        if url.endswith("/apps.connections.open"):
            return _FakeResponse({"ok": True, "url": "wss://fake-socket-mode.example"})
        return _FakeResponse({"ok": True})

    async def close(self):
        pass


class TestOpenSocketUrl:
    def test_open_socket_url_uses_app_token(self):
        session = _FakeSession()
        ch = SlackChannel(bot_token="xoxb-1", app_token="xapp-1", session=session)
        url = _run(ch._open_socket_url())
        assert url == "wss://fake-socket-mode.example"
        call = session.post_calls[-1]
        assert call["url"].endswith("/apps.connections.open")
        assert call["headers"]["Authorization"] == "Bearer xapp-1"

    def test_open_socket_url_raises_on_error(self):
        class _ErrSession(_FakeSession):
            async def post(self, url, headers=None, json=None):
                return _FakeResponse({"ok": False, "error": "invalid_auth"})
        ch = SlackChannel(bot_token="xoxb-1", app_token="bad", session=_ErrSession())
        with pytest.raises(RuntimeError):
            _run(ch._open_socket_url())


class TestHandleEnvelope:
    def _channel(self):
        return SlackChannel(bot_token="xoxb-1", app_token="xapp-1", session=_FakeSession())

    def test_hello_envelope_is_noop(self):
        ch = self._channel()
        ws = _FakeWS()
        _run(ch._handle_envelope(ws, {"type": "hello"}))
        assert ws.sent == []

    def test_events_api_message_acked_and_queued(self):
        ch = self._channel()
        ws = _FakeWS()
        envelope = {
            "type": "events_api",
            "envelope_id": "env-1",
            "payload": {"event": {
                "type": "message", "text": "hi there",
                "channel": "C123", "user": "U1", "ts": "1700000000.001",
            }},
        }

        async def scenario():
            await ch._handle_envelope(ws, envelope)
            return await ch.receive()

        ch._running = True
        msg = _run(scenario())
        assert ws.sent == [{"envelope_id": "env-1"}]  # must ack regardless
        assert isinstance(msg, ChannelMessage)
        assert msg.content == "hi there"
        assert msg.from_user == "U1"
        assert msg.metadata["channel_id"] == "C123"

    def test_bot_messages_are_ignored_but_still_acked(self):
        ch = self._channel()
        ws = _FakeWS()
        envelope = {
            "type": "events_api",
            "envelope_id": "env-2",
            "payload": {"event": {
                "type": "message", "text": "beep", "channel": "C123",
                "bot_id": "B999",
            }},
        }

        async def scenario():
            await ch._handle_envelope(ws, envelope)
            return await ch.receive()

        ch._running = True
        msg = _run(scenario())
        assert ws.sent == [{"envelope_id": "env-2"}]
        assert msg is None

    def test_allowed_channel_ids_filters(self):
        ch = SlackChannel(bot_token="x", app_token="y",
                           allowed_channel_ids=["C_ALLOWED"], session=_FakeSession())
        ws = _FakeWS()
        envelope = {
            "type": "events_api", "envelope_id": "env-3",
            "payload": {"event": {"type": "message", "text": "hi",
                                    "channel": "C_OTHER", "user": "U1"}},
        }

        async def scenario():
            await ch._handle_envelope(ws, envelope)
            return await ch.receive()

        ch._running = True
        msg = _run(scenario())
        assert msg is None

    def test_non_message_event_types_ignored(self):
        ch = self._channel()
        ws = _FakeWS()
        envelope = {
            "type": "events_api", "envelope_id": "env-4",
            "payload": {"event": {"type": "reaction_added"}},
        }

        async def scenario():
            await ch._handle_envelope(ws, envelope)
            return await ch.receive()

        ch._running = True
        msg = _run(scenario())
        assert msg is None
        assert ws.sent == [{"envelope_id": "env-4"}]  # still acked


class TestSend:
    def test_send_posts_to_chat_postmessage(self):
        session = _FakeSession()
        ch = SlackChannel(bot_token="xoxb-1", app_token="xapp-1", session=session)
        reply_to = ChannelMessage(
            from_user="U1", content="hi", channel="slack",
            metadata={"channel_id": "C123"},
        )
        _run(ch.send(reply_to, "hello back"))
        call = session.post_calls[-1]
        assert call["url"].endswith("/chat.postMessage")
        assert call["headers"]["Authorization"] == "Bearer xoxb-1"
        assert call["json"] == {"channel": "C123", "text": "hello back"}

    def test_send_includes_thread_ts_when_present(self):
        session = _FakeSession()
        ch = SlackChannel(bot_token="xoxb-1", app_token="xapp-1", session=session)
        reply_to = ChannelMessage(
            from_user="U1", content="hi", channel="slack",
            metadata={"channel_id": "C123", "thread_ts": "1700000000.001"},
        )
        _run(ch.send(reply_to, "hello back"))
        call = session.post_calls[-1]
        assert call["json"]["thread_ts"] == "1700000000.001"

    def test_send_without_channel_id_is_noop(self):
        session = _FakeSession()
        ch = SlackChannel(bot_token="xoxb-1", app_token="xapp-1", session=session)
        reply_to = ChannelMessage(from_user="U1", content="hi", channel="slack", metadata={})
        _run(ch.send(reply_to, "hello"))
        assert session.post_calls == []


class TestConnectGuard:
    def test_connect_without_tokens_stays_idle(self):
        ch = SlackChannel(bot_token="", app_token="", session=_FakeSession())
        _run(ch.connect())
        assert ch._running is False


class TestBuildFromOptions:
    def test_build_from_options(self):
        ch = build_from_options("sl", {
            "bot_token": "xoxb-1", "app_token": "xapp-1",
            "allowed_channel_ids": ["C1", "C2"],
        })
        assert ch.bot_token == "xoxb-1"
        assert ch.app_token == "xapp-1"
        assert ch.allowed_channel_ids == {"C1", "C2"}
