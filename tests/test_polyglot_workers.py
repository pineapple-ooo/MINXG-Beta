"""tests/test_polyglot_workers.py — exercises the four polyglot workers.

The polyglot workers all share the same structural contract:

* Subclass of BaseWorker
* Tagged with ``worker_id`` and ``version``
* Multiple @tool methods
* All tool methods are async, accept primitives/typed-lists, and return
  a dict that always has the ``status`` key

These tests cover the structural contract without requiring the runtime
binary to be present (Julia/R/clingo/wasmtime). When the runtime IS
present the workers do real work; when it isn't, they return
``{"status": "disabled", "hint": …}``. Both outcomes are valid — verify
they conform to the schema, not which one fires.
"""

import pytest

import minxg  # top-level package must export all four workers
from minxg.base import BaseWorker, ToolDef
from minxg.five_pillars.polyglot import (
    JuliaWorker, RWorker, DatalogWorker, WasmWorker,
)


WORKERS = [
    (JuliaWorker, "julia_math", "0.17.0"),
    (RWorker, "r_stats", "0.17.0"),
    (DatalogWorker, "datalog_logic", "0.17.0"),
    (WasmWorker, "wasm_compute", "0.17.0"),
]


# ── 1. Import-level contract ─────────────────────────────────────────

@pytest.mark.parametrize("cls,worker_id,version", WORKERS)
def test_worker_class_is_baseworker(cls, worker_id, version):
    assert issubclass(cls, BaseWorker), f"{cls.__name__} must subclass BaseWorker"


@pytest.mark.parametrize("cls,worker_id,version", WORKERS)
def test_worker_class_attributes(cls, worker_id, version):
    assert cls.worker_id == worker_id
    assert cls.version == version


def test_workers_exported_at_top_level():
    """All four workers must be reachable via ``import minxg``."""
    for attr in ("JuliaWorker", "RWorker", "DatalogWorker", "WasmWorker"):
        assert hasattr(minxg, attr), f"minxg.{attr} missing"
        assert getattr(minxg, attr).__name__ == attr


# ── 2. Instantiation + tool registration ─────────────────────────────

@pytest.mark.parametrize("cls,worker_id,version", WORKERS)
def test_worker_instantiation_registers_tools(cls, worker_id, version):
    worker = cls()
    assert worker.worker_id == worker_id
    assert len(worker.tools) > 0, f"{worker_id} registered zero tools"


@pytest.mark.parametrize("cls,worker_id,version", WORKERS)
def test_all_tools_have_valid_metadata(cls, worker_id, version):
    """Every ToolDef must have name + description + params dict + category."""
    worker = cls()
    for name, tool_def in worker.tools.items():
        assert isinstance(tool_def, ToolDef)
        assert tool_def.name == name
        assert isinstance(tool_def.description, str)
        assert isinstance(tool_def.params, dict)
        # category is non-empty so callers can filter by it
        assert tool_def.category, f"{name} has empty category"


# ── 3. Tool count: workers shouldn't be kitchen sinks ────────────────

@pytest.mark.parametrize("cls,worker_id,expected_range",
                         [(JuliaWorker, "julia_math", (3, 9)),
                          (RWorker, "r_stats", (3, 9)),
                          (DatalogWorker, "datalog_logic", (3, 10)),
                          (WasmWorker, "wasm_compute", (6, 12))])
def test_tool_count_in_design_range(cls, worker_id, expected_range):
    low, high = expected_range
    worker = cls()
    n = len(worker.tools)
    assert low <= n <= high, (
        f"{worker_id} exposed {n} tools; expected {low}..{high}"
    )


# ── 4. Disabled-runtime envelope ───────────────────────────────────

