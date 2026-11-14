"""One person, several accounts (spec §4.9 "Identity and the person model", roadmap F1.17b).

Pure code, no network. Decides which accounts are the same person from what creators publish themselves:

- a link both ways (A's bio links to B and B's links back), or a link one way plus a matching name or
  handle → linked automatically (`self_link`);
- a link one way with a different name (a YouTube description often links a sponsor's or a friend's
  Instagram), or the same name/handle with no link at all → only a candidate: Jev must say it's the same
  person (≥ NAME_MATCH_MERGE_FROM) before it's shown, and then only as "Probably also" (`name_match`).

Never merged on a name alone.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, Optional
from urllib.parse import unquote

from app.creators import constants as C

PLATFORMS = ("youtube", "x", "instagram", "linkedin")
MIN_NAME_CHARS = 5

_LINK = {
    "youtube": re.compile(r"(?:youtube\.com/(?:@([\w.\-]+)|channel/(UC[\w-]{20,}))|youtube\.com/c/([\w.\-]+))", re.I),
    "instagram": re.compile(r"instagram\.com/(?!p/|reel/|reels/|explore/|stories/|tv/)([A-Za-z0-9_.]+)", re.I),
    "x": re.compile(r"(?:twitter|x)\.com/(?!intent/|share|hashtag/|search|home|i/)([A-Za-z0-9_]{1,15})\b", re.I),
    "linkedin": re.compile(r"linkedin\.com/in/([A-Za-z0-9_\-%]+)", re.I),
}
_RESERVED = {"x": {"home", "explore", "settings", "login"}, "instagram": {"accounts", "about"}}


def parse_link(url: str) -> Optional[tuple[str, str]]:
    """("instagram", "sofia.codes") from a profile link; None for posts, searches and other sites.
    YouTube keys are "@handle" or the channel id ("UC…"); every key is lowercase except channel ids."""
    for platform, pattern in _LINK.items():
        m = pattern.search(url or "")
        if not m:
            continue
        if platform == "youtube":
            handle, channel, legacy = m.groups()
            if channel:
                return "youtube", channel
            return ("youtube", "@" + (handle or legacy).lower()) if (handle or legacy) else None
        key = unquote(m.group(1)).strip("/.").lower()
        if not key or key in _RESERVED.get(platform, set()):
            return None
        return platform, key
    return None


def own_keys(profile: dict) -> set[tuple[str, str]]:
    """The keys other creators' links would use for this account."""
    platform = profile.get("platform")
    keys = set()
    pid, handle = str(profile.get("platform_id") or ""), str(profile.get("handle") or "")
    if platform == "youtube":
        if pid:
            keys.add(("youtube", pid))
        if handle:
            keys.add(("youtube", "@" + handle.lstrip("@").lower()))
    elif platform in PLATFORMS:
        for v in (pid, handle):
            if v and not v.isdigit():  # X ids are numbers; links use the handle
                keys.add((platform, v.lstrip("@").lower()))
    parsed = parse_link(str(profile.get("url") or ""))
    if parsed:
        keys.add(parsed)
    return keys


def links_of(profile: dict) -> dict[str, tuple[str, str]]:
    """{platform: key} for the other-platform accounts this account links to itself (bio, description,
    website list). The account's own platform is ignored."""
    out: dict[str, tuple[str, str]] = {}
    urls: list[str] = list((profile.get("cross_links") or {}).values()) + list(profile.get("external_links") or [])
    for u in urls:
        parsed = parse_link(str(u))
        if parsed and parsed[0] != profile.get("platform") and parsed[0] not in out:
            out[parsed[0]] = parsed
    return out


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _name_words(s: str) -> str:
    """The name without decorations: "Sofia ♡ | Tech & AI" → "sofia", "Ben Holmes (BenCodes)" → "benholmes"."""
    s = re.split(r"[|•·(\[]| - | – ", s or "")[0]
    return _norm(s)


def similarity(a: dict, b: dict) -> float:
    """How alike two accounts' names and handles are, 0..1 (code only, no judgment)."""
    pairs = [(_norm(a.get("handle") or ""), _norm(b.get("handle") or "")),
             (_name_words(a.get("display_name") or ""), _name_words(b.get("display_name") or "")),
             (_norm(a.get("handle") or ""), _name_words(b.get("display_name") or "")),
             (_name_words(a.get("display_name") or ""), _norm(b.get("handle") or ""))]
    best = 0.0
    for x, y in pairs:
        if len(x) < MIN_NAME_CHARS or len(y) < MIN_NAME_CHARS:  # "sam", "alex": too common to mean anything
            continue
        if x == y:
            return 1.0
        ratio = SequenceMatcher(None, x, y).ratio()
        if min(len(x), len(y)) >= 5 and (x in y or y in x):  # "sofiacodes" vs "sofia"
            ratio = max(ratio, 0.9)
        best = max(best, ratio)
    return best


def decide(a: dict, b: dict) -> str:
    """For two accounts on different platforms: "link" (same person, published by them), "check"
    (worth asking Jev) or "no"."""
    if a.get("platform") == b.get("platform"):
        return "no"
    a_to_b = any(k in own_keys(b) for k in links_of(a).values())
    b_to_a = any(k in own_keys(a) for k in links_of(b).values())
    alike = similarity(a, b)
    if (a_to_b and b_to_a) or ((a_to_b or b_to_a) and alike >= C.NAME_SIMILAR_FROM):
        return "link"
    if a_to_b or b_to_a or alike >= C.NAME_SIMILAR_FROM:
        return "check"
    return "no"


def pending_links(profile: dict, known: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """Accounts this creator links to that we haven't measured yet (to measure for top results)."""
    known = set(known)
    return [k for k in links_of(profile).values() if k not in known]
