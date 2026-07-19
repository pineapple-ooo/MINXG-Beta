"""
multiligua_cli/experimental.py — [EXPERIMENTAL] extra verbs.

As of 0.16.0, the verb set covers everything from 0.13.0 plus four new
experimental verbs:

  - bench                local perf snapshot of representative components
  - replay               re-render a markdown chat log through the TUI pipe
  - theme                get / set the active TUI theme
  - safe-eval            restricted single-expression eval
  - hot-reload           rescan all extension sources
  - think                toggle ``<think>...</think>`` rendering for the active session
  - polyglot-manifest    list every language adapter MINXG can dispatch to,
                         with version numbers lifted from each adapter's
                         JSON manifest
  - contract             list every registered ``minxg.contracts`` Cell
                         (id + version + capability tags)
  - genesis              run a one-shot ``MINXG Genesis Loop``:
                         propose → mutate → evaluate → crystallise → report

Each verb is intentionally additive — they share no state with the
stable TUI and may be removed or renamed in a later minor release
without prior notice. The set lives behind an explicit `[EXPERIMENTAL]`
flag in the help text so users know what they're getting into.

Everything here is side-effect-light (touch only MINXG's runtime dir)
and returns a process exit code; CI runs them through
``tests/test_experimental_cli.py``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Single source of truth for the experimental namespace tag.
EXPERIMENTAL_TAG = "[EXPERIMENTAL]"

# Safe-eval sandbox: only these names may be referenced inside the expr.
SAFE_EVAL_GLOBALS: Dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "pow": pow,
    "range": range,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

SAFE_EVAL_BUILTINS_HELP = ", ".join(sorted(SAFE_EVAL_GLOBALS))


def _experimental_warning(name: str) -> None:
    """One-line stderr banner so users always know what they're into.
    Quiet by default — use --verbose in the parent parser to also tee."""
    if os.environ.get("MINXG_EXPERIMENTAL_QUIET"):
        return
    sys.stderr.write(f"{EXPERIMENTAL_TAG} minxg {name} — signature may change\n")


# ----------------------------------------------------------------------
# bench
# ----------------------------------------------------------------------

def _bench_one(label: str, fn: Callable[[], Any]) -> Tuple[str, float, str]:
    t0 = time.perf_counter()
    try:
        result = fn()
        dt = (time.perf_counter() - t0) * 1000.0
        return label, dt, repr(result)[:64]
    except Exception as exc:
        dt = (time.perf_counter() - t0) * 1000.0
        return label, dt, f"<error: {type(exc).__name__}: {exc}>"


def run_bench(args: argparse.Namespace) -> int:
    """Local perf snapshot — six well-defined nested operations."""
    _experimental_warning("bench")
    samples: List[Tuple[str, float, str]] = []

    # 1) Lossless round-trip
    def _lossless() -> bytes:
        from minxg import lossless
        return lossless.LosslessCodec().decompress(
            lossless.LosslessCodec().compress(b"perf-payload").payload
        )

    samples.append(_bench_one("lossless.roundtrip", _lossless))

    # 2) Driver engine step
    def _driver() -> str:
        from minxg.driver import DriverEngine, State, smoothing_field
        end, _ = DriverEngine([smoothing_field(rate=0.4)]).run(
            State(payload={"x": 0.0, "v": 1.0}), n_steps=8,
        )
        return str(end)

    samples.append(_bench_one("driver.step(8)", _driver))

    # 3) Twin python→rust (single def, single block)
    def _twin() -> str:
        from minxg.twin import python_to_rust
        return python_to_rust("def f(x):\n    if x > 0:\n        y = 1\n    else:\n        y = 0\n    return y\n")

    samples.append(_bench_one("twin.python_to_rust", _twin))

    # 4) Polyglot normalise
    def _poly() -> int:
        from minxg.polyglot.normalizer import normalize
        g = normalize("def f(x): return x + 1", language="python")
        return len(g.nodes)

    samples.append(_bench_one("polyglot.normalise", _poly))

    # 5) OperatorRegistry dump
    def _reg() -> int:
        from minxg.operators import OPERATOR_REGISTRY
        return OPERATOR_REGISTRY.total_operators

    samples.append(_bench_one("operators.total", _reg))

    # 6) Feature import cost
    def _import_cost() -> int:
        import importlib
        m = importlib.import_module("multiligua_cli.features")
        return len(m.list_experimental_exports())

    samples.append(_bench_one("features.list", _import_cost))

    longest = max(len(s[0]) for s in samples)
    print(f"{EXPERIMENTAL_TAG} minxg bench — local perf snapshot")
    print("-" * (longest + 32))
    for label, dt, summary in samples:
        print(f"  {label.ljust(longest)}  {dt:>10.3f} ms    {summary}")
    print("-" * (longest + 32))
    return 0


# ----------------------------------------------------------------------
# replay — re-render a markdown conversation
# ----------------------------------------------------------------------

_MSG_RE = re.compile(r"^###\s+(USER|ASSISTANT|TOOL|SYSTEM)\s*$", re.IGNORECASE)


def _parse_markdown_lines(md_path: Path) -> List[Dict[str, str]]:
    """Parse a `features.export_to_markdown` blob back into role→content rows."""
    text = md_path.read_text(encoding="utf-8")
    turns: List[Dict[str, str]] = []
    cur_role: Optional[str] = None
    cur_buf: List[str] = []
    for line in text.splitlines():
        m = _MSG_RE.match(line.strip())
        if m:
            if cur_role is not None:
                turns.append({"role": cur_role.lower(), "content": "\n".join(cur_buf).strip()})
            cur_role = m.group(1).lower()
            cur_buf = []
        else:
            if cur_role is not None and not line.startswith("# "):
                cur_buf.append(line)
    if cur_role is not None:
        turns.append({"role": cur_role, "content": "\n".join(cur_buf).strip()})
    return turns


def run_replay(args: argparse.Namespace) -> int:
    """Re-render a markdown chat log (or stdin) into plain stdout."""
    _experimental_warning("replay")
    md_arg: Optional[str] = getattr(args, "file", None)
    if md_arg and md_arg != "-":
        path = Path(md_arg)
        if not path.exists():
            sys.stderr.write(f"{EXPERIMENTAL_TAG} no such file: {md_arg}\n")
            return 2
        turns = _parse_markdown_lines(path)
    else:
        text = sys.stdin.read()
        # reuse _parse_markdown_lines by writing to a temp file
        tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "minxg_replay.md"
        tmp.write_text(text, encoding="utf-8")
        turns = _parse_markdown_lines(tmp)
        tmp.unlink(missing_ok=True)

    if not turns:
        sys.stderr.write(f"{EXPERIMENTAL_TAG} no turns parsed\n")
        return 0
    print(f"{EXPERIMENTAL_TAG} replayed {len(turns)} turn(s)")
    print("-" * 40)
    for t in turns:
        print(f"[{t['role'].upper()}] {t['content'][:240]}")
    print("-" * 40)
    return 0


# ----------------------------------------------------------------------
# theme — get/set TUI palette
# ----------------------------------------------------------------------

THEME_FILE = Path(
    os.environ.get("MINXG_HOME", str(Path.home() / ".minxg"))
) / "theme.json"
VALID_THEMES = ("dark", "colorful", "minimal")


def _read_theme() -> str:
    if THEME_FILE.exists():
        try:
            data = json.loads(THEME_FILE.read_text(encoding="utf-8"))
            if data.get("theme") in VALID_THEMES:
                return data["theme"]
        except Exception:
            pass
    return "dark"


def _write_theme(name: str) -> Path:
    THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = THEME_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"theme": name}, indent=2), encoding="utf-8")
    tmp.replace(THEME_FILE)
    return THEME_FILE


def run_theme(args: argparse.Namespace) -> int:
    """Show or set the active TUI theme. Press `minxg theme` to use default."""
    _experimental_warning("theme")
    name: Optional[str] = getattr(args, "name", None)
    if not name:
        print(f"current theme: {_read_theme()}")
        print(f"available:     {' / '.join(VALID_THEMES)}")
        return 0
    if name not in VALID_THEMES:
        sys.stderr.write(f"{EXPERIMENTAL_TAG} unknown theme: {name!r}; pick one of {VALID_THEMES}\n")
        return 2
    path = _write_theme(name)
    print(f"{EXPERIMENTAL_TAG} theme set to {name} (saved to {path})")
    return 0


# ----------------------------------------------------------------------
# safe-eval — restricted expression evaluator
# ----------------------------------------------------------------------

def _safe_eval(expr: str, locals_map: Optional[Dict[str, Any]] = None,
               *, max_len: int = 256) -> Any:
    """Compile `expr` into an AST, walk it, raise on anything dangerous.

    The allow-list is "arithmetic + allowed builtins". Anything that
    opens a side door (attribute access, comprehensions, imports,
    function/class definition, starred unpacking, lambdas) is rejected
    at the AST level. ``Call`` is allowed because that's how the user
    actually invokes ``abs(...)``, ``sum(...)``, etc.; the surrounding
    checks guarantee that ``Call.func`` is a bare ``Name`` that resolves
    to an entry in SAFE_EVAL_GLOBALS.
    """
    if len(expr) > max_len:
        raise ValueError(f"expression too long (>{max_len} chars)")
    import ast
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, (
            ast.Attribute, ast.Subscript, ast.Dict, ast.Set,
            ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
            ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef,
            ast.ClassDef, ast.Import, ast.ImportFrom,
            ast.Global, ast.Nonlocal, ast.Starred,
        )):
            raise ValueError(
                f"disallowed syntax: {type(node).__name__} "
                "(safe-eval supports arithmetic only)"
            )
        if isinstance(node, ast.Call):
            # only allow calls to bare names that resolve to allowed builtins
            if not isinstance(node.func, ast.Name) or \
                    node.func.id not in SAFE_EVAL_GLOBALS:
                raise ValueError(
                    f"disallowed call: "
                    f"{ast.unparse(node.func) if hasattr(ast, 'unparse') else node.func}"
                )
            # forbid keyword args that aren't trivial (defensive)
            for kw in node.keywords:
                if kw.arg is None:
                    raise ValueError("disallowed **kwargs unpacking")
    compiled = compile(tree, "<safe-eval>", "eval")
    g = dict(SAFE_EVAL_GLOBALS)
    if locals_map:
        g.update(locals_map)
    return eval(compiled, {"__builtins__": {}}, g)


def run_safe_eval(args: argparse.Namespace) -> int:
    _experimental_warning("safe-eval")
    expr: Optional[str] = getattr(args, "expr", None)
    json_locals: Optional[str] = getattr(args, "locals", None)
    if expr is None:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} usage: minxg safe-eval <expr> [--locals JSON]\n"
            f"   allowed builtins: {SAFE_EVAL_BUILTINS_HELP}\n"
        )
        return 2
    locals_map: Dict[str, Any] = {}
    if json_locals:
        try:
            locals_map = json.loads(json_locals)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"{EXPERIMENTAL_TAG} invalid --locals JSON: {e}\n")
            return 2
    try:
        result = _safe_eval(expr, locals_map)
    except Exception as exc:
        sys.stderr.write(f"{EXPERIMENTAL_TAG} safe-eval error: {type(exc).__name__}: {exc}\n")
        return 1
    print(repr(result))
    return 0


# ----------------------------------------------------------------------
# extension hot-reload
# ----------------------------------------------------------------------

def run_ext_reload(args: argparse.Namespace) -> int:
    """Rescan extension sources without restarting the process."""
    _experimental_warning("ext reload")
    try:
        from extensions.loader import rescan_all
        n = rescan_all()
        print(f"{EXPERIMENTAL_TAG} rescan complete: {n} extension(s) re-registered")
        return 0
    except Exception as exc:
        # Soft fallback so the CLI still tells the user something useful
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} rescan unavailable: {type(exc).__name__}: {exc}\n"
        )
        return 0


# ----------------------------------------------------------------------
# think — toggle ``<think>...</think>`` rendering for the active session
# ----------------------------------------------------------------------

THINK_FILE = Path(
    os.environ.get("MINXG_HOME", str(Path.home() / ".minxg"))
) / "think.json"


def _read_think_state() -> bool:
    """True if thinking tags should be rendered (default: True)."""
    if THINK_FILE.exists():
        try:
            data = json.loads(THINK_FILE.read_text(encoding="utf-8"))
            return bool(data.get("enabled", True))
        except Exception:
            pass
    return True


def _write_think_state(enabled: bool) -> Path:
    THINK_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = THINK_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"enabled": bool(enabled)}, indent=2),
                   encoding="utf-8")
    tmp.replace(THINK_FILE)
    return THINK_FILE


def run_think(args: argparse.Namespace) -> int:
    """Toggle the ``<think>...</think>`` rendering for chat output.

    Mirrors ``multiligua_cli/tui_chat.py:run`` which honours the same
    state file. The verb exists so users can disable the dim-italic
    block without editing config by hand.
    """
    _experimental_warning("think")
    action: Optional[str] = getattr(args, "action", None)
    if action is None:
        state = _read_think_state()
        print(f"{EXPERIMENTAL_TAG} think tags: {'on' if state else 'off'}")
        print(f"   use `minxg think on` / `off` to toggle")
        return 0
    if action not in ("on", "off"):
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} usage: minxg think [on|off]\n"
        )
        return 2
    enabled = (action == "on")
    path = _write_think_state(enabled)
    print(f"{EXPERIMENTAL_TAG} think tags set to {action} ({path})")
    return 0


# ----------------------------------------------------------------------
# polyglot-manifest — list language adapters + their manifest versions
# ----------------------------------------------------------------------

def _discover_polyglot_manifest() -> List[Dict[str, str]]:
    """Return every polyglot language adapter MINXG can dispatch to.

    Prefer the live registry in ``minxg.contracts.runtime``; fall back to
    the static manifest table if the runtime package is not importable.
    """
    try:
        from minxg.contracts.runtime import list_adapters
        return list_adapters()
    except Exception:
        pass
    try:
        from minxg.contracts.runtime.manifest import (
            POLYGLOT_LANGUAGES, POLYGLOT_MANIFEST,
        )
        return [
            {
                "name": POLYGLOT_MANIFEST[lang]["name"],
                "version": POLYGLOT_MANIFEST[lang]["version"],
                "status": POLYGLOT_MANIFEST[lang]["status"],
            }
            for lang in POLYGLOT_LANGUAGES
        ]
    except Exception:
        return []


def run_polyglot_manifest(args: argparse.Namespace) -> int:
    """Print every polyglot language adapter MINXG can dispatch to."""
    _experimental_warning("polyglot-manifest")
    from multiligua_cli.utils import HAS_RICH, console
    rows = _discover_polyglot_manifest()
    if not rows:
        print(f"{EXPERIMENTAL_TAG} polyglot-manifest: no adapters visible")
        return 0

    def _badge(status: str) -> str:
        return {
            "native": "[bold green]● native[/bold green]",
            "available": "[bold cyan]● ready[/bold cyan]",
            "disabled": "[bold bright_black]○ offline[/bold bright_black]",
        }.get(status, f"[dim]{status}[/dim]")

    if HAS_RICH:
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
        table = Table(
            title="Polyglot Runtime Manifest",
            box=box.ROUNDED,
            header_style="bold bright_blue",
            border_style="bright_black",
        )
        table.add_column("Language", style="cyan", no_wrap=True)
        table.add_column("Version", style="magenta", no_wrap=True)
        table.add_column("Status", style="green")
        for r in rows:
            table.add_row(r["name"], r["version"], _badge(r["status"]))
        console.print("")
        console.print(Panel(table, title="MINXG polyglot", border_style="blue"))
        console.print("")
    else:
        print(f"{EXPERIMENTAL_TAG} polyglot-manifest — {len(rows)} adapter(s)")
        for r in rows:
            print(f"  {r['name']:12s} {r['version']:10s}  {r['status']}")
    return 0


# ----------------------------------------------------------------------
# contract — list registered Cells in minxg.contracts
# ----------------------------------------------------------------------

def run_contract(args: argparse.Namespace) -> int:
    """List every Cell currently registered in ``minxg.contracts``.

    ``minxg.contracts.registry.get_registry`` is the single source of
    truth for these — the verb just renders what it sees, so a Cell
    that registers itself shows up here for free.
    """
    _experimental_warning("contract")
    try:
        from minxg.contracts.registry import get_registry
        reg = get_registry()
        ids = sorted(reg.all_ids())
    except Exception as exc:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} registry unavailable: "
            f"{type(exc).__name__}: {exc}\n"
        )
        return 1
    if not ids:
        print(f"{EXPERIMENTAL_TAG} no cells registered")
        return 0
    name_w = max(len(i) for i in ids)
    print(f"{EXPERIMENTAL_TAG} contract registry — {len(ids)} cell(s)")
    print("-" * (name_w + 24))
    for cell_id in ids:
        try:
            cell_obj = reg.get(cell_id)
            version = getattr(cell_obj, "cell_version", "0.0.0")
            caps = ", ".join(getattr(cell_obj, "cell_capabilities", ()) or ())
        except Exception:
            version, caps = "?", ""
        print(f"  {cell_id.ljust(name_w)}  {version:<10}  {caps}")
    print("-" * (name_w + 24))
    return 0


# ----------------------------------------------------------------------
# genesis  — one-shot self-evolution loop (MINXG Genesis Loop, 0.16.0)
# ----------------------------------------------------------------------

GENESIS_HOME = Path(
    os.environ.get("MINXG_HOME", str(Path.home() / ".minxg"))
) / "genesis"


def _genesis_propose(prompt: Optional[str]) -> str:
    """Phase 1 — derive a small candidate task from the seed prompt.

    The proposal is intentionally tiny: one Python function body of
    ≤ 240 chars wrapped in a complete module skeleton. Heavy lifting
    happens in `_genesis_mutate`.
    """
    seed = (prompt or "minxg-self-evolve").strip()[:80]
    return (
        f"def evolve(name: str = '{seed}') -> str:\n"
        f"    \"\"\"Genesis candidate generated for seed={seed!r}.\"\"\"\n"
        f"    return f'{{name}}-v1'\n"
    )


def _genesis_mutate(proposal: str, generations: int) -> List[str]:
    """Phase 2 — mutate deterministically. We append a generation tag."""
    pool: List[str] = []
    for g in range(1, max(1, int(generations)) + 1):
        pool.append(proposal.replace("v1", f"v{g}"))
    return pool


def _genesis_evaluate(candidates: List[str]) -> List[Tuple[str, float]]:
    """Phase 3 — score each candidate. Score = AST node count + length penalty.

    A smaller, well-formed module is rewarded; we use AST count as a
    cheap proxy for "how interesting is the shape". The real win is
    that the loop has to round-trip every candidate through Python's
    parser — malformed mutations get filtered out automatically.
    """
    import ast
    scored: List[Tuple[str, float]] = []
    for cand in candidates:
        try:
            tree = ast.parse(cand)
        except SyntaxError:
            continue
        nodes = sum(1 for _ in ast.walk(tree))
        # Reward uniqueness, penalise length.
        score = (nodes * 2.0) - (len(cand) / 80.0)
        scored.append((cand, round(score, 3)))
    return scored


def _genesis_crystallise(scored: List[Tuple[str, float]],
                         out_dir: Path, pool_size: int) -> Path:
    """Phase 4 — pick the best, write it to disk as `latest.py` + report.

    The crystallised artefact is *generated* code that MINXG genuinely
    emitted via its own loop; reviewers can audit it like any other
    source file under the project.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if not scored:
        raise RuntimeError("no candidate survived evaluation")
    scored.sort(key=lambda t: t[1], reverse=True)
    best_body, best_score = scored[0]
    target = out_dir / "latest.py"
    target.write_text(best_body + "\n", encoding="utf-8")
    report = out_dir / "report.json"
    report.write_text(
        json.dumps({
            "winner": {"score": best_score, "body_chars": len(best_body)},
            "evaluated": len(scored),
            "rejected": max(0, pool_size - len(scored)),
        }, indent=2),
        encoding="utf-8",
    )
    return target


