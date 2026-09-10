"""
marketplace_alerts.py — tell Daniel when a stranger uses the agent marketplace.

186 runs. 26 email addresses. Zero notifications, ever. There has never been
any notification code for marketplace_runs at all, so every one of those people
typed a real brief into Moodlight, left an address to receive the output, and
nobody was told they existed.

Some of them are exactly who the product is for: a strategist at Ogilvy running
the Copywriter six times on a diabetes charity, a CCO brief on an OCBC credit
card, an equity firm auditing its own brand to institutional LPs. One of them,
matei@rxmcreative.com, is the creative director behind the Rivoli EyeZone
session in the query log - the one who asked ten times for lines, said "too
lame and obvious", and left. The address was sitting in the table the whole
time.

PER PERSON, NOT PER RUN
-----------------------
186 rows against 26 addresses. Alerting per row would have sent 186 emails,
most of them our own testing, and an alert nobody reads is the same as no
alert. So the unit is a person: you hear about an address the first time it
appears, and again when someone already known comes back after a real gap.

WHAT THAT DELIBERATELY EXCLUDES
-------------------------------
Continued activity from someone recently alerted about. A user who ran three
agents yesterday and four more today produces nothing today, by design. The
returning rule below is what stops that from becoming permanent silence: once
their runs stop for _GAP_DAYS and then resume, you hear about it again.

WHY IT SEEDS ON FIRST RUN
-------------------------
Without seeding, the first execution would treat every address in the table as
new and send 26 alerts about people from April. Rows older than _SEED_DAYS are
marked as already-notified without mailing, once, so history is acknowledged
rather than replayed.
"""

import os
import smtplib
from email.mime.text import MIMEText

# Addresses that are us. Paul, Derric and Stein are deliberately NOT here -
# they are real users of the marketplace and their activity is worth knowing.
# Trim or extend this list; it is the only knob that decides who is invisible.
INTERNAL = (
    "daniel@moodlightintel.com",
    "intel@moodlightintel.com",
    "daniel.chu@me.com",
    "chudetat@gmail.com",
)

# A known user coming back after this long is news again.
_GAP_DAYS = 14

# On the very first run, anything older than this is history, not a lead.
_SEED_DAYS = 7

# A runaway would be worse than silence.
_MAX_PER_RUN = 25

_BRIEF_EXCERPT = 300


def _engine():
    from db_helper import make_engine
    url = os.getenv("DATABASE_URL", "")
    return make_engine(url) if url else None


def _ensure_column(conn):
    from sqlalchemy import text as sql_text
    conn.execute(sql_text(
        "ALTER TABLE marketplace_runs ADD COLUMN IF NOT EXISTS notified_at TIMESTAMPTZ"))
    conn.commit()


def _seed_if_first_run(conn):
    """Mark old history as acknowledged, once, without mailing anything.

    Returns the number of rows seeded. Detecting "first run" by the absence of
    any notified row is safe: after this runs once, at least one row is marked
    forever, so it can never fire twice.
    """
    from sqlalchemy import text as sql_text
    already = conn.execute(sql_text(
        "SELECT COUNT(*) FROM marketplace_runs WHERE notified_at IS NOT NULL")).scalar()
    if already:
        return 0
    n = conn.execute(sql_text(
        f"UPDATE marketplace_runs SET notified_at = NOW() "
        f"WHERE notified_at IS NULL "
        f"  AND created_at < NOW() - INTERVAL '{_SEED_DAYS} days'")).rowcount
    conn.commit()
    return n or 0


def _fetch_pending(conn):
    """Un-notified runs grouped by person, with the date of their previous run.

    prev_run deliberately looks only at runs BEFORE this batch, so the gap is
    measured against real prior activity rather than against the batch itself.
    """
    from sqlalchemy import text as sql_text
    return conn.execute(sql_text(f"""
        WITH pending AS (
            SELECT email, MIN(created_at) first_new, MAX(created_at) last_new,
                   COUNT(*) n
              FROM marketplace_runs
             WHERE notified_at IS NULL
               AND email IS NOT NULL AND email <> ''
               AND LOWER(email) NOT IN :internal
             GROUP BY email
        )
        SELECT p.email, p.first_new, p.last_new, p.n,
               (SELECT MAX(o.created_at) FROM marketplace_runs o
                 WHERE o.email = p.email AND o.created_at < p.first_new) prev_run
          FROM pending p
         ORDER BY p.last_new DESC
         LIMIT {_MAX_PER_RUN}
    """), {"internal": tuple(a.lower() for a in INTERNAL)}).fetchall()


