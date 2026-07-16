"""tests/test_tui_suggest.py — slash-command autocomplete engine + TUI input.

Coverage:

* ``multiligua_cli.suggest.suggest`` — the spec cases from the
  "MINXG chat redo" ticket:
  - ``//mo`` → ``/model`` (+ other ``mo*``)
  - ``//bo`` → ``/boss`` (+ other ``bo*``) — NOT ``/model``
  - plain prose must NOT register as a command attempt
  - single ``/mo`` is NOT a command, only ``//`` is the gate
* ``multiligua_cli.tui_input`` — the default hint closure
  and the entropy-gating.  Doesn't touch the TTY.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from multiligua_cli.suggest import (
    DEFAULT_COMMANDS,
    is_slash_prefix,
    primary_suggestion,
    suggest,
)
from multiligua_cli import tui_input


# ── Gate predicate ──────────────────────────────────────────────────────


def test_is_slash_prefix_positive():
    assert is_slash_prefix("//")
    assert is_slash_prefix("//model")
    assert is_slash_prefix("//bo")


def test_is_slash_prefix_negative():
    assert not is_slash_prefix("/model")     # single slash, NOT //
    assert not is_slash_prefix("")
    assert not is_slash_prefix("请帮我分内部储存")


# ── Typing spec cases from the user ticket ──────────────────────────────


def test_suggest_mo_matches_model_family():
    hits = suggest("//mo", DEFAULT_COMMANDS)
    # Must contain /model (canonical command) and any other 'mo*'.
    assert "/model" in hits
    # /memory is *me*… not *mo*… so it must NOT appear.
    assert "/memory" not in hits
    # /mode and /mobile are mo-completions and SHOULD be present.
    assert "/mode" in hits or "/mobile" in hits      # both are in DEFAULT


def test_suggest_bo_does_NOT_match_model():
    """The killer check — a single typo must NOT surface //model."""
    hits = suggest("//bo", DEFAULT_COMMANDS)
    assert "/model" not in hits
    assert "/memory" not in hits


def test_suggest_boss_letters_typed_completely():
    hits = suggest("//boss", DEFAULT_COMMANDS)
    assert "/boss" in hits


def test_suggest_no_match_returns_empty():
    hits = suggest("//strangecode", DEFAULT_COMMANDS)
    assert hits == ()


def test_suggest_empty_body_returns_everything():
    hits = suggest("//", DEFAULT_COMMANDS)
    # The default command set is exposed in full to prompt the user.
    assert "/help" in hits and "/model" in hits and "/exit" in hits


def test_suggest_prose_returns_empty():
    """User ticket: prose like '请帮我分内部储存...' must NOT trigger hints."""
    prose_pool = ("/model", "/memory", "/help")
    assert suggest("请帮我分内部储存/文件目录下的文件",
                     prose_pool) == ()
    assert suggest("Hello, MINXG.", prose_pool) == ()


def test_primary_suggestion_returns_first_match():
    assert primary_suggestion(
        "//mo", ("/model", "/mode", "/memory")) == "/model"
    assert primary_suggestion(
        "//bo", ("/model", "/boss")) == "/boss"
    # No match → empty hint.
    assert primary_suggestion(
        "//strange", ("/model", "/help")) == ""


# ── Default hint closure on the tui_input layer ────────────────────────


def test_default_hint_only_fires_on_double_slash():
    assert tui_input._default_hint("//mo") == "/model"
    assert tui_input._default_hint("//bo") == "/boss"
    assert tui_input._default_hint("//model") == "/model"
    # Gate silencing
    assert tui_input._default_hint("/mo") == ""            # single slash
    assert tui_input._default_hint("mo") == ""             # no slash at all
    assert tui_input._default_hint("") == ""               # empty buffer


def test_default_hint_does_not_break_on_prose():
    """The killer regression test from the user ticket."""
    assert tui_input._default_hint("请帮我分内部储存/文件") == ""


# ── Module symbols ──────────────────────────────────────────────────────


def test_module_exports():
    from multiligua_cli import suggest as _sd
    assert hasattr(_sd, "DEFAULT_COMMANDS")
    assert hasattr(_sd, "is_slash_prefix")
    assert hasattr(_sd, "suggest")
    assert hasattr(_sd, "primary_suggestion")


def test_default_command_set_includes_help_and_exit():
    """`/help`, `/exit`, and `/quit` must ALWAYS be in the suggest pool."""
    for cmd in ("/help", "/exit", "/quit"):
        assert cmd in DEFAULT_COMMANDS


def test_no_command_in_pool_starts_without_slash():
    for cmd in DEFAULT_COMMANDS:
        assert cmd.startswith("/"), f"command {cmd!r} missing leading slash"
