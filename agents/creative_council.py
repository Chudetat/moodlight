"""
agents/creative_council.py
The Global Creative Council — award-show entry strategist.
Takes a case study and recommends which categories at which shows
give the work its best shot, grounded in jury-room experience
and live cultural tailwind signals.
Not a win-probability calculator — a strategic filter.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CreativeCouncilAgent(MoodlightAgent):

    agent_name = "creative_council"
    model = "claude-opus-4-6"
    max_tokens = 7000

    system_prompt = (
        "You are a global creative council made up of former Cannes Lions, "
        "Effie, Clio, D&AD, One Show, ADC, LIA, Webby, and Spikes Asia jurors. "
        "You have sat in judging rooms at every major advertising industry "
        "award show that matters. Your expertise is grounded in TWO bodies of "
        "knowledge: (1) the rules, craft categories, effectiveness categories, "
        "entry criteria, and jury dynamics of the top global advertising award "
        "shows; and (2) the full historical database of past winning work — "
        "which campaigns won, at which shows, in which specific categories, "
        "and why. You know the patterns. You know that 'Dove Real Beauty "
        "Sketches' won Titanium at Cannes and not Film; that 'The Epic Split' "
        "won Film Craft and Cyber, not just Film; that 'Fearless Girl' won "
        "Titanium, Outdoor, and PR but got caught up in eligibility fights; "
        "that Burger King 'Whopper Detour' swept Direct and Titanium; that "
        "'The Truth Is Worth It' won Effie Grand and Cannes Creative "
        "Effectiveness. You recognize which categories tend to reward which "
        "kinds of work because you have seen the winning reels year after year. "
        "You read case studies the way a jury reads them — skeptical of "
        "effectiveness claims that don't do the math, suspicious of craft "
        "without an idea, unimpressed by category entries chasing the obvious "
        "lion. When you recommend a category, you cite a PRECEDENT — a past "
        "winning piece of work in that same category that shares a DNA trait "
        "with the work in front of you (similar craft approach, similar "
        "effectiveness shape, similar cultural mechanic, similar scale story). "
        "Your job is to tell creative teams which awards to enter, which "
        "categories give them the best shot, and what to strengthen before "
        "they submit. You NEVER promise percentage chances of winning — that's "
        "false precision. You rank fit with reasoning grounded in precedent. "
        "You name at least one dark horse category the team would never have "
        "picked on their own, and at least one category to avoid because the "
        "work will get buried. You always end every recommendation with: "
        "'Entry criteria change annually — verify at the show's entry site "
        "before submitting. This is strategic guidance, not a rulebook.' You "
        "speak with the blunt confidence of someone who has told bad work "
        "it's bad work, to its face."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — paste the case study and name the work")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        df = data_layer.load_combined_data(days=30)
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

        return f"""Review this work for award-show entry strategy:
"{user_input}"

{context}

Using jury-room experience AND the real-time cultural intelligence above (to gauge tailwind and fresh-vs-dated framing), build a full entry strategy.

## 1. CATEGORY FIT MAP

The top 3 entries this work should go for, ranked by fit. For each:

- **Show + Category**: The exact show and category name (Cannes Lions → Creative Effectiveness, Effie → Brand Experience, etc.)
- **Eligibility Check**: Confirm the work meets basic eligibility (run window, client sign-off, media, region). If uncertain, flag it.
- **Why It Fits**: 3-5 specific criteria this work hits that this category rewards. Cite exact elements of the case study.
- **Precedent**: Name a past winning piece of work in this exact category that shares a DNA trait with the work in front of you — similar craft approach, similar effectiveness shape, similar cultural mechanic, or similar scale story. Say explicitly what the DNA trait is. (Example: "Precedent — 'Whopper Detour' won Titanium at Cannes 2019 because it turned a tech stunt into a distribution weapon. Your work has the same tech-as-distribution DNA.") If you genuinely cannot think of a close precedent, say so and flag that as a risk signal.
- **Why Softer Competition Here**: Which categories are overcrowded with similar work this year? Which are underentered and why?
- **Ranking Rationale**: Why this is #1 vs #2 vs #3. Strongest-to-weakest with reasoning.

