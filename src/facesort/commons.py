"""Wikimedia Commons: find files, fetch their metadata, download originals.

API responses are cached under data/cache/commons, so the first run is the
snapshot every later run reads from. Downloads are checked against the SHA-1
Commons publishes for each file. Any HTTP error (including 429 throttling)
raises after retries; nothing here returns an empty result on failure.
"""

import hashlib
import re
import time
from pathlib import Path

import requests

from facesort.cache import cached_json

API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia requires an identifying User-Agent; generic ones get 403s.
USER_AGENT = "facesort/0.1 (https://github.com/Rajarshi-Misra/Face-Sorting) research study"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5
TITLES_PER_REQUEST = 50  # API limit for prop=imageinfo

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def _get(url: str, params: dict | None = None, stream: bool = False) -> requests.Response:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        r = _session.get(url, params=params, timeout=60, stream=stream)
        if r.status_code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
            wait = float(r.headers.get("Retry-After", 2**attempt))
            print(f"Commons {r.status_code}, retry {attempt}/{MAX_ATTEMPTS - 1} in {wait:.0f}s")
            time.sleep(wait)
            continue
        if not r.ok:
            raise RuntimeError(f"Commons HTTP {r.status_code} for {r.url}: {r.text[:300]}")
        return r
    raise AssertionError("unreachable")


def _api(params: dict) -> dict:
    params = {**params, "action": "query", "format": "json", "formatversion": "2"}

    def fetch() -> dict:
        data = _get(API, params).json()
        if "error" in data:
            raise RuntimeError(f"Commons API error: {data['error']}")
        return data

    return cached_json("commons", params, fetch)


def search_files(query: str) -> list[str]:
    """All File: titles matching a CirrusSearch query, e.g. 'deepcategory:"Annie Lööf" filemime:image/jpeg'."""
    titles: list[str] = []
    offset: int | None = 0
    while offset is not None:
        data = _api({"list": "search", "srsearch": query, "srnamespace": 6, "srlimit": 500, "sroffset": offset})
        titles += [hit["title"] for hit in data["query"]["search"]]
        offset = data.get("continue", {}).get("sroffset")
    return titles


def category_jpegs(category: str) -> list[str]:
    """JPEG file titles in a category and its subcategories."""
    return search_files(f'deepcategory:"{category}" filemime:image/jpeg')


def _plain(html: str | None) -> str | None:
    if html is None:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def image_info(titles: list[str]) -> list[dict]:
    """One row per title: url, size, sha1, licence, author, date. Raises if any title is missing."""
    rows: list[dict] = []
    for i in range(0, len(titles), TITLES_PER_REQUEST):
        batch = titles[i : i + TITLES_PER_REQUEST]
        data = _api({
            "titles": "|".join(batch),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|sha1|timestamp|user|extmetadata",
        })
        pages = data["query"]["pages"]
        missing = [p["title"] for p in pages if p.get("missing") or "imageinfo" not in p]
        if missing:
            raise RuntimeError(f"Commons has no file info for: {missing}")
        for page in pages:
            info = page["imageinfo"][0]
            meta = {k: v.get("value") for k, v in info.get("extmetadata", {}).items()}
            rows.append({
                "title": page["title"],
                "url": info["url"],
                "page_url": info["descriptionurl"],
                "width": info["width"],
                "height": info["height"],
                "mime": info["mime"],
                "sha1": info["sha1"],
                "uploaded": info["timestamp"],
                "uploader": info["user"],
                "licence": meta.get("LicenseShortName"),
                "licence_url": meta.get("LicenseUrl"),
                "author": _plain(meta.get("Artist")),
                "date_taken": _plain(meta.get("DateTimeOriginal")),
                "description": _plain(meta.get("ImageDescription")),
            })
    return rows


def _sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def download(url: str, dest: Path, sha1: str, pause: float = 1.0) -> Path:
    """Download `url` to `dest` unless a file with the right SHA-1 is already there.

    `pause` is a courtesy delay after each real download; upload.wikimedia.org throttles bursts.
    """
    if dest.exists():
        if _sha1(dest) == sha1:
            return dest
        raise RuntimeError(f"{dest} exists with the wrong SHA-1; raw files are never overwritten")

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with _get(url, stream=True) as r, tmp.open("wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    got = _sha1(tmp)
    if got != sha1:
        tmp.unlink()
        raise RuntimeError(f"SHA-1 mismatch for {url}: expected {sha1}, got {got}")
    tmp.replace(dest)
    time.sleep(pause)
    return dest
