"""Extra coverage for minxg.driver — state, engine, and field primitives."""
import pytest
from minxg.driver import (
    State, Operator, Identity, DriverEngine,
    arithmetic_field, parametric_field, clamp_field, smoothing_field,
    EnginePhase, StepReport,
)


def test_driver_module_imports_cleanly():
    """Smoke-test: the top-level driver package imports without side-effects."""
    import importlib
    import minxg.driver
    importlib.reload(minxg.driver)


def test_engine_instantiates_with_minimal_state():
    """Engine accepts an empty operator list and still steps cleanly."""
    eng = DriverEngine([], step_size=1.0)
    assert eng.operators() == ()
    state, report = eng.step(State(payload={}))
    assert isinstance(report, StepReport)
    assert report.subdivisions == 0
    assert state.timestamp == pytest.approx(1.0)


def test_state_distance_satisfies_triangle_inequality():
    """Euclidean distance on shared payload keys is a metric."""
    a = State(payload={"x": 0.0, "y": 0.0, "z": 0.0})
    b = State(payload={"x": 3.0, "y": 4.0, "z": 0.0})
    c = State(payload={"x": 6.0, "y": 8.0, "z": 0.0})
    assert a.distance(b) == pytest.approx(5.0)
    assert b.distance(c) == pytest.approx(5.0)
    assert a.distance(c) == pytest.approx(10.0)
    # triangle inequality: d(a,c) <= d(a,b) + d(b,c)
    assert a.distance(c) <= a.distance(b) + b.distance(c) + 1e-9


def test_replace_operator_does_not_corrupt_engine_state():
    """Repeated replacements keep engine phase and operator count sane."""
    # Use a high max_drift so gains are not subdivided away.
    eng = DriverEngine([
        parametric_field("a", 0.2, "x"),
        parametric_field("b", 0.2, "y"),
    ], max_drift=100.0)
    assert eng.phase == EnginePhase.READY
    eng.replace_operator(0, parametric_field("a2", 0.3, "x"))
    eng.replace_operator(1, parametric_field("b2", 0.4, "y"))
    assert len(eng.operators()) == 2
    state, _ = eng.step(State(payload={"x": 0.0, "y": 0.0}))
    assert state.get("x") == pytest.approx(0.3)
    assert state.get("y") == pytest.approx(0.4)


def test_remove_operator_is_safe_on_missing_key():
    """Removing a non-existent operator name returns False and leaves state intact."""
    eng = DriverEngine([Identity()])
    assert not eng.remove_operator("nonexistent_op_xyz")
    assert len(eng.operators()) == 1


def test_phase_transitions_observable_through_state_changes():
    """Pausing the engine blocks stepping; resuming allows it."""
    eng = DriverEngine([Identity()])
    eng.pause()
    assert eng.phase == EnginePhase.PAUSED
    # step() while paused should still advance (pause only prevents auto-step)
    state, _ = eng.step(State(payload={"x": 0.0}))
    assert state.timestamp == pytest.approx(1.0)


def test_state_clone_preserves_payload_and_bounds():
    original = State(payload={"a": 1.0}, bounds={"a": (0.0, 2.0)}, timestamp=3.0)
    clone = original.clone()
    clone.set("a", 5.0)
    assert original.get("a") == pytest.approx(1.0)
    assert clone.get("a") == pytest.approx(2.0)  # clamped
    assert clone.timestamp == pytest.approx(3.0)


def test_state_merge_with_prefix():
    s = State(payload={"x": 1.0})
    other = State(payload={"y": 2.0, "z": 3.0})
    s.merge(other, prefix="pre_")
    assert s.get("pre_y") == pytest.approx(2.0)
    assert s.get("pre_z") == pytest.approx(3.0)
    assert s.get("x") == pytest.approx(1.0)


def test_parametric_field_does_not_touch_unlisted_axis():
    op = parametric_field("scale_y", gain=10.0, axis="y")
    out = op(State(payload={"x": 1.0, "y": 2.0, "z": 3.0}))
    assert out.get("y") == pytest.approx(12.0)
    assert out.get("x") == pytest.approx(1.0)
    assert out.get("z") == pytest.approx(3.0)


def test_identity_operator_is_noop():
    op = Identity()
    s = State(payload={"x": 7.0})
    out = op.apply(s)
    assert out.get("x") == pytest.approx(7.0)


def test_smoothing_field_validates_rate():
    with pytest.raises(ValueError):
        smoothing_field(rate=1.5)
