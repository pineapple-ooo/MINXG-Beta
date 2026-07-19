"""tests/test_channel_discord.py — DiscordChannel against a mocked gateway websocket.

We can't reach discord.com/gateway.discord.gg from this sandbox, so
these tests fake the aiohttp session + websocket and assert on the
protocol handling: Identify payload shape, MESSAGE_CREATE parsing,
self/bot-message filtering, the channel allowlist, and REST send calls.
"""
from __future__ import annotations

import asyncio

import aiohttp
import pytest

from gateway.channel_discord import DiscordChannel, build_from_options
from gateway.channels import ChannelMessage


def _run(coro):
    return asyncio.run(coro)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class _FakeWSMessage:
    def __init__(self, data):
        self.type = aiohttp.WSMsgType.TEXT
        self._data = data

    def json(self):
        return self._data


class _FakeWS:
    def __init__(self, hello, events):
        self._hello = hello
        self._events = list(events)
        self.sent = []
        self.closed = False

    async def receive_json(self):
        return self._hello

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._events:
            raise StopAsyncIteration
        return _FakeWSMessage(self._events.pop(0))


class _FakeWSConnectCM:
    def __init__(self, ws):
        self._ws = ws

    async def __aenter__(self):
        return self._ws

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, ws=None):
        self._ws = ws
        self.get_calls = []
        self.post_calls = []

    async def get(self, url, headers=None):
        self.get_calls.append((url, headers))
        return _FakeResponse({"url": "wss://fake-gateway.example"})

    def ws_connect(self, url, heartbeat=None):
        return _FakeWSConnectCM(self._ws)

    async def post(self, url, headers=None, json=None):
        self.post_calls.append({"url": url, "headers": headers, "json": json})
        return _FakeResponse({})

    async def close(self):
        pass


HELLO = {"op": 10, "d": {"heartbeat_interval": 41250}}


def _dispatch(t, d, seq=1):
    return {"op": 0, "t": t, "s": seq, "d": d}


class TestConnectOnce:
    def test_identify_payload_sent_after_hello(self):
        ws = _FakeWS(HELLO, events=[])
        ch = DiscordChannel(bot_token="tok123", session=_FakeSession(ws))
        _run(ch._connect_once())
        assert ws.sent, "expected an Identify frame to be sent"
        identify = ws.sent[0]
        assert identify["op"] == 2
        assert identify["d"]["token"] == "tok123"
        assert identify["d"]["intents"] == (1 | (1 << 9) | (1 << 15))

    def test_message_create_lands_in_inbox(self):
        events = [_dispatch("READY", {"user": {"id": "self1", "username": "minxg-bot"}}, seq=1),
                  _dispatch("MESSAGE_CREATE", {
                      "content": "hello bot", "channel_id": "555",
                      "author": {"id": "u1", "username": "carol", "bot": False},
                      "id": "msg1",
                  }, seq=2)]
        ws = _FakeWS(HELLO, events=events)
        ch = DiscordChannel(bot_token="tok123", session=_FakeSession(ws))
        ch._running = True  # normally set by connect(); testing _connect_once() directly

        async def scenario():
            await ch._connect_once()
            return await ch.receive()

        msg = _run(scenario())
        assert isinstance(msg, ChannelMessage)
        assert msg.content == "hello bot"
        assert msg.from_user == "carol"
        assert msg.session_id == "discord_555"
        assert msg.metadata["channel_id"] == "555"

    def test_bot_messages_are_ignored(self):
        events = [_dispatch("MESSAGE_CREATE", {
            "content": "beep boop", "channel_id": "555",
            "author": {"id": "botid", "username": "otherbot", "bot": True},
        })]
        ws = _FakeWS(HELLO, events=events)
        ch = DiscordChannel(bot_token="tok123", session=_FakeSession(ws))
        ch._running = True  # normally set by connect(); testing _connect_once() directly

        async def scenario():
            await ch._connect_once()
            return await ch.receive()

        msg = _run(scenario())
        assert msg is None

    def test_own_messages_after_ready_are_ignored(self):
        events = [
            _dispatch("READY", {"user": {"id": "self1", "username": "minxg-bot"}}, seq=1),
            _dispatch("MESSAGE_CREATE", {
                "content": "echo", "channel_id": "555",
                "author": {"id": "self1", "username": "minxg-bot", "bot": False},
            }, seq=2),
        ]
        ws = _FakeWS(HELLO, events=events)
        ch = DiscordChannel(bot_token="tok123", session=_FakeSession(ws))
        ch._running = True  # normally set by connect(); testing _connect_once() directly

        async def scenario():
            await ch._connect_once()
            return await ch.receive()

        msg = _run(scenario())
        assert msg is None

    def test_allowed_channel_ids_filters(self):
        events = [_dispatch("MESSAGE_CREATE", {
            "content": "hi", "channel_id": "999",
            "author": {"id": "u1", "username": "dave", "bot": False},
        })]
        ws = _FakeWS(HELLO, events=events)
        ch = DiscordChannel(bot_token="tok123", allowed_channel_ids=[555], session=_FakeSession(ws))
        ch._running = True  # normally set by connect(); testing _connect_once() directly

        async def scenario():
            await ch._connect_once()
            return await ch.receive()

        msg = _run(scenario())
        assert msg is None  # channel 999 not allowlisted

    def test_non_hello_first_frame_raises(self):
        ws = _FakeWS({"op": 0, "d": {}}, events=[])
        ch = DiscordChannel(bot_token="tok123", session=_FakeSession(ws))
        with pytest.raises(RuntimeError):
            _run(ch._connect_once())


class TestSend:
    def test_send_posts_content_with_bot_auth(self):
        session = _FakeSession()
        ch = DiscordChannel(bot_token="tok123", session=session)
        reply_to = ChannelMessage(
            from_user="carol", content="hi", channel="discord",
            session_id="discord_555", metadata={"channel_id": "555"},
        )
        _run(ch.send(reply_to, "hello back"))
        call = session.post_calls[-1]
        assert call["url"].endswith("/channels/555/messages")
        assert call["headers"]["Authorization"] == "Bot tok123"
        assert call["json"] == {"content": "hello back"}

    def test_send_without_channel_id_is_noop(self):
        session = _FakeSession()
        ch = DiscordChannel(bot_token="tok123", session=session)
        reply_to = ChannelMessage(from_user="c", content="hi", channel="discord", metadata={})
        _run(ch.send(reply_to, "hello"))
        assert session.post_calls == []


class TestConnectGuard:
    def test_connect_without_token_stays_idle(self):
        ch = DiscordChannel(bot_token="", session=_FakeSession())
        _run(ch.connect())
        assert ch._running is False


class TestBuildFromOptions:
    def test_build_from_options(self):
        ch = build_from_options("dc", {"bot_token": "abc", "allowed_channel_ids": ["1", "2"]})
        assert ch.bot_token == "abc"
        assert ch.allowed_channel_ids == {1, 2}
