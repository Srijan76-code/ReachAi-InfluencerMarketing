from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import DATABASE_URL


def _asyncpg_database_url(database_url: str) -> tuple[str, dict[str, bool]]:
    """Adapt libpq-style SSL URL options for asyncpg."""
    if not database_url:
        return database_url, {}

    parsed = urlsplit(database_url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    requires_ssl = False
    supported_query = []

    for key, value in query:
        if key == "sslmode":
            requires_ssl = value not in {"", "disable", "allow", "prefer"}
        elif key == "channel_binding":
            continue
        else:
            supported_query.append((key, value))

    normalized_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(supported_query),
            parsed.fragment,
        )
    )
    if not requires_ssl and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        requires_ssl = True

    return normalized_url, {"ssl": True} if requires_ssl else {}


asyncpg_database_url, connect_args = _asyncpg_database_url(DATABASE_URL)

# Vercel pauses an instance between requests, and Neon closes idle connections. A pooled connection can come back
# half-dead: without timeouts the pre-ping (or any query) waits on it until Vercel kills the request at 300 s. So:
# connecting gives up after CONNECT_TIMEOUT_S, a statement after STATEMENT_TIMEOUT_S, and connections are replaced
# well before Neon drops them.
CONNECT_TIMEOUT_S = 10
STATEMENT_TIMEOUT_S = 60
POOL_RECYCLE_S = 240

engine = create_async_engine(
    asyncpg_database_url,
    connect_args={**connect_args, "timeout": CONNECT_TIMEOUT_S, "command_timeout": STATEMENT_TIMEOUT_S},
    pool_recycle=POOL_RECYCLE_S,
    pool_pre_ping=True,  # test connection before use; discard if dead
    pool_timeout=CONNECT_TIMEOUT_S,  # waiting for a free pooled connection
)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session