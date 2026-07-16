"""minxg/five_pillars/devtools/dev_forge.py — Multi-platform dev forge.

The superset worker introduced in v0.18.0.  Replaces the
role of ``android_forge`` for anyone targeting more than just
Android — covers Android, HarmonyOS, Linux, and Windows
through one facade.

Architectural note
------------------
This worker is **registered alongside** AndroidForgeWorker, not
"instead of".  AndroidForgeWorker stays 1:1 compatible for every
existing caller, with ApkForgeWorker preserved as a backward-compat
alias. DevForge takes over when the AI needs to decide *which* platform
to build for — the routing lives here.
here.

Tools
-----
* ``forge_capabilities`` — discovery of every supported
  (platform × framework) combination.
* ``forge_plan`` — validate a structured manifest for ANY
  platform.  Returns the same blueprint shape as
  ``apk_plan`` so callers can reuse downstream code.
* ``forge_scaffold`` — write the canonical project tree for
  the chosen (platform, framework).  Manifest is written for
  follow-up ``forge_build``.
* ``forge_build`` — dispatch to the right build command
  (``buildozer``, ``hvigorw``, ``cargo tauri``, ``dotnet``,
  ``pyinstaller``, …) via asyncio.
* ``forge_status`` — what is the build state for the
  project at ``root_path``?
* ``forge_export`` — draft the canonical export package
  for the chosen platform (``.apk``, ``.hap``, AppImage,
  ``.msi`` / ``.exe``, ``.deb``, ``.rpm``).
* ``forge_legal_notice`` — return the academic / legal use
  notice for any reverse-related tool routing here.

Lawful use
----------
Reverse engineering tools are exposed separately via the
``reverse_studio`` worker (see ``reverse_studio.py``).
DevForge does NOT bundle reverse capabilities — it focuses
on **building** apps for the four target platforms.
"""

from __future__ import annotations

import asyncio
import json
import re  # noqa: E402  (intentional location — used by _app_class)
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from minxg.base import BaseWorker, tool
from minxg.five_pillars.devtools.templates import (
    PLATFORMS, PLATFORM_DISPLAY, FRAMEWORKS,
    render_entrypoint, build_command,
)


_BUILD_LABEL = "minxg-quad-forge"


def _validate_pkg(pkg: str) -> Tuple[bool, str]:
    """Lenient package-name check.

    Accepts the dotted Java-style naming (Android, ArkTS)
    AND simple ident pkg (WinUI).  Rejects empty/whitespace.
    """
    if not pkg or not pkg.strip():
        return False, "package must be non-empty"
    s = pkg.strip()
    if len(s) > 128:
        return False, "package too long (>128)"
    return True, "ok"


def _validate_title(title: str) -> Tuple[bool, str]:
    if not title or len(title) > 80:
        return False, "title 1..80 chars"
    if any(c in title for c in "<>{}|\\"):
        return False, "title must not contain <>{}|\\"
    return True, "ok"


# ─── Worker ──────────────────────────────────────────────────────────


