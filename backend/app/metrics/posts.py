"""Per-post signals for the creator panel, the same for every platform (rule 5: no platform code here).

- matched topics: which of the brief's topics a post is about (word overlap, no AI cost), from the title and the
  description's opening summary only: later lines are usually link lists that repeat on every video
- x_usual: the post's reach divided by the creator's median reach; posts under YOUNG_POST_DAYS old are "new"
  instead (still collecting views) and left out of the median
- sponsored: the post's text says it's a paid promotion; brand names when they're spelled out
Numbers are computed here, never by a model (rule 2). Post text is untrusted: it's only matched, never executed.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timezone
from collections import Counter
from typing import Iterable, Optional

from app.metrics import constants as C

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "best", "by", "for", "from", "get", "how", "i", "in", "is", "it",
    "my", "of", "on", "or", "the", "this", "to", "top", "vs", "what", "why", "with", "you", "your", "guide",
    "tips", "tutorial", "video", "videos", "new", "2024", "2025", "2026", "2027",
}
_WORD = re.compile(r"[a-z0-9]+")
# whole phrases only: "#ad" must not match "#adventure"
_SPONSOR = re.compile(r"(?<![\w#])(?:" + "|".join(re.escape(p) for p in C.SPONSOR_PHRASES) + r")(?![\w])")
_BRAND = re.compile(r"(?i:sponsored by|thanks to|brought to you by|in partnership with)\s+@?"
                    r"([A-Z][\w&-]*(?:\.[A-Za-z]+)?(?:[ ]+[A-Z][\w&-]*(?:\.[A-Za-z]+)?){0,2})")


def _stem(w: str) -> str:
    """Crude plural fold so "interview" matches "interviews" (no NLP library, no cost)."""
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def words(text: str) -> set[str]:
    return {_stem(w) for w in _WORD.findall((text or "").lower()) if w not in STOP and len(w) > 1}


def match_terms(topics: Iterable[str]) -> list[str]:
    """The brief topics worth matching (deduped, non-empty)."""
    seen, out = set(), []
    for t in topics or []:
        t = (t or "").strip()
        key = t.lower()
        if t and key not in seen and words(t):
            seen.add(key)
            out.append(t)
    return out


def matched_topics(text: str, topics: list[str]) -> list[str]:
    have = words(text)
    hits = []
    for t in topics:
        need = words(t)
        if need and len(need & have) / len(need) >= C.MATCH_MIN_TERM_SHARE:
            hits.append(t)
    return hits


def summary(description: str) -> str:
    """The description's opening paragraph (its summary), before any link lists."""
    first = re.split(r"\n\s*\n|https?://", description or "", maxsplit=1)[0]
    return first[: C.DESCRIPTION_SUMMARY_CHARS]


def sponsorship(text: str, description: str = "") -> tuple[bool, list[str]]:
    blob = f"{text or ''}\n{description or ''}"
    low = blob.lower()
    sponsored = bool(_SPONSOR.search(low))
    brands = []
    if sponsored:
        for m in _BRAND.finditer(blob):
            name = m.group(1).strip(" .,-")
            if name and name.lower() not in {"the", "our", "my", "you", "everyone"}:
                brands.append(name)
    return sponsored, list(dict.fromkeys(brands))[:3]


def _reach(post: dict) -> tuple[Optional[float], str]:
    """Views where the platform shows them, else likes (Instagram photos), else reactions (LinkedIn)."""
    if post.get("views") is not None:
        return float(post["views"]), "views"
    if post.get("likes") is not None:
        return float(post["likes"]), "likes"
    return None, "reach"


def _days_old(published, as_of: Optional[datetime]) -> Optional[float]:
    if as_of is None or published is None:
        return None
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published)
        except ValueError:
            return None
    aware = lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return (aware(as_of) - aware(published)).total_seconds() / 86400


def analyse_posts(posts: list[dict], topics: list[str], limit: int = C.POSTS_IN_LEAD,
                  as_of: Optional[datetime] = None) -> tuple[list[dict], dict]:
    """Returns (post cards for the UI, summary signals). Cards keep the newest-first order.
    `as_of`: when the posts were fetched, to tell new posts (still collecting views) from settled ones."""
    young = [(d is not None and d < C.YOUNG_POST_DAYS) for d in (_days_old(p.get("published_at"), as_of) for p in posts)]
    reaches = [r for (r, _), y in zip((_reach(p) for p in posts), young) if r is not None and not y]
    median = statistics.median(reaches) if reaches else None
    cards, brands = [], Counter()
    fit_posts = sponsored_posts = 0
    for p, is_new in zip(posts, young):
        reach, label = _reach(p)
        topics_hit = matched_topics(f"{p.get('text', '')} {summary(p.get('description', ''))}", topics)
        sponsored, names = sponsorship(p.get("text", ""), p.get("description", ""))
        fit_posts += bool(topics_hit)
        sponsored_posts += sponsored
        brands.update(names)
        published = p.get("published_at")
        cards.append({
            "id": p.get("post_id"),
            "url": p.get("url"),
            "thumbnail_url": p.get("thumbnail_url"),
            "title": p.get("text", ""),
            "published_at": published.isoformat() if hasattr(published, "isoformat") else published,
            "format": p.get("format") or ("short" if p.get("is_short_form") else "long"),
            "reach": int(reach) if reach is not None else None,
            "reach_label": label,
            "likes": p.get("likes"),
            "comments": p.get("comments"),
            "x_usual": round(reach / median, 2) if reach is not None and median and not is_new else None,
            "is_new": is_new,
            "matched_topics": topics_hit,
            "sponsored": sponsored,
        })
    signals = {
        "posts_checked": len(posts),
        "fit_posts": fit_posts,
        "sponsored_posts": sponsored_posts,
        "sponsor_brands": [b for b, _ in brands.most_common(5)],
        "median_reach": round(median) if median is not None else None,
    }
    return cards[:limit], signals
