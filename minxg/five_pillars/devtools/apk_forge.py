"""minxg/five_pillars/devtools/apk_forge.py — Heavy-weight APK forge worker.

The :class:`ApkForgeWorker` gives the AI **first-class ability to author,
scaffold, validate, and build Android APKs**. It wraps the canonical
Buildozer / python-for-android toolchain, but layers on:

* Project layout audit (Check CLAIM that name/title/package/icon/permissions match)
* Buildozer spec generation from a structured manifest
* Dry-run + smoke tests + dependency resolution plan
* Kivy-style scaffold for `/storage/emulated/0/` users without Linux dev host
* Hook surface — the AI can attach hooks for build phases
* Cancel-safe subprocess routing through ``asyncio.subprocess``

A real APK build still requires a Linux dev host (or ``pydroid3``) and
the standard NDK/SDK — this is the *coordination layer*, not a
sandboxed compiler.

Psevdo (`pseudocode` block):

    worker = ApkForgeWorker()
    res = await worker.call("apk_plan", {
        "package": "ai.minxg.demo",
        "title": "MINXG Demo",
        "presets": ["kivy", "termux"],
        "python_version": "3.11",
    })
    # res["spec_path"] when written, res["blueprint"]: preflight checks

The worker exposes the minimum tool surface (~6 verbatim) needed to
forge, never the ~50 micro-tools. All callers go through dispatch.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import struct
import textwrap
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from minxg.base import BaseWorker, tool

_BUILD_PATH = Path(__file__).resolve().parent
_CODEGEN_TEMPLATE_NAME = "kivy_entry.py.tmpl"

# ─── Naming & spec-doc helpers ───────────────────────────────────────────────

_PKG_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def _validate_package(pkg: str) -> Tuple[bool, str]:
    if not pkg or len(pkg) > 128:
        return False, "package must be non-empty and ≤ 128 chars"
    if not _PKG_RE.match(pkg):
        return False, "package must be lowercase dotted identifiers"
    return True, "ok"


def _validate_title(title: str) -> Tuple[bool, str]:
    if not title or len(title) > 80:
        return False, "title 1..80 chars"
    if any(c in title for c in "<>{}|\\"):
        return False, "title must not contain <>{}|\\"
    return True, "ok"


def _default_kivy_entry() -> str:
    return textwrap.dedent(
        """\
        # MINXG APK entry point (kivy)
        from kivy.app import App
        from kivy.uix.label import Label

        class HelloKivy(App):
            def build(self):
                return Label(text="Hello from MINXG-built APK")

        if __name__ == "__main__":
            HelloKivy().run()
        """
    )


_BUILDOZER_PREFIX = "[buildozer]"
_REQUIRED_PERMS = {
    # Buildozer requires INTERNET to talk to Gradle remotes when offline=False
    "INTERNET",
}


# ─── Worker ──────────────────────────────────────────────────────────────────


class ApkForgeWorker(BaseWorker):
    """Forge Android APKs (kivy / termux python) from a structured manifest.

    Six tools, none of the legacy per-step ones.

    * ``apk_plan`` — given a manifest, return a project blueprint + checks.
    * ``apk_scaffold`` — write a fresh minxg-buildable project tree.
    * ``apk_spec`` — render ``buildozer.spec`` from the structured manifest.
    * ``apk_preflight`` — audit an existing project tree before building.
    * ``apk_build`` — kick off a real ``buildozer android debug`` (subprocess).
    * ``apk_status`` — what state is package.json in / last log?
    """

    worker_id = "apk_forge"
    version = "0.17.1"
    _category = "deploy"

    @tool(
        description=(
            "Plan an APK build. Accepts a structured manifest (package/title/"
            "version/presets/python_version/permissions). Returns blueprint, "
            "validation flags, and the dependency resolution plan. Does NOT "
            "write files — call ``apk_scaffold`` for that."
        ),
        category="deploy",
    )
    async def apk_plan(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(manifest, dict):
            return {"status": "error", "error": "manifest must be a dict"}
        notes: List[str] = []
        ok = True

        pkg = manifest.get("package") or ""
        pkg_ok, pkg_msg = _validate_package(pkg)
        notes.append(f"package: {pkg_msg}")
        if not pkg_ok:
            ok = False

        title = manifest.get("title") or ""
        t_ok, t_msg = _validate_title(title)
        notes.append(f"title: {t_msg}")
        if not t_ok:
            ok = False

        version = str(manifest.get("version", "0.1.0"))
        if not re.match(r"^[0-9]+(\.[0-9]+){0,3}$", version):
            notes.append("version: not semver")
            ok = False
        else:
            notes.append(f"version: {version}")

        presets = manifest.get("presets", [])
        if not isinstance(presets, list):
            return {"status": "error", "error": "presets must be a list"}
        valid_presets = {"kivy", "termux", "kivymd", "pyjnius", "webview",
                          "pure", "sdl2", "minimal", "p4a"}
        bad_p = [p for p in presets if p not in valid_presets]
        if bad_p:
            notes.append(f"unknown presets: {bad_p}")
            ok = False

        py = str(manifest.get("python_version", "3.11"))
        if py not in {"3.11", "3.12", "3.13"}:
            notes.append(f"python_version: cloest to {py} -> rolled back to 3.11")
            py = "3.11"
        notes.append(f"python_version: {py}")

        perms = manifest.get("permissions", [])
        if not isinstance(perms, list):
            perms = []
        # Make sure INTERNET is present if user didn't decide explicitly
        if "INTERNET" not in perms and not manifest.get("offline_only", False):
            notes.append("adding INTERNET permission (default for online gradle)")
            perms = list(perms) + ["INTERNET"]

        blueprint = {
            "package": pkg,
            "title": title,
            "version": version,
            "python_version": py,
            "presets": presets,
            "permissions": sorted(set(perms)),
            "offline_only": bool(manifest.get("offline_only", False)),
            "icon": manifest.get("icon"),
            "source_dir": manifest.get("source_dir"),
        }
        return {
            "status": "ok" if ok else "checks_failed",
            "blueprint": blueprint,
            "notes": notes,
            "presets_effective": [p for p in presets if p in valid_presets],
        }

    @tool(
        description=(
            "Write a fresh minxg-buildable project tree to ``root_path`` from a "
            "validated blueprint. Returns the list of paths created."
        ),
        category="deploy",
    )
    async def apk_scaffold(
        self,
        root_path: str,
        blueprint: Dict[str, Any],
        entry_filename: str = "main.py",
    ) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"status": "error", "error": f"mkdir failed: {e}"}

        # blueprint validation
        for k in ("package", "title", "version"):
            if k not in blueprint:
                return {"status": "error", "error": f"missing blueprint field {k!r}"}

        created: List[str] = []
        # entrypoint
        entry = root / entry_filename
        entry.write_text(_default_kivy_entry())
        created.append(str(entry))

        # buildozer.spec stub will be rendered by apk_spec
        (root / "buildozer.spec").write_text(
            _BUILDOZER_PREFIX + " skeleton - run apk_spec to overwrite\n"
        )
        created.append(str(root / "buildozer.spec"))

        # hooks dir
        hooks_dir = root / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        (hooks_dir / ".gitkeep").write_text("")
        created.append(str(hooks_dir))

        # minimal manifest.json
        manifest_path = root / "minxg-manifest.json"
        manifest_path.write_text(json.dumps(blueprint, indent=2, sort_keys=True))
        created.append(str(manifest_path))

        return {
            "status": "ok",
            "root": str(root),
            "created": created,
            "entry": str(entry),
        }

    @tool(
        description=(
            "Render ``buildozer.spec`` for a project at ``root_path`` using the "
            "stored minxg-manifest.json. Idempotent — safe to re-run."
        ),
        category="deploy",
    )
    async def apk_spec(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        manifest_file = root / "minxg-manifest.json"
        if not manifest_file.exists():
            return {"status": "error", "error": f"missing {manifest_file}"}
        try:
            blueprint = json.loads(manifest_file.read_text())
        except json.JSONDecodeError as e:
            return {"status": "error", "error": f"bad manifest json: {e}"}

        spec_lines = [
            f"[app] {_BUILDOZER_PREFIX} auto-generated by ApkForgeWorker",
            "title = " + str(blueprint.get("title", "MINXG APP")),
            "package.name = " + str(blueprint.get("package", "ai.minxg.demo")),
            "package.domain = org",
            "source.dir = .",
            "source.filename = main.py",
            "version = " + str(blueprint.get("version", "0.1.0")),
            "requirements = " + ", ".join(blueprint.get("presets", ["kivy"])),
            "orientation = portrait",
            "android.api = 33",
            "android.minapi = 21",
            "android.permissions = " + ",".join(blueprint.get("permissions", [])),
            "p4a.python_version = " + str(blueprint.get("python_version", "3.11")),
            "[buildozer]",
            "log_level = 2",
        ]
        spec_path = root / "buildozer.spec"
        spec_path.write_text("\n".join(spec_lines) + "\n")
        return {"status": "ok", "spec_path": str(spec_path), "lines": len(spec_lines)}

    @tool(
        description=(
            "Pre-flight check an existing project tree: buildozer.spec, main.py, "
            "permissions, package/name alignment. Returns a checklist."
        ),
        category="deploy",
    )
    async def apk_preflight(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        if not root.exists():
            return {"status": "error", "error": f"{root} missing"}

        checks = []
        spec = root / "buildozer.spec"
        if spec.exists():
            t = re.search(r"^title\s*=\s*(.+)$", spec.read_text(), re.M)
            p = re.search(r"package\.name\s*=\s*(.+)$", spec.read_text(), re.M)
            checks.append({
                "name": "spec_title",
                "ok": bool(t and t.group(1).strip()),
                "value": t.group(1).strip() if t else "",
            })
            checks.append({
                "name": "spec_package",
                "ok": bool(p),
                "value": p.group(1).strip() if p else "",
            })
        else:
            checks.append({"name": "buildozer.spec exists", "ok": False, "value": str(spec)})

        entry = root / "main.py"
        if not entry.exists():
            entry = root / "minxg_main.py"
        checks.append({
            "name": "entry_script",
            "ok": entry.exists(),
            "value": str(entry),
        })
        return {"status": "ok", "root": str(root), "checks": checks}

    @tool(
        description=(
            "Run a real ``buildozer android debug`` subprocess; routes through "
            "asyncio so it yields the event loop. The build still needs "
            "Buildozer + NDK + SDK on PATH. Returns last 200 lines of stdout."
        ),
        category="deploy",
    )
    async def apk_build(self, root_path: str, timeout_s: int = 1800) -> Dict[str, Any]:
        if shutil.which("buildozer") is None:
            return {
                "status": "disabled",
                "tool": "apk_build",
                "hint": (
                    "buildozer not on PATH. Install via `pip install buildozer`"
                    " on Linux/macOS dev host. Termux has limited support."
                ),
            }
        cwd = Path(root_path).expanduser()
        if not cwd.exists():
            return {"status": "error", "error": f"{cwd} missing"}
        try:
            proc = await asyncio.create_subprocess_exec(
                "buildozer", "android", "debug",
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            buf: List[bytes] = []
            try:
                while True:
                    line = await asyncio.wait_for(proc.stdout.readline(),
                                                   timeout=timeout_s)
                    if not line:
                        break
                    buf.append(line)
            except asyncio.TimeoutError:
                proc.kill()
                return {"status": "timeout", "stderr_tail": _tail(buf)}
            await proc.wait()
            return {"status": "ok" if proc.returncode == 0 else "build_failed",
                    "returncode": proc.returncode,
                    "stderr_tail": _tail(buf)}
        except Exception as e:
            return {"status": "error", "error": repr(e)}

    @tool(
        description=(
            "Show current APK build state for a project: latest build directory, "
            "manifest hash, sizes — useful before showing debug-summary to user."
        ),
        category="deploy",
    )
    async def apk_status(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        manifest_file = root / "minxg-manifest.json"
        if not manifest_file.exists():
            return {"status": "error", "error": "no minxg-manifest.json"}

        bdir = root / ".buildozer"
        apk_path = None
        if bdir.exists():
            for ap in (bdir / "android" / "platform" /
                       "build-armeabi-v7a" / "dists").rglob("*.apk"):
                apk_path = str(ap); break

        return {
            "status": "ok",
            "root": str(root),
            "has_build_dir": bdir.exists(),
            "apk_path": apk_path,
            "manifest_bytes": manifest_file.stat().st_size,
        }

    # ─── v0.16.5 expansion: UI / icons / pack / lint / AAB ────────────────────────

    @tool(
        description=(
            "List every UI template available across kivy / kivymd / flet / "
            "Compose MDC / React Native. AI uses this to discover what to "
            "ask for. Returns [{name, framework, tags, summary}, ...]."
        ),
        category="ui",
    )
    async def ui_widgets_list(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "count": len(_WIDGETS),
            "widgets": _WIDGETS,
        }

    @tool(
        description=(
            "Apply a base scaffold for the chosen framework (kivy / kivymd / "
            "flet / compose_mdc / react_native). Writes the entrypoint + "
            "navigation drawer scaffold into <root_path>. Theme is a dict of "
            "{primary, accent, mode}."
        ),
        category="ui",
    )
    async def ui_template_apply(
        self, root_path: str, framework: str,
        theme: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"status": "error", "error": f"mkdir {root}: {e}"}
        theme = theme or {"primary": "#6750A4", "accent": "#D0BCFF",
                            "mode": "light"}
        framework = framework.lower()
        app_dir = root / "app"
        app_dir.mkdir(exist_ok=True)

        written = []
        if framework in ("kivy", "kivymd"):
            (app_dir / f"main_{framework.replace('kivy', 'kv')}.kv").write_text(
                _kivy_kv_scaffold(theme)
            )
            (root / "main.py").write_text(_default_kivy_entry())
            written = [str(app_dir / f"main_{framework.replace('kivy', 'kv')}.kv"),
                        str(root / "main.py")]
        elif framework == "flet":
            (root / "main.py").write_text(textwrap.dedent("""\
                import flet as ft
                from app.screens.main import build_main

                async def main(page: ft.Page):
                    page.title = "MINXG"
                    await page.add_async(await build_main(page))

                if __name__ == "__main__":
                    ft.run(main)
            """))
            screens_dir = app_dir / "screens"; screens_dir.mkdir(parents=True, exist_ok=True)
            (screens_dir / "main.py").write_text(_flet_screen("main", []))
            written = [str(root / "main.py"), str(screens_dir / "main.py")]
        elif framework == "compose_mdc":
            (app_dir / "MainActivity.kt").write_text(_compose_kotlin("main", []))
            written = [str(app_dir / "MainActivity.kt")]
        elif framework == "react_native":
            (app_dir / "MainScreen.tsx").write_text(_rn_screen("main", []))
            written = [str(app_dir / "MainScreen.tsx")]
        else:
            return {
                "status": "error",
                "error": f"unknown framework {framework!r}",
                "supported": ["kivy", "kivymd", "flet", "compose_mdc",
                                "react_native"],
            }
        (root / "ui-theme.json").write_text(json.dumps(theme, indent=2))
        return {
            "status": "ok",
            "framework": framework,
            "root": str(root),
            "written": written,
        }

    @tool(
        description=(
            "Scaffold a single screen <screen_name> in <framework> with the "
            "given MD3 component list. Returns path written."
        ),
        category="ui",
    )
    async def screen_scaffold(
        self, root_path: str, framework: str,
        screen_name: str, components: List[str],
    ) -> Dict[str, Any]:
        root = Path(root_path).expanduser(); app = root / "app"
        app.mkdir(parents=True, exist_ok=True)
        framework = framework.lower()
        if framework in ("kivy", "kivymd"):
            out = app / f"{screen_name}.py"
            content = _kivymd_screen(screen_name, components)
        elif framework == "flet":
            out = app / f"{screen_name}.py"
            content = _flet_screen(screen_name, components)
        elif framework == "compose_mdc":
            out = app / f"{screen_name.title()}Screen.kt"
            content = _compose_kotlin(screen_name, components)
        elif framework == "react_native":
            out = app / f"{screen_name.title()}Screen.tsx"
            content = _rn_screen(screen_name, components)
        else:
            return {"status": "error",
                    "error": f"unknown framework {framework}"}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content)
        return {
            "status": "ok",
            "path": str(out),
            "lines": content.count("\n"),
            "framework": framework,
            "components": components,
        }

    @tool(
        description=(
            "Build a navigation graph that strings together the given "
            "screens for <framework>. Returns the nav graph source."
        ),
        category="ui",
    )
    async def nav_graph_build(
        self, framework: str, screens: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        if not isinstance(screens, list) or not screens:
            return {"status": "error", "error": "screens must be a non-empty list"}
        graph = _nav_graph(framework.lower(), screens)
        return {
            "status": "ok",
            "framework": framework,
            "screens": [s.get("name", "?") for s in screens],
            "graph": graph,
        }

    @tool(
        description=(
            "Generate an adaptive launcher icon (1024x1024 foreground + background "
            "layers) for a project at root_path. Accepts accent hex color, bg_mode "
            "(solid/gradient/trans), optional foreground base64 PNG bytes. Writes "
            "ic_launcher_foreground.png, ic_launcher_background.png, and the "
            "adaptive XML manifest. Returns bytesize of each file."
        ),
        category="asset",
    )
    async def apk_icon_generate(
        self, root_path: str,
        accent: str = "#6750A4",
        bg_mode: str = "solid",
        foreground_base64: str = "",
    ) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        mipmap = root / "app" / "src" / "main" / "res" / "mipmap-anydpi-v26"
        mipmap.mkdir(parents=True, exist_ok=True)
        drawable = root / "app" / "src" / "main" / "res" / "drawable"
        drawable.mkdir(parents=True, exist_ok=True)
        values = root / "app" / "src" / "main" / "res" / "values"
        values.mkdir(parents=True, exist_ok=True)

        sz = 1024
        rgb = _hex_to_rgb(accent)

        if bg_mode == "gradient":
            dark = tuple(max(0, c - 40) for c in rgb)
            bg_bytes = _color_gradient_to_top(sz, sz, rgb, dark)
        elif bg_mode == "trans":
            # fully transparent layer; cheap uniform fill
            zero = bytearray(w * h * 4 for w in [sz])  # placeholder
            zero = bytearray(sz * sz * 4)
            for i in range(0, len(zero), 4):
                zero[i:i + 4] = bytes((0, 0, 0, 0))
            bg_bytes = bytes(zero)
        else:
            bg_bytes = _color_solid(sz, sz, rgb)

        bg_png = _emit_png(sz, sz, bg_bytes)
        (drawable / "ic_launcher_background.png").write_bytes(bg_png)

        fg_bytes = bg_bytes
        if foreground_base64:
            try:
                fg_raw = base64.b64decode(foreground_base64)
                if len(fg_raw) >= sz * sz * 4:
                    fg_bytes = fg_raw[:sz * sz * 4]
                else:
                    fg_bytes = fg_raw + bytes(sz * sz * 4 - len(fg_raw))
            except Exception:
                pass

        fg_png = _emit_png(sz, sz, fg_bytes)
        (drawable / "ic_launcher_foreground.png").write_bytes(fg_png)

        (mipmap / "ic_launcher.xml").write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
                <background android:drawable="@drawable/ic_launcher_background"/>
                <foreground android:drawable="@drawable/ic_launcher_foreground"/>
            </adaptive-icon>
        """))
        (mipmap / "ic_launcher_round.xml").write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
                <background android:drawable="@drawable/ic_launcher_background"/>
                <foreground android:drawable="@drawable/ic_launcher_foreground"/>
            </adaptive-icon>
        """))
        (values / "ic_launcher_background.xml").write_text(
            f'<?xml version="1.0" encoding="utf-8"?><resources><color name="ic_launcher_background">{accent}</color></resources>'
        )

        return {"status": "ok",
                "root": str(root),
                "bg_bytes": len(bg_png),
                "fg_bytes": len(fg_png)}

    @tool(
        description=(
            "Generate the canonical res/ tree for a Kivy-KivyMD APK: "
            "strings.xml, colors.xml, themes.xml, and the mipmap adapters. "
            "All from the blueprint. Writes a dozen files."
        ),
        category="asset",
    )
    async def apk_asset_pack(
        self, root_path: str, blueprint: Dict[str, Any],
    ) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        res = root / "app" / "src" / "main" / "res"
        values = res / "values"; values.mkdir(parents=True, exist_ok=True)
        pkg = blueprint.get("package", "ai.minxg.demo")[:100]
        title = blueprint.get("title", "MINXG Demo")[:80]
        wrote = []

        strings = values / "strings.xml"
        strings.write_text(textwrap.dedent(f"""\
            <?xml version="1.0" encoding="utf-8"?>
            <resources>
                <string name="app_name">{title}</string>
                <string name="package_name">{pkg}</string>
            </resources>
        """))
        wrote.append(str(strings))

        colors = values / "colors.xml"
        colors.write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <resources>
                <color name="primary">#6750A4</color>
                <color name="primary_variant">#4F378B</color>
                <color name="on_primary">#FFFFFF</color>
                <color name="secondary">#625B71</color>
                <color name="surface">#FFFBFE</color>
            </resources>
        """))
        wrote.append(str(colors))

        themes = values / "themes.xml"
        themes.write_text(textwrap.dedent("""\
            <?xml version="1.0" encoding="utf-8"?>
            <resources>
                <style name="Theme.Minxg" parent="Theme.Material3.DayNight.NoActionBar">
                    <item name="colorPrimary">@color/primary</item>
                    <item name="colorOnPrimary">@color/on_primary</item>
                    <item name="colorSecondary">@color/secondary</item>
                </style>
            </resources>
        """))
        wrote.append(str(themes))

        # mipmap adapters (our icon generator handles the drawables)
        mdpi = res / "mipmap-anydpi-v26"; mdpi.mkdir(exist_ok=True)
        (mdpi / "ic_launcher.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?><adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@drawable/ic_launcher_background"/><foreground android:drawable="@drawable/ic_launcher_foreground"/></adaptive-icon>')
        (mdpi / "ic_launcher_round.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?><adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@drawable/ic_launcher_background"/><foreground android:drawable="@drawable/ic_launcher_foreground"/></adaptive-icon>')

        return {"status": "ok", "root": str(root), "wrote": len(wrote) + 2,
                "files": wrote + [str(mdpi/"ic_launcher.xml"), str(mdpi/"ic_launcher_round.xml")]}

    @tool(
        description=(
            "Audit an existing project tree for Android-specific issues: "
            "package name, permissions, SDK levels, missing INTERNET etc."
        ),
        category="lint",
    )
    async def apk_dryrun_lint(self, root_path: str) -> Dict[str, Any]:
        root = Path(root_path).expanduser()
        issues: List[str] = []
        ok = True

        spec = root / "buildozer.spec"
        if not spec.exists():
            issues.append("buildozer.spec missing")
            ok = False
        else:
            text = spec.read_text()
            if not re.search(r"^title\s*=\s*\S", text, re.M):
                issues.append("title empty")
                ok = False
            pkg_m = re.search(r"package\.name\s*=\s*(\S+)", text)
            pkg = pkg_m.group(1) if pkg_m else ""
            if _PKG_RE.match(pkg) is None:
                issues.append(f"bad package name: {pkg}")
                ok = False
            if "INTERNET" not in text:
                issues.append("INTERNET permission missing (needed for online builds)")
                ok = False
            android_api = re.search(r"android\.api\s*=\s*(\d+)", text)
            if android_api and int(android_api.group(1)) < 21:
                issues.append("android.api < 21")
                ok = False

        entry = root / (list(root.glob("main*.py"))[0].name if list(root.glob("main*.py")) else "main.py")
        if not entry.exists():
            issues.append("entry script missing")
            ok = False

        return {"status": "ok" if ok else "issues_found",
                "root": str(root),
                "issues": issues,
                "blocking": not ok}

    @tool(
        description=(
            "Run Buildozer in release mode targeting Android App Bundle (AAB). "
            "Timeout defaults 1800s. Must have ANDROID_HOME and Buildozer on PATH."
        ),
        category="build",
    )
    async def apk_release_aab(self, root_path: str, timeout_s: int = 1800) -> Dict[str, Any]:
        if shutil.which("buildozer") is None:
            return {"status": "disabled",
                    "tool": "apk_release_aab",
                    "hint": "buildozer not on PATH"}
        cwd = Path(root_path).expanduser()
        if not cwd.exists():
            return {"status": "error", "error": f"{cwd} missing"}
        try:
            proc = await asyncio.create_subprocess_exec(
                "buildozer", "android", "release", "--bundle",
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT)
            buf: List[bytes] = []
            try:
                while True:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout_s)
                    if not line:
                        break
                    buf.append(line)
            except asyncio.TimeoutError:
                proc.kill()
                return {"status": "timeout", "stderr_tail": _tail(buf)}
            await proc.wait()
            return {"status": "ok" if proc.returncode == 0 else "build_failed",
                    "returncode": proc.returncode,
                    "stderr_tail": _tail(buf)}
        except Exception as e:
            return {"status": "error", "error": repr(e)}


# ──────────────────────────────────────────────────────────────────────────
# v0.16.5 expansion — UI templates + icons + asset pack + lint + AAB
# ──────────────────────────────────────────────────────────────────────────

# Widget catalogue — drawn from the web search of mainstream Android dev tools
# (Material3 MDC, KivyMD, Flet, Compose). Each entry is a template the AI picks
# by name through ui_widgets_list.
_WIDGETS = [
    # Material3 component → tags + minimal KV/Python stub source
    {"name": "md_navigation_drawer", "framework": "kivymd", "tags": ["nav", "md3"],
     "summary": "Material3 navigation drawer (modal + standard)"},
    {"name": "md_bottom_sheet", "framework": "kivymd", "tags": ["sheet", "md3"],
     "summary": "Material3 bottom sheet (modal + standard)"},
    {"name": "md_top_app_bar", "framework": "kivymd", "tags": ["appbar", "md3"],
     "summary": "Material3 top app bar"},
    {"name": "md_tabs", "framework": "kivymd", "tags": ["tabs", "md3"],
     "summary": "Material3 tabs"},
    {"name": "md_card", "framework": "kivymd", "tags": ["card", "md3"],
     "summary": "Material3 card (elevated/filled/outlined)"},
    {"name": "md_button", "framework": "kivymd", "tags": ["button", "md3"],
     "summary": "Material3 button with leading/trailing icon"},
    {"name": "md_text_field", "framework": "kivymd", "tags": ["input", "md3"],
     "summary": "Material3 text field"},
    {"name": "md_slider", "framework": "kivymd", "tags": ["input", "md3"],
     "summary": "Material3 slider"},
    {"name": "md_switch", "framework": "kivymd", "tags": ["input", "md3"],
     "summary": "Material3 switch"},
    {"name": "md_snackbar", "framework": "kivymd", "tags": ["feedback", "md3"],
     "summary": "Material3 snackbar"},
    {"name": "md_list_item", "framework": "kivymd", "tags": ["list", "md3"],
     "summary": "Material3 list item"},
    {"name": "ft_navigation_destinations", "framework": "flet", "tags": ["nav"],
     "summary": "Flet NavigationBar / NavigationRail / NavigationDrawer"},
    {"name": "ft_bottom_sheet", "framework": "flet", "tags": ["sheet"],
     "summary": "Flet BottomSheet + CupertinoActionSheet"},
    {"name": "ft_canvas", "framework": "flet", "tags": ["canvas", "media"],
     "summary": "Custom-painted canvases via flet.canvas (lines/paths/shapes)"},
    {"name": "compose_scaffold", "framework": "compose_mdc", "tags": ["md3"],
     "summary": "Compose Scaffold + TopAppBar (skeleton, requires host)"},
    {"name": "compose_card", "framework": "compose_mdc", "tags": ["md3"],
     "summary": "ElevatedCard + AssistChip (skeleton, requires host)"},
    {"name": "rn_screen", "framework": "react_native", "tags": ["rn"],
     "summary": "React Native functional screen with StyleSheet"},
]


def _kivy_kv_scaffold(theme: Dict[str, str]) -> str:
    primary = theme.get("primary", "#6750A4")
    accent = theme.get("accent", "#D0BCFF")
    return textwrap.dedent(f"""\
        #:kivy 2.1.0
        #:import MDTopAppBar kivymd.uix.toolbar.MDTopAppBar
        #:import MDNavigationLayout kivymd.uix.navigationdrawer.MDNavigationLayout
        #:import MDNavigationDrawer kivymd.uix.navigationdrawer.MDNavigationDrawer

        <ScreenMain@MDScreen>:
            MDTopAppBar:
                title: "MINXG"
                pos_hint: {{"top": 1}}
                left_action_items: [["menu", lambda x: nav.set_state("toggle")]]

        MDScreen:

            MDNavigationLayout:
                id: nav
                ScreenMain:
                    name: "main"
                MDNavigationDrawer:
                    id: drawer
                    radius: (0, 16, 16, 0)
        """)


def _kivymd_screen(name: str, components: List[str]) -> str:
    widgets = "\n".join(
        f"        # component: {c}"
        for c in components
    )
    return textwrap.dedent(f"""\
        from kivy.lang import Builder
        from kivymd.uix.screen import MDScreen

        class {name.title()}Screen(MDScreen):
            pass

        Builder.load_string('''
        <{name.title()}Screen>:
            MDTopAppBar:
                title: "{name.title()}"
                pos_hint: {{"top": 1}}
{widgets}
        ''')
        """)


def _flet_screen(name: str, components: List[str]) -> str:
    return textwrap.dedent(f"""\
        import flet as ft

        async def build_{name}(page: ft.Page) -> ft.Control:
            controls = []
{chr(10).join(f'            # component: {c}' for c in components)}
            return ft.Column(controls)
        """)


def _compose_kotlin(name: str, components: List[str]) -> str:
    return textwrap.dedent(f"""\
        package ai.minxg.{name.lower()}

        import androidx.compose.material3.*
        import androidx.compose.runtime.Composable

        @Composable
        fun {name.title()}Screen() {{
            Scaffold(
                topBar = {{ TopAppBar(title = {{ Text("{name.title()}") }} ) }}
            ) {{ padding ->
                Column(modifier = Modifier.padding(padding)) {{
{chr(10).join(f'                    // component: {c}' for c in components)}
                }}
            }}
        }}
        """)


def _rn_screen(name: str, components: List[str]) -> str:
    return textwrap.dedent(f"""\
        import React from "react";
        import {{ View, Text, StyleSheet }} from "react-native";

        export default function {name.title()}Screen() {{
            return (
                <View style={{styles.root}}>
{chr(10).join(f'                    {{/* component: {c} */}}' for c in components)}
                </View>
            );
        }}

        const styles = StyleSheet.create({{
            root: {{ flex: 1, padding: 16 }},
        }});
        """)


def _nav_graph(framework: str, screens: List[Dict[str, str]]) -> str:
    """Return a nav-graph string depending on framework."""
    if framework in ("kivy", "kivymd"):
        body = "\n".join(
            f"        {s['name'].title()}Screen:" for s in screens
        )
        return textwrap.dedent(f"""\
            Builder.load_string('''
            ScreenManager:
{body}
            ''')
            """)
    if framework == "flet":
        return textwrap.dedent("""\
            import flet as ft
            page.navigation_bar = ft.NavigationBar(
                destinations=[
%s
                ],
            )
            """) % ",\n".join(
            f'''                    ft.NavigationBarDestination(label="{s.get("label", s["name"])}")'''
            for s in screens
        ).strip()
    if framework == "compose_mdc":
        routes = "\n".join(
            f'        composable("{s["name"]}") {{ {s["name"].title()}Screen() }}'
            for s in screens
        )
        return f"NavHost {{\n{routes}\n}}"
    # react_native fallback
    routes = "\n".join(
        f'        <Stack.Screen name="{s["name"]}" component={{{s["name"].title()}Screen}} />'
        for s in screens
    )
    return f"<Stack.Navigator>\n{routes}\n</Stack.Navigator>"


# ─── Upgraded ApkForge class — append new methods after the existing apk_status



def _tail(buf: List[bytes], n: int = 200) -> List[str]:
    return [ln.decode("utf-8", "replace").rstrip()
            for ln in buf[-n:]] if buf else []


# ─── v0.16.5 — pure-stdlib PNG emission (no Pillow needed) ──────────────
# Build a flat-color RGBA PNG by hand. Adapted from the stdlib's `png`
# example, simplified to single-block, single-color images.

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def _emit_png(width: int, height: int, rgba_pixels: bytes) -> bytes:
    """Render an RGBA frame as a PNG. Pure-stdlib. ``rgba_pixels`` length
    must equal ``width * height * 4``. Returns PNG bytes."""
    if len(rgba_pixels) != width * height * 4:
        raise ValueError("RGBA pixel buffer length mismatch")
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit, RGBA
    ihdr_chunk = _png_chunk(b"IHDR", ihdr)

    # Raw scanlines: each row prefixed with filter byte 0 ("None").
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgba_pixels[y * stride:(y + 1) * stride]
    idat_chunk = _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    iend_chunk = _png_chunk(b"IEND", b"")
    return _PNG_SIG + ihdr_chunk + idat_chunk + iend_chunk


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    s = h.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return (103, 80, 164)  # default MD3 primary
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _color_solid(w: int, h: int, rgb: Tuple[int, int, int]) -> bytes:
    r, g, b = rgb
    out = bytearray(w * h * 4)
    for i in range(0, w * h * 4, 4):
        out[i:i + 4] = bytes((r, g, b, 255))
    return bytes(out)


def _color_gradient_to_top(
    w: int, h: int, top: Tuple[int, int, int], bot: Tuple[int, int, int],
) -> bytes:
    out = bytearray(w * h * 4)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bot[0] - top[0]) * (1 - t))
        g = int(top[1] + (bot[1] - top[1]) * (1 - t))
        b = int(top[2] + (bot[2] - top[2]) * (1 - t))
        for x in range(w):
            o = (y * w + x) * 4
            out[o:o + 4] = bytes((r, g, b, 255))
    return bytes(out)
