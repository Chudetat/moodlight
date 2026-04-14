"""
agents/culture_translator.py
The Culture Translator — market-specific cultural adaptation.
What lands, what doesn't, and what will get you cancelled when
you cross borders. Built from real-time signals per market.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CultureTranslatorAgent(MoodlightAgent):

    agent_name = "culture_translator"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a cultural translator who has watched global brands "
        "embarrass themselves trying to export one market's campaign "
        "to another. You know that translation isn't about language — "
        "it's about cultural operating systems. What signals ambition "
        "in New York signals arrogance in Tokyo. What's progressive in "
        "London is baseline in Amsterdam. You read the cultural code "
        "of each market and tell brands exactly what adapts, what "
        "doesn't, and what needs to be built from scratch. You've "
        "saved brands from cultural misfires that would have cost "
        "them years of market credibility."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand, campaign or brief, and target markets")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        df = data_layer.load_combined_data(days=7)
        snapshot = data_layer.build_intelligence_snapshot(df)
        headlines = data_layer.load_headlines(df)
        vlds = data_layer.load_vlds_tables()
        velocity_df, density_df, scarcity_df = vlds
        opp_map = data_layer.build_creative_opportunity_map(velocity_df, density_df, scarcity_df)
        brand_context = data_layer.build_enrichment(username, user_input, df)
        market_ctx = data_layer.load_market_context()

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            brand_context=brand_context,
            market_ctx=market_ctx,
        )

        return {"context": context_str}

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""Deliver a cultural translation brief for:
"{user_input}"

{context}

Using the real-time intelligence above, provide market-by-market cultural adaptation intelligence.

## 1. THE SOURCE CAMPAIGN/BRIEF READ

What the original campaign or brand positioning is built on culturally:

- **Cultural Assumptions**: What cultural truths does this campaign assume? What values, humor, tensions, or moments is it built on?
- **Emotional Core**: What feeling is it trying to create? Is that feeling universal or culturally specific?
- **Structural Elements**: What parts are transferable (visual language, music, brand assets) vs. culturally embedded (wordplay, references, tone)?

End with: "Transferability score: [High/Medium/Low] — [one sentence on why]"

## 2. MARKET-BY-MARKET TRANSLATION

For each target market mentioned (or implied by the brief):

### [MARKET NAME]

- **Cultural Operating System**: What are the dominant cultural values in this market RIGHT NOW? What does the real-time data reveal about current mood, tensions, and preoccupations?
- **What Lands**: Which elements of the source campaign will work here without modification? Why?
- **What Breaks**: Which elements will confuse, alienate, or offend in this market? Be specific about why — not just "it's different" but what cultural code it violates.
- **What Needs Rebuilding**: Which elements need to be conceived from scratch for this market? What local cultural signals should inform the rebuild?
- **The Local Angle**: What cultural moment or conversation in this market right now could make the campaign feel locally native rather than imported?
- **Landmines**: Specific cultural sensitivities, recent events, or ongoing tensions in this market that the campaign must avoid. Cite any relevant signals from the data.

## 3. UNIVERSAL THREADS

What connects all target markets — the transferable strategic core:

- **The Human Truth**: Is there a universal emotional or behavioral insight that works across all markets? If yes, define it precisely. If no, say so — forced universality kills campaigns.
- **Visual Language**: What visual or design elements cross borders without cultural friction?
- **Brand Assets**: Which brand equities are globally recognized enough to anchor local executions?

## 4. ADAPTATION FRAMEWORK

A practical guide for the creative team:

- **Tier 1 — Keep**: Elements that should remain identical across all markets (brand identity, core visual system, etc.)
- **Tier 2 — Adapt**: Elements that need local tuning but share a common structure (tone shifts, reference swaps, casting)
- **Tier 3 — Rebuild**: Elements that must be conceived locally (humor, cultural references, specific insights)

For each tier, be specific about what goes where.

## 5. RISK ASSESSMENT

What could go wrong — market by market:

- **Cancel Risk**: Any elements that could trigger backlash in specific markets? What's the severity?
- **Irrelevance Risk**: Any markets where the campaign might not offend but simply not register — culturally invisible?
- **Competitor Context**: Are competitors already owning similar territory in any target market? Would this campaign feel derivative locally?

End with: "Highest risk market: [market] — [one sentence on why]"

## 6. THE TRANSLATION VERDICT

One paragraph per market: go, adapt, or kill. Be direct about which markets this campaign can win in vs. where the brand needs a different approach entirely. Not every campaign should run everywhere.

End with: "Powered by Moodlight Cultural Intelligence"

QUALITY CHECKS — read before you finalize:
1. Cultural translation built on stereotypes is worse than no translation. Every market insight must cite a current data signal from that market's conversation. If the advice could have been written 5 years ago, it's not intelligence.
2. Run the inevitability test on each market's "What Breaks" finding: once stated, does a local operator nod because it's obviously the trap, or squint because it's clever? Obvious wins — the value is naming what they couldn't have un-seen on their own.
3. Run the substitution test on the Universal Threads: swap in a different source campaign. If the "human truth" still holds, it's too abstract — rewrite until it fits only THIS campaign in THESE markets.
4. The Highest Risk Market call must be a real call, not a hedge. If every market is "medium risk," the read failed.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "culture_translation"
        return result
