"""minxg — Five-Pillar Operator Architecture v1.1.0

A modular worker platform organized along five mathematical/functional
operator dimensions. Each pillar is independently importable so that
editing one module never forces a project-wide rebuild.
"""
from .base import BaseWorker, ToolDef, WorkerRegistry
from . import _config as _cfg_mod

load_config = _cfg_mod.load_config
get = _cfg_mod.get
CONFIG = _cfg_mod.CONFIG

from .five_pillars.io.fs_io import FsIoWorker
from .five_pillars.io.fs_copy import FsCopyWorker
from .five_pillars.io.fs_search import FsSearchWorker
from .five_pillars.io.network import NetworkWorker
from .five_pillars.io.network_adv import NetworkAdvWorker
from .five_pillars.io.media_tools import MediaToolsWorker
from .five_pillars.io.media_adv import MediaAdvWorker
from .five_pillars.io.db_tools import DbToolsWorker
from .five_pillars.io.web_tools import WebToolsWorker
from .five_pillars.io.web_search import search as web_search  
from .five_pillars.io.archive_tools import ArchiveWorker
from .five_pillars.io.cloud_tools import CloudToolsWorker

from .five_pillars.dispatch.system import SystemWorker
from .five_pillars.dispatch.sh_query import ShQueryWorker
from .five_pillars.dispatch.sh_exec import ShExecWorker
from .five_pillars.dispatch.process_tools import ProcessToolsWorker
from .five_pillars.dispatch.limits_lock import LimitsLockWorker
from .five_pillars.dispatch.limits_break import LimitsBreakWorker
from .five_pillars.dispatch.platform_tools import PlatformWorker
from .five_pillars.dispatch.platform_registry import (
    CURRENT_PLATFORM, detect_platform, get_available_tools,
    get_tools_by_category, get_system_capabilities,
)
from .five_pillars.dispatch.adb_tools import AdbWorker
from .five_pillars.dispatch.root_tools import RootWorker
from .five_pillars.dispatch.dev_tools import DevToolsWorker
from .five_pillars.dispatch.security_tools import SecurityToolsWorker
from .five_pillars.dispatch.go_client import GoGatewayClient as GoBridge
from .five_pillars.dispatch.notify_tools import NotifyWorker

from .five_pillars.transform.state_session import StateSessionWorker
from .five_pillars.transform.state_machine import StateMachineWorker
from .five_pillars.transform.persistence import PersistenceWorker
from .five_pillars.transform.rules import RulesWorker
from .five_pillars.transform.events import EventsWorker
from .five_pillars.transform.hotreload import HotReloadWorker
from .five_pillars.transform.ai_tools import AiToolsWorker

from .five_pillars.scalar.text_tools import TextToolsWorker
from .five_pillars.scalar.datetime_tools import DateTimeToolsWorker
from .five_pillars.scalar.math_tools import MathToolsWorker
from .five_pillars.scalar.string_tools import StringWorker
from .five_pillars.scalar.version_tools import VersionWorker
from .five_pillars.scalar.color_tools import ColorWorker
from .five_pillars.scalar.markdown_tools import MarkdownWorker

from .five_pillars.aggregate.encoding_tools import EncodingToolsWorker
from .five_pillars.aggregate.crypto_tools import CryptoToolsWorker
from .five_pillars.aggregate.data_tools import DataToolsWorker
from .five_pillars.aggregate.template_tools import TemplateToolsWorker
from .five_pillars.aggregate.i18n_tools import I18nWorker
from .five_pillars.aggregate.ml_tools import MlToolsWorker
from .five_pillars.aggregate.benchmark_tools import BenchmarkToolsWorker

from .operators import OperatorWorker

__all__ = [
    "BaseWorker", "ToolDef", "WorkerRegistry",
    "FsIoWorker", "FsCopyWorker", "FsSearchWorker",
    "NetworkWorker", "NetworkAdvWorker",
    "MediaToolsWorker", "MediaAdvWorker",
    "DbToolsWorker", "WebToolsWorker", "web_search",
    "ArchiveWorker", "CloudToolsWorker",
    "SystemWorker", "ShQueryWorker", "ShExecWorker", "ProcessToolsWorker",
    "LimitsLockWorker", "LimitsBreakWorker", "PlatformWorker",
    "AdbWorker", "RootWorker", "DevToolsWorker",
    "SecurityToolsWorker", "GoBridge", "NotifyWorker",
    "StateSessionWorker", "StateMachineWorker",
    "PersistenceWorker", "RulesWorker", "EventsWorker", "HotReloadWorker",
    "AiToolsWorker",
    "TextToolsWorker", "DateTimeToolsWorker", "MathToolsWorker",
    "StringWorker", "VersionWorker", "ColorWorker", "MarkdownWorker",
    "EncodingToolsWorker", "CryptoToolsWorker", "DataToolsWorker",
    "TemplateToolsWorker", "I18nWorker",
    "MlToolsWorker", "BenchmarkToolsWorker",
    "OperatorWorker",
    "CURRENT_PLATFORM", "detect_platform", "get_available_tools",
    "get_tools_by_category", "get_system_capabilities",
]

VERSION = "0.12.5"

try:
    from . import cap as _cap
except ImportError:
    _cap = None

try:
    from . import ga
    from .ga import operators_ga as _ga_ops
    GA_OPERATORS = _ga_ops.GA_OPERATOR_COUNT
except ImportError:
    GA_OPERATORS = 0

try:
    from . import cat
    from .cat import operators_cat as _cat_ops
    CAT_OPERATORS = _cat_ops.CAT_OPERATOR_COUNT
except ImportError:
    CAT_OPERATORS = 0

try:
    from . import infogeo
    from .infogeo import operators_ig as _ig_ops
    IG_OPERATORS = _ig_ops.IG_OPERATOR_COUNT
except ImportError:
    IG_OPERATORS = 0

try:
    from . import topo
    from .topo import operators_topo as _topo_ops
    TOPO_OPERATORS = _topo_ops.TOPO_OPERATOR_COUNT
except ImportError:
    TOPO_OPERATORS = 0

try:
    from . import chaos
    from .chaos import operators_chaos as _chaos_ops
    CHAOS_OPERATORS = _chaos_ops.CHAOS_OPERATOR_COUNT
except ImportError:
    CHAOS_OPERATORS = 0

try:
    from . import fiber
    from .fiber import operators_fiber as _fiber_ops
    FIBER_OPERATORS = _fiber_ops.FIBER_OPERATOR_COUNT
except ImportError:
    FIBER_OPERATORS = 0

TOTAL_MATHEMATICAL_OPERATORS = (
    GA_OPERATORS + CAT_OPERATORS + IG_OPERATORS
    + TOPO_OPERATORS + CHAOS_OPERATORS + FIBER_OPERATORS
)

POLYGLOT_LANGUAGES = ("python", "rust", "javascript", "go", "shell")
LOSSLESS_MAGIC = b"MINSKE"
LOSSLESS_VERSION = 1
TWIN_ERROR = "UnsupportedTwinOp"
SELF_EVOLUTION_PHASES = ("born", "mutable", "live", "quiet", "gone")
LENS_LANGUAGES = ("en", "zh", "zh-TW", "ja", "ko")
DRIVER_PHASES = ("ready", "stepping", "paused", "halted", "faulted")
DRIVER_DEFAULT_MAX_SUBDIVISIONS = 6
