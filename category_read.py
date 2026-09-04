"""
category_read.py — measured category signal for brands the substrate cannot see.

The corpus is strong on broad cultural conversation and weak on individual brand
names. Ask a question about Old Mutual or JASPAL and the brand block comes back
empty, because neither appears in 90,000 daily English-language consumer
articles. The fourth-wall rule then correctly pivots the answer to web search
without telling the reader anything is missing.

The answers that come out of that path are good. They are also indistinguishable
from what anyone could produce with a search engine and a well-written prompt,
because the one asset that is not reproducible - the measured corpus - never
appears in them. A real example: an Old Mutual answer built its strongest move on
a trust-in-institutions argument sourced from a single news story, while the
thing that can actually measure institutional trust across thousands of documents
sat unused.

The existing no-signal notice already instructs the model to "rely on web search
results and the CATEGORY/cultural signal relevant to the brand's space". It has
simply never been given any category signal to rely on. This supplies it.

WHY CATEGORY AND NOT BETTER BRAND COVERAGE
------------------------------------------
Widening brand coverage means chasing every product brand into trade press and
retail media, which is expensive and, on the evidence of the QSR and CPG
substrate work, thin. Category is where this corpus is genuinely strong. Old
Mutual has no signal; the conversation about economics and institutions has
thousands of documents a month. Use the instrument where it reads well instead
of apologising for where it does not.

THE ONE THING THAT MUST NOT HAPPEN
----------------------------------
A category number must never be presented as the brand's number. "Sentiment
around Old Mutual is cold" is false and checkable; "the conversation this brand
sits inside is running cold" is true and useful. The rendered block says so
explicitly and repeatedly, because this is the exact substitution the existing
no-signal notice was written to prevent.
"""

# The tracked taxonomy, verbatim. VLDS and topic metrics exist ONLY for these
# exact strings, so a near-miss ("fintech", "insurance") silently returns
# nothing. 'other' is excluded: it is the catch-all and the largest bucket, so
# a read built on it describes everything and therefore nothing.
TRACKED_TOPICS = [
    "technology & ai", "sports", "business & corporate", "war & foreign policy",
    "entertainment", "politics", "education", "government",
    "healthcare & wellbeing", "economics", "crime & safety",
    "branding & advertising", "climate & environment", "culture & identity",
    "gender & sexuality", "labor & work", "creative & design", "immigration",
    "housing", "qsr", "media & journalism", "religion & values",
    "race & ethnicity",
]

_LOOKBACK_DAYS = 30

# Below this the category read is noise dressed as measurement, and shipping a
# number nobody should act on is worse than shipping none.
_MIN_DOCS = 200

_MODEL = "claude-haiku-4-5-20251001"


def resolve_category(question: str, brand: str = "", topic: str = "", client=None):
    """Map a question to the one tracked topic whose conversation contains it.

    A model rather than a keyword table: "Old Mutual" has to reach "economics"
    and JASPAL has to reach "branding & advertising", and no keyword list gets
    there. Routing prose has beaten matcher code everywhere else in this
    codebase.

    Returns a tracked topic string, or None when nothing fits - which is a real
    answer, not a failure. A question about Thai fashion retail genuinely may
    not belong to any of these.
    """
    if client is None:
        return None
    subject = " ".join(x for x in (brand, topic, question) if x)[:600]
    if not subject.strip():
        return None
    options = "\n".join(f"- {t}" for t in TRACKED_TOPICS)
    try:
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=20,
            system=(
                "You map a business question to the ONE broad news category whose "
                "conversation it belongs inside. Reply with the category string exactly as "
                "written, or NONE.\n\n"
                "Judge by the conversation the subject sits inside, not by the industry "
                "label. A retail bank or insurer belongs in 'economics'. A fashion retailer "
                "belongs in 'branding & advertising'. A staffing or employment question "
                "belongs in 'labor & work'. Answer NONE only when nothing genuinely fits - "
                "a wrong category is worse than none, because it will be measured and "
                "quoted.\n\nCategories:\n" + options
            ),
            messages=[{"role": "user", "content": subject}],
        )
        raw = "".join(getattr(b, "text", "") for b in resp.content)
        # Exact match alone is too brittle: a trailing full stop, a wrapping
        # quote or a capitalised reply all fail it, and the function then
        # returns None with nothing logged - the feature silently does nothing
        # and looks like the model ignoring the block. Normalise, then fall back
        # to containment.
        out = raw.strip().strip('."\'` \n').lower()
        if out in TRACKED_TOPICS:
            return out
        for t in TRACKED_TOPICS:
            if t in out:
                print(f"  [category_read] loose match {raw.strip()!r} -> {t!r}")
                return t
        print(f"  [category_read] no category for {subject[:60]!r} (model said {raw.strip()[:40]!r})")
        return None
    except Exception as e:
        print(f"  [category_read] resolve failed: {type(e).__name__}: {e}")
        return None


