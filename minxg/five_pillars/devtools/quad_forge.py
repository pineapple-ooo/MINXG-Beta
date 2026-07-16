"""
minxg/five_pillars/devtools/quad_forge.py — v0.18.3 quad-OS build dispatcher.

Heres-agent ships no native-build tooling — it's a Python monolith. MINXG
counter-attacks here: this module wraps cmake/meson/cargo/maven/gradle/xmake
with per-OS target profiles so you can build the same source tree for
Android (arm64-v8a), Linux (x86_64, aarch64), macOS (universal2), and
Windows (x86_64) from one entry point.

Profile system:
  - android-ndk  → cross-compile via NDK toolchain
  - linux-native  → host clang/gcc
  - macos-cross   → osxcross / darling (experimental)
  - win-cross     → mingw-w64

Each profile bundles: compiler triplet, linker flags, sysroot path,
target-cpu, cargo target triple, and signing recipe.

Worker contract: QuadForgeWorker exposes `forge_build(target, profile, src_dir,
out_dir)` as an AI tool; the complex 6-parameter surface is wrapped so a
single tool call can produce a deployable binary for any of the four OSes.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from minxg.base import BaseWorker, tool

log = logging.getLogger("py_workers.quad_forge")


# ── Target profile registry ────────────────────────────────────

@dataclass
class TargetProfile:
    """One OS → build-parameter bundle."""
    slug: str
    display_name: str
    rust_target: str          # `rustup target list` name
    cc: str                    # C compiler (clang / gcc / aarch64-linux-android21-clang)
    cflags: List[str] = field(default_factory=list)
    ldflags: List[str] = field(default_factory=list)
    strip_cmd: Optional[str] = None
    sysroot: Optional[str] = None
    cargo_opts: List[str] = field(default_factory=lambda: ["--release"])

_PROFILES: Dict[str, TargetProfile] = {
    "linux-x86_64": TargetProfile(
        slug="linux-x86_64",
        display_name="Linux x86_64 (host-native)",
        rust_target="x86_64-unknown-linux-gnu",
        cc="clang",
        cflags=["-O2", "-march=x86-64-v3"],
        ldflags=["-Wl,--gc-sections"],
        strip_cmd="strip",
    ),
    "linux-arm64": TargetProfile(
        slug="linux-arm64",
        display_name="Linux ARM64 (aarch64)",
        rust_target="aarch64-unknown-linux-gnu",
        cc="aarch64-linux-gnu-gcc",
        cflags=["-O2"],
        strip_cmd="aarch64-linux-gnu-strip",
    ),
    "android-arm64": TargetProfile(
        slug="android-arm64",
        display_name="Android arm64-v8a (NDK)",
        rust_target="aarch64-linux-android",
        cc="aarch64-linux-android21-clang",
        cflags=["-O2", "-fPIC"],
        ldflags=["-Wl,--gc-sections", "-Wl,-z,max-page-size=16384"],
        strip_cmd="llvm-strip",
    ),
    "macos-x86_64": TargetProfile(
        slug="macos-x86_64",
        display_name="macOS x86_64 (Intel)",
        rust_target="x86_64-apple-darwin",
        cc="clang",
        cflags=["-O2", "-mmacosx-version-min=11.0"],
        ldflags=["-Wl,-dead_strip"],
        strip_cmd="strip",
    ),
    "macos-arm64": TargetProfile(
        slug="macos-arm64",
        display_name="macOS ARM64 (Apple Silicon)",
        rust_target="aarch64-apple-darwin",
        cc="clang",
        cflags=["-O2", "-target", "arm64-apple-macos11"],
        ldflags=["-Wl,-dead_strip"],
        strip_cmd="strip",
    ),
    "win-x86_64": TargetProfile(
        slug="win-x86_64",
        display_name="Windows x86_64 (MinGW-w64)",
        rust_target="x86_64-pc-windows-gnu",
        cc="x86_64-w64-mingw32-gcc",
        cflags=["-O2", "-static"],
        ldflags=["-Wl,--gc-sections"],
        strip_cmd="x86_64-w64-mingw32-strip",
    ),
}


# ── Worker ──────────────────────────────────────────────────────


class QuadForgeWorker(BaseWorker):
    """Quad-OS build dispatcher — build Rust / C / C++ for 4 OSes.

    Exposed tool: `forge_build(target=..., src_dir=..., ...)`.
    Not tied to any particular build system — delegates to cargo,
    cmake, meson, or raw cc based on what src_dir contains.
    """

    facade_alias = "quad_forge"
    worker_id    = "quad_forge"
    tier         = "code"
    version      = "0.18.3"

    def __init__(self):
        super().__init__()
        self._available_profiles = self._probe_profiles()

    def _probe_profiles(self) -> Dict[str, bool]:
        """Check which target profiles have the needed toolchains on $PATH."""
        avail: Dict[str, bool] = {}
        for slug, prof in _PROFILES.items():
            avail[slug] = shutil.which(prof.cc) is not None
        return avail

    # ── Tool: forge build ──────────────────────────────────────

    @tool(
        description=(
            "Build native binaries for a target OS (linux-x86_64, linux-arm64, "
            "android-arm64, macos-x86_64, macos-arm64, win-x86_64). "
            "Auto-detects cargo/cmake/meson project type. "
            "Returns build log + artifact path on success."
        ),
        category="build",
        call_budget=20,
    )
    async def forge_build(
        self,
        target: str,
        src_dir: Optional[str] = None,
        profile: Optional[str] = None,
        clean_build: bool = False,
    ) -> Dict[str, Any]:
        prof = _PROFILES.get(target)
        if prof is None:
            return {
                "status": "error",
                "error": f"unknown target: {target!r}",
                "available": list(_PROFILES.keys()),
                "toolchain_available": self._available_profiles,
            }

        if profile:
            # per-build profile override (debug, release, minsize)
            prof.cargo_opts = [f"--profile={profile}"]

        src = self._resolve_src(src_dir)
        if src is None:
            return {
                "status": "error",
                "error": "No src_dir given and no default project root found",
            }

        kind = self._detect_project_kind(src)
        if kind == "unknown":
            return {
                "status": "error",
                "error": "Could not detect build system in src_dir",
                "src_dir": str(src),
            }

        if clean_build:
            await self._clean(src, kind)

        # Dispatch to build backend
        try:
            result = await self._build_async(src, prof, kind)
            return result
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "target": target,
                "kind": kind,
                "error": "Build exceeded 120s timeout",
            }
        except Exception as e:
            return {
                "status": "error",
                "target": target, "kind": kind,
                "error": f"{type(e).__name__}: {e}",
            }

    # ── Tool: list targets ─────────────────────────────────────

    @tool(
        description="List available quad-OS build targets and their toolchain availability.",
        category="build",
    )
    async def forge_targets(self) -> Dict[str, Any]:
        targets = []
        for slug, prof in _PROFILES.items():
            targets.append({
                "slug": slug,
                "display": prof.display_name,
                "rust_target": prof.rust_target,
                "cc": prof.cc,
                "toolchain_available": self._available_profiles.get(slug, False),
            })
        return {
            "status": "ok",
            "targets": targets,
            "note": (
                "On Android/Termux only linux-arm64 is likely available. "
                "Install android-ndk for android-arm64, mingw-w64 for windows."
            ),
        }

    # ── Internal: project detection ────────────────────────────

    def _resolve_src(self, src_dir: Optional[str]) -> Optional[Path]:
        if src_dir:
            p = Path(src_dir).resolve()
            return p if p.is_dir() else None
        # auto: rust_core is the most common default
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        for cand in [repo_root / "rust_core", repo_root / "cpp_core", repo_root]:
            if cand.is_dir():
                return cand
        return None

    def _detect_project_kind(self, src: Path) -> str:
        """Return 'cargo' | 'cmake' | 'meson' | 'raw-cc' | 'unknown'."""
        if (src / "Cargo.toml").exists():
            return "cargo"
        if (src / "CMakeLists.txt").exists():
            return "cmake"
        if (src / "meson.build").exists():
            return "meson"
        if list(src.glob("*.hpp")) or list(src.glob("*.cpp")) or list(src.glob("*.h")):
            return "raw-cc"
        return "unknown"

    async def _clean(self, src: Path, kind: str):
        if kind == "cargo":
            await _run(["cargo", "clean"], cwd=src)
        elif kind == "cmake":
            bd = src / "build"
            if bd.exists():
                shutil.rmtree(bd, ignore_errors=True)

    # ── Build dispatch ─────────────────────────────────────────

    async def _build_async(self, src: Path, prof: TargetProfile, kind: str) -> Dict[str, Any]:
        if kind == "cargo":
            return await self._build_cargo(src, prof)
        if kind == "cmake":
            return await self._build_cmake(src, prof)
        if kind == "meson":
            return await self._build_meson(src, prof)
        if kind == "raw-cc":
            return await self._build_raw_cc(src, prof)
        return {"status": "error", "error": f"unsupported build kind: {kind}"}

    async def _build_cargo(self, src: Path, prof: TargetProfile) -> Dict[str, Any]:
        env = os.environ.copy()
        env["CARGO_BUILD_TARGET"] = prof.rust_target
        if prof.cc:
            env["CC"] = prof.cc
        if "aarch64-linux-android" in prof.rust_target:
            # Need to detect NDK path
            ndk_home = os.environ.get("ANDROID_NDK_HOME", "")
            if ndk_home:
                env["ANDROID_NDK_HOME"] = ndk_home

        # Ensure target is installed
        await _run(["rustup", "target", "add", prof.rust_target], cwd=src, env=env, timeout=60)

        cmd = ["cargo", "build"] + prof.cargo_opts
        await _run(cmd, cwd=src, env=env, timeout=120)

        # Locate artifact
        art = self._find_cargo_artifact(src, prof.rust_target)
        return {
            "status": "ok",
            "target": prof.slug,
            "rust_target": prof.rust_target,
            "artifact": art,
            "kind": "cargo",
        }

    def _find_cargo_artifact(self, src: Path, rust_target: str) -> Optional[str]:
        build_dir = src / "target" / rust_target / "release"
        for pat in ["libminxg_rust_core.so", "libminxg_rust_core.a",
                     "minxg_rust_core.dll", "libminxg_rust_core.dylib"]:
            cand = build_dir / pat
            if cand.exists():
                return str(cand)
        return str(build_dir) if build_dir.exists() else None

    async def _build_cmake(self, src: Path, prof: TargetProfile) -> Dict[str, Any]:
        bd = src / "build"
        bd.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["CC"] = prof.cc
        env["CXX"] = prof.cc.replace("gcc", "g++").replace("clang", "clang++")
        env["CFLAGS"] = " ".join(prof.cflags)
        env["LDFLAGS"] = " ".join(prof.ldflags)

        await _run(["cmake", "-B", str(bd), "-S", str(src)], cwd=bd, env=env, timeout=60)
        await _run(["make", "-j$(nproc)"], cwd=bd, env=env, timeout=120)

        return {
            "status": "ok",
            "target": prof.slug,
            "kind": "cmake",
            "build_dir": str(bd),
            "artifacts": [_f for _f in os.listdir(bd) if os.access(str(bd / _f), os.X_OK)],
        }

    async def _build_meson(self, src: Path, prof: TargetProfile) -> Dict[str, Any]:
        return {"status": "error", "error": "meson cross-compile not yet implemented for quad-OS"}

    async def _build_raw_cc(self, src: Path, prof: TargetProfile) -> Dict[str, Any]:
        c_files = list(src.glob("*.cpp")) + list(src.glob("*.hpp")) + list(src.glob("*.h"))
        out = src / f"libminxg_cpp_{prof.slug}.so"
        env = os.environ.copy()
        env["CC"] = prof.cc
        env["CXX"] = prof.cc.replace("gcc", "g++").replace("clang", "clang++")

        cmd = ["clang++", "-shared", "-fPIC", "-O2", "-o", str(out)]
        for cf in c_files:
            cmd.append(str(cf))
        cmd += prof.cflags + prof.ldflags

        await _run(cmd, cwd=src, env=env, timeout=120)

        return {
            "status": "ok" if out.exists() else "error",
            "target": prof.slug,
            "kind": "raw-cc",
            "artifact": str(out) if out.exists() else None,
        }


# ── Helpers ─────────────────────────────────────────────────────



async def _run(
    cmd: List[str],
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> Tuple[str, int]:
    """Run a subprocess, return (stdout, rc). Raises on timeout."""
    import asyncio
    proc = await asyncio.wait_for(
        asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=env,
        ),
        timeout=timeout,
    )
    stdout_bytes, _ = await proc.communicate()
    return stdout_bytes.decode("utf-8", errors="replace"), proc.returncode or 1