"""Initialize database tables."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.database.connection import Base, engine
from app.infrastructure.database import models  # noqa: F401 - Import all models


async def init_database():
    """Create all database tables."""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())
