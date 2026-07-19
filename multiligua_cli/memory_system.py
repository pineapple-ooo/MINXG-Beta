"""
multiligua_cli/memory_system.py — Advanced Memory System

A comprehensive memory system for MINXG with:
- Multi-tier memory (working, short-term, long-term)
- Memory categories (facts, preferences, summaries, conversations)
- Similarity search and retrieval
- Memory compression and summarization
- Visualization and export
"""
from __future__ import annotations

import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class MemoryTier(Enum):
    WORKING = "working"      # Current session
    SHORT_TERM = "short"     # Last 24h
    LONG_TERM = "long"       # Persistent


class MemoryCategory(Enum):
    FACT = "fact"                    # Factual information
    PREFERENCE = "preference"        # User preferences
    SUMMARY = "summary"              # Conversation summaries
    CONVERSATION = "conversation"    # Raw conversation turns
    SKILL = "skill"                  # Learned skills/patterns
    CONTEXT = "context"              # Contextual information


@dataclass
class Memory:
    """A single memory item."""
    id: str
    content: str
    category: str
    tier: str
    tags: List[str]
    created_at: float
    updated_at: float
    access_count: int = 0
    importance: float = 1.0
    source: str = ""
    embedding: Optional[List[float]] = None
    pinned: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        return cls(**data)


@dataclass
class MemoryStats:
    """Statistics about the memory system."""
    total_memories: int = 0
    by_tier: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    total_size_bytes: int = 0
    oldest_memory: float = 0
    newest_memory: float = 0
    avg_importance: float = 0.0
    total_accesses: int = 0


