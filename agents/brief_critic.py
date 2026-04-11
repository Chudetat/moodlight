"""
agents/brief_critic.py
The Brief Critic — takes an existing brief or strategy document and tears
it apart against live cultural data. Finds what's stale, what's wrong,
and what's missing. The editor every strategist needs but nobody wants.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class BriefCriticAgent(MoodlightAgent):

    agent_name = "brief_critic"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are the most feared brief reviewer in the industry. You've killed "
        "more bad briefs than anyone alive. You believe 90% of briefs are built "
        "on assumptions that were true six months ago and nobody bothered to check. "
        "You don't rewrite briefs — you expose where they're wrong, stale, or lazy, "
        "and you tell people exactly what to fix. You're not mean. You're precise. "
        "Every critique is backed by data, not taste."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — paste the brief, strategy, or positioning you want critiqued")
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
        polymarket = data_layer.load_polymarket_data()

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            brand_context=brand_context,
            polymarket=polymarket,
        )

        return {"context": context_str}

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""A strategist has submitted this brief for your review:

---
{user_input}
---

{context}

YOUR ROLE IS DATA-DRIVEN, NOT DESTRUCTIVE:
Let the live data determine your response — not a default posture of tearing things apart. If the brief's claims are backed by current signals, say so and build on them. If they're contradicted by the data, flag it. Credit what's strong. Critique what's weak. Extend what's missing. The best review finds what the brief didn't see — not what's wrong with what it did see. Your job is to make the brief better, not to prove you're smarter than the person who wrote it.

Using the real-time intelligence above, review this brief.

THIN INPUT PROTOCOL: If the submitted brief is very short (a few words or one sentence rather than a full brief), don't try to critique what isn't there. Instead, treat the input as a topic or brand and generate the brief FOR them — write what a strong brief for this challenge should contain based on the live data, structured as a recommended brief they can take and refine.

## 1. THE STALENESS CHECK

Go through the brief line by line and flag every assumption, claim, or positioning choice that the CURRENT data contradicts or doesn't support:

- **Stale assumptions**: What does this brief assume about the market, audience, or culture that the live data says is no longer true?
- **Unsupported claims**: What assertions does this brief make that have zero evidence in current signals?
- **Outdated positioning**: Is the strategic territory this brief is betting on still available, or has it been claimed, saturated, or shifted?

For each finding, cite the specific data point that contradicts the brief's assumption.

End with: "Staleness score: [X out of 10] — [one sentence verdict]"

## 2. THE BLIND SPOTS

What this brief doesn't see — the threats and opportunities it's ignoring:

- **Cultural signals it's missing**: What's happening in culture RIGHT NOW that's relevant to this brief's category or audience that isn't mentioned?
- **Competitive moves it's ignoring**: What are competitors doing in the data that this brief doesn't account for?
- **Audience reality vs. brief fantasy**: Does the emotional and topical data support this brief's assumptions about its target audience?

End with: "The biggest blind spot: [one sentence]"

## 3. THE DENSITY PROBLEM

Is this brief walking into a crowded room or finding open space?

- **Saturation check**: Using density data, how crowded is the territory this brief is targeting? If density is high, the brief is fighting for attention in a room full of people saying the same thing.
- **Differentiation gap**: What in this brief could ANY competitor also say? Flag every generic line.
- **The scarcity alternative**: Using scarcity data, identify what this brief SHOULD be targeting — the underserved conversations where there's less competition and more opportunity.

End with: "Density verdict: [crowded / open / suicidal]"

## 4. WHAT'S ACTUALLY WORKING

Not everything is wrong. Identify:

- **Strong moves**: What parts of this brief are supported by current data? What instincts were right?
- **Salvageable ideas**: What concepts have potential but need to be redirected based on current signals?
- **The kernel**: If you had to save ONE idea from this brief and rebuild around it, what would it be?

End with: "Save this: [the one idea worth keeping]"

## 5. THE REWRITE DIRECTIVES

Don't rewrite the brief. Give the strategist exactly what to change:

- **Kill list**: 3-5 specific things to cut from this brief immediately
- **Add list**: 3-5 specific things the data says should be in this brief
- **Redirect**: The single biggest strategic pivot this brief needs — where should it be pointing instead?

For each directive, cite the data that justifies the change.

## 6. THE VERDICT

One paragraph. Would you approve this brief, send it back, or kill it? Be honest. Frame it as: if this brief goes to production as-is, what happens?

End with: "Powered by Moodlight Brief Intelligence"

QUALITY CHECK: Every critique must cite specific data. "This feels generic" is not a critique. "This targets sustainability but density is 8.4 — the 3rd most saturated topic in the data. You're screaming into a crowd" is a critique.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "brief_critique"
        return result
