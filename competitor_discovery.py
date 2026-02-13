#!/usr/bin/env python
"""
Competitor discovery for Moodlight's Competitive War Room.
Uses Claude to identify 3-5 competitors for a watched brand,
then caches results in the DB so discovery only happens once per brand.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()


def ensure_competitor_tables(engine):
    """Create brand_competitors and competitive_snapshots tables."""
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS brand_competitors (
                id SERIAL PRIMARY KEY,
                brand_name VARCHAR(200) NOT NULL,
                competitor_name VARCHAR(200) NOT NULL,
                confidence FLOAT DEFAULT 0.0,
                reasoning TEXT,
                discovered_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(brand_name, competitor_name)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS competitive_snapshots (
                id SERIAL PRIMARY KEY,
                brand_name VARCHAR(200) NOT NULL,
                snapshot_data TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


def get_cached_competitors(engine, brand_name):
    """Load competitors from DB cache. Returns list of dicts or empty list."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT competitor_name, confidence, reasoning
                    FROM brand_competitors
                    WHERE brand_name = :brand
                    ORDER BY confidence DESC
                """),
                {"brand": brand_name},
            )
            rows = result.fetchall()
            return [
                {
                    "competitor_name": row[0],
                    "confidence": row[1],
                    "reasoning": row[2],
                }
                for row in rows
            ]
    except Exception as e:
        print(f"  Could not load cached competitors: {e}")
        return []


def discover_competitors(brand_name):
    """Use Claude to identify 3-5 competitors for a brand.

    Returns list of dicts: [{competitor_name, confidence, reasoning}, ...]
    Returns empty list if API key is missing or call fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — cannot discover competitors")
        return []

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Identify 3-5 direct competitors for the brand/company '{brand_name}'. "
                        f"For each competitor, provide:\n"
                        f"1. The competitor name (as commonly known)\n"
                        f"2. A confidence score (0.0-1.0) for how direct a competitor they are\n"
                        f"3. A brief one-sentence reasoning\n\n"
                        f"Respond ONLY with a JSON array, no other text:\n"
                        f'[{{"competitor_name": "...", "confidence": 0.9, "reasoning": "..."}}]'
                    ),
                }
            ],
        )

        text = response.content[0].text.strip()
        # Handle potential markdown code fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        competitors = json.loads(text)

        # Validate structure
        validated = []
        for comp in competitors[:5]:  # Max 5
            if isinstance(comp, dict) and "competitor_name" in comp:
                validated.append({
                    "competitor_name": comp["competitor_name"],
                    "confidence": float(comp.get("confidence", 0.5)),
                    "reasoning": comp.get("reasoning", ""),
                })

        print(f"  Discovered {len(validated)} competitors for {brand_name}")
        return validated

    except Exception as e:
        print(f"  Competitor discovery failed: {e}")
        return []


def cache_competitors(engine, brand_name, competitors):
    """Store discovered competitors in DB."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            for comp in competitors:
                conn.execute(
                    text("""
                        INSERT INTO brand_competitors
                            (brand_name, competitor_name, confidence, reasoning)
                        VALUES (:brand, :comp, :conf, :reason)
                        ON CONFLICT (brand_name, competitor_name) DO NOTHING
                    """),
                    {
                        "brand": brand_name,
                        "comp": comp["competitor_name"],
                        "conf": comp["confidence"],
                        "reason": comp.get("reasoning", ""),
                    },
                )
            conn.commit()
    except Exception as e:
        print(f"  Could not cache competitors: {e}")


def ensure_competitors_cached(engine, brand_name):
    """Main entry point: return competitors from cache or discover them.

    - Checks DB cache first
    - If empty: calls Claude to discover, then caches
    - Returns list of competitor dicts
    """
    # Check cache
    cached = get_cached_competitors(engine, brand_name)
    if cached:
        return cached

    # Discover and cache
    print(f"  Discovering competitors for {brand_name}...")
    competitors = discover_competitors(brand_name)
    if competitors:
        cache_competitors(engine, brand_name, competitors)

    return competitors
