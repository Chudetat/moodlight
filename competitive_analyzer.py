#!/usr/bin/env python
"""
Competitive analysis for Moodlight's War Room.
Computes comparative VLDS, share of voice, and competitive gaps
between a watched brand and its discovered competitors.
"""

import os
import json
from dotenv import load_dotenv
from vlds_helper import calculate_brand_vlds
from alert_detector import _filter_by_brand

load_dotenv()


def compute_competitive_snapshot(df_news, df_social, brand_name, competitors):
    """Compute a full competitive snapshot for a brand vs its competitors.

    Args:
        df_news: News dataframe
        df_social: Social dataframe
        brand_name: The watched brand
        competitors: List of dicts with 'competitor_name' key

    Returns dict:
        {
            "BrandName": {"vlds": {...}, "mention_count": N},
            "Competitor1": {"vlds": {...}, "mention_count": N},
            ...
            "share_of_voice": {"BrandName": 35.0, "Competitor1": 25.0, ...},
            "competitive_gaps": {"velocity_gap": ..., "density_gap": ...}
        }
    """
    import pandas as pd

    all_names = [brand_name] + [c["competitor_name"] for c in competitors]
    snapshot = {}
    total_mentions = 0

    for name in all_names:
        brand_df = pd.concat([
            _filter_by_brand(df_news, name),
            _filter_by_brand(df_social, name),
        ], ignore_index=True)

        mention_count = len(brand_df)
        total_mentions += mention_count

        vlds = None
        if not brand_df.empty and len(brand_df) >= 5:
            vlds = calculate_brand_vlds(brand_df)

        snapshot[name] = {
            "vlds": vlds,
            "mention_count": mention_count,
        }

    # Share of voice (percentage of total mentions)
    sov = {}
    for name in all_names:
        count = snapshot[name]["mention_count"]
        sov[name] = round((count / total_mentions * 100) if total_mentions > 0 else 0, 1)
    snapshot["share_of_voice"] = sov

    # Competitive gaps (brand vs average competitor)
    brand_vlds = snapshot[brand_name].get("vlds") or {}
    comp_vlds_list = [
        snapshot[c["competitor_name"]].get("vlds") or {}
        for c in competitors
    ]
    comp_vlds_list = [v for v in comp_vlds_list if v]  # Filter out empties

    gaps = {}
    if brand_vlds and comp_vlds_list:
        for metric in ["velocity", "longevity", "density", "scarcity"]:
            brand_val = brand_vlds.get(metric, 0)
            avg_comp = sum(v.get(metric, 0) for v in comp_vlds_list) / len(comp_vlds_list)
            gaps[f"{metric}_gap"] = round(brand_val - avg_comp, 3)
            gaps[f"{metric}_brand"] = round(brand_val, 3)
            gaps[f"{metric}_comp_avg"] = round(avg_comp, 3)
    snapshot["competitive_gaps"] = gaps

    return snapshot


def get_previous_snapshot(engine, brand_name):
    """Load the most recent competitive snapshot from DB for comparison."""
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT snapshot_data FROM competitive_snapshots
                    WHERE brand_name = :brand
                    ORDER BY created_at DESC LIMIT 1
                """),
                {"brand": brand_name},
            )
            row = result.fetchone()
            if row:
                return json.loads(row[0])
    except Exception as e:
        print(f"  Could not load previous snapshot: {e}")

    return None


def store_snapshot(engine, brand_name, snapshot):
    """Store a competitive snapshot to DB."""
    from sqlalchemy import text

    try:
        # Make snapshot JSON-serializable
        serializable = _make_serializable(snapshot)

        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO competitive_snapshots (brand_name, snapshot_data)
                    VALUES (:brand, :data)
                """),
                {"brand": brand_name, "data": json.dumps(serializable)},
            )
            conn.commit()
    except Exception as e:
        print(f"  Could not store snapshot: {e}")


def _make_serializable(obj):
    """Convert numpy/pandas types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        return obj.item()
    return obj


def generate_competitive_insight(engine, snapshot, brand_name):
    """Generate an AI-powered competitive positioning analysis.

    Returns a string with the analysis, or None if unavailable.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic

        # Build a concise summary for the prompt
        sov = snapshot.get("share_of_voice", {})
        gaps = snapshot.get("competitive_gaps", {})

        competitors_info = []
        for name, data in snapshot.items():
            if name in ("share_of_voice", "competitive_gaps"):
                continue
            if name == brand_name:
                continue
            vlds = data.get("vlds") or {}
            competitors_info.append(
                f"- {name}: {data['mention_count']} mentions, "
                f"SOV {sov.get(name, 0)}%, "
                f"V={vlds.get('velocity', 'N/A')}, "
                f"D={vlds.get('density', 'N/A')}"
            )

        brand_data = snapshot.get(brand_name, {})
        brand_vlds = brand_data.get("vlds") or {}

        prompt = (
            f"Analyze the competitive positioning for '{brand_name}' based on this data:\n\n"
            f"Brand: {brand_name}\n"
            f"- Mentions: {brand_data.get('mention_count', 0)}\n"
            f"- Share of Voice: {sov.get(brand_name, 0)}%\n"
            f"- VLDS: V={brand_vlds.get('velocity', 'N/A')}, "
            f"L={brand_vlds.get('longevity', 'N/A')}, "
            f"D={brand_vlds.get('density', 'N/A')}, "
            f"S={brand_vlds.get('scarcity', 'N/A')}\n\n"
            f"Competitors:\n" + "\n".join(competitors_info) + "\n\n"
            f"Gaps (brand - avg competitor):\n"
            f"- Velocity: {gaps.get('velocity_gap', 'N/A')}\n"
            f"- Density: {gaps.get('density_gap', 'N/A')}\n\n"
            f"Provide a brief (3-4 sentences) competitive positioning insight. "
            f"Focus on actionable observations: where the brand leads, where it trails, "
            f"and one specific strategic recommendation."
        )

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    except Exception as e:
        print(f"  Competitive insight generation failed: {e}")
        return None
