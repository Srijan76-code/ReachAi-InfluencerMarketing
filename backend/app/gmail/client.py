"""Calls to Google (sign-in and the Gmail API) over httpx. The Gmail API is free, so there's no cost row."""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.gmail import constants as G


class GmailError(RuntimeError):
    """Something went wrong talking to Google; `revoked` means the founder must reconnect."""

    def __init__(self, message: str, revoked: bool = False):
        super().__init__(message)
        self.revoked = revoked


def client_id() -> Optional[str]:
    return os.getenv("GOOGLE_OAUTH_CLIENT_ID")


def configured() -> bool:
    return bool(client_id() and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"))


def auth_url(redirect_uri: str, state: str, login_hint: Optional[str] = None) -> str:
    q = {"client_id": client_id(), "redirect_uri": redirect_uri, "response_type": "code", "scope": " ".join(G.SCOPES),
         "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state}
    if login_hint:
        q["login_hint"] = login_hint
    return f"{G.AUTH_URL}?{urlencode(q)}"


async def _post(url: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=G.HTTP_TIMEOUT_SECONDS) as c:
        r = await c.post(url, data=data)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400:
        raise GmailError(body.get("error_description") or body.get("error") or f"Google said {r.status_code}",
                         revoked=body.get("error") == "invalid_grant")
    return body


async def exchange_code(code: str, redirect_uri: str) -> dict:
    """→ {"access_token", "refresh_token", "scope", ...}"""
    return await _post(G.TOKEN_URL, {"code": code, "client_id": client_id(), "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
                                     "redirect_uri": redirect_uri, "grant_type": "authorization_code"})


async def access_token(refresh_token: str) -> str:
    body = await _post(G.TOKEN_URL, {"refresh_token": refresh_token, "client_id": client_id(),
                                     "client_secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"), "grant_type": "refresh_token"})
    return body["access_token"]


async def revoke(token: str) -> None:
    try:
        await _post(G.REVOKE_URL, {"token": token})
    except GmailError:
        pass  # already revoked or expired: nothing to undo


async def _api(method: str, path: str, token: str, **kw) -> dict:
    async with httpx.AsyncClient(timeout=G.HTTP_TIMEOUT_SECONDS) as c:
        r = await c.request(method, f"{G.API}{path}", headers={"Authorization": f"Bearer {token}"}, **kw)
    if r.status_code == 401:
        raise GmailError("Gmail access was removed. Connect Gmail again.", revoked=True)
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message")
        except Exception:
            msg = None
        raise GmailError(msg or f"Gmail said {r.status_code}")
    return r.json()


async def profile(token: str) -> dict:
    return await _api("GET", "/profile", token)  # {"emailAddress": ...}


async def display_name(token: str) -> Optional[str]:
    """The sender name the founder set in Gmail for their main address (gmail.readonly covers this)."""
    try:
        body = await _api("GET", "/settings/sendAs", token)
    except GmailError:
        return None
    for a in body.get("sendAs") or []:
        if a.get("isPrimary") and (a.get("displayName") or "").strip():
            return a["displayName"].strip()
    return None


async def send(token: str, raw: str, thread_id: Optional[str] = None) -> dict:
    body = {"raw": raw}
    if thread_id:
        body["threadId"] = thread_id
    return await _api("POST", "/messages/send", token, json=body)  # {"id", "threadId"}


async def message(token: str, message_id: str) -> dict:
    return await _api("GET", f"/messages/{message_id}", token, params={"format": "metadata", "metadataHeaders": ["Message-ID", "Subject"]})


async def thread(token: str, thread_id: str) -> dict:
    return await _api("GET", f"/threads/{thread_id}", token, params={"format": "full"})