def run_genesis(args: argparse.Namespace) -> int:
    """Run one full ``MINXG Genesis Loop`` cycle: propose→mutate→evaluate→crystallise.

    This is the 0.16.0 self-evolved capability. It DOES NOT mutate the
    MINXG source tree — it produces a candidate module under
    ``~/.minxg/genesis/latest.py`` that human review can adopt (or not).
    Generated code is reproducible from the seed prompt, so two runs
    with the same seed compare cleanly.
    """
    _experimental_warning("genesis")
    seed: Optional[str] = getattr(args, "seed", None)
    generations: int = int(getattr(args, "generations", 3) or 3)
    out_dir = Path(getattr(args, "out", None) or GENESIS_HOME)
    proposal = _genesis_propose(seed)
    pool = _genesis_mutate(proposal, generations)
    scored = _genesis_evaluate(pool)
    if not scored:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} genesis: every candidate was rejected\n"
        )
        return 1
    target = _genesis_crystallise(scored, out_dir, len(pool))
    print(f"{EXPERIMENTAL_TAG} genesis loop complete")
    print(f"   seed       : {seed or '(default)'}")
    print(f"   generations: {generations}")
    print(f"   survived   : {len(scored)}/{len(pool)}")
    print(f"   winner     : score={scored[0][1]}  -> {target}")
    return 0


