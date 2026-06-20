"""
multiligua_cli/doctor.py — `minxg doctor` self-check.

End-to-end diagnostic that does NOT replace building steps — it surfaces
where the install is OK, where it is fragile, and where it is broken.

Reports on:
  - Platform + probe-able binaries (python, pip, git, curl, gcc, adb)
  - minxg import + version + worker count + native-lib status
  - Config file presence and key fields
  - Extension discovery and the opt-in state for built-ins

Exit code is 0 if everything works, 1 if any required component is
unavailable, 2 if anything appears degraded but workable.

This is a CLI-only surface; it never throws on a single probe failure,
it reports and moves on. That way users can paste the whole output
verbatim when filing a bug.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

from multiligua_cli.utils import (
    HAS_RICH,
    Colors,
    colorize,
    console,
    print_dim,
    print_error,
    print_info,
    print_success,
    print_warning,
)

try:
    from rich.panel import Panel
    from rich import box
except ImportError:  # pragma: no cover
    Panel = None
    box = None


Section = List[Tuple[str, str, str]]  # (key, status, value)


def _row(key: str, status: str, value: str = "") -> str:
    """Format one diagnostic row as `key  status  value`."""
    if value:
        return f"  {key:<32}{status:<10}{value}"
    return f"  {key:<32}{status}"


def _check_platform() -> Section:
    """Probe basic platform facts."""
    import platform as _p
    rows: Section = []
    system = _p.system()
    rows.append(("platform.system", "OK", system))
    if system == "Android":
        rows.append(("runtime", "OK", "Termux"))
    elif system == "Linux":
        rows.append(("runtime", "OK", "POSIX"))
    elif system == "Darwin":
        rows.append(("runtime", "OK", "macOS"))
    elif system == "Windows":
        rows.append(("runtime", "OK", "Windows"))
    else:
        rows.append(("runtime", "INFO", system))
    rows.append(("python", "OK", _p.python_version()))
    return rows


def _check_binaries() -> Section:
    """Probe ship-by-default tooling that install.sh looked for."""
    rows: Section = []
    wanted = [
        ("git", "Source-tree bootstrap (curl|bash path)"),
        ("curl", "Piped installer"),
        ("pip", "Editable install"),
        ("gcc", "Native C build (optional)"),
        ("clang", "Native C build (optional)"),
        ("adb", "minxg-adb extension (opt-in)"),
    ]
    for name, desc in wanted:
        path = shutil.which(name)
        if path:
            rows.append((f"binary {name}", "OK", f"{path} ({desc})"))
        else:
            rows.append((f"binary {name}", "MISSING", desc))
    return rows


def _check_minxg() -> Section:
    """Import minxg and probe its surface."""
    rows: Section = []
    try:
        import minxg
        rows.append(("minxg import", "OK", str(minxg.__file__)))
    except Exception as e:
        rows.append(("minxg import", "FAIL", repr(e)))
        return rows

    rows.append(("minxg.VERSION", "OK", str(minxg.VERSION)))

    try:
        workers = len(minxg.__all__)
        rows.append(("workers (__all__)", "OK", f"{workers} workers"))
    except Exception as e:
        rows.append(("workers (__all__)", "FAIL", repr(e)))

    try:
        rows.append(("operators (math)", "OK",
                     f"{minxg.TOTAL_MATHEMATICAL_OPERATORS} "
                     f"(ga={minxg.GA_OPERATORS} cat={minxg.CAT_OPERATORS} "
                     f"ig={minxg.IG_OPERATORS} topo={minxg.TOPO_OPERATORS} "
                     f"chaos={minxg.CHAOS_OPERATORS} "
                     f"fiber={minxg.FIBER_OPERATORS})"))
    except Exception as e:
        rows.append(("operators (math)", "FAIL", repr(e)))

    try:
        total_ops = minxg.operators.OPERATOR_REGISTRY.total_operators
        rows.append(("operators (total)", "OK",
                     f"{total_ops} across all categories"))
    except Exception as e:
        rows.append(("operators (total)", "FAIL", repr(e)))

    # Lazy import on purpose: cryptography can crash cold-start on Termux.
    try:
        from minxg.five_pillars.scalar import core_native
        # Force the lazy loader to actually run so we know it works.
        core_native._ensure_loaded()
        loaded_lib = core_native._lib
        if loaded_lib is not None:
            loaded_path = (getattr(core_native, "_lib_path", None)
                           or "loaded")
            rows.append(("native lib", "OK", str(loaded_path)))
        else:
            rows.append(("native lib", "FALLBACK",
                         "pure python (no C/C++ binding loaded)"))
    except Exception as e:
        rows.append(("native lib", "WARN", repr(e)))

    return rows


def _check_config() -> Section:
    """Look at the runtime config; never fail even if missing."""
    rows: Section = []
    try:
        from multiligua_cli.utils import get_config_path, load_config
    except Exception:
        rows.append(("config utils", "FAIL", "could not import config helpers"))
        return rows

    try:
        path = get_config_path()
    except Exception as e:
        rows.append(("config path", "FAIL", repr(e)))
        return rows

    rows.append(("config path", "OK" if path.exists() else "MISSING",
                 str(path)))
    if not path.exists():
        rows.append(("config", "WARN",
                     "run `minxg setup` to create one"))
        return rows

    try:
        cfg = load_config()
    except Exception as e:
        rows.append(("config load", "FAIL", repr(e)))
        return rows

    ai = cfg.get("ai", {}) if isinstance(cfg, dict) else {}
    rows.append(("config.load", "OK", "valid YAML"))
    rows.append(("ai.provider", "OK" if ai.get("provider") else "MISSING",
                 str(ai.get("provider", ""))))
    rows.append(("ai.model", "OK" if ai.get("model") else "MISSING",
                 str(ai.get("model", ""))))
    base = ai.get("base_url")
    rows.append(("ai.base_url",
                 "OK" if base else "MISSING",
                 str(base or "(empty)")))
    return rows


def _check_extensions() -> Section:
    """List installed and available extensions."""
    rows: Section = []
    try:
        from extensions.loader import (
            discover_extensions, list_extensions,
        )
        from extensions.package_cli import BUILTIN_OPTIONAL
    except Exception as e:
        rows.append(("extensions module", "FAIL", repr(e)))
        return rows

    try:
        exts = list_extensions()
    except Exception as e:
        rows.append(("extensions list", "FAIL", repr(e)))
        return rows

    rows.append(("installed extensions", "OK", str(len(exts))))
    enabled = sum(
        1 for e in exts
        if getattr(getattr(e, "module", None), "EXTENSION_ENABLED", True)
    )
    rows.append(("enabled count", "OK", f"{enabled} / {len(exts)}"))

    rows.append(("available built-ins", "OK",
                 ", ".join(sorted(BUILTIN_OPTIONAL.keys()))))
    return rows


def _check_platform_cap() -> Section:
    """Tell the user how many tools their host can dispatch."""
    rows: Section = []
    try:
        from multiling.platform_cap import summary, cap_for
        s = summary()
        rows.append(("platform", "OK", s["platform"]))
        rows.append(("tool cap", "OK", str(s["cap"])))
        rows.append(("active tools", "OK",
                     f"{s['active_count']} / {s['registered_count']}"))
        if s["dropped_count"] > 0:
            rows.append(("dropped tools", "INFO",
                         f"{s['dropped_count']} hidden above cap "
                         "(raise MINXG_TOOL_CAP to expose)"))
    except Exception as e:
        rows.append(("platform_cap", "WARN", repr(e)))
    return rows


def _render_section(title: str, rows: Section) -> str:
    """Render one section as a fixed-column table."""
    body_lines = [_row(*r) for r in rows]
    body = "\n".join(body_lines)
    if HAS_RICH:
        return str(console.print(
            Panel(body, title=title, box=box.SIMPLE, border_style="cyan")))
    return f"\n[{title}]\n{body}\n"


def run_doctor(args) -> int:
    """`minxg doctor` — full self-check, return process exit code."""
    if HAS_RICH and Panel is not None:
        console.print(Panel.fit(
            "MINXG doctor — self-check",
            style="cyan bold", box=box.DOUBLE,
        ))
    else:
        print(colorize("\n== MINXG doctor — self-check ==\n",
                       Colors.CYAN, Colors.BOLD))

    sections = [
        ("Platform", _check_platform()),
        ("Binaries", _check_binaries()),
        ("minxg package", _check_minxg()),
        ("Config", _check_config()),
        ("Tool cap", _check_platform_cap()),
        ("Extensions", _check_extensions()),
    ]

    fails = warns = 0
    printed: List[str] = []
    for title, rows in sections:
        if HAS_RICH and Panel is not None:
            console.print(Panel("\n".join(_row(*r) for r in rows),
                                title=title, box=box.SIMPLE,
                                border_style="cyan"))
        else:
            printed.append(f"\n[{title}]")
            for r in rows:
                printed.append(_row(*r))
        for _, status, _ in rows:
            s = status.upper()
            if s.startswith("FAIL"):
                fails += 1
            elif s.startswith("WARN") or s.startswith("FALLBACK"):
                warns += 1

    if not HAS_RICH:
        print("\n".join(printed))

    summary = (
        f"{fails} failure(s), {warns} warning(s) "
        f"out of {sum(len(rows) for _, rows in sections)} check(s)"
    )
    if HAS_RICH:
        if fails:
            console.print(f"\n[red]{summary}[/red]")
        elif warns:
            console.print(f"\n[yellow]{summary}[/yellow]")
        else:
            console.print(f"\n[green]{summary}[/green]")
    else:
        if fails:
            print_error(summary)
        elif warns:
            print_warning(summary)
        else:
            print_success(summary)

    if fails:
        return 1
    if warns:
        return 2
    return 0


if __name__ == "__main__":
    import argparse
    rc = run_doctor(argparse.Namespace())
    sys.exit(rc)
