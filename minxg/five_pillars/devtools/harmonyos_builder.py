"""minxg/five_pillars/devtools/harmonyos_builder.py — HarmonyOS NEXT build + deploy.

Wraps the MIT-licensed `harmonyos-deploy` npm package as MINXG @tool methods.
Builds HAR/HSP/HAP, pushes to device, launches — all from CLI.

Also integrates HMNextAuto (MIT) for UI automation testing on HarmonyOS NEXT.

Install requirements:
    npm install -g harmonyos-deploy
    pip install hmnextauto
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool


class HarmonyOSWorker(BaseWorker):
    """HarmonyOS NEXT build/deploy/test bridge.

    Two MIT tools:
    - harmonyos-deploy (npm) — build HAR/HSP/HAP, deploy to device
    - hmnextauto (pip) — UI automation testing framework
    """

    worker_id = "harmonyos_tools"
    version = "0.18.2"
    tier = "code"
    _category = "code"

    @tool(
        description="Build a HarmonyOS NEXT app (HAR/HSP/HAP) and deploy to device.",
        category="build",
    )
    async def harmonyos_build_deploy(
        self,
        project_path: str,
        build_mode: str = "debug",
        device: str = "",
        launch: bool = True,
        clean: bool = False,
    ) -> Dict[str, Any]:
        """Build and deploy HarmonyOS app.

        Args:
            project_path: path to HarmonyOS project root.
            build_mode: debug, release, or test.
            device: target device serial (auto-detect if empty).
            launch: auto-launch after install.
            clean: clean before build.
        """
        proj = Path(project_path)
        if not proj.exists():
            return {"status": "error", "error": f"Project path not found: {project_path}"}

        # Check npm tool availability
        try:
            subprocess.run(["npx", "harmonyos-deploy", "--version"],
                           capture_output=True, timeout=10)
        except Exception:
            return {
                "status": "disabled",
                "hint": "Install harmonyos-deploy: npm install -g harmonyos-deploy",
            }

        argv = ["npx", "harmonyos-deploy", "--all"]
        if build_mode == "release":
            argv.append("--release")
        elif build_mode == "test":
            argv.append("--test")
        else:
            argv.append("--debug")
        if device:
            argv.extend(["--device", device])
        if launch:
            argv.append("--launch")
        if clean:
            argv.append("--clean")

        loop = asyncio.get_running_loop()
        try:
            proc = await loop.run_in_executor(
                None,
                lambda: subprocess.run(argv, cwd=str(proj),
                                       capture_output=True, text=True, timeout=300),
            )
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "exit_code": proc.returncode,
                "stdout": proc.stdout[-2000:],
                "stderr": proc.stderr[-1000:],
                "command": " ".join(argv),
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Build timed out (300s)"}

    @tool(
        description="List connected HarmonyOS devices via HDC.",
        category="build",
    )
    async def harmonyos_list_devices(self) -> Dict[str, Any]:
        """List all connected HarmonyOS NEXT devices."""
        try:
            result = subprocess.run(
                ["hdc", "list", "targets"],
                capture_output=True, text=True, timeout=10,
            )
            devices = [d.strip() for d in result.stdout.strip().split("\n") if d.strip()]
            return {
                "status": "ok",
                "device_count": len(devices),
                "devices": devices,
                "message": f"Found {len(devices)} device(s)." if devices else "No devices connected.",
            }
        except FileNotFoundError:
            return {
                "status": "disabled",
                "hint": "HDC not found. Install HarmonyOS Command Line Tools from developer.huawei.com.",
            }

    @tool(
        description="Run a UI automation script on a HarmonyOS NEXT device via hmnextauto.",
        category="build",
    )
    async def harmonyos_ui_test(
        self,
        script: str,
        device_serial: str = "",
    ) -> Dict[str, Any]:
        """Execute a UI automation script on HarmonyOS device.

        Uses hmnextauto (MIT) — a uiautomator2-compatible framework
        for HarmonyOS NEXT.
        """
        try:
            from hmnextauto.driver import Driver
        except ImportError:
            return {
                "status": "disabled",
                "hint": "Install hmnextauto: pip install hmnextauto",
            }

        loop = asyncio.get_running_loop()
        try:
            def _run():
                d = Driver(device_serial) if device_serial else Driver()
                info = d.device_info
                # Execute the user's script in a restricted namespace
                ns = {"d": d, "Driver": Driver, "device_info": info}
                exec(script, ns)
                return {"device_info": str(info), "script_executed": True}

            result = await loop.run_in_executor(None, _run)
            return {"status": "ok", **result}
        except Exception as e:
            return {"status": "error", "error": str(e)}


__all__ = ["HarmonyOSWorker"]