@pytest.mark.parametrize("cls,expected_lang", [
    (JuliaWorker, "julia"),
    (RWorker, "r"),
    (DatalogWorker, "datalog"),
    (WasmWorker, "wasm"),
])
@pytest.mark.asyncio
async def test_workers_degrade_gracefully_when_runtime_absent(
        cls, expected_lang):
    """Without the runtime binary, tools return ``status=disabled``.

    Whether the runtime is installed on the test box is irrelevant —
    the contract is: tools NEVER raise; they always return a dict with
    ``status``. We verify the "disabled" envelope shape because that's
    what users see when, e.g., ``pkg install julia`` hasn't been run.
    """
    worker = cls()
    # Pick the first available tool and call it with minimal input.
    tool_name = next(iter(worker.tools))
    # WasmWorker handles divide-by-zero before checking runtime status,
    # so we deliberately pick inputs that pass validation.
    if isinstance(worker, WasmWorker):
        # arith_i32 add 1+1 — always reaches invoke path.
        tool_name = "wasm_arith_i32"
        result = await worker.call(tool_name, {"op": "add", "a": 1, "b": 1})
    elif isinstance(worker, RWorker):
        # r_eval with non-empty code goes through invoke gate.
        result = await worker.call("r_eval", {"code": "1+1"})
    elif isinstance(worker, DatalogWorker):
        # datalog_subset_check is engine-less pure-python and *always*
        # returns status=ok — verify its envelope is well-formed.
        result = await worker.call(
            "datalog_subset_check",
            {"a": ["a", "b"], "b": ["a", "b", "c"]},
        )
        assert result["status"] == "ok"
        assert result["subset"] is True
        assert result["language"] == "datalog"
        return  # subset_check short-circuits; nothing else to assert
    else:
        # JuliaWorker: try julia_eval.
        result = await worker.call("julia_eval", {"code": "1+1"})

    assert "status" in result
    # status must be one of the documented envelopes — never a raw exception
    assert result["status"] in (
        "ok", "disabled", "runtime_error", "error",
        "subset_violation",
    ), f"unexpected status: {result['status']!r}"
    assert result.get("language") == expected_lang


# ── 5. WasmWorker input validation (no runtime needed) ──────────────

@pytest.mark.asyncio
async def test_wasm_worker_catches_div_by_zero():
    worker = WasmWorker()
    result = await worker.call(
        "wasm_arith_i32",
        {"op": "div", "a": 10, "b": 0},
    )
    assert result["status"] == "error"
    assert "division by zero" in result["stderr"]
    # Worker reports which tool produced the error envelope.
    assert result["tool"] == "input_validation"


@pytest.mark.asyncio
async def test_wasm_worker_validates_op():
    worker = WasmWorker()
    result = await worker.call(
        "wasm_arith_i32",
        {"op": "invalid_op", "a": 1, "b": 2},
    )
    assert result["status"] == "error"
    assert "op must be" in result["stderr"]


@pytest.mark.asyncio
async def test_wasm_worker_validates_factorial_range():
    worker = WasmWorker()
    # 13! overflows i32; tool must reject n>12.
    result = await worker.call("wasm_factorial", {"n": 13})
    assert result["status"] == "error"
    assert "n must be in 0..12" in result["stderr"]


@pytest.mark.asyncio
async def test_wasm_worker_mat_det3_validates_shape():
    worker = WasmWorker()
    result = await worker.call("wasm_mat_det3", {"m": [1.0, 2.0, 3.0]})
    assert result["status"] == "error"
    assert "9 floats" in result["stderr"]


# ── 6. Datalog subset check (engine-less pure-python) ───────────────

@pytest.mark.asyncio
async def test_datalog_subset_check_returns_correct_envelope():
    worker = DatalogWorker()
    # Proper subset — must report subset=True and list missing=[].
    result = await worker.call(
        "datalog_subset_check",
        {"a": ["a", "b"], "b": ["a", "b", "c"]},
    )
    assert result["status"] == "ok"
    assert result["subset"] is True
    assert result["missing"] == []
    assert result["a_size"] == 2
    assert result["b_size"] == 3


@pytest.mark.asyncio
async def test_datalog_subset_check_detects_violation():
    worker = DatalogWorker()
    result = await worker.call(
        "datalog_subset_check",
        {"a": ["a", "x"], "b": ["a", "b", "c"]},
    )
    assert result["status"] == "subset_violation"
    assert result["subset"] is False
    assert "x" in result["missing"]


# ── 7. All workers produce valid ToolDef statistics ──────────────────

@pytest.mark.parametrize("cls,worker_id,version", WORKERS)
def test_workers_expose_statistics(cls, worker_id, version):
    worker = cls()
    stats = worker.statistics()
    assert stats["worker_id"] == worker_id
    assert stats["version"] == version
    assert isinstance(stats["uptime_sec"], (int, float))
    assert stats["uptime_sec"] >= 0
    assert stats["tool_count"] == len(worker.tools)


# ── 8. tools discovery via list_tools() ─────────────────────────────

@pytest.mark.parametrize("cls,worker_id,version", WORKERS)
def test_workers_list_tools_returns_sorted(cls, worker_id, version):
    worker = cls()
    tools = worker.list_tools()
    assert isinstance(tools, list)
    names = [t["name"] for t in tools]
    assert names == sorted(names), (
        f"{worker_id} tools not sorted: {names}"
    )
    for entry in tools:
        assert {"name", "description", "params", "category"} <= entry.keys()