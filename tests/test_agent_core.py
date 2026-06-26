"""
test_agent_core.py — cover multiling/agent/*.py

Tests cover:
  - agent, capability, reflection, role, session modules import
  - ReflectionEngine returns string suggestions
  - Capability score_for / registry match
  - AgentRole (Role) has name/description fields
  - AgentSession (MultiAgentSession) tracks turns/messages
"""
from __future__ import annotations

import pytest

from multiling.agent import (
    Agent,
    AgentConfig,
    MultiAgentSession,
    AgentMessage,
    Role,
    RoleRegistry,
    Capability,
    CapabilityRegistry,
    ReflectionEngine,
)


class TestModuleImports:
    def test_agent_module_imports(self):
        assert all([
            Agent, AgentConfig, MultiAgentSession, AgentMessage,
            Role, RoleRegistry, Capability, CapabilityRegistry,
            ReflectionEngine,
        ])

    def test_agent_class_instantiable(self):
        cfg = AgentConfig(name="test")
        agent = Agent(cfg)
        assert agent.config.name == "test"

    def test_reflection_engine_instantiable(self):
        engine = ReflectionEngine()
        assert engine is not None

    def test_role_class_instantiable(self):
        role = Role(name="analyst", description="data expert")
        assert role.name == "analyst"

    def test_capability_class_instantiable(self):
        cap = Capability(name="python")
        assert cap.name == "python"

    def test_multi_agent_session_instantiable(self):
        session = MultiAgentSession()
        assert session is not None


class TestReflectionEngine:
    def test_observe_returns_reflection_with_string_fields(self):
        engine = ReflectionEngine(agent_name="tester")
        reflection = engine.observe("run_tool", "success: done", success=True)
        assert isinstance(reflection.analysis, str)
        assert isinstance(reflection.lesson, str)
        assert isinstance(reflection.improvement_plan, str)
        assert len(reflection.analysis) > 0

    def test_get_improvement_suggestions_returns_strings(self):
        engine = ReflectionEngine()
        # Empty history should still return a list with at least one string
        suggestions = engine.get_improvement_suggestions()
        assert isinstance(suggestions, list)
        assert all(isinstance(s, str) for s in suggestions)
        assert len(suggestions) >= 1

    def test_reflection_stats_returns_dict(self):
        engine = ReflectionEngine()
        stats = engine.get_reflection_stats()
        assert isinstance(stats, dict)
        assert "total" in stats

    def test_reset_clears_history(self):
        engine = ReflectionEngine()
        engine.observe("action", "result")
        engine.reset()
        assert len(engine.get_recent_reflections()) == 0


class TestCapability:
    def test_score_for_exact_name_match(self):
        cap = Capability(name="python", category="programming", level=5)
        score = cap.score_for("python")
        assert score > 0

    def test_score_for_category_match(self):
        cap = Capability(name="python", category="programming", level=5)
        score = cap.score_for("programming")
        assert score > 0

    def test_score_for_no_match(self):
        cap = Capability(name="python", category="programming")
        score = cap.score_for("totally-unrelated")
        assert score == 0.0

    def test_capability_registry_register_and_find(self):
        registry = CapabilityRegistry()
        cap = Capability(name="python", category="programming", level=3)
        registry.register(cap)
        found = registry.get("python")
        assert found is cap
        by_cat = registry.find_by_category("programming")
        assert len(by_cat) == 1
        assert by_cat[0].name == "python"

    def test_capability_registry_match(self):
        registry = CapabilityRegistry()
        registry.register(Capability(name="python", category="programming", level=5))
        registry.register(Capability(name="react", category="web", level=3))
        results = registry.match(["python", "web"], min_score=1.0)
        assert len(results) >= 1


class TestAgentRole:
    def test_role_has_name_and_description(self):
        role = Role(name="coder", description="writes clean code")
        assert role.name == "coder"
        assert role.description == "writes clean code"

    def test_role_to_system_prompt(self):
        role = Role(name="analyst", description="data expert", persona="Be precise.")
        prompt = role.to_system_prompt()
        assert "analyst" in prompt
        assert "data expert" in prompt

    def test_role_registry_defaults(self):
        registry = RoleRegistry()
        # Pre-seeded with templates in get_default_role_registry, but fresh one is empty
        assert len(registry.list_roles()) == 0
        registry.register(Role(name="tester"))
        assert len(registry.list_roles()) == 1

    def test_role_registry_alias(self):
        registry = RoleRegistry()
        role = Role(name="coder")
        registry.register(role, alias="dev")
        assert registry.get("coder") is role
        assert registry.get("dev") is role


class TestAgentSession:
    def test_session_tracks_messages(self):
        session = MultiAgentSession()
        agent = Agent(AgentConfig(name="alice"))
        session.register_agent(agent)
        msg = session.send_message(agent.id, "", "hello world")
        assert len(session._messages) == 1
        assert msg.content == "hello world"

    def test_session_broadcast_message(self):
        session = MultiAgentSession()
        alice = Agent(AgentConfig(name="alice"))
        bob = Agent(AgentConfig(name="bob"))
        session.register_agent(alice)
        session.register_agent(bob)
        session.send_message(alice.id, "", "broadcast")
        # bob should have received the broadcast plus a system join message
        assert len(bob.get_messages()) >= 1
        broadcast_msgs = [m for m in bob.get_messages() if "broadcast" in m.get("content", "")]
        assert len(broadcast_msgs) == 1

    def test_session_summary(self):
        session = MultiAgentSession(session_id="sess-1")
        summary = session.get_summary()
        assert summary["session_id"] == "sess-1"
        assert summary["agent_count"] == 0

    def test_session_reset(self):
        session = MultiAgentSession()
        agent = Agent(AgentConfig(name="alice"))
        session.register_agent(agent)
        session.send_message(agent.id, "", "hi")
        session.reset()
        assert session._round == 0
        assert len(session._messages) == 0
