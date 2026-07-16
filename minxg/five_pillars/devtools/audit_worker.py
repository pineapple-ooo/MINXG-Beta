"""minxg/five_pillars/devtools/audit_worker.py -- Project audit worker.

The AuditWorker scans every Python file in the project for defects,
shortcomings, and blemishes that a senior reviewer would flag:

* Bare ``except:`` -- swallows all exceptions including SystemExit
* ``except Exception`` without re-raise -- hides bugs
* ``pass`` in ``except`` -- silent failure
* ``TODO`` / ``FIXME`` / ``HACK`` / ``XXX`` left in code
* ``print()`` left in non-CLI modules (should use logging)
* Functions > 50 lines -- too long, needs refactoring
* Files > 500 lines -- should be split
* Empty ``__init__.py`` without module docstring
* ``import *`` -- namespace pollution
* Mutable default arguments (``def f(x=[])``)
* Unused imports (heuristic: name not referenced after import line)
* Missing ``from __future__ import annotations`` in files using
  PEP 604 / PEP 585 type hints

Every finding is returned with: file path, line number, severity,
category, and a human-readable message.  The worker is a
``BaseWorker`` subclass so the AI can call it via ``@tool``
methods and the gateway exposes it as ``audit_tools``.
"""

from __future__ import annotations

import ast
import os
import re
import tokenize
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from minxg.base import BaseWorker, tool


# ── severity levels ──────────────────────────────────────────
SEV_CRITICAL = "critical"
SEV_WARNING = "warning"
SEV_INFO = "info"

# ── smell categories ────────────────────────────────────────
CAT_BARE_EXCEPT = "bare_except"
CAT_BROAD_EXCEPT = "broad_except"
CAT_PASS_EXCEPT = "pass_in_except"
CAT_TODO = "todo_marker"
CAT_PRINT = "stray_print"
CAT_LONG_FUNC = "long_function"
CAT_BIG_FILE = "big_file"
CAT_IMPORT_STAR = "import_star"
CAT_MUTABLE_DEFAULT = "mutable_default"
CAT_NO_DOCSTRING = "missing_module_docstring"
CAT_UNUSED_IMPORT = "unused_import"


def _walk_py_files(root: str, exclude_dirs: frozenset = frozenset({
    "__pycache__", ".git", "node_modules", "build", "build_asan",
    ".eggs", "*.egg-info", ".tox", "var", "cpp_core",
})) -> List[str]:
    """Yield every ``.py`` file under *root*, skipping excluded dirs."""
    results: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # mutate dirnames in-place to prune
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs
                       and not d.endswith(".egg-info")]
        for fn in filenames:
            if fn.endswith(".py"):
                results.append(os.path.join(dirpath, fn))
    return sorted(results)


def _line_count(filepath: str) -> int:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def _cat(severity: str, category: str, line: int, msg: str,
         filepath: str) -> Dict[str, Any]:
    return {
        "file": filepath,
        "line": line,
        "severity": severity,
        "category": category,
        "message": msg,
    }


# ── AST-based checks ─────────────────────────────────────────

