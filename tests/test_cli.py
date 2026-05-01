"""Tests for the CLI commands."""

from datetime import date, datetime

import pytest
from click.testing import CliRunner

from tokenwise.analyzer import AnalysisResult, DailySummary, ProjectStats, SessionStats
from tokenwise.cli import main


# ---------------------------------------------------------------------------
# Shared fixture: a minimal AnalysisResult that all commands can use
# ---------------------------------------------------------------------------


def _make_stats(
    session_id: str = "sess-1",
    project_name: str = "myproject",
    project_slug: str = "-Users-test-myproject",
    start_time: datetime | None = None,
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_write: int = 500,
    cache_read: int = 800,
    cost: float = 0.05,
) -> SessionStats:
    return SessionStats(
        session_id=session_id,
        project_slug=project_slug,
        project_name=project_name,
        model="claude-sonnet-4-6",
        start_time=start_time or datetime(2026, 4, 15, 10, 0, 0),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_write_tokens=cache_write,
        cache_read_tokens=cache_read,
        cost_usd=cost,
        turns=2,
    )


@pytest.fixture()
def sample_result() -> AnalysisResult:
    today = date.today()
    stats = _make_stats(start_time=datetime(today.year, today.month, today.day, 10, 0, 0))
    proj = ProjectStats(
        project_name="myproject",
        project_slug="-Users-test-myproject",
        sessions=1,
        input_tokens=1000,
        output_tokens=200,
        cache_write_tokens=500,
        cache_read_tokens=800,
        cost_usd=0.05,
    )
    daily = DailySummary(date=today, sessions=1, cost_usd=0.05, input_tokens=1000)
    return AnalysisResult(
        all_sessions=[stats],
        by_project={"-Users-test-myproject": proj},
        by_day={today: daily},
        total_cost_usd=0.05,
        total_tokens=2500,
    )


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# today command
# ---------------------------------------------------------------------------


def test_today_command_exits_zero(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["today"])
    assert result.exit_code == 0


def test_today_command_shows_cost_summary(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["today"])
    assert "Cost Summary" in result.output or result.exit_code == 0


# ---------------------------------------------------------------------------
# week command
# ---------------------------------------------------------------------------


def test_week_command_exits_zero(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["week"])
    assert result.exit_code == 0


def test_week_command_shows_output(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["week"])
    assert result.exit_code == 0
    assert len(result.output) > 0


# ---------------------------------------------------------------------------
# waste command
# ---------------------------------------------------------------------------


def test_waste_command_exits_zero(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["waste"])
    assert result.exit_code == 0


def test_waste_command_with_custom_top(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["waste", "--top", "5"])
    assert result.exit_code == 0


def test_waste_command_empty_sessions(runner, monkeypatch):
    empty = AnalysisResult(
        all_sessions=[], by_project={}, by_day={}, total_cost_usd=0.0, total_tokens=0
    )
    monkeypatch.setattr("tokenwise.cli._load", lambda: empty)
    result = runner.invoke(main, ["waste"])
    assert result.exit_code == 0
    assert "No wasteful sessions" in result.output


# ---------------------------------------------------------------------------
# export command
# ---------------------------------------------------------------------------


def test_export_command_table_exits_zero(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["export"])
    assert result.exit_code == 0


def test_export_command_csv_format(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["export", "--csv"])
    assert result.exit_code == 0
    assert "date,project,session_id" in result.output


def test_export_csv_contains_session_data(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["export", "--csv"])
    assert "myproject" in result.output
    assert "claude-sonnet-4-6" in result.output


# ---------------------------------------------------------------------------
# project command
# ---------------------------------------------------------------------------


def test_project_command_found(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["project", "myproject"])
    assert result.exit_code == 0


def test_project_command_partial_match(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["project", "my"])
    assert result.exit_code == 0


def test_project_command_not_found_exits_one(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["project", "nonexistent-xyz"])
    assert result.exit_code == 1


def test_project_command_not_found_shows_available(runner, sample_result, monkeypatch):
    monkeypatch.setattr("tokenwise.cli._load", lambda: sample_result)
    result = runner.invoke(main, ["project", "nonexistent-xyz"])
    assert "myproject" in result.output


# ---------------------------------------------------------------------------
# update-prices command
# ---------------------------------------------------------------------------


def test_update_prices_command(runner):
    result = runner.invoke(main, ["update-prices"])
    assert result.exit_code == 0
    assert "not yet implemented" in result.output


# ---------------------------------------------------------------------------
# _load — CLAUDE_PROJECTS_DIR missing
# ---------------------------------------------------------------------------


def test_load_exits_when_projects_dir_missing(runner, monkeypatch, tmp_path):
    missing = tmp_path / "nonexistent"
    monkeypatch.setattr("tokenwise.cli.CLAUDE_PROJECTS_DIR", missing)
    result = runner.invoke(main, ["today"])
    assert result.exit_code == 1
