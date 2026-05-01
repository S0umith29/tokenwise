from __future__ import annotations

import csv
import sys
from datetime import date, timedelta

import click
from rich.console import Console

from .analyzer import AnalysisResult, analyze, filter_by_date_range, top_wasteful_sessions
from .dashboard import (
    build_daily_table,
    build_projects_table,
    build_summary_panel,
    build_waste_table,
    console,
    live_dashboard,
)
from .parser import CLAUDE_PROJECTS_DIR, parse_all_sessions
from .security import assert_no_network_imports

# Fail fast if any of our modules somehow imported a network stack.
assert_no_network_imports()

_err = Console(stderr=True)


def _load() -> AnalysisResult:
    if not CLAUDE_PROJECTS_DIR.exists():
        _err.print(
            "[yellow]Warning:[/yellow] ~/.claude/projects/ not found. Is Claude Code installed?"
        )
        sys.exit(1)
    sessions = parse_all_sessions()
    return analyze(sessions)


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Track and reduce your Claude/Anthropic API costs."""
    if ctx.invoked_subcommand is None:
        # Default: live dashboard
        live_dashboard(_load)


@main.command()
def today() -> None:
    """Show today's token usage and cost."""
    result = _load()
    today_date = date.today()
    filtered = filter_by_date_range(result, today_date, today_date)

    console.print(build_summary_panel(filtered, label="Today"))
    console.print()
    console.print(build_projects_table(filtered))


@main.command()
def week() -> None:
    """Show last 7 days of usage."""
    result = _load()
    start = date.today() - timedelta(days=6)
    filtered = filter_by_date_range(result, start, date.today())

    console.print(build_summary_panel(filtered, label="Last 7 Days"))
    console.print()
    console.print(build_daily_table(filtered, days=7))
    console.print()
    console.print(build_projects_table(filtered))


@main.command()
@click.argument("name")
def project(name: str) -> None:
    """Drill into a specific project by name."""
    result = _load()

    matches = {
        slug: stats
        for slug, stats in result.by_project.items()
        if name.lower() in stats.project_name.lower() or name.lower() in slug.lower()
    }

    if not matches:
        _err.print(f"[red]No project matching '{name}' found.[/red]")
        available = ", ".join(s.project_name for s in result.by_project.values())
        _err.print(f"Available: {available}")
        sys.exit(1)

    for slug, stats in matches.items():
        sessions = [s for s in result.all_sessions if s.project_slug == slug]
        sessions.sort(key=lambda s: s.start_time or date.min, reverse=True)

        from rich import box
        from rich.table import Table

        table = Table(
            title=f"[bold]{stats.project_name}[/bold] — {len(sessions)} sessions",
            box=box.SIMPLE_HEAD,
            header_style="bold cyan",
        )
        table.add_column("Date")
        table.add_column("Model")
        table.add_column("Turns", justify="right")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Cache↓", justify="right")
        table.add_column("Cost", justify="right")

        from .dashboard import _fmt_cost, _fmt_tokens

        for s in sessions[:20]:
            date_str = s.start_time.strftime("%Y-%m-%d %H:%M") if s.start_time else "—"
            model_short = s.model.replace("claude-", "").replace("-20", " '")
            table.add_row(
                date_str,
                model_short,
                str(s.turns),
                _fmt_tokens(s.input_tokens),
                _fmt_tokens(s.output_tokens),
                _fmt_tokens(s.cache_read_tokens),
                _fmt_cost(s.cost_usd),
            )

        console.print(table)


@main.command()
@click.option("--top", default=10, show_default=True, help="Number of sessions to show.")
def waste(top: int) -> None:
    """Find sessions that burned tokens with little output."""
    result = _load()
    wasteful = top_wasteful_sessions(result, n=top)

    if not wasteful:
        console.print("[green]No wasteful sessions detected.[/green]")
        return

    console.print(build_waste_table(wasteful, n=top))
    console.print()
    console.print(
        "[dim]Tip: A high ratio means a large context window was sent for very little output.\n"
        "Consider breaking large sessions into smaller focused tasks.[/dim]"
    )


@main.command()
@click.option("--csv", "as_csv", is_flag=True, help="Output as CSV.")
def export(as_csv: bool) -> None:
    """Export raw session data."""
    result = _load()
    sessions = sorted(
        result.all_sessions,
        key=lambda s: s.start_time or date.min,
        reverse=True,
    )

    if as_csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(
            [
                "date",
                "project",
                "session_id",
                "model",
                "input_tokens",
                "output_tokens",
                "cache_write_tokens",
                "cache_read_tokens",
                "total_tokens",
                "cost_usd",
            ]
        )
        for s in sessions:
            writer.writerow(
                [
                    s.start_time.date() if s.start_time else "",
                    s.project_name,
                    s.session_id,
                    s.model,
                    s.input_tokens,
                    s.output_tokens,
                    s.cache_write_tokens,
                    s.cache_read_tokens,
                    s.total_tokens,
                    f"{s.cost_usd:.6f}",
                ]
            )
    else:
        from rich import box
        from rich.table import Table

        from .dashboard import _fmt_cost, _fmt_tokens

        table = Table(box=box.SIMPLE_HEAD, header_style="bold cyan")
        table.add_column("Date")
        table.add_column("Project")
        table.add_column("Total Tokens", justify="right")
        table.add_column("Cost", justify="right")
        for s in sessions[:50]:
            table.add_row(
                str(s.start_time.date()) if s.start_time else "—",
                s.project_name,
                _fmt_tokens(s.total_tokens),
                _fmt_cost(s.cost_usd),
            )
        console.print(table)


@main.command("update-prices")
def update_prices() -> None:
    """[stub] Update pricing data from Anthropic's website."""
    console.print(
        "[yellow]update-prices is not yet implemented.[/yellow]\n"
        "To update prices manually, edit [bold]src/tokenwise/pricing.py[/bold].\n"
        "Current prices: https://www.anthropic.com/pricing"
    )
