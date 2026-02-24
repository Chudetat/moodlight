#!/usr/bin/env python
"""
worker_lightweight.py — Consolidated Railway cron worker for lightweight jobs.

Usage:
    python worker_lightweight.py brief
    python worker_lightweight.py weekly-digest
    python worker_lightweight.py scheduled-reports

Each subcommand calls the existing main() from the corresponding module.
On failure, sends an email notification (replicates GH Actions failure step).
"""

import os
import sys
import traceback
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

JOBS = {
    "brief": {
        "module": "generate_brief",
        "label": "Intelligence Brief (2x Daily)",
    },
    "weekly-digest": {
        "module": "generate_weekly_digest",
        "label": "Weekly Strategic Digest",
    },
    "scheduled-reports": {
        "module": "run_scheduled_reports",
        "label": "Scheduled Reports",
    },
}


def send_failure_email(job_label: str, error_msg: str):
    """Send a failure notification email, replicating the GH Actions pattern."""
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = os.getenv("EMAIL_RECIPIENT", "")

    if not all([sender, password, recipient]):
        print("Email credentials not configured — cannot send failure notification.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = (
        f"The {job_label} pipeline failed at {timestamp}.\n\n"
        f"Error:\n{error_msg}\n\n"
        f"Check Railway logs for full details."
    )

    msg = MIMEText(body)
    msg["Subject"] = f"[Moodlight] Pipeline Failed: {job_label}"
    msg["From"] = sender
    msg["To"] = recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("Failure notification sent.")
    except Exception as e:
        print(f"Could not send failure notification: {e}")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in JOBS:
        valid = ", ".join(JOBS.keys())
        print(f"Usage: python worker_lightweight.py <{valid}>")
        sys.exit(1)

    job_name = sys.argv[1]
    job = JOBS[job_name]
    module_name = job["module"]
    job_label = job["label"]

    print("=" * 60)
    print(f"RAILWAY WORKER: {job_label}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Job: {job_name}")
    print("=" * 60)

    try:
        mod = __import__(module_name)
        mod.main()
        print(f"\n{job_label} completed successfully.")
        sys.exit(0)
    except SystemExit as e:
        # main() calls sys.exit(0) on success in some modules — let that through
        if e.code == 0 or e.code is None:
            print(f"\n{job_label} completed successfully.")
            sys.exit(0)
        # Non-zero exit from the module itself
        error_msg = f"Module exited with code {e.code}"
        print(f"\n{job_label} FAILED: {error_msg}")
        send_failure_email(job_label, error_msg)
        sys.exit(1)
    except Exception:
        error_msg = traceback.format_exc()
        print(f"\n{job_label} FAILED:\n{error_msg}")
        send_failure_email(job_label, error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
