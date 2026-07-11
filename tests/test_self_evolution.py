"""Tests for minxg.self_evolution closed loop."""
import math
import pytest
from minxg.driver import (
    State, DriverEngine, Operator, arithmetic_field, parametric_field,
)
from minxg.contracts.registry import Registry
from minxg.contracts.cell import CellMeta
from minxg.self_evolution import (
    FailureTour, FieldForge, TwinEngine, EvolutionLoop, LoopConfig,
)


class StormyField(Operator):
    name = "stormy"

    def apply(self, state: State) -> State:
        out = state.clone()
        for k in list(out.payload):
            out.payload[k] = out.payload[k] + 1e6
        return out


class CalmerField(Operator):
    name = "calmer"

    def apply(self, state: State) -> State:
        out = state.clone()
        for k in list(out.payload):
            out.payload[k] = out.payload[k] + 0.5
        return out


def test_failure_tour_detects_nan_and_huge():
    tour = FailureTour()
    detected = tour.detect_from_state(
        step=1,
        payload={"x": float("nan")},
        caused_by="stormy",
    )
    assert detected is not None
    assert "stormy" in tour.by_op()


def test_failure_tour_no_false_positive_on_normal_state():
    tour = FailureTour()
    assert tour.detect_from_state(step=1, payload={"x": 1.5}) is None


def test_twin_engine_rejects_worse_candidate():
    engine = DriverEngine([StormyField()])
    twin = TwinEngine(n_steps=4)
    calmer = CalmerField()
    outcome = twin.compare(
        engine,
        calmer,
        target_idx=0,
        probe=State(payload={"x": 0.0}),
    )
    assert outcome.accepted
    assert outcome.candidate_drift < outcome.baseline_drift


def test_twin_engine_accepts_worse_when_candidate_worse():
    stormy = StormyField()
    engine = DriverEngine([CalmerField()])
    twin = TwinEngine(n_steps=4)
    outcome = twin.compare(
        engine,
        stormy,
        target_idx=0,
        probe=State(payload={"x": 0.0}),
    )
    assert not outcome.accepted


class _DummyCell(metaclass=CellMeta):
    cell_id = "self_evolution.dummy"
    cell_version = "0.17.1"

    def apply(self, state):
        out = state.clone()
        out.payload["x"] = out.payload.get("x", 0.0) - 0.1
        return out


def test_field_forge_finds_at_least_one_proposal():
    reg = Registry()
    reg.register(_DummyCell())
    forge = FieldForge(registry=reg)
    proposals = forge.propose(
        failures_by_op={"stormy": 3},
        probe_state=State(payload={"x": 0.0}),
        n_probe_steps=2,
    )
    assert proposals


def test_evolution_loop_replaces_stormy_with_calmer():
    reg = Registry()
    reg.register(_DummyCell())
    storm_engine = DriverEngine([StormyField()], step_size=0.5)

    for _ in range(3):
        storm_engine.step(State(payload={"x": 0.0}))

    tour = FailureTour()
    for s in range(1, 4):
        tour.detect_from_state(
            step=s,
            payload={"x": float("nan")},
            caused_by="stormy",
        )

    loop = EvolutionLoop(
        live_engine=storm_engine,
        tour=tour,
        forge=FieldForge(registry=reg),
        twin=TwinEngine(n_steps=2),
    )
    config = LoopConfig(probe_state=State(payload={"x": 0.0}), n_steps=2, tolerance=0.0)
    record = loop.cycle(config)
    assert record.failures_seen == 3
    names = [op.name for op in storm_engine.operators()]
    assert "stormy" not in names
