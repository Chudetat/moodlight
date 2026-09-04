"""
ask_alerts.py — tell Daniel when a real person asks a real question.

Someone at or near Old Mutual typed their live strategic problem into Ask on a
Thursday morning and got a genuinely good answer back. He found out about it a
day later, because a query was run by hand. Seven substantive questions arrived
from four continents in a week and every one of them sat in a table nobody was
watching.

The product already captures. What it never did was tell anyone, and a lead
nobody sees is the same as no lead.

WHY A CRON JOB AND NOT A HOOK IN THE ASK ENDPOINT
-------------------------------------------------
The obvious build is to fire an email from ask_moodlight_api the moment a
question lands. Three reasons not to: that service has no mail credentials and
putting a Gmail app password on the public-facing widget backend to send one
notification is a bad trade; anything in the request path can add latency or
fail in front of a stranger; and one email per question is worse than a digest
the moment two arrive at once. worker_lightweight already holds the credentials
and already runs on cron.

WHAT COUNTS AS WORTH INTERRUPTING SOMEONE FOR
---------------------------------------------
Sixty characters and a resolved brand or topic. Real questions from working
professionals run long and specific - "How does Old Mutual modernise its legacy
without alienating the older, loyal customers who built its reputation" is 110
characters. Test pokes are short - "What is the cultural read on Nike right
now?" is 44. That single threshold separates the seven real questions of the
last week from the six that were ours.

The bar is deliberately loose. At roughly one a day, a false positive costs a
glance and a false negative costs a client.
"""

import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

# Real questions are long. This is the whole filter, and it is enough.
_MIN_QUESTION_CHARS = 60

# On a first run, do not mail out months of history. Anything older than this
# is archive, not a lead.
_MAX_AGE_HOURS = 72

# A runaway would be worse than silence.
_MAX_PER_RUN = 25

_ANSWER_EXCERPT = 320

# Put this in a question when deliberately exercising production Ask, and it
# will not be reported as inbound. Length alone does not separate our testing
# from a real question - the dominant-mood probe is 64 characters.
_TEST_MARKER = "[qa]"


def _engine():
    from db_helper import make_engine
    url = os.getenv("DATABASE_URL", "")
    return make_engine(url) if url else None


def _ensure_column(conn):
    from sqlalchemy import text as sql_text
    conn.execute(sql_text(
        "ALTER TABLE ask_queries ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ"))
    conn.commit()


def _fetch_new(conn):
    """New, substantive, first-of-its-kind questions.

    Three filters, and the second two exist because the first was not enough.
    A dry run against real data showed 11 would-be alerts of which 5 were our
    own testing: "In one sentence, what is the dominant mood in culture right
    now?" is 64 characters, clears the length bar, and had been run three times
    that week.

    So: alert once per DISTINCT question. Testing repeats verbatim; a stranger
    with a real problem does not ask the identical sentence three times. And
    skip anything carrying the test marker, which is what we use when poking
    production deliberately.
    """
    from sqlalchemy import text as sql_text
    return conn.execute(sql_text(f"""
        SELECT DISTINCT ON (LOWER(TRIM(question)))
               id, created_at, detected_brand, detected_topic,
               recommended_agent, question, COALESCE(answer, '')
          FROM ask_queries
         WHERE notified_at IS NULL
           AND created_at > NOW() - INTERVAL '{_MAX_AGE_HOURS} hours'
           AND LENGTH(question) >= {_MIN_QUESTION_CHARS}
           AND (detected_brand IS NOT NULL OR detected_topic IS NOT NULL)
           AND question NOT ILIKE '%{_TEST_MARKER}%'
           AND NOT EXISTS (
                 SELECT 1 FROM ask_queries older
                  WHERE LOWER(TRIM(older.question)) = LOWER(TRIM(ask_queries.question))
                    AND older.notified_at IS NOT NULL
               )
         ORDER BY LOWER(TRIM(question)), created_at
         LIMIT {_MAX_PER_RUN}
    """)).fetchall()


def _mark(conn, ids):
    from sqlalchemy import text as sql_text
    conn.execute(sql_text(
        "UPDATE ask_queries SET notified_at = NOW() WHERE id = ANY(:ids)"), {"ids": list(ids)})
    conn.commit()


def _compose(rows):
    named = [r[2] for r in rows if r[2]]
    if named:
        subject = f"Ask Moodlight: {named[0]}" + (f" and {len(rows)-1} more" if len(rows) > 1 else "")
    else:
        subject = f"Ask Moodlight: {len(rows)} question{'s' if len(rows) > 1 else ''}"

    parts = [
        f"{len(rows)} question{'s' if len(rows) > 1 else ''} worth a look.",
        "",
        "-" * 62,
        "",
    ]
    for _id, ts, brand, topic, agent, question, answer in rows:
        parts.append(f"{ts:%b %d, %H:%M UTC}")
        if brand:
            parts.append(f"Brand: {brand}")
        if topic:
            parts.append(f"Topic: {topic}")
        if agent:
            parts.append(f"Routed to: {agent}")
        parts.append("")
        parts.append(f'  "{question.strip()}"')
        excerpt = " ".join((answer or "").split())[:_ANSWER_EXCERPT]
        if excerpt:
            parts.append("")
            parts.append(f"  We said: {excerpt}...")
        parts.append("")
        parts.append("-" * 62)
        parts.append("")
    parts.append("These are people who found Moodlight on their own and asked it")
    parts.append("something they actually need answered.")
    return subject, "\n".join(parts)


def _send(subject, body):
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    # Deliberately NOT EMAIL_RECIPIENT. That list carries investors and an
    # external reader; inbound leads are not for them.
    recipient = os.getenv("ASK_ALERT_TO") or "daniel@moodlightintel.com"
    if not all([sender, password]):
        print("ask_alerts: email credentials not configured, nothing sent")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"ask_alerts: sent to {recipient}")
    return True


def main():
    engine = _engine()
    if not engine:
        print("ask_alerts: DATABASE_URL not set")
        return
    with engine.connect() as conn:
        _ensure_column(conn)
        rows = _fetch_new(conn)
        if not rows:
            print("ask_alerts: nothing new")
            return
        print(f"ask_alerts: {len(rows)} new question(s)")
        subject, body = _compose(rows)
        # Mark only after the mail is away. Marking first and failing to send
        # loses the lead permanently and silently, which is the failure this
        # module exists to prevent.
        if _send(subject, body):
            _mark(conn, [r[0] for r in rows])


if __name__ == "__main__":
    main()
