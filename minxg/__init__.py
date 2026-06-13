"""
minxg/__init__.py — Worker registry v1.0.0
"""
from .base import BaseWorker, ToolDef, WorkerRegistry
from . import _config as _cfg_mod
load_config = _cfg_mod.load_config
get = _cfg_mod.get
CONFIG = _cfg_mod.CONFIG

# Core I/O
from .fs_io import FsIoWorker
from .fs_copy import FsCopyWorker
from .fs_search import FsSearchWorker

# System & network
from .system import SystemWorker
from .network import NetworkWorker
from .sh_query import ShQueryWorker
from .sh_exec import ShExecWorker

# State & session
from .state_session import StateSessionWorker
from .state_machine import StateMachineWorker
from .limits_lock import LimitsLockWorker
from .limits_break import LimitsBreakWorker
from .persistence import PersistenceWorker
from .rules import RulesWorker
from .events import EventsWorker
from .hotreload import HotReloadWorker

# Text & encoding
from .text_tools import TextToolsWorker
from .encoding_tools import EncodingToolsWorker
from .math_tools import MathToolsWorker
from .datetime_tools import DateTimeToolsWorker

# Core tools
from .ai_tools import AiToolsWorker
from .media_tools import MediaToolsWorker
from .data_tools import DataToolsWorker
from .crypto_tools import CryptoToolsWorker
from .db_tools import DbToolsWorker
from .web_tools import WebToolsWorker
from .template_tools import TemplateToolsWorker
from .benchmark_tools import BenchmarkToolsWorker
from .cloud_tools import CloudToolsWorker
from .security_tools import SecurityToolsWorker
from .ml_tools import MlToolsWorker
from .process_tools import ProcessToolsWorker

# Platform & UI
from .platform_tools import PlatformWorker
from .notify_tools import NotifyWorker
from .i18n_tools import I18nWorker
from .string_tools import StringWorker
from .version_tools import VersionWorker
from .color_tools import ColorWorker
from .markdown_tools import MarkdownWorker

# v1.0.0: New worker modules
from .archive_tools import ArchiveWorker
from .network_adv import NetworkAdvWorker
from .dev_tools import DevToolsWorker
from .media_adv import MediaAdvWorker
from .adb_tools import AdbWorker
from .root_tools import RootWorker
from .operators import OperatorWorker

# Platform registry
from .platform_registry import (
    CURRENT_PLATFORM, detect_platform, get_available_tools,
    get_tools_by_category, get_system_capabilities,
)

__all__ = [
    "BaseWorker", "ToolDef", "WorkerRegistry",

    # Core I/O
    "FsIoWorker", "FsCopyWorker", "FsSearchWorker",

    # System & network
    "SystemWorker", "NetworkWorker", "ShQueryWorker", "ShExecWorker",

    # State & session
    "StateSessionWorker", "StateMachineWorker",
    "LimitsLockWorker", "LimitsBreakWorker",
    "PersistenceWorker", "RulesWorker", "EventsWorker", "HotReloadWorker",

    # Text & encoding
    "TextToolsWorker", "EncodingToolsWorker", "MathToolsWorker", "DateTimeToolsWorker",

    # Core tools
    "AiToolsWorker", "MediaToolsWorker", "DataToolsWorker",
    "CryptoToolsWorker", "DbToolsWorker", "WebToolsWorker",
    "TemplateToolsWorker", "BenchmarkToolsWorker", "CloudToolsWorker",
    "SecurityToolsWorker", "MlToolsWorker", "ProcessToolsWorker",

    # Platform & UI
    "PlatformWorker", "NotifyWorker", "I18nWorker",
    "StringWorker", "VersionWorker", "ColorWorker", "MarkdownWorker",

    # v1.0.0 new
    "ArchiveWorker", "NetworkAdvWorker", "DevToolsWorker",
    "MediaAdvWorker", "AdbWorker", "RootWorker", "OperatorWorker",

    # Platform registry
    "CURRENT_PLATFORM", "detect_platform", "get_available_tools",
    "get_tools_by_category", "get_system_capabilities",
]

VERSION = "1.0.0"

# ═══════════════════════════════════════════════════════════════════════════════
# Mathematical Pillar Sub-packages (auto-registered on import)
# ═══════════════════════════════════════════════════════════════════════════════
# These sub-packages register their operators with OPERATOR_REGISTRY on import.
# They define the five mathematical pillars of MINXG operator architecture:
#   - GA:      Geometric Algebra (Clifford Algebra)
#   - CAT:     Category Theory (morphisms, functors, monads)
#   - IG:      Information Geometry (Fisher metric, α-connections)
#   - TOPO:    Algebraic Topology (persistent homology, simplicial complexes)
#   - CHAOS:   Dynamical Systems & Fractals (Lyapunov, IFS, attractors)

# Import order matters: each sub-package registers on import
try:
    from . import ga
    from .ga import operators_ga as _ga_ops
    GA_OPERATORS = _ga_ops.GA_OPERATOR_COUNT
except ImportError as e:
    GA_OPERATORS = 0
    import warnings
    warnings.warn(f"GA operators not loaded: {e}")

try:
    from . import cat
    from .cat import operators_cat as _cat_ops
    CAT_OPERATORS = _cat_ops.CAT_OPERATOR_COUNT
except ImportError as e:
    CAT_OPERATORS = 0
    import warnings
    warnings.warn(f"CAT operators not loaded: {e}")

try:
    from . import infogeo
    from .infogeo import operators_ig as _ig_ops
    IG_OPERATORS = _ig_ops.IG_OPERATOR_COUNT
except ImportError as e:
    IG_OPERATORS = 0
    import warnings
    warnings.warn(f"IG operators not loaded: {e}")

try:
    from . import topo
    from .topo import operators_topo as _topo_ops
    TOPO_OPERATORS = _topo_ops.TOPO_OPERATOR_COUNT
except ImportError as e:
    TOPO_OPERATORS = 0
    import warnings
    warnings.warn(f"TOPO operators not loaded: {e}")

try:
    from . import chaos
    from .chaos import operators_chaos as _chaos_ops
    CHAOS_OPERATORS = _chaos_ops.CHAOS_OPERATOR_COUNT
except ImportError as e:
    CHAOS_OPERATORS = 0
    import warnings
    warnings.warn(f"CHAOS operators not loaded: {e}")

try:
    from . import fiber
    from .fiber import operators_fiber as _fiber_ops
    FIBER_OPERATORS = _fiber_ops.FIBER_OPERATOR_COUNT
except ImportError as e:
    FIBER_OPERATORS = 0
    import warnings
    warnings.warn(f"FIBER operators not loaded: {e}")

TOTAL_MATHEMATICAL_OPERATORS = (
    GA_OPERATORS + CAT_OPERATORS + IG_OPERATORS + TOPO_OPERATORS + CHAOS_OPERATORS + FIBER_OPERATORS
)
