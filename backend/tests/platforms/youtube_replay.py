"""Record real YouTube API responses once, then replay them in tests (no live calls in CI)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "youtube" / "recording.json"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _key(resource: str, params: dict) -> str:
    clean = {k: v for k, v in params.items() if v is not None and k != "key"}
    return resource + "?" + json.dumps(clean, sort_keys=True)


UNUSED_FIELDS = {"thumbnails", "localized", "tags", "etag", "liveBroadcastContent", "categoryId", "defaultAudioLanguage"}
MAX_DESCRIPTION = 1500


def scrub(value: Any) -> Any:
    """Recorded data is committed to a public repo: replace email addresses and drop fields
    the adapter never reads (keeps the fixture small)."""
    if isinstance(value, str):
        return EMAIL.sub("hidden@example.com", value)
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in UNUSED_FIELDS:
                continue
            if k == "description" and isinstance(v, str):
                v = v[:MAX_DESCRIPTION]
            out[k] = scrub(v)
        return out
    return value


class RecordingAPI:
    def __init__(self, inner):
        self.inner = inner
        self.calls: list[dict] = []

    async def _call(self, resource, method, params):
        response = await getattr(self.inner, method)(**params)
        self.calls.append({"key": _key(resource, params), "response": scrub(response)})
        return response

    async def search(self, **p): return await self._call("search", "search", p)
    async def channels(self, **p): return await self._call("channels", "channels", p)
    async def playlist_items(self, **p): return await self._call("playlistItems", "playlist_items", p)
    async def videos(self, **p): return await self._call("videos", "videos", p)


class ReplayAPI:
    """Serves recorded responses; unknown requests return empty results and are listed in `misses`."""

    def __init__(self, path: Path = FIXTURE, overrides: dict | None = None):
        data = json.loads(path.read_text())
        self.recorded_at = data["recorded_at"]
        self.responses = {c["key"]: c["response"] for c in data["calls"]}
        # Items by id, so lookups for a different batch of ids (e.g. after a filter dropped some)
        # can still be answered from what was recorded.
        self.items: dict[str, dict] = {"channels": {}, "videos": {}}
        for c in data["calls"]:
            resource = c["key"].split("?", 1)[0]
            if resource in self.items:
                for item in c["response"].get("items", []):
                    self.items[resource][item["id"]] = item
        self.overrides = overrides or {}
        self.calls: list[str] = []
        self.misses: list[str] = []

    async def _get(self, resource, params):
        key = _key(resource, params)
        self.calls.append(resource)
        if resource in self.overrides:
            result = self.overrides[resource]
            if isinstance(result, Exception):
                raise result
            return result
        if key in self.responses:
            return self.responses[key]
        if resource in self.items and "id" in params:
            ids = str(params["id"]).split(",")
            if all(i in self.items[resource] for i in ids):
                return {"items": [self.items[resource][i] for i in ids]}
        self.misses.append(key)
        return {"items": []}

    async def search(self, **p): return await self._get("search", p)
    async def channels(self, **p): return await self._get("channels", p)
    async def playlist_items(self, **p): return await self._get("playlistItems", p)
    async def videos(self, **p): return await self._get("videos", p)
