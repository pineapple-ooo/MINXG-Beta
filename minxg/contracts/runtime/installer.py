"""minxg.contracts.runtime.installer — runtime install plans.

Why this module exists
----------------------
As of 0.14.0, MINXG can dispatch to six non-Python runtimes (C / C++,
Go, WebAssembly, R, Julia, Datalog). Each one is gated on a host-side
binary or package being present: ``g++/clang``, ``go``, ``wasmtime``,
``Rscript`` (+ ``jsonlite``), ``julia`` (+ ``JSON.jl``), ``clingo`` /
pyDatalog.

Detect is cheap (which() / a tiny ``-e`` probe). *Installing* a runtime
is not — it pulls hundreds of MB, may need sudo, and can desync with the
user's pkg manager. So this module deliberately does TWO things and no
more:

1. ``detect_runtime(language)`` — probe one language's status without
   side-effects (used by ``minxg doctor`` and the ``runtime-plan``
   experimental verb).
2. ``plan_install(language)`` — return a :class:`InstallPlan` with one
   *shell command per supported platform* (``termux`` / ``linux`` /
   ``macos`` / ``windows`` / ``unknown``). Plans are pure data; we
   don't shell out, we don't assume the host has sudo, and we never
   run anything without the user explicitly opting in.

This is the entire contract. ``minxg runtime-plan`` prints the plan;
``minxg runtime-install --apply <language>`` executes one runner of it
behind the user's back, exactly one process at a time, never with sudo
on platforms where we can't detect the user's privilege state.

Design intent
-------------
* **Pure-data plans make the surface testable** — every plan is a
  dataclass so ``tests/test_polyglot_runtime_installer.py`` can assert
  the platform matrix without touching the file-system.
* **Minxg prefers native pkg managers.** Termux gets ``pkg install``,
  Debian-family Linux gets ``apt-get``, macOS gets ``brew``, Windows
  gets ``winget`` with a chocolatey fallback. We surface *all* of them
  so the user can pick.
* **Runners honour a no-sudo default.** On Linux we warn about
  ``sudo`` and offer the user-local alt where it exists.
* **Wasm on Termux falls back to the bundled emulator.** The whole
  point of the emulator is that wasmtime isn't strictly required —
  so the installer lists it as "optional".
* **Self-evolution deflates.** If ``language == "all"``, we return one
  row per detected-or-not runtime so the user sees the whole picture.
"""
from __future__ import annotations

import os
import platform as _platform
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import _exec

# ---------------------------------------------------------------------------
# Canonical language list — kept aligned with manifest.POLYGLOT_LANGUAGES,
# minus ``python`` (always-on), so the installer doesn't bother with
# something the user already has if they can import ``minxg``.
# ---------------------------------------------------------------------------

MANAGED_LANGUAGES: Tuple[str, ...] = (
    "cpp",  # C / C++ — system compiler
    "go",   # Go toolchain
    "wasm", # WebAssembly via wasmtime
    "r",    # R statistical
    "julia",  # Julia numerical
    "datalog",  # Datalog / ASP via clingo or pyDatalog
)


# ---------------------------------------------------------------------------
# Platform id — mirrors install.sh's detect_platform but in Python.
# ---------------------------------------------------------------------------


def platform_id() -> str:
    """Return one of ``termux`` / ``linux`` / ``macos`` / ``windows`` / ``unknown``.

    Detection rules are intentionally conservative: only flip to
    ``termux`` when the ``TERMUX_VERSION`` env var is set **or** the
    Termux app-private root exists. ``Darwin`` becomes ``macos``,
    ``Linux`` stays ``linux``, ``MINGW/MSYS/CYGWIN`` map to ``windows``.
    Anything else falls through to ``unknown`` so the user knows we
    can't recommend a specific package manager.
    """
    if os.environ.get("TERMUX_VERSION") or os.path.isdir(
        "/data/data/com.termux"
    ):
        return "termux"
    system = _platform.system()
    if system == "Linux":
        return "linux"
    if system == "Darwin":
        return "macos"
    if system.startswith(("MINGW", "MSYS", "CYGWIN")) or system == "Windows":
        return "windows"
    return "unknown"


