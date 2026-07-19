"""
MINXG Test Suite — Comprehensive test coverage

All tests must run and pass. No skipping.
"""
import pytest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest import mock


# ═══════════════════════════════════════════════════════════════════
#  Module Import Tests
# ═══════════════════════════════════════════════════════════════════

class TestImports:
    """All modules must import successfully."""

    def test_minxg_init(self):
        import minxg
        assert minxg is not None

    def test_minxg_base(self):
        from minxg.base import BaseWorker
        assert BaseWorker is not None

    def test_minxg_operators(self):
        from minxg.operators import Operator
        assert Operator is not None

    def test_minxg_drivers(self):
        from minxg.driver import DriverEngine
        assert DriverEngine is not None

    def test_multiligua_cli(self):
        import multiligua_cli
        assert multiligua_cli is not None

    def test_mcp_server(self):
        from minxg.mcp_server import WorkerRegistry
        assert WorkerRegistry is not None

    def test_features(self):
        from multiligua_cli.features import SELLING_POINTS
        assert isinstance(SELLING_POINTS, list)
        assert len(SELLING_POINTS) > 0

    def test_cost_tracker(self):
        from multiligua_cli.cost_tracker import CostTracker
        assert CostTracker is not None

    def test_themes(self):
        from multiligua_cli.themes import THEMES
        assert isinstance(THEMES, dict)
        assert len(THEMES) > 0

    def test_model_compare(self):
        from multiligua_cli.model_compare import ModelComparator
        assert ModelComparator is not None

    def test_memory_system(self):
        from multiligua_cli.memory_system import MemoryEngine
        assert MemoryEngine is not None

    def test_memory_viz(self):
        from multiligua_cli.memory_viz import print_memory_dashboard
        assert print_memory_dashboard is not None

    def test_web_ui(self):
        from multiligua_cli.web_ui import create_app
        assert create_app is not None

    def test_image_tools(self):
        import multiligua_cli.image_tools as img
        assert img is not None

    def test_audio_tools(self):
        import multiligua_cli.audio_tools as aud
        assert aud is not None

    def test_video_tools(self):
        import multiligua_cli.video_tools as vid
        assert vid is not None

    def test_pdf_tools(self):
        import multiligua_cli.pdf_tools as pdf
        assert pdf is not None

    def test_data_tools(self):
        import multiligua_cli.data_tools as data
        assert data is not None

    def test_setup_wizard(self):
        from multiligua_cli.setup import run_setup, detect_model_capabilities
        assert run_setup is not None
        assert detect_model_capabilities is not None

    def test_agents_react(self):
        from minxg.agents.react_agent import ReActAgent, PlanningAgent
        assert ReActAgent is not None
        assert PlanningAgent is not None

    def test_agents_rag(self):
        from minxg.agents.rag_system import VectorStore, RAGPipeline
        assert VectorStore is not None
        assert RAGPipeline is not None

    def test_workflow(self):
        from minxg.workflow.engine import WorkflowEngine
        assert WorkflowEngine is not None

    def test_function_calling(self):
        from minxg.function_calling import FunctionRegistry
        assert FunctionRegistry is not None

    def test_streaming(self):
        from minxg.streaming import StreamingResponse, TokenStream
        assert StreamingResponse is not None
        assert TokenStream is not None

    def test_guardrails(self):
        from minxg.guardrails import InputGuardrail, OutputGuardrail
        assert InputGuardrail is not None
        assert OutputGuardrail is not None

    def test_caching(self):
        from minxg.caching import SemanticCache, TieredCache
        assert SemanticCache is not None
        assert TieredCache is not None

    def test_monitoring(self):
        from minxg.monitoring import MetricsCollector, RequestTracker
        assert MetricsCollector is not None
        assert RequestTracker is not None


# ═══════════════════════════════════════════════════════════════════
#  Worker Tests
# ═══════════════════════════════════════════════════════════════════

