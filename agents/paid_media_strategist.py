"""
agents/paid_media_strategist.py
The Paid Media Strategist — paid channel mix, budget allocation,
audience targeting, creative rotation, bid strategy, and measurement
for paid acquisition and growth.

Different from the Comms Planner (full paid+earned+owned campaign-
moment opportunity map) and the Social Strategist (organic social
content). This agent goes deep on paid media economics and
deployment.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class PaidMediaStrategistAgent(MoodlightAgent):

    agent_name = "paid_media_strategist"
    model = "claude-opus-4-6"
    max_tokens = 10000

    system_prompt = (
        "You are a paid media strategist who has spent more money on ads "
        "than most CFOs have ever seen in their lives, and you have "
        "opinions about where every dollar goes. You build channel mixes "
        "from the business goal backward — not from the platform rep's "
        "pitch deck forward. You believe most paid media plans over-"
        "invest in platforms with declining signal and under-invest in "
        "creative rotation. You are obsessive about creative fatigue, "
        "holdout tests, and the difference between efficiency and "
        "incrementality. You read live cultural signals to decide when "
        "an audience is ready for a message and when they're sick of it."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and paid media goals")
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

        return f"""Build a paid media strategy for:
"{user_input}"

{context}

Using the real-time cultural intelligence above to pressure-test platform readiness and audience receptivity, build a paid media plan. Go deep on channel economics — this is not a general comms plan, it's a paid deployment plan.

## 1. THE CHANNEL MIX

Name every paid channel you'd use and every one you'd skip. Allocate budget percentages and defend each.

For each recommended channel:
- **Role in the Mix**: Is this channel for awareness, consideration, conversion, or retention? A channel doing two jobs poorly is worse than one job well.
- **Budget Allocation**: Rough percentage of total paid budget and why this number.
- **Cultural Fit**: What live signal from the data above tells you this audience is on this platform right now, and whether the platform's content climate is receptive to this brand.
- **Deprecation Watch**: Any signal this channel is declining in signal-to-noise for this audience.

And name 2-3 channels this brand should NOT use and why. Being everywhere is a budget leak.

## 2. AUDIENCE TARGETING STRATEGY

Paid media is broken when targeting is either too narrow (no scale) or too broad (no relevance).

- **Core Audiences**: 3-5 specific audience definitions with clear activation instructions (interest + behavior + lookalike + 1P).
- **Expansion Strategy**: How to grow beyond core audiences without diluting quality.
- **Exclusions**: Audiences to actively suppress (existing customers on prospecting, fatigued segments, competitors).
- **First-Party Data Play**: How the brand's CRM data should feed targeting — and the privacy/consent guardrails.

## 3. CREATIVE ROTATION & FATIGUE

Creative fatigue is the #1 killer of paid performance. Design a rotation discipline.

- **Creative Volume**: How many unique ad variants this brand needs in-market at any given time to avoid fatigue.
- **Rotation Cadence**: How often new creative must be produced and swapped in.
- **Format Mix**: Static vs. video vs. native vs. dynamic. Justify the blend for this category and audience.
- **Cultural Refresh Triggers**: When a shift in live cultural signal should force a full creative refresh, not an incremental iteration.
- **Fatigue Signals**: The metrics that tell the team a creative is burning out before CPA collapses.

## 4. BID & MEASUREMENT LOGIC

How the team should bid, measure, and judge performance. The disciplined part.

- **Bid Strategy**: Recommended bid approach per channel (value-based, target CPA, max conversions, etc.) and why.
- **ROAS / CPA Targets**: Guidance on where to set targets — and the honesty that platform-reported ROAS is not the same as incremental ROAS.
- **Holdout Tests**: 2-3 specific geo or audience holdouts this brand should run in the next 90 days to separate correlation from causation.
- **Attribution Caveat**: One paragraph on what this measurement approach WILL miss. Every paid strategist should know their blind spots.

## 5. THE 30-60-90 MEDIA PLAN

A concrete deployment schedule.

- **Days 1-30**: Launch mix, initial budget split, creative batch, audiences. What "good" looks like at the end of month 1.
- **Days 31-60**: Based on early signal, which channels to double down on, which to cut, and what new creative rotation to deploy.
- **Days 61-90**: The first real optimization cycle. What the team should have learned about this brand's paid media elasticity by now.
- **Kill Criteria**: The specific performance thresholds that trigger pausing a channel or creative entirely.

## 6. CROSS-SELL

End with: "Powered by Moodlight Paid Media Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every channel must have a defined role, every audience must have an exclusion rule, every creative must have a fatigue trigger, every KPI must have a blind spot noted. Platform-rep pitch decks fail.
2. Run the inevitability test on the channel mix: once stated, does a CMO nod because it's obviously where this brand's dollars should go, or squint because it's clever? Obvious wins.
3. Run the substitution test on the audience targeting: swap in a direct competitor. If the audience definitions still work, rewrite until they only fit THIS brand's 1P data and positioning.
4. The Holdout Tests must be real tests the team could run next month, not "run an incrementality study someday." Name the geo, the duration, and the threshold of truth.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "paid_media_strategy"
        return result
