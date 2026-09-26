from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import DATABASE_URL

connect_args = {}
if DATABASE_URL and "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    connect_args["ssl"] = "require"

engine = create_async_engine(
    DATABASE_URL or "postgresql+asyncpg://postgres:postgres@localhost:5432/reachai",
    connect_args=connect_args
)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session