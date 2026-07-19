"""
test_wizard_ui.py — exercise multiligua_cli/wizard_ui.py

Tests cover:
  - MinxgMenu can be constructed with title + 2 options
  - run() returns an int index when mocked input is sequential
  - run() returns None on cancel (empty input / EOF)
  - description lines render alongside options
"""
from __future__ import annotations

import os
import sys
from unittest import mock
import pytest

import multiligua_cli.wizard_ui as wizard_mod


# ── construction ────────────────────────────────────────────────────────────

class TestMinxgMenuConstruction:
    def test_basic_construction(self):
        menu = wizard_mod.MinxgMenu("Pick one", ["alpha", "beta"])
        assert menu.title == "Pick one"
        assert menu.options == ["alpha", "beta"]
        assert menu.selected == 0
        assert menu.running is True

    def test_empty_descriptions_defaults_to_blanks(self):
        menu = wizard_mod.MinxgMenu("Title", ["a", "b", "c"])
        assert menu.descriptions == ["", "", ""]

    def test_descriptions_preserved(self):
        menu = wizard_mod.MinxgMenu("Title", ["a", "b"], ["desc a", "desc b"])
        assert menu.descriptions == ["desc a", "desc b"]


# ── run() with readchar unavailable ────────────────────────────────────────

class TestMinxgMenuRunNoReadchar:
    """When readchar is missing, MinxgMenu falls back to numbered input."""

    def test_run_returns_index_for_valid_input(self, monkeypatch, capsys):
        monkeypatch.setattr(wizard_mod, "HAS_READCHAR", False)
        menu = wizard_mod.MinxgMenu("Title", ["opt_a", "opt_b", "opt_c"])
        # Simulate user typing "2" then enter
        with mock.patch("builtins.input", side_effect=["2"]):
            result = menu.run()
        assert result == 1  # 0-indexed: "2" -> index 1

    def test_run_returns_none_on_cancel_q(self, monkeypatch):
        monkeypatch.setattr(wizard_mod, "HAS_READCHAR", False)
        menu = wizard_mod.MinxgMenu("Title", ["opt_a", "opt_b"])
        with mock.patch("builtins.input", side_effect=["q"]):
            result = menu.run()
        assert result is None

    def test_run_returns_none_on_eof(self, monkeypatch):
        monkeypatch.setattr(wizard_mod, "HAS_READCHAR", False)
        menu = wizard_mod.MinxgMenu("Title", ["opt_a"])
        with mock.patch("builtins.input", side_effect=["", "bad", EOFError]):
            result = menu.run()
        assert result is None

    def test_run_rejects_out_of_range_then_accepts(self, monkeypatch, capsys):
        monkeypatch.setattr(wizard_mod, "HAS_READCHAR", False)
        menu = wizard_mod.MinxgMenu("Title", ["opt_a", "opt_b"])
        # "0" is out of range (1-based), "1" is valid
        with mock.patch("builtins.input", side_effect=["0", "1"]):
            result = menu.run()
        assert result == 0


# ── run() with readchar available (arrow-key path) ─────────────────────────

class TestMinxgMenuRunWithReadchar:
    """When readchar is present, MinxgMenu uses arrow-key navigation."""

    def test_run_returns_selected_on_enter(self, monkeypatch):
        """Simulate DOWN then ENTER."""
        monkeypatch.setattr(wizard_mod, "HAS_READCHAR", True)
        menu = wizard_mod.MinxgMenu("Title", ["alpha", "beta", "gamma"])
        menu.selected = 0
        # Sequence: DOWN moves to index 1, ENTER confirms
        fake_keys = iter([wizard_mod.readchar.key.DOWN, wizard_mod.readchar.key.ENTER])
        with mock.patch.object(wizard_mod.readchar, "readkey", side_effect=lambda: next(fake_keys)):
            result = menu.run()
        assert result == 1

    def test_run_returns_none_on_q(self, monkeypatch):
        monkeypatch.setattr(wizard_mod, "HAS_READCHAR", True)
        menu = wizard_mod.MinxgMenu("Title", ["alpha"])
        fake_keys = iter(["q"])
        with mock.patch.object(wizard_mod.readchar, "readkey", side_effect=lambda: next(fake_keys)):
            result = menu.run()
        assert result is None

    def test_run_returns_none_on_keyboard_interrupt(self, monkeypatch):
        monkeypatch.setattr(wizard_mod, "HAS_READCHAR", True)
        menu = wizard_mod.MinxgMenu("Title", ["alpha"])
        with mock.patch.object(
            wizard_mod.readchar, "readkey", side_effect=KeyboardInterrupt
        ):
            try:
                result = menu.run()
            except KeyboardInterrupt:
                result = None
        assert result is None


# ── description rendering ───────────────────────────────────────────────────

class TestDescriptionRendering:
    def test_descriptions_render_alongside_options(self, monkeypatch, capsys):
        """print_option_item should emit description text when given."""
        monkeypatch.setattr(wizard_mod, "HAS_RICH", False)
        # Direct call to print_option_item (used inside MinxgMenu)
        wizard_mod.print_option_item(
            selected=False, text="Option A", desc="some description"
        )
        captured = capsys.readouterr()
        assert "Option A" in captured.out
        assert "some description" in captured.out

    def test_option_item_selected_uses_gold(self, monkeypatch, capsys):
        monkeypatch.setattr(wizard_mod, "HAS_RICH", False)
        wizard_mod.print_option_item(selected=True, text="X", desc="Y")
        out = capsys.readouterr().out
        # The selected head should use GOLD style (ANSI code)
        assert wizard_mod.Colors.GOLD in out
