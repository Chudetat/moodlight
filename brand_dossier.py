"""
brand_dossier.py — on-demand brand background for brands the substrate can't see.

The standing corpus is news-shaped: it covers companies with constant press
(Constellation Brands) and misses product brands almost entirely (Hornitos got
zero mentions in 74,000 news documents). When enrichment finds no measurable
signal, the agent used to work from the brief alone — which is honest, but it
also meant it could not know a brand's CURRENT platform. That is how a strategy
gets written for an insider heritage brand whose live positioning is the exact
opposite.

This module fills that gap with one web-search call. It does NOT produce scored
metrics — RoBERTa scoring lives in worker_heavy and can't run inside an API
request. What it produces is background: what the brand is, what it is currently
running, and when. Correct, not deep.

Fails soft in every direction: no key, no network, refusal, empty result — all
return None so the caller falls back to the honest no-signal path.
"""

import os
import time

# brand (lowercased) -> (fetched_at_epoch, dossier_text). Process-local, which
# is enough: the API process is long-lived and a single brief usually runs 3+
# agents against the same brand within a minute.
_CACHE = {}
_TTL_SECONDS = 24 * 60 * 60

_MODEL = "claude-sonnet-5"
# Kept deliberately short. This is background, not an essay, and every token
# is latency inside a request the caller is already waiting on.
_MAX_TOKENS = 900
# Was briefly cut to 60s when the marketplace endpoint still held an HTTP
# connection open for the whole run: a slow agent plus a slow lookup crossed
# Railway's 300s gateway limit and returned 502, destroying the output, the
# email and the log row together.
#
# That constraint is gone. Marketplace runs are async now (job id + polling),
# so nothing is tied to a connection and a slow lookup is just slow. At 60s the
# lookup was giving up before web search finished, and brand facts came back
# tagged [RECALL] instead of [SUBSTRATE] - the feature silently doing nothing.
#
# 150s is sized to the work: several searches, page fetches, dynamic filtering.
_TIMEOUT_SECONDS = 150.0

_SYSTEM = (
    "You are a research assistant compiling factual background on a brand for a "
    "strategist. Use web search. Report only what you can find and attribute. "
    "Never speculate, never fill gaps with plausible-sounding detail, and never "
    "infer a brand's current campaign from its history. If you cannot establish "
    "something, say so explicitly — an absence you report is useful, an invention "
    "is not."
)

_PROMPT = """Research the brand below and return a factual background brief.

BRAND: {brand}{hint}

Search the web and report, in this order:

1. WHAT IT IS — category, owner/parent company, where it is made, founding date
   and any founding story that is documented on the brand's own site or in press.

2. CURRENT PLATFORM — the brand's live positioning, campaign, tagline or brand
   platform RIGHT NOW, with the date it launched and the agency if named. This is
   the most important section. A strategist who does not know this will propose
   work that contradicts what the brand is already running.

3. RECENT ACTIVITY — notable launches, partnerships, events or announcements in
   roughly the last 18 months, each with a date.

4. WHAT YOU COULD NOT ESTABLISH — anything a strategist would want that you could
   not verify.

Rules:
- Every claim needs a date or a source you actually saw. No date, no claim.
- If the brand has no findable current platform, write "NO CURRENT PLATFORM FOUND"
  rather than describing an old one as if it were live.
- If you can find nothing reliable about this brand at all, reply with exactly:
  NO RELIABLE INFORMATION FOUND
- Be compact. Facts, not prose. No recommendations, no strategy, no opinions."""

_HEADER = """BRAND BACKGROUND — {brand} (retrieved from the open web, {date})
---
This brand has no measurable presence in the current window, so what follows was
looked up rather than measured. Treat it as verified background, NOT as a
cultural read: it tells you what the brand IS and what it is CURRENTLY RUNNING.
It says nothing about momentum, sentiment or audience.

HOW TO USE IT — non-negotiable:
 - DO ground the work in these facts, especially the current platform. Proposing
   something that contradicts what the brand is already running is the specific
   failure this exists to prevent.
 - Do NOT describe this as a live conversation, emotional read or velocity. It
   is background, not signal.
 - Do NOT present anything here as a real-time finding, and never disclose to the
   reader where it came from. Discipline the work silently.
---
{body}
---"""


def _cache_get(key):
    hit = _CACHE.get(key)
    if not hit:
        return None
    fetched_at, text = hit
    if time.time() - fetched_at > _TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return text


def fetch_brand_dossier(brand, category_hint=""):
    """Return a background block for `brand`, or None if nothing usable.

    category_hint disambiguates common-word brands ("Corona" the beer, not the
    city). Pass whatever category context the brief supplies.
    """
    if not brand or len(brand.strip()) < 2:
        return None

    key = brand.strip().lower()
    cached = _cache_get(key)
    if cached is not None:
        print(f"  [brand_dossier] cache hit for {brand!r}")
        return cached

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [brand_dossier] ANTHROPIC_API_KEY not set — skipping lookup")
        return None

    try:
        from anthropic import Anthropic
        from datetime import datetime, timezone

        client = Anthropic(api_key=api_key, timeout=_TIMEOUT_SECONDS)
        hint = f"\nCATEGORY CONTEXT: {category_hint.strip()}" if category_hint else ""

        print(f"  [brand_dossier] looking up {brand!r} on the open web...")
        started = time.time()
        with client.messages.stream(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209", "name": "web_fetch"},
            ],
            messages=[{"role": "user",
                       "content": _PROMPT.format(brand=brand, hint=hint)}],
        ) as stream:
            resp = stream.get_final_message()
        print(f"  [brand_dossier] lookup took {time.time() - started:.0f}s")

        body = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        ).strip()

        if not body or "NO RELIABLE INFORMATION FOUND" in body.upper():
            print(f"  [brand_dossier] nothing usable found for {brand!r}")
            _CACHE[key] = (time.time(), None)
            return None

        dossier = _HEADER.format(
            brand=brand.upper(),
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            body=body,
        )
        _CACHE[key] = (time.time(), dossier)
        print(f"  [brand_dossier] retrieved {len(body)} chars for {brand!r}")
        return dossier

    except Exception as e:
        # Never let a lookup failure take down an agent run.
        print(f"  [brand_dossier] lookup failed for {brand!r}: "
              f"{type(e).__name__}: {e}")
        return None
