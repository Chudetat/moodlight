"""
agents/copywriter.py
The Copywriter — takes strategy or brief output and writes actual headlines,
social posts, and ad copy tuned to the cultural moment. The last mile
from strategy to execution.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CopywriterAgent(MoodlightAgent):

    agent_name = "copywriter"
    model = "claude-opus-4-6"
    max_tokens = 10000

    system_prompt = (
        "You are a copywriter whose work has been stolen, screenshot, and shared "
        "more times than you can count. You have written lines that made a CMO lean "
        "forward and lines that cost an agency an account — you know the difference "
        "and you know why. You believe great copy doesn't explain, it detonates. "
        "You believe the best lines feel inevitable once written: Nike 'Just Do It' "
        "could not have been anything else, 'Think Small' was the only honest line "
        "Volkswagen could have led with in 1959, 'The Ultimate Driving Machine' made "
        "every other BMW line look like a brochure caption. That is the bar.\n\n"
        "You hate clichés, buzzwords, and anything that sounds like it was written "
        "by a committee that never met the audience. You refuse to use the words "
        "'unlock,' 'empower,' 'elevate,' 'transform,' 'resonate,' 'curate,' "
        "'leverage,' 'journey,' 'reimagine,' 'disrupt,' 'revolutionize,' 'seamless,' "
        "'innovative,' 'cutting-edge,' 'world-class,' 'best-in-class,' or any "
        "sentence containing the phrase 'in today's fast-paced world.' You refuse "
        "two-part colon taglines ('Brand: abstract noun that means nothing'). You "
        "refuse alliteration for its own sake. You refuse anything that could appear "
        "on a LinkedIn post with a selfie attached.\n\n"
        "Every line you write must pass two checks the client will run in the room: "
        "(1) could a competitor in this category ship this same line this week? If "
        "yes, it's dead. (2) Does this feel like the only right answer once read, "
        "or merely a clever attempt? If merely clever, it's dead. You write for the "
        "cultural moment the data is showing you right now — not the brief that was "
        "approved three weeks ago. You speak with the blunt confidence of a writer "
        "who has killed lines that would have embarrassed clients in public."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand, campaign, or provide a brief to write from")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        df = data_layer.load_combined_data(days=5)
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

        return f"""Write copy for this:
"{user_input}"

{context}

Using the real-time intelligence above, write copy that could only exist this week.

**Hard rules — read before writing ANY line below:**

- **Banned words (auto-fail on delivery):** *unlock, empower, elevate, transform, resonate, curate, leverage, journey, reimagine, disrupt, revolutionize, seamless, innovative, cutting-edge, world-class, best-in-class, robust, synergy, game-changing, 10x, at the intersection of, a love letter to.* If ANY line contains a banned word, the entire deliverable fails. Rewrite.
- **Banned structural moves:** No two-part colon taglines. No alliteration for its own sake. No sentences that could appear on a LinkedIn post with a selfie. No "timeless" copy — if it could have run last month, it's wrong.
- **The inevitability test:** Before you submit any line, ask: "could a competitor in this category ship this same line this week?" If yes, rewrite. And: "once stated, does this feel like the only right answer, or merely a clever attempt?" If merely clever, rewrite.
- **The defensibility rule:** A skeptical CMO will ask "why THIS line?" about any line in this output. Every line must have a data-backed answer — a signal, a tension, a mood from the intelligence snapshot. "It sounds powerful" is not an answer.

## 1. THE CULTURAL READ

Before writing a single line, identify the emotional and cultural territory:

- **The mood**: What is the dominant emotional frequency in the data right now? Are people anxious, defiant, hopeful, exhausted, restless? Name it precisely.
- **The tension**: What cultural contradiction or friction point is most relevant to this brand? Great copy lives in tension — between what people want and what they feel, between what brands say and what's true.
- **The language**: What words, phrases, or patterns are showing up in the data? What's the cultural vocabulary right now? Not to copy it — to understand the register your audience is speaking in.

End with: "Write in the key of: [one word or phrase that captures the tone]"

## 2. HEADLINES (10 options)

Write 10 headlines. Each one should:
- Be immediately understandable without context
- Create an emotional response in under 3 seconds
- Feel like it belongs to THIS cultural moment, not last month
- Be something a competitor could NOT also say

Organize them:

**Tension headlines** (3) — Built on a cultural contradiction
1.
2.
3.

**Provocation headlines** (3) — Challenge the audience or category
4.
5.
6.

**Empathy headlines** (2) — Meet the audience where they are emotionally
7.
8.

**Wildcard headlines** (2) — Break a rule, subvert expectations
9.
10.

For each headline, add a one-line note: [Why this works right now — cite a specific signal]

End with: "Lead with: [number] — it's the sharpest line for this moment because [reason]"

## 3. SOCIAL POSTS (6 posts)

Write 6 social media posts ready to deploy. Each should work as standalone content:

For each post:
- **Platform**: Where this works best (and why the data supports that platform)
- **The post**: Full copy, ready to publish. Include the voice, the hook, the CTA.
- **Cultural hook**: What current signal or moment this post latches onto
- **Character count**: Keep it real — Instagram vs. X vs. LinkedIn have different constraints

Mix the formats:
- 2 x short-form (X/threads style — punchy, under 280 characters)
- 2 x medium-form (Instagram/LinkedIn — 2-3 paragraphs, narrative)
- 2 x reactive (designed to respond to or ride a specific current cultural signal)

## 4. LONG-FORM CONCEPT (1 piece)

One piece of long-form copy — could be a manifesto, a brand letter, a landing page, or an open letter. 200-400 words.

- **Format**: What form this takes and why
- **The copy**: Write it in full. Not a summary. Not an outline. The actual words.
- **Why now**: What makes this piece urgent based on current signals

## 5. THE KILL LIST

Lines you should NEVER write for this brand right now:

- **5 clichés to avoid**: Category-specific phrases that are overused in the data (high density, zero impact)
- **The tone trap**: What voice or approach would feel tone-deaf given the current cultural mood?
- **The competitor line**: What is every other brand in this space already saying? Don't join them.

## 6. THE COPY BRIEF

For whoever takes this forward — the rules for all copy on this campaign:

- **Voice in 5 words**: [five words that define the tone]
- **The line you can't cross**: [where bold becomes reckless]
- **The test**: [how to know if a line is working — what reaction should it get?]
- **Reference track**: [one cultural artifact — song, show, meme, moment — that captures the energy]

End with: "Powered by Moodlight Creative Intelligence"

QUALITY CHECKS — read before you finalize:
1. Scan every line for banned words listed at the top. If ANY appear, strike and rewrite. Auto-fail means auto-fail.
2. Run the substitution test on every headline, post, and tagline: swap the brand for a direct competitor. If the line still works, it's too generic — rewrite until it only works for THIS brand in THIS cultural moment.
3. Run the inevitability test on the top 3 headlines: once stated, does each feel like the only right answer for this brand this week, or merely clever? If merely clever, rewrite.
4. Every line must cite a specific signal (mood, tension, language pattern, velocity/density/scarcity value) from the intelligence snapshot. Uncited lines fail.
5. Delete any line that could have been written last month. Timeless copy is the enemy — this work should have an expiration date because the culture will move.
6. The Kill List must name patterns specific enough to use as a negative filter, not vibes. "Avoid clichés" fails. "Avoid any line built on the word 'journey,' because the data shows 3 direct competitors ran it this quarter" passes.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "copywriting"
        return result
