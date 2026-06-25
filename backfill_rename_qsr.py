"""
backfill_rename_qsr.py

Follow-up to the food&dining -> qsr rename + vocabulary narrowing.

Reclassifies every row currently tagged 'food & dining' under the NEW classifier:
  - real QSR rows                       -> 'qsr'
  - generic-dining rows (Disney/Michelin/fine-dining, etc.) -> whatever they now
    match (mostly 'other' or an adjacent category like 'entertainment')

Only 'food & dining' rows are touched. The narrowed 'qsr' vocabulary is a strict
SUBSET of the old 'food & dining' vocabulary, so no row OUTSIDE the old category
can newly become 'qsr' — reclassifying the old set is complete and sufficient.

DRY-RUN by default. Re-run with --apply to write. Writes a revert log
(ids -> 'food & dining') per table for full reversibility.
"""
import os
import sys
import json

APPLY = "--apply" in sys.argv

# Neutralize argv before importing pipeline modules (fetch_posts runs argparse
# at import and would reject --apply).
_saved_argv = sys.argv
sys.argv = [sys.argv[0]]
import psycopg2
from psycopg2.extras import execute_values
import fetch_news_rss as frss
import fetch_posts as fp
sys.argv = _saved_argv


def get_db():
    url = os.getenv("DATABASE_URL")
    if not url:
        url = json.loads(os.popen("railway variables --json 2>/dev/null").read())["DATABASE_URL"]
    return psycopg2.connect(url)


def backfill(conn, table, classify):
    r = conn.cursor()
    r.execute(f"SELECT id, text FROM {table} WHERE topic = 'food & dining'")
    rows = r.fetchall()
    r.close()

    changes = []      # (id, new_topic)
    dest = {}         # new_topic -> count
    for rid, text in rows:
        new = classify(text or "")
        changes.append((rid, new))
        dest[new] = dest.get(new, 0) + 1

    qsr_n = dest.get("qsr", 0)
    print(f"\n=== {table}: {len(rows):,} 'food & dining' rows reclassified "
          f"({qsr_n:,} -> qsr, {len(rows) - qsr_n:,} -> other/adjacent) ===")
    for d, n in sorted(dest.items(), key=lambda x: -x[1]):
        print(f"   {n:6}  -> {d}")

    if APPLY and changes:
        revert_path = f"backfill_rename_qsr_revert_{table}.json"
        with open(revert_path, "w") as f:
            json.dump([rid for rid, _ in changes], f)
        print(f"   revert log -> {revert_path} ({len(changes):,} ids; restore to 'food & dining')")
        w = conn.cursor()
        for i in range(0, len(changes), 1000):
            execute_values(
                w,
                f"UPDATE {table} AS t SET topic = v.new_topic "
                f"FROM (VALUES %s) AS v(id, new_topic) WHERE t.id = v.id",
                changes[i:i + 1000],
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
