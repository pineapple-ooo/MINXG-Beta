"""
extensions - extension discovery, registry, and lifecycle.

Every runtime extension is a first-class MINXG citizen: it advertises
an EXTENSION_NAME, declares its dependencies, and exposes a
handle_command(args) entry point that returns a POSIX exit code.
Built-ins like ``minxg-adb`` ship with the package but stay disabled
until the user opts in via ``minxg ext add <slug>``.

The runner is intentionally narrow: it never auto-enables based on
detected tools, so installing this project on a fresh box does not
suddenly grant remote powers on every other box the user touches.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


__all__ = [
    "ExtensionRegistry",
    "HOOK_NAMES",
    "register_hook",
    "get_default_registry",
    "get_extensions",
    "get_extension",
    "list_extensions",
    "reload_extensions",
    "cleanup_temp_dirs",
    "set_extension_enabled",
    "register_cli_extensions",
    "dispatch_extension",
    "register_hooks_from_extensions",
]

HOOK_NAMES = [
    "pre_chat_hook",
    "post_chat_hook",
    "tool_interceptor",
    "gateway_middleware",
    "cli_commands",
]


class ExtensionRegistry:
    """Holds ordered hook callbacks keyed by name (see HOOK_NAMES)."""

    def __init__(self):
        self._hooks: Dict[str, List[tuple]] = {name: [] for name in HOOK_NAMES}

    def register(self, hook_name: str, callback: Callable, priority: int = 50):
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append((priority, callback))
        self._hooks[hook_name].sort(key=lambda x: x[0])

    def run_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        results = []
        for _, cb in self._hooks.get(hook_name, []):
            try:
                results.append(cb(*args, **kwargs))
            except Exception as e:
                LOGGER.warning("Hook %s (%s) raised %s",
                               hook_name, getattr(cb, "__name__", cb), e)
        return results

    def run_hook_chain(self, hook_name: str, initial_value: Any,
                       *args, **kwargs) -> Any:
        """Map-and-reduce through a chain. Used by pre_chat_hook etc."""
        value = initial_value
        for _, cb in self._hooks.get(hook_name, []):
            try:
                value = cb(value, *args, **kwargs)
            except Exception as e:
                LOGGER.warning("Hook %s (%s) raised %s",
                               hook_name, getattr(cb, "__name__", cb), e)
        return value

    def list_hooks(self) -> Dict[str, int]:
        return {name: len(cbs) for name, cbs in self._hooks.items()}

    def clear(self):
        for name in self._hooks:
            self._hooks[name].clear()


def register_hook(hook_name: str, callback: Callable, priority: int = 50,
                  registry: ExtensionRegistry = None):
    if registry is None:
        registry = get_default_registry()
    registry.register(hook_name, callback, priority)


_default_registry: Optional[ExtensionRegistry] = None


def get_default_registry() -> ExtensionRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ExtensionRegistry()
    return _default_registry


import logging

LOGGER = logging.getLogger("extensions")


from extensions.loader import (
    ExtensionModule,
    get_extension,
    get_extensions,
    list_extensions,
    reload_extensions,
    cleanup_temp_dirs,
    set_extension_enabled,
)


def register_cli_extensions(subparsers) -> Dict[str, ExtensionModule]:
    """Discover CLI commands from every loaded extension.

    Each extension's ``register_cli(subparsers)`` is invoked, then
    command dispatch is returned in the ext_map keyed by extension name.
    """
    ext_map: Dict[str, ExtensionModule] = {}
    try:
        for ext in get_extensions():
            if ext.enabled and ext.name not in ext_map:
                ext_map[ext.name] = ext
                ext.register_cli(subparsers)
    except Exception as e:
        LOGGER.warning("register_cli_extensions failed: %s", e)
    return ext_map


def dispatch_extension(ext_map: Dict, command: str, args) -> int:
    """Run a registered extension's handle_command.

    Errors are surfaced to the user (traceback in dev, exit code in
    production) rather than swallowed.
    """
    ext = ext_map.get(command)
    if ext is None:
        return 1
    try:
        return ext.handle(args)
    except Exception as e:
        from multiligua_cli.utils import print_error
        print_error(f"extension dispatch failed: {e}")
        return 1


def register_hooks_from_extensions(registry=None) -> int:
    """Discover and call register_hooks() on every loaded extension.

    Forward-compat: caller may pass their own registry, or rely on the default.
    """
    if registry is None:
        registry = get_default_registry()
    count = 0
    for ext in get_extensions():
        fn = getattr(ext.module, "register_hooks", None)
        if fn:
            try:
                fn(registry)
                count += 1
            except Exception as e:
                LOGGER.warning("register_hooks failed for %s: %s", ext.name, e)
    return count
