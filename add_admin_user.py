import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (username, email, password_hash, tier)
        VALUES ('admin', 'intel@moodlightintel.com', '$2b$12$OXpPytylZIVxruJW3ZlJaObkM3r1LKB6ec9So45oYKm2hqBOMhh36', 'enterprise')
        ON CONFLICT (username) DO NOTHING
    """))
    conn.commit()
    print("✅ Admin user added with enterprise tier")
