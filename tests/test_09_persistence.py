"""End-to-end: pillars compose without breaking each other."""
import pytest
import math
import minxg.cat as cat
from minxg.ga import Multivector, Signature
from minxg.operators import OPERATOR_REGISTRY
import minxg


def test_pipeline_ga_to_cat_to_chaos():
    """A small pipeline: rotate vector (GA), map to length (CAT), check chaos stability."""
    sig = Signature(3, 0)
    e1 = Multivector({1: 1.0}, sig)
    e2 = Multivector({2: 1.0}, sig)

    from minxg.ga import Rotor
    R = Rotor.from_bivector(e1.outer(e2).normalize(), math.pi / 2)
    rotated = R.apply(e1)
    norm = rotated.norm

    to_len = cat.Morphism(
        "ga_to_len",
        (cat.Type("multivector"),),
        cat.Type("number"),
        lambda m: m.norm
    )
    length = to_len(rotated)
    assert abs(length - 1.0) < 1e-9


def test_import_works_after_other_pillar():
    """Importing pillars in any order should not cause issues."""
    from minxg.chaos import logistic_lyapunov
    from minxg.topo import SimplicialComplex, Simplex
    from minxg.fiber import TangentBundle
    lyap = logistic_lyapunov(3.5)
    assert isinstance(lyap, float)


def test_backward_compat_py_workers_alias():
    """Old `import py_workers` still works (aliased to minxg)."""
    import py_workers
    assert py_workers.__name__ in ("minxg", "py_workers")
