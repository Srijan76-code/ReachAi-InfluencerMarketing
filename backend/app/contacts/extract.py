"""Pulling email addresses and links out of a page or a bio. Code only."""

from __future__ import annotations

import html
import re
from typing import Iterable
from urllib.parse import unquote, urljoin

from app.contacts import constants as C

EMAIL = re.compile(r"(?<![\w.+-])[A-Za-z0-9][\w.+-]{0,63}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}(?![\w-])")
# "name [at] domain [dot] com", "name (at) domain (dot) com", "name{at}domain{dot}com"
OBFUSCATED = re.compile(
    r"([A-Za-z0-9][\w.+-]{0,63})\s*[\[({<]\s*at\s*[\])}>]\s*([A-Za-z0-9-]+(?:\s*[\[({<]\s*dot\s*[\])}>]\s*[A-Za-z0-9-]+)+)",
    re.I)
DOT = re.compile(r"\s*[\[({<]\s*dot\s*[\])}>]\s*", re.I)
MAILTO = re.compile(r"mailto:([^\"'?<>\s]+)", re.I)
CFEMAIL = re.compile(r"data-cfemail=[\"']([0-9a-fA-F]+)[\"']")
HREF = re.compile(r"href\s*=\s*[\"']([^\"'#][^\"']*)[\"']", re.I)
ANCHOR = re.compile(r"<a\b[^>]*href\s*=\s*[\"']([^\"'#][^\"']*)[\"'][^>]*>(.*?)</a>", re.I | re.S)
TAGS = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.I | re.S)


def _cf_decode(hexstr: str) -> str:
    """Cloudflare's email protection: the first byte is the key, XORed over the rest."""
    try:
        data = bytes.fromhex(hexstr)
        return "".join(chr(b ^ data[0]) for b in data[1:])
    except (ValueError, IndexError):
        return ""


def clean_email(raw: str) -> str:
    """Lowercased address, or "" when it's junk (image names, placeholders, no-reply inboxes, test domains)."""
    e = unquote(raw or "").strip().strip(".,;:'\"()<>[]").lower()
    if e.startswith("mailto:"):
        e = e[7:]
    if not EMAIL.fullmatch(e) or len(e) > 120:
        return ""
    local, _, domain = e.partition("@")
    if domain.rsplit(".", 1)[-1] in C.JUNK_TLDS or "@2x" in e or local.startswith(("u00", "x22")):
        return ""
    if domain in C.JUNK_DOMAINS or any(domain.endswith("." + d) for d in C.JUNK_DOMAINS):
        return ""
    if local in C.NEVER_LOCAL_PARTS or local.startswith(("noreply", "no-reply", "donotreply")):
        return ""
    return e


def emails_in(text: str) -> list[str]:
    """Every usable address in a bio or a page (HTML or plain text), first seen first."""
    if not text:
        return []
    found: list[str] = []
    found += MAILTO.findall(text)
    found += [_cf_decode(h) for h in CFEMAIL.findall(text)]
    plain = html.unescape(TAGS.sub(" ", text)) if "<" in text else html.unescape(text)
    found += EMAIL.findall(plain)
    found += [f"{m.group(1)}@{DOT.sub('.', m.group(2))}" for m in OBFUSCATED.finditer(plain)]
    out: list[str] = []
    for f in found:
        e = clean_email(f)
        if e and e not in out:
            out.append(e)
    return out


def links_in(page: str, base: str) -> list[str]:
    """Absolute http(s) links on a page, first seen first."""
    out: list[str] = []
    for href in HREF.findall(page or ""):
        url = urljoin(base, html.unescape(href.strip()))
        if url.startswith(("http://", "https://")) and url not in out:
            out.append(url.split("#")[0])
    return out


def contact_links(page: str, base: str, same_host: str) -> list[str]:
    """Links on the same site that look like a contact, about or work-with-me page."""
    from app.contacts.fetch import host_of

    scored: list[str] = []
    for href, label in ANCHOR.findall(page or ""):
        url = urljoin(base, html.unescape(href.strip())).split("#")[0]
        if not url.startswith(("http://", "https://")) or host_of(url) != same_host:
            continue
        hay = (url.lower() + " " + TAGS.sub(" ", label).lower())
        if any(h in hay for h in C.CONTACT_HINTS) and url not in scored and url.rstrip("/") != base.rstrip("/"):
            scored.append(url)
    return scored


def name_candidates(texts: Iterable[str]) -> list[str]:
    """First names stated in the creator's own words: "I'm Priya", "my name is Alex", "Hi, I am Sam"."""
    pat = re.compile(r"\b(?:i'?m|i am|my name is|name's|this is)\s+([A-Z][a-z]{1,20})\b")
    out: list[str] = []
    for t in texts:
        for m in pat.finditer(t or ""):
            n = m.group(1)
            if n not in out and n.lower() not in ("a", "an", "the", "here", "back", "so", "not", "just", "your"):
                out.append(n)
    return out
