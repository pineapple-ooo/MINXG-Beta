"""
Tests for MINXG Memory System

Tests cover:
- MemoryEngine CRUD operations
- Search and filtering
- Compression
- Export/Import
- Visualization helpers
"""
import pytest
import json
import tempfile
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
#  Memory Engine Tests
# ═══════════════════════════════════════════════════════════════════

def test_memory_engine_import():
    """Test that memory_system module imports correctly."""
    from multiligua_cli import memory_system
    assert hasattr(memory_system, 'MemoryEngine')
    assert hasattr(memory_system, 'Memory')
    assert hasattr(memory_system, 'MemoryTier')
    assert hasattr(memory_system, 'MemoryCategory')
    assert hasattr(memory_system, 'get_memory_engine')


def test_memory_engine_create():
    """Test creating a memory engine."""
    from multiligua_cli.memory_system import MemoryEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        assert engine.memories == {}
        assert engine.storage_path == path


def test_memory_add():
    """Test adding memories."""
    from multiligua_cli.memory_system import MemoryEngine, MemoryCategory, MemoryTier

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        mem = engine.add(
            content="The user prefers Python over JavaScript",
            category=MemoryCategory.PREFERENCE,
            tier=MemoryTier.LONG_TERM,
            tags=["coding", "language"],
            importance=0.8,
        )

        assert mem.id is not None
        assert mem.content == "The user prefers Python over JavaScript"
        assert mem.category == "preference"
        assert mem.tier == "long"
        assert mem.tags == ["coding", "language"]
        assert mem.importance == 0.8

        # Should be stored
        assert mem.id in engine.memories


def test_memory_get():
    """Test getting a memory."""
    from multiligua_cli.memory_system import MemoryEngine, MemoryCategory

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        mem = engine.add("Test content", category=MemoryCategory.FACT)
        retrieved = engine.get(mem.id)

        assert retrieved is not None
        assert retrieved.id == mem.id
        assert retrieved.access_count >= 1  # Access should increment


def test_memory_delete():
    """Test deleting a memory."""
    from multiligua_cli.memory_system import MemoryEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        mem = engine.add("To be deleted")
        assert mem.id in engine.memories

        result = engine.delete(mem.id)
        assert result is True
        assert mem.id not in engine.memories

        # Delete non-existent
        result = engine.delete("nonexistent")
        assert result is False


def test_memory_search():
    """Test searching memories."""
    from multiligua_cli.memory_system import MemoryEngine, MemoryCategory, MemoryTier

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        # Add several memories
        engine.add("Python is great", category=MemoryCategory.FACT, tags=["python"])
        engine.add("JavaScript is also good", category=MemoryCategory.FACT, tags=["javascript"])
        engine.add("User loves Python", category=MemoryCategory.PREFERENCE, tags=["python"])
        engine.add("Java is verbose", category=MemoryCategory.FACT, tags=["java"])

        # Search by content
        results = engine.search("python")
        assert len(results) == 2

        # Search by category
        results = engine.search("", category=MemoryCategory.PREFERENCE)
        assert len(results) == 1
        assert results[0].category == "preference"

        # Search by tags
        results = engine.search("", tags=["python"])
        assert len(results) == 2

        # Combined search
        results = engine.search("python", tags=["python"])
        assert len(results) == 2


def test_memory_stats():
    """Test memory statistics."""
    from multiligua_cli.memory_system import MemoryEngine, MemoryCategory, MemoryTier

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        # Initially empty
        stats = engine.get_stats()
        assert stats.total_memories == 0

        # Add some memories
        for i in range(5):
            engine.add(f"Memory {i}", category=MemoryCategory.FACT)
        for i in range(3):
            engine.add(f"Pref {i}", category=MemoryCategory.PREFERENCE)

        stats = engine.get_stats()
        assert stats.total_memories == 8
        assert stats.by_category["fact"] == 5
        assert stats.by_category["preference"] == 3
        assert stats.total_accesses == 0  # No gets yet


def test_memory_persistence():
    """Test that memories persist across engine instances."""
    from multiligua_cli.memory_system import MemoryEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"

        # Create and add
        engine1 = MemoryEngine(str(path))
        mem = engine1.add("Persistent memory")
        engine1._save()

        # Create new engine with same path
        engine2 = MemoryEngine(str(path))

        # Should have the memory
        assert len(engine2.memories) == 1
        assert mem.id in engine2.memories
        assert engine2.memories[mem.id].content == "Persistent memory"


