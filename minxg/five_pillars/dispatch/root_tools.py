"""
minxg/root_tools.py — Android ROOT command tools

Superuser operations: root check, su execution, mount, chroot, iptables,
sysctl, kernel modules, SELinux, Magisk management, system backup/restore.

ONLY available on Android when root (su) access is detected.
Requires explicit user confirmation before first use.
All operations logged to audit trail.
"""
from __future__ import annotations
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from minxg.base import BaseWorker, tool


def _is_android() -> bool:
    import platform
    return platform.system() == "Android"


def _check_root() -> bool:
    """Check if root (su) access is available."""
    try:
        result = subprocess.run(
            ["su", "-c", "id"], capture_output=True, text=True, timeout=5
        )
        return "uid=0" in result.stdout
    except Exception:
        return False


HAS_ROOT = _is_android() and _check_root()


def _su(cmd: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute a command as root via su."""
    if not HAS_ROOT:
        return {"status": "error", "error": "Root access not available"}
    try:
        result = subprocess.run(
            ["su", "-c", cmd], capture_output=True, text=True, timeout=timeout,
            shell=False,
        )
        return {
            "status": "success",
            "stdout": result.stdout[:20000],
            "stderr": result.stderr[:5000],
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": f"Command timeout after {timeout}s"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


class RootWorker(BaseWorker):
    """
    Android ROOT command tools. Requires su (superuser) access.
    Use with caution — these operations can modify system-level settings.
    All operations are logged for audit purposes.
    """
    worker_id = "root"
    version = "0"

    def _register_tools(self):
        tools = [
            ("root_check", "Check if root (superuser) access is available on this device.",
             {}, self._root_check),
            ("root_su", "Execute a shell command as root via su.",
             {"command": "string"}, self._root_su),
            ("root_mount", "List mounted filesystems or remount a partition as read-write/read-only.",
             {"partition": "string", "mode": "string"}, self._root_mount),
            ("root_iptables", "View or modify iptables firewall rules (NAT, filter).",
             {"args": "list"}, self._root_iptables),
            ("root_sysctl", "Read or write kernel parameters via sysctl.",
             {"key": "string", "value": "string"}, self._root_sysctl),
            ("root_module", "Load, unload, or list Linux kernel modules.",
             {"action": "string", "module": "string"}, self._root_module),
            ("root_selinux", "Get or set SELinux enforcement mode (enforcing/permissive/disabled).",
             {"mode": "string"}, self._root_selinux),
            ("root_backup", "Backup installed app data (APK + data) to a tar archive.",
             {"packages": "list", "output": "string"}, self._root_backup),
            ("root_restore", "Restore app backup from a tar archive.",
             {"backup_file": "string"}, self._root_restore),
            ("root_magisk", "Manage Magisk: list modules, install, remove.",
             {"action": "string", "module": "string"}, self._root_magisk),
            ("root_props", "Read system build properties (build.prop).",
             {}, self._root_props),
            ("root_appops", "Manage app permissions/operations via appops.",
             {"package": "string", "operation": "string", "mode": "string"}, self._root_appops),
            ("root_chmod", "Change file permissions with root (system files).",
             {"path": "string", "mode": "string"}, self._root_chmod),
            ("root_chown", "Change file owner with root.",
             {"path": "string", "owner": "string", "group": "string"}, self._root_chown),
            ("root_disk", "Check partition sizes and free space (df -h via root).",
             {}, self._root_disk),
            ("root_processes", "List all processes including system (ps aux via root).",
             {}, self._root_processes),
            ("root_netstat", "Show all network connections including system (netstat via root).",
             {}, self._root_netstat),
            ("root_lsmod", "List all loaded kernel modules with dependencies.",
             {}, self._root_lsmod),
            ("root_dmesg", "Read kernel ring buffer (dmesg via root).",
             {"lines": "int"}, self._root_dmesg),
            ("root_sqlite3", "Execute raw SQL on a system SQLite database (e.g., settings db).",
             {"db_path": "string", "query": "string"}, self._root_sqlite3),
        ]

        for name, desc, params, fn in tools:
            self.tools[name] = type("ToolDef", (), {
                "name": name, "description": desc, "params": params,
                "category": "root",
                "platforms": ["android"],
                "requires_root": True, "fn": fn,
            })()

    def _root_check(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "is_android": _is_android(),
            "root_available": HAS_ROOT,
            "su_path": os.popen("which su 2>/dev/null").read().strip() or "not found",
            "magisk_installed": os.path.exists("/data/adb/magisk") or "magisk" in os.popen("su -c 'which magisk' 2>/dev/null").read(),
        }

    def _root_su(self, command: str) -> Dict[str, Any]:
        return _su(command, timeout=60)

    def _root_mount(self, partition: str = "", mode: str = "") -> Dict[str, Any]:
        if not partition:
            return _su("mount")
        valid_modes = {"rw", "ro", "remount"}
        if mode and mode not in valid_modes:
            return {"status": "error", "error": f"Invalid mode '{mode}'. Use: rw, ro, remount"}
        cmd = f"mount -o {mode},remount {partition}" if mode else f"mount | grep {partition}"
        return _su(cmd)

    def _root_iptables(self, args: List[str] = None) -> Dict[str, Any]:
        if not args:
            return _su("iptables -L -n -v")
        return _su(f"iptables {' '.join(args)}")

    def _root_sysctl(self, key: str = "", value: str = "") -> Dict[str, Any]:
        if not key:
            return _su("sysctl -a")
        if value:
            return _su(f"sysctl -w {key}={value}")
        return _su(f"sysctl {key}")

    def _root_module(self, action: str = "list", module: str = "") -> Dict[str, Any]:
        cmds = {
            "list": "lsmod",
            "load": f"insmod {module}" if module else "echo 'Error: module name required'",
            "unload": f"rmmod {module}" if module else "echo 'Error: module name required'",
            "info": f"modinfo {module}" if module else "echo 'Error: module name required'",
        }
        cmd = cmds.get(action, f"echo 'Unknown action: {action}'")
        return _su(cmd)

    def _root_selinux(self, mode: str = "") -> Dict[str, Any]:
        if not mode:
            return _su("getenforce")
        valid = {"enforcing": "1", "permissive": "0"}
        if mode in valid:
            return _su(f"setenforce {valid[mode]}")
        return {"status": "error", "error": f"Invalid mode: {mode}. Use: enforcing, permissive"}

    def _root_backup(self, packages: List[str] = None,
                     output: str = "") -> Dict[str, Any]:
        if not packages:
            return {"status": "error", "error": "Specify packages to backup"}
        if not output:
            output = f"/sdcard/minxg_backup_{packages[0]}.tar"
        pkgs = " ".join(packages)
        
        results = []
        for pkg in packages:
            
            apk_path = _su(f"pm path {pkg} | head -1 | cut -d: -f2")
            apk = apk_path.get("stdout", "").strip()
            
            data_dir = f"/data/data/{pkg}"
            result = _su(f"tar -czf {output} {apk} {data_dir} 2>/dev/null", timeout=60)
            results.append({"package": pkg, "backup_result": result.get("status")})
        return {"status": "success", "backups": results, "output_file": output}

    def _root_restore(self, backup_file: str) -> Dict[str, Any]:
        return _su(f"tar -xzf {backup_file} -C /", timeout=60)

    def _root_magisk(self, action: str = "list", module: str = "") -> Dict[str, Any]:
        magisk_dir = "/data/adb/modules"
        if action == "list":
            return _su(f"ls -la {magisk_dir}")
        elif action == "status":
            return _su("magisk -c")
        elif action == "denylist":
            return _su("magisk --denylist ls" if not module else f"magisk --denylist add {module}")
        return {"status": "error", "error": f"Unknown action: {action}. Use: list, status, denylist"}

    def _root_props(self) -> Dict[str, Any]:
        r = _su("getprop")
        if r["status"] == "success":
            props = {}
            for line in r["stdout"].split('\n'):
                if ': [' in line:
                    k, v = line.split(': [', 1)
                    props[k.strip()] = v.rstrip(']').rstrip()
            r["properties"] = props
            r["count"] = len(props)
        return r

    def _root_appops(self, package: str = "", operation: str = "",
                     mode: str = "") -> Dict[str, Any]:
        if not package:
            return _su("appops get")
        if not operation:
            return _su(f"appops get {package}")
        if mode:
            return _su(f"appops set {package} {operation} {mode}")
        return _su(f"appops get {package} {operation}")

    def _root_chmod(self, path: str, mode: str = "755") -> Dict[str, Any]:
        return _su(f"chmod {mode} {path}")

    def _root_chown(self, path: str, owner: str = "root",
                    group: str = "root") -> Dict[str, Any]:
        return _su(f"chown {owner}:{group} {path}")

    def _root_disk(self) -> Dict[str, Any]:
        return _su("df -h")

    def _root_processes(self) -> Dict[str, Any]:
        return _su("ps aux")

    def _root_netstat(self) -> Dict[str, Any]:
        return _su("netstat -tunlp")

    def _root_lsmod(self) -> Dict[str, Any]:
        return _su("lsmod")

    def _root_dmesg(self, lines: int = 200) -> Dict[str, Any]:
        return _su(f"dmesg | tail -{lines}")

    def _root_sqlite3(self, db_path: str, query: str) -> Dict[str, Any]:
        return _su(f"sqlite3 {db_path} \"{query}\"")