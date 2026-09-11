"""
weekly_review.py — Layer 2. Read the week and say what is actually happening.

Layer 1 (answer_quality) counts five defects it already knows about. That is
worth having and it is not enough: the Hyundai drop, the contrastive-negation
tic and the attribution rule firing 16% of the time were all found by a person
reading real answers end to end, and none of them existed as a rule until after
they were found. A checklist encodes yesterday's mistakes. Nothing in the
system looks for tomorrow's.

This does. Once a week it assembles what actually happened - defect rates and
their direction, refusals, new leads, traffic shape, the real pushback people
typed, and the week's most substantial answers in full - and asks for a reading
of it. The instruction is deliberately not a checklist: find what nobody has
written a rule for yet.

WHY IT RIDES THE MONDAY CRON
----------------------------
Railway cron can only be set in the dashboard, never by CLI. worker-weekly-
digest already runs Mondays at 15:00 UTC, so this attaches there as a
non-blocking pre-step: no new service, nothing to configure, and a failure here
can never cost the digest.

WHAT IT COSTS AND WHY THAT IS FINE
-----------------------------------
One large call a week, roughly 40k tokens in. Pennies. The earlier estimate of
$10-15 a run assumed an agent session with tools; this is a single analysis
call against a prepared packet, which is most of the value for a fraction of
the price.

WHAT IT CANNOT DO
-----------------
It reads what the database holds. It cannot grep the codebase, follow a hunch
into a file, or check a claim against the live web. That is the ceiling of this
design, and the upgrade when it starts to bite is a scheduled agent session
with repository access rather than a bigger prompt.
"""

import os
import smtplib
from email.mime.text import MIMEText

from qa_marker import SQL_EXCLUDE_QA

_MODEL = "claude-opus-5"
_MAX_ANSWERS_READ = 8
_ANSWER_CHARS = 3000

_SYSTEM = """You are reviewing one week of a live intelligence product, for the person who
built it and sells it. He is a 30-year chief creative officer. He does not need the data
described back to him; he needs to know what it means and what to do.

You are looking for THREE things, in this order of value:

1. SOMETHING NOBODY HAS A RULE FOR YET. The defect counts below only measure faults
   already known. The valuable finding is a pattern visible in the raw answers that no
   existing check would catch - a habit of reasoning, a way questions get misread, a kind
   of question the product consistently handles badly, an opportunity it keeps walking
   past. This is the whole reason a human-style read exists on top of the counters.

2. WHAT MOVED, AND WHETHER IT MATTERS. A rate rising is a signal. A rate steady is the
   cost of doing business. Say which is which, and never present noise from a small
   sample as a trend - if the volume is too low to support a conclusion, say so plainly
   and move on.

3. WHAT THE USERS ARE ACTUALLY TELLING YOU. Corrective follow-ups are people saying the
   product failed them in their own words. They outrank every metric here.

RULES FOR YOUR OUTPUT
- Quote. Every claim about an answer carries the words that prove it.
- At most THREE recommendations, ranked, each naming the specific change. Fewer is
  better. A list of ten is a list nobody acts on.
- If the week was fine, say the week was fine. Manufacturing concerns to look useful
  destroys the only thing this report has, which is that it is worth reading.
- Plain ASCII. No em dashes, no curly quotes. It gets pasted into email.
- Do not define anything by denying something else ("it is not X, it is Y"). That
  construction is banned in the product and it is banned here.
- No preamble, no restating these instructions, no closing summary of what you said."""


def _engine():
    from db_helper import make_engine
    url = os.getenv("DATABASE_URL", "")
    return make_engine(url) if url else None


