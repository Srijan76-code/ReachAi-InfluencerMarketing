"""Contact and cross-platform links found in a creator's own bio or description (any platform)."""

from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
SOCIAL_PATTERNS = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/(?!p/|reel/|reels/|explore/|stories/)([A-Za-z0-9_.]+)", re.I),
    "x": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent/|share|hashtag/|search)([A-Za-z0-9_]+)", re.I),
    "linkedin": re.compile(r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([A-Za-z0-9_\-%]+)", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]+)", re.I),
    "youtube": re.compile(r"https?://(?:www\.|m\.)?youtube\.com/(?:@[\w.\-]+|channel/UC[\w-]{20,}|c/[\w.\-]+)", re.I),
}

def extract_links(text: str) -> tuple[list[str], dict[str, str], list[str]]:
    """(emails, social links by platform, other links) found in a channel description."""
    text = text or ""
    emails = list(dict.fromkeys(e.rstrip(".") for e in EMAIL.findall(text)))
    socials: dict[str, str] = {}
    for name, pattern in SOCIAL_PATTERNS.items():
        m = pattern.search(text)
        if m:
            socials[name] = m.group(0).rstrip("/.")
    social_urls = set(socials.values())
    others = [u.rstrip("/.") for u in URL.findall(text)]
    others = [u for u in dict.fromkeys(others) if not any(u.startswith(s) for s in social_urls)]
    return emails, socials, others


