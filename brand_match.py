"""
Shared brand-matching helper.

Two layers, both applied in resolve_brand_match():

  Step 0 — word-boundary matching (all brands). Naive substring matching
  produces fragment false positives: "virgin" matches "Virginia", "corona"
  matches "coronavirus", "shell" matches "seashell", "Nike" matches "Nikesh".
  Matching on word boundaries (\\bbrand\\b) eliminates that whole class.

  Step 1 — disambiguation catalog (only brands in BRAND_CATALOG). Word
  boundaries can't resolve true sense-homonyms that ARE the whole word: the
  Virgin Mary, a "virgin mojito", the sun's corona, the city of Corona, the
  bird "dove". For a cataloged brand, a post must ALSO contain at least one
  `require` term (category/disambiguator) and none of the `exclude` terms.
  Brands NOT in the catalog fall back to plain word-boundary matching, so
  adding the catalog never changes behavior for an uncatalogued brand.

Tradeoff (intentional, safe direction): `require` is strict — it drops a
genuine brand mention that happens to carry no category word ("grab a Corona
on the beach"). For these common-word brands the consumer dataset is mostly
namesakes anyway, so the alternative (keeping coronavirus/Coronation posts as
"Corona signal") is worse. When require yields nothing, the caller falls to
its honest no-brand-signal / web path.

See memory: project_brand_retrieval_limitation.
"""

import re
import pandas as pd


# brand (lowercased) -> {"require": [...], "exclude": [...]}.
# Seed only common-word / homonym brand names; distinctive names (Nike, Netflix,
# Okta, Airbnb, Starbucks...) need no entry — word boundaries alone are clean.
# Each rule cold-verified against live data before adding (see project memory).
BRAND_CATALOG = {
    "corona":   {"require": ["beer", "cerveza", "modelo", "lager", "extra", "constellation", "ab inbev"]},
    "victoria": {"require": ["beer", "cerveza", "modelo", "lager", "grupo modelo"]},
    "dove":     {"require": ["soap", "beauty", "deodorant", "unilever", "body wash",
                             "moisturizer", "real beauty", "self-esteem", "skincare", "skin care"]},
    "shell":    {"require": ["oil", "gas", "gasoline", "petrol", "fuel", "energy",
                             "petroleum", "lng", "station", "refinery"]},
    "virgin":   {"require": ["atlantic", "galactic", "media", "mobile", "records",
                             "active", "voyages", "branson", "airline"]},
    "visa":     {"require": ["payment", "payments", "mastercard", "fintech", "credit card",
                             "debit card", "card network", "card processing", "card issuer",
                             "digital payment", "swipe", "transaction"]},
    "peloton":  {"require": ["interactive", "pton", "treadmill", "fitness", "workout",
                             "instructor", "trainer", "tread", "exercise bike",
                             "stock", "shares", "earnings", "revenue", "nasdaq", "ipo"]},
    "high noon": {"require": ["seltzer", "vodka", "gallo", "hard seltzer", "drink",
                              "rtd", "flavor", "flavour", "abv", "beverage", "cocktail", "alcohol"]},
    "delta":    {"require": ["airline", "airlines", "flight", "flights", "skymiles",
                             "delta air", "aircraft", "layover", "basic economy", "fare", "nonstop", "jet"]},
    # QSR homonyms (cold-verified vs live data Jun 2026): "subway" is mostly NYC
    # transit + "Subway Series" baseball (~44 of 249 are the sandwich brand);
    # "sonic" is overwhelmingly the hedgehog/Sega/supersonic (~3 of 401 are the
    # drive-in), so require yields ~nothing -> honest no-signal, not namesake noise.
    "subway":   {"require": ["sandwich", "sandwiches", "footlong", "foot-long", "eat fresh",
                             "sub shop", "subway restaurant", "deli"]},
    "sonic":    {"require": ["drive-in", "drive in", "limeade", "slush", "tots", "sonic drive"]},
    # Reckitt common-word Powerbrands (added Jul 2026, health-hygiene substrate):
    # "finish" the verb (race/finish line, season finale, "finish the job") and
    # "vanish"/"vanished" (disappear) are overwhelmingly namesakes. Require the
    # dish / laundry-stain category so genuine brand mentions survive and noise
    # drops to honest no-signal. Category-standard require terms; tune vs live
    # data once ingestion accumulates. (Veet is distinctive -> no catalog entry.)
    "finish":   {"require": ["dishwasher", "dishwashing", "dish soap", "dish detergent",
                             "detergent", "rinse aid", "dishwasher tablet", "dishwasher pod", "reckitt"]},
    "vanish":   {"require": ["stain", "stains", "stain remover", "laundry", "oxi action",
                             "detergent", "whitening", "carpet cleaner", "fabric", "reckitt"]},
}


