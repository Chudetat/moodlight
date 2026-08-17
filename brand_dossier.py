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

# Process-local first hop: brand (lowercased) -> (fetched_at_epoch, text).
# Fast, but wiped by every deploy, which is exactly how we lost a good result -
# a lookup found Hornitos' live platform at 23:23, a deploy restarted the
# container at 23:39, and the 23:44 run re-rolled the dice and missed it.
_CACHE = {}
_TTL_SECONDS = 24 * 60 * 60

# Durable second hop. A brand's founding story and current platform do not
# change week to week, so there is no reason to re-fetch and re-gamble every
# time somebody asks. 30 days.
_DB_TTL_DAYS = 30

# Web search is genuinely variable: the same prompt finds a brand's live
# platform on one run and misses it on the next. Rather than fight that with
# ever-more-forceful prompt language, we keep the better answer - a stored
# dossier that HAS a platform section beats a fresh one that does not.
_NO_PLATFORM_MARKER = "NO CURRENT PLATFORM FOUND"

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

   SEARCH FOR THIS EXPLICITLY. Do not answer it from the brand's About page or
   its heritage story - those describe what the brand IS, not what it is
   currently SAYING, and a brand's live campaign is almost never on the page
   that describes its founding. Run dedicated searches along the lines of:
   "<brand> new campaign", "<brand> brand platform", "<brand> launches",
   "<brand> advertising agency", "<brand> press release" - and repeat them
   against the last two calendar years by name. Trade press (Ad Age, Adweek,
   Campaign, Marketing Dive, Shots) and the parent company's newsroom carry this
   when the brand's own site does not. A campaign launched 12-24 months ago is
   very likely still the live platform; recency of the article is not evidence
   that a platform has ended.

   Getting this section wrong is the single most expensive failure in this brief.
   Only write "NO CURRENT PLATFORM FOUND" after those searches have actually been
   run and come back empty.

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


def _has_platform(body):
    """Did the lookup actually establish what the brand is currently running?

    This is the section that matters and the section that fails. Everything
    else - founding, distillery, ownership - comes back reliably.
    """
    return bool(body) and _NO_PLATFORM_MARKER not in body.upper()


def _ensure_table(engine):
    from sqlalchemy import text as sql_text
    with engine.connect() as conn:
        conn.execute(sql_text("""
            CREATE TABLE IF NOT EXISTS brand_dossiers (
                brand VARCHAR(200) PRIMARY KEY,
                dossier TEXT NOT NULL,
                has_platform BOOLEAN DEFAULT FALSE,
                fetched_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()


def _db_get(key):
    """Return (dossier_text, has_platform) from storage, or (None, False)."""
    try:
        from db_helper import get_engine
        from sqlalchemy import text as sql_text
        engine = get_engine()
        if not engine:
            return None, False
        _ensure_table(engine)
        with engine.connect() as conn:
            row = conn.execute(sql_text(
                "SELECT dossier, has_platform FROM brand_dossiers "
                "WHERE brand = :b AND fetched_at > NOW() - INTERVAL '%d days'"
                % _DB_TTL_DAYS), {"b": key}).fetchone()
        return (row[0], bool(row[1])) if row else (None, False)
    except Exception as e:
        print(f"  [brand_dossier] store read failed: {type(e).__name__}: {e}")
        return None, False


def _db_put(key, dossier, has_platform):
    """Persist, but never downgrade: a stored dossier that established the
    current platform is not replaced by a fresh one that failed to."""
    try:
        from db_helper import get_engine
        from sqlalchemy import text as sql_text
        engine = get_engine()
        if not engine:
            return
        _ensure_table(engine)
        with engine.connect() as conn:
            conn.execute(sql_text("""
                INSERT INTO brand_dossiers (brand, dossier, has_platform, fetched_at)
                VALUES (:b, :d, :p, NOW())
                ON CONFLICT (brand) DO UPDATE SET
                    dossier      = CASE WHEN brand_dossiers.has_platform AND NOT :p
                                        THEN brand_dossiers.dossier ELSE EXCLUDED.dossier END,
                    has_platform = brand_dossiers.has_platform OR EXCLUDED.has_platform,
                    fetched_at   = NOW()
            """), {"b": key, "d": dossier, "p": has_platform})
            conn.commit()
    except Exception as e:
        print(f"  [brand_dossier] store write failed: {type(e).__name__}: {e}")


def _run_lookup(client, brand, hint):
    """One web-search pass. Returns the raw body text, or "" if unusable."""
    from datetime import datetime, timezone
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
        return ""
    return body


def fetch_brand_dossier(brand, category_hint=""):
    """Return a background block for `brand`, or None if nothing usable.

    Three hops, cheapest first: process cache, durable store, then the web.
    The store is what makes this reliable - web search finds a brand's live
    platform on some runs and not others, so we keep the answer rather than
    re-rolling the dice on every request.

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

    stored, stored_has_platform = _db_get(key)
    if stored and stored_has_platform:
        # Complete answer already on file. Nothing to gain from re-fetching.
        print(f"  [brand_dossier] store hit for {brand!r} (with platform)")
        _CACHE[key] = (time.time(), stored)
        return stored

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [brand_dossier] ANTHROPIC_API_KEY not set - skipping lookup")
        return stored or None

    try:
        from anthropic import Anthropic
        from datetime import datetime, timezone

        client = Anthropic(api_key=api_key, timeout=_TIMEOUT_SECONDS)
        hint = f"\nCATEGORY CONTEXT: {category_hint.strip()}" if category_hint else ""

        print(f"  [brand_dossier] looking up {brand!r} on the open web...")
        body = _run_lookup(client, brand, hint)

        # The platform section is the one that fails, and it fails as a dice
        # roll rather than a dead end. One retry converts most misses.
        if body and not _has_platform(body):
            print(f"  [brand_dossier] no platform found for {brand!r} - retrying once")
            retry = _run_lookup(client, brand, hint)
            if _has_platform(retry):
                body = retry

        if not body:
            print(f"  [brand_dossier] nothing usable found for {brand!r}")
            _CACHE[key] = (time.time(), stored)
            return stored or None

        dossier = _HEADER.format(
            brand=brand.upper(),
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            body=body,
        )
        has_platform = _has_platform(body)

        # Never downgrade: if we already had a dossier WITH a platform and this
        # one lacks it, keep the better one.
        if stored and stored_has_platform and not has_platform:
            print(f"  [brand_dossier] fresh lookup lost the platform - keeping stored")
            dossier = stored

        _db_put(key, dossier, has_platform or stored_has_platform)
        _CACHE[key] = (time.time(), dossier)
        print(f"  [brand_dossier] retrieved {len(body)} chars for {brand!r} "
              f"(platform: {'yes' if has_platform else 'NO'})")
        return dossier

    except Exception as e:
        # Never let a lookup failure take down an agent run.
        print(f"  [brand_dossier] lookup failed for {brand!r}: "
              f"{type(e).__name__}: {e}")
        return stored or None