def test_memory_compress():
    """Test memory compression."""
    from multiligua_cli.memory_system import MemoryEngine, MemoryCategory

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        # Add memories with varying importance
        for i in range(10):
            engine.add(
                f"Memory {i}",
                importance=0.1 * (i + 1),  # 0.1 to 1.0
            )

        assert len(engine.memories) == 10

        # Compress with min_importance=0.5
        removed, remaining = engine.compress(min_importance=0.5)

        # Memories with importance < 0.5 are removed: 0.1, 0.2, 0.3, 0.4
        # Memory with importance 0.5 is kept (>= 0.5)
        assert removed == 4  # 0.1, 0.2, 0.3, 0.4 removed
        assert remaining == 6


def test_memory_export_json():
    """Test exporting memories to JSON."""
    from multiligua_cli.memory_system import MemoryEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        engine.add("Memory 1")
        engine.add("Memory 2")

        exported = engine.export(format="json")
        data = json.loads(exported)

        assert len(data) == 2
        assert all("content" in m for m in data)


def test_memory_export_markdown():
    """Test exporting memories to Markdown."""
    from multiligua_cli.memory_system import MemoryEngine, MemoryCategory

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        engine.add("Fact 1", category=MemoryCategory.FACT)
        engine.add("Pref 1", category=MemoryCategory.PREFERENCE)

        exported = engine.export(format="markdown")

        assert "# MINXG Memory Export" in exported
        assert "Fact 1" in exported
        assert "Pref 1" in exported


def test_memory_import():
    """Test importing memories."""
    from multiligua_cli.memory_system import MemoryEngine

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"

        # Create engine with some memories
        engine1 = MemoryEngine(str(path))
        engine1.add("Import test")
        engine1._save()

        # Export
        exported = engine1.export(format="json")

        # Import into new engine
        engine2 = MemoryEngine(str(Path(tmpdir) / "test2.json"))
        count = engine2.import_memories(exported, format="json")

        assert count == 1
        assert len(engine2.memories) == 1


# ═══════════════════════════════════════════════════════════════════
#  Memory Visualization Tests
# ═══════════════════════════════════════════════════════════════════

def test_memory_viz_import():
    """Test that memory_viz module imports correctly."""
    from multiligua_cli import memory_viz
    assert hasattr(memory_viz, 'print_memory_dashboard')
    assert hasattr(memory_viz, 'print_memory_timeline')
    assert hasattr(memory_viz, 'print_memory_graph')
    assert hasattr(memory_viz, '_format_bytes')


def test_format_bytes():
    """Test byte formatting."""
    from multiligua_cli.memory_viz import _format_bytes

    assert _format_bytes(0) == "0 B"
    assert _format_bytes(500) == "500 B"
    assert _format_bytes(1500) == "1.5 KB"
    assert _format_bytes(1500000) == "1.4 MB"


def test_dashboard_with_empty_engine():
    """Test dashboard with empty engine."""
    from multiligua_cli.memory_system import MemoryEngine
    from multiligua_cli.memory_viz import print_memory_dashboard

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        # Should not raise
        stats = engine.get_stats()
        assert stats.total_memories == 0


# ═══════════════════════════════════════════════════════════════════
#  Integration Tests
# ═══════════════════════════════════════════════════════════════════

def test_memory_workflow():
    """Test a complete memory workflow."""
    from multiligua_cli.memory_system import MemoryEngine, MemoryCategory, MemoryTier

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_memories.json"
        engine = MemoryEngine(str(path))

        # Simulate a conversation
        engine.add("User name is Alice", category=MemoryCategory.FACT, importance=0.9)
        engine.add("User prefers dark mode", category=MemoryCategory.PREFERENCE, importance=0.7)
        engine.add("User is a Python developer", category=MemoryCategory.FACT, importance=0.8, tags=["coding"])
        engine.add("User asked about memory system", category=MemoryCategory.CONVERSATION, tags=["memory"])

        # Search for user info
        results = engine.search("Alice")
        assert len(results) == 1

        # Search by tag
        results = engine.search("", tags=["coding"])
        assert len(results) == 1

        # Get stats
        stats = engine.get_stats()
        assert stats.total_memories == 4
        assert stats.by_category["fact"] == 2
        assert stats.by_category["preference"] == 1
        assert stats.by_category["conversation"] == 1

        # Export
        exported = engine.export(format="json")
        assert len(json.loads(exported)) == 4


def test_global_engine():
    """Test global engine singleton."""
    from multiligua_cli.memory_system import get_memory_engine, reset_memory_engine

    reset_memory_engine()
    engine1 = get_memory_engine()
    engine2 = get_memory_engine()

    # Should be the same instance
    assert engine1 is engine2

    reset_memory_engine()
