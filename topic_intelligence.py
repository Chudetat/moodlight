"""
topic_intelligence.py
Shared intelligence layer for Brief and Radar products.

Computes topic deltas, staleness penalties, novelty boosts,
and returns ranked topics with "why this is interesting today" context.
"""

import os
import pandas as pd
from datetime import datetime, timezone, timedelta
from sqlalchemy import text as sql_text


# ── Snapshot table (stores VLDS history for delta computation) ──

def ensure_snapshot_table(engine):
    """Create topic_vlds_snapshots if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS topic_vlds_snapshots (
                id SERIAL PRIMARY KEY,
                snapshot_date DATE NOT NULL,
                topic VARCHAR(200) NOT NULL,
                velocity_score FLOAT,
                longevity_score FLOAT,
                density_score FLOAT,
                scarcity_score FLOAT,
                post_count INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(snapshot_date, topic)
            )
        """))
        conn.commit()


def save_vlds_snapshot(engine):
    """Snapshot current VLDS scores into history table. Called after calculate scripts run."""
    ensure_snapshot_table(engine)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with engine.connect() as conn:
        # Read current values from the 3 topic tables
        try:
            lon_df = pd.read_sql(sql_text("SELECT topic, velocity_score, longevity_score FROM topic_longevity"), engine)
        except Exception:
            lon_df = pd.DataFrame()
        try:
            den_df = pd.read_sql(sql_text("SELECT topic, density_score FROM topic_density"), engine)
        except Exception:
            den_df = pd.DataFrame()
        try:
            scar_df = pd.read_sql(sql_text("SELECT topic, scarcity_score FROM topic_scarcity"), engine)
        except Exception:
            scar_df = pd.DataFrame()

        # Merge
        topics = set()
        for df in [lon_df, den_df, scar_df]:
            if not df.empty and "topic" in df.columns:
                topics.update(df["topic"].tolist())

        if not topics:
            return

        for topic in topics:
            vel = lon_df.loc[lon_df["topic"] == topic, "velocity_score"].iloc[0] if not lon_df.empty and topic in lon_df["topic"].values else None
            lon = lon_df.loc[lon_df["topic"] == topic, "longevity_score"].iloc[0] if not lon_df.empty and topic in lon_df["topic"].values else None
            den = den_df.loc[den_df["topic"] == topic, "density_score"].iloc[0] if not den_df.empty and topic in den_df["topic"].values else None
            scar = scar_df.loc[scar_df["topic"] == topic, "scarcity_score"].iloc[0] if not scar_df.empty and topic in scar_df["topic"].values else None

            # Get post count from longevity table (most complete)
            pc = lon_df.loc[lon_df["topic"] == topic, "post_count"].iloc[0] if not lon_df.empty and "post_count" in lon_df.columns and topic in lon_df["topic"].values else None

            conn.execute(sql_text("""
                INSERT INTO topic_vlds_snapshots (snapshot_date, topic, velocity_score, longevity_score, density_score, scarcity_score, post_count)
                VALUES (:date, :topic, :vel, :lon, :den, :scar, :pc)
                ON CONFLICT (snapshot_date, topic) DO UPDATE SET
                    velocity_score = EXCLUDED.velocity_score,
                    longevity_score = EXCLUDED.longevity_score,
                    density_score = EXCLUDED.density_score,
                    scarcity_score = EXCLUDED.scarcity_score,
                    post_count = EXCLUDED.post_count
            """), {"date": today, "topic": topic, "vel": vel, "lon": lon, "den": den, "scar": scar, "pc": pc})

        conn.commit()
        print(f"  Saved VLDS snapshot for {len(topics)} topics ({today})")


# ── Output history (tracks what appeared in previous briefs/radars) ──

