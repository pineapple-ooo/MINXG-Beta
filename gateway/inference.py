"""
gateway/inference.py — Lightweight Inference

Task difficulty classification + dynamic model selection.

Strategies:
  - L1 (Fast): 70%+ routine tasks → small model / direct tools
  - L2 (Deep): complex reasoning / multi-step orchestration → large model
  - L3 (Expert): extremely complex tasks → strongest model

Classification dimensions:
  - Input length, keywords (analyze/compare/design/debug)
  - Historical tool call count (higher = more complex)
  - Multi-file / multi-step operations
"""
from __future__ import annotations
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ModelProfile:
    name: str
    base_url: str
    api_key: str
    provider: str
    level: int  
    max_tokens: int = 4096
    timeout: int = 60


class TaskGrader:
    """Task difficulty classifier."""

    DEEP_KEYWORDS = [
        "analyze", "compare", "design", "debug", "refactor", "optimize",
        "architecture", "troubleshoot", "multi-step", "complex", "comprehensive",
        "investigate", "evaluate", "assess", "review",
    ]

    EXPERT_KEYWORDS = [
        "system-wide", "root cause", "performance bottleneck",
        "security audit", "concurrency", "distributed",
        "fault tolerant", "scalability", "benchmark",
    ]

    @classmethod
    def grade(cls, query: str, history_tools: int = 0, session_turns: int = 0) -> int:
        """
        Return difficulty level 1/2/3.
        """
        q = query.lower()
        score = 1

        
        deep_hits = sum(1 for k in cls.DEEP_KEYWORDS if k.lower() in q)
        expert_hits = sum(1 for k in cls.EXPERT_KEYWORDS if k.lower() in q)

        if deep_hits >= 2 or expert_hits >= 1:
            score = 2
        if expert_hits >= 2 or (deep_hits >= 3 and history_tools > 3):
            score = 3

        
        if history_tools > 5:
            score = max(score, 2)
        if history_tools > 10 or session_turns > 20:
            score = max(score, 3)

        
        if len(query) > 2000:
            score = max(score, 2)
        if len(query) > 5000:
            score = max(score, 3)

        return min(score, 3)


class InferenceDispatcher:
    """
    Inference dispatcher: dynamic model selection based on task difficulty.
    """
    def __init__(self, models: List[ModelProfile] = None):
        self.models: Dict[int, ModelProfile] = {}
        if models:
            for m in models:
                self.models[m.level] = m
        else:
            
            self.models[1] = ModelProfile(
                name="default", base_url="", api_key="", provider="local", level=1
            )

    def register(self, profile: ModelProfile) -> None:
        """Register a model profile at its level."""
        self.models[profile.level] = profile

    def select(self, level: int) -> ModelProfile:
        """Select model at specified level; fall back to lower if unavailable."""
        for lv in range(level, 0, -1):
            if lv in self.models:
                return self.models[lv]
        return self.models.get(1, ModelProfile("fallback", "", "", "local", 1))

    async def chat_completion(
        self,
        messages: List[Dict],
        model: ModelProfile,
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
        temperature: float = 0.7,
    ) -> Any:
        """
        Call upstream LLM chat.completions interface.
        Returns dict (non-stream) or async generator (stream).
        """
        import aiohttp

        headers = {"Content-Type": "application/json"}
        if model.api_key:
            headers["Authorization"] = f"Bearer {model.api_key}"

        payload = {
            "model": model.name,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        url = model.base_url.rstrip("/") + "/chat/completions"

        session = aiohttp.ClientSession()
        if stream:
            return self._stream(session, url, payload, headers)

        try:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=model.timeout)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"LLM error {resp.status} at {url}: {text[:500]}")
                return await resp.json()
        finally:
            await session.close()

    async def _stream(self, session, url: str, payload: Dict, headers: Dict):
        """SSE streaming generator."""
        import aiohttp
        try:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=120)) as resp:
                async for line in resp.content:
                    line = line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            yield chunk
                        except json.JSONDecodeError:
                            continue
        finally:
            await session.close()