def _packet(conn):
    """Everything the reviewer reads. Assembled here so the model spends its
    attention on judgement rather than on querying."""
    from sqlalchemy import text as sql_text
    q = lambda s, **kw: conn.execute(sql_text(s), kw).fetchall()
    out = []

    vol = q(f"""SELECT COUNT(*), COUNT(DISTINCT ip_hash) FROM ask_queries
                 WHERE {SQL_EXCLUDE_QA} AND created_at > NOW() - INTERVAL '7 days'""")[0]
    prev = q(f"""SELECT COUNT(*), COUNT(DISTINCT ip_hash) FROM ask_queries
                  WHERE {SQL_EXCLUDE_QA}
                    AND created_at BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days'""")[0]
    out.append(f"VOLUME\n  this week: {vol[0]} questions from {vol[1]} visitors"
               f"\n  week before: {prev[0]} questions from {prev[1]} visitors")

    try:
        rates = q("""SELECT check_name, COUNT(*),
                            COUNT(*)::float / GREATEST((SELECT COUNT(DISTINCT query_id)
                              FROM answer_quality_findings
                             WHERE checked_at > NOW() - INTERVAL '7 days'),1)
                       FROM answer_quality_findings
                      WHERE checked_at > NOW() - INTERVAL '7 days'
                      GROUP BY check_name ORDER BY 2 DESC""")
        graded = q("""SELECT COALESCE(SUM(graded),0), COALESCE(SUM(clean),0)
                        FROM answer_quality_runs WHERE ran_at > NOW() - INTERVAL '7 days'""")[0]
        lines = [f"  {n}: {c} findings ({r:.2f} per answer with findings)" for n, c, r in rates]
        out.append(f"DEFECT COUNTS (Layer 1, last 7 days)\n"
                   f"  graded {graded[0]}, clean {graded[1]}\n" + "\n".join(lines))
    except Exception as e:
        out.append(f"DEFECT COUNTS unavailable: {type(e).__name__}")

    try:
        punts = q(f"""SELECT created_at, LEFT(question,90) FROM ask_queries
                       WHERE punt_checked_at IS NOT NULL AND {SQL_EXCLUDE_QA}
                         AND created_at > NOW() - INTERVAL '7 days'
                         AND id IN (SELECT query_id FROM answer_quality_findings)
                       ORDER BY created_at DESC LIMIT 10""")
        if punts:
            out.append("FLAGGED QUESTIONS THIS WEEK\n" +
                       "\n".join(f"  {t:%m-%d} {s}" for t, s in punts))
    except Exception:
        pass

    push = q(f"""SELECT created_at, ip_hash, LEFT(question,140) FROM ask_queries
                  WHERE {SQL_EXCLUDE_QA} AND created_at > NOW() - INTERVAL '7 days'
                    AND (LOWER(question) LIKE 'no %' OR LOWER(question) LIKE 'not %'
                      OR LOWER(question) LIKE '%wrong%' OR LOWER(question) LIKE 'too %'
                      OR LOWER(question) LIKE '%instead%' OR LOWER(question) LIKE '%i said%'
                      OR LOWER(question) LIKE '%actually%' OR LOWER(question) LIKE '%nothing new%')
                  ORDER BY created_at DESC LIMIT 12""")
    out.append("CORRECTIVE FOLLOW-UPS (users saying it failed them)\n" +
               ("\n".join(f"  {t:%m-%d} [{h[:8]}] {s}" for t, h, s in push)
                if push else "  none this week"))

    leads = q("""SELECT email, agent, LEFT(COALESCE(user_input,''),110)
                   FROM marketplace_runs
                  WHERE created_at > NOW() - INTERVAL '7 days'
                  ORDER BY created_at DESC LIMIT 8""")
    out.append("MARKETPLACE ACTIVITY\n" +
               ("\n".join(f"  {e} [{a}] {u}" for e, a, u in leads) if leads else "  none"))

    answers = q(f"""SELECT id, question, answer FROM ask_queries
                     WHERE {SQL_EXCLUDE_QA} AND created_at > NOW() - INTERVAL '7 days'
                       AND LENGTH(COALESCE(answer,'')) > 1500
                     ORDER BY LENGTH(answer) DESC LIMIT {_MAX_ANSWERS_READ}""")
    if answers:
        # Cut at a sentence boundary and SAY that it was cut. The first run of
        # this review reported that every answer ended mid-sentence and flagged
        # it as a possible product failure at the exact paragraph the product is
        # sold on. It was this truncation. The answers in the database are
        # complete. A reviewer cannot tell the difference unless told, and a
        # false critical finding costs more than a missed one.
        blocks = []
        for i, qq, a in answers:
            body = a or ""
            if len(body) > _ANSWER_CHARS:
                cut = body[:_ANSWER_CHARS]
                stop = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("? "), cut.rfind("! "))
                if stop > _ANSWER_CHARS // 2:
                    cut = cut[:stop + 1]
                body = (cut + f"\n[TRUNCATED FOR THIS REVIEW at ~{_ANSWER_CHARS} chars. "
                              f"The stored answer is {len(a)} chars and ends properly. "
                              f"Do NOT report this as the answer ending mid-thought.]")
            blocks.append(f"--- id={i}\nQ: {qq.strip()[:400]}\nA: {body}")
        out.append("THE WEEK'S SUBSTANTIAL ANSWERS, READ THESE PROPERLY\n" + "\n\n".join(blocks))
    return "\n\n" + ("\n\n" + "=" * 66 + "\n\n").join(out)


def _send(subject, body):
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("ASK_ALERT_TO") or "daniel@moodlightintel.com"
    if not all([sender, password]):
        print("weekly_review: email credentials not configured, nothing sent")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"weekly_review: sent to {recipient}")
    return True


def build(dry=False):
    engine = _engine()
    if not engine:
        raise RuntimeError("weekly_review: DATABASE_URL not set")
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("weekly_review: ANTHROPIC_API_KEY not set - the review did not run")
    from anthropic import Anthropic
    client = Anthropic(api_key=key)

    with engine.connect() as conn:
        packet = _packet(conn)
    print(f"weekly_review: packet {len(packet)} chars")

    resp = client.messages.create(
        model=_MODEL,
        max_tokens=4000,
        system=_SYSTEM,
        messages=[{"role": "user", "content":
                   "Here is the week. Read it and tell me what is happening."
                   + packet}],
        extra_body={"output_config": {"effort": "high"}},
    )
    report = "".join(b.text for b in resp.content
                     if getattr(b, "type", "") == "text").strip()
    if not report:
        raise RuntimeError("weekly_review: empty report from model")
    if dry:
        print("\n=== DRY RUN, not sent ===\n")
        print(report)
        return report
    _send("Moodlight weekly review", report)
    return report


def main():
    build(dry=False)


if __name__ == "__main__":
    import sys
    build(dry="--dry" in sys.argv)
