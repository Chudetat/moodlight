"""
answer_quality.py — Layer 1. Read every real answer and find the defects.

WHY THIS EXISTS
---------------
On 2026-09-11 a rule that had shipped five weeks earlier - attribute every
external figure so it can be checked - turned out to have fired in 37 of 232
substantial answers. Nothing was broken. It simply did not run, and a rule
silently not firing looks exactly like a rule working perfectly.

That was the seventh such discovery in two days. Web search built and gated
shut. Web search never built on the dashboard while everyone assumed it was. A
monitor that would have returned quietly forever for want of an API key. A
docstring claiming an alert surfaced an email address it never selected. 186
marketplace runs with no notification code in existence.

They share one cause: production had no voice. This gives it one.

WHAT IT CHECKS, AND WHY THESE
-----------------------------
Not "is this good strategy" - there is no ground truth for that, and a model
asked to grade its own taste produces congratulation. Every check below has a
right answer, and every finding must carry a QUOTE from the answer. A grader
that cannot point at the words does not get to make the claim.

  coverage         something the question named vanished without a word
  evidence_hygiene a claim about perception or behaviour built on coverage data
  follow_through   the load-bearing recommendation left as a bare clause
  attribution      an external figure with no source, or an aggregator credited
                   as though it were the authority
  ai_tells         banned phrases, the contrastive-negation tic, or an example
                   sentence from the prompt reused verbatim as its own line
  addressee        orders issued to a brand's management when the question never
                   said the reader works there
  falsifier        a call made with no checkable condition under which it is wrong

All seven are failures found in real answers, not invented categories. Neither
of the last two came from a checklist: addressee came from Layer 2 reading a
week end to end, and falsifier came from noticing that the two best answers in
the whole corpus (the stress-tests, ids 514 and 515) do one thing no first
answer ever does - they name the condition under which their own call fails.
A checklist only ever encodes the mistakes already known.

THE EMAIL GATE
--------------
It will not mail anything until ANSWER_QUALITY_EMAIL is set. A grader that
cries wolf is worse than no grader, because you learn to ignore the one channel
meant to tell you the truth. Run --calibrate first, read the output, and only
then turn sending on.
"""

import json
import os
import smtplib
import sys
from email.mime.text import MIMEText

from qa_marker import SQL_EXCLUDE_QA

_MODEL = "claude-opus-5"

# Short answers are pills and greetings; the defects below need room to happen.
_MIN_ANSWER_CHARS = 1200

_MAX_AGE_HOURS = 48

# Hard cost ceiling per run. At roughly $0.05 a grade this caps a runaway at
# well under a dollar an hour.
_MAX_PER_RUN = 12

_QUOTE_MAX = 200

CHECKS = ("coverage", "evidence_hygiene", "follow_through", "attribution", "ai_tells",
          "addressee", "falsifier")

