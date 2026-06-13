"""Centralized config: minxg.yaml is the source of truth.""""
import pytest
import minxg
from minxg.operators import OPERATOR_REGISTRY


def test_config_loads():
    assert minxg.CONFIG is not None
    assert minxg.get("project.name") == "minxg"
    assert minxg.get("project.version")


def test_config_pillar_count():
    pillars = minxg.get("pillars", [])
    assert len(pillars) == 6


def test_config_operator_total_matches_registry():
    config_total = minxg.get("operators.total")
    assert config_total == OPERATOR_REGISTRY.total_operators


def test_config_dot_path():
    assert minxg.get("acceleration.c_core.functions") == 11
    assert minxg.get("operators.categories.ga.count") == 47


def test_config_default_on_missing_key():
    assert minxg.get("nonexistent.key", "default") == "default"
    assert minxg.get("nonexistent.key") is None
