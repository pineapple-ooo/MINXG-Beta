"""
Toolset definitions for nexusai-multilang.

Toolsets are logical groupings of tools. Each tool belongs to exactly one toolset.
Toolsets can be enabled/disabled as a group.
"""

from typing import Dict, List, Optional, Set

# Core toolsets
TOOLSETS: Dict[str, dict] = {
    "file": {
        "description": "File operations - read, write, search, patch files",
        "tools": ["read_file", "write_file", "patch", "search_files", "ls_dir", "file_info"],
    },
    "terminal": {
        "description": "Terminal/shell execution",
        "tools": ["execute_command", "execute_code"],
    },
    "web": {
        "description": "Web fetching and HTTP operations",
        "tools": ["fetch_url", "http_status", "ping_tool"],
    },
    "system": {
        "description": "System information and management",
        "tools": ["system_info", "process_list", "disk_usage", "network_info"],
    },
    "delegate": {
        "description": "Subagent delegation for parallel tasks",
        "tools": ["delegate_task"],
    },
    "skills": {
        "description": "Skill management and usage",
        "tools": ["skill_view", "skill_manage", "skills_list"],
    },
    "cron": {
        "description": "Scheduled job management",
        "tools": ["cronjob"],
    },
}

# Toolset aliases
TOOLSET_ALIASES: Dict[str, str] = {
    "shell": "terminal",
    "exec": "terminal",
    "files": "file",
    "docs": "file",
    "network": "web",
    "net": "web",
    "sys": "system",
}


def resolve_toolset(name: str) -> Optional[str]:
    """Resolve a toolset name or alias to its canonical name."""
    if name in TOOLSETS:
        return name
    return TOOLSET_ALIASES.get(name)


def validate_toolset(name: str) -> bool:
    """Check if a toolset name or alias is valid."""
    return resolve_toolset(name) is not None


def get_all_toolsets() -> List[str]:
    """Return all known toolset names."""
    return list(TOOLSETS.keys())


def get_toolset_tools(toolset: str) -> List[str]:
    """Get all tools in a toolset by name or alias."""
    canonical = resolve_toolset(toolset)
    if canonical and canonical in TOOLSETS:
        return TOOLSETS[canonical]["tools"]
    return []


def get_toolsets_for_tool(tool_name: str) -> List[str]:
    """Find all toolsets that contain a given tool."""
    result = []
    for ts_name, ts_data in TOOLSETS.items():
        if tool_name in ts_data["tools"]:
            result.append(ts_name)
    return result


# Default enabled toolsets when none specified
DEFAULT_TOOLSETS = ["file", "terminal", "web", "system"]


__all__ = [
    "TOOLSETS",
    "TOOLSET_ALIASES", 
    "resolve_toolset",
    "validate_toolset",
    "get_all_toolsets",
    "get_toolset_tools",
    "get_toolsets_for_tool",
    "DEFAULT_TOOLSETS",
]