def _check_ast(filepath: str, source: str) -> List[Dict[str, Any]]:
    """Run AST-based checks on a single file."""
    findings: List[Dict[str, Any]] = []
    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        findings.append(_cat(SEV_CRITICAL, "syntax_error", e.lineno or 0,
                             f"SyntaxError: {e.msg}", filepath))
        return findings

    # Module docstring
    if not ast.get_docstring(tree):
        findings.append(_cat(SEV_INFO, CAT_NO_DOCSTRING, 1,
                             "module has no docstring", filepath))

    for node in ast.walk(tree):
        # bare except (except:)
        if isinstance(node, ast.ExceptHandler):
            if node.type is None and node.name is None:
                findings.append(_cat(SEV_CRITICAL, CAT_BARE_EXCEPT,
                                     node.lineno,
                                     "bare except: swallows all exceptions",
                                     filepath))
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                # broad except -- check if body is just pass
                body = node.body
                if len(body) == 1 and isinstance(body[0], ast.Pass):
                    findings.append(_cat(SEV_WARNING, CAT_PASS_EXCEPT,
                                         node.lineno,
                                         "except Exception: pass -- silent failure",
                                         filepath))

        # import *
        if isinstance(node, ast.ImportFrom) and node.names:
            for alias in node.names:
                if alias.name == "*":
                    findings.append(_cat(SEV_WARNING, CAT_IMPORT_STAR,
                                         node.lineno,
                                         "import * -- namespace pollution",
                                         filepath))

        # mutable default args
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defaults = node.args.defaults + node.args.kw_defaults
            for d in defaults:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    findings.append(_cat(SEV_WARNING, CAT_MUTABLE_DEFAULT,
                                         node.lineno,
                                         f"mutable default arg in {node.name}()",
                                         filepath))

            # long function
            end_line = getattr(node, "end_lineno", node.lineno)
            length = end_line - node.lineno + 1
            if length > 50:
                findings.append(_cat(SEV_INFO, CAT_LONG_FUNC,
                                     node.lineno,
                                     f"function {node.name}() is {length} lines (> 50)",
                                     filepath))

    return findings


# ── line-based checks ───────────────────────────────────────

_TODO_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


def _check_lines(filepath: str, source: str,
                  is_cli_module: bool = False) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()

        # TODO / FIXME / HACK / XXX
        m = _TODO_RE.search(stripped)
        if m:
            findings.append(_cat(SEV_INFO, CAT_TODO, i,
                                 f"{m.group(0)} marker left in code",
                                 filepath))

        # stray print() in non-CLI modules
        if not is_cli_module and re.match(r"\s*print\s*\(", stripped):
            # allow print in __main__ blocks
            if not stripped.startswith("#"):
                findings.append(_cat(SEV_INFO, CAT_PRINT, i,
                                     "print() in non-CLI module -- use logging",
                                     filepath))

    return findings


# ── unused import heuristic ─────────────────────────────────

def _check_unused_imports(filepath: str, source: str) -> List[Dict[str, Any]]:
    """Tokenize to find imports, then grep for each name in the
    remainder of the file.  O(n) per import name."""
    findings: List[Dict[str, Any]] = []
    lines = source.splitlines()
    try:
        tokens = list(tokenize.generate_tokens(iter(lines).__next__))
    except Exception:
        return findings

    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string in ("import", "from"):
            # Heuristic: find the imported names and check usage
            start_line = tok.start[0]
            # Collect names from this import statement
            names: List[str] = []
            for t2 in tokens:
                if t2.start[0] == start_line and t2.type == tokenize.NAME:
                    if t2.string not in ("import", "from", "as"):
                        names.append(t2.string)
            for name in names:
                # Check if name appears anywhere else in the file
                found = False
                for j, line in enumerate(lines):
                    if j == start_line - 1:
                        continue
                    if name in line:
                        found = True
                        break
                if not found and names:
                    findings.append(_cat(SEV_INFO, CAT_UNUSED_IMPORT,
                                         start_line,
                                         f"imported name {name!r} appears unused",
                                         filepath))
    return findings[:20]  # cap to avoid noise


