"""
MINXG Streaming — SSE and WebSocket streaming support.
"""
from __future__ import annotations

from typing import AsyncGenerator, Generator, Dict, Any, Optional, Callable
import asyncio
import json
import time


class StreamingResponse:
    """
    Server-Sent Events (SSE) streaming response.

    Yields chunks as they become available from the LLM.
    """

    def __init__(self, chunks: Generator[str, None, None]):
        self.chunks = chunks
        self._buffer = []
        self._done = False

    def __iter__(self) -> Generator[str, None, None]:
        for chunk in self.chunks:
            self._buffer.append(chunk)
            yield self._format_sse(chunk)
        yield "data: [DONE]\n\n"
        self._done = True

    @staticmethod
    def _format_sse(data: str) -> str:
        """Format data as SSE event."""
        return f"data: {data}\n\n"

    def get_buffer(self) -> list:
        """Get accumulated chunks."""
        return self._buffer

    def is_done(self) -> bool:
        """Check if streaming is complete."""
        return self._done


class AsyncStreamingResponse:
    """Async version of streaming response."""

    def __init__(self, chunks: AsyncGenerator[str, None]):
        self.chunks = chunks
        self._buffer = []
        self._done = False

    async def __aiter__(self) -> AsyncGenerator[str, None]:
        async for chunk in self.chunks:
            self._buffer.append(chunk)
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"
        self._done = True

    async def collect(self) -> str:
        """Collect all chunks into a single string."""
        result = []
        async for chunk in self:
            if chunk.strip() and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[5:].strip())
                    result.append(data.get("content", ""))
                except json.JSONDecodeError:
                    pass
        return "".join(result)


class StreamParser:
    """Parse streaming responses."""

    @staticmethod
    def parse_sse_line(line: str) -> Optional[Dict[str, Any]]:
        """Parse a single SSE line."""
        if line.startswith("data: "):
            data = line[6:].strip()
            if data == "[DONE]":
                return None
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def accumulate_chunks(chunks: list) -> str:
        """Accumulate chunks into final text."""
        return "".join(chunks)


class TokenStream:
    """
    Token-by-token streaming with callback support.

    Useful for real-time display of LLM output.
    """

    def __init__(
        self,
        on_token: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        self.on_token = on_token
        self.on_complete = on_complete
        self.on_error = on_error
        self._tokens = []
        self._start_time = time.time()
        self._end_time: Optional[float] = None

    def push(self, token: str) -> None:
        """Push a new token."""
        self._tokens.append(token)
        if self.on_token:
            self.on_token(token)

    def complete(self) -> str:
        """Mark stream as complete."""
        self._end_time = time.time()
        text = "".join(self._tokens)
        if self.on_complete:
            self.on_complete(text)
        return text

    def error(self, exc: Exception) -> None:
        """Handle stream error."""
        if self.on_error:
            self.on_error(exc)

    @property
    def tokens_per_second(self) -> float:
        """Calculate tokens per second."""
        elapsed = (self._end_time or time.time()) - self._start_time
        if elapsed == 0:
            return 0
        return len(self._tokens) / elapsed

    @property
    def total_tokens(self) -> int:
        """Total tokens received."""
        return len(self._tokens)

    @property
    def latency_ms(self) -> float:
        """Time to first token."""
        if len(self._tokens) > 0:
            return (self._end_time or time.time()) - self._start_time
        return 0


class ChunkAggregator:
    """Aggregate streaming chunks into structured output."""

    def __init__(self):
        self.chunks = []
        self.role: Optional[str] = None
        self.model: Optional[str] = None
        self.finish_reason: Optional[str] = None
        self.usage: Optional[Dict] = None

    def add(self, chunk: Dict[str, Any]) -> None:
        """Add a chunk."""
        self.chunks.append(chunk)
        if "model" in chunk:
            self.model = chunk["model"]
        if "usage" in chunk:
            self.usage = chunk["usage"]

    def get_content(self) -> str:
        """Extract full content from chunks."""
        content = []
        for chunk in self.chunks:
            delta = chunk.get("choices", [{}])[0].get("delta", {})
            if "content" in delta:
                content.append(delta["content"])
            if chunk.get("choices", [{}])[0].get("finish_reason") == "stop":
                self.finish_reason = "stop"
        return "".join(content)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to final response dict."""
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": self.role or "assistant",
                        "content": self.get_content(),
                    },
                    "finish_reason": self.finish_reason or "stop",
                }
            ],
            "usage": self.usage,
        }


async def stream_generator(
    text: str,
    chunk_size: int = 10,
    delay: float = 0.01,
) -> AsyncGenerator[str, None]:
    """Generate streaming chunks from text."""
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        yield chunk
        await asyncio.sleep(delay)


def create_mock_stream(
    text: str,
    model: str = "gpt-4o",
) -> AsyncGenerator[Dict[str, Any], None]:
    """Create a mock OpenAI-compatible stream."""
    async def _stream():
        words = text.split()
        for i, word in enumerate(words):
            chunk = {
                "id": f"chatcmpl-{i}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": word + " "},
                        "finish_reason": None,
                    }
                ],
            }
            yield chunk
            await asyncio.sleep(0.01)

        # Final chunk
        yield {
            "id": f"chatcmpl-final",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }

    return _stream()