_SYSTEM = """You are an adversarial reviewer of a strategic intelligence answer. You are
not its author and you gain nothing by approving it. Your job is to find where it falls
short, precisely, or to say clearly that it does not.

You are NOT judging whether the strategy is correct or whether the writing is good. You
are checking seven specific defects, each of which has a right answer.

1. coverage - The question named something (a competitor, market, product, audience,
   sub-question) that then vanished from the answer with no word about it. Deliberately
   setting something aside IS ALLOWED and is not a defect: "Hyundai is a sideshow here"
   passes. Silence fails. If the question named one thing only, this check passes.

2. evidence_hygiene - The answer makes a claim about what people believe, feel, or do,
   and supports it with tracked news or social coverage WITHOUT saying that is what the
   signal measures. Coverage register is not audience sentiment. If the answer states
   the distinction in the line where it uses the evidence, it passes. If it has no such
   claim, it passes.

3. follow_through - The recommendation the answer leans on most is left as a bare clause
   with no mechanism ("through partnership", "by repositioning", "with better content").
   If the load-bearing recommendation is argued with specifics, it passes.

4. attribution - Flag ONLY these two things:
     (a) an external figure (share, percentage, valuation, unit count, deal size) with
         NO source and NO sourcing frame of any kind; or
     (b) an aggregator, blog or SEO listicle credited as though it were the authority.
   These all PASS and must not be flagged:
     - naming the market and period as the frame ("Thailand's Q1 2026 registrations show
       the market up 22% to 201,033 units") - this is the permitted fallback when the
       issuing body cannot be identified, NOT a defect, and you must not demand a
       regulator or institution on top of it;
     - naming a publication for a reported EVENT ("Car and Driver reports a recall of");
     - figures drawn from Moodlight's own tracked signal, which is internal data and
       needs no external source;
     - qualitative or directional statements carrying no specific number.
   If the answer cites no external figures at all, it passes.

5. addressee - The answer assumes the reader works for the brand in question and issues
   instructions to that brand's management ("do not let the two swap costumes", "put this
   in front of legal early"), when the question never said who was asking. A brand name
   alone carries no principal: the asker may be an agency, investor, competitor or
   candidate. PASSES if the question states who is asking, if the answer names whose call
   it is, or if the read holds from any seat. Flag the imperative aimed at an assumed
   employer, and quote it.

6. falsifier - The answer makes a recommendation or a call but never names the specific,
   checkable condition under which that call would be WRONG. A risk list, a caveat, or
   "this depends on execution" does NOT count - it must be a condition a reader could go
   and check. PASSES if such a condition is named anywhere, in any words, or if the answer
   makes no call at all (a pure description or a set of options with tradeoffs already
   stated). Do not flag an answer for lacking a standing phrase; the condition can be
   stated in any language, anywhere in the piece.

7. ai_tells - Flag any of:
     - CONTRASTIVE NEGATION, the whole family, in every phrasing: "it is not just X it is
       Y", "X is not A, it is B", "That is not a sentimental story, it is a
       product-integrity story", the two-sentence split ("The tell is not a brand launch.
       It is a supply chain hire"), the trailing form ("underwritten by mix and cost, not
       volume"), "the question is not whether X, it is whether Y".
       COUNT THEM. Flag this ONLY at THREE OR MORE in one piece, and quote the third.
       One or two is not a finding and must not be reported.
       The prompt asks for at most one and three attempts to enforce that failed, because
       the construction is native to analytical writing and the lines it produces are
       often the best in the answer. The rule stays as a brake; the counter measures the
       thing that actually matters, which is a piece BUILT on the device. A check that
       fires on every answer forever teaches the reader to ignore the report.
     - banned phrasing: "delve", "tapestry", "testament to", "in an era of", "the
       result?", "unpack", "leverage" as a verb, "game-changer", "seamless", "robust",
       or a three-item rhythm built for rhythm's sake
     - a throat-clearing opener that restates the question before answering it
     - a closing paragraph that summarises what was just said

OUTPUT FORMAT. One finding per line, three fields separated by three pipes:

check|||exact words copied from the answer (under 200 chars)|||one sentence saying why

If there are no defects, output the single word NONE.
Output nothing else: no preamble, no code fence, no numbering, no closing remark.
Deliberately not JSON - the quotes you must copy contain quotation marks.

Rules that decide whether this tool is worth having:
- Every finding MUST carry a real quote copied from the answer. No quote, no finding.
- Report only what you can point at. An empty findings list is a valid and common result.
- Do not invent defects to seem useful. Most good answers have none or one."""


def _engine():
    from db_helper import make_engine
    url = os.getenv("DATABASE_URL", "")
    return make_engine(url) if url else None


