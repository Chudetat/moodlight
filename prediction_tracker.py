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
import html
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
        # Integrity-seal columns (idempotent — safe to run on an existing table)
        for stmt in (
            "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS evidence_sealed TEXT",
            "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS evidence_sha256 VARCHAR(64)",
            "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS sealed_at TIMESTAMPTZ",
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


def _canonical_evidence(evidence):
    """Deterministic JSON text for sealing/hashing — stable across processes.
    The seal (and the trace) are built from THIS text, so what a reader sees is
    byte-for-byte what the hash covers."""
    return json.dumps(evidence, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"))


def _hash_text(s):
    """SHA-256 of a UTF-8 string, hex."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


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
                   horizon_days=None, source="manual", capture=True,
                   prediction_date=None, evidence_override=None):
    """Log a curated, falsifiable call + a self-contained evidence snapshot.
    Returns the new prediction id, or None if it was a duplicate for that date.

    prediction_date: override the call's date, for logging historical calls from
        dated artifacts (e.g. past Radar emails). Defaults to today.
    evidence_override: store this dict as the evidence instead of a live-DB
        snapshot (for historical calls, pass the dated source document itself)."""
    ensure_predictions_table(engine)
    statement = (statement or "").strip()
    if not statement:
        raise ValueError("statement is required")

    brand, topic = _na(brand), _na(topic)
    today = datetime.now(timezone.utc).date()
    pdate = prediction_date or today
    due = pdate + timedelta(days=int(horizon_days)) if horizon_days else None
    shash = hashlib.md5(statement.lower().encode("utf-8")).hexdigest()

    if evidence_override is not None:
        evidence = _json_safe(evidence_override)
    elif capture:
        evidence = _capture_evidence(engine, brand, topic)
    else:
        evidence = None

    # Seal the evidence: canonical text + SHA-256, frozen at write time. This is
    # what makes "nothing changed since we called it" verifiable, not just asserted.
    if evidence is not None:
        sealed_text = _canonical_evidence(evidence)
        ev_hash = _hash_text(sealed_text)
    else:
        sealed_text = ev_hash = None

    with engine.connect() as conn:
        result = conn.execute(
            sql_text("""
                INSERT INTO predictions
                    (prediction_type, statement, statement_hash, brand, topic,
                     confidence, horizon_days, prediction_date, due_date, evidence,
                     evidence_sealed, evidence_sha256, sealed_at, source)
                VALUES
                    ('call', :statement, :shash, :brand, :topic,
                     :confidence, :horizon, :pdate, :due, CAST(:evidence AS JSONB),
                     :sealed_text, :ev_hash,
                     CASE WHEN :ev_hash IS NULL THEN NULL ELSE NOW() END, :source)
                ON CONFLICT (prediction_date, statement_hash) DO NOTHING
                RETURNING id
            """),
            {
                "statement": statement, "shash": shash,
                "brand": brand, "topic": topic,
                "confidence": confidence, "horizon": horizon_days,
                "pdate": pdate, "due": due,
                "evidence": json.dumps(evidence) if evidence is not None else None,
                "sealed_text": sealed_text, "ev_hash": ev_hash,
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


def resolve_prediction(engine, prediction_id, status, summary="", capture_outcome=True,
                       resolved_date=None, outcome_evidence_override=None):
    """Mark a call resolved. status in {played_out, missed, partial}.

    resolved_date: override the resolution date (for historical resolutions).
    outcome_evidence_override: store this dict as the outcome evidence instead of a
        live-DB snapshot (for historical calls, pass the verified external markers)."""
    ensure_predictions_table(engine)
    status = (status or "").strip().lower()
    if status not in VALID_OUTCOMES:
        raise ValueError(f"status must be one of {sorted(VALID_OUTCOMES)}")

    if outcome_evidence_override is not None:
        outcome_ev = _json_safe(outcome_evidence_override)
    elif capture_outcome:
        row = pd.read_sql(
            sql_text("SELECT brand, topic FROM predictions WHERE id = :id"),
            engine, params={"id": int(prediction_id)},
        )
        outcome_ev = _capture_evidence(
            engine, _na(row.iloc[0]["brand"]), _na(row.iloc[0]["topic"])
        ) if not row.empty else None
    else:
        outcome_ev = None

    rdate = resolved_date or datetime.now(timezone.utc).date()
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
                "rdate": rdate,
                "id": int(prediction_id),
            },
        )
        conn.commit()
    if result.rowcount:
        print(f"  Prediction #{prediction_id} resolved: {status}")
    else:
        print(f"  No prediction with id {prediction_id}")


def _evidence_digest(ev, limit=6):
    """Compact an evidence snapshot into a short text block for the draft prompt —
    top signal texts + counts + VLDS/metric highlights, without dumping raw JSON."""
    if not isinstance(ev, dict):
        return "  (no structured evidence)"
    lines = []
    if ev.get("captured_at"):
        lines.append(f"  captured_at: {ev['captured_at']}")
    if ev.get("counts"):
        lines.append(f"  row counts: {ev['counts']}")
    for key, label in (("top_news", "news"), ("top_social", "social")):
        rows = ev.get(key) or []
        if rows:
            lines.append(f"  top {label}:")
            for row in rows[:limit]:
                txt = str(row.get("text", "")).replace("\n", " ").strip()[:200]
                lines.append(f"    - [{row.get('created_at', '')}] ({row.get('source', '')}) {txt}")
    vlds = ev.get("vlds")
    if isinstance(vlds, dict):
        keep = {k: vlds[k] for k in ("topic", "velocity_score", "density_score",
                                     "scarcity_score", "longevity_score", "snapshot_date")
                if k in vlds}
        if keep:
            lines.append(f"  vlds: {keep}")
    if isinstance(ev.get("metrics"), dict) and ev["metrics"]:
        lines.append(f"  metrics: {json.dumps(ev['metrics'])[:400]}")
    if ev.get("evidence_note"):
        lines.append(f"  note: {ev['evidence_note']}")
    return "\n".join(lines) if lines else "  (empty)"


def draft_resolution(engine, prediction_id, model="claude-opus-4-6", max_tokens=2000):
    """ASSISTED RESOLUTION (#3): draft a PROPOSED verdict for a due call, for a human
    to accept or edit. READ-ONLY — writes nothing to the DB. The human still decides;
    resolve_prediction() is the only path that persists a verdict (no auto-grading).

    Pulls FRESH signal for the call's brand/topic at resolution time, sets it beside
    the original prediction + its sealed evidence, and asks the model to propose
    played_out / missed / partial with the specific markers behind it.
    """
    ensure_predictions_table(engine)
    row = pd.read_sql(
        sql_text("SELECT id, prediction_date, due_date, statement, brand, topic, "
                 "confidence, evidence, outcome_status FROM predictions WHERE id = :id"),
        engine, params={"id": int(prediction_id)},
    )
    if row.empty:
        print(f"  No prediction with id {prediction_id}")
        return None
    r = row.iloc[0]
    if _na(r["outcome_status"]):
        print(f"  Note: #{prediction_id} is already resolved ({r['outcome_status']}). "
              "Drafting for a second look — still writes nothing.")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ANTHROPIC_API_KEY not set — cannot draft (this is the module's only LLM call).")
        return None

    brand, topic = _na(r["brand"]), _na(r["topic"])
    fresh = _capture_evidence(engine, brand, topic)  # fresh signal at resolution time
    try:
        original = r["evidence"] if isinstance(r["evidence"], dict) else json.loads(r["evidence"] or "{}")
    except Exception:
        original = {}

    import anthropic  # lazy import: keeps the cron/daily-pass path LLM-dependency-free
    client = anthropic.Anthropic(api_key=api_key)

    homonym_note = ""
    if brand:
        homonym_note = (f"\nNOTE: fresh signal for the brand was name-matched on '{brand}' "
                        "(substring), so it may include same-name namesakes — discount "
                        "anything not actually about the brand.")

    system = (
        "You are a rigorous forecasting analyst helping a human resolve a cultural "
        "prediction. You DRAFT a proposed verdict for the human to accept or edit — you "
        "do NOT decide. Be skeptical and honest: distinguish 'the predicted thing "
        "actually happened' from 'there is merely signal in the space.' Signal presence "
        "is not confirmation. If the evidence is insufficient to judge, say so and "
        "propose 'partial' or recommend external verification. Never inflate a call to "
        "played_out on thin or tangential evidence. Cite the SPECIFIC markers (dated "
        "items, metric moves) behind your read."
    )
    prompt = f"""A falsifiable cultural prediction is now due for resolution. Draft a PROPOSED verdict for the human to accept or edit.

THE CALL (made {r['prediction_date']}, due {r['due_date']}):
"{r['statement']}"
  brand: {brand or '—'} | topic: {topic or '—'} | confidence at call: {_na(r['confidence']) or '—'}/10

ORIGINAL EVIDENCE (what was true when the call was made):
{_evidence_digest(original)}

FRESH SIGNAL (captured now, at resolution time):
{_evidence_digest(fresh)}{homonym_note}

Produce, in this exact structure:
1. PROPOSED VERDICT: one of played_out | missed | partial
2. CONFIDENCE IN THIS VERDICT: low | medium | high
3. OUTCOME MARKERS: the 2-5 specific, dated signals (from FRESH SIGNAL or verifiable public record) that support the verdict — or state plainly that the in-dashboard signal is insufficient and external verification is needed.
4. REASONING: 3-5 sentences. Explicitly separate 'the predicted event occurred' from 'the topic is merely active.'
5. WHAT WOULD CHANGE THE VERDICT: the one piece of evidence that, if the human found it, would flip your read.

Remember: this is a DRAFT. The human makes the final call and may edit freely."""

    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    draft = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()

    print("=" * 60)
    print(f"ASSISTED RESOLUTION DRAFT — prediction #{prediction_id}  (PROPOSED, not saved)")
    print("=" * 60)
    print(draft)
    print("-" * 60)
    print("This wrote NOTHING. To commit YOUR verdict (edit the summary as you see fit):")
    print(f'  python3 prediction_tracker.py resolve {prediction_id} '
          '<played_out|missed|partial> "<your summary>"')
    return {"prediction_id": int(prediction_id), "draft": draft, "model": model}


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


# ── Integrity seal: backfill + verify ───────────────────────────────────────

def seal_existing(engine):
    """One-time: seal any evidence-bearing rows logged before the seal existed.
    Honest by design — sealed_at = now (sealed AS OF today, never backdated to the
    original call date). The hash proves immutability from the seal forward."""
    ensure_predictions_table(engine)
    df = pd.read_sql(
        sql_text("SELECT id, evidence FROM predictions "
                 "WHERE evidence IS NOT NULL AND evidence_sha256 IS NULL "
                 "ORDER BY id"),
        engine,
    )
    if df.empty:
        print("  Nothing to seal — all evidence-bearing calls already sealed.")
        return
    sealed = 0
    with engine.connect() as conn:
        for _, r in df.iterrows():
            ev = r["evidence"]
            if isinstance(ev, str):
                ev = json.loads(ev)
            sealed_text = _canonical_evidence(ev)
            conn.execute(
                sql_text("UPDATE predictions SET evidence_sealed = :s, "
                         "evidence_sha256 = :h, sealed_at = NOW() WHERE id = :id"),
                {"s": sealed_text, "h": _hash_text(sealed_text), "id": int(r["id"])},
            )
            sealed += 1
        conn.commit()
    print(f"  Sealed {sealed} pre-existing call(s) as of now.")


def verify_seal(engine, prediction_id):
    """Recompute the hash from the stored sealed evidence and compare. This is
    what turns the seal into proof: anyone can re-run it. Returns True if intact."""
    ensure_predictions_table(engine)
    df = pd.read_sql(
        sql_text("SELECT id, statement, evidence_sealed, evidence_sha256, sealed_at "
                 "FROM predictions WHERE id = :id"),
        engine, params={"id": int(prediction_id)},
    )
    if df.empty:
        print(f"  No prediction with id {prediction_id}")
        return False
    r = df.iloc[0]
    if _na(r["evidence_sha256"]) is None or _na(r["evidence_sealed"]) is None:
        print(f"  #{prediction_id} has no seal (no evidence captured for this call).")
        return False
    recomputed = _hash_text(r["evidence_sealed"])
    ok = (recomputed == r["evidence_sha256"])
    print(f"  Prediction #{prediction_id}: {str(r['statement'])[:64]}")
    print(f"  Sealed at       : {r['sealed_at']}")
    print(f"  Stored hash     : {r['evidence_sha256']}")
    print(f"  Recomputed hash : {recomputed}")
    print(f"  Result: {'SEALED — evidence intact' if ok else 'TAMPERED — evidence changed since seal'}")
    return ok


# ── Evidence Trace: shareable proof artifact per call ────────────────────────

TRACE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proof_traces")

_TRACE_STYLE = """<style>
  :root{--ground:#E9EBEE;--paper:#FCFCFD;--text:#171A22;--muted:#5A616E;
    --line:#D2D6DD;--accent:#C57A11;--accent-2:#14484E;--tint:#E7EEEE;
    --serif:"Newsreader","Iowan Old Style",Palatino,Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;}
  *{box-sizing:border-box;}
  body{margin:0;background:var(--ground);color:var(--text);font-family:var(--sans);
    line-height:1.6;-webkit-font-smoothing:antialiased;}
  .wrap{max-width:760px;margin:0 auto;padding:clamp(1.4rem,5vw,3.2rem) clamp(1.2rem,5vw,2rem) 4rem;}
  .eyebrow{font-family:var(--mono);font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;
    color:var(--accent-2);margin:0 0 1.3rem;}
  .eyebrow b{color:var(--accent);font-weight:600;}
  h1{font-family:var(--serif);font-weight:500;font-size:clamp(1.8rem,5vw,2.7rem);line-height:1.1;
    letter-spacing:-.01em;margin:0 0 1rem;}
  .status{font-family:var(--mono);font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;
    color:var(--muted);display:flex;flex-wrap:wrap;gap:.4rem .9rem;margin:0 0 1.8rem;}
  .status .open{color:var(--accent);font-weight:600;}
  .status .res{color:var(--accent-2);font-weight:600;}
  .call{background:var(--paper);border:1px solid var(--line);border-left:3px solid var(--accent);
    border-radius:3px;padding:1.1rem 1.25rem;}
  .call.outcome{border-left-color:var(--accent-2);}
  .call .k{font-family:var(--mono);font-size:.66rem;letter-spacing:.13em;text-transform:uppercase;
    color:var(--accent);font-weight:600;display:block;margin-bottom:.5rem;}
  .call.outcome .k{color:var(--accent-2);}
  .call p{margin:0;font-family:var(--serif);font-size:1.12rem;line-height:1.4;}
  .section-label{font-family:var(--mono);font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;
    color:var(--muted);display:flex;align-items:center;gap:.8rem;margin:2.4rem 0 .6rem;}
  .section-label::after{content:"";flex:1;height:1px;background:var(--line);}
  .explainer{font-size:.95rem;color:var(--muted);margin:0 0 1.1rem;}
  .chips{display:flex;flex-wrap:wrap;gap:.5rem;margin:0 0 1.6rem;}
  .chip{font-family:var(--mono);font-size:.68rem;letter-spacing:.06em;text-transform:uppercase;
    color:var(--accent-2);background:var(--tint);border:1px solid var(--line);border-radius:2px;
    padding:.3rem .6rem;}
  .signal{background:var(--paper);border:1px solid var(--line);border-radius:3px;
    padding:1rem 1.15rem;margin-bottom:.9rem;}
  .signal .meta{font-family:var(--mono);font-size:.65rem;letter-spacing:.08em;text-transform:uppercase;
    color:var(--muted);display:flex;flex-wrap:wrap;gap:.3rem .8rem;margin-bottom:.55rem;}
  .signal .meta .tag{color:var(--accent);font-weight:600;}
  .signal .meta .num{color:var(--accent-2);}
  .signal .q{margin:0;font-family:var(--serif);font-size:1.06rem;line-height:1.4;}
  .gauges{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin:.4rem 0 .8rem;}
  @media(max-width:520px){.gauges{grid-template-columns:1fr 1fr;}}
  .gauge{background:var(--paper);border:1px solid var(--line);border-radius:3px;padding:.8rem .9rem;}
  .gauge .lab{font-family:var(--mono);font-size:.62rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
  .gauge .val{font-family:var(--serif);font-size:1.6rem;color:var(--accent-2);line-height:1.1;margin-top:.15rem;}
  .gauge .bar{height:4px;background:var(--line);border-radius:2px;margin-top:.5rem;overflow:hidden;}
  .gauge .bar i{display:block;height:100%;background:var(--accent-2);}
  .market{font-family:var(--mono);font-size:.85rem;color:var(--muted);margin-top:.6rem;}
  .market b{color:var(--accent-2);}
  .seal{margin-top:2.6rem;padding:1rem 1.15rem;background:var(--tint);border:1px solid var(--line);
    border-radius:3px;font-family:var(--mono);font-size:.74rem;line-height:1.7;color:var(--accent-2);}
  .seal code{background:var(--paper);border:1px solid var(--line);border-radius:2px;padding:.05rem .3rem;color:var(--text);}
  footer{margin-top:1.6rem;padding-top:1.3rem;border-top:2px solid var(--accent-2);font-size:.88rem;color:var(--muted);}
  footer .mark{font-family:var(--serif);font-style:italic;color:var(--text);}
  @page{margin:14mm;size:letter;}
  @media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact;background:var(--ground);}
    .wrap{padding:.4rem .4rem 1rem;}.call,.signal,.gauge,.gauges,.seal,footer{break-inside:avoid;}}
</style>"""


def _fmt_date(v):
    if _na(v) is None:
        return "—"
    return str(v)[:10]


def _num(v, nd=2):
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return None


def _signal_card(sig):
    src = html.escape(str(sig.get("source") or "—"))
    emo = html.escape(str(sig.get("emotion_top_1") or "—"))
    emp = _num(sig.get("empathy_score"), 2)
    emp_html = f'<span class="num">Empathy {emp}</span>' if emp is not None else ""
    txt = html.escape(str(sig.get("text") or "").strip())
    if len(txt) > 400:
        txt = txt[:400] + "…"
    return (f'<div class="signal"><div class="meta"><span class="tag">{src}</span>'
            f'<span>Emotion: {emo}</span>{emp_html}</div>'
            f'<p class="q">{txt}</p></div>')


def _gauge(label, val):
    try:
        f = float(val)
    except (TypeError, ValueError):
        return ""
    w = max(0, min(100, int(round(f * 100))))
    return (f'<div class="gauge"><span class="lab">{html.escape(label)}</span>'
            f'<div class="val">{f:.2f}</div>'
            f'<div class="bar"><i style="width:{w}%"></i></div></div>')


def render_trace(engine, prediction_id):
    """Render a self-contained Evidence Trace HTML for one call. Returns the path.
    Built from the SEALED evidence text, so what's shown is exactly what's hashed."""
    ensure_predictions_table(engine)
    df = pd.read_sql(sql_text("SELECT * FROM predictions WHERE id = :id"),
                     engine, params={"id": int(prediction_id)})
    if df.empty:
        print(f"  No prediction with id {prediction_id}")
        return None
    r = df.iloc[0]

    # Prefer the sealed text (what the hash covers); fall back to the JSONB copy.
    ev = {}
    sealed_raw = _na(r.get("evidence_sealed"))
    if sealed_raw:
        try:
            ev = json.loads(sealed_raw)
        except Exception:
            ev = {}
    elif _na(r.get("evidence")) is not None:
        ev = r["evidence"] if isinstance(r["evidence"], dict) else json.loads(r["evidence"])

    statement = html.escape(str(r["statement"]))
    topic = html.escape(str(_na(r.get("topic")) or "—"))
    brand = _na(r.get("brand"))
    conf = _na(r.get("confidence"))
    conf_txt = f"{int(conf)} / 10" if conf is not None else "—"
    called = _fmt_date(r.get("prediction_date"))
    due = _fmt_date(r.get("due_date"))
    status = _na(r.get("outcome_status"))

    if status:
        state = f'<span class="res">● Resolved — {html.escape(str(status))}</span>'
        when = f'<span>Resolved&nbsp; {_fmt_date(r.get("resolved_date"))}</span>'
    else:
        state = '<span class="open">● Open</span>'
        when = f'<span>Resolves&nbsp; {due}</span>' if due != "—" else ""
    brand_line = f'<span>Brand&nbsp; {html.escape(str(brand))}</span>' if brand else ""

    # Signals
    if ev.get("manual_entry"):
        note = html.escape(str(ev.get("note") or ""))
        sig_html = (f'<div class="signal"><div class="meta"><span class="tag">Manual entry</span>'
                    f'</div><p class="q">{note or "—"}</p></div>')
    else:
        parts = [_signal_card(s) for s in (list(ev.get("top_news") or [])
                 + list(ev.get("top_social") or []))[:8]]
        sig_html = "".join(parts)
    if not sig_html:
        sig_html = '<p class="explainer">No inline signals captured for this call.</p>'

    # Chips
    counts = ev.get("counts") or {}
    chips = []
    if counts.get("news_scored") is not None:
        chips.append(f'<span class="chip">{int(counts["news_scored"])} news signals</span>')
    if counts.get("social_scored") is not None:
        chips.append(f'<span class="chip">{int(counts["social_scored"])} social signals</span>')
    if ev.get("vlds"):
        chips.append('<span class="chip">VLDS scores</span>')
    if ev.get("market"):
        chips.append('<span class="chip">Market snapshot</span>')
    chips_html = f'<div class="chips">{"".join(chips)}</div>' if chips else ""

    # Gauges (VLDS)
    vlds = ev.get("vlds") or {}
    gauges = ""
    for label in ("velocity", "longevity", "density", "scarcity"):
        v = vlds.get(label)
        if v is None:
            v = vlds.get(label + "_score")
        if v is not None:
            gauges += _gauge(label.capitalize(), v)
    gauges_html = (f'<p class="section-label">The climate reading</p>'
                   f'<div class="gauges">{gauges}</div>') if gauges else ""

    spy = _num((ev.get("market") or {}).get("spy_price"), 2)
    market_html = (f'<p class="market">Market context at capture — <b>SPY {spy}</b></p>'
                   if spy else "")
    captured = _fmt_date(ev.get("captured_at"))

    outcome_html = ""
    if status:
        osum = html.escape(str(_na(r.get("outcome_summary")) or "")) or "—"
        outcome_html = (f'<p class="section-label">The outcome</p>'
                        f'<div class="call outcome"><span class="k">Resolved — '
                        f'{html.escape(str(status))}</span><p>{osum}</p></div>')

    ev_hash = _na(r.get("evidence_sha256"))
    if ev_hash:
        seal_html = (f'<div class="seal">Evidence sealed {_fmt_date(r.get("sealed_at"))} · '
                     f'SHA-256 <code>{html.escape(ev_hash[:24])}…</code><br>'
                     f'Nothing added or altered since. Verify independently: '
                     f'<code>python prediction_tracker.py verify {int(r["id"])}</code></div>')
    else:
        seal_html = '<div class="seal">No integrity seal on this call (no evidence captured).</div>'

    snapshot_line = (f'The moment this call was staked, Moodlight froze a complete, '
                     f'self-contained snapshot of what it was seeing — captured {captured}. '
                     f'It survives the 30-day data wipe and is sealed against tampering.')

    body = (f'<div class="wrap">'
            f'<p class="eyebrow">Radar by Moodlight · <b>Evidence Trace</b></p>'
            f'<h1>{statement}</h1>'
            f'<div class="status"><span>Called&nbsp; {called}</span>'
            f'<span>Topic&nbsp; {topic}</span>{brand_line}'
            f'<span>Confidence&nbsp; {conf_txt}</span>{state}{when}</div>'
            f'<div class="call"><span class="k">The call</span><p>{statement}</p></div>'
            f'{outcome_html}'
            f'<p class="section-label">The frozen snapshot</p>'
            f'<p class="explainer">{snapshot_line}</p>{chips_html}'
            f'<p class="section-label">The signals that grounded it</p>{sig_html}'
            f'{gauges_html}{market_html}'
            f'{seal_html}'
            f'<footer>This snapshot was frozen the moment the call was made — nothing '
            f'added, nothing backdated. Call → sealed evidence → verified outcome is the '
            f'whole point.<br><br><span class="mark">Radar by Moodlight</span> · '
            f'the explainable instrument</footer></div>')

    doc = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
           f"<title>Evidence Trace — call #{int(r['id'])}</title>"
           + _TRACE_STYLE + "</head><body>" + body + "</body></html>")

    os.makedirs(TRACE_DIR, exist_ok=True)
    path = os.path.join(TRACE_DIR, f"trace_{int(r['id'])}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path


# ── CLI / worker ────────────────────────────────────────────────────────────

def _parse_date(s):
    """Parse a YYYY-MM-DD CLI date string into a date."""
    return datetime.strptime(s, "%Y-%m-%d").date()


def _cli_log(engine, args):
    p = argparse.ArgumentParser(prog="prediction_tracker.py log")
    p.add_argument("statement")
    p.add_argument("--brand")
    p.add_argument("--topic")
    p.add_argument("--horizon", type=int, help="time horizon in days")
    p.add_argument("--confidence", type=int, help="1-10")
    p.add_argument("--source", default="manual")
    p.add_argument("--date", help="override call date YYYY-MM-DD (historical calls)")
    p.add_argument("--no-capture", action="store_true",
                   help="skip live-DB evidence capture (use for historical calls)")
    p.add_argument("--evidence-note",
                   help="text evidence to store instead of a live-DB snapshot "
                        "(e.g. the dated source document for a historical call)")
    ns = p.parse_args(args)
    pdate = _parse_date(ns.date) if ns.date else None
    ev_override = None
    if ns.evidence_note:
        ev_override = {"note": ns.evidence_note, "manual_entry": True,
                       "source_document": ns.source}
    log_prediction(engine, ns.statement, brand=ns.brand, topic=ns.topic,
                   confidence=ns.confidence, horizon_days=ns.horizon, source=ns.source,
                   capture=not ns.no_capture, prediction_date=pdate,
                   evidence_override=ev_override)


def _cli_resolve(engine, args):
    p = argparse.ArgumentParser(prog="prediction_tracker.py resolve")
    p.add_argument("id", type=int)
    p.add_argument("status", help="played_out | missed | partial")
    p.add_argument("summary", nargs="?", default="")
    p.add_argument("--date", help="override resolution date YYYY-MM-DD")
    p.add_argument("--no-capture", action="store_true",
                   help="skip live-DB outcome capture (use for historical calls)")
    p.add_argument("--evidence-note",
                   help="text outcome evidence to store (e.g. verified external markers)")
    ns = p.parse_args(args)
    rdate = _parse_date(ns.date) if ns.date else None
    oev_override = ({"note": ns.evidence_note, "manual_entry": True}
                    if ns.evidence_note else None)
    resolve_prediction(engine, ns.id, ns.status, ns.summary,
                       capture_outcome=not ns.no_capture, resolved_date=rdate,
                       outcome_evidence_override=oev_override)


def _due_digest_html(due_df, record_txt):
    """Build the due-for-resolution reminder email (HTML)."""
    today = datetime.now(timezone.utc).date()
    rows = ""
    for _, r in due_df.iterrows():
        who = html.escape(str(r["brand"] or r["topic"] or "—"))
        stmt = html.escape(str(r["statement"]))
        due = r["due_date"]
        overdue = ""
        try:
            if due is not None and pd.Timestamp(due).date() < today:
                overdue = ' <span style="color:#9A4E12;font-weight:600;">(overdue)</span>'
        except Exception:
            pass
        rows += (
            f'<tr><td style="padding:14px 16px;border-bottom:1px solid #E4E6EA;vertical-align:top;">'
            f'<div style="font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#C57A11;'
            f'font-weight:600;letter-spacing:.04em;">#{int(r["id"])} · due {due}{overdue} · {who}</div>'
            f'<div style="font-family:Georgia,serif;font-size:16px;color:#171A22;line-height:1.4;'
            f'margin:6px 0 8px;">{stmt}</div>'
            f'<div style="font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#5A616E;">'
            f'Resolve: <code style="background:#F1F2F4;padding:1px 5px;border-radius:2px;">'
            f'prediction_tracker.py resolve {int(r["id"])} played_out|partial|missed "…"</code></div>'
            f'</td></tr>'
        )
    record_html = html.escape(record_txt).replace("\n", "<br>")
    return (
        '<div style="max-width:640px;margin:0 auto;background:#FCFCFD;">'
        '<div style="padding:22px 16px 6px;">'
        '<div style="font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.16em;'
        'text-transform:uppercase;color:#14484E;">Radar by Moodlight · Proof Library</div>'
        '<h1 style="font-family:Georgia,serif;font-weight:500;font-size:24px;color:#171A22;'
        'margin:8px 0 4px;">Calls due for resolution</h1>'
        '<p style="font-family:system-ui,sans-serif;font-size:14px;color:#5A616E;margin:0 0 8px;">'
        'These calls have reached their horizon. Grade each one so the track record stays live.</p>'
        '</div>'
        f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
        '<div style="padding:16px;font-family:ui-monospace,Menlo,monospace;font-size:12px;'
        f'color:#5A616E;border-top:2px solid #14484E;margin-top:8px;">{record_html}</div>'
        '</div>'
    )


def send_due_digest(engine, due_df):
    """Email the due-for-resolution list. Sends only when there are due calls.
    Recipient: PREDICTION_DIGEST_TO > EMAIL_RECIPIENT > daniel@moodlightintel.com."""
    if due_df is None or due_df.empty:
        return False
    sender = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    recipient = (os.getenv("PREDICTION_DIGEST_TO")
                 or os.getenv("EMAIL_RECIPIENT")
                 or "daniel@moodlightintel.com")
    if not all([sender, password, recipient]):
        print("  Email credentials not configured — skipping due-call email.")
        return False

    n = len(due_df)
    subject = f"Moodlight — {n} prediction call{'' if n == 1 else 's'} due for resolution"
    body = _due_digest_html(due_df, accuracy_report(engine))

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient.split(",")[0].strip()
    msg.attach(MIMEText(body, 'html'))
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            for addr in [a.strip() for a in recipient.split(",") if a.strip()]:
                msg.replace_header('To', addr)
                server.send_message(msg)
                print(f"  Due-call email sent to {addr}")
        return True
    except Exception as e:
        print(f"  Due-call email failed: {e}")
        return False


def _daily_pass(engine):
    """Default (cron) pass: surface due-for-resolution calls + print the record."""
    due = list_due(engine)
    if not due.empty:
        print(f"\n  {len(due)} call(s) due for resolution:")
        for _, r in due.iterrows():
            who = r["brand"] or r["topic"] or "—"
            print(f"    #{int(r['id'])} (due {r['due_date']}) [{who}] "
                  f"{str(r['statement'])[:80]}")
        send_due_digest(engine, due)
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
    elif cmd == "trace":
        if len(sys.argv) < 3:
            print("  usage: prediction_tracker.py trace <id>")
        else:
            path = render_trace(engine, int(sys.argv[2]))
            if path:
                print(f"  Trace written: {path}")
    elif cmd == "verify":
        if len(sys.argv) < 3:
            print("  usage: prediction_tracker.py verify <id>")
        else:
            verify_seal(engine, int(sys.argv[2]))
    elif cmd == "draft":
        if len(sys.argv) < 3:
            print("  usage: prediction_tracker.py draft <id>")
        else:
            draft_resolution(engine, int(sys.argv[2]))
    elif cmd == "seal-existing":
        seal_existing(engine)
    else:
        # None, "due", or the worker's job name ("prediction-log") -> daily pass
        _daily_pass(engine)

    print("\nDone.")


if __name__ == "__main__":
    main()
