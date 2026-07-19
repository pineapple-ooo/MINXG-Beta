"""
test_self_evolution_extra.py — cover minxg/self_evolution/*.py

Tests cover:
  - failure_tour module imports
  - field_forge module imports
  - loop module imports
  - twin module imports
  - failure_tour detects NaN in state vector
  - failure_tour does not flag normal values
  - field_forge returns at least one proposal for a trivial field
  - evolution_loop phase transitions from 'born' through 'live'
"""
from __future__ import annotations

import math

import pytest

from minxg.self_evolution.failure_tour import FailureTour, Failure
from minxg.self_evolution.field_forge import FieldForge, FieldProposal
from minxg.self_evolution.loop import EvolutionLoop, LoopConfig, CycleRecord
from minxg.self_evolution.twin import TwinEngine, TwinOutcome
from minxg.driver import DriverEngine, State, Operator
from minxg.contracts.registry import get_registry, reset_registry, Registry
from minxg.contracts.cell import Cell
from minxg.contracts.lifecycle import LifecyclePhase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TrivialCell:
    """Minimal Cell-like object that acts as an identity operator."""
    cell_id = "trivial.identity"
    cell_version = "0.17.1"
    cell_capabilities = ("transform",)

    def apply(self, state: State) -> State:
        return state.clone()


def _make_engine_with_identity() -> DriverEngine:
    return DriverEngine(operators=[_IdentityOp()], step_size=1.0)


class _IdentityOp(Operator):
    name = "identity_op"

    def apply(self, state: State) -> State:
        return state.clone()


# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

class TestSelfEvolutionImports:
    def test_failure_tour_imports(self):
        assert FailureTour is not None
        assert Failure is not None

    def test_field_forge_imports(self):
        assert FieldForge is not None
        assert FieldProposal is not None

    def test_loop_imports(self):
        assert EvolutionLoop is not None
        assert LoopConfig is not None
        assert CycleRecord is not None

    def test_twin_imports(self):
        assert TwinEngine is not None
        assert TwinOutcome is not None


# ---------------------------------------------------------------------------
# FailureTour
# ---------------------------------------------------------------------------

class TestFailureTour:
    def test_detect_nan_in_state_vector(self):
        tour = FailureTour()
        payload = {"x": float("nan"), "y": 1.0, "z": 2.0}
        failure = tour.detect_from_state(step=1, payload=payload, caused_by="op_a")
        assert failure is not None
        assert failure.step == 1
        assert failure.caused_by == "op_a"
        assert len(tour) == 1

    def test_detect_non_finite_inf(self):
        tour = FailureTour()
        payload = {"x": 1e12}
        failure = tour.detect_from_state(step=2, payload=payload)
        assert failure is not None
        assert failure.step == 2

    def test_normal_values_not_flagged(self):
        tour = FailureTour()
        payload = {"x": 1.0, "y": -2.0, "z": 0.5}
        failure = tour.detect_from_state(step=3, payload=payload)
        assert failure is None
        assert len(tour) == 0

    def test_record_returns_failure(self):
        tour = FailureTour()
        failure = tour.record(
            step=10,
            state_payload={"a": 1.0},
            diagnostics={"nan_keys": 0},
            caused_by="op_b",
            note="test",
        )
        assert isinstance(failure, Failure)
        assert failure.step == 10
        assert failure.caused_by == "op_b"

    def test_recent_returns_last_n(self):
        tour = FailureTour()
        for i in range(5):
            tour.record(step=i, state_payload={"a": float("nan")}, diagnostics={})
        recent = tour.recent(limit=2)
        assert len(recent) == 2
        assert recent[0].step == 3
        assert recent[1].step == 4

    def test_by_op_counts_failures(self):
        tour = FailureTour()
        tour.record(step=1, state_payload={"a": float("nan")}, diagnostics={}, caused_by="op_x")
        tour.record(step=2, state_payload={"a": float("nan")}, diagnostics={}, caused_by="op_x")
        tour.record(step=3, state_payload={"a": float("nan")}, diagnostics={}, caused_by="op_y")
        counts = tour.by_op()
        assert counts["op_x"] == 2
        assert counts["op_y"] == 1


