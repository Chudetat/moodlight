"""
ask_sharpen.py — thin-query sharpener for Ask Moodlight.

When a user submits a thin/vague query, offer 3 sharper premises to pick from
instead of answering it badly. The tool is elite at building out a real premise
and weak at inventing one from a one-liner — so this fixes the INPUT.

Shared by the widget (ask_moodlight_api.py) and the dashboard (ask_engine.py).

Model: Sonnet — the sharpened premise steers every downstream answer, so premise
quality is the leverage point. A/B'd sharper than Haiku on the creative/cultural
queries that are the worst thin-query cases (e.g. Modelo). ~4s, and the heuristic
gate keeps it off the majority of queries.

Fails safe: any error, or the gate says skip, returns {"thin": False, "options": []}
so the caller just answers the original query.
"""
import os
import re
import json
from anthropic import Anthropic

SHARPEN_MODEL = "claude-sonnet-4-6"

# A query already carrying a real angle/audience/tension — don't tax it.
_RICH_SIGNALS = re.compile(
    r"\b(because|versus|vs\.?|without|even though|given that|specifically|targeting|among)\b"
    r"|gen ?z|millennial|aged \d",
    re.IGNORECASE,
)


def is_plausibly_thin(question: str, has_history: bool = False) -> bool:
    """Fast, no-model gate. Skip clearly-rich briefs and follow-ups; send
    everything else to the model, which makes the real thin/rich call.
    Deliberately permissive — missing a thin query (answering it badly) is a
    worse failure than taxing a borderline-rich one with a triage call."""
    if not question or has_history:
        return False
    words = question.strip().split()
    if len(words) >= 30:
        return False  # a long, detailed brief — clearly rich
    if _RICH_SIGNALS.search(question) and len(words) >= 15:
        return False  # medium-length AND already has an explicit angle
    return True


_TRIAGE_PROMPT = """You are a sharp creative strategist inside a cultural-intelligence tool. A user typed this query:

"{q}"

Decide if it is THIN (vague/generic, no real premise — e.g. "ideas for X", a bare brand name, "trends in Y") or RICH (already carries an angle, audience, or tension worth answering directly).

If RICH: return {{"thin": false, "options": []}}.
If THIN: return {{"thin": true, "options": ["...", "...", "..."]}} — exactly 3 sharpened versions the user can pick from. Each MUST add real substance the query lacks: a specific audience, a live cultural tension, a territory, or a point of view. Each must be a genuinely different angle, phrased the way the user would ask it. Keep each to one sentence. No fluff, no padding.

Return ONLY valid JSON, nothing else."""


def _extract_text(resp) -> str:
    """Join text blocks (robust to thinking-block models)."""
    return "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    ).strip()


def triage_and_sharpen(question: str, has_history: bool = False) -> dict:
    """Return {"thin": bool, "options": [str, ...]}.

    Never raises. Returns thin=False (caller answers the original) when the gate
    skips, the model says rich, JSON is unparseable, or anything errors."""
    try:
        if not is_plausibly_thin(question, has_history):
            return {"thin": False, "options": []}
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        raw = _extract_text(
            client.messages.create(
                model=SHARPEN_MODEL,
                max_tokens=600,
                messages=[{"role": "user", "content": _TRIAGE_PROMPT.format(q=question)}],
            )
        )
        m = re.search(r"\{.*\}", raw, re.S)  # tolerate code fences / stray text
        if not m:
            return {"thin": False, "options": []}
        data = json.loads(m.group(0))
        if not data.get("thin"):
            return {"thin": False, "options": []}
        opts = [o.strip() for o in data.get("options", []) if isinstance(o, str) and o.strip()][:3]
        if len(opts) < 2:  # not enough usable options — just answer
            return {"thin": False, "options": []}
        return {"thin": True, "options": opts}
    except Exception:
        return {"thin": False, "options": []}
