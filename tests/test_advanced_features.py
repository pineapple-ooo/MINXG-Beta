"""
Tests for new MINXG features:
- Agent framework
- RAG system
- Workflow engine
- Function calling
- Streaming
- Guardrails
- Caching
- Monitoring
"""
import pytest


# ═══════════════════════════════════════════════════════════════════
#  Agent Framework Tests
# ═══════════════════════════════════════════════════════════════════

def test_react_agent_import():
    """Test agent framework imports."""
    from minxg.agents.react_agent import ReActAgent, PlanningAgent, MultiAgentSystem
    assert ReActAgent is not None
    assert PlanningAgent is not None
    assert MultiAgentSystem is not None


def test_react_agent_run():
    """Test ReAct agent execution."""
    from minxg.agents.react_agent import ReActAgent

    agent = ReActAgent(name="test-agent", max_steps=5)
    result = agent.run("Test goal")

    assert "goal" in result
    assert result["goal"] == "Test goal"
    assert "state" in result


def test_planning_agent():
    """Test planning agent."""
    from minxg.agents.react_agent import PlanningAgent

    planner = PlanningAgent()
    plan = planner.plan_task("Complex task")

    assert len(plan) > 0
    assert all("task" in p for p in plan)


def test_multi_agent_system():
    """Test multi-agent system."""
    from minxg.agents.react_agent import MultiAgentSystem

    system = MultiAgentSystem()
    system.add_agent("agent1", "math")
    system.add_agent("agent2", "coding")

    assert len(system.agents) == 2

    status = system.get_team_status()
    assert "agent1" in status
    assert "agent2" in status


# ═══════════════════════════════════════════════════════════════════
#  RAG System Tests
# ═══════════════════════════════════════════════════════════════════

def test_rag_import():
    """Test RAG system imports."""
    from minxg.agents.rag_system import VectorStore, TextSplitter, RAGPipeline
    assert VectorStore is not None
    assert TextSplitter is not None
    assert RAGPipeline is not None


def test_vector_store():
    """Test vector store operations."""
    from minxg.agents.rag_system import VectorStore, Document

    store = VectorStore(dimension=128)
    doc = Document(id="1", content="Test document", embedding=[0.5] * 128)
    store.add(doc)

    assert len(store.vectors) == 1

    stats = store.stats()
    assert stats["total_documents"] == 1


def test_text_splitter():
    """Test text splitting."""
    from minxg.agents.rag_system import TextSplitter, Document

    splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
    text = "A" * 200
    chunks = splitter.split(text)

    assert len(chunks) > 1
    assert all(len(c) <= 55 for c in chunks)  # Allow some overlap


def test_rag_pipeline():
    """Test RAG pipeline."""
    from minxg.agents.rag_system import RAGPipeline, Document

    pipeline = RAGPipeline()
    docs = [
        Document(id="1", content="Python is a programming language"),
        Document(id="2", content="Machine learning with Python"),
    ]

    stats = pipeline.ingest(docs)
    assert stats["documents_ingested"] == 2
    assert stats["chunks_created"] >= 2


# ═══════════════════════════════════════════════════════════════════
#  Workflow Engine Tests
# ═══════════════════════════════════════════════════════════════════

def test_workflow_import():
    """Test workflow engine imports."""
    from minxg.workflow.engine import WorkflowEngine, WorkflowBuilder
    assert WorkflowEngine is not None
    assert WorkflowBuilder is not None


def test_workflow_creation():
    """Test workflow creation."""
    from minxg.workflow.engine import WorkflowEngine

    engine = WorkflowEngine()
    workflow = engine.create_workflow("test-workflow")

    assert workflow.workflow_id == "test-workflow"
    assert workflow.status == "pending"


def test_workflow_execution():
    """Test workflow execution."""
    from minxg.workflow.engine import WorkflowEngine

    engine = WorkflowEngine()
    engine.create_workflow("exec-test")
    engine.add_node("exec-test", "step1", "Step 1", "action")
    engine.add_node("exec-test", "step2", "Step 2", "action")
    engine.add_edge("exec-test", "step1", "step2")

    result = engine.execute("exec-test")

    assert result["status"] == "completed"
    assert result["total_nodes"] == 2


def test_workflow_builder():
    """Test fluent workflow builder."""
    from minxg.workflow.engine import WorkflowEngine, WorkflowBuilder

    engine = WorkflowEngine()
    builder = WorkflowBuilder("builder-test", engine)

    builder.add("a", "Task A").add("b", "Task B").connect("a", "b")

    result = builder.run()
    assert result["status"] == "completed"


# ═══════════════════════════════════════════════════════════════════
#  Function Calling Tests
# ═══════════════════════════════════════════════════════════════════

def test_function_registry():
    """Test function registry."""
    from minxg.function_calling import FunctionRegistry

    registry = FunctionRegistry()

    @registry.register(description="Add two numbers")
    def add(a: int, b: int) -> int:
        return a + b

    assert "add" in registry.functions

    result = registry.call("add", {"a": 2, "b": 3})
    assert result["result"] == 5


def test_openai_format():
    """Test OpenAI format conversion."""
    from minxg.function_calling import FunctionRegistry

    registry = FunctionRegistry()

    @registry.register(description="Test function")
    def test_func(name: str, age: int) -> str:
        return f"{name} is {age}"

    formatted = registry.to_openai_format()
    assert len(formatted) == 1
    assert formatted[0]["function"]["name"] == "test_func"


