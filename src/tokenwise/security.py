"""
Runtime security guarantees for tokenwise.

All checks here are designed to be fast, fail loudly, and be auditable by
anyone reading the source — no clever tricks.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import IO

# Modules that would imply network access — none of these should ever appear
# in tokenwise's own code.
_FORBIDDEN_NETWORK_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "urllib",
        "urllib.request",
        "urllib.parse",
        "requests",
        "httpx",
        "aiohttp",
        "http.client",
        "http.server",
        "ftplib",
        "smtplib",
        "xmlrpc",
        "xmlrpc.client",
    }
)

# The only two directory trees tokenwise is allowed to read or write.
_ALLOWED_READ_ROOTS = (Path.home() / ".claude" / "projects",)
_ALLOWED_WRITE_ROOTS = (Path.home() / ".tokenwise",)


# ---------------------------------------------------------------------------
# Network check
# ---------------------------------------------------------------------------


def assert_no_network_imports() -> None:
    """Raise if any network-capable module was imported by our own code.

    We check sys.modules at startup, after our own imports have settled.
    Third-party libraries (click, rich, pydantic) importing socket internally
    is out of our control and is not flagged — we only refuse to import those
    modules ourselves.
    """
    # Collect modules imported by tokenwise source files only.
    tokenwise_modules = {name for name in sys.modules if name.startswith("tokenwise.")}

    # Walk each tokenwise module's __file__ and check its source-level imports.
    # This is a best-effort lint; the grep CI check is the authoritative gate.
    # Here we just ensure nothing snuck into sys.modules *under our name*.
    loaded_network = _FORBIDDEN_NETWORK_MODULES & set(sys.modules.keys())
    if loaded_network:
        # Only raise if WE (tokenwise) imported them — check by seeing if any
        # tokenwise module directly references them.
        for mod_name in list(tokenwise_modules):
            mod = sys.modules.get(mod_name)
            if mod is None:
                continue
            src = getattr(mod, "__file__", None) or ""
            if not src:
                continue
            try:
                source_text = Path(src).read_text(encoding="utf-8")
            except OSError:
                continue
            for forbidden in loaded_network:
                if f"import {forbidden}" in source_text or f"from {forbidden}" in source_text:
                    raise RuntimeError(
                        f"Security violation: tokenwise module '{mod_name}' imports "
                        f"network module '{forbidden}'. tokenwise must never make "
                        f"network calls. File: {src}"
                    )


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def safe_read_path(p: Path | str) -> Path:
    """Resolve `p` and assert it sits inside an allowed read root.

    Raises ValueError for paths outside the allowed trees or for symlinks
    that escape them (resolving follows the link before checking).
    """
    resolved = Path(p).resolve()
    for root in _ALLOWED_READ_ROOTS:
        allowed = root.resolve()
        if resolved == allowed or _is_relative_to(resolved, allowed):
            return resolved
    raise ValueError(
        f"Path '{p}' resolves to '{resolved}', which is outside the allowed "
        f"read roots: {[str(r) for r in _ALLOWED_READ_ROOTS]}"
    )


def safe_write_path(p: Path | str) -> Path:
    """Resolve `p` and assert it sits inside an allowed write root."""
    resolved = Path(p).resolve()
    for root in _ALLOWED_WRITE_ROOTS:
        allowed = root.resolve()
        if resolved == allowed or _is_relative_to(resolved, allowed):
            return resolved
    raise ValueError(
        f"Path '{p}' resolves to '{resolved}', which is outside the allowed "
        f"write roots: {[str(r) for r in _ALLOWED_WRITE_ROOTS]}"
    )


def _is_relative_to(child: Path, parent: Path) -> bool:
    # Path.is_relative_to() was added in 3.9; replicate for safety.
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Read-only open helper
# ---------------------------------------------------------------------------


def open_readonly(path: Path | str) -> IO[str]:
    """Open a file strictly read-only.  Never call this with a write mode."""
    resolved = Path(path).resolve()
    return open(resolved, encoding="utf-8")  # noqa: WPS515 — intentional


# ---------------------------------------------------------------------------
# Cache directory / file permissions
# ---------------------------------------------------------------------------


def ensure_cache_dir(cache_dir: Path) -> None:
    """Create cache directory with user-only permissions (0o700)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(cache_dir, 0o700)


def set_cache_file_permissions(cache_file: Path) -> None:
    """Set cache file to user-read/write only (0o600)."""
    if cache_file.exists():
        os.chmod(cache_file, 0o600)
