"""




""""
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
    "import_hermes_skill",
    "import_claude_skill",
    "import_codex_tool",
    "run_ext_import",
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
                import logging

                logging.getLogger("extensions").warning(
                    "Hook %s (%s) raised %s", hook_name, getattr(cb, "__name__", cb), e,
                )
        return results

    def run_hook_chain(self, hook_name: str, initial_value: Any, *args, **kwargs) -> Any:
        """
        pre_chat_hook: (messages, system_prompt) → (messages, system_prompt)
        post_chat_hook: (response_text) → response_text
        """"
        value = initial_value
        for _, cb in self._hooks.get(hook_name, []):
            try:
                value = cb(value, *args, **kwargs)
            except Exception as e:
                import logging
                logging.getLogger("extensions").warning(
                    "Hook %s (%s) raised %s", hook_name, getattr(cb, "__name__", cb), e,
                )
        return value

    def list_hooks(self) -> Dict[str, int]:
        return {name: len(cbs) for name, cbs in self._hooks.items()}

    def clear(self):
        for name in self._hooks:
            self._hooks[name].clear()


def register_hook(
    hook_name: str,
    callback: Callable,
    priority: int = 50,
    registry: ExtensionRegistry = None,
):
    if registry is None:
        registry = get_default_registry()
    registry.register(hook_name, callback, priority)


_default_registry: Optional[ExtensionRegistry] = None


def get_default_registry() -> ExtensionRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = ExtensionRegistry()
    return _default_registry




from extensions.loader import (  
    ExtensionModule,
    get_extension,
    get_extensions,
    list_extensions,
    reload_extensions,
    cleanup_temp_dirs,
    import_hermes_skill,
    import_claude_skill,
    import_codex_tool,
    run_ext_import,
)


def register_cli_extensions(subparsers) -> Dict[str, ExtensionModule]:

    """
    ext_map: Dict[str, ExtensionModule] = {}
    try:
        for ext in get_extensions():
            if ext.name in ext_map:
                continue
            ext_map[ext.name] = ext
            ext.register_cli(subparsers)
    except Exception as e:
        import logging
        logging.getLogger("extensions").warning("register_cli_extensions failed: %s", e)
    return ext_map


def dispatch_extension(ext_map: Dict, command: str, args) -> int:
    ext = ext_map.get(command)
    if ext is None:
        return 1
    try:
        return ext.handle(args)
    except Exception as e:
        from multiligua_cli.utils import print_error

        import traceback
        traceback.print_exc()
        return 1


def register_hooks_from_extensions(registry: ExtensionRegistry = None) -> int:

    """"
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
                import logging
                logging.getLogger("extensions").warning("register_hooks failed for extension: %s", e)
    return count
