"""Tests for the security guarantees documented in THREAT_MODEL.md."""

import io
import stat
import sys
from pathlib import Path

import pytest

from tokenwise.security import (
    assert_no_network_imports,
    ensure_cache_dir,
    open_readonly,
    safe_read_path,
    safe_write_path,
    set_cache_file_permissions,
)

# ---------------------------------------------------------------------------
# 1. No network imports in tokenwise source
# ---------------------------------------------------------------------------


def test_no_network_imports_passes_cleanly():
    """assert_no_network_imports() must not raise in normal operation."""
    assert_no_network_imports()  # should not raise


def test_no_network_modules_imported_by_tokenwise():
    """tokenwise source files must not import any network-capable modules."""
    forbidden = {"socket", "urllib", "requests", "httpx", "aiohttp", "http.client", "ssl"}
    set(sys.modules.keys())
    # Find which tokenwise modules are loaded
    tw_modules = {n for n in sys.modules if n.startswith("tokenwise.")}

    for mod_name in tw_modules:
        mod = sys.modules[mod_name]
        src_file = getattr(mod, "__file__", None) or ""
        if not src_file or not src_file.endswith(".py"):
            continue
        source = Path(src_file).read_text(encoding="utf-8")
        for net_mod in forbidden:
            # Direct import or from-import
            assert f"import {net_mod}" not in source, (
                f"tokenwise/{mod_name} imports network module '{net_mod}'"
            )
            assert f"from {net_mod}" not in source, (
                f"tokenwise/{mod_name} imports from network module '{net_mod}'"
            )


# ---------------------------------------------------------------------------
# 2. Path safety — safe_read_path
# ---------------------------------------------------------------------------


def test_safe_read_path_accepts_allowed_root(tmp_path, monkeypatch):
    """Paths inside ~/.claude/projects/ must be accepted."""
    fake_root = tmp_path / ".claude" / "projects"
    fake_root.mkdir(parents=True)
    target = fake_root / "myproject" / "session.jsonl"
    target.parent.mkdir()
    target.touch()

    monkeypatch.setattr(
        "tokenwise.security._ALLOWED_READ_ROOTS",
        (fake_root,),
    )
    # Should not raise
    result = safe_read_path(target)
    assert result == target.resolve()


def test_safe_read_path_rejects_escape(tmp_path, monkeypatch):
    """Paths outside allowed roots must raise ValueError."""
    fake_root = tmp_path / ".claude" / "projects"
    fake_root.mkdir(parents=True)

    monkeypatch.setattr(
        "tokenwise.security._ALLOWED_READ_ROOTS",
        (fake_root,),
    )
    with pytest.raises(ValueError, match="outside the allowed"):
        safe_read_path(tmp_path / "etc" / "passwd")


def test_safe_read_path_rejects_traversal(tmp_path, monkeypatch):
    """Path traversal attempts (../../) must be blocked."""
    fake_root = tmp_path / ".claude" / "projects"
    fake_root.mkdir(parents=True)
    monkeypatch.setattr(
        "tokenwise.security._ALLOWED_READ_ROOTS",
        (fake_root,),
    )
    traversal = fake_root / ".." / ".." / "sensitive"
    with pytest.raises(ValueError, match="outside the allowed"):
        safe_read_path(traversal)


# ---------------------------------------------------------------------------
# 3. safe_write_path — write root enforcement
# ---------------------------------------------------------------------------


def test_safe_write_path_accepts_cache_dir(tmp_path, monkeypatch):
    """Paths inside ~/.tokenwise/ must be accepted for writing."""
    fake_cache = tmp_path / ".tokenwise"
    fake_cache.mkdir()
    monkeypatch.setattr(
        "tokenwise.security._ALLOWED_WRITE_ROOTS",
        (fake_cache,),
    )
    result = safe_write_path(fake_cache / "cache.json")
    assert result == (fake_cache / "cache.json").resolve()


def test_safe_write_path_rejects_claude_dir(tmp_path, monkeypatch):
    """Writes into ~/.claude/ must always be rejected."""
    fake_cache = tmp_path / ".tokenwise"
    fake_cache.mkdir()
    fake_claude = tmp_path / ".claude"
    fake_claude.mkdir()
    monkeypatch.setattr(
        "tokenwise.security._ALLOWED_WRITE_ROOTS",
        (fake_cache,),
    )
    with pytest.raises(ValueError, match="outside the allowed"):
        safe_write_path(fake_claude / "projects" / "anything.jsonl")


# ---------------------------------------------------------------------------
# 4. open_readonly — mode enforcement
# ---------------------------------------------------------------------------


