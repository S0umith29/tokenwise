from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime, timedelta

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .analyzer import AnalysisResult, DailySummary, SessionStats, filter_by_date_range

console = Console()

_COST_COLOR = "green"
_WARN_COLOR = "yellow"
_HOT_COLOR = "red"
_DIM = "dim"


def _fmt_cost(usd: float) -> str:
    if usd < 0.01:
        return f"[{_DIM}]< $0.01[/{_DIM}]"
    if usd >= 1.0:
        return f"[bold {_HOT_COLOR}]${usd:.2f}[/bold {_HOT_COLOR}]"
    return f"[{_COST_COLOR}]${usd:.4f}[/{_COST_COLOR}]"


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _sparkline(values: list[float], width: int = 8) -> str:
    bars = " ▁▂▃▄▅▆▇█"
    if not values or max(values) == 0:
        return " " * width
    hi = max(values)
    return "".join(bars[int(v / hi * 8)] for v in values[-width:])


def build_summary_panel(result: AnalysisResult, label: str = "All Time") -> Panel:
    today = date.today()
    today_result = filter_by_date_range(result, today, today)
    week_start = today - timedelta(days=6)
    week_result = filter_by_date_range(result, week_start, today)

    rows = [
        ("Today", today_result.total_cost_usd, today_result.total_tokens),
        ("This Week", week_result.total_cost_usd, week_result.total_tokens),
        ("All Time", result.total_cost_usd, result.total_tokens),
    ]

    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column("Period", style="bold")
    table.add_column("Cost", justify="right")
    table.add_column("Tokens", justify="right")

    for period, cost, tokens in rows:
        table.add_row(period, _fmt_cost(cost), f"[cyan]{_fmt_tokens(tokens)}[/cyan]")

    return Panel(table, title="[bold]Cost Summary[/bold]", border_style="blue", padding=(0, 1))


def build_projects_table(result: AnalysisResult, top_n: int = 10) -> Table:
    projects = sorted(result.by_project.values(), key=lambda p: p.cost_usd, reverse=True)[:top_n]

    table = Table(
        title="[bold]Projects[/bold]",
        box=box.SIMPLE_HEAD,
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
    )
    table.add_column("Project", min_width=18)
    table.add_column("Sessions", justify="right")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Cache↑", justify="right")
    table.add_column("Cache↓", justify="right")
    table.add_column("Cost", justify="right")

    for p in projects:
        table.add_row(
            f"[bold]{escape(p.project_name)}[/bold]",
            str(p.sessions),
            _fmt_tokens(p.input_tokens),
            _fmt_tokens(p.output_tokens),
            _fmt_tokens(p.cache_write_tokens),
            _fmt_tokens(p.cache_read_tokens),
            _fmt_cost(p.cost_usd),
        )

    return table


def build_daily_table(result: AnalysisResult, days: int = 7) -> Table:
    today = date.today()
    dates = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]

    table = Table(
        title=f"[bold]Last {days} Days[/bold]",
        box=box.SIMPLE_HEAD,
        border_style="bright_black",
        header_style="bold cyan",
    )
    table.add_column("Date")
    table.add_column("Sessions", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Trend", justify="left")
    table.add_column("Cost", justify="right")

    daily_costs = [result.by_day.get(d, DailySummary(date=d)).cost_usd for d in dates]
    sparkline_data = daily_costs

    for i, d in enumerate(dates):
        summary = result.by_day.get(d, DailySummary(date=d))
        label = "Today" if d == today else d.strftime("%a %b %d")
        style = "bold" if d == today else ""
        spark = _sparkline(sparkline_data[: i + 1])
        table.add_row(
            f"[{style}]{label}[/{style}]" if style else label,
            str(summary.sessions) if summary.sessions else "[dim]—[/dim]",
            _fmt_tokens(summary.total_tokens) if summary.total_tokens else "[dim]—[/dim]",
            f"[bright_black]{spark}[/bright_black]",
            _fmt_cost(summary.cost_usd) if summary.cost_usd else "[dim]—[/dim]",
        )

    return table


def build_waste_table(sessions: list[SessionStats], n: int = 10) -> Table:
    table = Table(
        title="[bold]Top Wasteful Sessions[/bold]  [dim](high context : low output)[/dim]",
        box=box.SIMPLE_HEAD,
        border_style="bright_black",
        header_style="bold cyan",
    )
    table.add_column("Project")
    table.add_column("Date")
    table.add_column("Input+Cache↓", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Ratio", justify="right")
    table.add_column("Cost", justify="right")

    for s in sessions[:n]:
        ratio = s.waste_ratio
        ratio_str = f"{ratio:.0f}x"
        color = _HOT_COLOR if ratio > 100 else _WARN_COLOR if ratio > 30 else "white"
        date_str = s.start_time.strftime("%b %d") if s.start_time else "—"
        table.add_row(
            escape(s.project_name),
            date_str,
            _fmt_tokens(s.input_tokens + s.cache_read_tokens),
            _fmt_tokens(s.output_tokens),
            f"[{color}]{ratio_str}[/{color}]",
            _fmt_cost(s.cost_usd),
        )

    return table


def render_dashboard(result: AnalysisResult) -> None:

    console.clear()
    now = datetime.now().strftime("%H:%M:%S")
    console.print(
        Panel(
            f"[bold cyan]tokenwise[/bold cyan]  [dim]last updated {now}[/dim]",
            border_style="bright_black",
            padding=(0, 1),
        )
    )
    console.print(build_summary_panel(result))
    console.print()
    console.print(build_projects_table(result))
    console.print()
    console.print(build_daily_table(result))


def live_dashboard(loader: Callable[[], AnalysisResult], refresh_seconds: int = 5) -> None:
    try:
        while True:
            result = loader()
            render_dashboard(result)
            time.sleep(refresh_seconds)
            console.clear()
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye.[/dim]")