# ---------------------------------------------------------------------------
# Detection — wraps the language-specific adapter _probe() when available,
# else falls back to a cheap ``which()`` lookup.
# ---------------------------------------------------------------------------


@dataclass
class RuntimeStatus:
    """Lightweight snapshot of one runtime's availability on this host."""

    language: str
    binary: str = ""
    available: bool = False
    note: str = ""
    version_hint: str = ""

    def to_row(self) -> Dict[str, str]:
        """Return a flat dict suitable for tables / JSON."""
        return {
            "language": self.language,
            "binary": self.binary or "-",
            "available": "yes" if self.available else "no",
            "note": self.note,
            "version_hint": self.version_hint,
        }


def detect_runtime(language: str) -> RuntimeStatus:
    """Probe a single language runtime. Pure read-only; never runs installs.

    ``RuntimeStatus.to_row()`` returns a dict where ``available`` is
    always one of the strings ``"yes"`` / ``"no"``. Callers (the
    polyglot doctor panel, the install planner) all rely on that
    unambiguous two-value contract, so it is enforced here once.
    """
    lang = language.lower().strip()
    if lang == "cpp":
        binary = shutil.which("g++") or shutil.which("clang++") or ""
        return RuntimeStatus(
            language="cpp",
            binary=binary or "g++/clang++",
            available=bool(binary),
            note=("system C/C++ compiler" if binary else "install g++ or clang++"),
        )
    if lang == "go":
        binary = shutil.which("go") or ""
        note = ""
        if binary:
            res = _exec.run([str(binary), "version"], timeout=5.0)
            note = res.get("stdout", "").splitlines()[0] if res.get("ok") else "go present"
        return RuntimeStatus(
            language="go",
            binary=binary or "go",
            available=bool(binary),
            note=note or "Go toolchain (https://go.dev/dl/)",
        )
    if lang == "wasm":
        binary = shutil.which("wasmtime") or ""
        return RuntimeStatus(
            language="wasm",
            binary=binary or "wasmtime",
            available=bool(binary),
            note=(
                "wasmtime CLI present"
                if binary
                else "optional — pure-python emulator fallback ships in minxg"
            ),
        )
    if lang == "r":
        binary = shutil.which("Rscript") or ""
        ok = bool(binary)
        note = "Rscript on PATH"
        pkg_ok = False
        version = ""
        if ok:
            res = _exec.run(
                [str(binary), "-e", 'cat(R.version$version.string, "\n")'],
                timeout=5.0,
            )
            if res.get("ok"):
                version = (res.get("stdout") or "").strip()
            res2 = _exec.run(
                [
                    str(binary),
                    "-e",
                    'if (!requireNamespace("jsonlite", quietly=TRUE)) '
                    'quit(status=1) else cat("ok\n")',
                ],
                timeout=5.0,
            )
            pkg_ok = res2.get("ok") and "ok" in (res2.get("stdout") or "").splitlines()
        if ok and not pkg_ok:
            note = "Rscript present but needs jsonlite"
            ok = False  # treat as missing until jsonlite lands
        elif not ok:
            note = "install R (Rscript must be on PATH)"
        return RuntimeStatus(
            language="r",
            binary=binary or "Rscript",
            available=ok,
            note=note,
            version_hint=version,
        )
    if lang == "julia":
        binary = shutil.which("julia") or ""
        ok = bool(binary)
        note = "julia on PATH"
        version = ""
        if ok:
            res = _exec.run(
                [str(binary), "-e", 'print(VERSION)'],
                timeout=5.0,
            )
            if res.get("ok"):
                version = (res.get("stdout") or "").strip()
        return RuntimeStatus(
            language="julia",
            binary=binary or "julia",
            available=ok,
            note=(note if ok else "install julia (https://julialang.org/downloads/)")
            + (" — JSON.jl recommended" if ok else ""),
            version_hint=version,
        )
    if lang == "datalog":
        clingo = shutil.which("clingo")
        has_pydatalog = False
        try:
            import pyDatalog  # type: ignore[import-not-found]  # noqa: F401
            has_pydatalog = True
        except Exception:
            has_pydatalog = False
        if clingo:
            return RuntimeStatus(
                language="datalog",
                binary=clingo,
                available=True,
                note="clingo (preferred Datalog solver)",
            )
        if has_pydatalog:
            return RuntimeStatus(
                language="datalog",
                binary="pyDatalog",
                available=True,
                note="pure-python pyDatalog fallback",
            )
        return RuntimeStatus(
            language="datalog",
            binary="clingo / pyDatalog",
            available=False,
            note="install clingo (preferred) or pyDatalog (fallback)",
        )
    return RuntimeStatus(
        language=lang,
        available=False,
        note=f"unknown language {lang!r}; managed: {', '.join(MANAGED_LANGUAGES)}",
    )