def _word_mask(text_lower: pd.Series, term: str) -> pd.Series:
    """Boolean mask: rows where ``term`` appears as a whole word (case-insensitive)."""
    return text_lower.str.contains(r"\b" + re.escape(term.strip().lower()) + r"\b",
                                   na=False, regex=True)


def resolve_brand_match(text_series: pd.Series, brand: str) -> pd.Series:
    """Boolean mask of rows that genuinely mention ``brand``.

    Word-boundary match on the brand name; for a cataloged (homonym) brand,
    additionally require a category term to co-occur and exclude noisy senses.
    Falsy / non-string brand -> all-False mask. Aligned to ``text_series.index``.
    """
    if not isinstance(brand, str) or not brand.strip():
        return pd.Series(False, index=text_series.index)
    b = brand.strip().lower()
    text_lower = text_series.str.lower()
    mask = _word_mask(text_lower, b)

    rule = BRAND_CATALOG.get(b)
    if rule:
        require = rule.get("require") or []
        if require:
            any_required = pd.Series(False, index=text_series.index)
            for term in require:
                any_required |= _word_mask(text_lower, term)
            mask &= any_required
        for term in (rule.get("exclude") or []):
            mask &= ~_word_mask(text_lower, term)
    return mask


# Field labels the marketplace brief emits. Longest-first so the alternation
# matches "markets/geography" before "markets".
_BRIEF_FIELD_LABELS = sorted(
    (
        "product/service", "product", "service", "brand", "company",
        "target audience", "audience", "markets/geography", "markets",
        "geography", "key challenge", "challenge", "objective", "goal",
        "timeline/budget", "timeline", "budget",
    ),
    key=len,
    reverse=True,
)

_LABEL_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(l) for l in _BRIEF_FIELD_LABELS) + r")\s*:",
    re.IGNORECASE,
)

_BRAND_LABEL_RE = re.compile(
    r"\b(?:product\s*/\s*service|product|service|brand|company)\s*:\s*",
    re.IGNORECASE,
)

# Emitted when the brand and its category have no measurable presence in the
# window. Replaces a silent `return ""`, which let agents present generic
# cultural material as if it were a brand read.


def extract_brand_phrase(user_need, max_words=4):
    """Pull the brand/product name out of a brief.

    Marketplace briefs arrive as labeled fields ("Product/Service: Hornitos
    Target Audience: ..."). Splitting those on " in " produced a 500-char
    run-on that was then used as a literal substring match, so it matched
    nothing and enrichment silently returned empty. Prefer the labeled field,
    and cap the result — a brand name is never a paragraph.
    """
    m = _BRAND_LABEL_RE.search(user_need or "")
    if m:
        tail = user_need[m.end():]
        nxt = _LABEL_RE.search(tail)
        phrase = (tail[: nxt.start()] if nxt else tail)
    else:
        phrase = user_need or ""
        for splitter in ["targeting ", " in ", " with the challenge"]:
            phrase = phrase.split(splitter)[0]
        phrase = phrase.replace("launch/promote ", "")

    phrase = phrase.strip().strip(".,;:-—").strip()
    words = phrase.split()
    if len(words) > max_words:
        phrase = " ".join(words[:max_words])
    return phrase.strip()
