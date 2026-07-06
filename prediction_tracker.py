#!/usr/bin/env python
"""
prediction_tracker.py — Moodlight prediction tracker / proof library.

Logs specific, falsifiable cultural "calls" at a point in time, captures a
SELF-CONTAINED snapshot of the supporting signals as evidence (so it survives
the 30-day data-retention wipe), and records whether each call played out.
Produces a documented, evidence-traced track record — the "explainable" demo.

Design guardrails (keep the proof honest):
  - A "call" is CURATED (falsifiable, human-readable), not a raw alert. Log the
    calls your outputs make (radar/brief/anomaly), or bind one to an alert.
  - Evidence is stored as JSONB IN this table (full text + scores), NOT as
    references to news_scored/social_scored (those are pruned at 30 days).
  - RESOLUTION is human judgment — you can't auto-know a cultural call came true.
    The daily pass surfaces due-for-resolution calls; you resolve them.

CLI:
    python prediction_tracker.py log "Corridos tumbados cross to US mainstream" \
        --topic music --horizon 60 --confidence 7
    python prediction_tracker.py resolve 12 played_out "Hit Billboard Hot 100 in Aug"
    python prediction_tracker.py report
    python prediction_tracker.py                 # daily pass: due list + record

Cron (via worker_lightweight.py prediction-log): runs the daily pass.
"""

import os
import sys
import json
import math
import hashlib
import argparse
from datetime import datetime, timezone, timedelta, date

import pandas as pd
from sqlalchemy import create_engine, text as sql_text
from dotenv import load_dotenv

load_dotenv()

VALID_OUTCOMES = {"played_out", "missed", "partial"}
EVIDENCE_TOP_N = 8


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    return create_engine(db_url, pool_pre_ping=True, pool_size=2, max_overflow=2)


def ensure_predictions_table(engine):
    """Create the predictions table if it doesn't exist. Idempotent."""
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                prediction_type VARCHAR(50) DEFAULT 'call',
                statement TEXT NOT NULL,
                statement_hash VARCHAR(32) NOT NULL,
                brand VARCHAR(200),
                topic VARCHAR(200),
                confidence INTEGER,
                horizon_days INTEGER,
                prediction_date DATE NOT NULL,
                due_date DATE,
                evidence JSONB,
                source VARCHAR(120) DEFAULT 'manual',

                outcome_status VARCHAR(20),
                outcome_summary TEXT,
                outcome_evidence JSONB,
                resolved_date DATE,

                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),

                UNIQUE (prediction_date, statement_hash)
            )
        """))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions (prediction_date)",
            "CREATE INDEX IF NOT EXISTS idx_predictions_due ON predictions (due_date)",
            "CREATE INDEX IF NOT EXISTS idx_predictions_outcome ON predictions (outcome_status)",
            "CREATE INDEX IF NOT EXISTS idx_predictions_brand ON predictions (brand)",
            "CREATE INDEX IF NOT EXISTS idx_predictions_topic ON predictions (topic)",
        ):
            conn.execute(sql_text(stmt))
        conn.commit()


def _na(v):
    """Return None for NaN/NaT/None/empty-string, else the value unchanged."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, str) and not v.strip():
        return None
    return v


