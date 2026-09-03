"""
brand_topic_memory.py — what the engine has seen about a subject before.

The substrate retains roughly 30 days. Everything older is deleted by
retention, which means every read is structurally amnesiac: ask about a brand
today and the answer can only describe the last month, with no idea whether
what it is looking at is a spike, a recovery, or the flat middle of a long
decline. The engine has been re-meeting every subject as a stranger.

This stores the engine's OWN read of a subject each time one is computed, so a
later run can say what changed since last time.

WHAT GOES IN HERE, AND WHAT NEVER DOES
--------------------------------------
Only the enrichment block: the VLDS read, the no-signal notice, the web
dossier. All of it is derived from the shared substrate plus a brand name.
`_build_marketplace_enrichment` uses the user's brief solely to extract that
name and never echoes the brief back, which is what makes this poolable across
everyone without leaking one person's thinking to the next.

A user's own words never belong in this table. The moment a brief, a campaign,
a positioning statement or an agent output lands here, one client's private
material starts being served to the next person who asks about their brand.
That is the difference between shared substrate and a confidentiality breach,
and there is no version of it that is merely a bug. Person-scoped memory is a
separate store with its own access control.

Fails soft in every direction. Memory is additive; nothing here is allowed to
take down a run that would otherwise have worked.
"""

import re

# How far back a recall reaches. Long enough to cross several substrate
# windows, short enough that a read is still about the present.
_LOOKBACK_DAYS = 180

# How many prior observations to hand the agent. Three gives a shape (then,
# later, most recently) without spending the prompt on history.
_MAX_RECALL = 3

# A subject seen only once has no story to tell, and rendering "we saw this
# once" costs tokens to say nothing.
_MIN_RECALL = 1

# Enrichment blocks run long. Stored whole, but truncated on the way into a
# prompt: the point of a recall is the delta, not a second full read.
_MAX_RENDER_CHARS = 1200


def _norm(subject: str) -> str:
    """Normalise a subject to a stable key.

    Brand phrases arrive with inconsistent case and spacing, and "Modelo" on
    Monday must hit the same row as "modelo  especial" on Friday. Homonym
    safety is not this module's job - resolve_brand_match already requires a
    category term for Corona, Dove, Shell and friends before any of this is
    reached.
    """
    return re.sub(r"\s+", " ", (subject or "").strip().lower())[:200]


def _ensure_table(engine):
    from sqlalchemy import text as sql_text
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS brand_topic_memory (
                subject      VARCHAR(200) NOT NULL,
                observed_on  DATE NOT NULL,
                enrichment   TEXT NOT NULL,
                sample_size  INTEGER,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (subject, observed_on)
            )
        """))
        conn.commit()


def remember(subject: str, enrichment: str, sample_size: int = None):
    """Store today's read of a subject. One row per subject per day.

    Re-running the same brand twice in an afternoon should not write twice;
    the day is the unit, and the later read wins because it is the one built
    on more data.
    """
    key = _norm(subject)
    if not key or not enrichment or not enrichment.strip():
        return
    try:
        from db_helper import get_engine
        from sqlalchemy import text as sql_text
        engine = get_engine()
        if not engine:
            return
        _ensure_table(engine)
        with engine.connect() as conn:
            conn.execute(sql_text("""
                INSERT INTO brand_topic_memory (subject, observed_on, enrichment, sample_size)
                VALUES (:s, CURRENT_DATE, :e, :n)
                ON CONFLICT (subject, observed_on) DO UPDATE SET
                    enrichment  = EXCLUDED.enrichment,
                    sample_size = EXCLUDED.sample_size,
                    created_at  = NOW()
            """), {"s": key, "e": enrichment, "n": int(sample_size) if sample_size else None})
            conn.commit()
    except Exception as e:
        print(f"  [brand_topic_memory] write failed for {key!r}: {type(e).__name__}: {e}")


def recall(subject: str):
    """Prior observations of a subject, oldest first. Today's is excluded.

    Today's read is already in the prompt as the live enrichment; repeating it
    under a memory heading would just tell the agent the same thing twice.
    """
    key = _norm(subject)
    if not key:
        return []
    try:
        from db_helper import get_engine
        from sqlalchemy import text as sql_text
        engine = get_engine()
        if not engine:
            return []
        _ensure_table(engine)
        with engine.connect() as conn:
            rows = conn.execute(sql_text(f"""
                SELECT observed_on, enrichment, sample_size
                FROM brand_topic_memory
                WHERE subject = :s
                  AND observed_on < CURRENT_DATE
                  AND observed_on > CURRENT_DATE - INTERVAL '{_LOOKBACK_DAYS} days'
                ORDER BY observed_on DESC
                LIMIT {_MAX_RECALL}
            """), {"s": key}).fetchall()
        return list(reversed(rows))
    except Exception as e:
        print(f"  [brand_topic_memory] read failed for {key!r}: {type(e).__name__}: {e}")
        return []


def render(subject: str) -> str:
    """A prompt block describing what the engine saw about this subject before.

    Deliberately NOT phrased like the upstream-agent preamble, which tells the
    agent the reader has just read the material and to skip the groundwork.
    Nobody has read this. It is background the engine is carrying forward, and
    the live read below it remains the source of truth.
    """
    rows = recall(subject)
    if len(rows) < _MIN_RECALL:
        return ""

    parts = [
        f"# WHAT THIS ENGINE HAS SEEN ABOUT {subject.upper()} BEFORE",
        "",
        "These are this engine's own earlier reads of this subject, from windows that have "
        "since rolled out of the live data. The reader has NOT seen them. They are here so "
        "you can tell whether today's read is a change or a continuation - use them for "
        "direction and duration, never as a substitute for the live read below.",
        "",
        "Rules: the current enrichment further down is the source of truth. Do not present a "
        "past observation as though it were happening now. If the earlier reads and today's "
        "read disagree, that disagreement IS the insight - say what moved. Never mention this "
        "history, the engine, or the fact that anything was remembered.",
        "",
    ]
    for observed_on, enrichment, sample_size in rows:
        body = (enrichment or "").strip()
        if len(body) > _MAX_RENDER_CHARS:
            body = body[:_MAX_RENDER_CHARS] + "\n[... truncated ...]"
        seen = f" ({sample_size} documents)" if sample_size else ""
        parts.append(f"## Observed {observed_on}{seen}")
        parts.append(body)
        parts.append("")
    parts.append("---")
    parts.append("")
    return "\n".join(parts)
