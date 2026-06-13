"""nexusai-multilang - Multi-language AI task orchestration framework.""""

from multiling.model_tools import (
    get_tool_definitions,
    handle_function_call,
    get_all_tool_names,
    get_toolset_for_tool,
    get_available_toolsets,
    check_toolset_requirements,
    refresh_tool_maps,
)
from multiling.orchestrator import NexusOrchestrator
from multiling.ipc_server import TCPIPCServer
from multiling.toolsets import (
    TOOLSETS, TOOLSET_ALIASES,
    DEFAULT_TOOLSETS,
    resolve_toolset, validate_toolset,
    get_all_toolsets, get_toolset_tools,
)

__version__ = "1.0.0"

__all__ = [
    "get_tool_definitions",
    "handle_function_call",
    "get_all_tool_names",
    "get_toolset_for_tool",
    "get_available_toolsets",
    "check_toolset_requirements",
    "refresh_tool_maps",
    "NexusOrchestrator",
    "TCPIPCServer",
    "DEFAULT_TOOLSETS",
]
