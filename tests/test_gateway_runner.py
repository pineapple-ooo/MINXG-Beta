"""
test_gateway_runner.py — cover gateway/*.py

Tests cover:
  - gateway module imports cleanly
  - runner module imports cleanly
  - inference module imports cleanly
  - router module imports cleanly
  - workspace module imports cleanly
  - can instantiate runner/server with minimal args (mock server)
"""
from __future__ import annotations

import asyncio
from unittest import mock

import pytest

import gateway
from gateway import inference, runner, router, workspace
from gateway.server import GatewayServer


class TestGatewayImports:
    def test_gateway_package_imports(self):
        assert gateway is not None
        assert hasattr(gateway, "run_gateway")
        assert hasattr(gateway, "GatewayServer")
        assert hasattr(gateway, "start_gateway")

    def test_runner_module_imports(self):
        assert hasattr(runner, "run_gateway")
        assert hasattr(runner, "main")

    def test_inference_module_imports(self):
        assert hasattr(inference, "InferenceDispatcher")
        assert hasattr(inference, "TaskGrader")
        assert hasattr(inference, "ModelProfile")

    def test_router_module_imports(self):
        assert hasattr(router, "WorkerRouter")
        assert hasattr(router, "WorkerRoute")

    def test_workspace_module_imports(self):
        assert hasattr(workspace, "StructuredWorkspace")
        assert hasattr(workspace, "WorkspaceSlot")


class TestGatewayServerInstantiation:
    def test_gateway_server_with_minimal_config(self):
        gw = GatewayServer(config={})
        assert gw.host == "0.0.0.0"
        assert gw.port == 18080
        assert gw.version == "0.16.0"

    def test_gateway_server_with_custom_config(self):
        gw = GatewayServer(config={
            "gateway": {"host": "127.0.0.1", "port": 9090},
            "ai": {"provider": "openai", "model": "gpt-4", "base_url": "https://api.test/v1", "api_key": "test"},
        })
        assert gw.host == "127.0.0.1"
        assert gw.port == 9090
        assert gw.ai_model == "gpt-4"
        assert gw.ai_base_url == "https://api.test/v1"

    def test_gateway_server_initialize_mocked(self):
        """GatewayServer can be instantiated and initialize() runs with mocks."""
        gw = GatewayServer(config={})
        assert gw.host == "0.0.0.0"
        assert gw.port == 18080
        assert gw.version == "0.16.0"

        # initialize() is async; mock heavy deps so it completes quickly
        with mock.patch("gateway.router.WorkerRouter") as MockRouter:
            with mock.patch("gateway.rag.HybridRAG") as MockRAG:
                with mock.patch("gateway.inference.InferenceDispatcher") as MockDisp:
                    mock_router = mock.MagicMock()
                    mock_router.routes = []
                    mock_router.fetch_tools = mock.AsyncMock(return_value=[])
                    MockRouter.return_value = mock_router
                    MockRAG.return_value = mock.MagicMock()
                    mock_disp = mock.MagicMock()
                    mock_disp.models = {}
                    MockDisp.return_value = mock_disp

                    result = gw.initialize()
                    if asyncio.iscoroutine(result):
                        try:
                            loop = asyncio.get_running_loop()
                            # We're already inside an event loop; create a task
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                                future = pool.submit(
                                    asyncio.run, result
                                )
                                future.result(timeout=10)
                        except RuntimeError:
                            asyncio.run(result)

        assert gw.router is mock_router
        assert gw.rag is not None
        assert gw.dispatcher is mock_disp

    def test_runner_run_gateway_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(runner.run_gateway)

    def test_workspace_slot_instantiation(self):
        slot = workspace.WorkspaceSlot("test", max_chars=100)
        assert slot.name == "test"
        assert slot.get() == ""

    def test_structured_workspace_instantiation(self):
        ws = workspace.StructuredWorkspace()
        assert "objective" in ws.slots
        assert ws.turn_count == 0


class TestTaskGrader:
    def test_grade_returns_int(self):
        assert isinstance(inference.TaskGrader.grade("hello"), int)

    def test_grade_range(self):
        level = inference.TaskGrader.grade("simple question")
        assert 1 <= level <= 3

    def test_grade_deep_keywords(self):
        level = inference.TaskGrader.grade("analyze and debug this code")
        assert level >= 2

    def test_grade_expert_keywords(self):
        level = inference.TaskGrader.grade("system-wide security audit")
        assert level >= 2


class TestWorkerRouter:
    def test_router_instantiation(self):
        r = router.WorkerRouter(py_url="http://127.0.0.1:19001")
        assert len(r.routes) >= 1
        assert r.routes[0].name == "py_workers"

    def test_router_legacy_routes(self):
        r = router.WorkerRouter(
            py_url="http://127.0.0.1:19001",
            enable_legacy=True,
            legacy_routes=[{"name": "cs_worker", "url": "http://127.0.0.1:19002", "lang": "csharp"}],
        )
        assert len(r.routes) == 2
        assert r.routes[1].name == "cs_worker"
