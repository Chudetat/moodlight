"""
agents/lifecycle_strategist.py
The Lifecycle Strategist — CRM, email, retention, and stage-based
journey design for the full customer lifecycle (acquisition →
onboarding → engagement → retention → win-back → advocacy).

Different from the Comms Planner (campaign-moment channel planning)
and the Content Strategist (editorial content pillars). This agent
designs triggered, stage-based journeys keyed to customer state.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class LifecycleStrategistAgent(MoodlightAgent):

    agent_name = "lifecycle_strategist"
    model = "claude-opus-4-6"
    max_tokens = 8000

    system_prompt = (
        "You are a lifecycle strategist who has watched too many brands "
        "spend 90% of their budget on acquisition and 10% on retention — "
        "then wonder why LTV is flat. You design triggered customer "
        "journeys across the full lifecycle: onboarding that actually "
        "activates, engagement loops that compound, retention plays that "
        "work before churn, win-backs that don't feel desperate, and "
        "advocacy flows that turn customers into a growth channel. You "
        "believe every lifecycle moment should earn its send, every "
        "email should have a job, and every journey should be killable. "
        "You read live cultural signals to tune tone, timing, and "
        "emotional register to the moment the customer is actually in."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and lifecycle goals")
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

        return f"""Design a customer lifecycle strategy for:
"{user_input}"

{context}

Using the real-time cultural intelligence above to tune tone, timing, and emotional register, design a lifecycle program that covers the full customer journey end-to-end. Ground every stage in either (a) a live cultural signal from the data above or (b) a concrete customer state transition.

## 1. THE LIFECYCLE MAP

Map this brand's customer journey across six canonical stages. For each, state what the customer is feeling, what outcome the brand needs, and what signal indicates they're in this stage.

- **Acquisition**: First touch to first purchase. What makes this brand's acquisition moment culturally distinctive right now?
- **Onboarding**: First purchase through activation. Define "activated" for this specific brand.
- **Engagement**: The active customer window. What does a "healthy" engaged customer look like?
- **Retention**: The pre-churn window. What are the early-warning signals this brand should watch?
- **Win-back**: The post-churn window. How long after churn is it still worth fighting for the customer?
- **Advocacy**: The post-loyalty window. What turns a retained customer into a referrer?

## 2. JOURNEY DESIGN

Design the triggered sequences for each stage. Be specific about triggers, channels, and content — not "send a welcome email."

For each of the 6 stages, design 1-2 journey sequences:
- **Trigger**: The exact customer event or state change that kicks off the journey
- **Channel Mix**: Email, SMS, push, in-app, direct mail — and why this blend for this moment
- **Sequence Logic**: 3-5 beats, with timing between each (e.g. "Day 0, Day 3, Day 7")
- **Emotional Register**: What the customer needs to feel at this moment, tied to the cultural context above
- **Success Metric**: How this specific journey will be judged

## 3. RETENTION LEVERS

Retention dies from a thousand small leaks. Name the leaks and the interventions.

- **Churn Diagnosis**: Based on brand context and cultural signals, what are the 3-5 most likely churn causes for this brand?
- **Pre-Churn Interventions**: For each cause, the lifecycle play that prevents it (not a discount — be creative).
- **Save Offers**: If and when to use monetary save offers — and when they destroy margin without saving the customer.
- **Reactivation vs. Win-back**: Draw the line between "still a customer we can engage" and "churned and needs a different play."

## 4. THE NEXT-BEST-ACTION LAYER

The rules that decide which journey a customer enters when multiple are eligible. This is where lifecycle programs collapse without discipline.

- **Priority Rules**: If a customer is eligible for 3 journeys, which one fires? Define the hierarchy.
- **Frequency Caps**: How many touches per week/month per channel is the ceiling for this brand's audience?
- **Suppression Rules**: Which customer states should trigger total silence (recent service issue, active complaint, bereavement signal, etc.)?
- **Personalization Tiers**: What personalization is worth the engineering cost vs. what's theater?

## 5. THE 90-DAY BUILD ROADMAP

A concrete plan for what to launch first, second, third — prioritized by impact on retention and revenue.

- **Month 1**: The journey sequences to build first and why (highest leverage for this brand right now)
- **Month 2**: The next layer of journeys + the measurement infrastructure needed to see if they work
- **Month 3**: Optimization + the first round of kill/expand decisions based on what the data is showing

## 6. CROSS-SELL

End with: "Powered by Moodlight Lifecycle Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every journey must have a trigger, every stage must have a success metric, every channel must have a frequency cap, every save play must have a margin ceiling. "Send more emails" fails.
2. Run the inevitability test on the #1 retention lever: once stated, does the lifecycle lead nod because it's obviously where churn is leaking, or squint because it's clever? Obvious wins.
3. Run the substitution test on each stage's journey sequence: swap in a competitor in the same vertical. If the sequences still work, rewrite until they only fit THIS brand's customer state transitions.
4. Every send in every journey must earn its spot. If a beat exists because "that's what lifecycle decks include," cut it.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "lifecycle_strategy"
        return result
