# Update generate_brief.py to use PostgreSQL

old_code = '''def load_recent_data():
    """Load last 24 hours of intelligence data"""
    df = pd.read_csv("news_scored.csv")'''

new_code = '''def load_recent_data():
    """Load last 24 hours of intelligence data"""
    # Try PostgreSQL first
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        try:
            from sqlalchemy import create_engine
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            engine = create_engine(db_url)
            df = pd.read_sql("SELECT * FROM news_scored", engine)
            if not df.empty:
                print(f"✅ Loaded {len(df)} rows from PostgreSQL")
                df['created_at'] = pd.to_datetime(df['created_at'], utc=True, errors='coerce')
                cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=7)
                return df[df['created_at'] >= cutoff]
        except Exception as e:
            print(f"DB error: {e}")
    # Fallback to CSV
    df = pd.read_csv("news_scored.csv")'''

with open('generate_brief.py', 'r') as f:
    content = f.read()

content = content.replace(old_code, new_code)

with open('generate_brief.py', 'w') as f:
    f.write(content)

print("✅ Updated generate_brief.py to use PostgreSQL")