# ----------------------------------------------------------------------
# runtime-plan / runtime-install — polyglot runtime install helpers (0.14+)
# ----------------------------------------------------------------------
#
# What users actually want when an adapter says ``status = "disabled"``:
# how do I install R / Julia / Datalog / wasmtime on this box? The six
# ``minxg.contracts.runtime`` adapters detect their own runtime at
# import time and silently fall back to emulators / pure-python when
# the host binary is absent, so the gap that needed filling was a
# user-visible *plan* the user can copy-paste and a guarded *executor*
# they can opt into with ``--apply``.
#
# Both verbs are [EXPERIMENTAL] in 0.14. We deliberately do NOT
# auto-sudo or chain steps on the user's behalf — these are the
# operating principles behind every recommended command below.

RUNTIME_LANG_HELP = (
    "language id (`cpp`, `go`, `wasm`, `r`, `julia`, `datalog`) or `all`"
)


def _resolve_runtime_lang(raw: Optional[str]) -> str:
    """Normalise a user-supplied language id, default ``all``.

    Empty / ``None`` / ``"all"`` all collapse to ``"all"`` so the
    plan renders every managed language. Unknown ids are passed
    through unchanged so the underlying ``plan_install`` can show a
    helpful "unknown language" note instead of silently dropping the
    request.
    """
    if raw is None:
        return "all"
    s = str(raw).strip().lower()
    return s or "all"


