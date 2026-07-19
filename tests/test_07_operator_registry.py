"""Operator Registry: all 376 operators correctly registered."""
import pytest
from minxg.operators import OPERATOR_REGISTRY
import minxg  
import minxg.ga, minxg.cat, minxg.infogeo, minxg.topo, minxg.chaos, minxg.fiber


def test_total_operator_count():
    assert OPERATOR_REGISTRY.total_operators == 376


def test_pillar_operator_counts():
    summary = OPERATOR_REGISTRY.category_summary()
    assert summary["ga"] == 47
    assert summary["cat"] == 79
    assert summary["infogeo"] == 51
    assert summary["topo"] == 53
    assert summary["chaos"] == 23
    assert summary["fiber"] == 53


def test_legacy_operators():
    summary = OPERATOR_REGISTRY.category_summary()
    assert summary["math"] == 20
    assert summary["text"] == 19
    assert summary["data"] == 12
    assert summary["logic"] == 13
    assert summary["system"] == 6


def test_id_ranges_respect_pillar_allocation():
    """Verify operator IDs fall in their declared ranges (PROJECT_INDEX §4)."""
    ranges = {
        "math": (0, 19),
        "text": (2000, 2018),
        "data": (3500, 3511),
        "cat": (4000, 4078),
        "ga": (5000, 5049),
        "logic": (5500, 5512),
        "fiber": (6000, 6052),
        "infogeo": (7000, 7050),
        "topo": (8000, 8052),
        "chaos": (8500, 8522),
        "system": (9000, 9005),
    }
    for op in OPERATOR_REGISTRY._by_id.values():
        lo, hi = ranges[op.category]
        assert lo <= op.op_id <= hi, (
            f"{op.name} id={op.op_id} outside {op.category} range [{lo}, {hi}]"
        )


def test_lookup_by_name_and_id_consistent():
    op_id = OPERATOR_REGISTRY.get_by_name("ga_outer")
    by_id = OPERATOR_REGISTRY.get_by_id(op_id.op_id)
    assert op_id is by_id


def test_idempotent_registration():
    """Re-registering a sub-package should not duplicate operators."""
    import minxg.ga as ga
    initial = OPERATOR_REGISTRY.total_operators
    from minxg.ga import operators_ga
    operators_ga.register_ga_operators()  
    assert OPERATOR_REGISTRY.total_operators == initial
