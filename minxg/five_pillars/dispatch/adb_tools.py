"""
minxg/adb_tools.py — Android Debug Bridge (ADB) tools v1.0.0

Complete ADB command suite for Android devices: device management, shell,
app install/uninstall, file push/pull, logcat, screencap, input, reboot.

Only available on Android platform. Falls back gracefully on other platforms.
"""
from __future__ import annotations
import os
import subprocess
import base64
import tempfile
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool


def _is_android() -> bool:
    import platform
    return platform.system() == "Android"


def _adb(cmd: List[str], timeout: int = 30, check: bool = False) -> Dict[str, Any]:
    """Execute an ADB command and return structured result."""
    try:
        result = subprocess.run(
            ["adb"] + cmd, capture_output=True, text=True, timeout=timeout
        )
        return {
            "status": "success",
            "stdout": result.stdout[:20000],
            "stderr": result.stderr[:5000],
            "exit_code": result.returncode,
        }
    except FileNotFoundError:
        return {"status": "error", "error": "ADB not found. Install Android SDK platform-tools."}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"ADB command timeout after {timeout}s"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


class AdbWorker(BaseWorker):
    """
    Android Debug Bridge tools. Full device management via ADB.
    Auto-disabled on non-Android platforms.
    """
    worker_id = "adb"
    version = "0.16.0"

    def _register_tools(self):
        tools = [
            ("adb_devices", "List connected Android devices and their states.",
             {}, self._adb_devices),
            ("adb_shell", "Execute a shell command on an Android device.",
             {"command": "string", "device": "string"}, self._adb_shell),
            ("adb_install", "Install an APK on a device.",
             {"apk_path": "string", "device": "string", "grant_permissions": "bool"}, self._adb_install),
            ("adb_uninstall", "Uninstall a package from a device.",
             {"package": "string", "device": "string"}, self._adb_uninstall),
            ("adb_push", "Push a file from host to device.",
             {"src": "string", "dst": "string", "device": "string"}, self._adb_push),
            ("adb_pull", "Pull a file from device to host.",
             {"src": "string", "dst": "string", "device": "string"}, self._adb_pull),
            ("adb_logcat", "Stream or dump logcat from device.",
             {"filter": "string", "lines": "int", "device": "string"}, self._adb_logcat),
            ("adb_screencap", "Capture screenshot from device. Returns base64-encoded PNG.",
             {"device": "string"}, self._adb_screencap),
            ("adb_screenrecord", "Record screen video from device.",
             {"duration_sec": "int", "device": "string"}, self._adb_screenrecord),
            ("adb_input_text", "Input text on device via ADB.",
             {"text": "string", "device": "string"}, self._adb_input_text),
            ("adb_input_keyevent", "Send a key event to device (e.g., KEYCODE_HOME=3, KEYCODE_BACK=4).",
             {"keycode": "int", "device": "string"}, self._adb_input_keyevent),
            ("adb_input_tap", "Tap at coordinates on device screen.",
             {"x": "int", "y": "int", "device": "string"}, self._adb_input_tap),
            ("adb_input_swipe", "Swipe on device screen from (x1,y1) to (x2,y2).",
             {"x1": "int", "y1": "int", "x2": "int", "y2": "int", "duration_ms": "int", "device": "string"},
             self._adb_input_swipe),
            ("adb_pm_list", "List installed packages on device.",
             {"filter": "string", "device": "string"}, self._adb_pm_list),
            ("adb_pm_info", "Get detailed info about an installed package.",
             {"package": "string", "device": "string"}, self._adb_pm_info),
            ("adb_am_start", "Start an activity/app on device.",
             {"package": "string", "activity": "string", "device": "string"}, self._adb_am_start),
            ("adb_am_force_stop", "Force-stop an app on device.",
             {"package": "string", "device": "string"}, self._adb_am_force_stop),
            ("adb_reboot", "Reboot the device.",
             {"mode": "string", "device": "string"}, self._adb_reboot),
            ("adb_tcpip", "Restart ADB in TCP/IP mode on a specific port.",
             {"port": "int"}, self._adb_tcpip),
            ("adb_connect", "Connect to a device over TCP/IP.",
             {"host": "string", "port": "int"}, self._adb_connect),
            ("adb_disconnect", "Disconnect from a TCP/IP device.",
             {"host": "string"}, self._adb_disconnect),
            ("adb_bugreport", "Generate a full bug report from device.",
             {"device": "string"}, self._adb_bugreport),
            ("adb_dumpsys", "Run dumpsys to get system service info.",
             {"service": "string", "device": "string"}, self._adb_dumpsys),
            ("adb_getprop", "Get system properties from device.",
             {"key": "string", "device": "string"}, self._adb_getprop),
            ("adb_setprop", "Set a system property on device (requires root).",
             {"key": "string", "value": "string", "device": "string"}, self._adb_setprop),
            ("adb_wm_size", "Get or set screen size/density on device.",
             {"device": "string"}, self._adb_wm_size),
            ("adb_battery", "Get battery status from device.",
             {"device": "string"}, self._adb_battery),
        ]

        for name, desc, params, fn in tools:
            self.tools[name] = type("ToolDef", (), {
                "name": name, "description": desc, "params": params,
                "category": "adb",
                "platforms": ["android"],
                "requires_root": False, "fn": fn,
            })()

    @staticmethod
    def _device_arg(device: str = "") -> List[str]:
        return ["-s", device] if device else []

    

    def _adb_devices(self) -> Dict[str, Any]:
        r = _adb(["devices", "-l"])
        if r["status"] != "success":
            return r
        devices = []
        for line in r["stdout"].split('\n')[1:]:
            if '\t' in line:
                parts = line.split()
                devices.append({"serial": parts[0], "state": parts[1] if len(parts) > 1 else "?"})
        r["devices"] = devices
        r["device_count"] = len(devices)
        return r

    def _adb_shell(self, command: str, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", command] if not device else ["-s", device, "shell", command],
                    timeout=60)

    def _adb_install(self, apk_path: str, device: str = "",
                     grant_permissions: bool = False) -> Dict[str, Any]:
        cmd = ["install"] + (["-g"] if grant_permissions else []) + [apk_path]
        return _adb(cmd, timeout=120)

    def _adb_uninstall(self, package: str, device: str = "") -> Dict[str, Any]:
        return _adb(["uninstall", package], timeout=30)

    def _adb_push(self, src: str, dst: str, device: str = "") -> Dict[str, Any]:
        return _adb(["push", src, dst], timeout=60)

    def _adb_pull(self, src: str, dst: str, device: str = "") -> Dict[str, Any]:
        return _adb(["pull", src, dst], timeout=120)

    def _adb_logcat(self, filter: str = "", lines: int = 200,
                    device: str = "") -> Dict[str, Any]:
        cmd = ["logcat", "-d", "-t", str(lines)]
        if filter:
            cmd.extend(["-s", filter])
        return _adb(cmd, timeout=10)

    def _adb_screencap(self, device: str = "") -> Dict[str, Any]:
        tmp = "/sdcard/minxg_screencap.png"
        r = _adb(["shell", "screencap", "-p", tmp], timeout=10)
        if r["status"] != "success":
            return r
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            local_path = f.name
        _adb(["pull", tmp, local_path])
        _adb(["shell", "rm", tmp])
        with open(local_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('ascii')
        os.unlink(local_path)
        return {"status": "success", "screenshot_base64": b64, "format": "png"}

    def _adb_screenrecord(self, duration_sec: int = 10,
                          device: str = "") -> Dict[str, Any]:
        tmp = "/sdcard/minxg_record.mp4"
        _adb(["shell", "screenrecord", "--time-limit", str(duration_sec), tmp],
             timeout=duration_sec + 10)
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            local_path = f.name
        _adb(["pull", tmp, local_path])
        _adb(["shell", "rm", tmp])
        return {"status": "success", "video_path": local_path,
                "duration_sec": duration_sec}

    def _adb_input_text(self, text: str, device: str = "") -> Dict[str, Any]:
        escaped = text.replace(" ", "%s").replace('"', '\\"')
        return _adb(["shell", "input", "text", escaped], timeout=5)

    def _adb_input_keyevent(self, keycode: int, device: str = "") -> Dict[str, Any]:
        KEYCODES = {3: "HOME", 4: "BACK", 24: "VOLUME_UP", 25: "VOLUME_DOWN",
                     26: "POWER", 82: "MENU", 84: "SEARCH", 187: "APP_SWITCH"}
        return _adb(["shell", "input", "keyevent", str(keycode)], timeout=5)

    def _adb_input_tap(self, x: int, y: int, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", "input", "tap", str(x), str(y)], timeout=5)

    def _adb_input_swipe(self, x1: int, y1: int, x2: int, y2: int,
                         duration_ms: int = 300, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2),
                     str(duration_ms)], timeout=5)

    def _adb_pm_list(self, filter: str = "", device: str = "") -> Dict[str, Any]:
        cmd = ["shell", "pm", "list", "packages"]
        if filter:
            cmd.append(filter)
        r = _adb(cmd, timeout=10)
        if r["status"] == "success":
            pkgs = [l.replace("package:", "").strip()
                    for l in r["stdout"].split('\n') if l.startswith("package:")]
            r["packages"] = pkgs
            r["count"] = len(pkgs)
        return r

    def _adb_pm_info(self, package: str, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", "dumpsys", "package", package], timeout=15)

    def _adb_am_start(self, package: str, activity: str = "",
                      device: str = "") -> Dict[str, Any]:
        target = f"{package}/{activity}" if activity else package
        return _adb(["shell", "am", "start", "-n", target], timeout=10)

    def _adb_am_force_stop(self, package: str, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", "am", "force-stop", package], timeout=10)

    def _adb_reboot(self, mode: str = "system", device: str = "") -> Dict[str, Any]:
        valid_modes = {"system", "recovery", "bootloader"}
        mmode = mode if mode in valid_modes else "system"
        return _adb([mmode] if mmode == "reboot" else ["reboot", mmode], timeout=120)

    def _adb_tcpip(self, port: int = 5555) -> Dict[str, Any]:
        return _adb(["tcpip", str(port)], timeout=10)

    def _adb_connect(self, host: str, port: int = 5555) -> Dict[str, Any]:
        return _adb(["connect", f"{host}:{port}"], timeout=10)

    def _adb_disconnect(self, host: str = "") -> Dict[str, Any]:
        return _adb(["disconnect", host] if host else ["disconnect"], timeout=10)

    def _adb_bugreport(self, device: str = "") -> Dict[str, Any]:
        return _adb(["bugreport"], timeout=60)

    def _adb_dumpsys(self, service: str, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", "dumpsys", service], timeout=15)

    def _adb_getprop(self, key: str = "", device: str = "") -> Dict[str, Any]:
        r = _adb(["shell", "getprop"] + ([key] if key else []), timeout=5)
        if r["status"] == "success" and not key:
            props = {}
            for line in r["stdout"].split('\n'):
                if ': [' in line:
                    k, v = line.split(': [', 1)
                    props[k.strip()] = v.rstrip(']').rstrip()
            r["system_properties"] = props
            r["count"] = len(props)
        return r

    def _adb_setprop(self, key: str, value: str, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", "setprop", key, value], timeout=5)

    def _adb_wm_size(self, device: str = "") -> Dict[str, Any]:
        return _adb(["shell", "wm", "size"], timeout=5)

    def _adb_battery(self, device: str = "") -> Dict[str, Any]:
        r = _adb(["shell", "dumpsys", "battery"], timeout=5)
        if r["status"] == "success":
            info = {}
            for line in r["stdout"].split('\n'):
                if ':' in line and ':' not in line.split(':', 1)[0].strip():
                    continue
                if ':' in line:
                    k, v = line.split(':', 1)
                    info[k.strip()] = v.strip()
            r["battery"] = info
        return r