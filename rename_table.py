import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ DATABASE_URL not found in .env")
    exit(1)

db_url = db_url.replace("postgres://", "postgresql://", 1)
engine = create_engine(db_url)

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE news_data RENAME TO news_scored"))
    conn.commit()
    print("✅ Renamed news_data to news_scored")
