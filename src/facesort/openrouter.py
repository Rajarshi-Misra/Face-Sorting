"""OpenRouter chat calls with any number of images in one message.

The cache key is the full request payload (model, prompt, every image's bytes
in the order sent, temperature, max_tokens), so a reshuffled order is a
different call and never a cache hit.
"""

import base64
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from facesort.cache import PROJECT_ROOT, cached_json

URL = "https://openrouter.ai/api/v1/chat/completions"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


def _api_key() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (expected in the project-root .env)")
    return key


def build_content(prompt: str, images: list[Path], numbered: bool) -> list[dict]:
    """Prompt first, then the images. With `numbered`, each image is preceded by 'Photo N:' (1-based)."""
    content: list[dict] = [{"type": "text", "text": prompt}]
    for i, path in enumerate(images, start=1):
        if numbered:
            content.append({"type": "text", "text": f"Photo {i}:"})
        b64 = base64.b64encode(Path(path).read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    return content


def _post(payload: dict) -> dict:
    headers = {"Authorization": f"Bearer {_api_key()}"}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        r = requests.post(URL, headers=headers, json=payload, timeout=300)
        if r.status_code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
            wait = float(r.headers.get("Retry-After", 2**attempt))
            print(f"OpenRouter {r.status_code}, retry {attempt}/{MAX_ATTEMPTS - 1} in {wait:.0f}s")
            time.sleep(wait)
            continue
        if not r.ok:
            raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        # OpenRouter can return 200 with the error in the body or inside the choice.
        if "error" in data:
            raise RuntimeError(f"OpenRouter error: {data['error']}")
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices: {str(data)[:500]}")
        if "error" in choices[0] or choices[0].get("finish_reason") == "error":
            raise RuntimeError(f"OpenRouter choice error: {choices[0]}")
        return data
    raise AssertionError("unreachable")


def call(
    model: str,
    prompt: str,
    images: list[Path],
    *,
    numbered: bool = False,
    temperature: float = 0,
    max_tokens: int = 2000,
) -> dict:
    """One chat call; returns the raw OpenRouter response (cached)."""
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": build_content(prompt, images, numbered)}],
    }
    return cached_json("openrouter", payload, lambda: _post(payload))


def text_of(response: dict) -> tuple[str, str | None]:
    """(content, finish_reason) of the first choice. Content is '' when the model sent none."""
    choice = response["choices"][0]
    return choice["message"].get("content") or "", choice.get("finish_reason")
