"""
minxg/platform_registry.py — Platform-aware tool registry

Every tool in MINXG declares which platforms it supports. This module:
  1. Auto-detects the current platform
  2. Filters tools available on this platform
  3. Provides platform capability queries for AI

Platforms supported: linux, macos, windows, android, ios, web
Each platform has different tool availability based on system capabilities.
"""
from __future__ import annotations
import platform as _platform
import sys
import os
from typing import Dict, List, Optional, Set






def detect_platform() -> str:
    """Detect the current platform. Returns one of: linux, macos, windows, android, ios, web."""
    system = _platform.system()

    if system == "Android":
        return "android"
    elif system == "Linux":
        return "linux"
    elif system == "Darwin":
        return "macos"
    elif system == "Windows":
        return "windows"
    elif system == "iOS":
        return "ios"

    
    if hasattr(sys, "platform") and "emscripten" in sys.platform:
        return "web"

    return system.lower()


def is_android() -> bool:
    """Check if running on Android (Termux or similar)."""
    return _platform.system() == "Android"


def is_root_available() -> bool:
    """Check if root access is available (Android only)."""
    if not is_android():
        return False
    try:
        result = os.popen("su -c 'id' 2>/dev/null").read()
        return "uid=0" in result
    except Exception:
        return False


def is_adb_available() -> bool:
    """Check if ADB is available on this device."""
    try:
        result = os.popen("which adb 2>/dev/null").read().strip()
        return bool(result)
    except Exception:
        return False


CURRENT_PLATFORM = detect_platform()








