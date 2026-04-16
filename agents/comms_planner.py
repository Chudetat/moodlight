"""
agents/comms_planner.py
The Comms Planner Agent — takes a campaign or message, pulls real-time
signals, and outputs a channel/timing plan based on where attention is
and where whitespace exists.

This is distribution strategy — not what to say, but where, when, and how
to deploy it for maximum impact.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CommsPlannerAgent(MoodlightAgent):

    agent_name = "comms_planner"
    model = "claude-opus-4-6"
    max_tokens = 7000

    system_prompt = (
        "You've run media for brands that outperformed competitors spending 10x more. "
        "You know attention is a commodity and timing is the only real edge. "
        "You don't believe in 'be everywhere' — you believe in being in the right place "
        "at the right moment with the right message. You've seen a thousand media plans "
        "that spread budget like peanut butter. Yours concentrate force where it matters. "
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

        df = data_layer.load_combined_data(days=5)
        # Fallback to 7 days if insufficient data
        if len(df) < 500:
            df = data_layer.load_combined_data(days=7)
        snapshot = data_layer.build_intelligence_snapshot(df)
        headlines = data_layer.load_headlines(df)
        vlds = data_layer.load_vlds_tables()
        velocity_df, density_df, scarcity_df = vlds
        opp_map = data_layer.build_creative_opportunity_map(velocity_df, density_df, scarcity_df)
        brand_context = data_layer.build_enrichment(username, user_input, df)

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            brand_context=brand_context,
        )

        return {"context": context_str}

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""A client needs a comms plan for this:
"{user_input}"

{context}

Using the real-time intelligence above, build a comms deployment plan.

## 1. ATTENTION MAP: Where the Conversation Actually Lives

Analyze the SOURCE DISTRIBUTION and engagement data to map where attention is concentrated right now. This is pure intelligence — where IS the conversation, not where should it be.

- **Conversation centers**: Top 3-4 platforms/sources driving volume for this topic. With data.
- **Signal quality**: Which sources are generating engagement vs. just noise? High volume doesn't mean high impact.
- **The dead zones**: Where is volume low AND engagement low? These are the places that LOOK obvious but the data says to avoid.

End with: "The conversation lives on: [platforms] — that's where the audience already is"

## 2. TIMING INTELLIGENCE: When to Deploy

Using VELOCITY and LONGEVITY data:

- **Launch window**: Based on topic velocity, when is the optimal moment to enter? Is the conversation accelerating (ride the wave) or peaking (you're already late)?
- **Conversation lifecycle**: Where is this topic in its lifecycle? (Emerging → Accelerating → Peak → Declining → Residual). Be specific.
- **Counter-programming windows**: When is competition quietest? When could you own the conversation by timing around the noise?

End with: "Deploy on: [specific timing] because [data reason]"

## 3. CHANNEL MIX: The Battle Plan

For each recommended channel:

| Channel | Role | Content Format | Investment Level | Why (cite data) |
|---------|------|---------------|-----------------|-----------------|
| Reddit | Seed / Credibility | Long-form commentary | Medium | 18% source share, 4x avg engagement on this topic |

Maximum 5 channels. Include one SECONDARY channel from the CREATIVE OPPORTUNITY MAP where scarcity is high — this is your low-competition flanking move. Flag it as the whitespace play.

## 4. THE 72-HOUR LAUNCH SEQUENCE

Structure the rollout:

- **Hour 0-4** (Seed): What goes out first, where, and why. The goal is to establish the narrative before anyone else does.
- **Hour 4-12** (Amplify): How does the message expand? Who picks it up? What's the second wave?
- **Hour 12-24** (Respond): How do you respond to initial engagement/reactions? What's the reactive playbook?
- **Day 2** (Sustain): How do you keep momentum without repeating yourself?
- **Day 3** (Pivot or Push): Based on response, do you double down or shift?

For each phase, one specific action — not a vague intention.

## 5. WHITESPACE OPPORTUNITY

The most valuable part of this plan. Identify:

- **The gap**: Where is there a conversation happening that NO brand is participating in? Use SCARCITY data and the CREATIVE OPPORTUNITY MAP — topics marked [OPPORTUNITY] are underserved.
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

End with: "Powered by Moodlight Comms Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every channel recommendation must cite specific data from the intelligence snapshot. "LinkedIn is good for B2B" fails. "LinkedIn is driving 34% of source volume on this topic with 3x the engagement of X" passes.
2. Run the inevitability test on the Whitespace Play: once stated, does a CMO nod because it's obviously the right flanking move, or squint because it's clever? Obvious wins — but the whitespace must still be unclaimed.
3. Run the substitution test on the 72-hour launch sequence: swap in a competitor in the same category. If the sequence still works, rewrite until it only fits THIS message in THIS moment.
4. The one-sentence plan must be specific enough for a CMO to act on without a follow-up meeting. Vague plans are theater, not intelligence.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "comms_plan"
        return result