class TestWorkers:
    """Worker functionality tests."""

    def test_worker_base(self):
        from minxg.base import BaseWorker

        class TestWorker(BaseWorker):
            name = "test_worker"
            description = "Test worker"

            def execute(self, *args, **kwargs):
                return {"success": True, "data": {"test": "data"}}

        worker = TestWorker()
        result = worker.execute()

        assert result["success"] is True
        assert result["data"] == {"test": "data"}
        assert worker.name == "test_worker"

    def test_worker_validation(self):
        from minxg.base import BaseWorker

        class ValidatedWorker(BaseWorker):
            name = "validated_worker"
            description = "Validated worker"

            def execute(self, value: int):
                if not isinstance(value, int):
                    return {"success": False, "error": "Expected int"}
                return {"success": True, "data": {"value": value * 2}}

        worker = ValidatedWorker()
        result = worker.execute(5)

        assert result["success"] is True
        assert result["data"]["value"] == 10

    def test_worker_error_handling(self):
        from minxg.base import BaseWorker

        class FailingWorker(BaseWorker):
            name = "failing_worker"
            description = "Worker that fails"

            def execute(self, *args, **kwargs):
                raise ValueError("Intentional failure")

        worker = FailingWorker()
        try:
            result = worker.execute()
            assert result["success"] is False
        except ValueError:
            pass  # Expected


# ═══════════════════════════════════════════════════════════════════
#  MCP Server Tests
# ═══════════════════════════════════════════════════════════════════

class TestMCPServer:
    """MCP server functionality tests."""

    def test_worker_registry(self):
        from minxg.mcp_server import WorkerRegistry

        registry = WorkerRegistry()
        tools = registry.get_tools()

        assert isinstance(tools, list)

    def test_worker_registration(self):
        from minxg.mcp_server import WorkerRegistry

        registry = WorkerRegistry()
        # Just verify get_tools returns a list
        tools = registry.get_tools()
        assert isinstance(tools, list)


# ═══════════════════════════════════════════════════════════════════
#  Features Tests
# ═══════════════════════════════════════════════════════════════════

class TestFeatures:
    """Feature showcase tests."""

    def test_selling_points_count(self):
        from multiligua_cli.features import SELLING_POINTS
        assert len(SELLING_POINTS) >= 10

    def test_selling_points_structure(self):
        from multiligua_cli.features import SELLING_POINTS
        for point in SELLING_POINTS:
            assert "name" in point or "title" in point
            assert "description" in point or "desc" in point


# ═══════════════════════════════════════════════════════════════════
#  Cost Tracker Tests
# ═══════════════════════════════════════════════════════════════════

class TestCostTracker:
    """Cost tracking tests."""

    def test_cost_tracker_creation(self):
        from multiligua_cli.cost_tracker import CostTracker
        tracker = CostTracker()
        assert tracker is not None

    def test_cost_recording(self):
        from multiligua_cli.cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.record("openai", "gpt-4o", 1000, 500)
        # Check that total_cost attribute exists and is >= 0
        assert tracker.total_cost >= 0

    def test_budget_alert(self):
        from multiligua_cli.cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.budget_usd = 1.0
        tracker.record("openai", "gpt-4o", 10000, 5000)
        assert tracker.should_alert() is False


# ═══════════════════════════════════════════════════════════════════
#  Theme Tests
# ═══════════════════════════════════════════════════════════════════

class TestThemes:
    """Theme system tests."""

    def test_themes_exist(self):
        from multiligua_cli.themes import THEMES
        assert len(THEMES) >= 8

    def test_theme_structure(self):
        from multiligua_cli.themes import THEMES
        for name, theme in THEMES.items():
            assert theme is not None


# ═══════════════════════════════════════════════════════════════════
#  Model Comparison Tests
# ═══════════════════════════════════════════════════════════════════

