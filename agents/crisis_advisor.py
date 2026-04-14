"""
agents/crisis_advisor.py
The Crisis Advisor — real-time crisis response intelligence.
What to say, what not to say, and how fast to move when your brand
gets tagged in something. Built on live cultural signals, not playbooks.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CrisisAdvisorAgent(MoodlightAgent):

    agent_name = "crisis_advisor"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a crisis communications specialist who has managed "
        "brand crises across every category — from viral social media "
        "pile-ons to product recalls to executive scandals. You don't "
        "panic and you don't hedge. You give brands a clear action plan "
        "within minutes, not days. You know that the first 4 hours "
        "determine whether a crisis becomes a footnote or a funeral. "
        "You believe most brands respond too slowly, too defensively, "
        "and with too many lawyers in the room. Your advice is direct, "
        "time-stamped, and built on what the cultural conversation is "
        "actually doing right now — not what the PR textbook says."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand and the situation")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        df = data_layer.load_combined_data(days=3)
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

        return f"""This brand is in a crisis situation. Deliver a real-time crisis response plan:
"{user_input}"

{context}

Using the real-time intelligence above, deliver a crisis advisory.

## 1. SITUATION READ

What the data actually shows about this moment:

- **Signal Velocity**: How fast is this spreading? Is it accelerating, plateauing, or already fading? What does the trajectory tell you about the next 24 hours?
- **Emotional Temperature**: What emotions are driving the conversation? Anger, disappointment, mockery, concern? Each demands a different response tone.
- **Amplification Risk**: Who's carrying this? Mainstream media, social media, niche communities? What's the escalation potential from current carriers to larger platforms?
- **Cultural Context**: What broader cultural moment or conversation is this crisis sitting inside? A brand safety issue during a cultural reckoning hits differently than a standalone product complaint.

End with: "Severity: [1-10] — [one sentence on trajectory]"

## 2. THE FIRST 4 HOURS

Immediate action plan — what to do right now:

- **Say This**: Draft the exact statement. Not talking points — the actual words. Keep it under 100 words. No corporate speak. No "we take this seriously" without specifics.
- **Don't Say This**: 2-3 responses that would feel natural but will make it worse. Explain why each one backfires in this specific cultural moment.
- **Channel Priority**: Where to post first, where to stay silent, where to monitor only. Not every platform needs a response.
- **Internal Action**: What needs to happen behind the scenes in the next 4 hours.

## 3. THE 24-HOUR MAP

How this plays out and how to stay ahead of it:

- **Hour 0-4**: [What's happening now and immediate response]
- **Hour 4-12**: [Likely escalation pattern and second-wave response]
- **Hour 12-24**: [Where this settles and what the next move is]

For each window: what to watch for that changes the plan.

## 4. WHAT MAKES IT WORSE

The traps — specific things this brand might be tempted to do that will extend or escalate the crisis:

- 3-4 specific mistakes, each with WHY it backfires given the current cultural data
- Include both obvious traps (deleting posts, going silent too long) and non-obvious ones specific to this situation

## 5. THE RECOVERY PLAY

Once the acute phase passes — how to turn this from damage control into brand strength:

- **The Narrative Flip**: How to reframe this moment as evidence of brand values (only if authentic — if it's not, say so)
- **The Rebuild Signal**: One concrete action (not just words) that would shift the cultural read
- **Timeline to Normal**: Realistic assessment of how long until this fades from the conversation, based on velocity patterns

## 6. HONEST VERDICT

One paragraph. Is this a real crisis or a Twitter tempest? Will anyone remember in 30 days? Is the brand's response more important than the inciting event? Give the CEO the 60-second version.

End with: "Powered by Moodlight Crisis Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every recommendation must be specific to THIS brand in THIS moment with THIS cultural context. Generic crisis playbook advice fails. Run the substitution test: swap in a different brand facing the same crisis shape. If the advice still works, rewrite until it only fits this specific situation.
2. The "Say This" statement must read as the only honest thing this brand could say right now. Run the inevitability test: once stated, does a CEO nod because it's obviously the right words, or squint because it's clever? In a crisis, clever loses.
3. Every "Don't Say This" trap must name WHY it backfires in THIS specific cultural moment, not in general. "It will look bad" fails. "The current empathy reading is hostile/cold — apologies that start with 'we hear you' will read as performative and amplify" passes.
4. The Honest Verdict must give a real answer on whether this is a real crisis or a Twitter tempest. Hedging fails — the CEO needs a call, not a menu.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "crisis_advisory"
        return result