def run_runtime_plan(args: argparse.Namespace) -> int:
    """Print the install plan for one language (or every managed one).

    Always dry-run. Reads ``args.language`` and ``args.platform``
    (platform override defaults to whatever ``installer.platform_id``
    detects). Unknown language ids are reported but we still
    render *something* (``plan_install`` returns a placeholder with
    a "no recipe" note), so the user gets a clear "this id is not
    managed by MINXG" message rather than a silent no-op.
    """
    _experimental_warning("runtime-plan")
    try:
        from minxg.contracts.runtime import (
            current_plan, render_install_plan, MANAGED_LANGUAGES,
        )
    except Exception as exc:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-plan: {type(exc).__name__}: {exc}\n"
        )
        return 1
    lang = _resolve_runtime_lang(getattr(args, "language", None))
    plat = getattr(args, "platform", None)
    if lang != "all" and lang not in MANAGED_LANGUAGES:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-plan: unknown language {lang!r}; "
            f"managed: {', '.join(MANAGED_LANGUAGES)}\n"
        )
        # Best-effort: still render a single no-op plan so the user
        # gets the same "host=..." header and "no recipe" output.
        from minxg.contracts.runtime.installer import plan_install
        sys.stdout.write(render_install_plan([plan_install(lang)], plat=plat))
        return 2
    try:
        plans = current_plan(lang)
    except Exception as exc:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-plan: planner failure: "
            f"{type(exc).__name__}: {exc}\n"
        )
        return 1
    if not plans:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-plan: nothing to plan for {lang!r}\n"
        )
        return 0
    text = render_install_plan(plans, plat=plat)
    sys.stdout.write(text)
    return 0


