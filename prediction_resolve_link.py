"""
prediction_resolve_link.py — signed one-click resolution links for due calls.

The tracker's daily email told Daniel to run a shell command. He will not, and a
ledger that stops being resolved is worse than no ledger: it shows calls going
stale in public, which reads as abandonment rather than as accountability.

So the email carries buttons. Clicking one opens a confirmation page with the
call and its drafted verdict; confirming there records the outcome.

WHY IT IS TWO CLICKS AND NOT ONE
--------------------------------
The link is a GET, and mail clients and security scanners follow GETs on their
own. A one-click link that writes would let a scanner grade a prediction. So the
link only OPENS a page and the page POSTs. Two clicks, no typing, and nothing a
prefetcher can trigger.

WHAT THIS DOES NOT DO
---------------------
It does not decide anything. The page proposes the drafted verdict and the
person picks. resolve_prediction remains the only path that records an outcome.
An engine that grades its own calls has an opinion of itself, not a track
record.
"""

import os
import hmac
import hashlib

# Links must survive the horizon: a call logged today may not be graded for 120
# days, so the token is derived only from the prediction id and cannot expire on
# its own. Rotating PREDICTION_LINK_SECRET invalidates every outstanding link.
_SECRET_ENV = "PREDICTION_LINK_SECRET"
_FALLBACK_ENV = "TEAM_TOKEN_SECRET"


def _secret() -> bytes:
    s = os.getenv(_SECRET_ENV) or os.getenv(_FALLBACK_ENV)
    if not s:
        raise RuntimeError(
            f"{_SECRET_ENV} (or {_FALLBACK_ENV}) must be set to sign resolution links"
        )
    return s.encode()


def token_for(prediction_id) -> str:
    """Deterministic token for one prediction. Constant across statuses on
    purpose: the token proves who is grading, the page decides what to."""
    return hmac.new(_secret(), str(int(prediction_id)).encode(),
                    hashlib.sha256).hexdigest()[:32]


def verify(prediction_id, provided: str) -> bool:
    if not provided:
        return False
    try:
        return hmac.compare_digest(token_for(prediction_id), provided)
    except Exception:
        return False


def resolve_url(prediction_id, base=None) -> str:
    base = (base or os.getenv("MOODLIGHT_API_URL")
            or "https://moodlight-api-production.up.railway.app").rstrip("/")
    return f"{base}/api/predictions/{int(prediction_id)}/resolve?t={token_for(prediction_id)}"


def buttons_html(prediction_id, base=None) -> str:
    """The row of buttons for the daily email. Falls back to nothing if the
    signing secret is missing, so a misconfigured env degrades the email rather
    than breaking the send."""
    try:
        url = resolve_url(prediction_id, base)
    except Exception:
        return ""
    def btn(label, status, bg, fg="#ffffff"):
        return (
            f'<a href="{url}&status={status}" '
            f'style="display:inline-block;padding:9px 16px;margin:0 6px 0 0;'
            f'background:{bg};color:{fg};text-decoration:none;border-radius:3px;'
            f'font-family:system-ui,sans-serif;font-size:13px;font-weight:600;">{label}</a>'
        )
    return (
        '<div style="margin-top:10px;">'
        + btn("Played out", "played_out", "#15803D")
        + btn("Partial", "partial", "#B45309")
        + btn("Missed", "missed", "#B91C1C")
        + '</div>'
    )