def build(engine, topic: str) -> str:
    """A measured read of one tracked category, or "" if it cannot be earned."""
    if not topic or topic not in TRACKED_TOPICS or engine is None:
        return ""
    try:
        from sqlalchemy import text as sql_text
        with engine.connect() as conn:
            total, older, newer = conn.execute(sql_text(f"""
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE created_at <  NOW() - INTERVAL '15 days'),
                       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '15 days')
                  FROM news_scored
                 WHERE topic = :t AND created_at > NOW() - INTERVAL '{_LOOKBACK_DAYS} days'
            """), {"t": topic}).fetchone()

            if not total or total < _MIN_DOCS:
                return ""

            # Everything below is expressed against the whole-corpus baseline,
            # never in absolute terms. Measured 2026-09-04: every category runs
            # 85-90 percent "Cold / Indifferent", because that is a property of
            # news writing rather than of any subject. Quoting "87 percent cold"
            # for economics looks like measurement and carries no information,
            # since sport and religion score the same. The distance from the
            # baseline is the only part that says anything.
            base_total, base_older, base_newer = conn.execute(sql_text(f"""
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE created_at <  NOW() - INTERVAL '15 days'),
                       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '15 days')
                  FROM news_scored
                 WHERE created_at > NOW() - INTERVAL '{_LOOKBACK_DAYS} days'
            """)).fetchone()

            warm_cat, warm_base = conn.execute(sql_text(f"""
                SELECT
                  ROUND(100.0 * COUNT(*) FILTER (
                      WHERE topic = :t AND empathy_label IN ('Warm / Supportive','Highly Empathetic'))
                      / NULLIF(COUNT(*) FILTER (WHERE topic = :t), 0), 1),
                  ROUND(100.0 * COUNT(*) FILTER (
                      WHERE empathy_label IN ('Warm / Supportive','Highly Empathetic'))
                      / NULLIF(COUNT(*), 0), 1)
                  FROM news_scored
                 WHERE created_at > NOW() - INTERVAL '{_LOOKBACK_DAYS} days'
                   AND empathy_label IS NOT NULL
            """), {"t": topic}).fetchone()

            emotions = conn.execute(sql_text(f"""
                SELECT emotion_top_1, COUNT(*) FROM news_scored
                 WHERE topic = :t AND created_at > NOW() - INTERVAL '{_LOOKBACK_DAYS} days'
                   AND emotion_top_1 IS NOT NULL
                 GROUP BY emotion_top_1 ORDER BY 2 DESC LIMIT 5
            """), {"t": topic}).fetchall()
    except Exception as e:
        print(f"  [category_read] build failed for {topic!r}: {type(e).__name__}: {e}")
        return ""

    def _growth(a, b):
        return (b - a) / a * 100 if a else None

    cat_growth = _growth(older, newer)
    base_growth = _growth(base_older, base_newer)

    if cat_growth is None:
        direction = "newly emerging"
    else:
        direction = ("expanding" if cat_growth > 15 else
                     "contracting" if cat_growth < -15 else "holding steady")

    lines = [
        f"[CATEGORY SIGNAL - THE CONVERSATION THIS BRAND SITS INSIDE: {topic.upper()}]",
        "",
        "READ THIS CAREFULLY BEFORE USING IT. These figures measure the CATEGORY, not the "
        "brand the user asked about. There is no tracked read on that brand specifically. "
        "You may say what the conversation around it looks like and where it is moving. You "
        "may NOT attach any of these numbers to the brand, describe them as the brand's "
        "sentiment, mood, velocity or share, or imply they were measured about the brand. "
        "Presenting a category number as a brand number is a credibility failure and it is "
        "checkable. Never mention that brand-level signal was unavailable.",
        "",
        f"Documents in the last {_LOOKBACK_DAYS} days: {total:,} "
        f"({100.0*total/base_total:.1f}% of all tracked coverage)",
    ]
    if cat_growth is not None and base_growth is not None:
        lines.append(
            f"Direction: {direction}, {cat_growth:+.0f}% across the window "
            f"({older:,} then {newer:,}), against {base_growth:+.0f}% for tracked coverage "
            f"overall. The gap between those two is the signal; the raw figure alone is not."
        )
    else:
        lines.append(f"Direction: {direction} ({older:,} then {newer:,})")

    if warm_cat is not None and warm_base is not None:
        delta = float(warm_cat) - float(warm_base)
        rel = ("warmer than" if delta > 0.5 else
               "colder than" if delta < -0.5 else "level with")
        lines.append(
            f"Emotional register: {warm_cat}% of this coverage reads warm or highly "
            f"empathetic, {rel} the {warm_base}% baseline across everything tracked. "
            f"Report the comparison, never the raw percentage - nearly all news coverage "
            f"scores cold, so the absolute number describes journalism rather than this "
            f"subject."
        )
    if emotions:
        lines.append("Dominant emotions: " + ", ".join(f"{e} ({n:,})" for e, n in emotions))
    lines.append("")
    lines.append(
        "Use this to ground the category argument in measurement rather than in a single "
        "news story. Cite a figure only where it carries an argument, and always as a "
        "comparison to the baseline rather than on its own."
    )
    lines.append("[END CATEGORY SIGNAL]")
    return "\n".join(lines)
