"""
multiligua_cli/cost_tracker.py — Token & Cost Tracking

Track API usage, token consumption, and estimated costs across
all providers. Provides real-time cost estimation and budget alerts.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════
#  Pricing Data (per 1M tokens, in USD)
# ═══════════════════════════════════════════════════════════════════

PRICING: Dict[str, Dict[str, float]] = {
    # Provider: {input: $/1M tokens, output: $/1M tokens}
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
        "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
        "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
        "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    },
    "google": {
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.14, "output": 0.28},
        "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    },
    "openrouter": {
        "default": {"input": 0.50, "output": 1.50},  # varies by model
    },
    "xai": {
        "grok-beta": {"input": 5.00, "output": 15.00},
        "grok-2": {"input": 2.00, "output": 10.00},
    },
    "ollama": {
        "default": {"input": 0.00, "output": 0.00},  # local, free
    },
    "llamacpp": {
        "default": {"input": 0.00, "output": 0.00},  # local, free
    },
    "vllm": {
        "default": {"input": 0.00, "output": 0.00},  # self-hosted
    },
}


# ═══════════════════════════════════════════════════════════════════
#  Cost Tracker
# ═══════════════════════════════════════════════════════════════════

@dataclass
class UsageRecord:
    """A single usage record."""
    timestamp: float
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    latency_ms: float


@dataclass
class CostTracker:
    """Track API usage and costs."""
    records: List[UsageRecord] = field(default_factory=list)
    budget_usd: float = 10.00  # Default budget
    budget_alert_threshold: float = 0.80  # Alert at 80%

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)

    @property
    def total_cost(self) -> float:
        return sum(r.cost for r in self.records)

    @property
    def total_requests(self) -> int:
        return len(self.records)

    @property
    def budget_remaining(self) -> float:
        return max(0.0, self.budget_usd - self.total_cost)

    @property
    def budget_used_percent(self) -> float:
        if self.budget_usd <= 0:
            return 0.0
        return (self.total_cost / self.budget_usd) * 100

    def should_alert(self) -> bool:
        """Check if we should alert about budget."""
        return self.budget_used_percent >= (self.budget_alert_threshold * 100)

    def estimate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a given token count."""
        provider_pricing = PRICING.get(provider, {})
        model_pricing = provider_pricing.get(model, provider_pricing.get("default", {"input": 0, "output": 0}))

        input_cost = (input_tokens / 1_000_000) * model_pricing.get("input", 0)
        output_cost = (output_tokens / 1_000_000) * model_pricing.get("output", 0)

        return input_cost + output_cost

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float = 0.0,
    ) -> UsageRecord:
        """Record a usage event."""
        cost = self.estimate_cost(provider, model, input_tokens, output_tokens)
        record = UsageRecord(
            timestamp=time.time(),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            latency_ms=latency_ms,
        )
        self.records.append(record)
        return record

    def get_summary(self) -> Dict[str, any]:
        """Get a summary of usage."""
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost,
            "budget_usd": self.budget_usd,
            "budget_remaining": self.budget_remaining,
            "budget_used_percent": self.budget_used_percent,
            "should_alert": self.should_alert(),
        }

    def get_by_provider(self) -> Dict[str, Dict[str, any]]:
        """Get usage breakdown by provider."""
        by_provider: Dict[str, Dict[str, any]] = {}
        for r in self.records:
            if r.provider not in by_provider:
                by_provider[r.provider] = {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0,
                }
            by_provider[r.provider]["requests"] += 1
            by_provider[r.provider]["input_tokens"] += r.input_tokens
            by_provider[r.provider]["output_tokens"] += r.output_tokens
            by_provider[r.provider]["cost"] += r.cost
        return by_provider

    def reset(self) -> None:
        """Reset all records."""
        self.records.clear()


# ═══════════════════════════════════════════════════════════════════
#  Global Tracker Instance
# ═══════════════════════════════════════════════════════════════════

_global_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get the global cost tracker."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


def reset_tracker() -> None:
    """Reset the global tracker."""
    global _global_tracker
    _global_tracker = CostTracker()


# ═══════════════════════════════════════════════════════════════════
#  Display Helpers
# ═══════════════════════════════════════════════════════════════════

def format_tokens(n: int) -> str:
    """Format token count for display."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n}"


def format_cost(usd: float) -> str:
    """Format cost for display."""
    if usd < 0.01:
        return f"${usd * 100:.2f}¢"
    return f"${usd:.2f}"


def print_cost_summary(console=None) -> None:
    """Print cost summary."""
    tracker = get_tracker()
    summary = tracker.get_summary()

    if console is None:
        try:
            from multiligua_cli.utils import console
        except ImportError:
            print(f"\nCost Summary:")
            print(f"  Requests: {summary['total_requests']}")
            print(f"  Input tokens: {format_tokens(summary['total_input_tokens'])}")
            print(f"  Output tokens: {format_tokens(summary['total_output_tokens'])}")
            print(f"  Total cost: {format_cost(summary['total_cost_usd'])}")
            print(f"  Budget: {format_cost(summary['budget_usd'])}")
            print(f"  Remaining: {format_cost(summary['budget_remaining'])}")
            print(f"  Used: {summary['budget_used_percent']:.1f}%")
            if summary['should_alert']:
                print(f"  ⚠️  BUDGET ALERT!")
            return

    try:
        from rich.table import Table
        from rich.panel import Panel
        from rich import box
    except ImportError:
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=box.SIMPLE,
        expand=True,
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Requests", str(summary["total_requests"]))
    table.add_row("Input Tokens", format_tokens(summary["total_input_tokens"]))
    table.add_row("Output Tokens", format_tokens(summary["total_output_tokens"]))
    table.add_row("Total Cost", format_cost(summary["total_cost_usd"]))
    table.add_row("Budget", format_cost(summary["budget_usd"]))
    table.add_row("Remaining", format_cost(summary["budget_remaining"]))

    used_pct = summary["budget_used_percent"]
    color = "green" if used_pct < 50 else "yellow" if used_pct < 80 else "red"
    table.add_row("Used", f"[{color}]{used_pct:.1f}%[/{color}]")

    title = "[bold gold3]◆  Cost Tracker[/bold gold3]"
    if summary["should_alert"]:
        title += " [bold red]⚠️  BUDGET ALERT[/bold red]"

    console.print(Panel(
        table,
        title=title,
        border_style="bright_blue",
        padding=(0, 1),
    ))