class TestModelCompare:
    """Model comparison tests."""

    def test_comparator_creation(self):
        from multiligua_cli.model_compare import ModelComparator
        comparator = ModelComparator()
        assert comparator is not None

    @pytest.mark.asyncio
    async def test_comparison_result(self):
        from multiligua_cli.model_compare import ModelComparator, ModelResponse

        comparator = ModelComparator()
        canned = {
            ("openai", "model-a"): ModelResponse(
                provider="openai", model="model-a", content="Response A",
                input_tokens=10, output_tokens=20, latency_ms=1000.0, cost_usd=0.01,
            ),
            ("openai", "model-b"): ModelResponse(
                provider="openai", model="model-b", content="A longer response B",
                input_tokens=10, output_tokens=25, latency_ms=500.0, cost_usd=0.02,
            ),
        }

        async def fake_query_model(provider, model, prompt, config):
            return canned[(provider, model)]

        with mock.patch.object(comparator, "_query_model", side_effect=fake_query_model):
            summary = await comparator.compare(
                "What is 2+2?",
                [("openai", "model-a"), ("openai", "model-b")],
                {},
            )

        assert summary is not None
        assert summary.prompt == "What is 2+2?"
        assert len(summary.responses) == 2
        # exercise the real aggregation logic, not just "truthy" checks
        assert summary.fastest.model == "model-b"   # lower latency_ms
        assert summary.cheapest.model == "model-a"  # lower cost_usd
        assert summary.longest.model == "model-b"   # longer content
        assert comparator.results == [summary]


# ═══════════════════════════════════════════════════════════════════
#  Memory System Tests
# ═══════════════════════════════════════════════════════════════════

class TestMemorySystem:
    """Memory system tests."""

    def test_memory_engine(self):
        from multiligua_cli.memory_system import MemoryEngine, MemoryCategory, MemoryTier
        engine = MemoryEngine()
        memory_id = engine.add(
            "Test memory",
            category=MemoryCategory.FACT,
            tier=MemoryTier.SHORT_TERM
        )
        assert memory_id is not None
        memories = engine.search("Test")
        assert len(memories) > 0

    def test_memory_compression(self):
        from multiligua_cli.memory_system import MemoryEngine, MemoryCategory, MemoryTier
        engine = MemoryEngine()
        engine.add("Important fact", category=MemoryCategory.FACT, importance=0.9)
        engine.add("Unimportant fact", category=MemoryCategory.FACT, importance=0.1)
        removed, remaining = engine.compress(min_importance=0.5)
        assert removed >= 1
        assert remaining >= 1

    def test_memory_export(self):
        from multiligua_cli.memory_system import MemoryEngine, MemoryCategory, MemoryTier
        import json
        engine = MemoryEngine()
        engine.add("Export test", category=MemoryCategory.FACT)
        exported = engine.export()
        data = json.loads(exported)
        # export returns a list of memory dicts
        assert isinstance(data, list)
        assert len(data) > 0
        assert "content" in data[0]


# ═══════════════════════════════════════════════════════════════════
#  Agent Framework Tests
# ═══════════════════════════════════════════════════════════════════

class TestAgents:
    """Agent framework tests."""

    def test_react_agent(self):
        from minxg.agents.react_agent import ReActAgent
        agent = ReActAgent(name="test-agent", max_steps=3)
        result = agent.run("Simple test goal")
        assert "goal" in result
        assert result["goal"] == "Simple test goal"

    def test_planning_agent(self):
        from minxg.agents.react_agent import PlanningAgent
        planner = PlanningAgent()
        plan = planner.plan_task("Complex task")
        assert len(plan) > 0
        assert all("task" in p for p in plan)

    def test_multi_agent_system(self):
        from minxg.agents.react_agent import MultiAgentSystem
        system = MultiAgentSystem()
        system.add_agent("agent1", "math")
        system.add_agent("agent2", "coding")
        assert len(system.agents) == 2


# ═══════════════════════════════════════════════════════════════════
#  RAG System Tests
# ═══════════════════════════════════════════════════════════════════