class QuadForgeWorker(BaseWorker):
    """Quad-OS development forge worker.

    ``QuadForge`` is the unifying name for MINXG's four-platform
    development toolchain: **Android** (via Buildozer/python-for-android),
    **HarmonyOS NEXT** (ArkTS + hvigor), **Linux** (PyQt/GTK/Tauri),
    and **Windows** (WinUI 3 / .NET / MSIX).

    One facade scaffolds, validates, builds, and exports projects
    for all four operating systems.  ``DevForgeWorker`` is preserved
    as a backward-compat alias — callers that imported it under the
    v0.18.0 name keep working unchanged.

    Reverse engineering capabilities are NOT here — they live in
    :class:`ReverseStudioWorker` with its own liability disclaimer.
    """

    worker_id = "quad_forge"
    version = "0.18.1"
    tier = "code"        # v0.18.x three-tier classification
    _category = "deploy"

    # ── Discovery ──────────────────────────────────────────────────
    @tool(
        description=(
            "List every (platform × framework) pair DevForge can "
            "scaffold / build / export.  Returned list is the "
            "discovery source the AI iterates before forging."
        ),
        category="deploy",
    )
    async def forge_capabilities(self) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for plat in PLATFORMS:
            for fw in FRAMEWORKS.get(plat, []):
                items.append({
                    "platform": plat,
                    "platform_label": PLATFORM_DISPLAY.get(plat, plat),
                    "framework": fw,
                    "build_cmd": build_command(plat, fw),
                    "exports": _exports_for(plat, fw),
                })
        return {
            "status": "ok",
            "platforms": list(PLATFORMS),
            "platform_display": dict(PLATFORM_DISPLAY),
            "count": len(items),
            "matrix": items,
        }

    # ── Plan ─────────────────────────────────────────────────────────
    @tool(
        description=(
            "Validate a manifest for ANY (platform, framework).  "
            "Returns blueprint + notes + suggested build command.  "
            "Call ``forge_scaffold`` for actual file emission."
        ),
        category="deploy",
    )
    async def forge_plan(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(manifest, dict):
            return {"status": "error", "error": "manifest must be a dict"}
        notes: List[str] = []

        plat = str(manifest.get("platform", "android")).lower()
        if plat not in PLATFORMS:
            return {"status": "error",
                    "error": f"platform must be one of {PLATFORMS}"}

        framework = str(manifest.get("framework", "")).lower()
        if framework not in FRAMEWORKS.get(plat, []):
            return {"status": "error",
                    "error": (f"framework {framework!r} not supported "
                              f"for {plat}; available: "
                              f"{FRAMEWORKS.get(plat, [])}")}

        pkg_ok, pkg_msg = _validate_pkg(manifest.get("package", ""))
        notes.append(f"package: {pkg_msg}")
        title_ok, title_msg = _validate_title(manifest.get("title", ""))
        notes.append(f"title: {title_msg}")

        blueprint = {
            "platform": plat,
            "platform_label": PLATFORM_DISPLAY.get(plat, plat),
            "framework": framework,
            "package": manifest.get("package", ""),
            "title": manifest.get("title", "MINXG"),
            "version": str(manifest.get("version", "0.1.0")),
            "permissions": list(manifest.get("permissions", [])),
            "python_version": str(manifest.get("python_version", "3.11")),
            "offline_only": bool(manifest.get("offline_only", False)),
            "icon": manifest.get("icon"),
            "build_cmd": build_command(plat, framework),
        }
        return {
            "status": "ok" if pkg_ok and title_ok else "checks_failed",
            "blueprint": blueprint,
            "notes": notes,
            "exports": _exports_for(plat, framework),
            "toolchain_available": _check_toolchain(plat, framework),
        }

    # ── Scaffold ────────────────────────────────────────────────────
    @tool(
        description=(
            "Write a fresh project tree to ``root_path`` for the "
            "given blueprint (produced by ``forge_plan``).  "
            "Returns the list of paths created."
        ),
        category="deploy",
    )
    async def forge_scaffold(
        self, root_path: str, blueprint: Dict[str, Any],
        entry_filename: str = "main.py",
    ) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"status": "error", "error": f"mkdir: {e}"}

        fw = blueprint.get("framework", "")
        entry_text = render_entrypoint(
            fw,
            app_class=_app_class(blueprint),
            title=blueprint.get("title", "MINXG"),
            package=blueprint.get("package", "ai.minxg"),
        )

        created: List[str] = []
        if entry_text:
            ext = _entry_ext(fw)
            entry = root / f"{Path(entry_filename).stem}{ext}"
            entry.write_text(entry_text)
            created.append(str(entry))

        manifest_path = root / "minxg-manifest.json"
        manifest_path.write_text(json.dumps(blueprint, indent=2,
                                             sort_keys=True))
        created.append(str(manifest_path))

        # build / build.sh whenever a real builder is detected
        builder = build_command(blueprint.get("platform", "android"), fw)
        if builder:
            build_file = root / ("build.sh" if not _is_windows_cmd(builder)
                                  else "build.cmd")
            build_file.write_text(_render_builder(builder, blueprint))
            created.append(str(build_file))

        return {
            "status": "ok",
            "root": str(root),
            "platform": blueprint.get("platform"),
            "framework": blueprint.get("framework"),
            "created": created,
        }

    # ── Build ────────────────────────────────────────────────────────
    @tool(
        description=(
            "Dispatch a real build for the chosen platform.  Uses "
            "asyncio so the event loop stays responsive for "
            "long-running compilations.  Timeout defaults 1800s.  "
            "Returns the tail of stdout and the return code."
        ),
        category="deploy",
    )
    async def forge_build(
        self, root_path: str, blueprint: Dict[str, Any],
        timeout_s: int = 1800,
    ) -> Dict[str, Any]:
        plat = blueprint.get("platform", "android")
        fw = blueprint.get("framework", "")
        cmd = build_command(plat, fw)
        if not cmd:
            return {"status": "error",
                    "error": f"no builder registered for {plat}/{fw}"}

        if not any(shutil.which(arg.split("/")[0]) is not None
                    for arg in cmd):
            return {
                "status": "disabled",
                "tool": "forge_build",
                "hint": (f"toolchain for {plat}/{fw} not on PATH.  "
                         f"Needed: {cmd}"),
            }

        cwd = Path(root_path).expanduser()
        if not cwd.exists():
            return {"status": "error", "error": f"{cwd} missing"}

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        buf: List[bytes] = []
        try:
            while True:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=timeout_s)
                if not line:
                    break
                buf.append(line)
        except asyncio.TimeoutError:
            proc.kill()
            return {"status": "timeout",
                    "tool": "forge_build",
                    "stdout_tail": _tail(buf)}
        await proc.wait()
        return {
            "status": "ok" if proc.returncode == 0 else "build_failed",
            "tool": "forge_build",
            "returncode": proc.returncode,
            "stdout_tail": _tail(buf),
        }

    # ── Status ───────────────────────────────────────────────────────
    @tool(
        description=(
            "Inspect the project at ``root_path``: manifest hash, "
            "whether any builder has produced an output bundle, and "
            "the size of the manifest file.  Useful before showing "
            "a build report to the user."
        ),
        category="deploy",
    )
    async def forge_status(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        manifest_file = root / "minxg-manifest.json"
        if not manifest_file.exists():
            return {"status": "error",
                    "error": "no minxg-manifest.json",
                    "hint": "call forge_scaffold first"}

        bp = json.loads(manifest_file.read_text())
        plat = bp.get("platform", "android")
        fw = bp.get("framework", "")
        outputs: List[str] = []
        if plat == "android":
            bdir = root / ".buildozer" / "android" / "platform"
            if bdir.exists():
                outputs = sorted(str(p) for p in bdir.rglob("*.apk"))
        elif plat == "harmonyos":
            bdir = root / "build" / "default" / "outputs"
            if bdir.exists():
                outputs = sorted(str(p) for p in bdir.rglob("*.hap"))
        elif plat == "linux":
            outputs = sorted(str(p) for p in root.rglob("AppImage")
                              + list(root.rglob("*.deb"))
                              + list(root.rglob("*.rpm")))
        elif plat == "windows":
            outputs = sorted(str(p) for p in root.rglob("*.exe")
                              + list(root.rglob("*.msi")))

        return {
            "status": "ok",
            "root": str(root),
            "platform": plat,
            "framework": fw,
            "build_cmd": build_command(plat, fw),
            "outputs": outputs,
            "manifest_bytes": manifest_file.stat().st_size,
        }

    # ── Export ───────────────────────────────────────────────────────
    @tool(
        description=(
            "Emit the canonical export package descriptor for the "
            "chosen platform.  Returns the inventory of files that "
            "should be bundled, the path the bundle lives at, and "
            "any platform-specific output instructions."
        ),
        category="deploy",
    )
    async def forge_export(
        self, root_path: str, blueprint: Dict[str, Any],
    ) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        if not root.exists():
            return {"status": "error", "error": f"{root} missing"}
        files: List[str] = []
        include = ("*.py", "*.kt", "*.swift", "*.ts", "*.tsx",
                   "package.json", "Cargo.toml", "App.config",
                   "App.xaml", "build.gradle", "pubspec.yaml")
        for pat in include:
            files.extend(sorted(str(p) for p in root.rglob(pat)))
        return {
            "status": "ok",
            "root": str(root),
            "files": files[:256],
            "total": len(files),
            "platforms_supported": list(PLATFORMS),
            "note": ("call forge_build with the right blueprint to "
                     "produce the actual .apk / .hap / appimage / "
                     ".exe / .msi artifact for this project."),
        }

    # ── Legal notice ─────────────────────────────────────────────────
    @tool(
        description=(
            "Return the academic-use / liability disclosure for "
            "DevForge operations.  Same content as ReverseStudio's "
            "so the AI can show the user before any reverse "
            "routing makes sense."
        ),
        category="deploy",
    )
    async def forge_legal_notice(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "scope": ("DevForge does not bundle reverse engineering "
                       "tools.  Reverse capabilities live in the "
                       "reverse_studio worker."),
            "academic_use_clause": ("Reverse engineering is permitted "
                                     "ONLY for academic, security-audit, "
                                     "or interoperability research under "
                                     "EU Directive 2009/24/EC Art. 6 or "
                                     "US DMCA §1201(f).  Bypassing any "
                                     "DRM or copying protected code is "
                                     "your sole responsibility — MINXG "
                                     "disclaims all liability."),
        }


# ─── Helpers ────────────────────────────────────────────────────────


def _app_class(blueprint: Dict[str, Any]) -> str:
    """Return a sensible PascalCase class name from a blueprint title."""
    t = str(blueprint.get("title", "App"))
    out = re.sub(r"[^A-Za-z0-9 ]", "", t).title().replace(" ", "")
    return out or "App"


def _entry_ext(framework: str) -> str:
    """File extension picked for the given framework entrypoint."""
    return {
        "kivy": ".py", "termux_python": ".py", "flet": ".py",
        "kotlin_compose": ".kt", "flutter": ".dart",
        "react_native": ".tsx", "cordova": ".js",
        "arkts": ".ets", "arkui": ".ets", "harmonyos_native": ".ets",
        "harmonyos_web": ".js",
        "tauri": ".rs", "gtk4": ".c", "qt6": ".cpp", "pyqt6": ".py",
        "fltk": ".cpp", "electron": ".js",
        "winui3": ".cs", "wpf": ".cs", "winforms": ".cs",
        "uwp": ".cs", "msix": ".cs",
        "pyinstaller": ".py", "wsl_linux": ".sh",
    }.get(framework, ".py")


def _is_windows_cmd(cmd: List[str]) -> bool:
    """True if the builder is invoked through ``cmd.exe`` (Windows)."""
    return cmd and cmd[0].split("/")[0] in {"dotnet", "msbuild"}


def _render_builder(cmd: List[str], blueprint: Dict[str, Any]) -> str:
    """Render a shell-friendly script that runs the builder for *cmd*."""
    plat = blueprint.get("platform", "android")
    fw = blueprint.get("framework", "")
    head = ("@echo off\n# build for {plat}/{fw}\n"
             if _is_windows_cmd(cmd)
             else "#!/usr/bin/env bash\n# build for {plat}/{fw}\nset -e\n").format(
                 plat=plat, fw=fw)
    body = " ".join(cmd)
    return head + body + "\n"


def _tail(buf: List[bytes], n: int = 200) -> List[str]:
    return [ln.decode("utf-8", "replace").rstrip()
            for ln in buf[-n:]] if buf else []


def _exports_for(platform: str, framework: str) -> List[str]:
    """Return the canonical **output bundle extensions** for a (p,f)."""
    return {
        "android":    ["apk", "aab"],
        "harmonyos":  ["hap"],
        "linux":      ["AppImage", "deb", "rpm", "tar.gz"],
        "windows":    ["exe", "msi"],
    }.get(platform, [])


def _check_toolchain(platform: str, framework: str) -> Dict[str, bool]:
    """Best-effort availability probe of the framework's toolchain."""
    cmd = build_command(platform, framework)
    return {tool: shutil.which(tool) is not None
             for tool in cmd or []}




# Backward-compat alias — callers that imported DevForgeWorker
# under the v0.18.0 name keep working unchanged.
DevForgeWorker = QuadForgeWorker


__all__ = ["QuadForgeWorker", "DevForgeWorker"]