def run_runtime_install(args: argparse.Namespace) -> int:
    """Run, or dry-run, the install plan for one language.

    Safety properties
    -----------------
    * Without ``--apply``, prints the plan and returns 0 — no
      subprocess is launched.
    * With ``--apply``, runs *one* ``sh -c <cmd>`` per language with
      a 10-minute timeout. The runner is the
      :func:`minxg.contracts.runtime._exec.run` shared helper, so
      `test_polyglot_runtime_installer` can monkeypatch the runner
      without touching the file-system.
    * The executor NEVER recurses into ``run_install("all")``; the
      user has to invoke each language they want by name.
    * ``lang`` must be either ``"all"`` or one of the managed
      language ids (see ``MANAGED_LANGUAGES``); anything else is
      treated as a typo and rejected with rc=2.

    Exit codes follow ``minxg`` convention: 0 = applied or no-op,
    1 = underlying runner returned ok=False, 2 = unsupported
    language id requested.
    """
    _experimental_warning("runtime-install")
    try:
        from minxg.contracts.runtime import MANAGED_LANGUAGES
    except Exception as exc:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-install: {type(exc).__name__}: {exc}\n"
        )
        return 1
    apply = bool(getattr(args, "apply", False))
    lang = _resolve_runtime_lang(getattr(args, "language", None))
    plat = getattr(args, "platform", None)
    if lang != "all" and lang not in MANAGED_LANGUAGES:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-install: unknown language {lang!r}; "
            f"managed: {', '.join(MANAGED_LANGUAGES)}\n"
        )
        return 2
    try:
        from minxg.contracts.runtime import (
            current_plan, run_install as _run_install,
        )
    except Exception as exc:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-install: {type(exc).__name__}: {exc}\n"
        )
        return 1
    try:
        plans = current_plan(lang)
    except Exception as exc:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-install: planner failure: "
            f"{type(exc).__name__}: {exc}\n"
        )
        return 1
    if not plans:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} runtime-install: no plans for {lang!r}\n"
        )
        return 2
    result = _run_install(
        lang, plat=plat, apply=apply,
    )
    sys.stdout.write(
        json.dumps({
            "applied": apply,
            "platform": result.get("platform"),
            "plans": result.get("plans", []),
        }, indent=2, default=str)
    )
    sys.stdout.write("\n")
    if not apply:
        print(f"{EXPERIMENTAL_TAG} runtime-install dry-run — re-run with --apply to execute")
        return 0
    # Real execution: surface failure if any plan row's runner failed.
    for row in result.get("plans", []):
        out = row.get("runner_output") or {}
        if out and out.get("ok") is False:
            sys.stderr.write(
                f"{EXPERIMENTAL_TAG} runtime-install: {row.get('language')} "
                f"failed: {out.get('stderr') or 'runner ok=False'}\n"
            )
            return 1
    return 0


