"""tests/test_orchestrator_session_reuse.py — multiling/orchestrator.py's
`_run_with_upstream_ai` and `_stream_conversation`.

These had zero test coverage before this pass despite being the code
that actually talks to an AI provider — which is exactly how a real
bug survived here: both used to open a **fresh** `aiohttp.ClientSession()`
(and therefore a fresh TCP/TLS handshake) on every single round-trip
within one multi-turn tool-calling conversation, discarding connection
reuse for no reason. Fixed to share one session across a conversation's
round-trips instead.

Verifying "the framework's own per-call overhead went down" isn't
meaningful against a mock in isolation (mocks don't pay TCP/TLS
handshake cost either way), so what's tested here is the thing that
actually matters and *is* observable locally: multiple round-trips in
one conversation arrive at the server over the **same** underlying
connection when they should, using a real local aiohttp server (no
external network needed — this sandbox can't reach a real AI provider
anyway) rather than mocking `aiohttp` itself, which would only prove
the code *calls* aiohttp correctly, not that connections are actually
being reused end to end.
"""
from __future__ import annotations

import asyncio
import json as jsonlib

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from multiling.orchestrator import NexusOrchestrator


def _sse(data: dict) -> bytes:
    return f"data: {jsonlib.dumps(data)}\n\n".encode("utf-8")


