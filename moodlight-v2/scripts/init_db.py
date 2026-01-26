#!/usr/bin/env python3
"""
Initialize the database - creates all tables.
Run this script once before starting the application.

Usage:
    python -m scripts.init_db
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_engine, Base
from app.models import User, UserSession, NewsItem, Brief


async def init_database():
    """Create all tables in the database."""
    print("Creating database tables...")

    async with async_engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    print("Database tables created successfully:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")


if __name__ == "__main__":
    asyncio.run(init_database())
