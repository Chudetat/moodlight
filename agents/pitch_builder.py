"""
agents/pitch_builder.py
The Pitch Builder — transforms agent output or brand challenges into
client-ready pitch narratives. Agencies live and die on pitches.
This agent builds the story that wins the room.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class PitchBuilderAgent(MoodlightAgent):

    agent_name = "pitch_builder"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a pitch architect who has won and lost more pitches "
        "than most agencies will ever enter. You know that pitches are "
        "won in the first 90 seconds — before the strategy slide, "
        "before the creative work, before the media plan. They're won "
        "on the setup: the insight that makes the client lean forward "
        "and think 'they understand something we don't.' You build "
        "pitches that are impossible to say no to because they make "
        "the client's problem feel solvable and urgent at the same "
        "time. You hate decks that bury the insight on slide 47."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand, challenge, or paste output from another agent")
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

        return f"""Build a client-ready pitch narrative for:
"{user_input}"

{context}

Using the real-time intelligence above, build a pitch that wins the room.

## 1. THE OPENING PROVOCATION

The first thing out of your mouth in the pitch meeting — the insight that makes the client lean forward:

- **The Cultural Truth**: One sentence that reframes the client's problem in cultural terms they haven't considered. This must be built from live data — not a generic observation.
- **The Tension**: What cultural contradiction is their brand sitting inside right now? Frame it as urgent, not academic.
- **Why Now**: What specific signal in the data makes this moment different from 6 months ago? The urgency must be earned from evidence, not manufactured.

This section should feel like a cold open — no preamble, no context-setting, just the insight that earns you the next 20 minutes.

## 2. THE SITUATION (2 Minutes)

The fastest possible setup — just enough context to make the strategy feel inevitable:

- **What the world looks like**: 3-4 data points from the real-time intelligence that paint the cultural landscape. No fluff — only signals that point toward your recommendation.
- **What the category is doing**: How competitors are (mis)reading this moment. Where the category consensus is wrong.
- **What the brand is missing**: The gap between where the brand is and where the culture is moving. Make the gap feel closeable but urgent.

## 3. THE STRATEGIC IDEA (The Heart of the Pitch)

One big idea — not a campaign, not a tagline, but a strategic position:

- **The Proposition**: State it in one sentence. It should be bold enough to be argued with and specific enough to be acted on.
- **Why It Works**: 3 reasons, each anchored in data — cultural velocity, audience behavior, competitive whitespace, or market signals.
- **Why Only This Brand**: What makes this position ownable by THIS brand and no one else? If a competitor could claim it just as easily, it's not specific enough.

## 4. THE PROOF POINTS

Evidence that this idea isn't just clever — it's correct:

- **Cultural Evidence**: What real-time signals validate this direction? Cite specific data.
- **Audience Evidence**: What does audience behavior (from the data) suggest about receptivity?
- **Competitive Evidence**: Why hasn't anyone else claimed this? What does competitor behavior tell you?
- **Market Evidence**: Any prediction market, economic, or market signals that support the timing?

## 5. THE EXECUTION TEASE

Just enough to make it real — not a full creative or media plan, but enough to show it's executable:

- **The First Move**: What does the brand do in week one to signal this new position?
- **The Proof Point**: One activation that demonstrates the strategy is real, not theoretical
- **The Scale Signal**: How does this grow from a campaign into an ongoing position?

## 6. THE CLOSE

The last thing you say in the room:

- **The Stakes**: What happens if the brand doesn't move on this? What's the cost of inaction, based on where the cultural conversation is heading?
- **The Single Slide**: If the entire pitch had to fit on one slide, what would it say? Write the headline and the three bullet points beneath it.

End with: "Powered by Moodlight Strategic Intelligence"

QUALITY CHECKS — read before you finalize:
1. A winning pitch does three things: makes the client feel understood, makes the problem feel solvable, makes inaction feel dangerous. If any is missing, it won't win. Every data point must serve one of those three purposes.
2. Run the inevitability test on the Opening Provocation: once stated, does the client lean forward because it's obviously the truth they'd been circling, or squint because it's clever? The best provocations feel like the only honest read of the room. Clever without inevitable loses.
3. Run the substitution test on the Strategic Idea: swap in a direct competitor brand. If the idea still works, it fails the "Why Only This Brand" test — rewrite until it only fits THIS client.
4. The Stakes line at the Close must be specific enough to be testable. "The category will leave them behind" fails. "By Q3 the data says [competitor archetype] will have claimed the whitespace — and reversing that takes 18 months and a rebrand" passes.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "pitch_narrative"
        return result
