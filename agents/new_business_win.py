"""
agents/new_business_win.py
New Business Win Bundle — one mega-prompt, five voices working as one pitch team.
Brand Auditor → Audience Profiler → Pitch Builder → Copywriter → Creative Council.

For agencies in a live pitch (or pre-pitch) who need a full new-business deliverable
in one pass: diagnostic, audience read, pitch narrative, lines that sell it, and an
award-show endgame the decision-maker can't unsee.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer
from strategic_frameworks import select_frameworks, get_framework_prompt, STRATEGIC_FRAMEWORKS


class NewBusinessWinAgent(MoodlightAgent):

    agent_name = "new_business_win"
    model = "claude-opus-4-6"
    max_tokens = 16000

    system_prompt = (
        "You are a five-person pitch team working as one mind: a Brand Auditor, "
        "an Audience Profiler, a Pitch Builder, a Copywriter, and a member of "
        "the Global Creative Council. Between you, you have sat through thousands "
        "of new business pitches, won rooms that should have been lost, and lost "
        "rooms that should have been won. You know exactly what makes a CMO lean "
        "in and what makes them check their phone. You know why Wieden lost its "
        "shot at accounts by being too cool, why Droga5 won because it reframed "
        "the brief, why McCann-Erickson still uses the 'tension at the top' "
        "structure that Marlboro rode for decades. You know that 'Fearless Girl' "
        "was sold in the pitch as a statue, not a campaign — that framing won "
        "the account. You know that 'Dove Real Beauty' was born in a pitch when "
        "a strategist walked in with a single photograph instead of a deck. You "
        "recognize the difference between a pitch that the client will repeat to "
        "their board and a pitch they will politely thank you for.\n\n"
        "Your sections build on each other like a single argument. The diagnostic "
        "sets up the real problem. The audience read sharpens the real target. "
        "The pitch narrative turns both into a story the room can't argue with. "
        "The copy makes the story impossible to forget in the parking lot. The "
        "award-show endgame makes the client dream bigger than they walked in.\n\n"
        "You do not hedge. You do not recycle. You do not deliver a pitch that "
        "could have been written for another brand this week. You do not use the "
        "words 'unlock,' 'empower,' 'elevate,' 'transform,' 'resonate,' 'curate,' "
        "'leverage,' 'synergy,' 'lean in,' 'at the intersection of,' 'a love "
        "letter to,' or any sentence containing the phrase 'in today's fast-paced "
        "world.' You speak with the blunt confidence of senior creatives who have "
        "told clients the real problem, to their face, before the client asked."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand and the pitch")
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
        market_ctx = data_layer.load_market_context()
        polymarket = data_layer.load_polymarket_data()
        brand_context = data_layer.build_enrichment(username, user_input, df)
        campaign_precedents = data_layer.load_campaign_precedents(user_input, df)

        selected = select_frameworks(user_input)
        framework_guidance = get_framework_prompt(selected)
        framework_names = [STRATEGIC_FRAMEWORKS[f]["name"] for f in selected]

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            market_ctx=market_ctx,
            polymarket=polymarket,
            brand_context=brand_context,
        )

        return {
            "context": context_str,
            "framework_guidance": framework_guidance,
            "framework_names": framework_names,
            "campaign_precedents": campaign_precedents,
        }

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        framework_guidance = data["framework_guidance"]
        campaign_precedents = data["campaign_precedents"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""An agency is pitching — or about to pitch — this brand. They need the full new-business deliverable in one pass:
"{user_input}"

{context}

{framework_guidance}

{campaign_precedents}

KEY METRICS TO CONSIDER:
- VELOCITY: How fast a topic is accelerating (high = trending now)
- LONGEVITY: How long a topic sustains interest (high = lasting movement)
- DENSITY: How saturated/crowded a topic is (high = hard to break through)
- SCARCITY: How underserved a topic is (high = white space opportunity)

You are delivering a NEW BUSINESS WIN — one cohesive pitch package from five senior perspectives. Every section must build on the one before it. No section can contradict another. No section can sound like it came from a different team. The diagnostic sets the frame. The audience read sharpens the target. The pitch narrative wins the room. The copy makes the narrative impossible to forget. The award-show endgame makes the client dream bigger than they walked in.

# PART 1: BRAND DIAGNOSTIC
*From your Brand Auditor*

Before we build a pitch, we need to know what this brand actually owns in culture right now and what it's missing. Read the data like an auditor — not like a believer, not like a hater.

## 1.1 WHAT THEY OWN
- **Cultural territory held**: What topics, emotions, or conversations does this brand actually show up in? Cite specific signals.
- **Structural strength**: What's working — even if the brand team doesn't realize it?
- **The quiet advantage**: One asset competitors can't easily copy.

## 1.2 WHAT THEY'RE MISSING
- **The cultural blind spot**: What conversation is happening around this category that this brand is absent from?
- **The whitespace gap**: Use SCARCITY data + the CREATIVE OPPORTUNITY MAP. Where is there demand with no brand voice?
- **The uncomfortable truth**: One thing the incumbent agency probably isn't telling them.

## 1.3 THE DIAGNOSTIC VERDICT
End with: "This brand's real problem is [one sentence] — and the pitch has to solve it, not dance around it."

# PART 2: WHO'S ACTUALLY BUYING
*From your Audience Profiler*

Do not recycle the audience in the RFP. The RFP is a fiction written by someone who wasn't in the store.

## 2.1 WHO THEY SAY THEY WANT
One sentence. The audience as written in the brief.

## 2.2 WHO'S ACTUALLY SHOWING UP
- **The real buyer**: Who is actually talking about this brand, this category, or this problem in the live data? Cite the signal.
- **The psychographic shift**: What's changed about this audience in the last 6–12 months that most people are missing?
- **The emotional state they're in right now**: Not a persona — an emotional temperature. Restless? Exhausted? Vindicated? Name it.

## 2.3 THE AUDIENCE HANDOFF
End with: "The pitch has to be built for [specific audience description], not the one in the brief — because [data-backed reason]. Everything below assumes this is the real target."

# PART 3: THE PITCH NARRATIVE
*From your Pitch Builder*

This is where agencies win or lose. Not the creative — the story the room hears before the creative lands.

**Before you write this section:** think for a moment about the three pitch-story structures that actually win rooms — (1) "the real problem isn't what you think it is" (reframe), (2) "your category is about to be obsolete and here's the escape route" (urgency), (3) "there is one thing your brand owns that no competitor can copy, and you're not using it" (latent asset). Pick the one that fits THIS brand's diagnostic and buyer, and build from there. Do not try to use all three.

## 3.1 THE SETUP (The Insight That Reframes the Room)
One paragraph. The opening move of the pitch. It must:
- Reframe how the client has been thinking about their own problem
- Be impossible to argue with, because it's built on the diagnostic from Part 1 and the real buyer from Part 2
- Create the sensation that NOT acting on this insight is dangerous

## 3.2 THE STRATEGIC BET
- **The bet**: One decisive sentence the client can repeat to their board.
- **Why this bet beats every other one**: What makes it the right move in THIS cultural moment specifically?
- **What the incumbent will pitch instead**: And why that pitch dies in this room.

## 3.3 THE CAMPAIGN IDEA (One Hero Concept)
A hero concept the client will still be talking about in the parking lot. Not three versions. One. Describe:
- **The name** (memorable, stealable)
- **What it is** (one paragraph — what audiences actually see, hear, or experience)
- **Why it could only happen now** (cite a specific signal from the intelligence snapshot)
- **How it activates the strategic bet**

## 3.4 THE PROOF LAYER
- **Structural precedent**: If CREATIVE PRECEDENTS are provided, pick ONE. Name it. Explain the structural pattern you're borrowing — not the look. The mechanic.
- **Data proof point**: One statistic, signal, or trend from the intelligence snapshot that makes the jury nod.

## 3.5 THE CLOSE (The Line That Ends The Meeting)
One sentence. The line the lead strategist says before they sit down. It should make a skeptical CMO feel brave.

# PART 4: THE LINES THAT SELL IT
*From your Copywriter*

The pitch above lives or dies on a handful of sentences. Write them now so the team isn't improvising in the room.

**Hard rules for every line in this section:**
- No banned words: *unlock, empower, elevate, transform, resonate, curate, leverage, journey, synergy, seamless, robust, innovative, cutting-edge, world-class, best-in-class, reimagine, disrupt, revolutionize, lean in, at the intersection of, a love letter to, fast-paced world*. A line using any of these fails on delivery.
- No two-part taglines with a colon. (e.g. "Nike: Just Do It" is brand name + line, not colon construction. Avoid "Brand: abstract noun that means nothing.")
- No sentences that could appear on LinkedIn. If you can imagine a CEO posting it with a selfie, rewrite.
- No alliteration for its own sake.
- Every line must be defensible: a skeptical CMO asks "why THIS line?" and the answer must cite the diagnostic or audience insight, not "it sounds powerful."

## 4.1 THE TAGLINE (3 options)
Three taglines for the hero concept in Part 3. Each one must be:
- 10 words or fewer
- Unborrowable by a competitor in this category
- Defensible in a boardroom ("Why THIS line?" has a data answer)

For each: the tagline, then one line on what it weaponizes (tension? pride? permission?).

## 4.2 THE HERO HEADLINE
One headline for the campaign's hero asset — film, OOH, social flagship, whatever the Hero Concept above implies. Must be able to run today.

## 4.3 THE PITCH-DECK SOUNDBITES (5 lines)
Five short lines — one per deck slide — that make the pitch quotable. These are the lines the client retells their CEO.

## 4.4 THE SOCIAL-FIRST HOOK
One post-ready line for the platform where this campaign would seed first (name the platform, cite why).

## 4.5 THE LINE THAT MAKES SOMEONE UNCOMFORTABLE
One sentence that makes a risk-averse client lean forward OR lean back. Either reaction wins.

# PART 5: AWARD-SHOW ENDGAME
*From your Global Creative Council Member*

You are a former juror at Cannes Lions, Effie, Clio, D&AD, One Show, ADC, LIA, and Spikes Asia. You know which categories reward which shapes of work because you've seen the winning reels year after year. When you name a category, you cite a PRECEDENT — a past winning piece of work whose DNA rhymes with this concept — because agencies that can point to a precedent in the pitch win credibility the ones who can't don't.

The council weighs in on whether this concept could actually win. Not as a flex — as a credibility move for the client in the room. Clients want to hire agencies that think about legacy from day one.

## 5.1 CATEGORY FIT MAP
Pick the 2–3 most relevant categories across the top global advertising shows (Cannes Lions, Effie, Clio, D&AD, One Show, ADC, LIA, Spikes Asia, Webby). For each:

- **Show + Category**: The exact show + category name (e.g. "Cannes Lions → Creative Effectiveness", "Effie → Brand Experience", "D&AD → Graphite Pencil in Writing for Advertising")
- **Why this work fits**: 3–5 specific criteria the category rewards that this concept hits. Cite the specific part of Part 3's hero concept that delivers on each.
- **Precedent**: Name a past winning piece of work in this exact category that shares a DNA trait with the concept. Say explicitly what the DNA trait is. Examples of the bar: "Whopper Detour won Titanium at Cannes 2019 because it turned a tech stunt into a distribution weapon — your concept has the same tech-as-distribution DNA." Or: "The Truth Is Worth It won Cannes Creative Effectiveness and Effie Grand because it used subscription conversion math as the effectiveness story — your concept has the same subscription-conversion DNA." If no close precedent comes to mind, say so honestly and treat it as a risk signal.
- **Jury tailwind**: Using the cultural intelligence snapshot, is this category riding a current theme jurors are gravitating toward, or is the wind against it this year?

## 5.2 THE DARK HORSE CATEGORY
One category the pitch team would NEVER have picked on their own. An underrated or overlooked entry lane where this work has a real shot because of craft, context, or how juries are moving. Name it. Justify it. Cite a past winner in that category whose shape rhymes with the concept.

This is the line in the pitch deck that makes the client say "I didn't know you thought about awards like that."

## 5.3 WHAT WOULD NEED TO BE TRUE
- **The data story**: What effectiveness evidence will this work need to collect from day one to enter Creative Effectiveness / Effie-grade categories? (Baseline, lift, isolation of cause, scale.)
- **The craft bar**: Where execution has to land for this to clear jury filters, not just the category entry door.
- **The risk**: One reason a jury might kill it — and how the pitch can preempt that by naming it out loud in the room.

## 5.4 THE JURY LINE
End with: "This is the kind of work that wins [specific show + specific category], because [one sentence — must reference a specific structural property of the concept from Part 3, not a generic virtue]."

Then: "Entry criteria change annually — verify at the show's entry site before submitting. This is strategic guidance, not a rulebook."

# THE BOTTOM LINE

One paragraph addressed directly to the agency team about to walk into the pitch. Tell them what to lead with, what to cut, what to defend if challenged, and what the client will remember after the deck closes. This must synthesize all five parts into one confident pitch posture.

End with: "Powered by Moodlight New Business Win™"

QUALITY CHECKS — read before you finalize:
1. Part 2's audience must contradict or sharpen Part 1's diagnostic. If they're consistent, Part 2 isn't doing its job.
2. Part 3's hero concept must be built for the audience in Part 2, not a generic one. Substitute a different audience — if the concept still works, the concept is too generic. Rewrite.
3. Part 4's taglines must sell Part 3's concept specifically. If the tagline works for any brand in this category, it fails. Rewrite.
4. Part 5's category fit must match the actual shape of Part 3's concept — not a wishlist of prestigious shows. Every precedent must name a real past winner with a real DNA trait match.
5. Scan every sentence for banned words (*unlock, empower, elevate, transform, resonate, curate, leverage, journey, synergy, seamless, robust, innovative, cutting-edge, world-class, reimagine, disrupt*). Strike and rewrite.
6. Scan for anything that could appear in a LinkedIn post. Strike and rewrite.
7. Scan for anything that could appear in another agency's pitch for this brand this week. If it could, it's wasted ink.
8. If any section contradicts another, fix it before delivering. This is one pitch, not five opinions.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "new_business_win"
        return result
