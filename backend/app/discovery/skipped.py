"""Why creators were left out of a run (spec §4.14): the drop reasons recorded on run_candidates,
grouped into a few plain buckets so the results page can say "312 looked at, 41 skipped as inactive"."""

import re
from collections import Counter

# reason text -> bucket shown to the user. Matched on the start of the reason, in order.
_BUCKETS = (
    ("inactive for", "inactive"),
    ("no recent posts", "inactive"),
    ("suspicious engagement", "suspicious engagement"),
    ("below the view floor", "too few views"),
    ("too few views", "too few views"),
    ("no views", "too few views"),
    ("below the minimum subscriber", "too small"),
    ("above the maximum subscriber", "too large"),
    ("outside the target countries", "wrong country"),
    ("too few videos", "too few posts"),
    ("not an individual creator", "not an individual creator"),
    ("posts in a different language", "different language"),
    ("content made for children", "made for children"),
    ("profile contains instructions aimed at ai", "unsafe profile text"),
)


def bucket(reason: str) -> str:
    r = reason.strip().lower()
    for start, label in _BUCKETS:
        if r.startswith(start):
            return label
    # unknown reason: keep the words, drop numbers and detail after a colon
    return re.sub(r"\d+", "N", r.split(":")[0]).strip() or "other"


def summarise(rows) -> dict:
    """rows: (stage, drop_reason) pairs for one run. Each creator counts once per bucket."""
    looked_at = skipped = 0
    counts: Counter = Counter()
    for stage, reason in rows:
        looked_at += 1
        if not reason:
            continue
        skipped += 1
        for b in {bucket(part) for part in reason.split(";") if part.strip()}:
            counts[b] += 1
    return {
        "looked_at": looked_at,
        "skipped": skipped,
        "reasons": [{"reason": r, "count": n} for r, n in counts.most_common()],
    }
