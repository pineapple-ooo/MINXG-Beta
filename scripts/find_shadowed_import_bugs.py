#!/usr/bin/env python3
"""
Static scan for a specific real bug class found in multiligua_cli/main.py:

    A function has a module-level name (e.g. `sys`, imported at the top of
    the file) that is ALSO imported locally somewhere inside the function
    body (e.g. `import sys` inside an `if` branch). Because CPython decides
    a name is local to a function at *compile* time (if it's ever a target
    of an assignment/import anywhere in the function body), any reference
    to that name *earlier* in the function — even in a branch that runs
    before the local import statement — raises UnboundLocalError at runtime.

This script parses every .py file with `ast`, and for every function:
  1. Collects names imported/assigned locally anywhere in the function body
     (only at the function's own scope — not nested functions).
  2. Checks whether that name is also bound by a module-level `import` /
     `from ... import` statement.
  3. If so, and the name is *used* (Load context) at a line number earlier
     than the local import within the same function, it's a confirmed bug
     exactly like the one already fixed in multiligua_cli/main.py.
  4. If the name is used but we can't prove ordering conflicts with 100%
     confidence (e.g. used only after every local-import branch), it's
     reported as a lower-confidence "shadowing" finding worth a human look,
     since it's still fragile.

Usage: python3 scripts/find_shadowed_import_bugs.py [root_dir]
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def module_level_imported_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name)
    return names


class FuncScanner(ast.NodeVisitor):
    """Walks a single function body (not descending into nested defs) and
    records, per name: the set of lines where it's locally bound (import/
    assignment) and the set of lines where it's read."""

    def __init__(self):
        self.bound_lines: dict[str, list[int]] = {}
        self.read_lines: dict[str, list[int]] = {}

    def visit_FunctionDef(self, node):
        pass  # don't descend into nested function defs

    visit_AsyncFunctionDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef

    def visit_Import(self, node):
        for alias in node.names:
            name = (alias.asname or alias.name).split(".")[0]
            self.bound_lines.setdefault(name, []).append(node.lineno)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            self.bound_lines.setdefault(name, []).append(node.lineno)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.read_lines.setdefault(node.id, []).append(node.lineno)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound_lines.setdefault(node.id, []).append(node.lineno)
        self.generic_visit(node)


def scan_file(path: Path):
    findings = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return findings

    mod_names = module_level_imported_names(tree)
    if not mod_names:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        scanner = FuncScanner()
        for stmt in node.body:
            scanner.visit(stmt)
        for name in mod_names & scanner.bound_lines.keys():
            bound = sorted(scanner.bound_lines[name])
            reads = sorted(scanner.read_lines.get(name, []))
            first_bind = bound[0]
            earlier_reads = [ln for ln in reads if ln < first_bind]
            if earlier_reads:
                findings.append((
                    path, node.name, name, first_bind, earlier_reads, "CONFIRMED"
                ))
            elif reads:
                findings.append((
                    path, node.name, name, first_bind, reads, "fragile-only"
                ))
    return findings


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    skip_dirs = {".git", "__pycache__", "node_modules", "build", "dist", ".venv", "venv", "target"}
    confirmed = []
    fragile = []
    for path in root.rglob("*.py"):
        if any(part in skip_dirs for part in path.parts):
            continue
        for f in scan_file(path):
            (confirmed if f[5] == "CONFIRMED" else fragile).append(f)

    print(f"=== CONFIRMED UnboundLocalError-class bugs: {len(confirmed)} ===")
    for path, fn, name, bind_ln, reads, _ in confirmed:
        print(f"{path}:{bind_ln}  in {fn}()  '{name}' shadowed-by-local-import/assign, "
              f"but read earlier at line(s) {reads}")

    print(f"\n=== Fragile (shadowed but no proven earlier read — lower priority): {len(fragile)} ===")
    for path, fn, name, bind_ln, reads, _ in fragile:
        print(f"{path}:{bind_ln}  in {fn}()  '{name}' locally re-imported/assigned "
              f"(reads at {reads} all appear after the local bind in source order)")


if __name__ == "__main__":
    main()