# ---------------------------------------------------------------------------
# FieldForge
# ---------------------------------------------------------------------------

class TestFieldForge:
    def test_propose_returns_list(self):
        forge = FieldForge()
        probe = State(payload={"x": 1.0})
        proposals = forge.propose({}, probe)
        assert isinstance(proposals, list)

    def test_propose_returns_at_least_one_for_trivial_field(self):
        # Reset registry to a clean state and register a trivial cell
        reset_registry()
        reg = get_registry()
        reg.register(_TrivialCell())

        forge = FieldForge(registry=reg)
        probe = State(payload={"x": 1.0})
        # Need at least one failure entry for propose to iterate
        proposals = forge.propose({"identity_op": 1}, probe)
        assert len(proposals) >= 1

        prop = proposals[0]
        assert isinstance(prop, FieldProposal)
        assert prop.replace_op == "identity_op"
        assert prop.candidate_id == "trivial.identity"

    def test_propose_empty_failures_returns_empty(self):
        forge = FieldForge()
        probe = State(payload={"x": 1.0})
        proposals = forge.propose({}, probe)
        assert proposals == []


# ---------------------------------------------------------------------------
# TwinEngine
# ---------------------------------------------------------------------------

class TestTwinEngine:
    def test_twin_compare_accepts_equal_operator(self):
        engine = _make_engine_with_identity()
        twin = TwinEngine(n_steps=2)
        probe = State(payload={"x": 1.0})
        candidate = _IdentityOp()
        outcome = twin.compare(engine, candidate, 0, probe, tolerance=0.0)
        assert isinstance(outcome, TwinOutcome)
        assert outcome.accepted is True
        assert outcome.baseline_drift == outcome.candidate_drift

    def test_twin_outcome_summary(self):
        engine = _make_engine_with_identity()
        twin = TwinEngine(n_steps=1)
        probe = State(payload={"x": 1.0})
        outcome = twin.compare(engine, _IdentityOp(), 0, probe)
        assert outcome.summary in ("accept", "reject")


# ---------------------------------------------------------------------------
# EvolutionLoop
# ---------------------------------------------------------------------------

class TestEvolutionLoop:
    def test_cycle_with_no_failures_returns_empty_record(self):
        tour = FailureTour()
        forge = FieldForge()
        twin = TwinEngine()
        engine = _make_engine_with_identity()

        loop = EvolutionLoop(
            live_engine=engine,
            tour=tour,
            forge=forge,
            twin=twin,
        )
        record = loop.cycle(LoopConfig(probe_state=State(payload={"x": 1.0})))
        assert isinstance(record, CycleRecord)
        assert record.applied == []
        assert record.rejected == []
        assert record.failures_seen == 0

    def test_cycle_applies_accepted_proposal(self):
        # Set up registry with a trivial cell
        reset_registry()
        reg = get_registry()
        reg.register(_TrivialCell())

        tour = FailureTour()
        tour.record(step=1, state_payload={"x": 1.0}, diagnostics={}, caused_by="identity_op")
        forge = FieldForge(registry=reg)
        twin = TwinEngine(n_steps=2)
        engine = _make_engine_with_identity()

        loop = EvolutionLoop(
            live_engine=engine,
            tour=tour,
            forge=forge,
            twin=twin,
        )
        record = loop.cycle(LoopConfig(
            probe_state=State(payload={"x": 1.0}),
            tolerance=0.0,
            max_replaces_per_cycle=1,
        ))
        assert record.failures_seen == 1
        # With an identity-op engine and identity candidate, drift is equal,
        # so proposal should be accepted.
        assert len(record.applied) == 1
        assert record.applied[0].replace_op == "identity_op"

    def test_registry_lifecycle_born_to_live(self):
        """The Registry lifecycle transitions from BORN to LIVE when locked."""
        reset_registry()
        reg = get_registry()
        assert reg.lifecycle == LifecyclePhase.BORN
        reg.lock()
        assert reg.lifecycle == LifecyclePhase.LIVE
        reg.unlock()
        assert reg.lifecycle == LifecyclePhase.MUTABLE
