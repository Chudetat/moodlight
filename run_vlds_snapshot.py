#!/usr/bin/env python3
"""Daily VLDS snapshot writer (delta-layer freshness).

Captures today's VLDS (velocity / longevity / density / scarcity per topic) into
topic_vlds_snapshots so the delta layer has day-over-day history — used by
compute_vlds_deltas (Ask directional deltas, Brief, Radar).

Why this exists as a dedicated job: the in-pipeline calls in
calculate_{density,longevity,scarcity}.py wrap save_vlds_snapshot in a NON-FATAL
try/except, so when it fails in the worker runtime the error is swallowed and
snapshots silently stop — they stalled at 2026-07-06, which is why the Ask delta
layer had no history to diff. This job runs with a FRESH engine, verifies the
write actually landed, and RAISES on failure so worker_lightweight sends a
failure email. No more silent starvation.

Run:  python worker_lightweight.py vlds-snapshot     (schedule daily on Railway)
"""
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from topic_intelligence import ensure_snapshot_table, save_vlds_snapshot


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    engine = create_engine(url)

    ensure_snapshot_table(engine)
    save_vlds_snapshot(engine)

    # Verify today's snapshot actually landed — the whole point of this job is to
    # fail LOUDLY (not swallow) if the write did not persist.
    with engine.connect() as conn:
        n = conn.execute(text(
            "SELECT COUNT(*) FROM topic_vlds_snapshots WHERE snapshot_date = CURRENT_DATE"
        )).scalar()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"VLDS snapshot for {today}: {n} topics written.")
    if not n:
        raise RuntimeError(
            "VLDS snapshot wrote 0 rows for today — check the topic_longevity / "
            "topic_density / topic_scarcity source tables are populated."
        )


if __name__ == "__main__":
    main()
