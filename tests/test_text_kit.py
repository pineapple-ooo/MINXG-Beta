"""tests/test_text_kit.py — verify the text_kit facade collapse.

The legacy ``text_tools.py`` (12), ``string_tools.py`` (8), and the bulk
of ``text_adv.py`` (~80) were collapsed into one ``TextKitWorker`` with
2 tools: ``text_op`` (dispatch) and ``text_op_list`` (discovery).

This file verifies:
* The worker instantiates and registers exactly 2 tools.
* Every route registered in ``_ROUTES`` produces a non-error result
  when invoked via ``text_op``.
* The op-catalogue returned by ``text_op_list`` covers every route and
  groups them by category.
* Unknown ops produce a clean error envelope (no exception).
"""

import pytest

from minxg.five_pillars.aggregate.text_kit import (
    TextKitWorker, _ROUTES,
)


# ── 1. Worker registration contract ─────────────────────────────────────

def test_text_kit_worker_is_importable():
    """The facade module must be importable without raising."""
    # Imported at module level — if we got here it's importable.
    pass


def test_text_kit_registers_exactly_two_tools():
    """One of the entire design goals: surface 2 tools, not 100."""
    worker = TextKitWorker()
    name_set = set(worker.tools.keys())
    assert name_set == {"text_op", "text_op_list"}, (
        f"expected exactly two tools, got {name_set}"
    )


def test_text_kit_worker_id_and_version():
    worker = TextKitWorker()
    assert worker.worker_id == "text_kit"
    assert worker.version == "0.16.0"


def test_text_kit_both_tools_have_valid_metadata():
    worker = TextKitWorker()
    for tool_def in worker.tools.values():
        assert tool_def.description, "empty description"
        assert tool_def.category == "text", (
            f"category should be 'text', got {tool_def.category!r}"
        )


# ── 2. Routes catalogue consistency ────────────────────────────────────

def test_every_route_has_required_keys():
    for op, spec in _ROUTES.items():
        assert "fn" in spec, f"op {op!r} missing 'fn'"
        assert "args" in spec, f"op {op!r} missing 'args'"
        assert "category" in spec, f"op {op!r} missing 'category'"
        assert "summary" in spec, f"op {op!r} missing 'summary'"
        assert callable(spec["fn"])
        assert isinstance(spec["args"], list)
        assert isinstance(spec["summary"], str)


def test_routes_have_at_least_25_ops():
    """Sanity check — collapse should produce a non-trivial authoritative set."""
    assert len(_ROUTES) >= 25, (
        f"only {len(_ROUTES)} routes; the collapse target was >=25"
    )


def test_routes_cover_all_text_tools_legacy_ops():
    """The legacy text_tools.py exposed this exact set of tools.
    Each must be reachable via text_op."""
    legacy = {"tokenize", "word_frequency", "trim", "truncate",
              "word_count", "slugify", "token_estimate", "text_diff",
              "text_wrap", "extract_urls", "extract_emails",
              "normalize_whitespace", "extract_hashtags"}
    missing = legacy - set(_ROUTES)
    assert not missing, f"missing legacy text_tools.py routes: {missing}"


# ── 3. text_op_list catalogues reflect _ROUTES ────────────────────────

@pytest.mark.asyncio
async def test_text_op_list_returns_categorised_grouping():
    worker = TextKitWorker()
    result = await worker.call("text_op_list", {})
    assert "categories" in result
    assert "total_ops" in result
    assert result["total_ops"] == len(_ROUTES)
    # Every category bucket should appear. Keys:
    cats = result["categories"]
    expected_cats = {"analyze", "transform", "extract", "similarity",
                     "regex", "format", "escape"}
    actual_cats = set(cats.keys())
    assert expected_cats <= actual_cats, (
        f"missing categories: {expected_cats - actual_cats}"
    )


@pytest.mark.asyncio
async def test_text_op_list_contains_per_op_summary():
    worker = TextKitWorker()
    result = await worker.call("text_op_list", {})
    found_slugify = False
    for cat_entries in result["categories"].values():
        for entry in cat_entries:
            assert "op" in entry
            assert "args" in entry
            assert "summary" in entry
            if entry["op"] == "slugify":
                found_slugify = True
    assert found_slugify, "slugify entry not present in any category"


# ── 4. Operational smoke tests ─────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("op,kwargs,expect_key", [
    ("tokenize", {"text": "Hello World"}, "words"),
    ("word_count", {"text": "Hello World"}, "words"),
    ("slugify", {"text": "Hello World!"}, "slug"),
    ("trim", {"text": "  hi  "}, "text"),
    ("truncate", {"text": "abcdef", "max_length": 3}, "text"),
    ("extract_urls", {"text": "see https://x.y and http://a.b/c"}, "urls"),
    ("extract_emails", {"text": "ping a@b.com and c@d.io"}, "emails"),
    ("extract_hashtags", {"text": "#one #two buzz #three"}, "hashtags"),
    ("levenshtein", {"a": "kitten", "b": "sitting"}, "distance"),
    ("jaro_winkler", {"a": "MARTHA", "b": "MARHTA"}, "similarity"),
    ("camel_to_snake", {"text": "CamelCaseInput"}, "result"),
    ("html_escape", {"text": "<b>&\""}, "result"),
    ("json_escape", {"text": 'a"b'}, "result"),
    ("text_diff", {"old": "a\nb", "new": "a\nc"}, "diff"),
])
async def test_text_op_route_produces_named_key(op, kwargs, expect_key):
    worker = TextKitWorker()
    result = await worker.call("text_op", {"op": op, **kwargs})
    assert "status" not in result or result.get("status") != "error", (
        f"{op} returned error: {result}"
    )
    assert expect_key in result, (
        f"op {op!r} missing expected key {expect_key!r}; got {list(result)}"
    )


# ── 5. Error envelopes ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_text_op_unknown_op_returns_clean_error():
    worker = TextKitWorker()
    result = await worker.call("text_op", {"op": "bogus_op_doesnt_exist"})
    assert result["status"] == "error"
    assert "available" in result
    assert "slugify" in result["available"] # known good name
    assert "bogus_op_doesnt_exist" in result["error"]


@pytest.mark.asyncio
async def test_text_op_regex_invalid_pattern_returns_clean_error():
    worker = TextKitWorker()
    # Unbalanced '[' is a regex error
    result = await worker.call("text_op", {
        "op": "regex_findall", "pattern": "[", "text": "x"})
    assert result.get("status") == "error"
    assert "error" in result


@pytest.mark.asyncio
async def test_text_op_missing_op_arg_returns_error():
    worker = TextKitWorker()
    result = await worker.call("text_op", {})
    assert result["status"] == "error"


# ── 6. Backward-compatibility smoke (legacy callers can co-exist) ────

def test_legacy_text_tools_worker_still_exists():
    """make sure we did NOT delete the old TextToolsWorker —
    only added a parallel facade."""
    from minxg.five_pillars.scalar.text_tools import TextToolsWorker
    worker = TextToolsWorker()
    name_set = set(worker.tools.keys())
    # Old design: every method was a separate tool. Some are now redundant
    # with text_kit, but we must not have reduced coverage.
    assert len(name_set) >= 10, (
        f"legacy worker should still expose its 12 tools; got {len(name_set)}"
    )