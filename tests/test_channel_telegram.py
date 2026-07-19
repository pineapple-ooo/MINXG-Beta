"""tests/test_channel_telegram.py — TelegramChannel against a mocked HTTP session.

We can't reach api.telegram.org from this sandbox (outbound network is
allowlisted to package registries only), so these tests fake the
aiohttp session and assert on: URL construction, param/payload shape,
offset tracking, the allowlist filter, and graceful handling of
malformed/error responses.
"""
from __future__ import annotations

import asyncio
import json as jsonlib

import pytest

from gateway.channel_telegram import TelegramChannel, build_from_options
from gateway.channels import ChannelMessage


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []
        self._get_queue = []
        self.closed = False

    def queue_get_response(self, payload):
        self._get_queue.append(payload)

    async def get(self, url, params=None, timeout=None):
        self.get_calls.append({"url": url, "params": params})
        payload = self._get_queue.pop(0) if self._get_queue else {"ok": True, "result": []}
        return _FakeResponse(payload)

    async def post(self, url, json=None):
        self.post_calls.append({"url": url, "json": json})
        return _FakeResponse({"ok": True, "result": {}})

    async def close(self):
        self.closed = True


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def channel():
    ch = TelegramChannel(bot_token="123:ABC", session=_FakeSession())
    _run(ch.connect())
    return ch


class TestConnect:
    def test_connect_without_token_stays_idle(self):
        ch = TelegramChannel(bot_token="", session=_FakeSession())
        _run(ch.connect())
        assert ch._running is False

    def test_connect_with_token_marks_running(self, channel):
        assert channel._running is True

    def test_base_url_embeds_token(self, channel):
        assert channel._base_url == "https://api.telegram.org/bot123:ABC"


class TestReceive:
    def test_receive_parses_text_message(self, channel):
        channel._session.queue_get_response({
            "ok": True,
            "result": [{
                "update_id": 5001,
                "message": {
                    "message_id": 42,
                    "chat": {"id": 999},
                    "from": {"id": 111, "username": "alice"},
                    "text": "hello there",
                },
            }],
        })
        msg = _run(channel.receive())
        assert isinstance(msg, ChannelMessage)
        assert msg.content == "hello there"
        assert msg.from_user == "alice"
        assert msg.session_id == "telegram_999"
        assert msg.metadata["chat_id"] == 999
        # offset must advance past the delivered update
        assert channel._offset == 5002

    def test_receive_uses_offset_and_timeout_params(self, channel):
        _run(channel.receive())
        call = channel._session.get_calls[-1]
        assert call["url"].endswith("/getUpdates")
        assert call["params"]["offset"] == 0
        assert call["params"]["timeout"] == channel.poll_timeout

    def test_receive_skips_non_message_updates(self, channel):
        channel._session.queue_get_response({
            "ok": True,
            "result": [{"update_id": 1, "edited_message": {"text": "no text field handling"}}],
        })
        msg = _run(channel.receive())
        assert msg is None

    def test_receive_returns_none_on_api_error(self, channel):
        channel._session.queue_get_response({"ok": False, "description": "Unauthorized"})
        msg = _run(channel.receive())
        assert msg is None

    def test_allowed_chat_ids_filters_messages(self):
        ch = TelegramChannel(bot_token="123:ABC", allowed_chat_ids=[42], session=_FakeSession())
        _run(ch.connect())
        ch._session.queue_get_response({
            "ok": True,
            "result": [{
                "update_id": 1,
                "message": {"chat": {"id": 999}, "from": {"username": "bob"}, "text": "hi"},
            }],
        })
        msg = _run(ch.receive())
        assert msg is None  # chat 999 not in allowlist

    def test_allowed_chat_ids_admits_listed_chat(self):
        ch = TelegramChannel(bot_token="123:ABC", allowed_chat_ids=[999], session=_FakeSession())
        _run(ch.connect())
        ch._session.queue_get_response({
            "ok": True,
            "result": [{
                "update_id": 1,
                "message": {"chat": {"id": 999}, "from": {"username": "bob"}, "text": "hi"},
            }],
        })
        msg = _run(ch.receive())
        assert msg is not None
        assert msg.from_user == "bob"


class TestSend:
    def test_send_posts_chat_id_and_text(self, channel):
        reply_to = ChannelMessage(
            from_user="alice", content="hi", channel="telegram",
            session_id="telegram_999", metadata={"chat_id": 999},
        )
        _run(channel.send(reply_to, "hello back"))
        call = channel._session.post_calls[-1]
        assert call["url"].endswith("/sendMessage")
        assert call["json"] == {"chat_id": 999, "text": "hello back"}

    def test_send_truncates_long_text(self, channel):
        reply_to = ChannelMessage(
            from_user="alice", content="hi", channel="telegram",
            session_id="telegram_999", metadata={"chat_id": 999},
        )
        _run(channel.send(reply_to, "x" * 5000))
        call = channel._session.post_calls[-1]
        assert len(call["json"]["text"]) == 4096

    def test_send_without_chat_id_is_noop(self, channel):
        reply_to = ChannelMessage(from_user="a", content="hi", channel="telegram", metadata={})
        _run(channel.send(reply_to, "hello"))
        assert channel._session.post_calls == []


class TestBuildFromOptions:
    def test_build_from_options_reads_all_fields(self):
        ch = build_from_options("tg", {
            "bot_token": "999:ZZZ",
            "allowed_chat_ids": [1, 2, 3],
            "poll_timeout": 10,
        })
        assert ch.bot_token == "999:ZZZ"
        assert ch.allowed_chat_ids == {1, 2, 3}
        assert ch.poll_timeout == 10

    def test_build_from_options_defaults(self):
        ch = build_from_options("tg", {})
        assert ch.allowed_chat_ids == set()
        assert ch.poll_timeout == 25
