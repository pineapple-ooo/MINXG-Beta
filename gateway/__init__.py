"""gateway package — OpenAI-compatible AI Agent Gateway v1.0.0

Public surface (stable, import-safe):

    GatewayServer   gateway.server       the FastAPI/aiohttp-shaped server
    GatewayConfig   gateway.config       structured config (single source of truth)
    start_gateway   gateway.server       convenience factory
    run_gateway     gateway.runner       CLI entry point

Internals exposed for tests/extensions::

    WorkerRouter        gateway.router
    HybridRAG           gateway.rag
    InferenceDispatcher gateway.inference
    StructuredWorkspace gateway.workspace
"""
from gateway.config import (
    GatewayConfig,
    GatewayBinding,
    AIConfig,
    WorkerURL,
    ChannelConfig,
)
from gateway.runner import run_gateway
from gateway.server import GatewayServer, start_gateway

__all__ = [
    "GatewayConfig",
    "GatewayBinding",
    "AIConfig",
    "WorkerURL",
    "ChannelConfig",
    "GatewayServer",
    "start_gateway",
    "run_gateway",
]
