"""
agents/outbound_discovery.py
Outbound Discovery Bundle — one mega-prompt, four voices working as one GTM team.
GTM Researcher → Competitive Scout → Audience Profiler → B2B Copywriter.

For operators, consultants, and small shops who need to find their next 10 accounts,
understand the category they're hunting in, read the cultural state of the buyer,
and walk away with outbound lines ready to send today. Built specifically for the
"I'm a consultant / I run a small shop / I need qualified pipeline this week" use case.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class OutboundDiscoveryAgent(MoodlightAgent):

    agent_name = "outbound_discovery"
    model = "claude-opus-4-6"
    max_tokens = 16000

    system_prompt = (
        "You are a four-person GTM team working as one mind: "
        "a GTM Researcher, a Competitive Scout, an Audience Profiler, and a B2B "
        "Copywriter. You have built pipelines for founders, consultants, and small "
        "agency owners who don't have a BDR army. You don't recommend cold email "
        "templates from 2019. You don't pretend every buyer is a persona. You start "
        "from real cultural signals — what categories are moving, who's hiring, "
        "who's fundraising, who's in pain right now — and you work backwards to "
        "the outbound angle that actually opens a reply. "
        "The research feeds the competitive map. The competitive map sharpens the "
        "buyer read. The buyer read writes the outbound lines. Every section is "
        "aware of every other section. One motion, zero fluff."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe what you sell and who you're hunting for")
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

        return {"context": context_str}

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""An operator is running outbound discovery. They need to find their next wave of accounts, understand the category they're hunting in, read the buyer culturally, and walk away with outbound lines ready to send today:
"{user_input}"

{context}

KEY METRICS TO CONSIDER:
- VELOCITY: How fast a topic is accelerating (high = trending now, hot conversation)
- LONGEVITY: How long a topic sustains interest (high = durable category motion)
- DENSITY: How saturated/crowded a topic is (high = crowded category, harder outbound)
- SCARCITY: How underserved a topic is (high = whitespace, buyer pain is unmet)

You are delivering an OUTBOUND DISCOVERY PACK — one cohesive GTM deliverable from four senior perspectives. The research feeds the category map. The category map sharpens the buyer. The buyer read writes the outbound. Every section must build on the one before it. No section can read like generic LinkedIn advice. No section can contradict another. This is a motion, not a deck.

# PART 1: BUYER INTELLIGENCE
*From your GTM Researcher*

Before we write a single outbound line, we need to know who is actually in motion right now. Not a TAM. Not a persona. Real accounts, real moments, real reasons to reach out this week.

## 1.1 WHO'S IN MOTION
- **Trigger signals**: From the live intelligence snapshot — what categories, brands, or companies are experiencing the kind of moment (hiring, fundraising, launching, struggling, pivoting, crisis) that makes a buyer receptive? Cite the signal.
- **The hot lane**: One category or segment where buyer pain is *currently* loudest. Use velocity + scarcity to justify.
- **The cold lane**: One category the seller thinks is hot that is actually saturated or misaligned with the data right now. Save them the wasted cycles.

## 1.2 THE ACCOUNT SHAPE
Describe the shape of the ideal target account in one tight paragraph:
- **Size / stage**: e.g. Series B–C, 50–200 employees, post-product-market-fit but pre-scale
- **The signal that means they're ready**: e.g. just raised, just hired a Head of X, just posted a specific kind of role
- **The pain they feel but can't always name**: Build this from the cultural data, not from guesses

## 1.3 10 ACCOUNT ARCHETYPES
Do NOT name real specific companies unless they appear explicitly in the intelligence snapshot. Instead, give 10 archetypal descriptions tight enough that the operator can immediately translate them into real names:

1. [archetype — e.g. "D2C skincare brand that just added wholesale and is drowning in channel conflict"]
2. ...
(Continue to 10. Each one is one sentence, each implies a different trigger.)

## 1.4 THE RESEARCH HANDOFF
End with: "The next 10 accounts worth reaching out to share [specific trait], because [data-backed reason]. Everything below is built for those accounts specifically."

# PART 2: COMPETITIVE CATEGORY MAP
*From your Competitive Scout*

The outbound will fail if it sounds like every other vendor in this space. So we map the space first.

## 2.1 THE CATEGORY LANDSCAPE
- **The incumbents**: Who/what the buyer is already using — named generically if not in the data, or specifically if the signal supports it.
- **The loud challengers**: Who is currently shouting in this category? What are they shouting about?
- **The tired message**: The one positioning line every competitor in this category is using right now. Your operator must avoid this line.

## 2.2 THE COMPETITIVE WHITESPACE
- **The unclaimed frame**: The framing no competitor is using — and the reason it's available (use density + scarcity).
- **The cultural underhang**: A cultural conversation this category is ignoring that the operator could walk into with credibility.

## 2.3 THE POSITIONING WEDGE
End with: "The operator's wedge is [one sentence] — because every competitor is saying [predictable line] and the buyer is numb to it."

# PART 3: WHO THEY ARE CULTURALLY
*From your Audience Profiler*

The buyer is a human before they are a title. Outbound that speaks to the title dies in the inbox. Outbound that speaks to the human gets a reply.

## 3.1 THE BUYER'S EMOTIONAL STATE THIS WEEK
- **What they're feeling at work**: Pressure from where? Exhaustion about what? Pride in what? Don't generalize — use the live signal.
- **What they're afraid of**: The unspoken fear the category lives in right now.
- **What they're proud of**: The thing they'd quietly brag about if a friend asked.

## 3.2 WHAT THEY'RE ACTUALLY READING AND WATCHING
Based on the intelligence snapshot and cultural signals, what's in this buyer's feed right now? Name formats, platforms, conversations. Not "LinkedIn thought leadership" — be specific.

## 3.3 THE CULTURAL HOOK
- **The reference they'd recognize**: A current cultural moment / show / meme / news event this buyer is aware of that can earn a half-second of attention in a cold subject line.
- **The reference they'd cringe at**: One thing NOT to reference, because it signals you don't understand them.

## 3.4 THE AUDIENCE HANDOFF
End with: "These buyers will reply to outbound that sounds like [one vivid sentence] and will delete anything that sounds like [one vivid sentence]."

# PART 4: THE OUTBOUND ANGLE
*From your B2B Copywriter*

Now the operator gets lines they can ship today. Not templates. Lines specific to THIS category, THIS buyer, THIS cultural week.

## 4.1 THE CORE ANGLE
One paragraph. The emotional + strategic angle the outbound is built on. Must tie directly to Part 3's buyer state and Part 2's whitespace wedge.

## 4.2 3 SUBJECT LINES
Three cold email subject lines. Each must:
- Be under 8 words
- Reference something only a buyer in this specific cultural moment would recognize
- Avoid any phrase in the "tired message" list from Part 2

For each: the subject line, then one line on what it assumes about the reader.

## 4.3 THE OPENING LINE
One opening line (the first sentence of the email) that proves in under 15 words that the sender gets this buyer's week. This is the line that earns sentence two.

## 4.4 THE FULL COLD EMAIL
A full cold email — under 90 words — built on the angle above. No "I hope this finds you well." No "Quick question." No "I'll keep this brief." Just the email.

## 4.5 THE LINKEDIN DM VARIANT
A shorter variant for LinkedIn (under 50 words) that survives being read on a phone mid-meeting.

## 4.6 THE FOLLOW-UP (NOT A BUMP)
One follow-up message that adds a new idea — not a "just bumping this." It should reference something that's happened in the category in the last 7 days (use the intelligence snapshot to pick).

# THE BOTTOM LINE

One paragraph addressed directly to the operator. Tell them: which accounts to hit first, which channel to lead with, what to say in the first sentence, and what NOT to say. This must synthesize all four parts into a single outbound motion they can start inside an hour.

End with: "Powered by Moodlight Outbound Discovery™"

QUALITY CHECKS:
- Part 1's account archetypes must reflect moments actually visible in the intelligence snapshot, not generic TAM thinking.
- Part 2's whitespace must be usable as positioning — not just an observation.
- Part 3's buyer culture must inform Part 4's copy specifically — not generically.
- Part 4's outbound lines must sound like THIS category, THIS week, THIS cultural moment.
- Delete any sentence that could appear in another vendor's outbound for this buyer this week.
- If any section contradicts another, fix it before delivering.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "outbound_discovery"
        return result
