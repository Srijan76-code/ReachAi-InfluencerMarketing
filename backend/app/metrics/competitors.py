"""Creators who already promote a competitor (roadmap F1.19). Code only: a post counts when it's sponsored
(the same markers as app/metrics/posts.sponsorship) and its sponsor is a competitor: the named sponsor
("sponsored by Notion"), or, when no sponsor is named, a competitor named as a whole word in the post. A review
that just mentions a competitor isn't a promotion."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from app.metrics.posts import sponsorship


def _pattern(name: str) -> re.Pattern:
    words = [re.escape(w) for w in name.split()]
    return re.compile(r"(?<![\w@#.])" + r"[\s\-]?".join(words) + r"(?![\w])", re.I)


def promotions(posts: Iterable[dict], competitors: Iterable[str]) -> list[dict]:
    """[{"brand": "Notion", "posts": 2}] for competitors named in the creator's sponsored posts, most first."""
    names = [c for c in dict.fromkeys(competitors) if c and len(c.strip()) >= 2]
    if not names:
        return []
    patterns = {n: _pattern(n) for n in names}
    hits: Counter = Counter()
    for p in posts or []:
        text, desc = str(p.get("text") or ""), str(p.get("description") or "")
        sponsored, brands = sponsorship(text, desc)
        if not sponsored:
            continue
        # a named sponsor ("sponsored by Acme") is who the post promotes: a competitor merely mentioned in it
        # doesn't count. Without a named sponsor, a competitor named anywhere in the sponsored post counts.
        blob = " ".join(brands) if brands else f"{text}\n{desc}"
        for n, pat in patterns.items():
            if pat.search(blob):
                hits[n] += 1
    return [{"brand": b, "posts": c} for b, c in hits.most_common()]
