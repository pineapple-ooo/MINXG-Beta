"""Tests for minxg.driver (Temporal Operator-Field driver engine)."""
import pytest
from minxg.driver import (
    State, Operator, Identity, DriverEngine,
    arithmetic_field, parametric_field, smoothing_field, clamp_field,
    EnginePhase,
)


def test_state_bounds_clamps():
    s = State(payload={"x": 5.0}, bounds={"x": (-1.0, 1.0)})
    s.set("x", 10.0)
    assert s.get("x") == 1.0
    s.set("x", -5.0)
    assert s.get("x") == -1.0


def test_state_distance_is_metric():
    a = State(payload={"x": 0.0, "y": 0.0})
    b = State(payload={"x": 3.0, "y": 4.0})
    assert a.distance(b) == pytest.approx(5.0)


def test_engine_advances_timestamp():
    eng = DriverEngine([Identity()], step_size=0.5)
    state, report = eng.step(State(payload={"x": 0.0}))
    assert state.timestamp == pytest.approx(0.5)
    assert report.subdivisions == 0
    assert eng.phase == EnginePhase.READY


def test_arithmetic_field_is_composable():
    eng = DriverEngine([
        arithmetic_field(lambda s: {"x": 1.0}, name="push_x"),
        smoothing_field(rate=0.5),
    ])
    end, _ = eng.run(State(payload={"x": 0.0}), n_steps=4)
    assert end.get("x") < 4.0
    assert end.get("x") > 0.0


def test_parametric_field_only_touches_listed_axis():
    op = parametric_field("axis_y", gain=2.5, axis="y")
    out = op(State(payload={"x": 0.0, "y": 1.0}))
    assert out.get("y") != 1.0
    assert out.get("x") == 0.0


def test_clamp_field_normalises_explosions():
    op = clamp_field(-1.0, 1.0)
    out = op(State(payload={"x": 1e9, "y": -1e9}))
    assert out.get("x") == 1.0
    assert out.get("y") == -1.0


def test_replace_operator_does_not_corrupt_engine():
    eng = DriverEngine([parametric_field("a", 0.5, "x"),
                        parametric_field("b", 0.5, "x")])
    state_before, _ = eng.step(State(payload={"x": 1.0}))
    eng.replace_operator(0, parametric_field("new_a", 0.1, "x"))
    state_after, _ = eng.step(state_before)
    assert state_after.get("x") > state_before.get("x")


def test_remove_operator_is_safe():
    eng = DriverEngine([parametric_field("a", 1.0, "x"),
                        parametric_field("b", 1.0, "y")])
    assert eng.remove_operator("b")
    assert not eng.remove_operator("missing")


def test_phase_transitions_observable():
    seen = []
    eng = DriverEngine([Identity()])
    eng.on_phase(lambda a, b: seen.append((a, b)))
    eng.pause()
    eng.step(State(payload={}))
    assert (EnginePhase.READY, EnginePhase.PAUSED) in seen or (EnginePhase.STEPPING, EnginePhase.PAUSED) in seen