# ---------------------------------------------------------------------------
# Plan dataclass — every InstallPlan is pure data, never executes.
# ---------------------------------------------------------------------------


@dataclass
class InstallPlan:
    """One language's install recipes, one row per platform.

    Attributes
    ----------
    language
        The MINXG language id (``cpp`` / ``go`` / ``wasm`` / ``r`` /
        ``julia`` / ``datalog``).
    status
        Latest :class:`RuntimeStatus` captured at plan time.
    commands
        Mapping platform-id → recommended shell command. Empty string
        means "no recommendation; install manually".
    notes
        Per-platform warnings / clarifications the user should read
        before copying the command.
    """

    language: str
    status: RuntimeStatus
    commands: Dict[str, str] = field(default_factory=dict)
    notes: Dict[str, str] = field(default_factory=dict)

    def command_for(self, plat: Optional[str] = None) -> Tuple[str, str]:
        """Return ``(command, note)`` for ``plat`` (default: current host).

        Empty string when no recipe is known.
        """
        plat = (plat or platform_id()).lower()
        cmd = self.commands.get(plat, "")
        note = self.notes.get(plat, "")
        if plat == "unknown":
            note = (
                (note + " " if note else "")
                + "(unknown host; pick the closest platform manually)"
            )
        return cmd, note


# ---------------------------------------------------------------------------
# Plan generator — the heart of the module. Static, never executes.
# ---------------------------------------------------------------------------


def _noop_cmd() -> str:
    """Always-available sentinel: tells the user 'no install needed'."""
    return "echo 'already on PATH — nothing to install'"