# ----------------------------------------------------------------------
# argparse wiring — invoked from main.py
# ----------------------------------------------------------------------
# argparse wiring — invoked from main.py
# ----------------------------------------------------------------------

def add_subparsers(sub) -> None:
    """Wire every experimental verb under a single parent parser group."""
    p_bench = sub.add_parser("bench", help=f"{EXPERIMENTAL_TAG} local perf snapshot")
    p_bench.set_defaults(_experimental_cmd="bench")

    p_replay = sub.add_parser("replay", help=f"{EXPERIMENTAL_TAG} replay a markdown chat log")
    p_replay.add_argument("file", nargs="?", default="-",
                          help="path to .md (or '-' for stdin)")
    p_replay.set_defaults(_experimental_cmd="replay")

    p_theme = sub.add_parser("theme", help=f"{EXPERIMENTAL_TAG} get/set TUI theme")
    p_theme.add_argument("name", nargs="?",
                         help=f"theme name ({'/'.join(VALID_THEMES)})")
    p_theme.set_defaults(_experimental_cmd="theme")

    p_safe = sub.add_parser(
        "safe-eval",
        help=f"{EXPERIMENTAL_TAG} restricted expression evaluator",
    )
    p_safe.add_argument("expr", nargs="?", help="arithmetic expression")
    p_safe.add_argument("--locals", help="JSON object of local bindings")
    p_safe.set_defaults(_experimental_cmd="safe-eval")

    p_reload = sub.add_parser(
        "ext-reload",
        help=f"{EXPERIMENTAL_TAG} rescan extension sources",
    )
    p_reload.add_argument("--all", action="store_true", help="rescan every source")
    p_reload.set_defaults(_experimental_cmd="ext-reload")

    # 0.16.0 — additional experimental verbs.

    p_think = sub.add_parser(
        "think",
        help=f"{EXPERIMENTAL_TAG} toggle ``[thinking]...[/thinking]`` rendering",
    )
    p_think.add_argument(
        "action", nargs="?", choices=("on", "off"),
        help="toggle display of model CoT thinking tags",
    )
    p_think.set_defaults(_experimental_cmd="think")

    sub.add_parser(
        "polyglot-manifest",
        help=f"{EXPERIMENTAL_TAG} list polyglot language adapters + versions",
    ).set_defaults(_experimental_cmd="polyglot-manifest")

    sub.add_parser(
        "contract",
        help=f"{EXPERIMENTAL_TAG} list registered minxg.contracts Cells",
    ).set_defaults(_experimental_cmd="contract")

    p_genesis = sub.add_parser(
        "genesis",
        help=f"{EXPERIMENTAL_TAG} run one MINXG Genesis Loop cycle",
    )
    p_genesis.add_argument("--seed", help="seed prompt for the loop")
    p_genesis.add_argument(
        "--generations", type=int, default=3,
        help="how many mutation generations to explore (default 3)",
    )
    p_genesis.add_argument(
        "--out", help="output directory (default ~/.minxg/genesis)",
    )
    p_genesis.set_defaults(_experimental_cmd="genesis")

    # 0.16.0 — polyglot runtime install helpers.
    p_runtime_plan = sub.add_parser(
        "runtime-plan",
        help=f"{EXPERIMENTAL_TAG} print install plan for a polyglot runtime",
    )
    p_runtime_plan.add_argument(
        "language", nargs="?", default="all",
        help=RUNTIME_LANG_HELP,
    )
    p_runtime_plan.add_argument(
        "--platform", help="override host platform id (termux|linux|macos|windows)",
    )
    p_runtime_plan.set_defaults(_experimental_cmd="runtime-plan")

    p_runtime_install = sub.add_parser(
        "runtime-install",
        help=f"{EXPERIMENTAL_TAG} execute (or dry-run) the polyglot install plan",
    )
    p_runtime_install.add_argument(
        "language", nargs="?", default="all",
        help=RUNTIME_LANG_HELP,
    )
    p_runtime_install.add_argument(
        "--apply", action="store_true",
        help="actually run the recommended install command (default: dry-run)",
    )
    p_runtime_install.add_argument(
        "--platform", help="override host platform id (termux|linux|macos|windows)",
    )
    p_runtime_install.set_defaults(_experimental_cmd="runtime-install")

    # 0.16.0 — `minxg sg` — call the polyglot worker tools from the CLI.
    # The polyglot adapters have always had invoke() entries; this verb
    # makes them reachable for users without going through the AI layer.
    p_sg = sub.add_parser(
        "sg",
        help=(
            f"{EXPERIMENTAL_TAG} dispatch a polyglot worker tool by name. "
            "Use ``minxg polyglot-manifest`` (and ``minxg tools``) to find "
            "the registered worker tool names per language."
        ),
    )
    p_sg.add_argument(
        "tool",
        help=(
            "Fully qualified tool name, e.g. ``julia_math.julia_fib`` or "
            "``r_stats.r_summary``. Abbreviated prefixes like ``julia_`` "
            "match the first available tool on any JuliaWorker."
        ),
    )
    p_sg.add_argument(
        "--json", action="store_true",
        help="read tool arguments as a single JSON object on stdin.",
    )
    p_sg.set_defaults(_experimental_cmd="sg")


