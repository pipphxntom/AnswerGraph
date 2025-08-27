from typing import AsyncGenerator
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, DeclarativeBase
from sqlalchemy.pool import NullPool

from src.core.config import settings

# Get database URL from environment or settings
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)

# Create async engine
engine = create_async_engine(
    DATABASE_URL, 
    echo=settings.DEBUG,
    future=True,
    # Use connection pooling in production, disable in testing
    poolclass=NullPool if os.getenv("TESTING") else None
)

# Create async session factory
async_session_factory = async_sessionmaker(
    engine, 
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Define base model class
class Base(DeclarativeBase):
    """Base model class for all SQLAlchemy models."""
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting an async database session.
    Use this as a FastAPI dependency.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# For backwards compatibility
get_session = get_async_session