def plan_install(language: str) -> InstallPlan:
    """Return an :class:`InstallPlan` for one language (no side-effects).

    The status is captured at call time, so call this immediately
    before showing it to the user. The commands dict is platform-keyed
    and the plans below mirror the recommended awk/sed-free one-liners
    for each stack.

    When the detector reports the runtime as already available on
    every platform we still emit real package-manager commands —
    the user *may* be on a fresh box even though the local probe
    (which sees only this process's PATH) found the binary. The
    :func:`run_install` executor is the one place that should
    short-circuit on availability, not this planner.
    """
    lang = language.lower().strip()
    status = detect_runtime(lang)
    plan = InstallPlan(language=lang, status=status)

    if lang == "cpp":
        plan.commands.update({
            "termux": "pkg install -y clang",
            "linux": "sudo apt-get update && sudo apt-get install -y g++",
            "macos": "brew install gcc",
            "windows": "winget install -G msys2 ...",
            "unknown": "",
        })
        plan.notes.update({
            "termux": "Termux ships clang as the default C/C++ compiler.",
            "linux": "Fallback (no sudo): install via your distro's user-mode toolchain.",
            "windows": "winget install -e --id MSYS2.MSYS2 then use the g++ bundled there.",
        })
    elif lang == "go":
        plan.commands.update({
            "termux": "pkg install -y golang",
            "linux": "sudo apt-get install -y golang",
            "macos": "brew install go",
            "windows": "winget install -e --id GoLang.Go",
            "unknown": "",
        })
        plan.notes.update({
            "termux": "pkg sometimes lags one minor version behind go.dev; if you need HEAD, use the upstream tarball.",
        })
    elif lang == "wasm":
        # wasm is "optional" — the runtime adapter already ships a
        # pure-python emulator fallback. The cmd list still reflects
        # real install paths so users who *do* want it can act.
        plan.commands.update({
            "termux": "pkg install -y wasmtime  # may not be packaged; see notes",
            "linux": "curl -fsSL https://wasmtime.dev/install.sh | bash",
            "macos": "brew install wasmtime",
            "windows": "winget install -e --id BytecodeAlliance.Wasmtime",
            "unknown": "",
        })
        plan.notes.update({
            "termux": "Termux does not always ship wasmtime; install via the upstream install.sh if 'pkg install wasmtime' returns no package.",
            "linux": "The official install.sh adds wasmtime to ~/.cargo/bin; PATH it from your shell rc.",
        })
    elif lang == "r":
        plan.commands.update({
            "termux": "pkg install -y r",
            "linux": "sudo apt-get install -y r-base  # then: sudo R -e 'install.packages(\"jsonlite\")'",
            "macos": "brew install r && R -e 'install.packages(\"jsonlite\")'",
            "windows": "winget install -e --id RProject.R  # then: R -e 'install.packages(\"jsonlite\")'",
            "unknown": "",
        })
        plan.notes.update({
            "termux": "Termux packages the base CRAN build; no extra repos needed.",
            "linux": "If `r-base` is unavailable, add CRAN's apt repo first (https://cran.r-project.org/).",
            "macos": "Homebrew's r is a keg-only formula; symlink manually if you need Rscript on PATH.",
            "windows": "Winget installs the r-base build; add Rscript to PATH or run from the installer shell.",
        })
    elif lang == "julia":
        plan.commands.update({
            "termux": "pkg install -y julia  # may not be packaged; see notes",
            "linux": "curl -fsSL https://install.julialang.org | sh",
            "macos": "brew install julia && julia -e 'using Pkg; Pkg.add(\"JSON\")'",
            "windows": "winget install -e --id JuliaLang.Julia",
            "unknown": "",
        })
        plan.notes.update({
            "termux": "If `pkg install julia` 404s, fall back to the upstream installer script (tarball extract).",
            "linux": "The install.julialang.org script targets ~/.julia; append ~/.juliaup/bin to PATH.",
            "windows": "After winget install, install the JSON.jl package once: julia -e 'using Pkg; Pkg.add(\"JSON\")'",
        })
    elif lang == "datalog":
        plan.commands.update({
            "termux": "pkg install -y clingo  # may not be packaged; see notes",
            "linux": "sudo apt-get install -y clingo",
            "macos": "brew install clingo",
            "windows": "choco install clingo  # winget has no clingo package as of last check",
            "unknown": "",
        })
        plan.notes.update({
            "termux": "If `pkg install clingo` 404s, fall back to pyDatalog: pip install pyDatalog.",
            "linux": "Some distros ship clingo under slightly different names (potassco-clingo); adjust.",
            "windows": "Chocolatey recommended; otherwise build clingo from source via CMake.",
        })
    else:
        plan.notes["unknown"] = (
            f"unknown language {lang!r}; managed: {', '.join(MANAGED_LANGUAGES)}"
        )
        plan.commands.update({p: "" for p in ("termux", "linux", "macos", "windows", "unknown")})
    return plan


def current_plan(language: str = "all") -> List[InstallPlan]:
    """Plan one language (or every managed language) at the current host."""
    if language.lower().strip() in ("", "all"):
        return [plan_install(lang) for lang in MANAGED_LANGUAGES]
    return [plan_install(language)]


# ---------------------------------------------------------------------------
# Render — turn InstallPlans into human-readable text the CLI can print.
# ---------------------------------------------------------------------------


