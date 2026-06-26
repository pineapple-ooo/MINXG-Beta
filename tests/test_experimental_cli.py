"""tests/test_experimental_cli.py — coverage for the [EXPERIMENTAL] verbs.

These exercise `multiligua_cli/experimental.py` (bench, replay, theme,
safe-eval, ext-reload), the in-parser wiring inside `main.py`, and the
`minxg.__init__` top-level promotions of eight subsystem modules.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _NS(**kw):
    return argparse.Namespace(**kw)


# ----------------------------------------------------------------------
# safe-eval
# ----------------------------------------------------------------------

class SafeEvalTests(unittest.TestCase):
    def setUp(self):
        from multiligua_cli.experimental import run_safe_eval, SAFE_EVAL_GLOBALS
        self.run_safe_eval = run_safe_eval
        self.globals_snapshot = set(SAFE_EVAL_GLOBALS)

    def test_arithmetic_basics(self):
        # run_safe_eval returns the process exit code; the printed
        # value is the actual eval result.
        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(self.run_safe_eval(_NS(expr="1 + 2 * 3", locals=None)), 0)
            self.assertEqual(self.run_safe_eval(_NS(expr="abs(-5)", locals=None)), 0)
            self.assertEqual(self.run_safe_eval(_NS(expr="sum([1, 2, 3])", locals=None)), 0)
        # 1+2*3 = 7, abs(-5) = 5, sum([1,2,3]) = 6
        self.assertIn("7", out.getvalue())
        self.assertIn("5", out.getvalue())
        self.assertIn("6", out.getvalue())

    def test_disallowed_syntaxes(self):
        from multiligua_cli.experimental import _safe_eval
        with self.assertRaises(ValueError):
            _safe_eval('__import__("os")')
        with self.assertRaises(ValueError):
            _safe_eval('open("/etc/passwd").read()')
        with self.assertRaises(ValueError):
            _safe_eval('(lambda: 1)()')

    def test_cli_missing_expr(self):
        self.assertEqual(self.run_safe_eval(_NS(expr=None, locals=None)), 2)

    def test_cli_invalid_locals_json(self):
        self.assertEqual(self.run_safe_eval(
            _NS(expr="1+1", locals="{bad json}")), 2)


# ----------------------------------------------------------------------
# bench
# ----------------------------------------------------------------------

class BenchTests(unittest.TestCase):
    def test_run_bench_returns_zero(self):
        from multiligua_cli.experimental import run_bench
        rc = run_bench(_NS())
        self.assertEqual(rc, 0)


# ----------------------------------------------------------------------
# replay
# ----------------------------------------------------------------------

class ReplayTests(unittest.TestCase):
    def test_roundtrip_export_then_replay(self):
        from multiligua_cli.features import export_to_markdown
        from multiligua_cli.experimental import run_replay, _parse_markdown_lines

        with tempfile.TemporaryDirectory() as td:
            md_path = Path(td) / "conv.md"
            md_path.write_text("", encoding="utf-8")
            # swap to temp via the function's own return path instead
            msg = [
                {"role": "user", "content": "hello world"},
                {"role": "assistant", "content": "hi back"},
                {"role": "tool", "content": "ok"},
            ]
            ret = export_to_markdown(msg)
            try:
                turns = _parse_markdown_lines(Path(ret))
                self.assertEqual([t["role"] for t in turns],
                                 ["user", "assistant", "tool"])
                rc = run_replay(_NS(file=ret))
                self.assertEqual(rc, 0)
            finally:
                if os.path.exists(ret):
                    os.unlink(ret)

    def test_replay_missing_file(self):
        from multiligua_cli.experimental import run_replay
        self.assertEqual(run_replay(_NS(file="/no/such/path.md")), 2)

    def test_replay_empty(self):
        from multiligua_cli.experimental import run_replay
        with tempfile.NamedTemporaryFile("w", suffix=".md",
                                         delete=False) as f:
            f.write("# no turns in here")
            name = f.name
        try:
            self.assertEqual(run_replay(_NS(file=name)), 0)
        finally:
            os.unlink(name)


# ----------------------------------------------------------------------
# theme
# ----------------------------------------------------------------------

class ThemeTests(unittest.TestCase):
    def setUp(self):
        self._old_home = os.environ.pop("MINXG_HOME", None)
        self._tmp = Path(tempfile.mkdtemp())
        os.environ["MINXG_HOME"] = str(self._tmp)
        # re-bind module-level THEME_FILE
        import multiligua_cli.experimental as exp_mod
        exp_mod.THEME_FILE = self._tmp / "theme.json"

    def tearDown(self):
        if self._old_home is not None:
            os.environ["MINXG_HOME"] = self._old_home

    def test_default_when_missing(self):
        from multiligua_cli.experimental import run_theme
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = run_theme(_NS(name=None))
        self.assertEqual(rc, 0)
        self.assertIn("dark", out.getvalue())

    def test_set_then_get(self):
        from multiligua_cli.experimental import run_theme
        with mock.patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(run_theme(_NS(name="minimal")), 0)
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(run_theme(_NS(name=None)), 0)
        self.assertIn("minimal", out.getvalue())

    def test_invalid_name(self):
        from multiligua_cli.experimental import run_theme
        self.assertEqual(run_theme(_NS(name="hotpink")), 2)


# ----------------------------------------------------------------------
# ext-reload (soft-fail behaviour)
# ----------------------------------------------------------------------

class ExtReloadTests(unittest.TestCase):
    def test_ext_reload_returns_zero(self):
        from multiligua_cli.experimental import run_ext_reload
        self.assertEqual(run_ext_reload(_NS(all=True)), 0)


# ----------------------------------------------------------------------
# submodule promotion inside minxg/__init__.py
# ----------------------------------------------------------------------

class TopLevelSubsystemsTests(unittest.TestCase):
    SUBSYSTEMS = (
        "twin", "lens", "lossless", "self_evolution", "polyglot",
        "driver", "cap", "contracts",
    )

    def setUp(self):
        for name in list(sys.modules):
            if name.startswith("minxg"):
                del sys.modules[name]

    def test_top_level_promotion(self):
        import minxg
        for name in self.SUBSYSTEMS:
            with self.subTest(name=name):
                self.assertTrue(
                    hasattr(minxg, name),
                    f"minxg.{name} must be a top-level attribute after 0.13.0",
                )
                self.assertIsNotNone(getattr(minxg, name))

    def test_all_lists_subsystems(self):
        import minxg
        for name in self.SUBSYSTEMS:
            with self.subTest(name=name):
                self.assertIn(name, minxg.__all__)


if __name__ == "__main__":
    unittest.main()
