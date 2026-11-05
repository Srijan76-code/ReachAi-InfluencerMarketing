"""Building the emails we send and reading the replies we get (plain text only)."""

from __future__ import annotations

import base64
import re
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from typing import Optional

from app.gmail import constants as G

_HEADER_UNSAFE = re.compile(r"[\r\n]")


def build(*, sender: str, to: str, subject: str, body: str, sender_name: Optional[str] = None,
          in_reply_to: Optional[str] = None) -> str:
    """The base64url RFC 2822 message the Gmail API wants. Replies carry In-Reply-To/References so they
    stay in the same thread in both inboxes."""
    m = EmailMessage()
    m["From"] = formataddr((_HEADER_UNSAFE.sub(" ", sender_name or ""), sender)) if sender_name else sender
    m["To"] = _HEADER_UNSAFE.sub("", to)
    m["Subject"] = _HEADER_UNSAFE.sub(" ", subject)[:200]
    if in_reply_to:
        m["In-Reply-To"] = in_reply_to
        m["References"] = in_reply_to
    m.set_content(body)
    return base64.urlsafe_b64encode(m.as_bytes()).decode()


def reply_subject(subject: Optional[str]) -> str:
    s = (subject or "").strip() or "Collaboration"
    return s if s.lower().startswith("re:") else f"Re: {s}"


def header(msg: dict, name: str) -> Optional[str]:
    for h in (msg.get("payload") or {}).get("headers") or []:
        if (h.get("name") or "").lower() == name.lower():
            return h.get("value")
    return None


def sender_email(msg: dict) -> str:
    return parseaddr(header(msg, "From") or "")[1].lower()


def _plain(part: dict) -> Optional[str]:
    if (part.get("mimeType") or "").startswith("text/plain") and (part.get("body") or {}).get("data"):
        data = part["body"]["data"]
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
    for p in part.get("parts") or []:
        t = _plain(p)
        if t:
            return t
    return None


_QUOTE_START = re.compile(r"^(On .{5,200}wrote:|-{2,}\s*Original Message|From: .+|>)", re.I)
_ON_LINE = re.compile(r"^On\s.{5,}", re.I)
_WROTE = re.compile(r"wrote:\s*$", re.I)
QUOTE_HEADER_MAX_LINES = 3  # mail apps wrap "On <date> <name> <address> wrote:" over up to three lines


def _quote_starts(lines: list[str], i: int) -> bool:
    line = lines[i].strip()
    if _QUOTE_START.match(line):
        return True
    if _ON_LINE.match(line):  # "On Thu, Nov 5, 2026 at 5:42 AM Srijan Patel <a@b.com>" / "wrote:"
        joined = " ".join(l.strip() for l in lines[i:i + QUOTE_HEADER_MAX_LINES])
        return bool(re.match(r"^On\s.{5,300}?wrote:", joined, re.I)) and any(_WROTE.search(l.strip()) for l in lines[i:i + QUOTE_HEADER_MAX_LINES])
    return False


def reply_text(msg: dict) -> str:
    """Just what they wrote: the plain-text part without the quoted earlier messages, trimmed."""
    text = _plain(msg.get("payload") or {}) or msg.get("snippet") or ""
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    for i, line in enumerate(lines):
        if _quote_starts(lines, i):
            break
        out.append(line)
    return "\n".join(out).strip()[: G.MAX_BODY_CHARS]


def same_text(a: Optional[str], b: Optional[str]) -> bool:
    """The same message, ignoring spacing and case (a pasted copy of an email, or an email pasted again)."""
    norm = lambda t: " ".join((t or "").lower().split())  # noqa: E731
    return bool(norm(a)) and norm(a) == norm(b)