def _detail(conn, email, first_new):
    from sqlalchemy import text as sql_text
    return conn.execute(sql_text("""
        SELECT agent, COALESCE(user_input, '')
          FROM marketplace_runs
         WHERE email = :e AND created_at >= :t AND notified_at IS NULL
         ORDER BY created_at DESC LIMIT 4"""),
        {"e": email, "t": first_new}).fetchall()


def _mark(conn, emails, cutoff_by_email):
    """Mark every evaluated run, including ones that produced no alert.

    Leaving a no-alert run un-notified would make it eligible again on the next
    pass forever, and would keep shifting the gap baseline. Everything looked at
    is accounted for.
    """
    if not emails:
        return
    from sqlalchemy import text as sql_text
    for e in emails:
        conn.execute(sql_text(
            "UPDATE marketplace_runs SET notified_at = NOW() "
            "WHERE email = :e AND notified_at IS NULL AND created_at >= :t"),
            {"e": e, "t": cutoff_by_email[e]})
    conn.commit()


def _compose(leads):
    new = [l for l in leads if l["kind"] == "new"]
    subject = (f"Marketplace: {new[0]['email']}" if len(new) == 1 and len(leads) == 1
               else f"Marketplace: {len(leads)} lead" + ("s" if len(leads) > 1 else ""))
    if new and len(leads) > 1:
        subject = f"Marketplace: {len(new)} new, {len(leads) - len(new)} returning"

    parts = ["Someone used the agent marketplace and left an address.", "",
             "-" * 62, ""]
    for l in leads:
        tag = "NEW" if l["kind"] == "new" else f"RETURNING after {l['gap_days']} days"
        parts.append(f"{tag}: {l['email']}")
        parts.append(f"{l['n']} run(s), {l['last_new']:%b %d %H:%M UTC}")
        parts.append("")
        for agent, brief in l["detail"]:
            clean = " ".join((brief or "").split())[:_BRIEF_EXCERPT]
            parts.append(f"  [{agent}] {clean}")
        parts.append("")
        parts.append("-" * 62)
        parts.append("")
    parts.append("The brief is the useful part: it says what they are working on.")
    return subject, "\n".join(parts)


def _send(subject, body):
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    # Same reasoning as ask_alerts: EMAIL_RECIPIENT carries investors and an
    # external reader. Inbound leads are not for them.
    recipient = os.getenv("ASK_ALERT_TO") or "daniel@moodlightintel.com"
    if not all([sender, password]):
        print("marketplace_alerts: email credentials not configured, nothing sent")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)
    print(f"marketplace_alerts: sent to {recipient}")
    return True


def main():
    engine = _engine()
    if not engine:
        # Raise, never return quietly. A lead alert that goes silent when
        # misconfigured reads as "no leads" forever.
        raise RuntimeError("marketplace_alerts: DATABASE_URL not set")

    with engine.connect() as conn:
        _ensure_column(conn)
        seeded = _seed_if_first_run(conn)
        if seeded:
            print(f"marketplace_alerts: seeded {seeded} historical run(s), not mailed")

        rows = _fetch_pending(conn)
        if not rows:
            print("marketplace_alerts: nothing new")
            return

        leads, evaluated, cutoffs = [], [], {}
        for email, first_new, last_new, n, prev_run in rows:
            evaluated.append(email)
            cutoffs[email] = first_new
            if prev_run is None:
                kind, gap = "new", None
            else:
                gap = (first_new - prev_run).days
                if gap < _GAP_DAYS:
                    # Known, recently active. Accounted for, not mailed.
                    continue
                kind = "returning"
            leads.append({"email": email, "kind": kind, "gap_days": gap,
                          "n": n, "last_new": last_new,
                          "detail": _detail(conn, email, first_new)})

        print(f"marketplace_alerts: {len(evaluated)} address(es) evaluated, "
              f"{len(leads)} worth mailing")

        if not leads:
            _mark(conn, evaluated, cutoffs)
            return

        subject, body = _compose(leads)
        # Mark only after the mail is away. Marking first and failing to send
        # loses the lead permanently and silently.
        if _send(subject, body):
            _mark(conn, evaluated, cutoffs)


if __name__ == "__main__":
    main()
