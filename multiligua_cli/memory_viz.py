"""
multiligua_cli/memory_viz.py — Memory Visualization

Visual representation of the memory system including:
- Memory graph/network
- Category distribution
- Timeline view
- Importance heatmap
"""
from __future__ import annotations

from typing import Dict, List, Optional


def print_memory_dashboard(engine=None, console=None) -> None:
    """Print a visual dashboard of the memory system."""
    if engine is None:
        from multiligua_cli.memory_system import get_memory_engine
        engine = get_memory_engine()

    if console is None:
        try:
            from multiligua_cli.utils import console
        except ImportError:
            _print_text_dashboard(engine)
            return

    try:
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
        from rich.text import Text
        from rich.console import Group
    except ImportError:
        _print_text_dashboard(engine)
        return

    stats = engine.get_stats()

    # ── Summary Panel ──────────────────────────────────────────────
    summary = Table(
        show_header=False,
        show_edge=False,
        padding=(0, 1),
        box=box.SIMPLE,
        expand=True,
    )
    summary.add_column("Metric", style="bold cyan", width=20)
    summary.add_column("Value", style="bold")

    summary.add_row("Total Memories", str(stats.total_memories))
    summary.add_row("Total Size", _format_bytes(stats.total_size_bytes))
    summary.add_row("Avg Importance", f"{stats.avg_importance:.2f}")
    summary.add_row("Total Accesses", str(stats.total_accesses))

    if stats.oldest_memory:
        from datetime import datetime
        oldest = datetime.fromtimestamp(stats.oldest_memory).strftime("%Y-%m-%d")
        newest = datetime.fromtimestamp(stats.newest_memory).strftime("%Y-%m-%d")
        summary.add_row("Age Range", f"{oldest} → {newest}")

    # ── Distribution Table ─────────────────────────────────────────
    dist = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        expand=True,
    )
    dist.add_column("Tier", style="bold", width=12)
    dist.add_column("Category", style="bold", width=14)
    dist.add_column("Count", justify="right")
    dist.add_column("Bar", width=30)

    max_count = max(stats.by_tier.values()) if stats.by_tier else 1

    # Show by tier
    for tier, count in sorted(stats.by_tier.items()):
        bar_len = int((count / max_count) * 25) if max_count > 0 else 0
        bar = "█" * bar_len
        dist.add_row(tier.title(), "—", str(count), f"[cyan]{bar}[/cyan]")

    # Show by category
    for cat, count in sorted(stats.by_category.items()):
        bar_len = int((count / max_count) * 25) if max_count > 0 else 0
        bar = "█" * bar_len
        dist.add_row("—", cat.title(), str(count), f"[green]{bar}[/green]")

    # ── Recent Memories ────────────────────────────────────────────
    recent_table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        expand=True,
    )
    recent_table.add_column("ID", style="dim", width=10)
    recent_table.add_column("Category", width=12)
    recent_table.add_column("Content", width=50)
    recent_table.add_column("Imp.", justify="right", width=6)
    recent_table.add_column("Accesses", justify="right", width=8)

    recent = sorted(
        engine.memories.values(),
        key=lambda m: m.created_at,
        reverse=True,
    )[:10]

    for mem in recent:
        content = mem.content[:47] + "..." if len(mem.content) > 50 else mem.content
        imp_color = "green" if mem.importance > 0.7 else "yellow" if mem.importance > 0.4 else "red"
        recent_table.add_row(
            mem.id[:8],
            mem.category.title(),
            content,
            f"[{imp_color}]{mem.importance:.2f}[/{imp_color}]",
            str(mem.access_count),
        )

    # ── Assemble Dashboard ─────────────────────────────────────────
    console.print(Panel(
        summary,
        title="[bold gold3]◆  Memory Dashboard[/bold gold3]",
        border_style="bright_blue",
        padding=(0, 1),
    ))

    console.print(Panel(
        dist,
        title="[bold gold3]◆  Distribution[/bold gold3]",
        border_style="bright_blue",
        padding=(0, 1),
    ))

    if recent:
        console.print(Panel(
            recent_table,
            title="[bold gold3]◆  Recent Memories[/bold gold3]",
            border_style="bright_blue",
            padding=(0, 1),
        ))


