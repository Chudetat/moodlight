"""
punt_monitor.py — tell Daniel when Ask refused to answer a stranger.

On 2026-09-10 someone from MSQ DX typed their company name into Ask. MSQ DX is
a 600-person digital experience company inside MSQ, a 1,900-person creative and
media group. Ask could not identify them and asked them to explain who they
were. The capability to answer was built and deployed; a gating condition kept
it shut. Nobody found out from the product. It surfaced because Daniel happened
to see the visit notification.

That is the failure this module exists to catch. Not a crash, not a 500. Ask
answering politely and uselessly, to someone who will never write in to say so.
They just leave.

WHY ask_alerts.py COULD NOT HAVE CAUGHT IT
------------------------------------------
ask_alerts reports an inbound question only if it runs at least 60 characters
AND the classifier resolved a brand or topic. "MSQDX" is five characters with
no resolved brand. It failed both filters. The lead-alert system is blind to
precisely the visitor shape that just failed, so this module is the deliberate
inverse: no length floor, no brand requirement. Every answered question gets
looked at.

WHY A CLASSIFIER AND NOT A PHRASE LIST
--------------------------------------
Three punts on the same input produced three different wordings - "that came
through as noise on my end", "that's not enough to work with", "that's not a
brand, a ticker, or a category I can read anything into". A regex catches the
phrasing that happened to be seen once. Haiku catches the shape.

WHAT THIS DOES NOT DO
---------------------
It has no opinion on quality. A confident, fluent, wrong answer passes. It
detects one thing: Ask declining to answer and handing the work back to the
person who asked. That is a smoke alarm for the front door, not for the house.

Detection is after the fact by design. A visitor has already been failed by the
time this fires. The build that catches it BEFORE a stranger hits it is a
synthetic canary, deliberately held back: it would write rows into ask_queries,
and query_log_sweep, the admin endpoint and the dashboard tab all read that
table without filtering test rows. A daily canary would manufacture a phantom
deep-session user and corrupt the monthly sweep. Add [qa] filtering to those
three consumers first, then the canary is safe.
"""

import os
import smtplib
from email.mime.text import MIMEText

# Deliberately NOT ask_alerts' 60-char floor or its brand requirement. A bare
# token with no resolved brand is the exact query this exists for.
_MAX_AGE_HOURS = 48

# Ceiling on classifier calls per run. Rows left unclassified are retried next
# run and age out of the window on their own, so nothing wedges the queue.
_MAX_PER_RUN = 60

_ANSWER_EXCERPT = 400

# Shared with ask_alerts: our own production pokes are not visitors.
from qa_marker import SQL_EXCLUDE_QA

_CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"

_CLASSIFIER_SYSTEM = """You are checking whether an AI analyst ANSWERED a question or DECLINED to.

Return exactly one word: PUNT or ANSWERED.

PUNT means the response refused to engage with the subject and handed the work
back to the user - asking them to identify a company, name a brand, explain an
acronym, rephrase, supply context, or pick from a menu of what to ask instead.
A response that says it cannot place the subject and asks what sits behind it
is a PUNT even if it is polite, well written, or offers general observations
alongside the request.

ANSWERED means the response engaged with the subject and delivered a read on
it. An answer that states a limit ("no tracked signal on this brand") and then
analyses anyway is ANSWERED. An answer that is wrong, thin, or generic is still
ANSWERED - you are not judging quality, only whether it answered.

One word. No punctuation, no explanation."""


def _engine():
    from db_helper import make_engine
    url = os.getenv("DATABASE_URL", "")
    return make_engine(url) if url else None


def _ensure_column(conn):
    from sqlalchemy import text as sql_text
    conn.execute(sql_text(
        "ALTER TABLE ask_queries ADD COLUMN IF NOT EXISTS punt_checked_at TIMESTAMPTZ"))
    conn.commit()


def _fetch_unchecked(conn):
    from sqlalchemy import text as sql_text
    return conn.execute(sql_text(f"""
        SELECT id, created_at, detected_brand, ip_hash,
               question, COALESCE(answer, '')
          FROM ask_queries
         WHERE punt_checked_at IS NULL
           AND created_at > NOW() - INTERVAL '{_MAX_AGE_HOURS} hours'
           AND {SQL_EXCLUDE_QA}
         ORDER BY created_at
         LIMIT {_MAX_PER_RUN}
    """)).fetchall()


def _mark(conn, ids):
    if not ids:
        return
    from sqlalchemy import text as sql_text
    conn.execute(sql_text(
        "UPDATE ask_queries SET punt_checked_at = NOW() WHERE id = ANY(:ids)"),
        {"ids": list(ids)})
    conn.commit()


