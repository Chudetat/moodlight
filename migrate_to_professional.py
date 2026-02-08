"""
Migration script: Update tier structure from Foundation to Professional.

Changes:
- Rename 'foundation' tier -> 'professional'
- Professional tier now has unlimited briefs (no credit tracking needed)
- Update default tier for new users

Pricing model:
- Professional: $899/month (all-access, unlimited briefs)
- Enterprise: Custom pricing

Run once, then delete this file.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    # Step 1: Rename foundation -> professional
    print("Updating 'foundation' tier to 'professional'...")
    result = conn.execute(text("UPDATE users SET tier = 'professional' WHERE tier = 'foundation'"))
    print(f"  Updated {result.rowcount} users")

    # Step 2: Update default tier for new users
    print("Setting default tier to 'professional'...")
    conn.execute(text("ALTER TABLE users ALTER COLUMN tier SET DEFAULT 'professional'"))

    conn.commit()
    print("\n✅ Migration complete!")
    print("   - All foundation users are now professional")
    print("   - Professional tier has unlimited briefs")
    print("   - New users default to professional tier")
    print("\nYou can delete this file now.")