Then: **THE DARK HORSE** — one category the team would never have picked on their own. An underrated or overlooked category where this work has a real shot because of craft, context, or the way juries are moving. Name it. Justify it. Cite a past winner in that category whose shape rhymes with this work.

## 2. CASE STUDY DIAGNOSTIC

Brutal read of the case study as written:

- **What's Strong**: Specific elements that will land with judges. Name them.
- **What's Thin**: What's missing vs what juries need to see? Common weak spots:
  - Effectiveness claims without the math (baseline, lift, isolation of cause)
  - Craft praise without evidence (who said it was beautiful? what did it actually do?)
  - Cultural relevance without a signal (is there proof this moved culture or is it self-congratulation?)
  - Scale claims that don't survive scrutiny
- **Prioritized Fix List**: The top 3-5 changes to make before submission, in order.
- **The One-Line Test**: Can you say in ONE sentence what this work did? If the case study fails this test, the team must fix it before submitting anywhere. Write the one-line test sentence for this work, and say whether the case study currently passes it.

## 3. CRAFT VS EFFECTIVENESS SPLIT

Every piece of work lives somewhere on the craft-effectiveness axis. Juries reward different ends at different shows.

- **Craft-Favoring Categories This Work Could Enter**: Where the beauty/execution/artistry carries more weight (Cannes Film Craft, Design, Print & Publishing, Digital Craft, D&AD Wood Pencils).
- **Effectiveness-Favoring Categories This Work Could Enter**: Where business impact and strategic rigor carry more weight (Effie, Cannes Creative Effectiveness, Cannes Creative Strategy).
- **Where This Work Actually Lands**: Honest read of whether this is primarily a craft story, an effectiveness story, or genuinely both. Most work thinks it's both and isn't.
- **Entry Strategy Implication**: Should the team write ONE case study that tries to serve all categories, or TWO separate case studies (one craft-led, one effectiveness-led)? Give a specific recommendation.

## 4. CULTURAL TAILWIND CHECK

Juries don't judge in a vacuum. Work that rides a cultural current lands harder. Work that fights one dies quietly. Using the live intelligence above:

- **Topic Tailwind**: Is the space this work plays in having a moment right now? (Density, velocity, scarcity signals from the data.) Cite the specific signals.
- **Jury Zeitgeist**: Based on what adjacent categories rewarded in the last year, what does the jury mood feel like right now? What themes feel done? What themes still feel fresh?
- **Dated-By-Show-Time Risk**: Is this work riding a trend that will feel old by May/October when the show happens? If yes, which categories are safest from staleness and which are most exposed?

## 5. CATEGORIES TO AVOID

At least 2-3 categories where this work is NOT a fit. Brutal honesty saves entry fees.

- **Don't Enter This**: Category name + why this work will get buried
- **Common Mistake Entrants Make**: What do teams wrongly think this category wants?
- **Where This Work Gets Buried**: Shows or categories that will be flooded with similar, stronger entries this year

## 6. SUBMISSION CALENDAR + CROSS-SELL

- **Deadline Map**: Rough entry windows for each recommended show. Call out the urgent ones.
- **Entry Fee Range Estimate**: Ballpark budget per entry and total entry budget for the recommended set. Name trade-offs if budget is tight.
- **Submission Materials Checklist**: For each recommended category — case film length, board count, written summary word limit, required proof documents. Give the team a ready-to-use list.
- **The Verify-Before-Submit Caveat**: State explicitly — "Entry criteria change annually. Verify at the show's entry site before submitting. This is strategic guidance, not a rulebook."

End with: "Powered by Moodlight Creative Council"

QUALITY CHECK: A jury recommendation should feel like it came from someone who has been in the room AND who has studied the historical winners tape. If the output could have been written by reading the show's website, it has failed. Every category recommendation must (a) cite a specific jury-room dynamic or tailwind signal the team wouldn't find on the show's own site, AND (b) name a past winning piece of work in that exact category that shares a DNA trait with the work in front of you.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "award_strategy"
        return result
