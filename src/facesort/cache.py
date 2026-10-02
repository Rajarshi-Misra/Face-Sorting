"""Disk cache for API responses.

Every external call (Commons, OpenRouter) goes through `cached_json`, so reruns
are free and a finished run can be rebuilt exactly from `data/cache/`.
Only successful responses are written: a failure raises and leaves no file.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = PROJECT_ROOT / "data" / "cache"


def key_for(obj: Any) -> str:
    """Stable sha256 of any JSON-serialisable object (dict key order ignored, list order kept)."""
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def cached_json(namespace: str, key_obj: Any, fetch: Callable[[], Any]) -> Any:
    cache_dir = CACHE_ROOT / namespace
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key_for(key_obj)}.json"

    if path.exists():
        return json.loads(path.read_text())

    data = fetch()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)  # atomic: a crash mid-write never leaves a half-written cache file
    return data
