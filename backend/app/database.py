from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# ---------------------------------------------------------------------------
# Pool config — Vercel functions are single-process; keep pool tiny to avoid
# exceeding Supabase connection limits on the free tier.
# When using the Supabase Supavisor transaction pooler (port 6543) asyncpg
# must disable prepared-statement caching.
# ---------------------------------------------------------------------------
_connect_args: dict = {
    "timeout": settings.HEALTHCHECK_TIMEOUT_SECONDS,
    "command_timeout": settings.HEALTHCHECK_TIMEOUT_SECONDS,
}
if ":6543" in settings.DATABASE_URL or "pooler" in settings.DATABASE_URL.lower():
    _connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=300,
    echo=settings.DEBUG,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def close_database() -> None:
    """Release pooled connections during application shutdown."""
    await engine.dispose()
