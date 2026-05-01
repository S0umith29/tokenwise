"""Tests for the JSONL parser using fixture data."""

import json
from pathlib import Path

import pytest

import tokenwise.security as _sec
from tokenwise.parser import parse_all_sessions, parse_session

# ---------------------------------------------------------------------------
# Shared fixture: redirect allowed read roots to tmp_path so safe_read_path
# doesn't reject our test JSONL files.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def allow_tmp_reads(tmp_path, monkeypatch):
    """Patch security allowed roots so parser tests can use tmp_path."""
    monkeypatch.setattr(_sec, "_ALLOWED_READ_ROOTS", (tmp_path,))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(tmp_path: Path, slug: str, lines: list[dict]) -> Path:
    session_id = "aaaabbbb-0000-1111-2222-333344445555"
    proj_dir = tmp_path / slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    path = proj_dir / f"{session_id}.jsonl"
    with open(path, "w") as f:
        for obj in lines:
            f.write(json.dumps(obj) + "\n")
    return path


SAMPLE_USER_MSG = {
    "type": "user",
    "uuid": "user-uuid-1",
    "sessionId": "aaaabbbb-0000-1111-2222-333344445555",
    "timestamp": "2026-04-15T10:00:00.000Z",
    "cwd": "/Users/test/myproject",
    "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]},
}

SAMPLE_ASSISTANT_MSG = {
    "type": "assistant",
    "uuid": "asst-uuid-1",
    "sessionId": "aaaabbbb-0000-1111-2222-333344445555",
    "timestamp": "2026-04-15T10:00:05.000Z",
    "message": {
        "role": "assistant",
        "model": "claude-sonnet-4-6",
        "content": [{"type": "text", "text": "Hello there!"}],
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "cache_creation_input_tokens": 5000,
            "cache_read_input_tokens": 8000,
        },
    },
}

SYNTHETIC_ASSISTANT_MSG = {
    "type": "assistant",
    "uuid": "asst-uuid-synth",
    "sessionId": "aaaabbbb-0000-1111-2222-333344445555",
    "timestamp": "2026-04-15T10:00:10.000Z",
    "message": {
        "role": "assistant",
        "model": "<synthetic>",
        "content": [],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    },
}


# ---------------------------------------------------------------------------
# Test 1: parse a simple session with one real turn
# ---------------------------------------------------------------------------


def test_parse_single_turn(tmp_path):
    path = _write_jsonl(
        tmp_path,
        "-Users-test-myproject",
        [SAMPLE_USER_MSG, SAMPLE_ASSISTANT_MSG],
    )
    session = parse_session(path, "-Users-test-myproject")

    assert len(session.turns) == 1
    turn = session.turns[0]
    assert turn.model == "claude-sonnet-4-6"
    assert turn.usage.input_tokens == 1000
    assert turn.usage.output_tokens == 200
    assert turn.usage.cache_creation_input_tokens == 5000
    assert turn.usage.cache_read_input_tokens == 8000


# ---------------------------------------------------------------------------
# Test 2: synthetic / zero-token turns are excluded
# ---------------------------------------------------------------------------


def test_synthetic_turns_excluded(tmp_path):
    path = _write_jsonl(
        tmp_path,
        "-Users-test-myproject",
        [SAMPLE_USER_MSG, SYNTHETIC_ASSISTANT_MSG, SAMPLE_ASSISTANT_MSG],
    )
    session = parse_session(path, "-Users-test-myproject")

    assert len(session.turns) == 1
    assert session.turns[0].model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Test 3: project_path extracted from cwd field
# ---------------------------------------------------------------------------


def test_project_path_from_cwd(tmp_path):
    path = _write_jsonl(
        tmp_path,
        "-Users-test-myproject",
        [SAMPLE_USER_MSG, SAMPLE_ASSISTANT_MSG],
    )
    session = parse_session(path, "-Users-test-myproject")

    assert session.project_path == "/Users/test/myproject"
    assert session.project_name == "myproject"


# ---------------------------------------------------------------------------
# Test 4: aggregate token counts are correct
# ---------------------------------------------------------------------------


def test_aggregate_token_counts(tmp_path):
    second_turn = {
        **SAMPLE_ASSISTANT_MSG,
        "uuid": "asst-uuid-2",
        "timestamp": "2026-04-15T10:01:00.000Z",
        "message": {
            **SAMPLE_ASSISTANT_MSG["message"],
            "usage": {
                "input_tokens": 500,
                "output_tokens": 100,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 4000,
            },
        },
    }
    path = _write_jsonl(
        tmp_path,
        "-Users-test-myproject",
        [SAMPLE_USER_MSG, SAMPLE_ASSISTANT_MSG, second_turn],
    )
    session = parse_session(path, "-Users-test-myproject")

    assert len(session.turns) == 2
    assert session.total_input == 1500
    assert session.total_output == 300
    assert session.total_cache_write == 5000
    assert session.total_cache_read == 12000


# ---------------------------------------------------------------------------
# Test 5: empty project directory yields no sessions
# ---------------------------------------------------------------------------


def test_empty_projects_dir(tmp_path):
    (tmp_path / "empty-project").mkdir()
    sessions = parse_all_sessions(tmp_path)
    assert sessions == []


# ---------------------------------------------------------------------------
# Test 6: parse_all_sessions ignores non-jsonl files
# ---------------------------------------------------------------------------


def test_non_jsonl_files_ignored(tmp_path):
    proj_dir = tmp_path / "-Users-test-proj"
    proj_dir.mkdir()
    (proj_dir / "memory").write_text("not a session file")
    (proj_dir / "notes.txt").write_text("also not a session")

    _write_jsonl(tmp_path, "-Users-test-proj", [SAMPLE_USER_MSG, SAMPLE_ASSISTANT_MSG])
    sessions = parse_all_sessions(tmp_path)

    assert len(sessions) == 1
    assert sessions[0].project_name == "myproject"


# ---------------------------------------------------------------------------
# Test 7: malformed JSON lines are skipped gracefully
# ---------------------------------------------------------------------------


def test_malformed_lines_skipped(tmp_path):
    proj_dir = tmp_path / "-Users-test-bad"
    proj_dir.mkdir()
    path = proj_dir / "aaaabbbb-0000-1111-2222-333344445555.jsonl"
    with open(path, "w") as f:
        f.write("this is not json\n")
        f.write(json.dumps(SAMPLE_USER_MSG) + "\n")
        f.write("{broken\n")
        f.write(json.dumps(SAMPLE_ASSISTANT_MSG) + "\n")

    session = parse_session(path, "-Users-test-bad")
    assert len(session.turns) == 1
