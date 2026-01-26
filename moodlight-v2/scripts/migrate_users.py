#!/usr/bin/env python3
"""
Migrate users from config.yaml to PostgreSQL database.
Reads existing streamlit_authenticator credentials and creates users in the new system.

Usage:
    python -m scripts.migrate_users
"""
import asyncio
import sys
from pathlib import Path

import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.services.auth import get_user_by_username, hash_password
from app.models import User


async def migrate_users(config_path: str = "../config.yaml"):
    """Migrate users from config.yaml to database."""
    # Load config.yaml
    config_file = Path(__file__).parent.parent.parent / "config.yaml"

    if not config_file.exists():
        print(f"Error: config.yaml not found at {config_file}")
        return False

    with open(config_file) as f:
        config = yaml.safe_load(f)

    credentials = config.get("credentials", {}).get("usernames", {})

    if not credentials:
        print("No users found in config.yaml")
        return False

    print(f"Found {len(credentials)} users to migrate")

    async with AsyncSessionLocal() as db:
        migrated = 0
        skipped = 0

        for username, user_data in credentials.items():
            # Check if already exists
            existing = await get_user_by_username(db, username)
            if existing:
                print(f"  Skipping '{username}' - already exists")
                skipped += 1
                continue

            # Create user (password hash is already bcrypt from config.yaml)
            email = user_data.get("email", f"{username}@moodlightintel.com")
            password_hash = user_data.get("password", "")

            # Note: password_hash from config.yaml is already hashed
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                tier="starter"  # Default tier for migrated users
            )
            db.add(user)
            migrated += 1
            print(f"  Migrated '{username}' ({email})")

        await db.commit()

        print(f"\nMigration complete: {migrated} migrated, {skipped} skipped")
        return True


if __name__ == "__main__":
    asyncio.run(migrate_users())
