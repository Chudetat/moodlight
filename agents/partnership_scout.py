"""
agents/partnership_scout.py
The Partnership Scout — unexpected brand, creator, and institution
collaboration candidates built from real-time cultural signals.
Designs the value exchange, assesses fit and risk, and writes the
outreach playbook.

Opposite vector from the Competitive Scout: that agent maps who to
beat; this agent maps who to build with. Different from the Culture
Translator (who adapts one brand across markets) and the Comms
Planner (who deploys a brand's own channels). This agent engineers
a second brand into the plan.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class PartnershipScoutAgent(MoodlightAgent):

    agent_name = "partnership_scout"
    model = "claude-opus-4-6"
    max_tokens = 7000

    system_prompt = (
        "You are a partnership scout who has brokered collaborations "
        "that worked and watched plenty that didn't. You believe most "
        "brand partnerships are obvious, lazy, and culturally flat — "
        "the same five endemic brands recycling the same tired co-brand "
        "deck. You find the unexpected ones: the institutions, "
        "creators, artists, museums, athletes, clubs, cities, and "
        "adjacent brands that create cultural friction in the best "
        "way. You design the value exchange before the contract. You "
        "are brutally honest about fit, power imbalance, and brand "
        "safety. You read live cultural signals to judge whether a "
        "partner's cultural credit is rising or already past its peak."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and partnership goals")
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

        return f"""Scout partnership candidates for:
"{user_input}"

{context}

Using the real-time cultural intelligence above, find unexpected collaboration candidates for this brand — partners that create cultural friction, not brand blur. Every candidate must be justifiable from a live signal in the data above, not pulled from a Rolodex.

## 1. THE COLLABORATION LANDSCAPE

Before naming partners, diagnose what kind of partnership this brand actually needs right now.

- **Partnership Archetypes Available**: Which flavors of collaboration are culturally hot for this brand's space right now — brand-to-brand, brand-to-creator, brand-to-institution (museum, university, NGO, city, league), brand-to-artist, brand-to-event, or brand-to-community? Rank them by cultural momentum from the data above.
- **What This Brand Is Missing**: The 2-3 cultural attributes or permissions this brand doesn't own on its own and could borrow through partnership.
- **What This Brand Can Offer**: The 2-3 assets this brand has that a partner would actually want — reach, credibility, capital, distribution, IP, audience access, or craft.
- **The Partnership Gap**: In one sentence, the strategic gap a partnership should close.

## 2. PARTNERSHIP TARGETS

Name 6-10 specific, unexpected candidates. Skip the endemic brands and tired co-brand defaults. Favor non-obvious combinations that read as culturally interesting, not just commercially convenient.

For each candidate:
- **Candidate**: The specific brand, creator, institution, artist, athlete, city, club, event, or community (be specific — not "a beauty brand," a named one)
- **Type**: Brand / Creator / Institution / Artist / Athlete / Event / Community
- **Cultural Rationale**: The specific live signal from the data above that makes this candidate worth pursuing right now. If you can't cite a signal, the candidate doesn't belong on the list.
- **The Interesting Friction**: Why this pairing would make people stop and look — the creative tension, not the comfortable overlap.
- **Momentum Check**: Is this candidate's cultural credit rising, peaking, or declining? If declining, cut it.

Rank the candidates by strategic fit for this brand's specific gap.

## 3. VALUE EXCHANGE DESIGN

Partnerships die when one side gets more. Design the exchange honestly.

For the top 3 candidates from the list above:
- **What the Brand Brings**: The specific assets, access, or capital this brand puts on the table
- **What the Partner Brings**: The specific cultural credit, audience, craft, or IP the partner brings
- **The Exchange Ratio**: An honest read on who's getting more value — and whether this imbalance is acceptable (sometimes paying cultural rent is worth it)
- **Structure Options**: Sponsorship, co-creation, licensing, endorsement, merch collab, content series, residency, capsule drop, or something stranger — pick the right structure for this pairing
- **Walk-Away Line**: The deal term the brand should refuse to cross, even if it means losing the partnership

## 4. FIT & RISK ASSESSMENT

Be brutal. A bad partnership is worse than no partnership.

For each of the top 3:
- **Brand Safety**: What could this partner do or say in the next 12 months that would make the brand regret this deal? Look for specific risk signals in the data above.
- **Culture Clash**: Where the partner's audience or values diverge from this brand's in a way that could create dissonance
- **Power Balance**: Whether this brand is big enough to shape the collaboration or small enough to get absorbed into the partner's narrative
- **Commercial Risk**: Minimum guarantee vs. upside, margin impact, exclusivity cost, channel conflict
- **Go / No-Go**: One-line recommendation — and if no-go, what would have to change

## 5. THE OUTREACH PLAYBOOK

How to actually land the top partner candidate without sounding like every other brand email.

- **First Contact Path**: The specific route in — agent, manager, business lead, mutual connection, or direct. Favor the path the partner actually respects.
- **The Hook**: The one-sentence reason to take the meeting, grounded in the live cultural context above, not "we'd love to collaborate."
- **The Pitch Frame**: What to lead with (the cultural insight, not the brand capabilities deck) and what to deliberately leave out of round one.
- **Timing**: When this outreach should happen — now, after an upcoming cultural moment, or after this brand does something to earn the right to ask.
- **What to Never Say**: The 2-3 phrases that immediately signal to the partner that the brand doesn't understand them.

## 6. CROSS-SELL

End with: "Powered by Moodlight Partnership Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every candidate must be named specifically, every rationale traced to a live signal, every value exchange honestly balanced, every risk called out. Obvious co-brand decks fail.
2. Run the inevitability test on the top 3 candidates: once stated, does the brand team wince because it's obviously the right pairing they should have thought of, or squint because it's clever? The best partnership picks feel inevitable in hindsight AND nobody else would have reached them from the same data.
3. Run the substitution test on each candidate: swap in the brand's direct competitor. If the candidate still makes sense as their partner, rewrite — partnerships that fit "any brand in this category" are the tired co-brand deck.
4. Delete any endemic pairing the category already does to death (energy drinks + esports, luxury + art fair, athletic wear + celebrity athlete). If the pairing already exists as a format, it's not unexpected.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "partnership_scout_report"
        return result