class ScriptedOpenAIServer:
    """A tiny local stand-in for an OpenAI-compatible /chat/completions
    endpoint. Tracks which underlying connection (by `transport` object
    identity) each request arrived on, so tests can assert on real
    connection reuse instead of just "no exception was raised"."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0
        self.connections_seen = set()
        self.request_payloads = []

    async def handler(self, request: web.Request) -> web.StreamResponse:
        # Identify the underlying connection this request arrived on.
        transport = request.transport
        self.connections_seen.add(id(transport))

        payload = await request.json()
        self.request_payloads.append(payload)
        response_spec = self.responses[min(self.call_count, len(self.responses) - 1)]
        self.call_count += 1

        if payload.get("stream"):
            resp = web.StreamResponse(
                status=200, headers={"Content-Type": "text/event-stream"})
            await resp.prepare(request)
            for chunk in response_spec["stream_chunks"]:
                await resp.write(_sse(chunk))
            await resp.write(b"data: [DONE]\n\n")
            await resp.write_eof()
            return resp
        else:
            return web.json_response(response_spec["json"])

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_post("/chat/completions", self.handler)
        return app


def _openai_json_response(content: str = None, tool_calls: list = None) -> dict:
    message = {"role": "assistant", "content": content or ""}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}]}


def _tool_call_chunk(idx, call_id, name, arguments):
    return {"choices": [{"delta": {"tool_calls": [
        {"index": idx, "id": call_id, "function": {"name": name, "arguments": arguments}}
    ]}}]}


def _text_chunk(text):
    return {"choices": [{"delta": {"content": text}}]}


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


async def _run_server(app):
    server = TestServer(app)
    await server.start_server()
    return server


class _BackgroundServer:
    """Runs a TestServer on its own event loop in a background thread.

    `_run_with_upstream_ai` is a *synchronous* method that creates and
    drives its own `asyncio.new_event_loop()` internally (that's true
    both before and after this pass's fix — not something introduced
    by it). That means it can't be called from inside a coroutine
    that's already running under `asyncio.run()`: a nested
    `run_until_complete()` on a second loop raises `RuntimeError:
    Cannot run the event loop while another loop is running`. Running
    the test server in a separate thread (with its own loop) sidesteps
    that entirely — the orchestrator call happens in plain synchronous
    code on the main thread, and it reaches the server over a real
    TCP connection like it would any other HTTP server.
    """

    def __init__(self, app):
        import threading
        self._app = app
        self._loop = None
        self._server = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._server = self._loop.run_until_complete(_run_server(self._app))
        self._ready.set()
        self._loop.run_forever()

    def start(self) -> str:
        self._thread.start()
        self._ready.wait(timeout=5)
        return str(self._server.make_url(""))

    def stop(self):
        async def _close():
            await self._server.close()
        asyncio.run_coroutine_threadsafe(_close(), self._loop).result(timeout=5)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


class TestNonStreamingSessionReuse:
    def test_single_round_trip_gets_correct_result(self):
        server_obj = ScriptedOpenAIServer([
            {"json": _openai_json_response("hello there")},
        ])
        bg = _BackgroundServer(server_obj.app())
        base_url = bg.start()
        try:
            orch = NexusOrchestrator(
                ai_provider="openai", ai_base_url=base_url,
                ai_model="test-model", enabled_toolsets=[],
            )
            result = orch._run_with_upstream_ai([{"role": "user", "content": "hi"}], [])
        finally:
            bg.stop()

        assert result["final_response"] == "hello there"
        assert server_obj.call_count == 1

    def test_multi_round_tool_call_reuses_one_connection(self):
        """The actual bug this pass fixed: a multi-round tool-calling
        conversation used to open a brand new TCP connection (via a
        brand new aiohttp.ClientSession()) for every single round."""
        server_obj = ScriptedOpenAIServer([
            {"json": _openai_json_response(tool_calls=[{
                "id": "call_1", "type": "function",
                "function": {"name": "noop_tool", "arguments": "{}"},
            }])},
            {"json": _openai_json_response("done after tool call")},
        ])
        bg = _BackgroundServer(server_obj.app())
        base_url = bg.start()
        try:
            orch = NexusOrchestrator(
                ai_provider="openai", ai_base_url=base_url,
                ai_model="test-model", enabled_toolsets=[],
            )
            from unittest import mock
            with mock.patch(
                "multiling.orchestrator.handle_function_call",
                return_value=jsonlib.dumps({"ok": True}),
            ):
                result = orch._run_with_upstream_ai(
                    [{"role": "user", "content": "do the thing"}],
                    [{"type": "function", "function": {"name": "noop_tool", "parameters": {}}}],
                )
        finally:
            bg.stop()

        assert server_obj.call_count == 2, "expected exactly 2 round-trips (tool call + follow-up)"
        assert len(server_obj.connections_seen) == 1, (
            f"expected 1 reused connection across both round-trips, "
            f"saw {len(server_obj.connections_seen)} distinct connections"
        )


class TestStreamingSessionReuse:
    def test_single_round_trip_streams_text(self):
        server_obj = ScriptedOpenAIServer([
            {"stream_chunks": [_text_chunk("hel"), _text_chunk("lo")]},
        ])

        async def scenario():
            server = await _run_server(server_obj.app())
            try:
                base_url = str(server.make_url(""))
                orch = NexusOrchestrator(
                    ai_provider="openai", ai_base_url=base_url,
                    ai_model="test-model", enabled_toolsets=[],
                )
                events = []
                async for event in orch._stream_conversation(
                    [{"role": "user", "content": "hi"}], tools=[],
                ):
                    events.append(event)
                return events
            finally:
                await server.close()

        events = asyncio.run(scenario())
        text = "".join(e["content"] for e in events if e["type"] == "text")
        assert text == "hello"
        assert events[-1]["type"] == "done"
        assert server_obj.call_count == 1

    def test_multi_round_tool_call_reuses_one_connection(self):
        server_obj = ScriptedOpenAIServer([
            {"stream_chunks": [_tool_call_chunk(0, "call_1", "noop_tool", "{}")]},
            {"stream_chunks": [_text_chunk("all done")]},
        ])

        async def scenario():
            server = await _run_server(server_obj.app())
            try:
                base_url = str(server.make_url(""))
                orch = NexusOrchestrator(
                    ai_provider="openai", ai_base_url=base_url,
                    ai_model="test-model", enabled_toolsets=[],
                )
                from unittest import mock
                events = []
                with mock.patch(
                    "multiling.orchestrator.handle_function_call",
                    return_value=jsonlib.dumps({"ok": True}),
                ):
                    async for event in orch._stream_conversation(
                        [{"role": "user", "content": "do it"}],
                        tools=[{"type": "function",
                                "function": {"name": "noop_tool", "parameters": {}}}],
                    ):
                        events.append(event)
                return events
            finally:
                await server.close()

        events = asyncio.run(scenario())
        assert any(e["type"] == "tool_call" for e in events)
        assert any(e["type"] == "tool_result" for e in events)
        final_text = "".join(e["content"] for e in events if e["type"] == "text")
        assert final_text == "all done"
        assert server_obj.call_count == 2, "expected exactly 2 round-trips"
        assert len(server_obj.connections_seen) == 1, (
            f"expected 1 reused connection across both streaming round-trips, "
            f"saw {len(server_obj.connections_seen)} distinct connections"
        )

    def test_max_iters_bound_is_respected(self):
        """Server always responds with another tool call — the loop
        must still stop at max_iters instead of looping forever."""
        server_obj = ScriptedOpenAIServer([
            {"stream_chunks": [_tool_call_chunk(0, f"call_{i}", "noop_tool", "{}")]}
            for i in range(10)
        ])

        async def scenario():
            server = await _run_server(server_obj.app())
            try:
                base_url = str(server.make_url(""))
                orch = NexusOrchestrator(
                    ai_provider="openai", ai_base_url=base_url,
                    ai_model="test-model", enabled_toolsets=[],
                )
                from unittest import mock
                events = []
                with mock.patch(
                    "multiling.orchestrator.handle_function_call",
                    return_value=jsonlib.dumps({"ok": True}),
                ):
                    async for event in orch._stream_conversation(
                        [{"role": "user", "content": "loop forever?"}],
                        tools=[{"type": "function",
                                "function": {"name": "noop_tool", "parameters": {}}}],
                        max_iters=3,
                    ):
                        events.append(event)
                return events
            finally:
                await server.close()

        events = asyncio.run(scenario())
        assert events[-1] == {"type": "done", "final_text": "[Max iterations reached]"}
        assert server_obj.call_count == 3
        # even bounded-out, the connection should still have been reused
        assert len(server_obj.connections_seen) == 1