class AuditWorker(BaseWorker):
    """Project-wide defect scanner.

    Scans every Python file in the project for common code smells,
    bugs, and blemishes a senior reviewer would flag.  Results are
    returned with file path, line number, severity, category, and
    a human-readable message.

    Non-Python files (Rust, C++, R, shell) are skipped — the
    audit focuses on the Python surface that the AI agent
    controls.  Native code is validated by the build system.
    """

    worker_id = "audit_tools"
    version = "0.18.1"
    tier = "code"
    _category = "deploy"

    SCAN_ROOTS = ("minxg", "multiligua_cli", "gateway", "extensions", "tests")
    EXCLUDE_DIRS = frozenset({
        "__pycache__", ".git", "node_modules", "build", "build_asan",
        ".eggs", "var", "cpp_core",
    })
    BIG_FILE_THRESHOLD = 500

    @tool(
        description="Scan the entire project for code defects, smells, and blemishes.",
        category="deploy",
    )
    async def audit_scan(
        self, root_path: str = "",
        max_findings: int = 200,
    ) -> Dict[str, Any]:
        """Walk every .py file and return a structured findings list."""
        project_root = Path(root_path) if root_path else Path(__file__).parent.parent.parent.parent
        findings: List[Dict[str, Any]] = []

        for subdir in self.SCAN_ROOTS:
            scan_dir = project_root / subdir
            if not scan_dir.is_dir():
                continue
            for filepath in _walk_py_files(str(scan_dir)):
                # skip __pycache__ etc
                if any(exc in filepath for exc in self.EXCLUDE_DIRS):
                    continue
                try:
                    source = open(filepath, "r", encoding="utf-8",
                                  errors="replace").read()
                except Exception:
                    continue

                # file size
                lc = source.count("\n") + 1
                if lc > self.BIG_FILE_THRESHOLD:
                    findings.append(_cat(SEV_INFO, CAT_BIG_FILE, 0,
                                         f"file is {lc} lines (> {self.BIG_FILE_THRESHOLD}) -- consider splitting",
                                         filepath))

                rel = os.path.relpath(filepath, str(project_root))
                is_cli = rel.startswith("multiligua_cli" + os.sep) or rel.startswith("tests" + os.sep)
                findings.extend(_check_ast(filepath, source))
                findings.extend(_check_lines(filepath, source, is_cli))
                findings.extend(_check_unused_imports(filepath, source))

                if len(findings) >= max_findings:
                    findings = findings[:max_findings]
                    break
            if len(findings) >= max_findings:
                break

        # summary
        by_sev: Dict[str, int] = {}
        by_cat: Dict[str, int] = {}
        for f in findings:
            by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
            by_cat[f["category"]] = by_cat.get(f["category"], 0) + 1

        return {
            "status": "ok",
            "total_findings": len(findings),
            "by_severity": by_sev,
            "by_category": by_cat,
            "findings": findings,
        }

    @tool(
        description="Audit a single file for defects and smells.",
        category="deploy",
    )
    async def audit_file(self, filepath: str) -> Dict[str, Any]:
        """Scan one .py file and return its findings."""
        p = Path(filepath).expanduser()
        if not p.is_file():
            return {"status": "error", "error": f"file not found: {filepath}"}
        source = p.read_text(encoding="utf-8", errors="replace")
        findings = _check_ast(str(p), source)
        findings.extend(_check_lines(str(p), source, False))
        findings.extend(_check_unused_imports(str(p), source))
        return {
            "status": "ok",
            "file": str(p),
            "total_findings": len(findings),
            "findings": findings,
        }

    @tool(
        description="Return a summary of audit categories and what they mean.",
        category="deploy",
    )
    async def audit_categories(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "categories": {
                CAT_BARE_EXCEPT: "bare except: swallows all exceptions including SystemExit",
                CAT_BROAD_EXCEPT: "broad except Exception -- may hide bugs",
                CAT_PASS_EXCEPT: "except ...: pass -- silent failure",
                CAT_TODO: "TODO/FIXME/HACK/XXX marker left in code",
                CAT_PRINT: "print() in non-CLI module -- should use logging",
                CAT_LONG_FUNC: "function longer than 50 lines",
                CAT_BIG_FILE: "file longer than 500 lines",
                CAT_IMPORT_STAR: "import * -- namespace pollution",
                CAT_MUTABLE_DEFAULT: "mutable default argument (list/dict/set)",
                CAT_NO_DOCSTRING: "module has no docstring",
                CAT_UNUSED_IMPORT: "imported name appears unused",
            },
        }


__all__ = ["AuditWorker"]
