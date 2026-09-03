"""
person_memory.py — what THIS person told us before.

The other half of memory. brand_topic_memory pools what the engine observed
about a subject and is safe to share with anyone, because nothing in it came
from a user. This module is the opposite: it recalls what one person typed -
their brief, their positioning, the work they got back - and none of it may
ever reach anyone else.

WHY THIS IS GATED AND THE OTHER ONE IS NOT
------------------------------------------
The marketplace has no login by design: type an email, get a brief. That is
the right trade for a front door, and the wrong trade for memory. If recall
keyed on an email address alone, anyone who guessed a colleague's address
would be handed that colleague's client thinking. Derric is running this on a
product his wife is launching and on a company where he is president; that is
exactly the material that must not come back for a stranger who types his
address.

So recall requires the signed team token already issued by Team Builder - an
HMAC of the email under a server secret, delivered in a link to that person's
inbox. Possession of it means possession of the mailbox. Without it this
module returns nothing at all, and the run proceeds exactly as it does today.

There is no new store here. Every run's input and output is already written to
marketplace_runs. This is the read nobody ever wrote.
"""

import re

# How far back to look. Long enough to span a real engagement, short enough
# that a brief from another era does not haunt a new one.
_LOOKBACK_DAYS = 120

# Two prior runs. Enough to establish continuity, not so much that the
# person's history crowds out the brief they just wrote.
_MAX_RECALL = 2

# Prior outputs run to 12,000+ characters. What matters on recall is the shape
# of what they were told, not the whole document.
_MAX_OUTPUT_CHARS = 1500
_MAX_INPUT_CHARS = 600

# Words too generic to prove two briefs are about the same thing.
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "about",
    "product", "service", "brand", "audience", "target", "challenge", "key",
    "market", "markets", "timeline", "budget", "company", "business", "new",
}


def _subject_terms(text: str) -> set:
    """Distinctive words from a brief, used to decide if two runs are related."""
    words = re.findall(r"[a-z0-9]{4,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def _is_related(current: str, prior: str) -> bool:
    """Whether a prior run is about the same thing as this one.

    Without this, a Diane brief from three weeks ago gets injected into an
    unrelated run for a different company and makes the answer worse, not
    better. Memory that fires on everything is noise wearing memory's clothes.

    Deliberately strict: two distinctive words in common, not one. One shared
    word is a coincidence.
    """
    a, b = _subject_terms(current), _subject_terms(prior)
    if not a or not b:
        return False
    return len(a & b) >= 2


def recall(email: str, current_input: str):
    """Prior related runs for this person, oldest first.

    The caller is responsible for having verified the token BEFORE calling
    this. This function does not check it, because a memory module quietly
    deciding its own access rules is how a gate gets bypassed later by a
    caller that forgot one existed.
    """
    addr = (email or "").strip().lower()
    if not addr or not current_input:
        return []
    try:
        from db_helper import get_engine
        from sqlalchemy import text as sql_text
        engine = get_engine()
        if not engine:
            return []
        with engine.connect() as conn:
            rows = conn.execute(sql_text(f"""
                SELECT created_at, agent, user_input, output
                FROM marketplace_runs
                WHERE email = :e
                  AND output IS NOT NULL
                  AND created_at > NOW() - INTERVAL '{_LOOKBACK_DAYS} days'
                ORDER BY created_at DESC
                LIMIT 25
            """), {"e": addr}).fetchall()
    except Exception as e:
        print(f"  [person_memory] read failed for {addr!r}: {type(e).__name__}: {e}")
        return []

    related = [r for r in rows if _is_related(current_input, r[2] or "")]
    return list(reversed(related[:_MAX_RECALL]))


def render(email: str, current_input: str, agent_labels: dict = None) -> str:
    """A prompt block describing this person's own prior work.

    Framed as continuity with a returning client, which is what it is. Unlike
    the upstream-agent rail, the reader may well have forgotten the detail -
    it could be weeks old - so the agent is told to build on it, not to assume
    it was just read.
    """
    rows = recall(email, current_input)
    if not rows:
        return ""

    parts = [
        "# WHAT THIS PERSON HAS ALREADY WORKED ON WITH YOU",
        "",
        "This is the same person, returning, on what looks like the same piece of business. "
        "Below is what they briefed before and what they were given back. It may be weeks "
        "old, so do not assume they remember the detail - but do not start from zero either.",
        "",
        "Rules: the brief in the main prompt is the current instruction and overrides anything "
        "here. Do not repeat a recommendation they were already given - advance it, or say why "
        "it should change. If the new brief contradicts the old one, follow the new one. Never "
        "mention this history, that you remember them, or that any of this was stored.",
        "",
    ]
    for created_at, agent, user_input, output in rows:
        label = (agent_labels or {}).get(agent, agent)
        brief = (user_input or "").strip()[:_MAX_INPUT_CHARS]
        prior = (output or "").strip()
        if len(prior) > _MAX_OUTPUT_CHARS:
            prior = prior[:_MAX_OUTPUT_CHARS] + "\n[... truncated ...]"
        parts.append(f"## {created_at:%Y-%m-%d} — they briefed {label}")
        parts.append("What they asked for:")
        parts.append(brief)
        parts.append("")
        parts.append("What they were given:")
        parts.append(prior)
        parts.append("")
    parts.append("---")
    parts.append("")
    return "\n".join(parts)
