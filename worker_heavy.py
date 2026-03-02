#!/usr/bin/env python
"""
worker_heavy.py — Railway cron worker for heavy pipeline jobs (torch + transformers).

Usage:
    python worker_heavy.py fetch-news
    python worker_heavy.py fetch-social
    python worker_heavy.py fetch-social-brands

Each subcommand runs an ordered list of scripts via subprocess, matching the
corresponding GH Actions workflow step-for-step. On any step failure, sends
a failure notification email and exits non-zero.

Exit code 2 from fetch_posts.py = X API quota hit (non-fatal, continues).
"""

import os
import sys
import subprocess
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

# Each job is (label, list of (step_name, command) tuples)
JOBS = {
    "fetch-news": {
        "label": "Fetch News (Hourly)",
        "steps": [
            ("Fetch markets", [sys.executable, "fetch_markets.py"]),
            ("Fetch economic indicators", [sys.executable, "fetch_economic_indicators.py"]),
            ("Fetch commodities", [sys.executable, "fetch_commodities.py"]),
            ("Fetch brand stocks", [sys.executable, "fetch_brand_stocks.py"]),
            ("Fetch news (RSS)", [sys.executable, "fetch_news_rss.py"]),
            ("Score news", [sys.executable, "score_empathy.py", "news.csv", "news_scored.csv"]),
            ("Save news to PostgreSQL", [sys.executable, "save_to_db.py", "news_scored.csv", "news_scored"]),
            ("Calculate longevity", [sys.executable, "calculate_longevity.py"]),
            ("Calculate density", [sys.executable, "calculate_density.py"]),
            ("Calculate scarcity", [sys.executable, "calculate_scarcity.py"]),
            ("Run alert detection", [sys.executable, "alert_pipeline.py"]),
            ("Cleanup old data", [sys.executable, "cleanup_old_data.py"]),
        ],
    },
    "fetch-social": {
        "label": "Fetch Social (3x Daily)",
        "steps": [
            ("Fetch X posts", [sys.executable, "fetch_posts.py"]),
            ("Score social", [sys.executable, "score_empathy.py", "social.csv", "social_scored.csv"]),
            ("Save social to PostgreSQL", [sys.executable, "save_to_db.py", "social_scored.csv", "social_scored"]),
            ("Calculate longevity", [sys.executable, "calculate_longevity.py"]),
            ("Calculate density", [sys.executable, "calculate_density.py"]),
            ("Calculate scarcity", [sys.executable, "calculate_scarcity.py"]),
            ("Run alert detection", [sys.executable, "alert_pipeline.py"]),
        ],
    },
    "fetch-social-brands": {
        "label": "Fetch Social - Brand Watchlist (Daily)",
        "steps": [
            ("Fetch brand X posts", [sys.executable, "fetch_posts.py", "--brand-queries"]),
            ("Score social", [sys.executable, "score_empathy.py", "social.csv", "social_scored.csv"]),
            ("Save social to PostgreSQL", [sys.executable, "save_to_db.py", "social_scored.csv", "social_scored"]),
            ("Calculate longevity", [sys.executable, "calculate_longevity.py"]),
            ("Calculate density", [sys.executable, "calculate_density.py"]),
            ("Calculate scarcity", [sys.executable, "calculate_scarcity.py"]),
            ("Run alert detection", [sys.executable, "alert_pipeline.py"]),
        ],
    },
}

# fetch_posts.py returns exit code 2 when X API quota is hit — non-fatal
NON_FATAL_EXIT_CODES = {2}


def run_step(step_name: str, command: list, step_num: int, total: int) -> bool:
    """Run a single pipeline step. Returns True on success, False on failure."""
    print(f"\n--- Step {step_num}/{total}: {step_name} ---", flush=True)
    try:
        result = subprocess.run(command, timeout=1800)  # 30 min timeout
        if result.returncode == 0:
            print(f"OK: {step_name}", flush=True)
            return True
        elif result.returncode in NON_FATAL_EXIT_CODES:
            print(f"WARN: {step_name} exited with code {result.returncode} (non-fatal, continuing)", flush=True)
            return True
        else:
            print(f"FAIL: {step_name} exited with code {result.returncode}", flush=True)
            return False
    except subprocess.TimeoutExpired:
        print(f"FAIL: {step_name} timed out after 30 minutes", flush=True)
        return False


def send_failure_email(job_label: str, failed_step: str):
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
        f"Failed step: {failed_step}\n\n"
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
        print(f"Usage: python worker_heavy.py <{valid}>")
        sys.exit(1)

    job_name = sys.argv[1]
    job = JOBS[job_name]
    job_label = job["label"]
    steps = job["steps"]

    print("=" * 60)
    print(f"RAILWAY WORKER: {job_label}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Job: {job_name} ({len(steps)} steps)")
    print("=" * 60)

    for i, (step_name, command) in enumerate(steps, 1):
        ok = run_step(step_name, command, i, len(steps))
        if not ok:
            print(f"\n{job_label} FAILED at step {i}/{len(steps)}: {step_name}")
            send_failure_email(job_label, step_name)
            sys.exit(1)

    print(f"\n{job_label} completed successfully ({len(steps)} steps).")
    sys.exit(0)


if __name__ == "__main__":
    main()
