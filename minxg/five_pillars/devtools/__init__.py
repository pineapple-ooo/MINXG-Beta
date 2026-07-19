"""minxg/five_pillars/devtools/ -- build / package / ship.

Houses AndroidForge (Buildozer / python-for-android wrapper),
the quad-OS QuadForge dispatcher, the DevShell facade,
and the academic-only ReverseStudioWorker.  Heavy: every tool
here shells out to external compilers / inspectors.

v0.18.2 additions:
- UnifiedChannelWorker -- 19 chat platform bridge (MIT unified-channel)
- HarmonyOSWorker -- HarmonyOS NEXT build/deploy/test (MIT harmonyos-deploy + hmnextauto)
- BinaryToolbeltWorker -- BAP disasm + omill lifter/deobfuscator + native Rust entropy scan

Naming note (v0.18.x)
---------------------
``AndroidForgeWorker`` is the canonical name introduced in v0.18.x.
``ApkForgeWorker`` is preserved as a backward-compat alias for any
code that imported the v0.17.x name.

``QuadForgeWorker`` is the canonical name introduced in v0.18.1.
``DevForgeWorker`` is preserved as a backward-compat alias for any
code that imported the v0.18.0 name.
"""

from .android_forge import AndroidForgeWorker, ApkForgeWorker
from .dev_forge import QuadForgeWorker, DevForgeWorker
from .dev_shell import DevShellWorker
from .reverse_studio import ReverseStudioWorker, LEGAL_NOTICE
from .templates import (
    PLATFORMS, PLATFORM_DISPLAY, FRAMEWORKS,
    render_entrypoint, build_command,
)
from .unified_channel import UnifiedChannelWorker, _CHANNEL_LIST
from .harmonyos_builder import HarmonyOSWorker
from .binary_toolbelt import BinaryToolbeltWorker
from .quad_forge import QuadForgeWorker, TargetProfile, _PROFILES
from .math_pillar_dispatcher import MathPillarDispatcher

__all__ = [
    "AndroidForgeWorker",
    "ApkForgeWorker",          # back-compat alias for v0.17.x
    "QuadForgeWorker",
    "DevForgeWorker",          # back-compat alias for v0.18.0
    "DevShellWorker",
    "ReverseStudioWorker",
    "LEGAL_NOTICE",
    "UnifiedChannelWorker",    # v0.18.2: 19-channel messaging
    "HarmonyOSWorker",          # v0.18.2: HarmonyOS NEXT build/deploy
    "BinaryToolbeltWorker",     # v0.18.2: BAP + omill + Rust entropy
    "MathPillarDispatcher",     # v0.18.3: 7-pillar math facade for AI
    "PLATFORMS", "PLATFORM_DISPLAY", "FRAMEWORKS",
    "render_entrypoint", "build_command",
]