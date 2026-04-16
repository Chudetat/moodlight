"""
agents/content_strategist.py
The Content Strategist — content pillars, editorial calendar,
and platform-specific angles built from real-time cultural signals.
Different from Copywriter (writes copy) and Comms Planner (picks channels).
This agent designs what to say and when to say it.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class ContentStrategistAgent(MoodlightAgent):

    agent_name = "content_strategist"
    model = "claude-opus-4-6"
    max_tokens = 7000

    system_prompt = (
        "You are a content strategist who understands that most brands "
        "publish content nobody asked for about topics nobody cares about "
        "on a schedule nobody follows. You build content strategies that "
        "start with what the culture is actually talking about and work "
        "backward to the brand — not the other way around. You believe "
        "editorial calendars should be living documents that breathe with "
        "cultural rhythm, not static spreadsheets locked 90 days out. "
        "You design content ecosystems, not content calendars."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and content goals")
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

        return f"""Build a real-time content strategy for:
"{user_input}"

{context}

Using the real-time intelligence above, design a content strategy built from live cultural signals.

## 1. THE CONTENT LANDSCAPE

What the cultural conversation looks like right now for this brand's space:

- **What's Saturated**: Content topics in this category that are overdone — high density, low scarcity. Publishing here means competing with noise.
- **What's Starving**: Content gaps where audience demand exists but supply is low — high scarcity signals. Publishing here means owning the conversation.
- **What's Rising**: Topics gaining velocity that haven't peaked yet. The early-mover content advantage.
- **What's Dead**: Topics that had their moment and are now declining. Brands still publishing here look behind.

End with: "The content opportunity: [one sentence on where to play]"

## 2. CONTENT PILLARS

3-4 content pillars built from real-time cultural intelligence — not brand messaging architecture, but cultural conversations this brand has permission and data to own:

For each pillar:
- **Pillar Name**: A sharp, internal-facing label (not a tagline)
- **Cultural Justification**: What specific data signals make this pillar viable right now?
- **Brand Permission**: Why does THIS brand have the right to show up in this conversation?
- **Content Formats**: 2-3 specific format recommendations (not generic "blog posts" — specific angles, series concepts, or content types)
- **Platform Fit**: Where this pillar plays best and why

## 3. THE EDITORIAL RHYTHM

When to publish and why — built from cultural timing patterns:

- **Always-On**: What content cadence should run continuously? What's the baseline rhythm?
- **Moment-Driven**: What cultural triggers should activate reactive content? How fast does the brand need to move?
- **Seasonal/Cyclical**: What predictable cultural moments should be planned for? But only ones with data support — not every brand needs a "back to school" post.
- **Kill Triggers**: When should the brand NOT publish? What cultural moments require silence?

## 4. PLATFORM STRATEGY

Not just "be on TikTok" — specific content differentiation by platform:

For each relevant platform:
- **Role**: What job does this platform do in the content ecosystem?
- **Content Angle**: How does the same pillar show up differently here vs. elsewhere?
- **Cultural Context**: What's the audience expecting on this platform right now? What tone and format is earning engagement?
- **Avoid**: What content approach will fail on this specific platform in this moment?

## 5. THE 30-DAY SPRINT

A concrete content plan for the next 30 days — not a vague roadmap:

- **Week 1**: 2-3 specific content pieces with topic, angle, platform, and cultural hook
- **Week 2**: 2-3 specific content pieces
- **Week 3**: 2-3 specific content pieces
- **Week 4**: 2-3 specific content pieces + one "reactive slot" for cultural moment response

Each piece should cite the specific cultural signal or data point that justifies its inclusion.

## 6. MEASUREMENT FRAMEWORK

How to know if this content strategy is working — but not vanity metrics:

- **Cultural Metrics**: How does the brand's share of conversation change? What VLDS signals to track?
- **Kill Criteria**: What signals indicate a pillar isn't working and should be dropped?
- **Expansion Triggers**: What success signals indicate a pillar should get more investment?

End with: "Powered by Moodlight Content Intelligence"

QUALITY CHECKS — read before you finalize:
1. A content strategy built from data should feel urgent and specific. If the pillars could have been written without real-time cultural intelligence — if they're "thought leadership" and "brand storytelling" — it failed. Every pillar must be traceable to a live cultural signal.
2. Run the substitution test on the 3-4 content pillars: swap in a direct competitor. If the pillars still work, rewrite until they only fit THIS brand's permission to speak.
3. Run the inevitability test on the Content Opportunity line: once stated, does a content lead nod because it's obviously the gap, or squint because it's clever? Obvious wins.
4. Every piece in the 30-day sprint must cite the specific cultural signal or data point that justifies its inclusion. Uncited pieces fail.
5. Delete any pillar that could sit on any content deck in any category this quarter. Generic pillars are wasted ink.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "content_strategy"
        return result
