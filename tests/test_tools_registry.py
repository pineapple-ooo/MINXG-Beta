"""
test_tools_registry.py — cover tools/*.py

Tests cover:
  - tools module imports cleanly
  - registry module imports cleanly
  - can register a dummy tool and retrieve it
  - unknown tool name returns None or raises
"""
from __future__ import annotations

import pytest

from tools import registry as tools_registry_mod
from tools.registry import ToolRegistry, registry, ToolEntry


class TestToolsImports:
    def test_tools_module_imports_cleanly(self):
        # tools/__init__.py re-exports registry, discover_builtin_tools, etc.
        import tools
        assert tools is not None
        assert hasattr(tools, "discover_builtin_tools")

    def test_registry_module_imports_cleanly(self):
        from tools.registry import ToolRegistry, registry, ToolEntry
        assert ToolRegistry is not None
        assert registry is not None
        assert ToolEntry is not None


class TestRegistryOperations:
    def test_register_and_retrieve_dummy_tool(self):
        test_registry = ToolRegistry()

        def dummy_handler(args):
            return "ok"

        test_registry.register(
            name="dummy_tool",
            toolset="test",
            schema={"description": "A dummy tool", "parameters": {}},
            handler=dummy_handler,
        )
        entry = test_registry.get_entry("dummy_tool")
        assert entry is not None
        assert entry.name == "dummy_tool"
        assert entry.toolset == "test"

    def test_unknown_tool_name_returns_none(self):
        test_registry = ToolRegistry()
        assert test_registry.get_entry("nonexistent_tool") is None

    def test_unknown_tool_dispatch_returns_error_json(self):
        test_registry = ToolRegistry()
        result = test_registry.dispatch("nonexistent_tool", {})
        assert "error" in result

    def test_get_all_tool_names_empty_registry(self):
        test_registry = ToolRegistry()
        assert test_registry.get_all_tool_names() == []

    def test_deregister_removes_tool(self):
        test_registry = ToolRegistry()

        def dummy_handler(args):
            return "ok"

        test_registry.register(
            name="temp_tool",
            toolset="test",
            schema={"description": "temp"},
            handler=dummy_handler,
        )
        assert test_registry.get_entry("temp_tool") is not None
        test_registry.deregister("temp_tool")
        assert test_registry.get_entry("temp_tool") is None

    def test_get_toolset_for_tool(self):
        test_registry = ToolRegistry()

        def dummy_handler(args):
            return "ok"

        test_registry.register(
            name="mytool",
            toolset="files",
            schema={"description": "file tool"},
            handler=dummy_handler,
        )
        assert test_registry.get_toolset_for_tool("mytool") == "files"

    def test_schema_roundtrip(self):
        test_registry = ToolRegistry()
        schema = {"description": "echo", "parameters": {"msg": {"type": "string"}}}
        test_registry.register(
            name="echo",
            toolset="test",
            schema=schema,
            handler=lambda args: args,
        )
        raw_schema = test_registry.get_schema("echo")
        assert raw_schema["description"] == "echo"
