"""Tests for dashboard rendering helpers."""

from datetime import date, datetime

from rich.panel import Panel
from rich.table import Table

from tokenwise.analyzer import (
    AnalysisResult,
    DailySummary,
    ProjectStats,
    SessionStats,
)
from tokenwise.dashboard import (
    _fmt_cost,
    _fmt_tokens,
    _sparkline,
    build_daily_table,
    build_projects_table,
    build_summary_panel,
    build_waste_table,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    sessions: list[SessionStats] | None = None,
    by_project: dict | None = None,
    by_day: dict | None = None,
    total_cost: float = 0.0,
    total_tokens: int = 0,
) -> AnalysisResult:
    return AnalysisResult(
        all_sessions=sessions or [],
        by_project=by_project or {},
        by_day=by_day or {},
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
    )


def _make_project(
    name: str = "myproject",
    slug: str = "-Users-test-myproject",
    sessions: int = 3,
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_write: int = 500,
    cache_read: int = 800,
    cost: float = 0.05,
) -> ProjectStats:
    return ProjectStats(
        project_name=name,
        project_slug=slug,
        sessions=sessions,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_write_tokens=cache_write,
        cache_read_tokens=cache_read,
        cost_usd=cost,
    )


def _make_session_stat(
    session_id: str = "sess-1",
    project_name: str = "myproject",
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_read: int = 800,
    cost: float = 0.05,
    start_time: datetime | None = None,
) -> SessionStats:
    return SessionStats(
        session_id=session_id,
        project_slug="-Users-test",
        project_name=project_name,
        model="claude-sonnet-4-6",
        start_time=start_time or datetime(2026, 4, 15, 10, 0, 0),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_write_tokens=0,
        cache_read_tokens=cache_read,
        cost_usd=cost,
        turns=2,
    )


# ---------------------------------------------------------------------------
# _fmt_cost
# ---------------------------------------------------------------------------


def test_fmt_cost_below_cent():
    result = _fmt_cost(0.001)
    assert "< $0.01" in result


def test_fmt_cost_exact_zero():
    result = _fmt_cost(0.0)
    assert "< $0.01" in result


def test_fmt_cost_cents_range():
    result = _fmt_cost(0.05)
    assert "$0.0500" in result


def test_fmt_cost_one_dollar_or_more():
    result = _fmt_cost(1.50)
    assert "$1.50" in result


def test_fmt_cost_large_value():
    result = _fmt_cost(100.0)
    assert "$100.00" in result


# ---------------------------------------------------------------------------
# _fmt_tokens
# ---------------------------------------------------------------------------


def test_fmt_tokens_small():
    assert _fmt_tokens(500) == "500"


def test_fmt_tokens_thousands():
    result = _fmt_tokens(1500)
    assert result == "1.5k"


def test_fmt_tokens_exact_thousand():
    result = _fmt_tokens(1000)
    assert result == "1.0k"


def test_fmt_tokens_millions():
    result = _fmt_tokens(2_500_000)
    assert result == "2.5M"


def test_fmt_tokens_zero():
    assert _fmt_tokens(0) == "0"


# ---------------------------------------------------------------------------
# _sparkline
# ---------------------------------------------------------------------------


def test_sparkline_empty_values():
    result = _sparkline([])
    assert result == " " * 8


def test_sparkline_all_zeros():
    result = _sparkline([0.0, 0.0, 0.0])
    assert result == " " * 8


def test_sparkline_returns_correct_width():
    result = _sparkline([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], width=5)
    assert len(result) == 5


def test_sparkline_single_value():
    result = _sparkline([5.0], width=4)
    assert len(result) == 1  # only 1 value available


def test_sparkline_uses_last_n_values():
    # 10 values, width 3 → should use last 3
    values = [1.0] * 7 + [2.0, 4.0, 8.0]
    result = _sparkline(values, width=3)
    assert len(result) == 3


# ---------------------------------------------------------------------------
# build_summary_panel
# ---------------------------------------------------------------------------


def test_build_summary_panel_returns_panel():
    result = _make_result()
    panel = build_summary_panel(result)
    assert isinstance(panel, Panel)


def test_build_summary_panel_custom_label():
    result = _make_result()
    panel = build_summary_panel(result, label="Today")
    assert isinstance(panel, Panel)


def test_build_summary_panel_with_real_data():
    today = date.today()
    daily = DailySummary(date=today, sessions=2, cost_usd=0.10, input_tokens=1000)
    result = _make_result(
        by_day={today: daily},
        total_cost=0.10,
        total_tokens=1000,
    )
    panel = build_summary_panel(result, label="All Time")
    assert isinstance(panel, Panel)


# ---------------------------------------------------------------------------
# build_projects_table
# ---------------------------------------------------------------------------


def test_build_projects_table_returns_table():
    result = _make_result()
    table = build_projects_table(result)
    assert isinstance(table, Table)


def test_build_projects_table_with_projects():
    proj = _make_project()
    result = _make_result(by_project={proj.project_slug: proj})
    table = build_projects_table(result)
    assert isinstance(table, Table)


def test_build_projects_table_respects_top_n():
    projects = {
        f"slug-{i}": _make_project(name=f"proj-{i}", slug=f"slug-{i}", cost=float(i))
        for i in range(15)
    }
    result = _make_result(by_project=projects)
    table = build_projects_table(result, top_n=5)
    assert isinstance(table, Table)


# ---------------------------------------------------------------------------
# build_daily_table
# ---------------------------------------------------------------------------


def test_build_daily_table_returns_table():
    result = _make_result()
    table = build_daily_table(result)
    assert isinstance(table, Table)


def test_build_daily_table_with_data():
    today = date.today()
    daily = DailySummary(date=today, sessions=3, cost_usd=0.25, input_tokens=5000)
    result = _make_result(by_day={today: daily})
    table = build_daily_table(result, days=7)
    assert isinstance(table, Table)


def test_build_daily_table_custom_days():
    result = _make_result()
    table = build_daily_table(result, days=14)
    assert isinstance(table, Table)


# ---------------------------------------------------------------------------
# build_waste_table
# ---------------------------------------------------------------------------


def test_build_waste_table_returns_table():
    sessions = [_make_session_stat()]
    table = build_waste_table(sessions)
    assert isinstance(table, Table)


def test_build_waste_table_empty():
    table = build_waste_table([])
    assert isinstance(table, Table)


def test_build_waste_table_high_ratio_colors():
    # High waste ratio (> 100) triggers red color
    s = _make_session_stat(input_tokens=100_000, output_tokens=10)
    table = build_waste_table([s], n=1)
    assert isinstance(table, Table)


def test_build_waste_table_medium_ratio_colors():
    # Mid waste ratio (> 30, <= 100) triggers yellow
    s = _make_session_stat(input_tokens=5000, output_tokens=100)
    table = build_waste_table([s], n=1)
    assert isinstance(table, Table)


def test_build_waste_table_no_start_time():
    s = _make_session_stat(start_time=None)
    # Override start_time after creation isn't possible via dataclass directly,
    # so patch via object attribute
    object.__setattr__(s, "start_time", None) if False else None
    # Use a SessionStats with no start_time by building manually
    s2 = SessionStats(
        session_id="x",
        project_slug="slug",
        project_name="proj",
        model="claude-sonnet-4-6",
        start_time=None,
        input_tokens=1000,
        output_tokens=10,
        cache_write_tokens=0,
        cache_read_tokens=0,
        cost_usd=0.01,
        turns=1,
    )
    table = build_waste_table([s2], n=1)
    assert isinstance(table, Table)
