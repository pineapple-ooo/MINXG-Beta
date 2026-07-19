"""
multiligua_cli/model_compare.py — Multi-Model Comparison

Compare responses from multiple AI models side by side.
Useful for evaluating model quality, cost, and speed.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ModelResponse:
    """Response from a single model."""
    provider: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost_usd: float
    error: Optional[str] = None


@dataclass
class ComparisonResult:
    """Result of comparing multiple models."""
    prompt: str
    responses: List[ModelResponse]
    started_at: float
    finished_at: float

    @property
    def total_time_ms(self) -> float:
        return (self.finished_at - self.started_at) * 1000

    @property
    def fastest(self) -> Optional[ModelResponse]:
        valid = [r for r in self.responses if not r.error]
        return min(valid, key=lambda r: r.latency_ms) if valid else None

    @property
    def cheapest(self) -> Optional[ModelResponse]:
        valid = [r for r in self.responses if not r.error]
        return min(valid, key=lambda r: r.cost_usd) if valid else None

    @property
    def shortest(self) -> Optional[ModelResponse]:
        valid = [r for r in self.responses if not r.error]
        return min(valid, key=lambda r: len(r.content)) if valid else None

    @property
    def longest(self) -> Optional[ModelResponse]:
        valid = [r for r in self.responses if not r.error]
        return max(valid, key=lambda r: len(r.content)) if valid else None


class ModelComparator:
    """Compare responses from multiple models."""

    def __init__(self):
        self.results: List[ComparisonResult] = []
        self._orchestrators: Dict[str, Any] = {}

    def _get_orchestrator(self, provider: str, model: str, config: dict) -> Any:
        """Get or create an orchestrator for a provider/model pair."""
        key = f"{provider}:{model}"
        if key not in self._orchestrators:
            try:
                from multiling.orchestrator import NexusOrchestrator
                self._orchestrators[key] = NexusOrchestrator(
                    ai_base_url=config.get("ai", {}).get("base_url"),
                    ai_api_key=config.get("ai", {}).get("api_key"),
                    ai_provider=provider,
                    ai_model=model,
                )
            except ImportError:
                self._orchestrators[key] = None
        return self._orchestrators[key]

    async def _query_model(
        self,
        provider: str,
        model: str,
        prompt: str,
        config: dict,
    ) -> ModelResponse:
        """Query a single model and return response metrics."""
        started = time.time()

        try:
            orch = self._get_orchestrator(provider, model, config)
            if orch is None:
                return ModelResponse(
                    provider=provider,
                    model=model,
                    content="",
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=0,
                    cost_usd=0,
                    error="Failed to create orchestrator",
                )

            # Run the query
            response = await orch.run(prompt)
            latency = (time.time() - started) * 1000

            # Estimate tokens (rough approximation)
            output_tokens = len(response) // 4 if isinstance(response, str) else 0
            input_tokens = len(prompt) // 4

            # Estimate cost
            from multiligua_cli.cost_tracker import get_tracker
            tracker = get_tracker()
            cost = tracker.estimate_cost(provider, model, input_tokens, output_tokens)

            return ModelResponse(
                provider=provider,
                model=model,
                content=response or "",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
                cost_usd=cost,
            )

        except Exception as e:
            return ModelResponse(
                provider=provider,
                model=model,
                content="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=(time.time() - started) * 1000,
                cost_usd=0,
                error=str(e),
            )

    async def compare(
        self,
        prompt: str,
        models: List[Tuple[str, str]],  # [(provider, model), ...]
        config: dict,
    ) -> ComparisonResult:
        """Compare multiple models on the same prompt."""
        started = time.time()

        # Query all models concurrently
        tasks = [
            self._query_model(provider, model, prompt, config)
            for provider, model in models
        ]
        responses = await asyncio.gather(*tasks)

        result = ComparisonResult(
            prompt=prompt,
            responses=list(responses),
            started_at=started,
            finished_at=time.time(),
        )

        self.results.append(result)
        return result

    def print_comparison(self, result: ComparisonResult, console=None) -> None:
        """Print a comparison result in a formatted way."""
        if console is None:
            try:
                from multiligua_cli.utils import console
            except ImportError:
                print(f"\nComparison Results:")
                print(f"  Prompt: {result.prompt[:50]}...")
                print(f"  Total time: {result.total_time_ms:.0f}ms")
                for r in result.responses:
                    status = "✓" if not r.error else f"✗ {r.error}"
                    print(f"  {r.provider}/{r.model}: {status}")
                return

        try:
            from rich.table import Table
            from rich.panel import Panel
            from rich import box
            from rich.text import Text
        except ImportError:
            return

        # Summary table
        summary = Table(
            show_header=True,
            header_style="bold cyan",
            box=box.SIMPLE,
            expand=True,
        )
        summary.add_column("Model", style="bold")
        summary.add_column("Status", width=8)
        summary.add_column("Latency", justify="right")
        summary.add_column("Tokens", justify="right")
        summary.add_column("Cost", justify="right")
        summary.add_column("Length", justify="right")

        for r in result.responses:
            status = "[green]✓[/green]" if not r.error else f"[red]✗[/red]"
            summary.add_row(
                f"{r.provider}/{r.model}",
                status,
                f"{r.latency_ms:.0f}ms",
                f"{r.output_tokens}",
                f"${r.cost_usd:.4f}",
                f"{len(r.content)}",
            )

        console.print(Panel(
            summary,
            title="[bold gold3]◆  Model Comparison[/bold gold3]",
            border_style="bright_blue",
            padding=(0, 1),
        ))

        # Side-by-side responses
        if len(result.responses) > 1:
            # Find the longest content for sync
            max_len = max(len(r.content) for r in result.responses if not r.error)

            for r in result.responses:
                if r.error:
                    console.print(f"\n[red]✗ {r.provider}/{r.model}: {r.error}[/red]")
                    continue

                console.print(f"\n[bold cyan]▸ {r.provider}/{r.model}[/bold cyan] "
                             f"[dim]({r.latency_ms:.0f}ms, {r.output_tokens} tokens, "
                             f"${r.cost_usd:.4f})[/dim]")
                console.print(f"[dim]{'─' * 60}[/dim]")
                console.print(r.content[:500] + ("..." if len(r.content) > 500 else ""))

        # Winner highlights
        console.print()
        if result.fastest:
            console.print(f"  [bold green]⚡ Fastest:[/bold green] "
                         f"{result.fastest.provider}/{result.fastest.model} "
                         f"({result.fastest.latency_ms:.0f}ms)")
        if result.cheapest:
            console.print(f"  [bold green]💰 Cheapest:[/bold green] "
                         f"{result.cheapest.provider}/{result.cheapest.model} "
                         f"(${result.cheapest.cost_usd:.4f})")


# Global comparator instance
_comparator: Optional[ModelComparator] = None


def get_comparator() -> ModelComparator:
    """Get the global model comparator."""
    global _comparator
    if _comparator is None:
        _comparator = ModelComparator()
    return _comparator
