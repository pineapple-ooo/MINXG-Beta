"""
Tests for MINXG MCP Server

These tests verify the MCP server module loads correctly and the WorkerRegistry
functions properly. They do NOT require fastmcp to be installed.
"""
import sys
import pytest

# ─── Import Tests ────────────────────────────────────────────────────────────

def test_mcp_server_imports():
    """Test that mcp_server module can be imported."""
    # This should not raise even without fastmcp installed
    from minxg import mcp_server
    assert hasattr(mcp_server, 'WorkerRegistry')
    assert hasattr(mcp_server, 'registry')
    assert hasattr(mcp_server, 'main')
    assert hasattr(mcp_server, 'SERVER_NAME')
    assert mcp_server.SERVER_NAME == "minxg"


def test_worker_registry_init():
    """Test WorkerRegistry initializes correctly."""
    from minxg.mcp_server import WorkerRegistry
    reg = WorkerRegistry()
    assert reg._workers == {}
    assert reg._loaded is False


def test_worker_registry_load_without_minxg(monkeypatch):
    """Test that registry.load() is a no-op when MINXG is not available."""
    from minxg import mcp_server
    monkeypatch.setattr(mcp_server, '_MINXG_AVAILABLE', False)
    reg = mcp_server.WorkerRegistry()
    reg.load()  # Should not raise
    assert reg._loaded is False  # Still False because _MINXG_AVAILABLE is False
    assert reg._workers == {}


# ─── Fallback Tool Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_tools_return_error():
    """Test that fallback tools return error when MCP is not installed."""
    from minxg import mcp_server

    # These should all return error dict when fastmcp is not installed
    if mcp_server.mcp is None:
        result = await mcp_server.minxg_file_read("/tmp/test")
        assert "error" in result

        result = await mcp_server.minxg_hash("hello")
        assert "error" in result

        result = await mcp_server.minxg_version()
        assert "version" in result
        assert "error" in result


# ─── Main Function Tests ────────────────────────────────────────────────────

def test_main_exits_without_mcp(monkeypatch, capsys):
    """Test that main() exits with error when MCP is not available."""
    from minxg import mcp_server

    # Force mcp to None
    monkeypatch.setattr(mcp_server, 'mcp', None)

    with pytest.raises(SystemExit) as exc_info:
        mcp_server.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "fastmcp" in captured.err


# ─── Worker List Tests ──────────────────────────────────────────────────────

def test_worker_registry_has_expected_workers():
    """Test that WORKERS list contains expected entries."""
    from minxg.mcp_server import WorkerRegistry

    worker_keys = [w[0] for w in WorkerRegistry.WORKERS]

    # Core workers should be present
    assert "fs_io" in worker_keys
    assert "network" in worker_keys
    assert "crypto" in worker_keys
    assert "math" in worker_keys
    assert "system" in worker_keys

    # Should have ~20 workers
    assert len(worker_keys) >= 15


def test_worker_registry_keys_unique():
    """Test that all worker keys are unique."""
    from minxg.mcp_server import WorkerRegistry
    keys = [w[0] for w in WorkerRegistry.WORKERS]
    assert len(keys) == len(set(keys)), "Worker keys must be unique"
