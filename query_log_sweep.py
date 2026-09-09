#!/usr/bin/env python
"""
query_log_sweep.py — read what real users actually did, and find the defects.

Run:  railway run -s moodlight-api python3 query_log_sweep.py

Every fix this found on 2026-09-09 came from reading the log, not the code, and
none of them would have surfaced any other way:

  1. A creative director briefed Ask on a Dubai eyewear store opening and asked
     ten times for lines. Ask answered with strategy every time. "those are too
     long", "too lame and obvious", "lol no too pun-y", "nothing new?" - then
     they left. Fixed by CREATIVE_EXECUTION in shared_prompts.
  2. Two users corrected which company had been identified, both by pasting
     their own URL ("wrong product. https://ao2clear.com/"). Ask had no URL
     handling at all. Fixed by attaching web_fetch when a question carries a
     link.
  3. Answers for brands the substrate cannot see were built entirely on web
     search, with none of the measured corpus visible. Fixed by category_read.

The method matters more than any single query below: corrective follow-ups are
where the product failed a real person, and they are the only unfaked signal of
quality this system has. A user who rephrases, corrects or says "no" is telling
you something no metric will.

Re-run monthly. Read the pushback list first.
"""

import os
import psycopg2

PUSHBACK = (
    "no,", "not ", "wrong", "i don't want", "i dont want", "instead", "too ",
    "stop ", "again", "actually", "i said", "that's not", "thats not",
    "nothing new", "more specific", "i need", "can you just", "why did",
    "you missed", "didn't", "didnt",
)


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL not set")
    c = psycopg2.connect(url)
    cur = c.cursor()

    print("=" * 72)
    print("MOODLIGHT QUERY LOG SWEEP")
    print("=" * 72)

    cur.execute("SELECT COUNT(*), MIN(created_at)::date, MAX(created_at)::date FROM ask_queries")
    n, lo, hi = cur.fetchone()
    print(f"\n{n} questions, {lo} to {hi}")

    # 1. THE IMPORTANT ONE. A follow-up that corrects or rejects is the product
    #    failing a real person, in their own words.
    print("\n--- CORRECTIVE FOLLOW-UPS (read these first) ---")
    cur.execute("SELECT ip_hash, created_at, question FROM ask_queries ORDER BY ip_hash, created_at")
    seen, hits = set(), []
    for h, ts, q in cur.fetchall():
        key = (h, ts.date())
        ql = (q or "").lower().strip()
        if key in seen and any(ql.startswith(p) or f" {p}" in ql[:60] for p in PUSHBACK):
            hits.append((ts.date(), h[:8], q[:150]))
        seen.add(key)
    print(f"{len(hits)} found")
    for d, h, q in hits:
        print(f"  {d} [{h}] {q}")

    # 2. Depth of engagement. A long session is someone working, not bouncing.
    print("\n--- SESSION DEPTH ---")
    cur.execute("""SELECT q, COUNT(*) FROM (
                     SELECT ip_hash, DATE(created_at) d, COUNT(*) q
                       FROM ask_queries GROUP BY ip_hash, d) t
                   GROUP BY q ORDER BY q""")
    rows = cur.fetchall()
    tot = sum(x for _, x in rows)
    one = next((x for q, x in rows if q == 1), 0)
    for q, x in rows:
        print(f"  {x:4} sessions asked {q} question(s)")
    print(f"  -> {100*one/tot:.0f}% single-question")

    print("\n--- DEEP SESSIONS (5+ questions: who is doing real work) ---")
    cur.execute("""SELECT ip_hash, DATE(created_at) d, COUNT(*) q FROM ask_queries
                    GROUP BY ip_hash, d HAVING COUNT(*) >= 5 ORDER BY q DESC LIMIT 10""")
    for h, d, q in cur.fetchall():
        cur.execute("""SELECT LEFT(question,90) FROM ask_queries
                        WHERE ip_hash=%s AND DATE(created_at)=%s ORDER BY created_at LIMIT 3""", (h, d))
        first = [r[0] for r in cur.fetchall()]
        print(f"  {d} [{h[:8]}] {q} questions")
        for f in first:
            print(f"      {f}")

    # 3. Silent failures. Any recent row without an answer is a real defect.
    print("\n--- MISSING ANSWERS BY MONTH (pre-May is historical, ignore) ---")
    cur.execute("""SELECT TO_CHAR(created_at,'YYYY-MM'), COUNT(*),
                          COUNT(*) FILTER (WHERE answer IS NULL OR LENGTH(answer)<40)
                     FROM ask_queries GROUP BY 1 ORDER BY 1""")
    for m, t, x in cur.fetchall():
        flag = "  <-- CHECK" if x and m >= "2026-06" else ""
        print(f"  {m}: {x:4}/{t:4} missing{flag}")

    # 4. Capture rate. The number that says whether any of this converts.
    print("\n--- CAPTURE ---")
    cur.execute("SELECT COUNT(*) FROM ask_queries")
    asks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT email) FROM marketplace_runs")
    emails = cur.fetchone()[0]
    print(f"  {asks} questions -> {emails} email addresses ({100*emails/asks:.1f}%)")
    print("  (was 5.1% on 2026-09-09, before the inline handoff shipped)")

    print("\n--- URLS PASTED (web_fetch should be firing on these) ---")
    cur.execute("""SELECT COUNT(*) FROM ask_queries WHERE question ILIKE '%http%'""")
    print(f"  {cur.fetchone()[0]} questions contain a URL")

    print("\nDone. The pushback list is the part that matters.")


if __name__ == "__main__":
    main()
