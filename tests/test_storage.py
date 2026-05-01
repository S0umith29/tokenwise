"""Tests for the storage / cache module."""

import json
import stat

import pytest

import tokenwise.security as _sec
import tokenwise.storage as storage


@pytest.fixture()
def fake_cache(tmp_path, monkeypatch):
    """Redirect all cache paths to tmp_path so tests never touch ~/.tokenwise."""
    cache_dir = tmp_path / ".tokenwise"
    cache_file = cache_dir / "cache.json"
    monkeypatch.setattr(storage, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(storage, "CACHE_FILE", cache_file)
    monkeypatch.setattr(_sec, "_ALLOWED_WRITE_ROOTS", (cache_dir,))
    return cache_dir, cache_file


# ---------------------------------------------------------------------------
# load_cache
# ---------------------------------------------------------------------------


def test_load_cache_returns_empty_dict_when_file_missing(fake_cache):
    result = storage.load_cache()
    assert result == {}


def test_load_cache_returns_data_from_valid_json(fake_cache):
    cache_dir, cache_file = fake_cache
    cache_dir.mkdir(parents=True)
    cache_file.write_text('{"mtimes": {"a": 1.0}}', encoding="utf-8")
    result = storage.load_cache()
    assert result == {"mtimes": {"a": 1.0}}


def test_load_cache_returns_empty_on_corrupt_json(fake_cache):
    cache_dir, cache_file = fake_cache
    cache_dir.mkdir(parents=True)
    cache_file.write_text("{not valid json!!}", encoding="utf-8")
    result = storage.load_cache()
    assert result == {}


def test_load_cache_returns_empty_on_oserror(fake_cache, monkeypatch):
    cache_dir, cache_file = fake_cache
    cache_dir.mkdir(parents=True)
    cache_file.write_text("{}", encoding="utf-8")

    original_open = open

    def bad_open(path, *args, **kwargs):
        if str(path) == str(cache_file):
            raise OSError("simulated read error")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", bad_open)
    result = storage.load_cache()
    assert result == {}


# ---------------------------------------------------------------------------
# save_cache
# ---------------------------------------------------------------------------


def test_save_cache_creates_file_with_correct_data(fake_cache):
    storage.save_cache({"hello": "world", "count": 42})
    _, cache_file = fake_cache
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data == {"hello": "world", "count": 42}


def test_save_cache_sets_file_permissions_600(fake_cache):
    storage.save_cache({"x": 1})
    _, cache_file = fake_cache
    mode = stat.S_IMODE(cache_file.stat().st_mode)
    assert mode == 0o600


def test_save_cache_creates_directory_with_700(fake_cache):
    cache_dir, _ = fake_cache
    storage.save_cache({})
    mode = stat.S_IMODE(cache_dir.stat().st_mode)
    assert mode == 0o700


def test_save_then_load_roundtrip(fake_cache):
    data = {"mtimes": {"/some/path.jsonl": 1234567890.0}}
    storage.save_cache(data)
    loaded = storage.load_cache()
    assert loaded == data


# ---------------------------------------------------------------------------
# get_file_mtime
# ---------------------------------------------------------------------------


def test_get_file_mtime_returns_positive_for_existing_file(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text("data")
    mtime = storage.get_file_mtime(f)
    assert mtime > 0.0


def test_get_file_mtime_returns_zero_for_missing_file(tmp_path):
    mtime = storage.get_file_mtime(tmp_path / "nonexistent.jsonl")
    assert mtime == 0.0


# ---------------------------------------------------------------------------
# is_cache_valid
# ---------------------------------------------------------------------------


def test_is_cache_valid_true_when_mtime_matches(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text("data")
    current_mtime = storage.get_file_mtime(f)
    cache = {"mtimes": {str(f): current_mtime}}
    assert storage.is_cache_valid(cache, f) is True


def test_is_cache_valid_false_when_mtime_stale(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text("data")
    cache = {"mtimes": {str(f): 0.0}}
    assert storage.is_cache_valid(cache, f) is False


def test_is_cache_valid_false_when_key_absent(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text("data")
    assert storage.is_cache_valid({}, f) is False


def test_is_cache_valid_false_when_mtimes_key_absent(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text("data")
    assert storage.is_cache_valid({"other": {}}, f) is False


# ---------------------------------------------------------------------------
# update_cache_mtime
# ---------------------------------------------------------------------------


def test_update_cache_mtime_sets_correct_value(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text("data")
    cache: dict = {}
    storage.update_cache_mtime(cache, f)
    assert cache["mtimes"][str(f)] == storage.get_file_mtime(f)


def test_update_cache_mtime_overwrites_stale_value(tmp_path):
    f = tmp_path / "session.jsonl"
    f.write_text("data")
    cache = {"mtimes": {str(f): 0.0}}
    storage.update_cache_mtime(cache, f)
    assert cache["mtimes"][str(f)] == storage.get_file_mtime(f)