def _classify(client, question, answer):
    """True if Ask declined to answer. None if the check itself failed.

    None is not False. A classifier error leaves the row unmarked so the next
    run retries it - swallowing the error as "answered" would hide the exact
    thing this module was built to surface.
    """
    try:
        resp = client.messages.create(
            model=_CLASSIFIER_MODEL,
            max_tokens=5,
            system=_CLASSIFIER_SYSTEM,
            messages=[{"role": "user", "content":
                       f"QUESTION:\n{question[:1500]}\n\nRESPONSE:\n{answer[:4000]}"}],
        )
        verdict = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        ).strip().upper()
        if verdict.startswith("PUNT"):
            return True
        if verdict.startswith("ANSWERED"):
            return False
        print(f"  [punt_monitor] unparseable verdict {verdict!r}, leaving unmarked")
        return None
    except Exception as e:
        print(f"  [punt_monitor] classify failed: {type(e).__name__}: {e}")
        return None


def _compose(punts, empties):
    lead = punts[0][2] or (punts[0][4].strip()[:40] if punts else "")
    subject = f"Ask punted: {lead}" + (
        f" and {len(punts) - 1} more" if len(punts) > 1 else "")

    parts = [
        f"Ask declined to answer {len(punts)} visitor "
        f"question{'s' if len(punts) > 1 else ''}.",
        "",
        "These are people who found Moodlight on their own and were handed the",
        "work back. They do not write in to complain. They leave.",
        "",
        "-" * 62,
        "",
    ]
    for _id, ts, brand, ip_hash, question, answer in punts:
        parts.append(f"{ts:%b %d, %H:%M UTC}   visitor {ip_hash or 'unknown'}")
        parts.append(f"Brand detected: {brand or 'NONE'}")
        parts.append("")
        parts.append(f'  Asked: "{question.strip()}"')
        parts.append("")
        excerpt = " ".join((answer or "").split())[:_ANSWER_EXCERPT]
        parts.append(f"  We said: {excerpt}...")
        parts.append("")
        parts.append("-" * 62)
        parts.append("")
    if empties:
        parts.append(f"Separately: {empties} question(s) in this window have no")
        parts.append("answer recorded at all. That is a delivery failure, not a punt.")
        parts.append("")
    return subject, "\n".join(parts)


def _send(subject, body):
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    # Same reasoning as ask_alerts: EMAIL_RECIPIENT carries investors and an
    # external reader. Our own misses are not for them.
    recipient = os.getenv("ASK_ALERT_TO") or "daniel@moodlightintel.com"
    if not all([sender, password]):
        print("punt_monitor: email credentials not configured, nothing sent")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"punt_monitor: sent to {recipient}")
    return True


def main():
    # These raise rather than return. A monitor that goes quiet when it is
    # misconfigured is worse than no monitor: it reads as "no punts today"
    # forever. Raising makes worker_lightweight mail the failure instead.
    # worker-ask-alerts had no ANTHROPIC_API_KEY when this shipped - ask_alerts
    # is pure SQL and SMTP and never needed one - so this is not hypothetical.
    engine = _engine()
    if not engine:
        raise RuntimeError("punt_monitor: DATABASE_URL not set")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "punt_monitor: ANTHROPIC_API_KEY not set on this service - "
            "the punt check did not run")
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    with engine.connect() as conn:
        _ensure_column(conn)
        rows = _fetch_unchecked(conn)
        if not rows:
            print("punt_monitor: nothing to check")
            return
        print(f"punt_monitor: checking {len(rows)} answer(s)")

        punts, answered, empties = [], [], []
        for row in rows:
            answer = row[5]
            if not answer.strip():
                # Nothing to classify. Counted, reported, and marked so it does
                # not sit in the queue forever.
                empties.append(row[0])
                continue
            verdict = _classify(client, row[4], answer)
            if verdict is True:
                punts.append(row)
            elif verdict is False:
                answered.append(row[0])

        print(f"punt_monitor: {len(punts)} punt(s), {len(answered)} answered, "
              f"{len(empties)} with no answer, "
              f"{len(rows) - len(punts) - len(answered) - len(empties)} unresolved")

        # Clean rows are marked immediately. Punts are marked only after the
        # mail is away - marking first and failing to send loses the miss
        # permanently and silently, which is the failure this module prevents.
        _mark(conn, answered + empties)

        if not punts:
            if empties:
                print(f"punt_monitor: {len(empties)} answer(s) missing, no punts")
            return

        subject, body = _compose(punts, len(empties))
        if _send(subject, body):
            _mark(conn, [r[0] for r in punts])


if __name__ == "__main__":
    main()
