#!/usr/bin/env python
"""
proof_views_report.py — who is reaching the proof library, and from where.

Run:  railway run -s moodlight-api python3 proof_views_report.py

The only question worth answering here is whether anyone arrives from OUTSIDE
moodlightintel.com. A hit referred by the Squarespace section means Daniel's own
funnel is working. A hit from LinkedIn, a DM, or with no referrer at all means
the artifact is travelling on its own, which is a different and much better
signal - it is the difference between a page on a site and a thing people send
each other.

Bots are separated out rather than filtered silently, because a crawler hitting
it is worth knowing (it means the page is indexable) and would otherwise inflate
the human count.
"""

import os
import psycopg2

BOT_MARKERS = ("bot", "crawler", "spider", "curl", "wget", "python-requests",
               "headless", "slackbot", "facebookexternalhit", "preview")


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set")
    cur = psycopg2.connect(url).cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM proof_views")
    except Exception:
        print("No proof_views table yet - nobody has loaded the page since logging shipped.")
        return

    total = cur.fetchone()[0]
    print("=" * 66)
    print("PROOF LIBRARY VIEWS")
    print("=" * 66)
    print(f"\n{total} page loads logged\n")
    if not total:
        return

    print("--- WHERE THEY CAME FROM ---")
    cur.execute("""
        SELECT COALESCE(
                 CASE
                   WHEN referer IS NULL OR referer = '' THEN 'direct / no referrer'
                   WHEN referer ILIKE '%moodlightintel.com%' THEN 'moodlightintel.com (own site)'
                   WHEN referer ILIKE '%linkedin%'  THEN 'LinkedIn'
                   WHEN referer ILIKE '%google%'    THEN 'Google'
                   WHEN referer ILIKE '%t.co%' OR referer ILIKE '%twitter%' OR referer ILIKE '%x.com%' THEN 'X'
                   ELSE referer
                 END, 'unknown') src,
               COUNT(*), COUNT(DISTINCT ip_hash)
          FROM proof_views GROUP BY src ORDER BY 2 DESC""")
    for src, hits, people in cur.fetchall():
        print(f"  {hits:4} hits / {people:3} distinct  {src}")

    print("\n--- HUMANS VS BOTS ---")
    like = " OR ".join(["LOWER(COALESCE(user_agent,'')) LIKE %s"] * len(BOT_MARKERS))
    params = [f"%{m}%" for m in BOT_MARKERS]
    cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT ip_hash) FROM proof_views WHERE {like}", params)
    b_hits, b_people = cur.fetchone()
    cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT ip_hash) FROM proof_views WHERE NOT ({like})", params)
    h_hits, h_people = cur.fetchone()
    print(f"  humans: {h_hits} hits / {h_people} distinct")
    print(f"  bots  : {b_hits} hits / {b_people} distinct")

    print("\n--- BY DAY ---")
    cur.execute("""SELECT DATE(created_at), COUNT(*), COUNT(DISTINCT ip_hash)
                     FROM proof_views GROUP BY 1 ORDER BY 1 DESC LIMIT 14""")
    for d, hits, people in cur.fetchall():
        print(f"  {d}: {hits:4} hits / {people:3} distinct")

    print("\n--- OFF-SITE REFERRERS IN FULL (the ones that matter) ---")
    cur.execute("""SELECT referer, COUNT(*) FROM proof_views
                    WHERE referer IS NOT NULL AND referer <> ''
                      AND referer NOT ILIKE '%moodlightintel.com%'
                    GROUP BY referer ORDER BY 2 DESC LIMIT 20""")
    rows = cur.fetchall()
    if not rows:
        print("  none yet - every referred visit has come from the site itself")
    for r, n in rows:
        print(f"  {n:4}  {r}")


if __name__ == "__main__":
    main()
