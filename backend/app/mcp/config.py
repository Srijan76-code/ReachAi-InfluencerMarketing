"""MCP settings, read from the environment on each call so tests and deploys can change them."""

import os
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

DEFAULT_PUBLIC_URL = "http://localhost:8000/api/mcp"
DEFAULT_CLERK_JWKS_URL = "https://tidy-redfish-49.clerk.accounts.dev/.well-known/jwks.json"
DEFAULT_APP_URL = "http://localhost:3000"

# How long a key's last_used_at is left alone, so a busy agent does not write on every call.
API_KEY_TOUCH_SECONDS = 300

# Hard limits so one tool call never returns more than a client can show (claude.ai drops
# results over ~150,000 characters; Claude Code over 25,000 tokens).
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 25
MAX_TEXT_CHARS = 20_000


def agent_runs_per_day() -> int:
    """How many creator searches one user's agents may start per day (each costs YouTube quota and Jev calls).
    Raised from 3 to 10 on Nov 13: every search now costs credits shown before it starts, so credits limit spend;
    10 keeps one user well inside the YouTube quota (spec §1)."""
    try:
        return max(0, int(os.getenv("MCP_RUNS_PER_DAY", "10")))
    except ValueError:
        return 10


def public_url() -> str:
    """Full public URL of the MCP endpoint, e.g. https://reachai.example/api/mcp (no trailing slash)."""
    return os.getenv("MCP_PUBLIC_URL", DEFAULT_PUBLIC_URL).rstrip("/")


def endpoint_path() -> str:
    return urlsplit(public_url()).path or "/api/mcp"


def clerk_issuer_url() -> str:
    explicit = os.getenv("CLERK_ISSUER_URL")
    if explicit:
        return explicit.rstrip("/")
    jwks = os.getenv("CLERK_JWKS_URL", DEFAULT_CLERK_JWKS_URL)
    return jwks.split("/.well-known/")[0].rstrip("/")


def clerk_secret_key() -> str | None:
    return os.getenv("CLERK_SECRET_KEY") or None


def app_url() -> str:
    """Base URL of the web app, used for "open in ReachAI" links."""
    return os.getenv("APP_URL", DEFAULT_APP_URL).rstrip("/")


def allowed_hosts() -> list[str]:
    host = urlsplit(public_url()).netloc
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    if host:
        hosts.append(host)
    return hosts


def allowed_origins() -> list[str]:
    parts = urlsplit(public_url())
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if parts.scheme and parts.netloc:
        origins.append(f"{parts.scheme}://{parts.netloc}")
    return origins