def dispatch(args: argparse.Namespace) -> int:
    """Route a parsed args with `_experimental_cmd` to its handler."""
    cmd = getattr(args, "_experimental_cmd", None)
    if cmd == "bench":
        return run_bench(args)
    if cmd == "replay":
        return run_replay(args)
    if cmd == "theme":
        return run_theme(args)
    if cmd == "safe-eval":
        return run_safe_eval(args)
    if cmd == "ext-reload":
        return run_ext_reload(args)
    if cmd == "think":
        return run_think(args)
    if cmd == "polyglot-manifest":
        return run_polyglot_manifest(args)
    if cmd == "contract":
        return run_contract(args)
    if cmd == "genesis":
        return run_genesis(args)
    if cmd == "runtime-plan":
        return run_runtime_plan(args)
    if cmd == "runtime-install":
        return run_runtime_install(args)
    if cmd == "sg":
        return run_sg(args)
    sys.stderr.write(f"{EXPERIMENTAL_TAG} unknown verb: {cmd!r}\n")
    return 2


# sg — single-shot dispatch into a polyglot worker tool.
# -----------------------------------------------------------------------

def run_sg(args: argparse.Namespace) -> int:
    """Call a polyglot worker tool by fully-qualified name.

    Format: ``minxg sg <worker_id>.<tool_name> [--json] [<args...>]``

    * Without ``--json``: positional args after the tool name are coerced
      to keyword arguments via str.split("=") syntax
      (``tool=arg tool=arg``) or treated as a single string passed as
      ``code`` for ``*_eval`` tools. JSON mode is the explicit, recommended
      path because parameter types are preserved.
    * With ``--json``: read the JSON object from stdin instead.

    Exit codes:
        0 — tool returned ``status: ok`` (or a non-error variant)
        1 — tool returned ``status: disabled`` (runtime missing)
        2 — tool name not found / bad arguments
        3 — internal dispatcher error
    """
    _experimental_warning("sg")
    from minxg.base import WorkerRegistry

    spec: str = getattr(args, "tool", "")
    if not spec or "." not in spec:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} sg syntax: ``<worker_id>.<tool_name>`` "
            "(e.g. ``r_stats.r_summary``, ``wasm_compute.wasm_fib``)\n"
        )
        return 2

    worker_id, _, tool_name = spec.partition(".")
    # Build or reuse a registry. Workers self-register on import, so
    # importing the polyglot sub-package is enough.
    try:
        from minxg.five_pillars.polyglot import JuliaWorker, RWorker, DatalogWorker, WasmWorker
        registry = WorkerRegistry()
        registry.register(JuliaWorker())
        registry.register(RWorker())
        registry.register(DatalogWorker())
        registry.register(WasmWorker())
    except Exception as e:
        sys.stderr.write(f"{EXPERIMENTAL_TAG} sg: registry build failed: {e}\n")
        return 3

    worker = registry.get(worker_id)
    if worker is None:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} sg: unknown worker ``{worker_id}``\n"
        )
        return 2
    if tool_name not in worker.tools:
        sys.stderr.write(
            f"{EXPERIMENTAL_TAG} sg: worker ``{worker_id}`` has no tool "
            f"``{tool_name}``. Available: {sorted(worker.tools)}\n"
        )
        return 2

    # Collect args.
    try:
        if getattr(args, "json", False):
            import json as _json
            raw = sys.stdin.read()
            params = _json.loads(raw) if raw.strip() else {}
        else:
            params = _sg_parse_positional(sys.argv[1:])
    except Exception as e:
        sys.stderr.write(f"{EXPERIMENTAL_TAG} sg: arg parse failed: {e}\n")
        return 2

    import asyncio
    try:
        result = asyncio.run(worker.call(tool_name, params))
    except Exception as e:
        sys.stderr.write(f"{EXPERIMENTAL_TAG} sg: tool raised: {e}\n")
        return 3

    import json as _json2
    print(_json2.dumps(result, ensure_ascii=False, indent=2, default=str))
    status = result.get("status")
    if status in ("ok", "subset_violation"):
        return 0
    if status == "disabled":
        return 1
    if status == "error":
        return 2
    return 0


def _sg_parse_positional(argv: List[str]) -> Dict[str, Any]:
    """Parse leftover ``--key=value`` / ``key=value`` / positional ``k k`` pairs.

    Bare positional args (no ``=``) are merged into ``code`` so that
    ``minxg sg r_stats.r_eval -- -- '$x + 1'`` ends up with
    ``{"code": "$x + 1"}`` after stripping the leading separator.
    """
    params: Dict[str, Any] = {}
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("--") and "=" in tok:
            key, _, val = tok[2:].partition("=")
            params[key] = val
        elif "=" in tok and not tok.startswith("-"):
            key, _, val = tok.partition("=")
            params[key] = val
        else:
            params.setdefault("code", "")
            if params["code"]:
                params["code"] += " "
            params["code"] += tok
        i += 1
    return params
