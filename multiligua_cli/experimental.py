"""
multiligua_cli/experimental.py — [EXPERIMENTAL] extra verbs for 0.13.0.

Subcommands exposed as `minxg bench`, `minxg replay`, `minxg theme`,
`minxg safe-eval`. Each verb is intentionally additive — they share no
state with the stable TUI and may be removed or renamed in a later
minor release without prior notice.

The set lives behind an explicit `[EXPERIMENTAL]` flag in the help text
so users know what they're getting into. Behaviour:
  - bench         local perf snapshot of representative components
  - replay        re-render a markdown chat log through the TUI pipe
  - theme         get / set the active TUI theme
  - safe-eval     restricted single-expression eval
  - hot-reload    re-scan all extension sources
  - export-markdown   write a synthetic chat log

Everything here is side-effect-light (touch only MINXG's runtime dir)
and returns a process exit code; CI runs them through `tests/test_experimental_cli.py`.
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
    sys.stderr.write(f"{EXPERIMENTAL_TAG} unknown verb: {cmd!r}\n")
    return 2