def ensure_output_history_table(engine):
    """Create output_topic_history if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS output_topic_history (
                id SERIAL PRIMARY KEY,
                output_type VARCHAR(20) NOT NULL,
                output_date DATE NOT NULL,
                topic VARCHAR(200) NOT NULL,
                section VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


def log_output_topics(engine, output_type, topics, section=None):
    """Log which topics appeared in a brief or radar output."""
    ensure_output_history_table(engine)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with engine.connect() as conn:
        for topic in topics:
            conn.execute(sql_text("""
                INSERT INTO output_topic_history (output_type, output_date, topic, section)
                VALUES (:type, :date, :topic, :section)
            """), {"type": output_type, "date": today, "topic": topic, "section": section})
        conn.commit()


def get_topic_staleness(engine, output_type, lookback_days=7):
    """Return dict of topic -> {last_appeared, consecutive_days, appearances}."""
    ensure_output_history_table(engine)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    with engine.connect() as conn:
        rows = conn.execute(sql_text("""
            SELECT topic, output_date
            FROM output_topic_history
            WHERE output_type = :type AND output_date >= :cutoff
            ORDER BY output_date DESC
        """), {"type": output_type, "cutoff": cutoff}).fetchall()

    staleness = {}
    for topic, date in rows:
        if topic not in staleness:
            staleness[topic] = {"last_appeared": date, "appearances": 0, "dates": set()}
        staleness[topic]["appearances"] += 1
        staleness[topic]["dates"].add(date)

    # Compute consecutive days from today
    today = datetime.now(timezone.utc).date()
    for topic, info in staleness.items():
        consec = 0
        for i in range(lookback_days):
            check_date = today - timedelta(days=i + 1)
            if check_date in info["dates"]:
                consec += 1
            else:
                break
        info["consecutive_days"] = consec

    return staleness


# ── Delta computation ──

def compute_vlds_deltas(engine, hours_ago=24):
    """Compare current VLDS to a previous snapshot. Returns DataFrame with delta columns."""
    cutoff_date = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).strftime("%Y-%m-%d")

    # Current values
    try:
        current = pd.read_sql(sql_text("""
            SELECT topic, velocity_score AS velocity, longevity_score AS longevity
            FROM topic_longevity
        """), engine)
    except Exception:
        current = pd.DataFrame()

    try:
        den = pd.read_sql(sql_text("SELECT topic, density_score AS density FROM topic_density"), engine)
        if not current.empty and not den.empty:
            current = current.merge(den, on="topic", how="outer")
        elif not den.empty:
            current = den
    except Exception:
        pass

    try:
        scar = pd.read_sql(sql_text("SELECT topic, scarcity_score AS scarcity FROM topic_scarcity"), engine)
        if not current.empty and not scar.empty:
            current = current.merge(scar, on="topic", how="outer")
        elif not scar.empty:
            current = scar
    except Exception:
        pass

    if current.empty:
        return pd.DataFrame()

    # Previous snapshot
    try:
        prev = pd.read_sql(sql_text("""
            SELECT topic,
                   velocity_score AS prev_velocity,
                   longevity_score AS prev_longevity,
                   density_score AS prev_density,
                   scarcity_score AS prev_scarcity
            FROM topic_vlds_snapshots
            WHERE snapshot_date <= :cutoff
            ORDER BY snapshot_date DESC
        """), engine, params={"cutoff": cutoff_date})

        if not prev.empty:
            # Keep only latest snapshot per topic
            prev = prev.drop_duplicates(subset=["topic"], keep="first")
            current = current.merge(prev, on="topic", how="left")

            # Compute deltas
            for dim in ["velocity", "longevity", "density", "scarcity"]:
                if dim in current.columns and f"prev_{dim}" in current.columns:
                    current[f"{dim}_delta"] = current[dim] - current[f"prev_{dim}"]
                else:
                    current[f"{dim}_delta"] = None
        else:
            for dim in ["velocity", "longevity", "density", "scarcity"]:
                current[f"{dim}_delta"] = None
    except Exception:
        for dim in ["velocity", "longevity", "density", "scarcity"]:
            current[f"{dim}_delta"] = None

    return current


# ── Empathy deltas ──

def compute_empathy_deltas(engine):
    """Compare empathy scores between last 24h and previous 24h by topic."""
    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_48h = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        recent = pd.read_sql(sql_text("""
            SELECT topic, AVG(empathy_score) AS empathy_recent, COUNT(*) AS count_recent
            FROM news_scored
            WHERE created_at >= :cutoff AND empathy_score IS NOT NULL
            GROUP BY topic
        """), engine, params={"cutoff": cutoff_24h})

        previous = pd.read_sql(sql_text("""
            SELECT topic, AVG(empathy_score) AS empathy_previous, COUNT(*) AS count_previous
            FROM news_scored
            WHERE created_at >= :cutoff_48h AND created_at < :cutoff_24h AND empathy_score IS NOT NULL
            GROUP BY topic
        """), engine, params={"cutoff_48h": cutoff_48h, "cutoff_24h": cutoff_24h})

        if recent.empty:
            return pd.DataFrame()

        merged = recent.merge(previous, on="topic", how="left")
        merged["empathy_delta"] = merged["empathy_recent"] - merged["empathy_previous"].fillna(merged["empathy_recent"])
        return merged

    except Exception:
        return pd.DataFrame()


# ── Main intelligence computation ──

def compute_topic_intelligence(engine, output_type="brief"):
    """
    Master function: returns ranked topics with deltas, staleness, novelty, and radar scores.

    Returns a list of dicts, each with:
        topic, velocity, longevity, density, scarcity,
        velocity_delta, density_delta, scarcity_delta,
        empathy_recent, empathy_delta,
        staleness_penalty, novelty_boost, radar_score,
        why_interesting (human-readable reason)
    """
    vlds = compute_vlds_deltas(engine)
    if vlds.empty:
        return []

    empathy = compute_empathy_deltas(engine)
    staleness = get_topic_staleness(engine, output_type)

    results = []
    for _, row in vlds.iterrows():
        topic = row["topic"]

        # VLDS values
        vel = row.get("velocity") or 0
        lon = row.get("longevity") or 0
        den = row.get("density") or 0
        scar = row.get("scarcity") or 0

        # Deltas
        vel_d = row.get("velocity_delta") or 0
        den_d = row.get("density_delta") or 0
        scar_d = row.get("scarcity_delta") or 0

        # Empathy
        emp_recent = None
        emp_delta = None
        if not empathy.empty and topic in empathy["topic"].values:
            emp_row = empathy[empathy["topic"] == topic].iloc[0]
            emp_recent = emp_row.get("empathy_recent")
            emp_delta = emp_row.get("empathy_delta")

        # Staleness penalty
        stale = staleness.get(topic, {})
        consec = stale.get("consecutive_days", 0)
        appearances = stale.get("appearances", 0)
        # Exponential penalty: 1.0 (never appeared) → 0.5 (1 day) → 0.25 (2 days) → etc.
        staleness_penalty = 1.0 / (2 ** consec) if consec > 0 else 1.0

        # Longevity dampening: high-longevity topics need bigger deltas to surface
        longevity_dampen = 0.5 if lon > 0.7 else 0.8 if lon > 0.5 else 1.0

        # Novelty boost: first time in 7 days = 3x, first time in 3 days = 2x
        if appearances == 0:
            novelty_boost = 3.0
        elif consec == 0:
            novelty_boost = 2.0
        else:
            novelty_boost = 1.0

        # Compute radar score (what's most interesting RIGHT NOW)
        abs_delta = abs(vel_d) + abs(den_d) + abs(scar_d)
        radar_score = (abs_delta + vel * 0.3 + scar * 0.2) * novelty_boost * staleness_penalty * longevity_dampen

        # Determine WHY this topic is interesting
        reasons = []
        if appearances == 0:
            reasons.append("new_to_radar")
        if vel_d > 0.1:
            reasons.append("accelerating")
        if vel_d < -0.1:
            reasons.append("decelerating")
        if den_d > 0.15:
            reasons.append("getting_crowded")
        if den_d < -0.15:
            reasons.append("clearing_out")
        if scar > 0.5 and den < 0.3:
            reasons.append("white_space")
        if den > 0.7:
            reasons.append("saturated")
        if emp_delta is not None and abs(emp_delta) > 0.02:
            reasons.append("empathy_shift_up" if emp_delta > 0 else "empathy_shift_down")
        if vel > 0.5 and den < 0.4:
            reasons.append("rising_edge")

        if not reasons:
            reasons.append("stable")

        results.append({
            "topic": topic,
            "velocity": vel,
            "longevity": lon,
            "density": den,
            "scarcity": scar,
            "velocity_delta": vel_d,
            "density_delta": den_d,
            "scarcity_delta": scar_d,
            "empathy_recent": emp_recent,
            "empathy_delta": emp_delta,
            "staleness_penalty": staleness_penalty,
            "novelty_boost": novelty_boost,
            "longevity_dampen": longevity_dampen,
            "radar_score": radar_score,
            "consecutive_days_appeared": consec,
            "reasons": reasons,
        })

    # Sort by radar_score descending
    results.sort(key=lambda x: x["radar_score"], reverse=True)
    return results


def format_intelligence_context(topics, top_n=10):
    """Format topic intelligence into a context string for Claude prompts.

    Returns human-readable context about what's interesting and why,
    without exposing raw scores — Claude should translate into plain language.
    """
    if not topics:
        return "No topic intelligence available.\n"

    lines = []
    lines.append("TOPIC INTELLIGENCE (what's different today)")
    lines.append("=" * 50)

    interesting = [t for t in topics if "stable" not in t["reasons"]][:top_n]
    stable = [t for t in topics if "stable" in t["reasons"]]

    if interesting:
        for t in interesting:
            reason_str = ", ".join(t["reasons"])
            line = f"\n{t['topic'].upper()} [{reason_str}]"
            line += f"\n  Velocity: {t['velocity']:.2f} (delta: {t['velocity_delta']:+.3f})"
            line += f"\n  Density: {t['density']:.2f} (delta: {t['density_delta']:+.3f})"
            line += f"\n  Scarcity: {t['scarcity']:.2f} (delta: {t['scarcity_delta']:+.3f})"
            line += f"\n  Longevity: {t['longevity']:.2f}"
            if t["empathy_recent"] is not None:
                line += f"\n  Empathy: {t['empathy_recent']:.4f} (delta: {t['empathy_delta']:+.4f})"
            if t["consecutive_days_appeared"] > 0:
                line += f"\n  WARNING: Appeared in {t['consecutive_days_appeared']} consecutive previous outputs — only include if there's a genuinely new angle"
            lines.append(line)
    else:
        lines.append("\nNo significant changes detected in the last 24 hours.")

    # White space opportunities
    white_space = [t for t in topics if "white_space" in t["reasons"]]
    if white_space:
        lines.append("\n\nWHITE SPACE (high scarcity, low density — nobody's covering these)")
        lines.append("-" * 50)
        for t in white_space[:5]:
            lines.append(f"  {t['topic']}: scarcity {t['scarcity']:.2f}, density {t['density']:.2f}")

    # Saturated (mention briefly for "avoid" signals)
    saturated = [t for t in topics if "saturated" in t["reasons"]]
    if saturated:
        lines.append("\n\nSATURATED (everyone's here — adding more is noise)")
        lines.append("-" * 50)
        for t in saturated[:5]:
            lines.append(f"  {t['topic']}: density {t['density']:.2f}, velocity {t['velocity']:.2f}")

    # Stale topics — explicitly tell Claude what NOT to lead with
    stale = [t for t in topics if t["consecutive_days_appeared"] >= 2]
    if stale:
        lines.append("\n\nSTALE TOPICS (appeared 2+ consecutive days — DO NOT lead with these unless material change)")
        lines.append("-" * 50)
        for t in stale:
            lines.append(f"  {t['topic']}: {t['consecutive_days_appeared']} consecutive days")

    return "\n".join(lines)
