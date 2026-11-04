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


def reply_text(msg: dict) -> str:
    """Just what they wrote: the plain-text part without the quoted earlier messages, trimmed."""
    text = _plain(msg.get("payload") or {}) or msg.get("snippet") or ""
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if _QUOTE_START.match(line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()[: G.MAX_BODY_CHARS]
