"""tests/test_polyglot_runtime_installer.py — polyglot runtime install helpers.

Covers ``minxg/contracts/runtime/installer.py`` plus the two
[EXPERIMENTAL] CLI verbs wired in
``multiligua_cli/experimental.py`` (0.14+).

The matrix under test is platform-aware (termux / linux / macos /
windows / unknown), so the tests deliberately exercise
``--platform`` overrides instead of relying on the host's actual
``platform_id()`` — that's the only way the test stays reproducible
on a Mac in CI and on a Termux phone.

The ``run_install(..., apply=True)`` path is exercised by monkey-patching
the caller-supplied ``runner`` callable — we never invoke ``sh -c
pkg install`` in a unit test.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


def _NS(**kw):
    return argparse.Namespace(**kw)


def _first_json_object(text: str) -> str:
    """Pull the leading JSON object out of a stdout stream.

    ``run_runtime_install`` writes a JSON payload first, then a
    trailing "[EXPERIMENTAL] runtime-install dry-run..." line when
    ``apply=False``. The block extraction just lifts the first
    brace-matched object so the test only parses the JSON.
    """
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


# ----------------------------------------------------------------------
# platform_id
# ----------------------------------------------------------------------


class PlatformIDTests(unittest.TestCase):
    """`platform_id()` must collapse Termux / Linux / macOS / Windows.

    Tests use ``mock.patch`` on ``os.path.isdir`` AND ``platform.system``
    to avoid relying on the real host (Termux sets ``/data/data/com.termux``
    on THIS machine, which would otherwise leak across tests).
    """

    def test_termux_via_env_var(self):
        from minxg.contracts.runtime.installer import platform_id
        with mock.patch.dict(
            os.environ, {"TERMUX_VERSION": "0.118"}, clear=False
        ):
            self.assertEqual(platform_id(), "termux")

    def test_termux_via_app_dir(self):
        from minxg.contracts.runtime.installer import platform_id
        env = {k: v for k, v in os.environ.items() if k != "TERMUX_VERSION"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.isdir", return_value=True):
            self.assertEqual(platform_id(), "termux")

    def test_linux_when_neither_termux_nor_darwin(self):
        """v0.14.1: Linux is no longer supported; returns 'unknown'."""
        from minxg.contracts.runtime.installer import platform_id
        env = {k: v for k, v in os.environ.items() if k != "TERMUX_VERSION"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.isdir", return_value=False), \
             mock.patch("platform.system", return_value="Linux"):
            self.assertEqual(platform_id(), "unknown")

    def test_macos(self):
        """v0.14.1: macOS is no longer supported; returns 'unknown'."""
        from minxg.contracts.runtime.installer import platform_id
        env = {k: v for k, v in os.environ.items() if k != "TERMUX_VERSION"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.isdir", return_value=False), \
             mock.patch("platform.system", return_value="Darwin"):
            self.assertEqual(platform_id(), "unknown")

    def test_windows_msys(self):
        from minxg.contracts.runtime.installer import platform_id
        env = {k: v for k, v in os.environ.items() if k != "TERMUX_VERSION"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.isdir", return_value=False), \
             mock.patch("platform.system", return_value="MINGW64_NT-10.0"):
            self.assertEqual(platform_id(), "windows")

    def test_unknown_for_exotic_system(self):
        from minxg.contracts.runtime.installer import platform_id
        env = {k: v for k, v in os.environ.items() if k != "TERMUX_VERSION"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.isdir", return_value=False), \
             mock.patch("platform.system", return_value="Plan9"):
            self.assertEqual(platform_id(), "unknown")


# ----------------------------------------------------------------------
# detect_runtime
# ----------------------------------------------------------------------


class DetectRuntimeTests(unittest.TestCase):
    """`detect_runtime` must classify each language with no side-effects."""

    def test_cpp_found_when_gpp_on_path(self):
        from minxg.contracts.runtime.installer import detect_runtime
        with mock.patch(
            "shutil.which", side_effect=lambda c: "/usr/bin/g++" if c == "g++" else None
        ):
            st = detect_runtime("cpp")
        self.assertTrue(st.available)
        self.assertIn("g++", st.binary)

    def test_cpp_missing_falls_back_to_clang(self):
        from minxg.contracts.runtime.installer import detect_runtime
        with mock.patch(
            "shutil.which",
            side_effect=lambda c: "/usr/bin/clang++" if c == "clang++" else None,
        ):
            st = detect_runtime("cpp")
        self.assertTrue(st.available)
        self.assertIn("clang", st.binary)

    def test_cpp_missing(self):
        from minxg.contracts.runtime.installer import detect_runtime
        with mock.patch("shutil.which", return_value=None):
            st = detect_runtime("cpp")
        self.assertFalse(st.available)
        self.assertEqual(st.binary, "g++/clang++")

    def test_wasm_optional_missing_is_fine(self):
        from minxg.contracts.runtime.installer import detect_runtime
        with mock.patch("shutil.which", return_value=None):
            st = detect_runtime("wasm")
        self.assertFalse(st.available)
        self.assertIn("emulator", st.note)

    def test_go_returns_version_in_note(self):
        from minxg.contracts.runtime.installer import detect_runtime
        fake_proc = {"ok": True, "stdout": "go version go1.22.3 linux/amd64", "stderr": ""}
        with mock.patch(
            "shutil.which", return_value="/usr/local/go/bin/go"
        ) as which_, mock.patch(
            "minxg.contracts.runtime._exec.run", return_value=fake_proc
        ) as runner:
            st = detect_runtime("go")
        self.assertTrue(st.available)
        self.assertIn("go1.22.3", st.note)
        which_.assert_called_with("go")
        runner.assert_called()

    def test_r_needs_jsonlite(self):
        from minxg.contracts.runtime.installer import detect_runtime
        version_proc = {"ok": True, "stdout": "R version 4.3.1", "stderr": ""}
        with mock.patch(
            "shutil.which", return_value="/usr/bin/Rscript"
        ), mock.patch(
            "minxg.contracts.runtime._exec.run",
            side_effect=[
                # R version probe
                version_proc,
                # jsonlite probe — pretend Rscript fails
                {"ok": False, "stdout": "", "stderr": "no jsonlite"},
            ],
        ):
            st = detect_runtime("r")
        # Without jsonlite we treat as missing, exact wording is permissive.
        self.assertFalse(st.available)
        self.assertIn("jsonlite", st.note)

    def test_julia_with_version(self):
        from minxg.contracts.runtime.installer import detect_runtime
        with mock.patch(
            "shutil.which", return_value="/usr/local/julia/bin/julia"
        ), mock.patch(
            "minxg.contracts.runtime._exec.run",
            return_value={"ok": True, "stdout": "1.10.5", "stderr": ""},
        ):
            st = detect_runtime("julia")
        self.assertTrue(st.available)
        self.assertEqual(st.version_hint, "1.10.5")

    def test_datalog_clingo_preferred(self):
        from minxg.contracts.runtime.installer import detect_runtime
        with mock.patch("shutil.which", return_value="/usr/bin/clingo"):
            st = detect_runtime("datalog")
        self.assertTrue(st.available)
        self.assertIn("clingo", st.binary)

    def test_datalog_pydatalog_fallback(self):
        from minxg.contracts.runtime.installer import detect_runtime
        with mock.patch("shutil.which", return_value=None), \
             mock.patch.dict(sys.modules, {"pyDatalog": mock.MagicMock()}):
            st = detect_runtime("datalog")
        self.assertTrue(st.available)
        self.assertIn("pyDatalog", st.binary)

    def test_unknown_language_says_so(self):
        from minxg.contracts.runtime.installer import detect_runtime
        st = detect_runtime("brainfuck")
        self.assertFalse(st.available)
        self.assertIn("unknown", st.note)


# ----------------------------------------------------------------------
# plan_install / current_plan / render_install_plan — pure-data shapes
# ----------------------------------------------------------------------


class PlanInstallTests(unittest.TestCase):
    """Every managed language has a plan on every supported platform."""

    LANGS = ("cpp", "go", "wasm", "r", "julia", "datalog")
    PLATS = ("termux", "windows", "unknown")

    def test_managed_languages_have_a_plan(self):
        from minxg.contracts.runtime.installer import (
            plan_install, MANAGED_LANGUAGES,
        )
        self.assertEqual(
            tuple(MANAGED_LANGUAGES), self.LANGS
        )
        for lang in self.LANGS:
            plan = plan_install(lang)
            self.assertEqual(plan.language, lang)
            self.assertEqual(set(plan.commands.keys()), set(self.PLATS))

    def test_unmanaged_language_still_yields_a_plan(self):
        from minxg.contracts.runtime.installer import plan_install
        plan = plan_install("brainfuck")
        self.assertEqual(plan.language, "brainfuck")
        # All platforms present, but no real cmd.
        for plat in self.PLATS:
            cmd, _ = plan.command_for(plat)
            self.assertEqual(cmd, "")

    def test_unknown_platform_falls_back_to_unknown_key(self):
        from minxg.contracts.runtime.installer import plan_install
        plan = plan_install("cpp")
        cmd, _ = plan.command_for("Plan9")
        # Unknown plat picks the ``unknown`` recipe (empty).
        self.assertEqual(cmd, plan.commands["unknown"])

    def test_termux_cmd_for_cpp_is_pkg(self):
        from minxg.contracts.runtime.installer import plan_install
        plan = plan_install("cpp")
        cmd, note = plan.command_for("termux")
        self.assertIn("pkg install", cmd)
        self.assertIn("clang", cmd)
        self.assertTrue(note)  # Termux gets a helpful note

    def test_termux_for_r_is_pkg_install(self):
        from minxg.contracts.runtime.installer import plan_install
        plan = plan_install("r")
        cmd, _ = plan.command_for("termux")
        self.assertIn("pkg install", cmd)

    def test_render_includes_status_per_language(self):
        from minxg.contracts.runtime.installer import (
            plan_install, render_install_plan,
        )
        plans = [plan_install(lang) for lang in ("cpp", "wasm")]
        rendered = render_install_plan(plans, plat="termux")
        self.assertIn("host=termux", rendered)
        self.assertIn(". cpp", rendered)
        self.assertIn(". wasm", rendered)
        self.assertIn("pkg install -y clang", rendered)

    def test_status_snapshot_layout(self):
        from minxg.contracts.runtime.installer import status_snapshot
        rows = status_snapshot()
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertIn("language", row)
            self.assertIn("binary", row)
            self.assertIn("available", row)
            self.assertIn("note", row)
            self.assertIn(row["available"], ("yes", "no"))

    def test_current_plan_all_handles_unknown_id(self):
        from minxg.contracts.runtime.installer import current_plan
        # ``all`` returns one plan per managed language, ``brainfuck``
        # returns a single no-op plan.
        plans = current_plan("brainfuck")
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].language, "brainfuck")


# ----------------------------------------------------------------------
# run_install — apply=False (dry-run) doesn't subprocess, apply=True
# uses the test seam.
# ----------------------------------------------------------------------


class RunInstallTests(unittest.TestCase):
    """The executor is the only place subprocess calls are made."""

    def test_dry_run_never_calls_runner(self):
        from minxg.contracts.runtime.installer import run_install
        calls = []

        def tracker(cmd):
            calls.append(cmd)
            return {"ok": True, "stdout": "", "stderr": ""}

        with mock.patch(
            "minxg.contracts.runtime._exec.run"
        ) as runner, mock.patch("shutil.which", return_value=None):
            runner.side_effect = lambda *a, **kw: (_ for _ in ()).throw(
                AssertionError("dry-run must not call _exec.run")
            )
            result = run_install("r", plat="termux", apply=False, runner=tracker)
        # tracker was *not* invoked.
        self.assertEqual(calls, [])
        self.assertFalse(result["plans"][0]["applied"])

    def test_apply_uses_runner_and_marks_applied(self):
        from minxg.contracts.runtime.installer import run_install
        seen = []

        def fake_runner(cmd):
            seen.append(cmd)
            return {"ok": True, "stdout": "installed\n", "stderr": ""}

        with mock.patch("shutil.which", return_value=None):
            result = run_install(
                "r", plat="termux", apply=True, runner=fake_runner,
            )
        self.assertEqual(len(seen), 1)
        self.assertIn("pkg install", seen[0])
        rows = result["plans"]
        self.assertEqual(rows[0]["language"], "r")
        self.assertTrue(rows[0]["applied"])
        self.assertTrue(rows[0]["runner_output"]["ok"])

    def test_apply_surfaces_failure(self):
        from minxg.contracts.runtime.installer import run_install

        def bad_runner(cmd):
            return {"ok": False, "stdout": "", "stderr": "permission denied"}

        with mock.patch("shutil.which", return_value=None):
            result = run_install(
                "julia", plat="termux", apply=True, runner=bad_runner,
            )
        self.assertFalse(result["plans"][0]["runner_output"]["ok"])
        self.assertEqual(
            result["plans"][0]["runner_output"]["stderr"], "permission denied",
        )

    def test_apply_no_op_when_already_available_known_caller(self):
        """When the detector says the binary is present, the plan prints
        a sentinel ``echo 'already on PATH'`` cmd which the executor
        short-circuits without invoking the runner.
        """
        from minxg.contracts.runtime.installer import run_install
        triggered = []

        def failing_runner(cmd):
            triggered.append(cmd)
            return {"ok": True}

        # cpp on termux — we *pretend* g++ is present, then re-call with
        # apply=True and expect the runner to NOT fire.
        with mock.patch(
            "shutil.which", return_value="/usr/bin/g++"
        ):
            result = run_install(
                "cpp", plat="termux", apply=True, runner=failing_runner,
            )
        self.assertEqual(triggered, [])
        self.assertFalse(result["plans"][0]["applied"])

    def test_apply_unknown_platform_records_empty_command(self):
        from minxg.contracts.runtime.installer import run_install
        triggered = []

        def tracker(cmd):
            triggered.append(cmd)
            return {"ok": True, "stdout": "", "stderr": ""}

        result = run_install(
            "r", plat="Plan9", apply=True, runner=tracker,
        )
        self.assertEqual(triggered, [])
        self.assertEqual(result["plans"][0]["command"], "")
        self.assertFalse(result["plans"][0]["applied"])

    def test_runtime_install_dispatch_dry_run_returns_0(self):
        """The CLI verb defaults to dry-run; check end-to-end via
        ``multiligua_cli.experimental.run_runtime_install`` without
        ever spawning a subprocess."""
        from multiligua_cli.experimental import run_runtime_install

        args = _NS(language="r", apply=False, platform="linux")
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = run_runtime_install(args)
        self.assertEqual(rc, 0)
        payload = json.loads(_first_json_object(out.getvalue()))
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["platform"], "linux")
        self.assertEqual(len(payload["plans"]), 1)
        # The trailing dry-run hint line should still appear in stderr-or-stdout
        # (currently it goes to stdout after the JSON).
        self.assertIn("dry-run", out.getvalue() + err.getvalue())

    def test_runtime_install_unknown_language_returns_2(self):
        from multiligua_cli.experimental import run_runtime_install
        args = _NS(language="brainfuck", apply=False, platform=None)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = run_runtime_install(args)
        self.assertEqual(rc, 2)

    def test_runtime_plan_dispatch(self):
        from multiligua_cli.experimental import run_runtime_plan
        args = _NS(language="all", platform="termux")
        with redirect_stdout(io.StringIO()) as out, \
             redirect_stderr(io.StringIO()):
            rc = run_runtime_plan(args)
        self.assertEqual(rc, 0)
        body = out.getvalue()
        self.assertIn("host=termux", body)
        # All six managed languages present.
        for lang in ("cpp", "go", "wasm", "r", "julia", "datalog"):
            self.assertIn(f". {lang}", body)

    def test_dispatch_routes_runtime_install(self):
        """``experimental.dispatch`` resolves `_experimental_cmd` to the
        new verbs (parity with the other 0.14 experimental verbs)."""
        from multiligua_cli.experimental import dispatch
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = dispatch(_NS(
                _experimental_cmd="runtime-install",
                language="cpp",
                apply=False,
                platform="linux",
            ))
        self.assertEqual(rc, 0)

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = dispatch(_NS(
                _experimental_cmd="runtime-plan",
                language="go",
                platform="macos",
            ))
        self.assertEqual(rc, 0)


# ----------------------------------------------------------------------
# Doctor integration — the polyglot section doesn't crash on any host.
# ----------------------------------------------------------------------


class DoctorPolyglotSectionTests(unittest.TestCase):
    """`minxg doctor` adds a Polyglot runtimes panel; we assert the
    public threshold: at least one row per managed language, never
    a FAIL status.
    """

    def test_doctor_section_lists_every_managed_language(self):
        from multiligua_cli.doctor import _check_polyglot_runtimes
        rows = _check_polyglot_runtimes()
        # First row is the probe row; the rest are per-language.
        self.assertGreaterEqual(len(rows), 7)
        keys = [r[0] for r in rows]
        for lang in ("cpp", "go", "wasm", "r", "julia", "datalog"):
            self.assertTrue(
                any(k.startswith(f"runtime {lang}") for k in keys),
                f"missing row for {lang}: {keys!r}",
            )
        statuses = [r[1] for r in rows]
        self.assertNotIn("FAIL", statuses)
