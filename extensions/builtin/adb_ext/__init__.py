"""
extensions/builtin/adb_ext/__init__.py — ADB命令扩展 v1.0.1

检测条件: adb命令可用 → 自动启用
平台: Android/Linux/Windows/macOS (有adb即可)
""""
import os, sys, subprocess

EXTENSION_NAME = "minxg-adb"
EXTENSION_DESCRIPTION = "ADB工具: 管理Android设备 (devices/shell/install/logcat/screenshot)"
EXTENSION_VERSION = "1.0.1"
EXTENSION_PRIORITY = 90
EXTENSION_SOURCE = "builtin"


def _check_adb() -> bool:
    try:
        r = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except:
        return False



ADB_AVAILABLE = _check_adb()


def handle_command(args) -> int:
    if not ADB_AVAILABLE:
        print("ADB工具未激活。请安装 Android SDK Platform Tools。")
        print("  Linux: apt install android-tools-adb")
        print("  macOS: brew install android-platform-tools")
        print("  Termux: pkg install android-tools")
        return 1

    subcmd = getattr(args, 'adb_subcommand', None)
    if subcmd is None:
        print("ADB工具子命令:")
        print("  devices      列出已连接设备")
        print("  shell CMD    在设备上执行shell命令")
        print("  install APK  安装APK")
        print("  screenshot   截图")
        print("  logcat       查看设备日志")
        return 0

    cmd = getattr(args, 'shell_command', None)
    if subcmd == "devices":
        r = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True)
        print(r.stdout.strip())
    elif subcmd == "shell" and cmd:
        r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, timeout=30)
        print(r.stdout.strip())
    elif subcmd == "install":
        apk = getattr(args, 'apk_path', '')
        if apk:
            r = subprocess.run(["adb", "install", apk], capture_output=True, text=True, timeout=60)
            print(r.stdout.strip())
        else:
            print("用法: minxg ext adb install <apk_path>")
    elif subcmd == "screenshot":
        r = subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=10)
        out = os.path.expanduser("~/adb_screenshot.png")
        with open(out, "wb") as f:
            f.write(r.stdout)
        print(f"截图已保存: {out} ({len(r.stdout)} bytes)")
    elif subcmd == "logcat":
        r = subprocess.run(["adb", "logcat", "-d", "-t", "50"], capture_output=True, text=True, timeout=10)
        print(r.stdout[-5000:])
    return 0


def register_cli(subparsers):
    p = subparsers.add_parser("adb", help="ADB工具 (Android设备管理)")
    sp = p.add_subparsers(dest="adb_subcommand")
    sp.add_parser("devices", help="列出设备")
    sp_shell = sp.add_parser("shell", help="执行shell")
    sp_shell.add_argument("shell_command", help="命令")
    sp_install = sp.add_parser("install", help="安装APK")
    sp_install.add_argument("apk_path", help="APK路径")
    sp.add_parser("screenshot", help="截图")
    sp.add_parser("logcat", help="设备日志")


def register_hooks(registry):
    if not ADB_AVAILABLE:
        return

    from extensions import register_hook

    register_hook("tool_interceptor", lambda tools: tools + [
        {"name": "adb_devices", "description": "列出已连接的Android设备", "category": "adb"},
        {"name": "adb_shell", "description": "在Android设备上执行shell命令", "category": "adb"},
        {"name": "adb_install", "description": "在设备上安装APK应用", "category": "adb"},
        {"name": "adb_uninstall", "description": "卸载设备上的应用", "category": "adb"},
        {"name": "adb_push", "description": "推送文件到设备", "category": "adb"},
        {"name": "adb_pull", "description": "从设备拉取文件", "category": "adb"},
        {"name": "adb_logcat", "description": "查看设备系统日志", "category": "adb"},
        {"name": "adb_screenshot", "description": "截取设备屏幕", "category": "adb"},
        {"name": "adb_reboot", "description": "重启设备", "category": "adb"},
    ], priority=80)