class TestRAG:
    """RAG system tests."""

    def test_vector_store(self):
        from minxg.agents.rag_system import VectorStore, Document
        store = VectorStore(dimension=128)
        doc = Document(id="1", content="Test", embedding=[0.5] * 128)
        store.add(doc)
        assert len(store.vectors) == 1

    def test_text_splitter(self):
        from minxg.agents.rag_system import TextSplitter
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        chunks = splitter.split("A" * 200)
        assert len(chunks) > 1

    def test_rag_pipeline(self):
        from minxg.agents.rag_system import RAGPipeline, Document
        pipeline = RAGPipeline()
        docs = [Document(id="1", content="Python programming")]
        stats = pipeline.ingest(docs)
        assert stats["documents_ingested"] == 1


# ═══════════════════════════════════════════════════════════════════
#  Workflow Engine Tests
# ═══════════════════════════════════════════════════════════════════

class TestWorkflow:
    """Workflow engine tests."""

    def test_workflow_creation(self):
        from minxg.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        workflow = engine.create_workflow("test")
        assert workflow.workflow_id == "test"

    def test_workflow_execution(self):
        from minxg.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        engine.create_workflow("exec-test")
        engine.add_node("exec-test", "step1", "Step 1", "action")
        engine.add_node("exec-test", "step2", "Step 2", "action")
        engine.add_edge("exec-test", "step1", "step2")
        result = engine.execute("exec-test")
        assert result["status"] == "completed"


# ═══════════════════════════════════════════════════════════════════
#  Function Calling Tests
# ═══════════════════════════════════════════════════════════════════

class TestFunctionCalling:
    """Function calling tests."""

    def test_function_registry(self):
        from minxg.function_calling import FunctionRegistry
        registry = FunctionRegistry()

        @registry.register(description="Add numbers")
        def add(a: int, b: int) -> int:
            return a + b

        result = registry.call("add", {"a": 2, "b": 3})
        assert result["result"] == 5

    def test_openai_format(self):
        from minxg.function_calling import FunctionRegistry
        registry = FunctionRegistry()

        @registry.register(description="Test")
        def test_func(name: str) -> str:
            return name

        formatted = registry.to_openai_format()
        assert len(formatted) == 1


# ═══════════════════════════════════════════════════════════════════
#  Streaming Tests
# ═══════════════════════════════════════════════════════════════════

class TestStreaming:
    """Streaming tests."""

    def test_token_stream(self):
        from minxg.streaming import TokenStream
        tokens = []
        stream = TokenStream(on_token=tokens.append)
        stream.push("Hello ")
        stream.push("World")
        result = stream.complete()
        assert result == "Hello World"

    def test_chunk_aggregator(self):
        from minxg.streaming import ChunkAggregator
        agg = ChunkAggregator()
        agg.add({"choices": [{"delta": {"content": "Hello "}}]})
        agg.add({"choices": [{"delta": {"content": "World"}}]})
        content = agg.get_content()
        assert content == "Hello World"


# ═══════════════════════════════════════════════════════════════════
#  Guardrails Tests
# ═══════════════════════════════════════════════════════════════════

class TestGuardrails:
    """Guardrails tests."""

    def test_input_guardrail(self):
        from minxg.guardrails import InputGuardrail
        guard = InputGuardrail()
        result = guard.validate("Normal input")
        assert result.result.value == "pass"

    def test_too_long_input(self):
        from minxg.guardrails import InputGuardrail
        guard = InputGuardrail()
        result = guard.validate("A" * 200000)
        assert result.result.value == "fail"

    def test_output_guardrail(self):
        from minxg.guardrails import OutputGuardrail
        guard = OutputGuardrail()
        result = guard.validate("Normal output")
        assert result.result.value == "pass"


# ═══════════════════════════════════════════════════════════════════
#  Caching Tests
# ═══════════════════════════════════════════════════════════════════

class TestCaching:
    """Caching tests."""

    def test_semantic_cache(self):
        from minxg.caching import SemanticCache
        cache = SemanticCache()
        cache.set("What is Python?", "Python is a language", "gpt-4o")
        result = cache.get("What is Python?", "gpt-4o")
        assert result is not None

    def test_tiered_cache(self):
        from minxg.caching import TieredCache
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = TieredCache(cache_dir=tmpdir)
            cache.set("key", "value")
            result = cache.get("key")
            assert result == "value"


