"""Tests for the analyzer module."""

from datetime import date, datetime, timezone

import pytest

from tokenwise.analyzer import (
    AnalysisResult,
    DailySummary,
    ProjectStats,
    SessionStats,
    analyze,
    filter_by_date_range,
    top_wasteful_sessions,
)
from tokenwise.parser import AssistantTurn, Session, TokenUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _make_turn(
    model: str = "claude-sonnet-4-6",
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_write: int = 500,
    cache_read: int = 800,
    timestamp: str = "2026-04-15T10:00:00Z",
) -> AssistantTurn:
    return AssistantTurn(
        uuid="test-uuid",
        session_id="sess-1",
        project_slug="-Users-test-myproject",
        timestamp=_ts(timestamp),
        model=model,
        usage=TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_write,
            cache_read_input_tokens=cache_read,
        ),
    )


def _make_session(
    session_id: str = "sess-1",
    slug: str = "-Users-test-myproject",
    project_path: str = "/Users/test/myproject",
    turns: list[AssistantTurn] | None = None,
) -> Session:
    return Session(
        session_id=session_id,
        project_slug=slug,
        project_path=project_path,
        turns=turns or [_make_turn()],
    )


# ---------------------------------------------------------------------------
# SessionStats properties
# ---------------------------------------------------------------------------


def test_session_stats_total_tokens():
    stats = SessionStats(
        session_id="s1",
        project_slug="slug",
        project_name="proj",
        model="claude-sonnet-4-6",
        start_time=None,
        input_tokens=1000,
        output_tokens=200,
        cache_write_tokens=500,
        cache_read_tokens=800,
        cost_usd=0.01,
        turns=1,
    )
    assert stats.total_tokens == 2500


def test_session_stats_waste_ratio_normal():
    stats = SessionStats(
        session_id="s1",
        project_slug="slug",
        project_name="proj",
        model="claude-sonnet-4-6",
        start_time=None,
        input_tokens=1000,
        output_tokens=100,
        cache_write_tokens=0,
        cache_read_tokens=500,
        cost_usd=0.01,
        turns=1,
    )
    assert stats.waste_ratio == (1000 + 500) / 100


def test_session_stats_waste_ratio_zero_output():
    stats = SessionStats(
        session_id="s1",
        project_slug="slug",
        project_name="proj",
        model="claude-sonnet-4-6",
        start_time=None,
        input_tokens=1000,
        output_tokens=0,
        cache_write_tokens=0,
        cache_read_tokens=0,
        cost_usd=0.0,
        turns=0,
    )
    assert stats.waste_ratio == 0.0


# ---------------------------------------------------------------------------
# ProjectStats properties
# ---------------------------------------------------------------------------


def test_project_stats_total_tokens():
    p = ProjectStats(
        project_name="proj",
        project_slug="slug",
        input_tokens=100,
        output_tokens=200,
        cache_write_tokens=300,
        cache_read_tokens=400,
    )
    assert p.total_tokens == 1000


# ---------------------------------------------------------------------------
# DailySummary properties
# ---------------------------------------------------------------------------


def test_daily_summary_total_tokens():
    d = DailySummary(
        date=date(2026, 4, 15),
        input_tokens=100,
        output_tokens=200,
        cache_write_tokens=300,
        cache_read_tokens=400,
    )
    assert d.total_tokens == 1000


# ---------------------------------------------------------------------------
# analyze — empty input
# ---------------------------------------------------------------------------


def test_analyze_empty_sessions():
    result = analyze([])
    assert result.all_sessions == []
    assert result.by_project == {}
    assert result.by_day == {}
    assert result.total_cost_usd == 0.0
    assert result.total_tokens == 0


# ---------------------------------------------------------------------------
# analyze — single session
# ---------------------------------------------------------------------------


def test_analyze_single_session_produces_one_stat():
    session = _make_session()
    result = analyze([session])
    assert len(result.all_sessions) == 1
    stat = result.all_sessions[0]
    assert stat.model == "claude-sonnet-4-6"
    assert stat.input_tokens == 1000
    assert stat.output_tokens == 200
    assert stat.cache_write_tokens == 500
    assert stat.cache_read_tokens == 800
    assert stat.turns == 1


def test_analyze_single_session_populates_by_project():
    session = _make_session()
    result = analyze([session])
    assert "-Users-test-myproject" in result.by_project
    p = result.by_project["-Users-test-myproject"]
    assert p.sessions == 1
    assert p.input_tokens == 1000


def test_analyze_single_session_populates_by_day():
    session = _make_session()
    result = analyze([session])
    day = date(2026, 4, 15)
    assert day in result.by_day
    assert result.by_day[day].sessions == 1


def test_analyze_total_cost_is_positive():
    session = _make_session()
    result = analyze([session])
    assert result.total_cost_usd > 0


