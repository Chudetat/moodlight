#!/usr/bin/env python
"""Run scheduled reports — queries report_schedules, generates and emails due reports."""
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()


def _get_engine():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL not set")
        return None
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    return create_engine(db_url, pool_pre_ping=True, pool_size=1, max_overflow=0)


def main():
    engine = _get_engine()
    if not engine:
        print("No database connection.")
        sys.exit(1)

    # Track pipeline run
    run_id = None
    try:
        from alert_pipeline import start_pipeline_run, complete_pipeline_run
        run_id = start_pipeline_run(engine, "scheduled_reports")
    except Exception as e:
        print(f"WARNING: start_pipeline_run tracking failed: {e}")

    processed = 0
    errors = 0

    try:
        with engine.connect() as conn:
            due = conn.execute(text("""
                SELECT rs.id, rs.username, rs.subject, rs.subject_type,
                       rs.frequency, rs.days_lookback, u.email
                FROM report_schedules rs
                JOIN users u ON rs.username = u.username
                WHERE rs.enabled = TRUE
                  AND (rs.next_run IS NULL OR rs.next_run <= NOW() AT TIME ZONE 'UTC')
            """)).fetchall()

            if not due:
                print("No scheduled reports due.")
            else:
                print(f"Found {len(due)} scheduled report(s) due.")

            from generate_report import generate_intelligence_report, email_report

            for row in due:
                sched_id, uname, subject, subject_type, frequency, days_lookback, email = row
                print(f"Generating report for {uname}: {subject} ({subject_type}, {days_lookback}d)")

                try:
                    report_text = generate_intelligence_report(
                        engine, subject, days=days_lookback, subject_type=subject_type
                    )

                    email_ok = True
                    if email:
                        email_ok = email_report(report_text, subject, email, days=days_lookback)
                        if email_ok:
                            print(f"  Emailed to {email}")
                        else:
                            print(f"  Email failed for {email}, will retry next run")
                    else:
                        print(f"  No email on file for {uname}, skipping email")

                    if not email_ok:
                        errors += 1
                        continue

                    # Update schedule timestamps
                    now = datetime.now(timezone.utc)
                    if frequency == "daily":
                        next_run = now + timedelta(days=1)
                    else:
                        next_run = now + timedelta(weeks=1)

                    conn.execute(text("""
                        UPDATE report_schedules
                        SET last_run = :now, next_run = :next_run, updated_at = :now
                        WHERE id = :id
                    """), {"now": now, "next_run": next_run, "id": sched_id})
                    conn.commit()
                    processed += 1

                except Exception as e:
                    print(f"  Error processing schedule {sched_id}: {e}")
                    errors += 1

        print(f"Done. Processed: {processed}, Errors: {errors}")

        if run_id:
            try:
                complete_pipeline_run(engine, run_id, "success", processed)
            except Exception as e:
                print(f"WARNING: complete_pipeline_run success tracking failed: {e}")

    except Exception as e:
        print(f"Fatal error: {e}")
        if run_id:
            try:
                from alert_pipeline import complete_pipeline_run
                complete_pipeline_run(engine, run_id, "failed", processed, str(e)[:500])
            except Exception as e2:
                print(f"WARNING: complete_pipeline_run failure tracking failed: {e2}")
        sys.exit(1)


if __name__ == "__main__":
    main()