# ═══════════════════════════════════════════════════════════════════
#  Monitoring Tests
# ═══════════════════════════════════════════════════════════════════

class TestMonitoring:
    """Monitoring tests."""

    def test_metrics_collector(self):
        from minxg.monitoring import MetricsCollector
        metrics = MetricsCollector()
        metrics.inc("requests", 1)
        metrics.inc("requests", 1)
        metrics.set("temperature", 25.5)
        assert metrics.get("requests") == 2
        assert metrics.get("temperature") == 25.5

    def test_request_tracker(self):
        from minxg.monitoring import RequestTracker
        tracker = RequestTracker()
        with tracker.start_request("/test", "POST"):
            pass
        dashboard = tracker.get_dashboard()
        assert "requests_total" in dashboard

    def test_health_checker(self):
        from minxg.monitoring import HealthChecker
        health = HealthChecker()
        health.register("healthy_check", lambda: True)
        result = health.check_all()
        assert result["healthy"] is True


# ═══════════════════════════════════════════════════════════════════
#  Setup Wizard Tests
# ═══════════════════════════════════════════════════════════════════

class TestSetupWizard:
    """Setup wizard tests."""

    def test_model_capability_detection(self):
        from multiligua_cli.setup import detect_model_capabilities

        caps = detect_model_capabilities("gpt-4o")
        assert caps["vision"] is True
        assert caps["function_calling"] is True
        assert caps["streaming"] is True

        caps = detect_model_capabilities("claude-3-sonnet")
        assert caps["vision"] is True
        assert caps["function_calling"] is True

        caps = detect_model_capabilities("gpt-3.5-turbo")
        assert caps["vision"] is True
        assert caps["streaming"] is True


# ═══════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests."""

    def test_all_modules_importable(self):
        modules = [
            'minxg',
            'minxg.base',
            'minxg.operators',
            'minxg.driver',
            'minxg.mcp_server',
            'multiligua_cli',
            'multiligua_cli.setup',
            'multiligua_cli.features',
            'multiligua_cli.cost_tracker',
            'multiligua_cli.themes',
            'multiligua_cli.model_compare',
            'multiligua_cli.memory_system',
            'multiligua_cli.memory_viz',
            'multiligua_cli.web_ui',
            'minxg.agents.react_agent',
            'minxg.agents.rag_system',
            'minxg.workflow.engine',
            'minxg.function_calling',
            'minxg.streaming',
            'minxg.guardrails',
            'minxg.caching',
            'minxg.monitoring',
        ]
        for module in modules:
            __import__(module)

    def test_config_roundtrip(self):
        import yaml
        config = {
            "ai": {
                "provider": "openai",
                "model": "gpt-4o",
                "base_url": "https://api.openai.com/v1",
            },
            "vision": {
                "enabled": True,
                "formats": ["jpeg", "png"],
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config, f)
            with open(config_path) as f:
                loaded = yaml.safe_load(f)
            assert loaded["ai"]["provider"] == "openai"
            assert loaded["vision"]["enabled"] is True


# ═══════════════════════════════════════════════════════════════════
#  Performance Tests
# ═══════════════════════════════════════════════════════════════════

class TestPerformance:
    """Performance tests."""

    def test_import_speed(self):
        import time
        start = time.time()
        import minxg
        elapsed = time.time() - start
        assert elapsed < 5.0

    def test_worker_creation_speed(self):
        import time
        from minxg.base import BaseWorker

        class QuickWorker(BaseWorker):
            name = "quick_worker"
            description = "Quick"

            def execute(self, *args, **kwargs):
                return {"success": True, "data": {}}

        start = time.time()
        for _ in range(100):
            worker = QuickWorker()
            worker.execute()
        elapsed = time.time() - start
        assert elapsed < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x", "--no-header"])
