"""
agents/comms_planner.py
The Comms Planner Agent — takes a campaign or message, pulls real-time
signals, and outputs a channel/timing plan based on where attention is
and where whitespace exists.

This is distribution strategy — not what to say, but where, when, and how
to deploy it for maximum impact.
"""

from .base_agent import MoodlightAgent
from . import data_layer
from generate_strategic_brief import REGULATORY_GUIDANCE


class CommsPlannerAgent(MoodlightAgent):

    agent_name = "comms_planner"
    model = "claude-opus-4-6"
    max_tokens = 4000

    system_prompt = (
        "You are the sharpest comms planner in the industry. You don't believe "
        "in 'be everywhere' — you believe in being in the right place at the right "
        "moment with the right message. You've seen a thousand media plans that spread "
        "budget like peanut butter. Yours concentrate force where it matters. "
        "Every recommendation is backed by where attention actually is, not where "
        "marketers wish it was."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the campaign, message, or what you're trying to distribute")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        # Comms planner uses tighter window for timing relevance
        df = data_layer.load_combined_data(days=3)
        snapshot = data_layer.build_intelligence_snapshot(df)
        headlines = data_layer.load_headlines(df)
        vlds = data_layer.load_vlds_tables()
        velocity_df, density_df, scarcity_df = vlds
        brand_context = data_layer.build_enrichment(username, user_input, df)

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            brand_context=brand_context,
        )

        return {"context": context_str}

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]

        return f"""A client needs a comms plan for this:
"{user_input}"

TRAINING DATA BAN: Your ONLY sources of truth are the Moodlight intelligence data provided below. Do NOT inject assumptions about platform demographics or media behavior from your training data. Use the SOURCE DISTRIBUTION and engagement data to ground every recommendation in where conversations are actually happening RIGHT NOW.

{context}

Using the real-time intelligence above, build a comms deployment plan.

## 1. ATTENTION MAP: Where the Conversation Actually Lives

Analyze the SOURCE DISTRIBUTION and engagement data to map where attention is concentrated right now. Not where marketers assume it is — where the DATA says it is.

- **Primary channels**: Top 2-3 platforms/sources driving conversation for this topic. With data backing.
- **Secondary channels**: Emerging or underserved channels where competition is low.
- **Dead zones**: Where NOT to spend. Channels that look obvious but the data shows low engagement or saturation.

End with: "Concentrate force on: [channels] because [data reason]"

## 2. TIMING INTELLIGENCE: When to Deploy

Using VELOCITY and LONGEVITY data:

- **Launch window**: Based on topic velocity, when is the optimal moment to enter? Is the conversation accelerating (ride the wave) or peaking (you're already late)?
- **Day-of-week / time-of-day**: Based on when high-engagement content is being posted, when should you deploy?
- **Conversation lifecycle**: Where is this topic in its lifecycle? (Emerging → Accelerating → Peak → Declining → Residual). Be specific.
- **Counter-programming windows**: When is competition quietest? When could you own the conversation by timing around the noise?

End with: "Deploy on: [specific timing] because [data reason]"

## 3. CHANNEL MIX: The Battle Plan

For each recommended channel, provide:

| Channel | Role | Content Format | Investment Level | Why |
|---------|------|---------------|-----------------|-----|
| [Platform] | [Awareness/Engagement/Conversion] | [Format] | [High/Med/Low] | [Data reason] |

Maximum 5 channels. If you recommend more, you're spreading too thin.

## 4. MESSAGE SEQUENCING: The 72-Hour Launch Plan

Structure the rollout:

- **Hour 0-4** (Seed): What goes out first, where, and why. The goal is to establish the narrative before anyone else does.
- **Hour 4-12** (Amplify): How does the message expand? Who picks it up? What's the second wave?
- **Hour 12-24** (Respond): How do you respond to initial engagement/reactions? What's the reactive playbook?
- **Day 2** (Sustain): How do you keep momentum without repeating yourself?
- **Day 3** (Pivot or Push): Based on response, do you double down or shift?

For each phase, one specific action — not a vague intention.

## 5. WHITESPACE OPPORTUNITY

The most valuable part of this plan. Identify:

- **The gap**: Where is there a conversation happening that NO brand is participating in? Use SCARCITY data.
- **The angle in**: How does your client's message connect to that whitespace?
- **The risk**: Why isn't anyone there already? (Is it truly opportunity, or is there a reason brands avoid it?)

End with: "The whitespace play: [one sentence]"

## 6. MEASUREMENT SIGNALS

Not generic KPIs. Specific signals to watch:

- **Green light** (working): What would you see in the first 24 hours that confirms the plan is working?
- **Yellow light** (adjust): What signals suggest you need to tweak channels or timing?
- **Red light** (pull back): What would make you recommend pausing the campaign?

## 7. THE ONE-SENTENCE PLAN

If you had to brief a CMO in one sentence, what's the plan?

End with: "---
Powered by Moodlight Comms Intelligence"

QUALITY CHECK: Every channel recommendation must cite specific data from the intelligence snapshot. "LinkedIn is good for B2B" is generic garbage. "LinkedIn is driving 34% of source volume on this topic with 3x the engagement of X" is intelligence.

{REGULATORY_GUIDANCE}
"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "comms_plan"
        return result