TOOL_PLATFORM_MATRIX: Dict[str, Dict] = {
    
    "file_read":       {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "file", "requires_root": False},
    "file_write":      {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "file", "requires_root": False},
    "file_search":     {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "file", "requires_root": False},
    "file_hash":       {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "file", "requires_root": False},
    "file_walk":       {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "file", "requires_root": False},
    "file_watch":      {"platforms": ["linux", "macos", "windows"], "category": "file", "requires_root": False},
    "file_chmod":      {"platforms": ["linux", "macos", "android"], "category": "file", "requires_root": False},
    "file_chown":      {"platforms": ["linux", "macos", "android"], "category": "file", "requires_root": True},
    "file_stat":       {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "file", "requires_root": False},
    "file_diff":       {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "file", "requires_root": False},
    "file_merge":      {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "file", "requires_root": False},

    
    "process_list":    {"platforms": ["linux", "macos", "android"], "category": "process", "requires_root": False},
    "process_kill":    {"platforms": ["linux", "macos", "android"], "category": "process", "requires_root": False},
    "process_info":    {"platforms": ["linux", "macos", "android"], "category": "process", "requires_root": False},
    "process_nice":    {"platforms": ["linux", "macos"], "category": "process", "requires_root": False},
    "process_cgroup":  {"platforms": ["linux", "android"], "category": "process", "requires_root": True},
    "process_spawn":   {"platforms": ["linux", "macos", "windows", "android"], "category": "process", "requires_root": False},

    
    "net_ping":        {"platforms": ["linux", "macos", "windows", "android"], "category": "network", "requires_root": False},
    "net_dns":         {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "network", "requires_root": False},
    "net_http_get":    {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "network", "requires_root": False},
    "net_http_post":   {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "network", "requires_root": False},
    "net_traceroute":  {"platforms": ["linux", "macos", "android"], "category": "network", "requires_root": True},
    "net_ssl_check":   {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "network", "requires_root": False},
    "net_port_scan":   {"platforms": ["linux", "macos", "android"], "category": "network", "requires_root": False},
    "net_websocket":   {"platforms": ["linux", "macos", "windows", "android", "web"], "category": "network", "requires_root": False},
    "net_download":    {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "network", "requires_root": False},
    "net_speed_test":  {"platforms": ["linux", "macos", "windows", "android"], "category": "network", "requires_root": False},

    
    "sys_cpu":         {"platforms": ["linux", "macos", "windows", "android"], "category": "system", "requires_root": False},
    "sys_memory":      {"platforms": ["linux", "macos", "windows", "android"], "category": "system", "requires_root": False},
    "sys_disk":        {"platforms": ["linux", "macos", "windows", "android"], "category": "system", "requires_root": False},
    "sys_sensors":     {"platforms": ["linux", "android"], "category": "system", "requires_root": False},
    "sys_battery":     {"platforms": ["linux", "android", "ios"], "category": "system", "requires_root": False},
    "sys_uptime":      {"platforms": ["linux", "macos", "windows", "android"], "category": "system", "requires_root": False},
    "sys_env":         {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "system", "requires_root": False},
    "sys_dmesg":       {"platforms": ["linux", "android"], "category": "system", "requires_root": False},
    "sys_reboot":      {"platforms": ["linux", "android"], "category": "system", "requires_root": True},

    
    "encode_base64":   {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "encoding", "requires_root": False},
    "encode_url":      {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "encoding", "requires_root": False},
    "encode_html":     {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "encoding", "requires_root": False},
    "hash_md5":        {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "crypto", "requires_root": False},
    "hash_sha256":     {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "crypto", "requires_root": False},
    "encrypt_aes":     {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "crypto", "requires_root": False},
    "compress_gzip":   {"platforms": ["linux", "macos", "windows", "android", "ios", "web"], "category": "compress", "requires_root": False},
    "compress_zstd":   {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "compress", "requires_root": False},
    "compress_lz4":    {"platforms": ["linux", "macos", "windows", "android"], "category": "compress", "requires_root": False},

    
    "archive_list":    {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "archive", "requires_root": False},
    "archive_extract": {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "archive", "requires_root": False},
    "archive_create":  {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "archive", "requires_root": False},
    "archive_detect":  {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "archive", "requires_root": False},
    "zip_list":        {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "archive", "requires_root": False},
    "zip_extract":     {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "archive", "requires_root": False},
    "zip_create":      {"platforms": ["linux", "macos", "windows", "android", "ios"], "category": "archive", "requires_root": False},
    "tar_list":        {"platforms": ["linux", "macos", "android"], "category": "archive", "requires_root": False},
    "tar_extract":     {"platforms": ["linux", "macos", "android"], "category": "archive", "requires_root": False},

    
    "image_info":      {"platforms": ["linux", "macos", "windows", "android"], "category": "media", "requires_root": False},
    "image_resize":    {"platforms": ["linux", "macos", "windows", "android"], "category": "media", "requires_root": False},
    "image_convert":   {"platforms": ["linux", "macos", "windows", "android"], "category": "media", "requires_root": False},
    "audio_info":      {"platforms": ["linux", "macos", "windows", "android"], "category": "media", "requires_root": False},
    "audio_convert":   {"platforms": ["linux", "macos", "windows", "android"], "category": "media", "requires_root": False},
    "video_info":      {"platforms": ["linux", "macos", "windows", "android"], "category": "media", "requires_root": False},
    "video_thumb":     {"platforms": ["linux", "macos", "windows", "android"], "category": "media", "requires_root": False},

    
    "git_status":      {"platforms": ["linux", "macos", "windows", "android"], "category": "dev", "requires_root": False},
    "git_log":         {"platforms": ["linux", "macos", "windows", "android"], "category": "dev", "requires_root": False},
    "git_diff":        {"platforms": ["linux", "macos", "windows", "android"], "category": "dev", "requires_root": False},
    "docker_ps":       {"platforms": ["linux", "macos", "windows"], "category": "dev", "requires_root": False},

    
    "adb_devices":     {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_shell":       {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_install":     {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_uninstall":   {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_push":        {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_pull":        {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_logcat":      {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_screencap":   {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_input":       {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_reboot":      {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_tcpip":       {"platforms": ["android"], "category": "adb", "requires_root": False},
    "adb_pm_list":     {"platforms": ["android"], "category": "adb", "requires_root": False},

    
    "root_check":      {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_su":         {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_mount":      {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_chroot":     {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_iptables":   {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_sysctl":     {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_selinux":    {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_module":     {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_backup":     {"platforms": ["android"], "category": "root", "requires_root": True},
    "root_restore":    {"platforms": ["android"], "category": "root", "requires_root": True},

    
    "cloud_aws_list":  {"platforms": ["linux", "macos", "windows"], "category": "cloud", "requires_root": False},
    "cloud_gcp_list":  {"platforms": ["linux", "macos", "windows"], "category": "cloud", "requires_root": False},
    "cloud_do_list":   {"platforms": ["linux", "macos", "windows"], "category": "cloud", "requires_root": False},
    "cloud_cf_list":   {"platforms": ["linux", "macos", "windows"], "category": "cloud", "requires_root": False},

    
    "db_sqlite_query": {"platforms": ["linux", "macos", "windows", "android"], "category": "db", "requires_root": False},
    "db_sqlite_schema":{"platforms": ["linux", "macos", "windows", "android"], "category": "db", "requires_root": False},
}





TOOL_CATEGORIES = [
    "file", "process", "network", "system", "encoding", "crypto", "compress",
    "archive", "media", "dev", "adb", "root", "cloud", "db", "math",
    "text", "datetime", "ml", "security", "benchmark",
]






def get_available_tools(platform: Optional[str] = None) -> Dict[str, Dict]:
    """
    Return all tools available on the given platform. If platform is None,
    auto-detects the current platform.
    """
    plat = platform or CURRENT_PLATFORM
    available = {}
    for name, meta in TOOL_PLATFORM_MATRIX.items():
        if plat in meta.get("platforms", []):
            available[name] = meta
    return available


def get_tools_by_category(platform: Optional[str] = None,
                          category: Optional[str] = None) -> Dict[str, Dict]:
    """Filter tools by platform and/or category."""
    tools = get_available_tools(platform)
    if category:
        tools = {k: v for k, v in tools.items() if v.get("category") == category}
    return tools


def is_tool_available(tool_name: str, platform: Optional[str] = None) -> bool:
    """Check if a specific tool is available on this platform."""
    plat = platform or CURRENT_PLATFORM
    meta = TOOL_PLATFORM_MATRIX.get(tool_name)
    if not meta:
        return False
    return plat in meta.get("platforms", [])


def get_tool_count(platform: Optional[str] = None) -> int:
    """Number of tools available on this platform."""
    return len(get_available_tools(platform))


def get_system_capabilities() -> Dict:
    """Return full system capability report for AI context."""
    plat = CURRENT_PLATFORM
    return {
        "platform": plat,
        "platform_name": _platform.platform(),
        "python_version": sys.version,
        "is_android": is_android(),
        "root_available": is_root_available(),
        "adb_available": is_adb_available(),
        "total_tools_defined": len(TOOL_PLATFORM_MATRIX),
        "tools_available": get_tool_count(plat),
        "categories_available": len(set(
            v["category"] for v in get_available_tools(plat).values()
        )),
    }