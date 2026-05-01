from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .security import open_readonly, safe_read_path

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class AssistantTurn(BaseModel):
    uuid: str
    session_id: str
    project_slug: str
    timestamp: datetime
    model: str
    usage: TokenUsage


class Session(BaseModel):
    session_id: str
    project_slug: str
    project_path: str = ""  # real path from cwd field on user messages
    turns: list[AssistantTurn] = Field(default_factory=list)

    @property
    def project_name(self) -> str:
        if self.project_path:
            return Path(self.project_path).name
        # Fallback: last dash-separated token of slug
        return self.project_slug.rstrip("-").rsplit("-", 1)[-1] or self.project_slug

    @property
    def start_time(self) -> datetime | None:
        return self.turns[0].timestamp if self.turns else None

    @property
    def end_time(self) -> datetime | None:
        return self.turns[-1].timestamp if self.turns else None

    @property
    def total_input(self) -> int:
        return sum(t.usage.input_tokens for t in self.turns)

    @property
    def total_output(self) -> int:
        return sum(t.usage.output_tokens for t in self.turns)

    @property
    def total_cache_write(self) -> int:
        return sum(t.usage.cache_creation_input_tokens for t in self.turns)

    @property
    def total_cache_read(self) -> int:
        return sum(t.usage.cache_read_input_tokens for t in self.turns)

    @property
    def total_tokens(self) -> int:
        return self.total_input + self.total_output + self.total_cache_write + self.total_cache_read

    @property
    def primary_model(self) -> str:
        if not self.turns:
            return "unknown"
        counts: dict[str, int] = {}
        for t in self.turns:
            if t.model and t.model != "<synthetic>":
                counts[t.model] = counts.get(t.model, 0) + 1
        return max(counts, key=lambda m: counts[m]) if counts else "unknown"


def _parse_jsonl(path: Path) -> Iterator[dict]:
    safe_read_path(path)  # path-safety guard — raises if path escapes allowed roots
    with open_readonly(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def parse_session(jsonl_path: Path, project_slug: str) -> Session:
    session_id = jsonl_path.stem
    session = Session(session_id=session_id, project_slug=project_slug)

    for record in _parse_jsonl(jsonl_path):
        rtype = record.get("type")

        # Pick up real working directory from any user message
        if rtype == "user" and not session.project_path:
            cwd = record.get("cwd", "")
            if cwd:
                session.project_path = cwd

        elif rtype == "assistant":
            msg = record.get("message", {})
            raw_usage = msg.get("usage")
            model = msg.get("model", "")

            # Skip synthetic/empty turns
            if not raw_usage or model == "<synthetic>":
                continue

            # Skip if all counts are zero
            input_tok = raw_usage.get("input_tokens", 0) or 0
            output_tok = raw_usage.get("output_tokens", 0) or 0
            cache_create = raw_usage.get("cache_creation_input_tokens", 0) or 0
            cache_read = raw_usage.get("cache_read_input_tokens", 0) or 0

            if input_tok == output_tok == cache_create == cache_read == 0:
                continue

            ts_str = record.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ts = datetime.now(tz=timezone.utc)

            turn = AssistantTurn(
                uuid=record.get("uuid", ""),
                session_id=session_id,
                project_slug=project_slug,
                timestamp=ts,
                model=model,
                usage=TokenUsage(
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    cache_creation_input_tokens=cache_create,
                    cache_read_input_tokens=cache_read,
                ),
            )
            session.turns.append(turn)

    return session


def parse_all_sessions(projects_dir: Path | None = None) -> list[Session]:
    root = projects_dir or CLAUDE_PROJECTS_DIR
    if not root.exists():
        return []

    sessions: list[Session] = []
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir():
            continue
        slug = project_dir.name
        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            session = parse_session(jsonl_file, slug)
            if session.turns:  # skip empty sessions
                sessions.append(session)

    return sessions
