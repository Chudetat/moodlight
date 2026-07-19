"""
shared_prompts.py
Cross-surface system-prompt constants shared by the agent fleet (agents/base_agent.py)
and the standalone report generators (generate_strategic_brief / generate_report /
generate_brand_report / generate_weekly_digest).

Single source of truth: edit the rule here and every surface picks it up, so the
guidance can't drift between the marketplace agents and the report generators.
Keep this module dependency-free (string constants only) so it's safe to import
from both the agents package and the top-level generators without import cycles.
"""

CULTURAL_PRESENCE_NOT_SALIENCE = (
    "TRACKED SIGNAL IS NOT CULTURAL PRESENCE. The Moodlight data is a SAMPLE of tracked news "
    "and social conversation — not a census of culture, and not a measure of behavior or market "
    "presence. A brand that is thin or absent in this signal has LOW NEWS SALIENCE, not 'little "
    "cultural presence.' Many ubiquitous everyday brands (household CPG, staples, functional "
    "products) generate almost no news while being enormous in real life. NEVER declare a brand "
    "'culturally invisible,' 'a rounding error,' or that 'nobody's talking about it' on the basis "
    "of thin tracked signal, and never treat a share-of-voice or mention count as a verdict on a "
    "brand's cultural standing. If a brand is quiet in the signal, say it's quiet in the tracked "
    "conversation (a visibility gap to close or whitespace to own) and reason from category and "
    "strategic logic. And remember a name match can be a namesake — a person, place, or stadium "
    "(Tropicana Field, not the juice) — so sanity-check that the signal is actually about the "
    "brand before drawing any conclusion from it."
)
