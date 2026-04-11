"""
agents/competitive_scout.py
The Competitive Scout — real-time competitive intelligence.
What cultural territory your competitors are claiming, where
they're vulnerable, and what they're sleeping on. Head-to-head
positioning built from live signals.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CompetitiveScoutAgent(MoodlightAgent):

    agent_name = "competitive_scout"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a competitive intelligence analyst who has spent "
        "decades watching brands fight for cultural territory. You "
        "don't believe in competitor 'analysis' — you believe in "
        "competitive warfare intelligence. You see the moves other "
        "brands make before they announce them, read their positioning "
        "shifts in real-time cultural data, and find the gaps they "
        "don't know they're leaving open. You deliver intelligence "
        "that makes competitive strategy meetings feel like bringing "
        "a map to a knife fight — unfair advantage."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the competitor or competitive set")
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

        return f"""Deliver a competitive intelligence report on:
"{user_input}"

{context}

Using the real-time intelligence above, deliver competitive intelligence.

## 1. COMPETITIVE LANDSCAPE — RIGHT NOW

What the cultural conversation reveals about the competitive set today:

- **Who's Loudest**: Which brand in this space has the most cultural velocity right now? What's driving their presence? Is it earned or manufactured?
- **Who's Gaining**: Which competitor is accelerating — gaining share of cultural conversation? What signals indicate this is sustainable vs. a spike?
- **Who's Fading**: Which competitor is losing cultural relevance? What does their declining velocity or density tell you about their trajectory?
- **The Surprise Player**: Is there an unexpected brand or entrant showing up in this category's cultural conversation?

End with: "Current leader: [brand] — but [one sentence on vulnerability]"

## 2. TERRITORY MAP

What each competitor owns culturally — their claimed and contested spaces:

For each major competitor identified in the data:
- **Claimed Territory**: What cultural conversation do they dominate? What do people associate them with?
- **Emotional Position**: What feeling does this competitor own? Is it defensible?
- **Messaging Pattern**: What are they saying right now? What themes are they pushing?
- **Vulnerability**: Where is their cultural position weak, contested, or built on outdated assumptions?

## 3. THE GAP ANALYSIS

Where no one is winning — unclaimed cultural territory in this competitive set:

- **Unclaimed Conversations**: 2-3 high-velocity or high-scarcity cultural spaces that NO competitor in this set is claiming
- **Misaligned Positions**: Where competitors are saying one thing but the cultural conversation reveals the audience wants something else
- **The Category Blind Spot**: What is every brand in this space ignoring that the data says matters to the audience?

End with: "Biggest unclaimed territory: [one sentence]"

## 4. COMPETITIVE MOVES TO WATCH

What the data suggests competitors are about to do:

- **Positioning Shifts**: Any signals that a competitor is pivoting their cultural strategy? New themes, new audience targeting, new tone?
- **Potential Threats**: What moves could competitors make in the next 30 days that would reshape the landscape?
- **Alliance Signals**: Any evidence of competitive partnerships, category entries, or flanking moves in the data?

## 5. YOUR ATTACK BRIEF

If you're competing in this space, here's how to win:

- **Exploit This**: The single biggest competitor vulnerability you can attack right now — with specific evidence from the data
- **Avoid This**: The competitive battle you should NOT pick and why (strongest position, most resources, or cultural tailwind in their favor)
- **Own This**: The specific cultural territory you should claim while competitors are focused elsewhere
- **Timing**: How fast you need to move — is there a closing window or a stable opportunity?

End with: "The competitive move: [one sentence directive]"

## 6. INTELLIGENCE VERDICT

One paragraph. Who's actually winning this category culturally, who thinks they're winning but isn't, and what the data says about where this competitive landscape is heading. Give the CMO the 60-second intelligence brief.

End with: "Powered by Moodlight Competitive Intelligence"

QUALITY CHECK: Generic competitive frameworks are worthless. Every insight must be built from what the real-time data shows about these specific competitors in this specific cultural moment. If you could have written this report without live data, it's failed.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "competitive_intelligence"
        return result