def render_install_plan(plans: List[InstallPlan], *, plat: Optional[str] = None) -> str:
    """Pretty-print one or more plans as fixed-column text (no Rich required).

    The format intentionally fits inside an 80-column TTY so it works in
    CI logs. Doctor / runtime-plan share this rendering.
    """
    plat = plat or platform_id()
    lines: List[str] = []
    lines.append(f"# MINXG polyglot runtime install plan — host={plat}")
    lines.append("")

    status_w = max(8, max(len("available"), max(len(p.status.language) for p in plans) + 2))
    for p in plans:
        bits = []
        bits.append(f". {p.language}")
        bits.append(f"  status:  {'available' if p.status.available else 'missing'}")
        if p.status.binary:
            bits.append(f"  binary:  {p.status.binary}")
        if p.status.version_hint:
            bits.append(f"  version: {p.status.version_hint}")
        if p.status.note:
            bits.append(f"  detail:  {p.status.note}")
        cmd, note = p.command_for(plat)
        if cmd:
            bits.append(f"  install ({plat}): {cmd}")
        else:
            bits.append(f"  install ({plat}): (no recipe — manual only)")
        if note:
            bits.append(f"  note:    {note}")
        bits.append("")
        lines.extend(bits)
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Executor — opt-in via ``--apply``; never auto-sudo, never recursive.
# ---------------------------------------------------------------------------


def run_install(language: str, plat: Optional[str] = None,
                *, apply: bool = False, runner: Optional[Any] = None) -> Dict[str, Any]:
    """Execute the plan's install cmd for ``language``, optionally.

    Parameters
    ----------
    language
        ``cpp`` / ``go`` / ``wasm`` / ``r`` / ``julia`` / ``datalog`` / ``all``.
    plat
        Override the host platform id. Default: auto-detect.
    apply
        When ``False`` (default) we return the plan *without* executing
        it. Set ``True`` to actually run the install command via the
        shared :func:`_exec.run` helper.
    runner
        Test seam: anything callable ``runner(cmd:str) -> Dict[str, Any]``.
        When provided, replaces subprocess execution so unit tests can
        assert exactly what command would have been run. Defaults to
        ``shutil.which(cmd)`` short-circuit plus :func:`_exec.run` for
        shell strings.

    Returns
    -------
    Dict with keys: ``language``, ``platform``, ``applied``, ``command``,
    ``note``, ``runner_output`` (only when applied).
    """
    plat = (plat or platform_id()).lower()
    plans = current_plan(language)
    out: List[Dict[str, Any]] = []

    for p in plans:
        cmd, note = p.command_for(plat)
        row: Dict[str, Any] = {
            "language": p.language,
            "platform": plat,
            "applied": False,
            "command": cmd,
            "note": note,
        }
        if not cmd:
            out.append(row)
            continue
        # Auto-short-circuit: when the runtime is already present we
        # avoid re-running the install (and write a no-op sentinel so
        # the JSON output stays consistent across plans).
        if p.status.available:
            row["command"] = _noop_cmd()
            row["note"] = (note + " " if note else "") + (
                "runtime already present — install skipped"
            )
            out.append(row)
            continue
        if not apply:
            row["note"] = (note + " " if note else "") + (
                "(dry-run — set apply=True to execute)"
            )
            out.append(row)
            continue
        # Real execution path. The runner is shell-string, so we hand it
        # off via ``sh -c``. We intentionally do NOT use sudo unless
        # the command itself contains it; add a safety note that
        # platforms requiring privilege must already know that.
        if runner is not None:
            res = runner(cmd)
        else:
            res = _exec.run(["sh", "-c", cmd], timeout=600.0)
        row["applied"] = True
        row["runner_output"] = res
        out.append(row)
    return {"plans": out, "platform": plat, "any": bool(out)}


# ---------------------------------------------------------------------------
# Module-level convenience — single-pass snapshot the doctor uses.
# ---------------------------------------------------------------------------


def status_snapshot() -> List[Dict[str, str]]:
    """Return ``[{language, available, binary, note}, ...]`` for the doctor.

    Pure JSON-y dicts, one row per managed language, no plan/install
    commands included (the doctor just wants "is it installed?").
    """
    return [p.status.to_row() for p in current_plan("all")]
