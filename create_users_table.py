import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            tier VARCHAR(20) DEFAULT 'solo',
            briefs_used INTEGER DEFAULT 0,
            briefs_reset_date DATE DEFAULT CURRENT_DATE,
            stripe_customer_id VARCHAR(100),
            stripe_subscription_id VARCHAR(100),
            extra_briefs_addon BOOLEAN DEFAULT FALSE,
            extra_seats INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.commit()
    print("✅ Users table created successfully")