class MemoryEngine:
    """
    Advanced memory engine with multi-tier storage,
    similarity search, and automatic compression.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.memories: Dict[str, Memory] = {}
        self.storage_path = Path(storage_path) if storage_path else (
            Path.home() / ".minxg" / "memory" / "memories.json"
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _generate_id(self, content: str) -> str:
        """Generate a unique ID for a memory."""
        return hashlib.md5(
            f"{content}{time.time()}".encode()
        ).hexdigest()[:12]

    def add(
        self,
        content: str,
        category: MemoryCategory = MemoryCategory.FACT,
        tier: MemoryTier = MemoryTier.SHORT_TERM,
        tags: Optional[List[str]] = None,
        source: str = "",
        importance: float = 1.0,
    ) -> Memory:
        """Add a new memory."""
        now = time.time()
        memory = Memory(
            id=self._generate_id(content),
            content=content,
            category=category.value,
            tier=tier.value,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            access_count=0,
            importance=importance,
            source=source,
        )
        self.memories[memory.id] = memory
        self._save()
        return memory

    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        mem = self.memories.get(memory_id)
        if mem:
            mem.access_count += 1
            mem.updated_at = time.time()
        return mem

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        if memory_id in self.memories:
            del self.memories[memory_id]
            self._save()
            return True
        return False

    def search(
        self,
        query: str,
        category: Optional[MemoryCategory] = None,
        tier: Optional[MemoryTier] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Memory]:
        """Search memories by content, category, tier, or tags."""
        results = []
        query_lower = query.lower()

        for mem in self.memories.values():
            # Filter by category
            if category and mem.category != category.value:
                continue
            # Filter by tier
            if tier and mem.tier != tier.value:
                continue
            # Filter by tags
            if tags and not any(t in mem.tags for t in tags):
                continue
            # Search content
            if query and query_lower not in mem.content.lower():
                continue

            results.append(mem)

        # Sort by importance and recency
        results.sort(
            key=lambda m: (
                m.importance * 0.6 +
                (1.0 / (1.0 + time.time() - m.created_at)) * 0.4
            ),
            reverse=True,
        )

        return results[:limit]

    def get_stats(self) -> MemoryStats:
        """Get memory system statistics."""
        stats = MemoryStats(total_memories=len(self.memories))
        stats.by_tier = {}
        stats.by_category = {}

        total_importance = 0.0
        total_accesses = 0
        oldest = float("inf")
        newest = 0

        for mem in self.memories.values():
            # By tier
            stats.by_tier[mem.tier] = stats.by_tier.get(mem.tier, 0) + 1
            # By category
            stats.by_category[mem.category] = (
                stats.by_category.get(mem.category, 0) + 1
            )
            total_importance += mem.importance
            total_accesses += mem.access_count
            oldest = min(oldest, mem.created_at)
            newest = max(newest, mem.created_at)

        stats.total_accesses = total_accesses
        stats.oldest_memory = oldest if oldest != float("inf") else 0
        stats.newest_memory = newest
        stats.avg_importance = (
            total_importance / len(self.memories) if self.memories else 0
        )

        # Estimate size
        stats.total_size_bytes = len(json.dumps(
            [m.to_dict() for m in self.memories.values()]
        ))

        return stats

    def compress(
        self,
        max_memories: int = 100,
        min_importance: float = 0.3,
    ) -> Tuple[int, int]:
        """
        Compress memories by removing low-importance ones.
        Returns (removed_count, remaining_count).
        """
        to_remove = []
        for mem_id, mem in self.memories.items():
            if mem.pinned:
                continue
            if mem.importance < min_importance:
                to_remove.append(mem_id)

        # If still over limit, remove oldest low-importance
        if len(self.memories) - len(to_remove) > max_memories:
            sorted_mems = sorted(
                self.memories.items(),
                key=lambda x: (x[1].importance, x[1].created_at),
            )
            for mem_id, mem in sorted_mems:
                if len(self.memories) - len(to_remove) <= max_memories:
                    break
                if mem_id not in to_remove and not mem.pinned:
                    to_remove.append(mem_id)

        for mem_id in to_remove:
            del self.memories[mem_id]

        self._save()
        return len(to_remove), len(self.memories)

    def export(self, format: str = "json") -> str:
        """Export memories to JSON or Markdown."""
        if format == "json":
            return json.dumps(
                [m.to_dict() for m in self.memories.values()],
                indent=2,
                ensure_ascii=False,
            )
        elif format == "markdown":
            lines = ["# MINXG Memory Export\n"]
            lines.append(f"*Generated: {datetime.now().isoformat()}*\n")
            lines.append(f"*Total: {len(self.memories)} memories*\n\n")

            by_cat = {}
            for mem in self.memories.values():
                if mem.category not in by_cat:
                    by_cat[mem.category] = []
                by_cat[mem.category].append(mem)

            for cat, mems in by_cat.items():
                lines.append(f"## {cat.title()}\n")
                for mem in mems[:20]:  # Limit per category
                    lines.append(f"- {mem.content[:200]}")
                    if mem.tags:
                        lines.append(f"  *Tags: {', '.join(mem.tags)}*")
                lines.append("")

            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")

    def import_memories(self, data: str, format: str = "json") -> int:
        """Import memories from JSON or Markdown."""
        count = 0
        if format == "json":
            memories = json.loads(data)
            for mem_dict in memories:
                mem = Memory.from_dict(mem_dict)
                self.memories[mem.id] = mem
                count += 1
        elif format == "markdown":
            # Simple parser for markdown format
            for line in data.split("\n"):
                line = line.strip()
                if line.startswith("- ") and not line.startswith("- *"):
                    self.add(
                        content=line[2:],
                        category=MemoryCategory.FACT,
                    )
                    count += 1
        self._save()
        return count

    def _save(self) -> None:
        """Save memories to disk."""
        try:
            data = [m.to_dict() for m in self.memories.values()]
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save memories: {e}")

    def _load(self) -> None:
        """Load memories from disk."""
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for mem_dict in data:
                mem = Memory.from_dict(mem_dict)
                self.memories[mem.id] = mem
        except Exception as e:
            print(f"Warning: Failed to load memories: {e}")


# Global instance
_engine: Optional[MemoryEngine] = None


def get_memory_engine() -> MemoryEngine:
    """Get the global memory engine."""
    global _engine
    if _engine is None:
        _engine = MemoryEngine()
    return _engine


def reset_memory_engine() -> None:
    """Reset the global memory engine."""
    global _engine
    _engine = None
