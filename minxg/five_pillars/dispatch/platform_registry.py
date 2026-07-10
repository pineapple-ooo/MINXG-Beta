"""
minxg/platform_registry.py — Platform-aware tool registry v2.0.0

Every tool in MINXG declares which platforms it supports. This module:
  1. Auto-detects the current platform
  2. Filters tools available on this platform
  3. Provides platform capability queries for AI

Platforms supported (v0.16.0): android, windows
All other platforms (linux, macos, ios, web) have been retired.
Each platform has different tool availability based on system capabilities.
"""
from __future__ import annotations
import platform as _platform
import sys
import os
from typing import Dict, List, Optional, Set


# Supported platforms — android + windows only as of v0.16.0
SUPPORTED_PLATFORMS = {"android", "windows"}


def detect_platform() -> str:
    """Detect the current platform. Returns one of: android, windows, unknown."""
    system = _platform.system()

    if system == "Android":
        return "android"
    elif system == "Windows":
        return "windows"

    # Any other OS is not officially supported from v0.16.0
    return "unknown"


def is_android() -> bool:
    """Check if running on Android (Termux or similar)."""
    return _platform.system() == "Android"

def is_windows() -> bool:
    """Check if running on Windows."""
    return _platform.system() == "Windows"


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
    
    "file_read":       {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_write":      {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_search":     {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_hash":       {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_walk":       {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_watch":      {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_chmod":      {"platforms": ["android"], "category": "file", "requires_root": False},
    "file_chown":      {"platforms": ["android"], "category": "file", "requires_root": True},
    "file_stat":       {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_diff":       {"platforms": ["android", "windows"], "category": "file", "requires_root": False},
    "file_merge":      {"platforms": ["android", "windows"], "category": "file", "requires_root": False},

    
    "process_list":    {"platforms": ["android"], "category": "process", "requires_root": False},
    "process_kill":    {"platforms": ["android"], "category": "process", "requires_root": False},
    "process_info":    {"platforms": ["android"], "category": "process", "requires_root": False},
    "process_cgroup":  {"platforms": ["android"], "category": "process", "requires_root": True},
    "process_spawn":   {"platforms": ["android", "windows"], "category": "process", "requires_root": False},

    
    "net_ping":        {"platforms": ["android", "windows"], "category": "network", "requires_root": False},
    "net_dns":         {"platforms": ["android", "windows"], "category": "network", "requires_root": False},
    "net_http_get":    {"platforms": ["android", "windows"], "category": "network", "requires_root": False},
    "net_http_post":   {"platforms": ["android", "windows"], "category": "network", "requires_root": False},
    "net_ssl_check":   {"platforms": ["android", "windows"], "category": "network", "requires_root": False},
    "net_websocket":   {"platforms": ["android", "windows"], "category": "network", "requires_root": False},
    "net_download":    {"platforms": ["android", "windows"], "category": "network", "requires_root": False},
    "net_speed_test":  {"platforms": ["android", "windows"], "category": "network", "requires_root": False},

    
    "sys_cpu":         {"platforms": ["android", "windows"], "category": "system", "requires_root": False},
    "sys_memory":      {"platforms": ["android", "windows"], "category": "system", "requires_root": False},
    "sys_disk":        {"platforms": ["android", "windows"], "category": "system", "requires_root": False},
    "sys_sensors":     {"platforms": ["android"], "category": "system", "requires_root": False},
    "sys_battery":     {"platforms": ["android"], "category": "system", "requires_root": False},
    "sys_uptime":      {"platforms": ["android", "windows"], "category": "system", "requires_root": False},
    "sys_env":         {"platforms": ["android", "windows"], "category": "system", "requires_root": False},
    "sys_dmesg":       {"platforms": ["android"], "category": "system", "requires_root": False},

    
    "encode_base64":   {"platforms": ["android", "windows"], "category": "encoding", "requires_root": False},
    "encode_url":      {"platforms": ["android", "windows"], "category": "encoding", "requires_root": False},
    "encode_html":     {"platforms": ["android", "windows"], "category": "encoding", "requires_root": False},
    "hash_md5":        {"platforms": ["android", "windows"], "category": "crypto", "requires_root": False},
    "hash_sha256":     {"platforms": ["android", "windows"], "category": "crypto", "requires_root": False},
    "encrypt_aes":     {"platforms": ["android", "windows"], "category": "crypto", "requires_root": False},
    "compress_gzip":   {"platforms": ["android", "windows"], "category": "compress", "requires_root": False},
    "compress_zstd":   {"platforms": ["android", "windows"], "category": "compress", "requires_root": False},
    "compress_lz4":    {"platforms": ["android", "windows"], "category": "compress", "requires_root": False},

    
    "archive_list":    {"platforms": ["android", "windows"], "category": "archive", "requires_root": False},
    "archive_extract": {"platforms": ["android", "windows"], "category": "archive", "requires_root": False},
    "archive_create":  {"platforms": ["android", "windows"], "category": "archive", "requires_root": False},
    "archive_detect":  {"platforms": ["android", "windows"], "category": "archive", "requires_root": False},
    "zip_list":        {"platforms": ["android", "windows"], "category": "archive", "requires_root": False},
    "zip_extract":     {"platforms": ["android", "windows"], "category": "archive", "requires_root": False},
    "zip_create":      {"platforms": ["android", "windows"], "category": "archive", "requires_root": False},

    
    "image_info":      {"platforms": ["android", "windows"], "category": "media", "requires_root": False},
    "image_resize":    {"platforms": ["android", "windows"], "category": "media", "requires_root": False},
    "image_convert":   {"platforms": ["android", "windows"], "category": "media", "requires_root": False},
    "audio_info":      {"platforms": ["android", "windows"], "category": "media", "requires_root": False},
    "audio_convert":   {"platforms": ["android", "windows"], "category": "media", "requires_root": False},
    "video_info":      {"platforms": ["android", "windows"], "category": "media", "requires_root": False},
    "video_thumb":     {"platforms": ["android", "windows"], "category": "media", "requires_root": False},

    
    "git_status":      {"platforms": ["android", "windows"], "category": "dev", "requires_root": False},
    "git_log":         {"platforms": ["android", "windows"], "category": "dev", "requires_root": False},
    "git_diff":        {"platforms": ["android", "windows"], "category": "dev", "requires_root": False},

    
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

    
    "db_sqlite_query": {"platforms": ["android", "windows"], "category": "db", "requires_root": False},
    "db_sqlite_schema":{"platforms": ["android", "windows"], "category": "db", "requires_root": False},
}


TOOL_CATEGORIES = [
    "file", "process", "network", "system", "encoding", "crypto", "compress",
    "archive", "media", "dev", "adb", "root", "db", "math",
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
        "is_windows": is_windows(),
        "root_available": is_root_available(),
        "adb_available": is_adb_available(),
        "total_tools_defined": len(TOOL_PLATFORM_MATRIX),
        "tools_available": get_tool_count(plat),
        "categories_available": len(set(
            v["category"] for v in get_available_tools(plat).values()
        )),
        "supported_platforms": sorted(SUPPORTED_PLATFORMS),
    }