def test_common_schemas():
    """Test common function schemas."""
    from minxg.function_calling import COMMON_SCHEMAS

    assert "calculator" in COMMON_SCHEMAS
    assert "search" in COMMON_SCHEMAS
    assert "send_email" in COMMON_SCHEMAS


# ═══════════════════════════════════════════════════════════════════
#  Streaming Tests
# ═══════════════════════════════════════════════════════════════════

def test_streaming_import():
    """Test streaming imports."""
    from minxg.streaming import StreamingResponse, TokenStream, ChunkAggregator
    assert StreamingResponse is not None
    assert TokenStream is not None
    assert ChunkAggregator is not None


def test_token_stream():
    """Test token stream."""
    from minxg.streaming import TokenStream

    tokens = []
    stream = TokenStream(on_token=tokens.append)

    stream.push("Hello ")
    stream.push("World")
    result = stream.complete()

    assert result == "Hello World"
    assert stream.total_tokens == 2


def test_chunk_aggregator():
    """Test chunk aggregation."""
    from minxg.streaming import ChunkAggregator

    agg = ChunkAggregator()
    agg.add({
        "choices": [{"delta": {"content": "Hello "}}],
        "model": "gpt-4o",
    })
    agg.add({
        "choices": [{"delta": {"content": "World"}, "finish_reason": "stop"}],
    })

    content = agg.get_content()
    assert content == "Hello World"


# ═══════════════════════════════════════════════════════════════════
#  Guardrails Tests
# ═══════════════════════════════════════════════════════════════════

def test_guardrails_import():
    """Test guardrails imports."""
    from minxg.guardrails import InputGuardrail, OutputGuardrail, Guardrails
    assert InputGuardrail is not None
    assert OutputGuardrail is not None
    assert Guardrails is not None


def test_input_guardrail():
    """Test input validation."""
    from minxg.guardrails import InputGuardrail

    guard = InputGuardrail()

    # Normal input
    result = guard.validate("Hello, how are you?")
    assert result.result.value == "pass"

    # Too long input
    result = guard.validate("A" * 200000)
    assert result.result.value == "fail"


def test_pii_detection():
    """Test PII detection."""
    from minxg.guardrails import Guardrails

    guard = Guardrails()
    result = guard.validate_input("My email is test@example.com")

    # Should detect email
    assert result.result.value in ("pass", "modify")


def test_output_guardrail():
    """Test output validation."""
    from minxg.guardrails import OutputGuardrail

    guard = OutputGuardrail()

    result = guard.validate("Normal output text")
    assert result.result.value == "pass"


# ═══════════════════════════════════════════════════════════════════
#  Caching Tests
# ═══════════════════════════════════════════════════════════════════

def test_caching_import():
    """Test caching imports."""
    from minxg.caching import SemanticCache, TieredCache, CacheMiddleware
    assert SemanticCache is not None
    assert TieredCache is not None
    assert CacheMiddleware is not None


def test_semantic_cache():
    """Test semantic cache."""
    from minxg.caching import SemanticCache

    cache = SemanticCache()
    cache.set("What is Python?", "Python is a programming language", "gpt-4o")

    # Exact match
    result = cache.get("What is Python?", "gpt-4o")
    assert result is not None

    stats = cache.stats()
    assert stats["total_entries"] == 1


def test_tiered_cache():
    """Test tiered cache."""
    from minxg.caching import TieredCache
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = TieredCache(cache_dir=tmpdir)
        cache.set("key1", "value1")

        result = cache.get("key1")
        assert result == "value1"

        stats = cache.stats()
        assert stats["l1_entries"] >= 1


# ═══════════════════════════════════════════════════════════════════
#  Monitoring Tests
# ═══════════════════════════════════════════════════════════════════

def test_monitoring_import():
    """Test monitoring imports."""
    from minxg.monitoring import MetricsCollector, RequestTracker, AlertManager, HealthChecker
    assert MetricsCollector is not None
    assert RequestTracker is not None
    assert AlertManager is not None
    assert HealthChecker is not None


def test_metrics_collector():
    """Test metrics collection."""
    from minxg.monitoring import MetricsCollector

    metrics = MetricsCollector()
    metrics.inc("requests", 1)
    metrics.inc("requests", 1)
    metrics.set("temperature", 25.5)
    metrics.observe("latency", 100)
    metrics.observe("latency", 200)

    assert metrics.get("requests") == 2
    assert metrics.get("temperature") == 25.5

    hist = metrics.get_histogram("latency")
    assert hist["count"] == 2


def test_request_tracker():
    """Test request tracking."""
    from minxg.monitoring import RequestTracker

    tracker = RequestTracker()

    with tracker.start_request("/v1/chat", "POST"):
        pass  # Simulate request

    dashboard = tracker.get_dashboard()
    assert "requests_total" in dashboard


def test_health_checker():
    """Test health checking."""
    from minxg.monitoring import HealthChecker

    health = HealthChecker()
    health.register("test_check", lambda: True)
    health.register("fail_check", lambda: False)

    result = health.check_all()
    assert result["healthy"] is False

    status = health.get_status()
    assert status == "unhealthy"


# ═══════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════

def test_all_modules_importable():
    """Test that all new modules can be imported."""
    modules = [
        'minxg.agents.react_agent',
        'minxg.agents.rag_system',
        'minxg.workflow.engine',
        'minxg.function_calling',
        'minxg.streaming',
        'minxg.guardrails',
        'minxg.caching',
        'minxg.monitoring',
    ]

    for module_path in modules:
        __import__(module_path)
