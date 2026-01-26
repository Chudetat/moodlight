#!/usr/bin/env python3
"""
Add a new user to the database.

Usage:
    python -m scripts.add_user <username> <email> <password> [tier]

Example:
    python -m scripts.add_user admin admin@example.com secretpassword pro
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.services.auth import create_user, get_user_by_username


async def add_user(username: str, email: str, password: str, tier: str = "starter"):
    """Add a new user to the database."""
    async with AsyncSessionLocal() as db:
        # Check if user already exists
        existing = await get_user_by_username(db, username)
        if existing:
            print(f"Error: User '{username}' already exists")
            return False

        # Create user
        user = await create_user(db, username, email, password, tier)
        print(f"User created successfully:")
        print(f"  Username: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  Tier: {user.tier}")
        return True


def main():
    if len(sys.argv) < 4:
        print("Usage: python -m scripts.add_user <username> <email> <password> [tier]")
        print("Tier options: starter (default), pro, enterprise")
        sys.exit(1)

    username = sys.argv[1]
    email = sys.argv[2]
    password = sys.argv[3]
    tier = sys.argv[4] if len(sys.argv) > 4 else "starter"

    if tier not in ["starter", "pro", "enterprise"]:
        print(f"Error: Invalid tier '{tier}'. Must be starter, pro, or enterprise")
        sys.exit(1)

    success = asyncio.run(add_user(username, email, password, tier))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
