"""
agents/data_strategist.py
The Data Strategist — measurement plans, KPI hierarchies, first-party
data activation, attribution, and learning agendas built from real-time
cultural signals and the brand's operating context.

Different from the Audience Profiler (who the audience is) and the
Content Strategist (what to publish). This agent designs how the brand
instruments, measures, and learns from its own activity.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class DataStrategistAgent(MoodlightAgent):

    agent_name = "data_strategist"
    model = "claude-opus-4-6"
    max_tokens = 7000

    system_prompt = (
        "You are a data strategist who has watched too many brands confuse "
        "dashboards for decisions. You build measurement plans that start "
        "with the business question, not the available metric. You believe "
        "first-party data is worthless if it isn't activated, KPI trees are "
        "worthless if they don't ladder to revenue, and attribution models "
        "are worthless if teams don't trust them. You design what to "
        "instrument, what to ignore, and what to learn — and you are brutal "
        "about vanity metrics. You read live cultural signals as the outside "
        "context that validates or invalidates the brand's internal "
        "measurement assumptions."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and measurement goals")
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

        return f"""Build a measurement and data activation plan for:
"{user_input}"

{context}

Using the real-time intelligence above as the outside market context, design a data strategy that tells this brand what to instrument, what to activate, and what to learn. Ground every recommendation in either (a) a live cultural signal from the data above or (b) a concrete business decision the brand needs to make.

## 1. THE KPI HIERARCHY

Build a three-tier KPI tree that ladders from business outcome down to daily operating metrics. No vanity metrics allowed.

- **North Star Metric**: The single number this brand should manage to. Define it, justify it, and name what it excludes and why.
- **Tier 1 — Outcome KPIs (3-5 metrics)**: The business results the North Star is composed of (e.g. revenue, retention, LTV, category share). For each: the definition, the decision it informs, and the cultural signal from the data above that makes this metric load-bearing right now.
- **Tier 2 — Driver KPIs (5-8 metrics)**: The inputs teams can actually influence week-to-week. For each: the owner, the cadence, and the outcome KPI it rolls up to.
- **Kill List**: 3-5 metrics this brand is probably tracking that it should stop tracking. Name them specifically and explain why they're noise, not signal.

## 2. THE MEASUREMENT PLAN

How the brand will actually capture these metrics — not a wishlist, an instrumentation plan:

- **Events to Instrument**: Specific user or system events that must be captured to compute the KPIs above. Name the event, the properties to log, and the KPI it feeds.
- **Data Sources**: Where the data comes from — product, CRM, ad platforms, customer support, offline. Call out any dependencies on teams outside marketing.
- **Quality Guardrails**: The 3-5 data quality checks that must be in place before the plan goes live (e.g. deduplication, identity stitching, consent capture).
- **Cadence**: Which metrics get reviewed daily, weekly, monthly, quarterly — and who gets the report. If a metric has no owner and no cadence, it's not in the plan.

## 3. FIRST-PARTY DATA ACTIVATION

First-party data is leverage only if it's activated. Design how this brand puts its own data to work:

- **Asset Audit**: Based on the brand context and the live data above, what first-party signals does this brand likely have or should be collecting? (e.g. purchase history, browse behavior, email engagement, app telemetry, loyalty data, customer service transcripts.)
- **Activation Use Cases**: 4-6 specific plays that turn raw data into action. For each: the data asset, the audience or decision it powers, the channel of activation, and the expected lift.
- **Identity & Consent**: How the brand should think about identity resolution and consent in its specific context. Flag any regulatory or cultural risk you see in the data above.
- **The Cold-Start Play**: What this brand should do in the first 30 days if its first-party data is thin or unreliable.

## 4. THE ATTRIBUTION MODEL

Pick a model and defend it. Then tell the brand what to do when it inevitably disagrees with gut:

- **Recommended Model**: Name the attribution approach (MMM, MTA, incrementality testing, lift studies, or a hybrid) and justify the choice given this brand's size, channel mix, and data maturity.
- **What This Model Will Overweight and Underweight**: Be honest about the blind spots. Every model is wrong — the question is whether you know which way.
- **Incrementality Tests**: 2-3 specific geo or audience holdouts this brand should run in the next 90 days to pressure-test the attribution model against reality.
- **Decision Rights**: When attribution data conflicts with platform-reported ROAS or executive instinct, whose call wins and why. This is where most measurement programs die.

## 5. THE LEARNING AGENDA

A measurement plan without a learning agenda is accounting. Design what this brand is trying to find out:

- **Top 5 Questions**: The biggest strategic questions whose answers would change the brand's next 12 months — grounded in the cultural tensions visible in the data above.
- **How Each Question Gets Answered**: For each question, the study design (test, cohort analysis, survey overlay, panel, quasi-experiment) and the data sources it depends on.
- **Kill Criteria**: Name 2-3 beliefs this brand currently holds that should be considered falsified if the data shows X. If you can't write down what would change your mind, you're not learning.
- **Learning Cadence**: How insights get shared, who decides what's acted on, and how the brand avoids the "dashboard graveyard" pattern.

## 6. CROSS-SELL

End with: "Powered by Moodlight Data Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every KPI must have an owner, every metric must have a decision attached, every first-party asset must have an activation play, and every learning question must have a falsifiable answer. Dashboard wish-lists fail.
2. Run the inevitability test on the North Star: once stated, does the CMO nod because it's obviously the number that matters, or squint because it's clever? Obvious wins.
3. Run the substitution test on the Top 5 Learning Questions: swap in a different brand in the same category. If the questions still work, rewrite until they only fit THIS brand's strategic tension.
4. The Kill List must name specific vanity metrics this brand is likely tracking, not generic ones. "Avoid vanity metrics" fails. "Drop impression share from the weekly dashboard — it creates a false signal that correlates with awareness spend but not revenue" passes.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "data_strategy"
        return result