def _ensure_schema(conn):
    from sqlalchemy import text as sql_text
    conn.execute(sql_text(
        "ALTER TABLE ask_queries ADD COLUMN IF NOT EXISTS quality_checked_at TIMESTAMPTZ"))
    # Findings are kept, not just mailed. A single defect is an anecdote; the
    # rate over time is the thing that would have shown a rule firing 16% of
    # the time. Layer 2 reads this table.
    conn.execute(sql_text("""
        CREATE TABLE IF NOT EXISTS answer_quality_findings (
            id SERIAL PRIMARY KEY,
            query_id INTEGER,
            checked_at TIMESTAMPTZ DEFAULT NOW(),
            check_name VARCHAR(40),
            quote TEXT,
            why TEXT
        )"""))
    conn.execute(sql_text(
        "CREATE TABLE IF NOT EXISTS answer_quality_runs ("
        " id SERIAL PRIMARY KEY, ran_at TIMESTAMPTZ DEFAULT NOW(),"
        " graded INTEGER, clean INTEGER, defective INTEGER)"))
    conn.execute(sql_text(
        "ALTER TABLE answer_quality_runs ADD COLUMN IF NOT EXISTS "
        "digest_sent BOOLEAN DEFAULT FALSE"))
    conn.commit()


def _fetch(conn, limit=None, historical=False):
    from sqlalchemy import text as sql_text
    age = "" if historical else f"AND created_at > NOW() - INTERVAL '{_MAX_AGE_HOURS} hours'"
    unchecked = "" if historical else "AND quality_checked_at IS NULL"
    return conn.execute(sql_text(f"""
        SELECT id, created_at, question, answer
          FROM ask_queries
         WHERE LENGTH(COALESCE(answer,'')) >= {_MIN_ANSWER_CHARS}
           AND {SQL_EXCLUDE_QA}
           {age} {unchecked}
         ORDER BY created_at DESC
         LIMIT {int(limit or _MAX_PER_RUN)}
    """)).fetchall()


def _grade(client, question, answer):
    """Findings for one answer. None means the check itself failed.

    None is not "clean". A grader that reports success when it errored would
    reproduce the exact failure this module was built to catch.
    """
    try:
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=2000,
            system=_SYSTEM,
            messages=[{"role": "user", "content":
                       f"QUESTION:\n{question[:2500]}\n\nANSWER:\n{answer[:14000]}"}],
            extra_body={"output_config": {"effort": "medium"}},
        )
        raw = "".join(b.text for b in resp.content
                      if getattr(b, "type", "") == "text").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if raw.upper().startswith("NONE"):
            return []
        out = []
        for line in raw.splitlines():
            parts = line.split("|||")
            if len(parts) < 2:
                continue
            check = parts[0].strip().lower().lstrip("-* ").strip()
            quote = parts[1].strip().strip('"')
            why = parts[2].strip() if len(parts) > 2 else ""
            # No quote, no finding - and the quote must actually appear in the
            # answer. This is the whole defence against a grader inventing work
            # to look useful. Normalise whitespace so a reflowed quote matches.
            norm = " ".join(answer.split()).lower()
            probe = " ".join(quote.split()).lower()[:60]
            if check in CHECKS and probe and probe in norm:
                out.append((check, quote[:_QUOTE_MAX], why))
        return out
    except Exception as e:
        print(f"  [answer_quality] grade failed: {type(e).__name__}: {e}")
        return None


def _record(conn, qid, findings):
    from sqlalchemy import text as sql_text
    for check, quote, why in findings:
        conn.execute(sql_text(
            "INSERT INTO answer_quality_findings (query_id, check_name, quote, why) "
            "VALUES (:q, :c, :t, :w)"),
            {"q": qid, "c": check, "t": quote, "w": why})
    conn.execute(sql_text(
        "UPDATE ask_queries SET quality_checked_at = NOW() WHERE id = :q"), {"q": qid})
    conn.commit()


# Sent on the first hourly run at or after this hour, UTC. 15:00 UTC is 8am
# Pacific, so it is waiting when Daniel starts. Anchoring to an hour matters:
# a pure "20 hours since the last one" rule drifts four hours earlier each day
# and wanders round the clock, and a report that arrives at 3am is a report
# nobody reads.
_DIGEST_HOUR_UTC = int(os.getenv("ANSWER_QUALITY_DIGEST_HOUR", "15"))


