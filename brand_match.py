"""
Shared brand-matching helper.

Step 0: word-boundary matching. Brand retrieval across Moodlight (Ask widget,
website Ask, dashboard, marketplace, reports) finds a brand's posts by matching
the brand name against post text. Naive substring matching produces fragment
false positives — "virgin" matches "Virginia", "corona" matches "coronavirus",
"shell" matches "seashell". Matching on word boundaries (\bbrand\b) eliminates
that whole class for every brand, with no per-brand configuration.

This does NOT resolve true sense-homonyms that survive word boundaries (the
Virgin Mary, the US Virgin Islands, a "virgin mojito", the sun's corona). Those
need the brand-disambiguation catalog layer, which will extend this module.
See memory: project_brand_retrieval_limitation.
"""

import re
import pandas as pd


def resolve_brand_match(text_series: pd.Series, brand: str) -> pd.Series:
    """Boolean mask of rows whose text mentions ``brand`` as a whole word.

    Args:
        text_series: a pandas Series of post text (any case).
        brand: the brand name (any case). Falsy / non-string -> all-False mask.

    Returns:
        Boolean Series aligned to ``text_series.index``.

    Word boundaries (``\\b``) prevent substring-fragment false positives while
    still matching possessives ("Nike's"), multi-word names ("Liquid Death"),
    and names with digits ("7up"). The brand is regex-escaped, so special
    characters in a name (e.g. "AT&T") are matched literally, not as regex.
    """
    if not isinstance(brand, str) or not brand.strip():
        return pd.Series(False, index=text_series.index)
    pattern = r"\b" + re.escape(brand.strip().lower()) + r"\b"
    return text_series.str.lower().str.contains(pattern, na=False, regex=True)
