from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from .parser import Session
from .pricing import compute_cost


@dataclass
class SessionStats:
    session_id: str
    project_slug: str
    project_name: str
    model: str
    start_time: datetime | None
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_usd: float
    turns: int

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )

    @property
    def waste_ratio(self) -> float:
        """High ratio = lots of context for little output (potentially wasteful)."""
        if self.output_tokens == 0:
            return 0.0
        return (self.input_tokens + self.cache_read_tokens) / max(self.output_tokens, 1)


@dataclass
class ProjectStats:
    project_name: str
    project_slug: str
    sessions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )


@dataclass
class DailySummary:
    date: date
    sessions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )


@dataclass
class AnalysisResult:
    all_sessions: list[SessionStats]
    by_project: dict[str, ProjectStats]
    by_day: dict[date, DailySummary]
    total_cost_usd: float
    total_tokens: int


def _session_to_stats(session: Session) -> SessionStats:
    model = session.primary_model
    cost = compute_cost(
        model,
        session.total_input,
        session.total_output,
        session.total_cache_write,
        session.total_cache_read,
    )
    return SessionStats(
        session_id=session.session_id,
        project_slug=session.project_slug,
        project_name=session.project_name,
        model=model,
        start_time=session.start_time,
        input_tokens=session.total_input,
        output_tokens=session.total_output,
        cache_write_tokens=session.total_cache_write,
        cache_read_tokens=session.total_cache_read,
        cost_usd=cost,
        turns=len(session.turns),
    )


def analyze(sessions: list[Session]) -> AnalysisResult:
    all_stats: list[SessionStats] = []
    by_project: dict[str, ProjectStats] = {}
    by_day: dict[date, DailySummary] = {}

    for session in sessions:
        stats = _session_to_stats(session)
        all_stats.append(stats)

        # Per-project
        key = stats.project_slug
        if key not in by_project:
            by_project[key] = ProjectStats(
                project_name=stats.project_name,
                project_slug=stats.project_slug,
            )
        p = by_project[key]
        p.sessions += 1
        p.input_tokens += stats.input_tokens
        p.output_tokens += stats.output_tokens
        p.cache_write_tokens += stats.cache_write_tokens
        p.cache_read_tokens += stats.cache_read_tokens
        p.cost_usd += stats.cost_usd

        # Per-day
        if stats.start_time:
            day = stats.start_time.astimezone(timezone.utc).date()
            if day not in by_day:
                by_day[day] = DailySummary(date=day)
            d = by_day[day]
            d.sessions += 1
            d.input_tokens += stats.input_tokens
            d.output_tokens += stats.output_tokens
            d.cache_write_tokens += stats.cache_write_tokens
            d.cache_read_tokens += stats.cache_read_tokens
            d.cost_usd += stats.cost_usd

    total_cost = sum(s.cost_usd for s in all_stats)
    total_tokens = sum(s.total_tokens for s in all_stats)

    return AnalysisResult(
        all_sessions=all_stats,
        by_project=by_project,
        by_day=by_day,
        total_cost_usd=total_cost,
        total_tokens=total_tokens,
    )


def filter_by_date_range(
    result: AnalysisResult,
    start: date,
    end: date,
) -> AnalysisResult:
    filtered = [
        s
        for s in result.all_sessions
        if s.start_time and start <= s.start_time.astimezone(timezone.utc).date() <= end
    ]

    # Re-aggregate from filtered sessions
    by_project: dict[str, ProjectStats] = {}
    by_day: dict[date, DailySummary] = {}

    for stats in filtered:
        key = stats.project_slug
        if key not in by_project:
            by_project[key] = ProjectStats(
                project_name=stats.project_name,
                project_slug=stats.project_slug,
            )
        p = by_project[key]
        p.sessions += 1
        p.input_tokens += stats.input_tokens
        p.output_tokens += stats.output_tokens
        p.cache_write_tokens += stats.cache_write_tokens
        p.cache_read_tokens += stats.cache_read_tokens
        p.cost_usd += stats.cost_usd

        if stats.start_time:
            day = stats.start_time.astimezone(timezone.utc).date()
            if day not in by_day:
                by_day[day] = DailySummary(date=day)
            d = by_day[day]
            d.sessions += 1
            d.input_tokens += stats.input_tokens
            d.output_tokens += stats.output_tokens
            d.cache_write_tokens += stats.cache_write_tokens
            d.cache_read_tokens += stats.cache_read_tokens
            d.cost_usd += stats.cost_usd

    return AnalysisResult(
        all_sessions=filtered,
        by_project=by_project,
        by_day=by_day,
        total_cost_usd=sum(s.cost_usd for s in filtered),
        total_tokens=sum(s.total_tokens for s in filtered),
    )


def top_wasteful_sessions(result: AnalysisResult, n: int = 10) -> list[SessionStats]:
    return sorted(result.all_sessions, key=lambda s: s.waste_ratio, reverse=True)[:n]
