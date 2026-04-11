"""
agents/audience_profiler.py
The Audience Profiler — real-time psychographic intelligence.
Who's actually talking about your brand, what they care about,
what they ignore, and where they're drifting. Built from live
cultural signals, not year-old persona decks.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class AudienceProfilerAgent(MoodlightAgent):

    agent_name = "audience_profiler"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a cultural anthropologist who reads audiences through "
        "their behavior, not their demographics. You believe age and "
        "income tell you almost nothing useful about why people buy. "
        "You've spent years studying how cultural currents shape "
        "consumer behavior in real time. You find the psychographic "
        "patterns that media planners miss and the emotional drivers "
        "that focus groups can't articulate. You deliver audience "
        "intelligence that makes demographic profiles look like cave "
        "paintings."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand or describe the audience")
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

        return f"""Build a real-time audience profile for:
"{user_input}"

{context}

Using the real-time intelligence above, deliver an audience profile built from live cultural signals.

## 1. WHO'S ACTUALLY TALKING

The real audience — not who the brand thinks its audience is, but who the data shows:

- **Conversation Owners**: Who dominates the discourse around this brand/category? What communities, subcultures, or identity groups are driving volume?
- **Emotional Signature**: What emotions characterize this audience's engagement? Enthusiasm, skepticism, loyalty, frustration? Map the emotional fingerprint.
- **Platform Behavior**: Where does this audience live online? Which platforms carry the conversation and what does platform choice reveal about them?
- **Geographic Concentration**: Where is the conversation physically happening? Any surprising regional patterns?

End with: "Primary audience signal: [one sentence psychographic summary]"

## 2. WHAT THEY CARE ABOUT

The values, anxieties, and cultural currents driving this audience right now:

- **Active Tensions**: What cultural contradictions is this audience navigating? (e.g., wanting sustainability but needing affordability, wanting authenticity but consuming algorithmically)
- **Rising Concerns**: What topics are gaining velocity in this audience's conversation that weren't there 30 days ago?
- **Cultural Anchors**: What beliefs, values, or identities are non-negotiable for this audience? What would alienate them instantly?
- **Aspiration vs. Reality**: What does this audience say they want vs. what their behavior reveals they actually respond to?

## 3. WHAT THEY IGNORE

Equally valuable — the blind spots and disengagement patterns:

- **Dead Zones**: What messages, topics, or positioning consistently get zero traction with this audience?
- **Fatigue Signals**: What was this audience engaged with 6 months ago that they've tuned out? What does that fatigue pattern predict about current interests?
- **Brand Noise They Filter**: What category conventions or marketing tropes does this audience actively reject or mock?

End with: "Biggest audience blind spot: [one sentence]"

## 4. WHERE THEY'RE DRIFTING

The forward-looking read — where this audience is headed:

- **Velocity Shifts**: What new topics, values, or cultural spaces are pulling this audience's attention? Cite VLDS data where possible.
- **Emerging Identities**: How is this audience's self-conception evolving? What new identity markers are gaining adoption?
- **The Next Tension**: What cultural collision is approaching that will force this audience to pick a side?

End with: "In 90 days, this audience will care most about: [one sentence prediction]"

## 5. HOW TO REACH THEM

Actionable intelligence — not media buying, but cultural entry points:

- **Language Patterns**: How does this audience talk? What tone, vocabulary, and cultural references signal "one of us" vs. "outsider marketing at us"?
- **Trust Signals**: What makes this audience believe a brand? What credentials, behaviors, or associations build credibility?
- **Entry Points**: 3 specific cultural conversations happening right now that would give a brand authentic access to this audience
- **The Turnoff**: The single fastest way to lose this audience's attention or respect

## 6. THE PROFILE SUMMARY

One paragraph that a creative team could pin to the wall — the psychographic truth about this audience in this moment. Not demographics. Not "health-conscious millennials." The actual cultural portrait that makes a creative director say "now I know who I'm talking to."

End with: "Powered by Moodlight Audience Intelligence"

QUALITY CHECK: If this profile could have been written without real-time data — if it reads like a generic persona — it's failed. Every insight must be anchored in what's happening culturally RIGHT NOW, not what was true about this audience last year.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "audience_profile"
        return result