def _should_digest(conn):
    """One digest a day, at a predictable hour, not one email per defect.

    Calibration on 2026-09-11 showed essentially every answer carries one or
    two findings. Mailing per finding would put an email in the inbox for every
    answer, and a channel that fires constantly is a channel you stop reading -
    the precise failure this module was built to prevent. So: record always,
    report daily, and make the report about the RATE, because a rate is the
    thing that would have shown a rule firing 16% of the time.
    """
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    if now.hour < _DIGEST_HOUR_UTC:
        return False
    from sqlalchemy import text as sql_text
    last = conn.execute(sql_text(
        "SELECT MAX(ran_at) FROM answer_quality_runs WHERE digest_sent")).scalar()
    if last is None:
        return True
    # Once per calendar day. A run that missed its hour (deploy, outage) still
    # sends later the same day rather than skipping the day entirely.
    return last.date() < now.date() or (now - last) > timedelta(hours=23)


def _digest(conn):
    """Yesterday's defect rate, against the trailing fortnight."""
    from sqlalchemy import text as sql_text
    day = conn.execute(sql_text("""
        SELECT COUNT(DISTINCT q.id),
               COUNT(DISTINCT f.query_id)
          FROM ask_queries q
          LEFT JOIN answer_quality_findings f ON f.query_id = q.id
         WHERE q.quality_checked_at > NOW() - INTERVAL '24 hours'""")).fetchone()
    graded, defective = day[0] or 0, day[1] or 0
    if not graded:
        return None, None

    rows = conn.execute(sql_text("""
        SELECT check_name, COUNT(*) FROM answer_quality_findings
         WHERE checked_at > NOW() - INTERVAL '24 hours'
         GROUP BY check_name ORDER BY 2 DESC""")).fetchall()
    prior = dict(conn.execute(sql_text("""
        SELECT check_name, COUNT(*)::float / GREATEST(COUNT(DISTINCT query_id),1)
          FROM answer_quality_findings
         WHERE checked_at BETWEEN NOW() - INTERVAL '15 days' AND NOW() - INTERVAL '24 hours'
         GROUP BY check_name""")).fetchall())

    clean_pct = 100 * (graded - defective) / graded
    subject = f"Answer quality: {clean_pct:.0f}% clean of {graded} graded"
    parts = [f"{graded} answers graded in the last 24h. "
             f"{graded - defective} clean ({clean_pct:.0f}%).", "",
             "DEFECTS BY TYPE (per answer graded, vs trailing 14 days):", ""]
    for name, n in rows:
        rate = n / graded
        was = prior.get(name)
        trend = "" if was is None else f"   was {was:.2f}  {'UP' if rate > was * 1.3 else 'down' if rate < was * 0.7 else 'flat'}"
        parts.append(f"  {name:18} {rate:.2f}{trend}")
    parts += ["", "A rate moving UP is the signal. A steady rate is the cost of",
              "doing business until a rule is rewritten.", "", "-" * 62, "",
              "WORST OF THE DAY", ""]
    worst = conn.execute(sql_text("""
        SELECT f.query_id, f.check_name, f.quote, f.why
          FROM answer_quality_findings f
         WHERE f.checked_at > NOW() - INTERVAL '24 hours'
         ORDER BY f.id DESC LIMIT 6""")).fetchall()
    for qid, check, quote, why in worst:
        parts.append(f"  id={qid} [{check}] {why}")
        parts.append(f'      "{quote}"')
        parts.append("")
    parts.append("If a quote does not read as a defect to you, the grader is")
    parts.append("miscalibrated and should be told so.")
    return subject, "\n".join(parts)


def _send(subject, body):
    # Structurally off until deliberately enabled. See THE EMAIL GATE above.
    if not os.getenv("ANSWER_QUALITY_EMAIL"):
        print("answer_quality: ANSWER_QUALITY_EMAIL not set, not mailing (findings saved)")
        return False
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("ASK_ALERT_TO") or "daniel@moodlightintel.com"
    if not all([sender, password]):
        print("answer_quality: email credentials not configured, nothing sent")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"answer_quality: sent to {recipient}")
    return True


