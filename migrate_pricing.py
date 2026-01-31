"""
Migration script: Update users table for new Foundation + pay-per-brief pricing model.

Changes:
- Rename briefs_used -> brief_credits
- Drop briefs_reset_date column
- Drop extra_briefs_addon column
- Update tier defaults from 'solo'/'starter' to 'foundation'
- Enterprise users keep their tier unchanged

Run once, then delete this file.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    # Step 1: Rename briefs_used to brief_credits
    print("Renaming briefs_used -> brief_credits...")
    conn.execute(text("ALTER TABLE users RENAME COLUMN briefs_used TO brief_credits"))

    # Step 2: Update any old tier names to 'foundation'
    print("Updating old tier names to 'foundation'...")
    conn.execute(text("UPDATE users SET tier = 'foundation' WHERE tier IN ('solo', 'starter', 'pro', 'team')"))

    # Step 3: Drop old columns
    print("Dropping briefs_reset_date...")
    conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS briefs_reset_date"))

    print("Dropping extra_briefs_addon...")
    conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS extra_briefs_addon"))

    # Step 4: Set default tier for new users to 'foundation'
    print("Setting default tier to 'foundation'...")
    conn.execute(text("ALTER TABLE users ALTER COLUMN tier SET DEFAULT 'foundation'"))

    # Step 5: Set brief_credits default to 0
    print("Setting default brief_credits to 0...")
    conn.execute(text("ALTER TABLE users ALTER COLUMN brief_credits SET DEFAULT 0"))

    # Step 6: Reset admin brief_credits (enterprise = unlimited, credits field unused)
    print("Resetting admin brief_credits to 0 (enterprise has unlimited)...")
    conn.execute(text("UPDATE users SET brief_credits = 0 WHERE tier = 'enterprise'"))

    conn.commit()
    print("\n✅ Migration complete! Users table updated for new pricing model.")
    print("You can delete this file now.")