def test_analyze_total_tokens():
    session = _make_session()
    result = analyze([session])
    assert result.total_tokens == 1000 + 200 + 500 + 800


# ---------------------------------------------------------------------------
# analyze — multiple sessions, aggregation
# ---------------------------------------------------------------------------


def test_analyze_two_sessions_same_project_aggregates():
    s1 = _make_session(session_id="s1")
    s2 = _make_session(session_id="s2")
    result = analyze([s1, s2])
    p = result.by_project["-Users-test-myproject"]
    assert p.sessions == 2
    assert p.input_tokens == 2000


def test_analyze_two_sessions_different_projects():
    s1 = _make_session(session_id="s1", slug="-Users-a", project_path="/Users/a")
    s2 = _make_session(session_id="s2", slug="-Users-b", project_path="/Users/b")
    result = analyze([s1, s2])
    assert len(result.by_project) == 2


def test_analyze_session_without_start_time_skips_by_day():
    session = Session(
        session_id="empty",
        project_slug="-Users-test",
        project_path="/Users/test",
        turns=[],
    )
    result = analyze([session])
    assert result.by_day == {}


# ---------------------------------------------------------------------------
# filter_by_date_range
# ---------------------------------------------------------------------------


def test_filter_by_date_range_keeps_matching_session():
    session = _make_session()
    result = analyze([session])
    filtered = filter_by_date_range(result, date(2026, 4, 15), date(2026, 4, 15))
    assert len(filtered.all_sessions) == 1


def test_filter_by_date_range_excludes_outside_session():
    session = _make_session()
    result = analyze([session])
    filtered = filter_by_date_range(result, date(2026, 4, 1), date(2026, 4, 10))
    assert len(filtered.all_sessions) == 0
    assert filtered.total_cost_usd == 0.0
    assert filtered.total_tokens == 0


def test_filter_by_date_range_aggregates_by_project():
    s1 = _make_session(session_id="s1", turns=[_make_turn(timestamp="2026-04-15T10:00:00Z")])
    s2 = _make_session(session_id="s2", turns=[_make_turn(timestamp="2026-04-20T10:00:00Z")])
    result = analyze([s1, s2])
    filtered = filter_by_date_range(result, date(2026, 4, 15), date(2026, 4, 15))
    p = filtered.by_project["-Users-test-myproject"]
    assert p.sessions == 1


def test_filter_by_date_range_populates_by_day():
    session = _make_session()
    result = analyze([session])
    filtered = filter_by_date_range(result, date(2026, 4, 15), date(2026, 4, 15))
    assert date(2026, 4, 15) in filtered.by_day


# ---------------------------------------------------------------------------
# top_wasteful_sessions
# ---------------------------------------------------------------------------


def test_top_wasteful_sessions_returns_sorted_by_ratio():
    high_waste = SessionStats(
        session_id="s1",
        project_slug="slug",
        project_name="proj",
        model="claude-sonnet-4-6",
        start_time=None,
        input_tokens=10000,
        output_tokens=10,
        cache_write_tokens=0,
        cache_read_tokens=0,
        cost_usd=0.01,
        turns=1,
    )
    low_waste = SessionStats(
        session_id="s2",
        project_slug="slug",
        project_name="proj",
        model="claude-sonnet-4-6",
        start_time=None,
        input_tokens=100,
        output_tokens=100,
        cache_write_tokens=0,
        cache_read_tokens=0,
        cost_usd=0.001,
        turns=1,
    )
    result = AnalysisResult(
        all_sessions=[low_waste, high_waste],
        by_project={},
        by_day={},
        total_cost_usd=0.011,
        total_tokens=10210,
    )
    top = top_wasteful_sessions(result, n=2)
    assert top[0].session_id == "s1"
    assert top[1].session_id == "s2"


def test_top_wasteful_sessions_respects_n():
    sessions = [
        SessionStats(
            session_id=f"s{i}",
            project_slug="slug",
            project_name="proj",
            model="claude-sonnet-4-6",
            start_time=None,
            input_tokens=1000 * i,
            output_tokens=10,
            cache_write_tokens=0,
            cache_read_tokens=0,
            cost_usd=0.01,
            turns=1,
        )
        for i in range(1, 6)
    ]
    result = AnalysisResult(
        all_sessions=sessions,
        by_project={},
        by_day={},
        total_cost_usd=0.05,
        total_tokens=sum(s.total_tokens for s in sessions),
    )
    top = top_wasteful_sessions(result, n=3)
    assert len(top) == 3


def test_top_wasteful_sessions_empty():
    result = AnalysisResult(
        all_sessions=[], by_project={}, by_day={}, total_cost_usd=0.0, total_tokens=0
    )
    assert top_wasteful_sessions(result) == []
