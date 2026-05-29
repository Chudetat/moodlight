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