def test_open_readonly_returns_readable_file(tmp_path, monkeypatch):
    """open_readonly must open the file and allow reading."""
    import tokenwise.security as _sec
    monkeypatch.setattr(_sec, "_ALLOWED_READ_ROOTS", (tmp_path,))
    f = tmp_path / "data.json"
    f.write_text('{"key": "value"}')
    with open_readonly(f) as fh:
        content = fh.read()
    assert '"key"' in content


def test_open_readonly_file_mode_is_r(tmp_path, monkeypatch):
    """open_readonly must open in 'r' mode only."""
    import tokenwise.security as _sec
    monkeypatch.setattr(_sec, "_ALLOWED_READ_ROOTS", (tmp_path,))
    f = tmp_path / "data.txt"
    f.write_text("hello")
    with open_readonly(f) as fh:
        assert fh.mode == "r"


def test_open_readonly_cannot_write(tmp_path, monkeypatch):
    """The file handle from open_readonly must not be writable."""
    import tokenwise.security as _sec
    monkeypatch.setattr(_sec, "_ALLOWED_READ_ROOTS", (tmp_path,))
    f = tmp_path / "data.txt"
    f.write_text("original")
    with open_readonly(f) as fh:
        with pytest.raises((OSError, io.UnsupportedOperation)):
            fh.write("overwrite")  # type: ignore[attr-defined]


def test_open_readonly_rejects_path_outside_allowed_roots(tmp_path, monkeypatch):
    """open_readonly must refuse paths not inside any allowed read root."""
    import tokenwise.security as _sec
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(_sec, "_ALLOWED_READ_ROOTS", (allowed,))
    outside = tmp_path / "secret.txt"
    outside.write_text("classified")
    with pytest.raises(ValueError, match="outside the allowed"):
        open_readonly(outside)


# ---------------------------------------------------------------------------
# 5. Cache directory and file permissions
# ---------------------------------------------------------------------------


def test_ensure_cache_dir_creates_with_700(tmp_path):
    """Cache directory must be created with mode 0o700."""
    cache_dir = tmp_path / ".tokenwise"
    ensure_cache_dir(cache_dir)
    assert cache_dir.exists()
    mode = stat.S_IMODE(cache_dir.stat().st_mode)
    assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"


def test_set_cache_file_permissions_600(tmp_path):
    """Cache file must be set to mode 0o600 after writing."""
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("{}")
    set_cache_file_permissions(cache_file)
    mode = stat.S_IMODE(cache_file.stat().st_mode)
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


# ---------------------------------------------------------------------------
# 6. No eval / exec / pickle / subprocess in source
# ---------------------------------------------------------------------------


def _scan_src_for_pattern(pattern: str) -> list[str]:
    """Return list of 'file:line' matches for `pattern` in src/tokenwise/."""
    src_root = Path(__file__).parent.parent / "src" / "tokenwise"
    hits = []
    for py_file in sorted(src_root.rglob("*.py")):
        for i, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # skip comment lines
            if pattern in line:
                hits.append(f"{py_file.relative_to(src_root)}:{i}: {stripped}")
    return hits


def test_no_eval_in_source():
    assert _scan_src_for_pattern("eval(") == [], "Found eval() in source"


def test_no_exec_in_source():
    assert _scan_src_for_pattern("exec(") == [], "Found exec() in source"


def test_no_pickle_in_source():
    assert _scan_src_for_pattern("pickle") == [], "Found pickle in source"


def test_no_subprocess_in_source():
    hits = _scan_src_for_pattern("subprocess")
    assert hits == [], f"Found subprocess usage: {hits}"


def test_no_os_system_in_source():
    hits = _scan_src_for_pattern("os.system(")
    assert hits == [], f"Found os.system() usage: {hits}"


# ---------------------------------------------------------------------------
# 7. Read-only enforcement on ~/.claude — no write-mode opens
# ---------------------------------------------------------------------------


def test_no_write_mode_opens_on_claude_dir():
    """Source must never open ~/.claude/ files in write/append mode."""
    src_root = Path(__file__).parent.parent / "src" / "tokenwise"
    write_mode_patterns = ["'w'", '"w"', "'a'", '"a"', "'r+'", '"r+"', "'w+'", '"w+"']
    # We check that no open() call with a write mode appears immediately
    # followed by a reference to the claude projects path variable.
    # The stronger check: grep for open( calls with write flags in parser.py
    # specifically, since that's the only module that touches ~/.claude.
    parser_src = (src_root / "parser.py").read_text(encoding="utf-8")
    for pattern in write_mode_patterns:
        # Allow the pattern if it's in a comment
        for line in parser_src.splitlines():
            if line.strip().startswith("#"):
                continue
            if "open(" in line and pattern in line:
                pytest.fail(f"parser.py contains a write-mode open(): {line.strip()!r}")
