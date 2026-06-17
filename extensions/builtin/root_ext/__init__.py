"""
extensions/builtin/root_ext/__init__.py — ROOT权限扩展 v1.0.1

检测条件: su命令可用 → 自动启用
平台: Android/Linux (需要root)
"""
import os, sys, subprocess

EXTENSION_NAME = "minxg-root"
EXTENSION_DESCRIPTION = "ROOT工具: su执行/mount/iptables/sysctl/SELinux/内核模块"
EXTENSION_VERSION = "1.0.1"
EXTENSION_PRIORITY = 95
EXTENSION_SOURCE = "builtin"


def _check_root() -> bool:
    
    for p in ["/system/bin/su", "/system/xbin/su", "/sbin/su",
              "/su/bin/su", "/magisk/.core/bin/su"]:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return True
    
    try:
        r = subprocess.run(["su", "-c", "echo ok"], capture_output=True,
                          text=True, timeout=5)
        if r.returncode == 0 and "ok" in r.stdout:
            return True
    except:
        pass
    return False


ROOT_AVAILABLE = _check_root()


def handle_command(args) -> int:
    if not ROOT_AVAILABLE:
        print("此设备未ROOT。ROOT工具无法使用。")
        return 1

    subcmd = getattr(args, 'root_subcommand', None)
    if subcmd is None:
        print("ROOT工具子命令:")
        print("  check        检查ROOT状态")
        print("  shell CMD    以root执行命令")
        print("  info         系统信息 (root视角)")
        print("  magisk       Magisk信息")
        return 0

    if subcmd == "check":
        print("ROOT权限: ✅ 已解锁")
        try:
            r = subprocess.run(["su", "-c", "id"], capture_output=True, text=True, timeout=5)
            print(f"用户: {r.stdout.strip()}")
        except:
            pass
    elif subcmd == "shell":
        cmd = getattr(args, 'shell_command', 'id')
        r = subprocess.run(["su", "-c", cmd], capture_output=True, text=True, timeout=30)
        print(r.stdout.strip())
    elif subcmd == "info":
        for title, cmd in [("内核", "uname -a"), ("分区", "df -h | head -5"),
                           ("挂载", "mount | head -5"), ("内存", "free -h")]:
            r = subprocess.run(["su", "-c", cmd], capture_output=True, text=True, timeout=10)
            print(f"\n=== {title} ===")
            print(r.stdout[:500])
    elif subcmd == "magisk":
        try:
            r = subprocess.run(["su", "-c", "magisk -c"], capture_output=True, text=True, timeout=5)
            print(r.stdout.strip() or "Magisk未检测到")
        except:
            print("Magisk未安装")
    return 0


def register_cli(subparsers):
    p = subparsers.add_parser("root", help="ROOT工具 (需要root)")
    sp = p.add_subparsers(dest="root_subcommand")
    sp.add_parser("check", help="检查ROOT")
    sp_shell = sp.add_parser("shell", help="root Shell")
    sp_shell.add_argument("shell_command", help="命令")
    sp.add_parser("info", help="系统信息")
    sp.add_parser("magisk", help="Magisk")


def register_hooks(registry):
    if not ROOT_AVAILABLE:
        return

    from extensions import register_hook

    register_hook("tool_interceptor", lambda tools: tools + [
        {"name": "root_check", "description": "检查设备ROOT状态", "category": "root"},
        {"name": "root_su", "description": "以root执行任意命令", "category": "root"},
        {"name": "root_mount", "description": "挂载/卸载文件系统", "category": "root"},
        {"name": "root_iptables", "description": "管理iptables防火墙", "category": "root"},
        {"name": "root_sysctl", "description": "读写内核参数", "category": "root"},
        {"name": "root_lsmod", "description": "内核模块列表", "category": "root"},
        {"name": "root_selinux_status", "description": "SELinux状态管理", "category": "root"},
        {"name": "root_setprop", "description": "设置系统属性", "category": "root"},
        {"name": "root_chroot", "description": "chroot到指定目录", "category": "root"},
    ], priority=85)