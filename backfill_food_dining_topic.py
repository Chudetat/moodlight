"""
backfill_food_dining_topic.py

One-time reclassification of existing news_scored / social_scored rows after
adding the 'food & dining' topic category (P1).

Only rows that match a food keyword change — they move INTO 'food & dining'
from whatever non-priority bucket they previously landed in (business, economics,
branding, labor, sports, entertainment, other). No other row is touched, because
'food & dining' sits at the END of the priority list: a row that doesn't match a
food keyword classifies exactly as it did before.

DRY-RUN by default (no writes). Review the from->to breakdown, then re-run with
  python backfill_food_dining_topic.py --apply

Each table is reclassified with ITS OWN pipeline classifier (news -> fetch_news_rss,
social -> fetch_posts) so the result matches what the live pipeline would produce.
"""
import os
import sys
import json
import psycopg2
from psycopg2.extras import execute_values

import fetch_news_rss as frss
import fetch_posts as fp

APPLY = "--apply" in sys.argv


def get_db():
    url = os.getenv("DATABASE_URL")
    if not url:
        # fall back to the Railway-linked service var
        url = json.loads(os.popen("railway variables --json 2>/dev/null").read())["DATABASE_URL"]
    return psycopg2.connect(url)


def backfill(conn, table, classify):
    read = conn.cursor(name=f"scan_{table}")  # server-side streaming cursor
    read.itersize = 5000
    read.execute(f"SELECT id, text, topic FROM {table}")

    # ISOLATE the P1 change: only move rows that NOW classify as 'food & dining'.
    # Re-running the full classifier would also surface unrelated drift (the live
    # classifier has evolved since these rows were first scored). We deliberately
    # leave that historical drift alone and touch ONLY rows that become food.
    changes = []          # (id, prior_topic) — prior_topic powers the revert log
    sources = {}          # prior topic -> count
    scanned = 0
    for rid, text, old in read:
        scanned += 1
        if not text:
            continue
        if classify(text) == "food & dining" and old != "food & dining":
            changes.append((rid, old))
            sources[old] = sources.get(old, 0) + 1
    read.close()

    print(f"\n=== {table}: scanned {scanned:,} | moving {len(changes):,} rows into 'food & dining' ===")
    for src, n in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"   {n:6}  {src} -> food & dining")

    if APPLY and changes:
        # Write a revert log FIRST so the change is fully reversible:
        # backfill_food_dining_revert_<table>.json maps id -> prior topic.
        revert_path = f"backfill_food_dining_revert_{table}.json"
        with open(revert_path, "w") as f:
            json.dump(changes, f)
        print(f"   revert log -> {revert_path} ({len(changes):,} rows)")
        w = conn.cursor()
        for i in range(0, len(changes), 1000):
            batch = [(rid, "food & dining") for rid, _old in changes[i:i + 1000]]
            execute_values(
                w,
                f"UPDATE {table} AS t SET topic = v.new_topic "
                f"FROM (VALUES %s) AS v(id, new_topic) WHERE t.id = v.id::bigint",
                batch,
            )
        conn.commit()
        print(f"   APPLIED {len(changes):,} updates to {table}")
    elif changes:
        print("   (dry-run — pass --apply to write)")


def main():
    print("MODE:", "APPLY (writing)" if APPLY else "DRY-RUN (no writes)")
    conn = get_db()
    try:
        backfill(conn, "news_scored", frss.classify_topic)
        backfill(conn, "social_scored", fp.classify_topic)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
