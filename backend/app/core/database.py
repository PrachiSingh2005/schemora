from typing import AsyncGenerator
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Schemora architecture requires PostgreSQL + pgvector exclusively
db_url = settings.DATABASE_URL
if "sqlite" in db_url:
    raise RuntimeError(
        f"Invalid DATABASE_URL configuration: '{db_url}'. "
        "Schemora backend architecture requires PostgreSQL + pgvector exclusively. SQLite is not permitted."
    )

try:
    import asyncpg
    has_asyncpg = True
except ImportError:
    has_asyncpg = False

try:
    import psycopg
    has_psycopg = True
except ImportError:
    has_psycopg = False

if not has_asyncpg and not has_psycopg:
    raise ImportError(
        "Neither 'asyncpg' nor 'psycopg' PostgreSQL driver is installed in this Python environment. "
        "Please run commands from the backend directory: 'cd Schemora/backend' and use 'uv run python ...'"
    )

if db_url.startswith("postgresql://"):
    if has_asyncpg:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://")
elif db_url.startswith("postgresql+asyncpg://") and not has_asyncpg and has_psycopg:
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
elif db_url.startswith("postgresql+psycopg://") and has_asyncpg:
    db_url = db_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")

connect_args = {}
if "asyncpg" in db_url:
    connect_args["command_timeout"] = 60
elif "psycopg" in db_url:
    connect_args["connect_timeout"] = 60

engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Alias for backwards compatibility across services/scripts
async_session_maker = AsyncSessionLocal


class Base(DeclarativeBase):
    """Base model class for SQLAlchemy."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for acquiring async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