def _json_safe(obj):
    """Recursively coerce a value into something JSONB accepts.
    Drops NaN/NaT (JSONB rejects NaN); converts dates/timestamps/Decimals/numpy."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, (str, int)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)


def _rows_subset(df, keys, limit):
    """Top `limit` rows of df as list of dicts, keeping only `keys` that exist."""
    out = []
    if df is None or df.empty:
        return out
    present = [k for k in keys if k in df.columns]
    for _, row in df.head(limit).iterrows():
        out.append({k: _json_safe(row[k]) for k in present})
    return out


def _capture_evidence(engine, brand=None, topic=None, top_n=EVIDENCE_TOP_N):
    """Snapshot the signals supporting a call, self-contained (survives the wipe).
    Never raises — partial capture records a 'capture_errors' note instead."""
    brand, topic = _na(brand), _na(topic)
    ev = {"captured_at": datetime.now(timezone.utc).isoformat(),
          "brand": brand, "topic": topic}

    # Top recent news/social signals — full text + scores kept INLINE
    news_keys = ["text", "source", "link", "topic", "empathy_score",
                 "intensity", "emotion_top_1", "created_at"]
    for table, key in (("news_scored", "top_news"), ("social_scored", "top_social")):
        try:
            conds, params = [], {"n": top_n}
            if brand:
                conds.append("text ILIKE :brand")
                params["brand"] = f"%{brand}%"
            if topic:
                conds.append("topic = :topic")
                params["topic"] = topic
            where = (" WHERE " + " OR ".join(conds)) if conds else ""
            df = pd.read_sql(
                sql_text(f"SELECT * FROM {table}{where} ORDER BY created_at DESC LIMIT :n"),
                engine, params=params,
            )
            ev[key] = _rows_subset(df, news_keys, top_n)
            ev.setdefault("counts", {})[table] = int(len(df))
        except Exception as e:
            ev.setdefault("capture_errors", []).append(f"{table}: {e}")

    # Latest VLDS snapshot for the topic
    if topic:
        try:
            df = pd.read_sql(
                sql_text("SELECT * FROM topic_vlds_snapshots WHERE topic = :t "
                         "ORDER BY snapshot_date DESC LIMIT 1"),
                engine, params={"t": topic},
            )
            if not df.empty:
                ev["vlds"] = {k: _json_safe(df.iloc[0][k]) for k in df.columns}
        except Exception as e:
            ev.setdefault("capture_errors", []).append(f"vlds: {e}")

    # Latest metric values (global + brand/topic scope)
    metrics = {}
    for scope, name in (("global", None), ("brand", brand), ("topic", topic)):
        if scope != "global" and not name:
            continue
        try:
            conds, params = ["scope = :scope"], {"scope": scope}
            if name:
                conds.append("scope_name = :name")
                params["name"] = name
            df = pd.read_sql(
                sql_text("SELECT metric_name, metric_value, snapshot_date "
                         f"FROM metric_snapshots WHERE {' AND '.join(conds)} "
                         "ORDER BY snapshot_date DESC LIMIT 40"),
                engine, params=params,
            )
            seen = {}
            for _, r in df.iterrows():
                m = r["metric_name"]
                if m not in seen:
                    seen[m] = _json_safe(r["metric_value"])
            if seen:
                metrics[scope if not name else f"{scope}:{name}"] = seen
        except Exception as e:
            ev.setdefault("capture_errors", []).append(f"metrics[{scope}]: {e}")
    if metrics:
        ev["metrics"] = metrics

    # Market context
    try:
        spy = pd.read_sql(
            sql_text("SELECT price FROM markets WHERE symbol='SPY' "
                     "ORDER BY timestamp DESC LIMIT 1"),
            engine,
        )
        if not spy.empty:
            ev.setdefault("market", {})["spy_price"] = _json_safe(spy.iloc[0]["price"])
    except Exception:
        pass

    return _json_safe(ev)


def log_prediction(engine, statement, brand=None, topic=None, confidence=None,
                   horizon_days=None, source="manual", capture=True):
    """Log a curated, falsifiable call + a self-contained evidence snapshot.
    Returns the new prediction id, or None if it was a duplicate for today."""
    ensure_predictions_table(engine)
    statement = (statement or "").strip()
    if not statement:
        raise ValueError("statement is required")

    brand, topic = _na(brand), _na(topic)
    today = datetime.now(timezone.utc).date()
    due = today + timedelta(days=int(horizon_days)) if horizon_days else None
    shash = hashlib.md5(statement.lower().encode("utf-8")).hexdigest()

    evidence = _capture_evidence(engine, brand, topic) if capture else None

    with engine.connect() as conn:
        result = conn.execute(
            sql_text("""
                INSERT INTO predictions
                    (prediction_type, statement, statement_hash, brand, topic,
                     confidence, horizon_days, prediction_date, due_date, evidence, source)
                VALUES
                    ('call', :statement, :shash, :brand, :topic,
                     :confidence, :horizon, :pdate, :due, CAST(:evidence AS JSONB), :source)
                ON CONFLICT (prediction_date, statement_hash) DO NOTHING
                RETURNING id
            """),
            {
                "statement": statement, "shash": shash,
                "brand": brand, "topic": topic,
                "confidence": confidence, "horizon": horizon_days,
                "pdate": today, "due": due,
                "evidence": json.dumps(evidence) if evidence is not None else None,
                "source": source,
            },
        )
        row = result.fetchone()
        conn.commit()

    if row:
        pid = row[0]
        tail = "…" if len(statement) > 70 else ""
        print(f"  Logged prediction #{pid}: {statement[:70]}{tail}")
        return pid
    print(f"  Duplicate call for today — not re-logged: {statement[:70]}")
    return None


def capture_from_alert(engine, alert_id, statement=None, horizon_days=None, confidence=None):
    """Turn a detected alert into a logged call (curated — you pick the alert)."""
    ensure_predictions_table(engine)
    df = pd.read_sql(
        sql_text("SELECT id, brand, topic, title, summary FROM alerts WHERE id = :id"),
        engine, params={"id": int(alert_id)},
    )
    if df.empty:
        print(f"  No alert with id {alert_id}")
        return None
    a = df.iloc[0]
    stmt = statement or _na(a.get("summary")) or _na(a.get("title")) or ""
    stmt = str(stmt).strip()
    if not stmt:
        print(f"  Alert {alert_id} has no usable statement text")
        return None
    return log_prediction(
        engine, stmt,
        brand=_na(a.get("brand")), topic=_na(a.get("topic")),
        confidence=confidence, horizon_days=horizon_days,
        source=f"alert:{alert_id}",
    )


def resolve_prediction(engine, prediction_id, status, summary="", capture_outcome=True):
    """Mark a call resolved. status in {played_out, missed, partial}."""
    ensure_predictions_table(engine)
    status = (status or "").strip().lower()
    if status not in VALID_OUTCOMES:
        raise ValueError(f"status must be one of {sorted(VALID_OUTCOMES)}")

    outcome_ev = None
    if capture_outcome:
        row = pd.read_sql(
            sql_text("SELECT brand, topic FROM predictions WHERE id = :id"),
            engine, params={"id": int(prediction_id)},
        )
        if not row.empty:
            outcome_ev = _capture_evidence(
                engine, _na(row.iloc[0]["brand"]), _na(row.iloc[0]["topic"])
            )

    with engine.connect() as conn:
        result = conn.execute(
            sql_text("""
                UPDATE predictions
                SET outcome_status = :status,
                    outcome_summary = :summary,
                    outcome_evidence = CAST(:oev AS JSONB),
                    resolved_date = :rdate,
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "status": status, "summary": summary,
                "oev": json.dumps(outcome_ev) if outcome_ev is not None else None,
                "rdate": datetime.now(timezone.utc).date(),
                "id": int(prediction_id),
            },
        )
        conn.commit()
    if result.rowcount:
        print(f"  Prediction #{prediction_id} resolved: {status}")
    else:
        print(f"  No prediction with id {prediction_id}")