def _maybe_digest(conn, graded, clean, defective):
    """Record the run and send the daily digest if one is due.

    Called on BOTH paths - after grading, and when there was nothing new to
    grade - because the digest reports the last 24 hours, not this hour's work.
    """
    from sqlalchemy import text as sql_text
    sent = False
    if _should_digest(conn):
        subject, body = _digest(conn)
        if subject:
            sent = _send(subject, body)
        else:
            print("answer_quality: digest due but nothing graded in 24h, nothing sent")
    conn.execute(sql_text(
        "INSERT INTO answer_quality_runs (graded, clean, defective, digest_sent) "
        "VALUES (:g, :c, :d, :s)"),
        {"g": graded, "c": clean, "d": defective, "s": sent})
    conn.commit()


def _client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "answer_quality: ANTHROPIC_API_KEY not set on this service - "
            "the quality check did not run")
    from anthropic import Anthropic
    return Anthropic(api_key=key)


def calibrate(n=30, only_id=None):
    """Grade historical answers and print everything. Writes nothing, mails nothing.

    The acceptance test before this is allowed near an inbox: does it flag the
    answers that are genuinely short of the bar, and stay quiet on the ones that
    are fine? If it flags almost everything it is noise and must be retuned or
    binned.
    """
    engine = _engine()
    client = _client()
    with engine.connect() as conn:
        _ensure_schema(conn)
        if only_id:
            from sqlalchemy import text as sql_text
            rows = conn.execute(sql_text(
                "SELECT id, created_at, question, answer FROM ask_queries WHERE id=:i"),
                {"i": only_id}).fetchall()
        else:
            rows = _fetch(conn, limit=n, historical=True)
    print(f"CALIBRATION over {len(rows)} historical answer(s). Nothing written, nothing mailed.\n")
    clean = tally = 0
    counts = {c: 0 for c in CHECKS}
    for qid, ts, q, a in rows:
        f = _grade(client, q, a)
        if f is None:
            print(f"id={qid} GRADER ERROR"); continue
        tally += 1
        if not f:
            clean += 1
            print(f"id={qid:4} {ts:%m-%d} CLEAN   {' '.join(q.split())[:70]}")
            continue
        print(f"id={qid:4} {ts:%m-%d} {len(f)} defect(s)  {' '.join(q.split())[:70]}")
        for check, quote, why in f:
            counts[check] += 1
            print(f"        [{check}] {why}")
            print(f'            "{quote[:150]}"')
    print(f"\n{clean} of {tally} clean ({100*clean/tally:.0f}%)" if tally else "")
    print("by check:", {k: v for k, v in counts.items() if v})


def main():
    engine = _engine()
    if not engine:
        raise RuntimeError("answer_quality: DATABASE_URL not set")
    client = _client()
    with engine.connect() as conn:
        _ensure_schema(conn)
        rows = _fetch(conn)
        if not rows:
            # NOT an early return. The daily digest lives below, and at three
            # real questions a day most hours have nothing new to grade - so an
            # early return here meant the digest could only ever fire in an hour
            # that happened to carry a fresh answer, and on a quiet day the
            # report simply never arrived while findings sat unreported.
            print("answer_quality: nothing new to grade")
            _maybe_digest(conn, graded=0, clean=0, defective=0)
            return
        print(f"answer_quality: grading {len(rows)} answer(s)")
        defective, graded, clean = [], 0, 0
        for qid, ts, q, a in rows:
            f = _grade(client, q, a)
            if f is None:
                continue  # left unchecked, retried next run, ages out on its own
            graded += 1
            _record(conn, qid, f)
            if f:
                defective.append((qid, q, f))
            else:
                clean += 1
        print(f"answer_quality: {graded} graded, {clean} clean, {len(defective)} defective")
        _maybe_digest(conn, graded, clean, len(defective))


if __name__ == "__main__":
    if "--calibrate" in sys.argv:
        i = sys.argv.index("--calibrate")
        arg = sys.argv[i + 1] if len(sys.argv) > i + 1 else "30"
        if arg.startswith("id="):
            calibrate(only_id=int(arg[3:]))
        else:
            calibrate(n=int(arg))
    else:
        main()
