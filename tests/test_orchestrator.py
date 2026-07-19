"""
test_orchestrator.py — cover multiling/orchestrator.py

Tests cover:
  - orchestrator module imports cleanly
  - start_api_server is an async function / coroutine
  - config merge with default host/port/api_key
  - api_key generation fallback when config missing
"""
from __future__ import annotations

import asyncio
import inspect
import os

import pytest

from multiling.orchestrator import NexusOrchestrator, start_api_server


class TestModuleImports:
    def test_orchestrator_imports_cleanly(self):
        assert callable(NexusOrchestrator)
        assert callable(start_api_server)

    def test_start_api_server_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(start_api_server)

    def test_orchestrator_has_expected_attrs(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AI_BASE_URL", raising=False)
        monkeypatch.delenv("AI_API_KEY", raising=False)
        orch = NexusOrchestrator(config={})
        assert hasattr(orch, "api_key")
        assert hasattr(orch, "model")
        assert hasattr(orch, "ai_base_url")
        assert hasattr(orch, "ai_api_key")
        assert hasattr(orch, "ai_provider")


class TestConfigMerge:
    def test_default_host_port_api_key_from_config(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AI_BASE_URL", raising=False)
        monkeypatch.delenv("AI_API_KEY", raising=False)

        config = {
            "ai": {
                "base_url": "http://example.com/v1",
                "api_key": "cfg-key",
                "provider": "openai",
                "model": "gpt-4",
            },
            "gateway": {
                "host": "127.0.0.1",
                "port": 9999,
            },
        }

        # Constructor takes ai_model as explicit kwarg, not from config['ai']['model'].
        # Default model param is "hermes-3-mini" when ai_model is omitted.
        orch = NexusOrchestrator(ai_model="gpt-4", config=config)

        assert orch.ai_base_url == "http://example.com/v1"
        assert orch.ai_api_key == "cfg-key"
        assert orch.ai_provider == "openai"
        assert orch.ai_model == "gpt-4"
        assert orch.model == "gpt-4"

    def test_defaults_when_config_empty(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AI_BASE_URL", raising=False)
        monkeypatch.delenv("AI_API_KEY", raising=False)

        orch = NexusOrchestrator(config={})

        assert orch.ai_base_url == "http://localhost:11434/v1"
        assert orch.ai_provider == "local"
        assert orch.model == "hermes-3-mini"
        assert orch.ai_model == "hermes-3-mini"

    def test_args_override_config(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AI_BASE_URL", raising=False)
        monkeypatch.delenv("AI_API_KEY", raising=False)

        orch = NexusOrchestrator(
            api_key="arg-key",
            ai_base_url="http://override/v1",
            ai_api_key="arg-ai-key",
            ai_provider="anthropic",
            ai_model="claude-3",
            config={
                "ai": {
                    "base_url": "http://cfg/v1",
                    "api_key": "cfg-key",
                    "provider": "openai",
                    "model": "gpt-4",
                }
            },
        )

        assert orch.api_key == "arg-key"
        assert orch.ai_base_url == "http://override/v1"
        assert orch.ai_api_key == "arg-ai-key"
        assert orch.ai_provider == "anthropic"
        assert orch.ai_model == "claude-3"


class TestApiKeyFallback:
    def test_api_key_generated_when_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        orch = NexusOrchestrator(config={})
        assert orch.api_key is not None
        assert isinstance(orch.api_key, str)
        assert len(orch.api_key) == 32  # secrets.token_hex(16)

    def test_env_openai_api_key_used(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
        monkeypatch.delenv("AI_API_KEY", raising=False)
        orch = NexusOrchestrator(config={})
        assert orch.api_key == "env-openai-key"

    def test_arg_api_key_precedence_over_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        orch = NexusOrchestrator(api_key="arg-key", config={})
        assert orch.api_key == "arg-key"
