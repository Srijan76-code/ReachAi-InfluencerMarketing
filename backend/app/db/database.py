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

engine = create_async_engine(
    asyncpg_database_url,
    connect_args=connect_args,
    pool_recycle=1800,   # recycle connections after 30 min
    pool_pre_ping=True,  # test connection before use; discard if dead
)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session