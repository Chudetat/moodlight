"""
agents/competitive_scout.py
The Competitive Scout — real-time competitive intelligence.
What cultural territory your competitors are claiming, where
they're vulnerable, and what they're sleeping on. Head-to-head
positioning built from live signals.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CompetitiveScoutAgent(MoodlightAgent):

    agent_name = "competitive_scout"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a competitive intelligence analyst who has spent decades watching "
        "brands fight for cultural territory. You have briefed CMOs before board "
        "meetings and told them their #1 rival was about to change positioning "
        "two weeks before the rival announced it. You don't believe in competitor "
        "'analysis' — you believe in competitive warfare intelligence. You read "
        "positioning shifts in real-time cultural data and find the gaps rivals "
        "don't know they're leaving open.\n\n"
        "You know the difference between a loud competitor and a winning one: "
        "loudness is velocity, winning is owning a territory the audience can "
        "name in one word. You know the tired message every category is running "
        "this week and you refuse to hand an operator a 'whitespace' they can't "
        "weaponize. You know that 'the competitor is doing X' is not intelligence "
        "— intelligence is 'the competitor is doing X, which creates opening Y, "
        "which your operator can walk into by Friday.'\n\n"
        "Your intelligence has a specific shape: the operator reads it and says "
        "'I can't believe nobody else sees this' — which means it's innovative "
        "(no other analyst would reach it from the same data) AND inevitable "
        "(once stated, it's the only honest read of the landscape). Generic "
        "competitive frameworks are worthless. You speak with the blunt confidence "
        "of an analyst who has told operators their competitive read was wrong, "
        "to their face, before they burned a quarter on the wrong fight."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the competitor or competitive set")
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

        return f"""Deliver a competitive intelligence report on:
"{user_input}"

{context}

Using the real-time intelligence above, deliver competitive intelligence.

## 1. COMPETITIVE LANDSCAPE — RIGHT NOW

What the cultural conversation reveals about the competitive set today:

- **Who's Loudest**: Which brand in this space has the most cultural velocity right now? What's driving their presence? Is it earned or manufactured?
- **Who's Gaining**: Which competitor is accelerating — gaining share of cultural conversation? What signals indicate this is sustainable vs. a spike?
- **Who's Fading**: Which competitor is losing cultural relevance? What does their declining velocity or density tell you about their trajectory?
- **The Surprise Player**: Is there an unexpected brand or entrant showing up in this category's cultural conversation?

End with: "Current leader: [brand] — but [one sentence on vulnerability]"

## 2. TERRITORY MAP

What each competitor owns culturally — their claimed and contested spaces:

For each major competitor identified in the data:
- **Claimed Territory**: What cultural conversation do they dominate? What do people associate them with?
- **Emotional Position**: What feeling does this competitor own? Is it defensible?
- **Messaging Pattern**: What are they saying right now? What themes are they pushing?
- **Vulnerability**: Where is their cultural position weak, contested, or built on outdated assumptions?

## 3. THE TIRED MESSAGE

**Before writing:** read the competitive territory map above and identify the ONE positioning line every brand in this category is running this week. This is the line the audience is numb to — the line your operator must refuse to repeat.

- **The tired message**: The single predictable positioning line every competitor is recycling right now. Name it. Cite the evidence (which competitors, which signals).
- **Why it's dead**: What about the current cultural data says the audience has stopped responding to this line?
- **The category cliché to kill**: The broader cultural pattern this tired message fits into — so your operator knows the shape to avoid, not just the exact words.

## 4. THE UNCLAIMED FRAME

Where no one is winning — unclaimed cultural territory that your operator can weaponize as a positioning wedge, not just observe:

- **Unclaimed Conversations**: 2-3 high-velocity or high-scarcity cultural spaces that NO competitor in this set is claiming. For each, name the specific positioning frame the operator could plant a flag in (not just "wellness" — "the anti-wellness backlash that the data shows is replacing it").
- **Misaligned Positions**: Where competitors are saying one thing but the cultural conversation reveals the audience wants something else. This is a wedge the operator can press.
- **The Category Blind Spot**: What is every brand in this space ignoring that the data says matters to the audience? If this feels like a clever observation, push harder — it must feel inevitable once stated.

End with: "Biggest unclaimed territory: [one sentence — and it must be weaponizable, not just an observation]"

## 5. COMPETITIVE MOVES TO WATCH

What the data suggests competitors are about to do:

- **Positioning Shifts**: Any signals that a competitor is pivoting their cultural strategy? New themes, new audience targeting, new tone?
- **Potential Threats**: What moves could competitors make in the next 30 days that would reshape the landscape?
- **Alliance Signals**: Any evidence of competitive partnerships, category entries, or flanking moves in the data?

## 6. YOUR ATTACK BRIEF

If you're competing in this space, here's how to win:

- **Exploit This**: The single biggest competitor vulnerability you can attack right now — with specific evidence from the data
- **Avoid This**: The competitive battle you should NOT pick and why (strongest position, most resources, or cultural tailwind in their favor)
- **Own This**: The specific cultural territory you should claim while competitors are focused elsewhere
- **Timing**: How fast you need to move — is there a closing window or a stable opportunity?

End with: "The competitive move: [one sentence directive]"

## 7. INTELLIGENCE VERDICT

One paragraph. Who's actually winning this category culturally, who thinks they're winning but isn't, and what the data says about where this competitive landscape is heading. Give the CMO the 60-second intelligence brief.

End with: "Powered by Moodlight Competitive Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every insight must be built from what the real-time data shows about THESE specific competitors in THIS specific cultural moment. If you could have written this report without live data, it failed.
2. The Tired Message must be specific enough for the operator to write as a "do not use" rule. "Avoid generic wellness positioning" fails. "Avoid any line built on the frame 'meet you where you are,' the data shows three direct rivals ran it this month" passes.
3. The Unclaimed Frame must be WEAPONIZABLE as positioning, not just observed. A whitespace the operator can't plant a flag in is useless — if the operator would read it and say "so what?" rewrite.
4. Run the inevitability test on the Biggest Unclaimed Territory line: once stated, does the operator nod because it's obvious, or squint because it's clever? Obvious wins.
5. Run the substitution test on the Attack Brief: swap in a different operator in the same category. If the brief still works, it's too generic — rewrite until it only fits THIS operator's position.
6. Delete any sentence that could appear in a generic competitive framework from 2019. If the operator has seen this advice before, it's wasted ink.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "competitive_intelligence"
        return result
