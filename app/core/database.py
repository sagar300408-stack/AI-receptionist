from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Create async database engine
# SQLite needs connect_args for enforcement of foreign keys
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
    future=True
)

# Async session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for SQLAlchemy ORM models
class Base(DeclarativeBase):
    pass

async def get_db_session() -> AsyncSession:
    """Dependency for providing database sessions to FastAPI routes."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
