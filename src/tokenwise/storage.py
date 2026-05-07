from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .security import ensure_cache_dir, open_readonly, safe_write_path, set_cache_file_permissions

CACHE_DIR = Path.home() / ".tokenwise"
CACHE_FILE = CACHE_DIR / "cache.json"


def load_cache() -> dict[str, Any]:
    if not CACHE_FILE.exists():
        return {}
    try:
        with open_readonly(CACHE_FILE) as f:
            data: dict[str, Any] = json.load(f)
            return data
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


def save_cache(data: dict[str, Any]) -> None:
    safe_write_path(CACHE_FILE)  # path-safety guard before any write
    ensure_cache_dir(CACHE_DIR)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    set_cache_file_permissions(CACHE_FILE)


def get_file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def is_cache_valid(cache: dict[str, Any], jsonl_path: Path) -> bool:
    key = str(jsonl_path)
    cached_mtime: float = cache.get("mtimes", {}).get(key, 0.0)
    return cached_mtime == get_file_mtime(jsonl_path)


def update_cache_mtime(cache: dict[str, Any], jsonl_path: Path) -> None:
    cache.setdefault("mtimes", {})[str(jsonl_path)] = get_file_mtime(jsonl_path)
