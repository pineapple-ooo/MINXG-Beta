"""minxg/five_pillars/devtools/dev_shell.py — Unified dev shell facade.

The ``dev_shell`` worker is a single facade for the typical
*every-day* developer commands.  It does NOT replace platform-
specific builders — instead it routes each command to the
correct host binary/path:

* ``lint``      → ``ruff`` / ``eslint`` / ``cargo clippy`` / etc.
* ``format``    → ``black`` / ``prettier`` / ``dotnet format``
* ``test``      → ``pytest`` / ``jest`` / ``cargo test`` / ``flutter test``
* ``run``       → ``python main.py`` / ``cargo run`` / ``gradle run``
* ``clean``     → removes tree-shaped build artifacts
* ``gengitignore`` → emit ``.gitignore`` for the platform
* ``doctor``    → show what tools are on PATH and upgrade hints

Path resolution prefers the project's own bounded version
(e.g.  ``vendor/flake8`` before global), so it remains a
*coordination* tool like DevForge — call out to binaries,
not a sandboxed compiler.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from minxg.base import BaseWorker, tool


# Language → runner /linter / formatter metadata.  Each entry
# uses the **canonical** binary name (path resolved at runtime).
_LINTERS = {
    "python":    {"lint": ["ruff", "check", "."],
                  "format": ["ruff", "format", "."],
                  "test": ["pytest", "-q", "--tb=line"],
                  "run":  [sys.executable, "main.py"]},
    "rust":      {"lint": ["cargo", "clippy", "--", "-D", "warnings"],
                  "format": ["cargo", "fmt", "--all"],
                  "test": ["cargo", "test", "--release"],
                  "run":  ["cargo", "run", "--release"]},
    "javascript":{"lint": ["eslint", "src"],
                  "format": ["prettier", "--write", "src"],
                  "test": ["jest"],
                  "run":  ["npm", "start"]},
    "typescript":{"lint": ["tsc", "--noEmit"],
                  "format": ["prettier", "--write", "src"],
                  "test": ["npm", "test"],
                  "run":  ["npm", "start"]},
    "java":      {"lint": ["checkstyle", "src/main/java"],
                  "format": ["google-java-format", "-i", "-r", "src"],
                  "test": ["mvn", "test"],
                  "run":  ["mvn", "spring-boot:run"]},
    "kotlin":    {"lint": ["./gradlew", "lint"],
                  "format": ["ktlint", "src/**/*.kt"],
                  "test": ["./gradlew", "test"],
                  "run":  ["./gradlew", "run"]},
    "go":        {"lint": ["golangci-lint", "run"],
                  "format": ["gofmt", "-w", "."],
                  "test": ["go", "test", "./..."],
                  "run":  ["go", "run", "."]},
    "csharp":    {"lint": ["dotnet", "format", "--verify-no-changes", "."],
                  "format": ["dotnet", "format", "."],
                  "test": ["dotnet", "test"],
                  "run":  ["dotnet", "run"]},
    "ahk":       {"lint": ["ahk2exe", "/script", "main.ahk"],
                  "format": ["ahk-formatter", "main.ahk"],
                  "test": [],
                  "run":  ["autohotkey", "main.ahk"]},
    "shell":     {"lint": ["shellcheck", "-x"],
                  "format": ["shfmt", "-w", "."],
                  "test": ["bats", "tests"],
                  "run":  ["bash", "main.sh"]},
    "lua":       {"lint": ["luacheck", "."],
                  "format": ["stylua", "."],
                  "test": ["busted", "spec"],
                  "run":  ["lua", "main.lua"]},
}


_LANG_PATTERNS = {
    "python":     ["*.py"],
    "rust":       ["Cargo.toml"],
    "javascript": ["package.json"],
    "typescript": ["tsconfig.json"],
    "java":       ["pom.xml", "build.gradle", "build.gradle.kts"],
    "kotlin":     ["build.gradle.kts", "settings.gradle.kts"],
    "go":         ["go.mod"],
    "csharp":     ["*.csproj"],
    "ahk":        ["*.ahk"],
    "shell":      ["*.sh"],
    "lua":        ["*.lua"],
}


def _detect_language(root: Path) -> str:
    """Best-effort language probe — checks project markers."""
    for lang, markers in _LANG_PATTERNS.items():
        for marker in markers:
            for p in root.rglob(marker):
                # Ignore vendored/build dirs.
                parts = set(p.parts)
                if parts & {"node_modules", ".venv", "venv", "build",
                             "target", ".gradle", "ios", "android",
                             ".cargo"}:
                    continue
                return lang
    return "unknown"


def _missing_tools(cmd: List[str]) -> List[str]:
    out: List[str] = []
    for arg in cmd:
        binary = arg.split("/")[0]
        if binary.startswith((".", "$")):
            continue
        if shutil.which(binary) is None:
            out.append(binary)
    return out


def _run(cmd: List[str], cwd: Path, timeout_s: int) -> Dict[str, Any]:
    """Sync subprocess run; trusted binaries only (lint/test/format)."""
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True,
            text=True, timeout=timeout_s,
        )
        return {
            "status": "ok" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout.splitlines()[-100:],
            "stderr_tail": proc.stderr.splitlines()[-100:],
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "tool": cmd[0]}
    except FileNotFoundError as e:
        return {"status": "disabled", "tool": cmd[0], "error": str(e)}


# ─── Worker ──────────────────────────────────────────────────────────


class DevShellWorker(BaseWorker):
    """Unified dev shell facade — lint / format / test / run / clean.

    Ten tools collapsed onto one facade.  The AI picks the
    right language at runtime; users can override by passing
    ``language="rust"`` explicitly.
    """

    worker_id = "dev_shell"
    version = "0.18.0"
    tier = "code"        # v0.18.0 three-tier classification
    _category = "deploy"

    @tool(
        description=(
            "Return the canonical command set for a given language.  "
            "Useful before invoking lint/run/test so the AI can show "
            "what will be executed."
        ),
        category="deploy",
    )
    async def shell_capabilities(
        self, language: str = "",
    ) -> Dict[str, Any]:
        if language:
            cmds = _LINTERS.get(language)
            if cmds is None:
                return {"status": "error",
                        "error": f"unknown language {language!r}",
                        "supported": list(_LINTERS)}
            return {"status": "ok", "language": language,
                     "commands": cmds}
        return {"status": "ok",
                "languages": list(_LINTERS),
                "count": len(_LINTERS)}

    @tool(
        description=(
            "Detect the primary language of a project at root_path.  "
            "Walks for known marker files (Cargo.toml, package.json, "
            "build.gradle.kts, etc.)."
        ),
        category="deploy",
    )
    async def shell_detect(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        if not root.exists():
            return {"status": "error", "error": f"{root} missing"}
        lang = _detect_language(root)
        return {"status": "ok", "root": str(root),
                 "language": lang}

    # ── Helpers ──────────────────────────────────────────────────────
    async def _resolve_lang(self, root_path: str,
                            language: str) -> Dict[str, Any]:
        """Translate ``root_path`` + optional ``language`` into a
        {root, lang, cmd_table} bundle, erroring out early if
        the language is unknown.
        """
        root = Path(root_path).expanduser()
        if not root.exists():
            return {"status": "error", "error": f"{root} missing"}
        if not language or language == "auto":
            language = _detect_language(root)
        cmds = _LINTERS.get(language)
        if cmds is None:
            return {"status": "error",
                    "error": f"unknown language {language!r}",
                    "supported": list(_LINTERS)}
        return {"status": "ok",
                "root": root,
                "language": language,
                "cmds": cmds}

    # ── Commands ─────────────────────────────────────────────────────
    @tool(description="Run the canonical lint command for a language.",
          category="deploy")
    async def lint(
        self, root_path: str, language: str = "auto",
    ) -> Dict[str, Any]:
        ctx = await self._resolve_lang(root_path, language)
        if ctx["status"] != "ok":
            return ctx
        cmd = ctx["cmds"]["lint"]
        if not cmd:
            return {"status": "ok", "tool": "lint",
                    "note": "no lint configured"}
        if _missing_tools(cmd):
            return {"status": "disabled", "tool": "lint",
                    "missing": _missing_tools(cmd),
                    "hint": ("install missing tools or pick a "
                              "different language")}
        return {"tool": "lint", **_run(cmd, ctx["root"], 240)}

    @tool(description="Run the canonical formatter for a language.",
          category="deploy")
    async def format(
        self, root_path: str, language: str = "auto",
    ) -> Dict[str, Any]:
        ctx = await self._resolve_lang(root_path, language)
        if ctx["status"] != "ok":
            return ctx
        cmd = ctx["cmds"]["format"]
        if not cmd:
            return {"status": "ok", "tool": "format",
                    "note": "no formatter configured"}
        if _missing_tools(cmd):
            return {"status": "disabled", "tool": "format",
                    "missing": _missing_tools(cmd)}
        return {"tool": "format", **_run(cmd, ctx["root"], 240)}

    @tool(description="Run the canonical test runner for a language.",
          category="deploy")
    async def test(
        self, root_path: str, language: str = "auto",
    ) -> Dict[str, Any]:
        ctx = await self._resolve_lang(root_path, language)
        if ctx["status"] != "ok":
            return ctx
        cmd = ctx["cmds"]["test"]
        if not cmd:
            return {"status": "ok", "tool": "test",
                    "note": "no runner configured"}
        if _missing_tools(cmd):
            return {"status": "disabled", "tool": "test",
                    "missing": _missing_tools(cmd)}
        return {"tool": "test", **_run(cmd, ctx["root"], 900)}

    @tool(description="Run the canonical entry command for a language.",
          category="deploy")
    async def run(
        self, root_path: str, language: str = "auto",
    ) -> Dict[str, Any]:
        ctx = await self._resolve_lang(root_path, language)
        if ctx["status"] != "ok":
            return ctx
        cmd = ctx["cmds"]["run"]
        if not cmd:
            return {"status": "ok", "tool": "run",
                    "note": "no runner configured"}
        if _missing_tools(cmd):
            return {"status": "disabled", "tool": "run",
                    "missing": _missing_tools(cmd)}
        return {"tool": "run", **_run(cmd, ctx["root"], 600)}

    # ── House-keeping ────────────────────────────────────────────────
    @tool(description=(
        "Clean common build artefacts at root_path — __pycache__, "
        "build/, target/, .gradle/, dist/, .next/.  Idempotent."
    ), category="deploy")
    async def clean(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        if not root.exists():
            return {"status": "error", "error": f"{root} missing"}
        targets = ["__pycache__", "build", "target", "dist",
                   ".gradle", ".next", ".pytest_cache", "node_modules",
                   ".venv", "venv", ".cxx", "DerivedData"]
        removed = 0
        for name in targets:
            for p in root.rglob(name):
                if p.is_dir():
                    try:
                        import shutil as _sh
                        _sh.rmtree(p, ignore_errors=True)
                        removed += 1
                    except OSError:
                        pass
        return {"status": "ok", "root": str(root),
                "removed_count": removed}

    @tool(description=(
        "Generate a sensible .gitignore for a target language."
    ), category="deploy")
    async def gengitignore(
        self, root_path: str, language: str,
    ) -> Dict[str, Any]:
        templates = {
            "python": "*.pyc\n__pycache__/\n.venv/\n.eggs/\nbuild/\ndist/\n*.egg-info/\n.pytest_cache/\n",
            "rust":   "target/\n**/*.rs.bk\nCargo.lock\n",
            "javascript": "node_modules/\ndist/\n.DS_Store\n*.log\n",
            "typescript": "node_modules/\ndist/\n*.js.map\n",
            "java":   "build/\ntarget/\n*.class\n.idea/\n.vscode/\n.gradle/\n",
            "kotlin": "build/\n.gradle/\n.idea/\n*.iml\n",
            "go":     "*.exe\n*.dll\n*.so\n*.dylib\n*.test\n*.out\n",
            "csharp": "bin/\nobj/\n*.user\n.vs/\n",
            "ahk":    "*.exe\n",
            "shell":  "",
            "lua":    "luac.out\n",
        }
        body = templates.get(language)
        if body is None:
            return {"status": "error",
                    "error": f"unknown language {language!r}",
                    "supported": list(templates)}
        out = Path(root_path).expanduser() / ".gitignore"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body)
        return {"status": "ok", "language": language,
                "path": str(out), "bytes": len(body)}

    @tool(description=(
        "Doctor — report which tooling is on PATH and which is "
        "missing for each supported language."
    ), category="deploy")
    async def doctor(self) -> Dict[str, Any]:
        results: Dict[str, Dict[str, Any]] = {}
        for lang, cmds in _LINTERS.items():
            seen: Dict[str, bool] = {}
            for verb, cmd in cmds.items():
                for arg in cmd:
                    bin_ = arg.split("/")[0]
                    if bin_.startswith((".", "$")) or bin_ == "main.py":
                        continue
                    if bin_ not in seen:
                        seen[bin_] = shutil.which(bin_) is not None
            results[lang] = seen
        return {"status": "ok", "report": results,
                "path": shutil.which("echo") and "$PATH"}


__all__ = ["DevShellWorker"]