def _print_text_dashboard(engine) -> None:
    """Fallback text-only dashboard."""
    stats = engine.get_stats()

    print("\n" + "=" * 60)
    print("  MINXG Memory Dashboard")
    print("=" * 60)

    print(f"\n  Total Memories: {stats.total_memories}")
    print(f"  Total Size: {_format_bytes(stats.total_size_bytes)}")
    print(f"  Avg Importance: {stats.avg_importance:.2f}")
    print(f"  Total Accesses: {stats.total_accesses}")

    print("\n  By Tier:")
    for tier, count in sorted(stats.by_tier.items()):
        print(f"    {tier:12} {count:4}")

    print("\n  By Category:")
    for cat, count in sorted(stats.by_category.items()):
        print(f"    {cat:14} {count:4}")

    print("\n  Recent Memories:")
    recent = sorted(
        engine.memories.values(),
        key=lambda m: m.created_at,
        reverse=True,
    )[:5]

    for mem in recent:
        print(f"    [{mem.category}] {mem.content[:60]}...")

    print()


def _format_bytes(size: int) -> str:
    """Format byte size for display."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def print_memory_timeline(engine=None, console=None, limit: int = 50) -> None:
    """Print a timeline view of memories."""
    if engine is None:
        from multiligua_cli.memory_system import get_memory_engine
        engine = get_memory_engine()

    if not engine.memories:
        if console:
            console.print("[dim]No memories to display.[/dim]")
        else:
            print("No memories.")
        return

    memories = sorted(engine.memories.values(), key=lambda m: m.created_at)

    if console:
        try:
            from rich.console import Console
            from rich.text import Text
            from datetime import datetime

            console.print(f"\n[bold]Memory Timeline ({len(memories)} memories)[/bold]\n")

            # Group by day
            by_day = {}
            for mem in memories:
                day = datetime.fromtimestamp(mem.created_at).strftime("%Y-%m-%d")
                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(mem)

            for day in sorted(by_day.keys()):
                console.print(f"\n[bold cyan]{day}[/bold cyan]")
                for mem in by_day[day][:limit // len(by_day) + 1]:
                    cat_emoji = {
                        "fact": "📌",
                        "preference": "❤️",
                        "summary": "📝",
                        "conversation": "💬",
                        "skill": "🛠️",
                        "context": "📎",
                    }.get(mem.category, "•")

                    importance_bar = "█" * int(mem.importance * 5)
                    console.print(
                        f"  {cat_emoji} [{importance_bar:<5}] {mem.content[:70]}..."
                    )
        except ImportError:
            pass
    else:
        print(f"\nMemory Timeline ({len(memories)} memories)\n")
        for mem in memories[-limit:]:
            day = datetime.fromtimestamp(mem.created_at).strftime("%Y-%m-%d")
            print(f"  [{day}] [{mem.category}] {mem.content[:80]}")


def print_memory_graph(engine=None, console=None) -> None:
    """Print a simple text-based memory graph showing connections."""
    if engine is None:
        from multiligua_cli.memory_system import get_memory_engine
        engine = get_memory_engine()

    if not engine.memories:
        return

    # Build tag co-occurrence graph
    tag_connections = {}
    for mem in engine.memories.values():
        tags = mem.tags
        for i, t1 in enumerate(tags):
            if t1 not in tag_connections:
                tag_connections[t1] = {}
            for t2 in tags[i + 1:]:
                tag_connections[t1][t2] = tag_connections[t1].get(t2, 0) + 1
                tag_connections[t2] = tag_connections.get(t2, {})
                tag_connections[t2][t1] = tag_connections[t2].get(t1, 0) + 1

    if not tag_connections:
        return

    if console:
        try:
            from rich.table import Table
            from rich.panel import Panel
            from rich import box

            table = Table(
                show_header=True,
                header_style="bold cyan",
                box=box.SIMPLE,
            )
            table.add_column("Tag 1", style="bold")
            table.add_column("Tag 2", style="bold")
            table.add_column("Connections", justify="right")

            edges = []
            for t1, connections in tag_connections.items():
                for t2, count in connections.items():
                    if t1 < t2:  # Avoid duplicates
                        edges.append((t1, t2, count))

            edges.sort(key=lambda x: x[2], reverse=True)

            for t1, t2, count in edges[:20]:
                table.add_row(t1, t2, str(count))

            console.print(Panel(
                table,
                title="[bold gold3]◆  Memory Tag Graph[/bold gold3]",
                border_style="bright_blue",
                padding=(0, 1),
            ))
        except ImportError:
            pass
    else:
        print("\nMemory Tag Connections:")
        for t1, connections in list(tag_connections.items())[:10]:
            for t2, count in list(connections.items())[:5]:
                if t1 < t2:
                    print(f"  {t1} ──{count}── {t2}")
