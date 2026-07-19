"""tests/test_extension_tool_discovery.py — proves the real bug fix:
enabled extensions' `register_hooks(registry)` is now actually called
during chat-agent tool discovery. Before this fix, `discover_extensions()`
imported every extension module (needed for `minxg ext list` metadata),
but nothing in the chat startup path ever invoked `register_hooks()` on
them — extensions only ever reached `minxg ext <verb>` CLI dispatch,
never a live conversation, no matter what they registered.

This test creates a real, throwaway extension under extensions/user/
(the loader hardcodes that path — see extensions/loader.py
_get_extensions_dirs()), enables it via the real state-file mechanism,
and confirms the tool it registers actually shows up in
tools.registry.registry after multiling.model_tools.ensure_tools_discovered().
"""
from __future__ import annotations

import sys
import json as jsonlib
from pathlib import Path

import pytest


EXT_NAME = "minxg-test-discovery-ext"

EXT_SOURCE = '''
EXTENSION_NAME = "{name}"
EXTENSION_DESCRIPTION = "throwaway test extension for tool discovery"
EXTENSION_VERSION = "0.0.1"


def handle_command(args) -> int:
    return 0


def register_hooks(registry) -> None:
    def _handler(args):
        return "{{\\"ok\\": true}}"

    registry.register(
        name="__test_discovery_tool__",
        toolset="testing",
        schema={{"type": "object", "properties": {{}}}},
        handler=_handler,
        check_fn=lambda: True,
        emoji="",
    )
'''.format(name=EXT_NAME)


def _extensions_user_dir() -> Path:
    from extensions.loader import _user_state_dir
    return _user_state_dir()


@pytest.fixture
def temp_extension():
    user_dir = _extensions_user_dir()  # extensions/user/
    ext_file = user_dir / f"{EXT_NAME}.py"
    state_file = user_dir / f"{EXT_NAME}.state"
    ext_file.write_text(EXT_SOURCE, encoding="utf-8")
    state_file.write_text(jsonlib.dumps({"enabled": True}), encoding="utf-8")

    for k in list(sys.modules):
        # NOT "extensions" itself: popping the top-level package here used
        # to cause a module-identity split for any *other* test that had
        # already done `import extensions.builtin.<x>` normally (see
        # tests/test_multiagent_ext.py) -- re-importing "extensions" fresh
        # doesn't reattach already-cached submodules to the new object.
        if k.startswith("extensions._dynamic"):
            sys.modules.pop(k, None)
    import extensions.loader as loader_mod
    loader_mod._cached = None

    import multiling.model_tools as model_tools_mod
    model_tools_mod._discovered = False

    from tools.registry import registry
    registry._tools.pop("__test_discovery_tool__", None)

    yield

    ext_file.unlink(missing_ok=True)
    state_file.unlink(missing_ok=True)
    loader_mod._cached = None
    model_tools_mod._discovered = False
    registry._tools.pop("__test_discovery_tool__", None)


class TestExtensionToolDiscovery:
    def test_enabled_extension_tool_becomes_registered(self, temp_extension):
        from multiling.model_tools import ensure_tools_discovered
        from tools.registry import registry

        assert "__test_discovery_tool__" not in registry.get_all_tool_names()
        ensure_tools_discovered()
        assert "__test_discovery_tool__" in registry.get_all_tool_names()

    def test_disabled_extension_tool_is_not_registered(self, temp_extension):
        # flip it back off via the same state-file mechanism the CLI uses
        state_file = _extensions_user_dir() / f"{EXT_NAME}.state"
        state_file.write_text(jsonlib.dumps({"enabled": False}), encoding="utf-8")
        import extensions.loader as loader_mod
        loader_mod._cached = None

        from multiling.model_tools import ensure_tools_discovered
        from tools.registry import registry

        ensure_tools_discovered()
        assert "__test_discovery_tool__" not in registry.get_all_tool_names()

    def test_registered_tool_is_actually_callable(self, temp_extension):
        from multiling.model_tools import ensure_tools_discovered
        from tools.registry import registry

        ensure_tools_discovered()
        result = registry.dispatch("__test_discovery_tool__", {})
        assert jsonlib.loads(result) == {"ok": True}
