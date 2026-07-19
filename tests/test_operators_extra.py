"""Extra coverage for minxg operator registry and pillar operator modules."""
import minxg
import minxg.ga
import minxg.cat
import minxg.chaos
import minxg.topo
import minxg.fiber
import minxg.infogeo

from minxg.operators import OPERATOR_REGISTRY, Operator
from minxg.ga.operators_ga import register_ga_operators
from minxg.cat.operators_cat import register_cat_operators
from minxg.chaos.operators_chaos import register_chaos_operators
from minxg.topo.operators_topo import register_topo_operators
from minxg.fiber.operators_fiber import register_fiber_operators
from minxg.infogeo.operators_ig import register_ig_operators


def test_operator_worker_registers_all_six_pillar_sets():
    """After importing and registering pillars, all 6 pillar categories exist."""
    expected_pillars = {"ga", "cat", "chaos", "topo", "fiber", "infogeo"}
    summary = OPERATOR_REGISTRY.category_summary()
    assert expected_pillars.issubset(set(summary.keys()))


def test_total_operator_count_at_least_three_hundred():
    assert OPERATOR_REGISTRY.total_operators >= 300


def test_lookup_by_name_returns_callable():
    names = ["add", "upper", "ga_outer", "cat_id_number",
             "chaos_logistic", "topo_make_simplex", "fiber_vector_bundle",
             "ig_bernoulli"]
    for name in names:
        op = OPERATOR_REGISTRY.get_by_name(name)
        assert op is not None, f"operator {name!r} missing from registry"
        assert callable(op.fn), f"operator {name!r} fn is not callable"


def test_legacy_operators_still_present():
    legacy_names = ["add", "sub", "mul", "upper", "strip", "list_len",
                    "and", "or", "file_read", "date_now"]
    summary = OPERATOR_REGISTRY.category_summary()
    # legacy categories should still have entries
    assert summary.get("math", 0) > 0
    assert summary.get("text", 0) > 0
    assert summary.get("data", 0) > 0
    assert summary.get("logic", 0) > 0
    assert summary.get("system", 0) > 0
    for name in legacy_names:
        assert OPERATOR_REGISTRY.get_by_name(name) is not None, name


def test_idempotent_registration_does_not_duplicate():
    initial = OPERATOR_REGISTRY.total_operators
    register_ga_operators()
    register_cat_operators()
    register_chaos_operators()
    register_topo_operators()
    register_fiber_operators()
    register_ig_operators()
    assert OPERATOR_REGISTRY.total_operators == initial


def test_same_operator_id_does_not_duplicate():
    """Directly re-registering an Operator with an existing id is a no-op."""
    existing = OPERATOR_REGISTRY.get_by_name("add")
    assert existing is not None
    duplicate = Operator(
        op_id=existing.op_id,
        name="add_dup",
        category="math",
        description="dup",
        input_types=existing.input_types,
        output_type=existing.output_type,
        is_pure=existing.is_pure,
        fn=existing.fn,
    )
    count_before = OPERATOR_REGISTRY.total_operators
    OPERATOR_REGISTRY.register(duplicate)
    assert OPERATOR_REGISTRY.total_operators == count_before
    # original name unchanged
    assert OPERATOR_REGISTRY.get_by_name("add").name == "add"
