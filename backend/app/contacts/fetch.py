"""Fetching a creator's link page or website safely. The URLs come from creators' bios (untrusted), so:
public http(s) hosts only (no private, loopback or cloud-metadata addresses, checked again on every redirect),
a short timeout, a size cap, and HTML or text only."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urljoin, urlsplit

import httpx

from app.contacts import constants as C

logger = logging.getLogger(__name__)


def host_of(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def host_matches(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


async def _public(host: str) -> bool:
    """True when every address the host resolves to is a public one."""
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        ip = ipaddress.ip_address(host)
        addrs = [ip]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError, OSError):
            return False
        addrs = [ipaddress.ip_address(i[4][0]) for i in infos]
    return bool(addrs) and all(a.is_global and not a.is_multicast for a in addrs)


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[tuple[str, str]]:
    """(final url, text) or None. Never raises."""
    current = url
    try:
        for _ in range(C.MAX_REDIRECTS + 1):
            parts = urlsplit(current)
            if parts.scheme not in ("http", "https") or not await _public(parts.hostname or ""):
                return None
            async with client.stream("GET", current, timeout=C.FETCH_TIMEOUT_S, follow_redirects=False) as r:
                if r.is_redirect and r.headers.get("location"):
                    current = urljoin(current, r.headers["location"])
                    continue
                if r.status_code != 200:
                    return None
                kind = r.headers.get("content-type", "").lower()
                if kind and "html" not in kind and "text" not in kind:
                    return None
                chunks, size = [], 0
                async for chunk in r.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= C.MAX_PAGE_BYTES:
                        break
                return str(r.url), b"".join(chunks)[: C.MAX_PAGE_BYTES].decode(r.encoding or "utf-8", "replace")
        return None
    except (httpx.HTTPError, ValueError, UnicodeError, OSError) as exc:
        logger.info("contact page fetch failed for %s: %s", host_of(url), type(exc).__name__)
        return None


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": C.USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
                             timeout=C.FETCH_TIMEOUT_S)


async def domain_accepts_mail(client: httpx.AsyncClient, domain: str, cache: dict) -> Optional[bool]:
    """Whether a domain can receive email (has MX, else an A record), via free DNS-over-HTTPS. None = couldn't
    tell (we keep the address then)."""
    domain = domain.lower()
    if host_matches(domain, C.KNOWN_MAIL_DOMAINS):
        return True
    if domain in cache:
        return cache[domain]
    answer: Optional[bool] = None
    for base in C.DOH_URLS:
        try:
            found = False
            for rtype in ("MX", "A"):
                r = await client.get(base, params={"name": domain, "type": rtype},
                                     headers={"Accept": "application/dns-json"}, timeout=4.0)
                r.raise_for_status()
                data = r.json()
                if data.get("Status") == 3:  # NXDOMAIN: the domain doesn't exist
                    break
                if any(a.get("type") in (15, 1) for a in data.get("Answer") or []):
                    found = True
                    break
            answer = found
            break
        except (httpx.HTTPError, ValueError):
            continue
    cache[domain] = answer
    return answer