def list_due(engine):
    """Unresolved calls whose horizon has elapsed (ready to resolve)."""
    return pd.read_sql(
        sql_text("""
            SELECT id, prediction_date, due_date, brand, topic, statement
            FROM predictions
            WHERE outcome_status IS NULL AND due_date IS NOT NULL
              AND due_date <= :today
            ORDER BY due_date ASC
        """),
        engine, params={"today": datetime.now(timezone.utc).date()},
    )


def accuracy_report(engine):
    """Track-record summary: counts by outcome + hit rate on resolved calls."""
    df = pd.read_sql(
        sql_text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE outcome_status IS NULL) AS open,
                COUNT(*) FILTER (WHERE outcome_status = 'played_out') AS played_out,
                COUNT(*) FILTER (WHERE outcome_status = 'partial') AS partial,
                COUNT(*) FILTER (WHERE outcome_status = 'missed') AS missed
            FROM predictions
        """),
        engine,
    )
    r = df.iloc[0]
    resolved = int(r["played_out"]) + int(r["partial"]) + int(r["missed"])
    hit = (int(r["played_out"]) / resolved * 100) if resolved else 0.0
    tail = "" if resolved else "  (none resolved yet)"
    return "\n".join([
        f"  Predictions: {int(r['total'])} total | {int(r['open'])} open | {resolved} resolved",
        f"  Resolved -> played_out: {int(r['played_out'])} | "
        f"partial: {int(r['partial'])} | missed: {int(r['missed'])}",
        f"  Hit rate (played_out / resolved): {hit:.0f}%{tail}",
    ])


def report_detail(engine):
    """Per-call listing with a STATUS column (open first, then by due date)."""
    df = pd.read_sql(
        sql_text("""
            SELECT id, COALESCE(outcome_status, 'open') AS status,
                   due_date, source, statement
            FROM predictions
            ORDER BY (outcome_status IS NOT NULL),
                     due_date ASC NULLS LAST, id ASC
        """),
        engine,
    )
    if df.empty:
        return "  (no predictions logged yet)"
    lines = [f"  {'ID':<5} {'STATUS':<11} {'DUE':<12} {'SOURCE':<20} CALL"]
    for _, r in df.iterrows():
        stmt = str(r["statement"])
        stmt = (stmt[:58] + "…") if len(stmt) > 58 else stmt
        due = str(r["due_date"]) if _na(r["due_date"]) is not None else "—"
        src = str(_na(r["source"]) or "—")[:20]
        lines.append(f"  #{int(r['id']):<4} {r['status']:<11} {due:<12} {src:<20} {stmt}")
    return "\n".join(lines)


# ── CLI / worker ────────────────────────────────────────────────────────────

def _cli_log(engine, args):
    p = argparse.ArgumentParser(prog="prediction_tracker.py log")
    p.add_argument("statement")
    p.add_argument("--brand")
    p.add_argument("--topic")
    p.add_argument("--horizon", type=int, help="time horizon in days")
    p.add_argument("--confidence", type=int, help="1-10")
    p.add_argument("--source", default="manual")
    ns = p.parse_args(args)
    log_prediction(engine, ns.statement, brand=ns.brand, topic=ns.topic,
                   confidence=ns.confidence, horizon_days=ns.horizon, source=ns.source)


def _cli_resolve(engine, args):
    p = argparse.ArgumentParser(prog="prediction_tracker.py resolve")
    p.add_argument("id", type=int)
    p.add_argument("status", help="played_out | missed | partial")
    p.add_argument("summary", nargs="?", default="")
    ns = p.parse_args(args)
    resolve_prediction(engine, ns.id, ns.status, ns.summary)


def _daily_pass(engine):
    """Default (cron) pass: surface due-for-resolution calls + print the record."""
    due = list_due(engine)
    if not due.empty:
        print(f"\n  {len(due)} call(s) due for resolution:")
        for _, r in due.iterrows():
            who = r["brand"] or r["topic"] or "—"
            print(f"    #{int(r['id'])} (due {r['due_date']}) [{who}] "
                  f"{str(r['statement'])[:80]}")
    else:
        print("\n  No calls currently due for resolution.")
    print("\n  Track record:")
    print(accuracy_report(engine))


def main():
    engine = _get_engine()
    ensure_predictions_table(engine)
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 60)
    print("PREDICTION TRACKER")
    print("=" * 60)

    if cmd == "log":
        _cli_log(engine, sys.argv[2:])
    elif cmd == "resolve":
        _cli_resolve(engine, sys.argv[2:])
    elif cmd == "report":
        print(accuracy_report(engine))
        print()
        print(report_detail(engine))
    else:
        # None, "due", or the worker's job name ("prediction-log") -> daily pass
        _daily_pass(engine)

    print("\nDone.")


if __name__ == "__main__":
    main()
