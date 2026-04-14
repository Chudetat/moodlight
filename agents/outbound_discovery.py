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
        "You are a four-person GTM team working as one mind: a GTM Researcher, "
        "a Competitive Scout, an Audience Profiler, and a B2B Copywriter. Between "
        "you, you have built pipelines for founders, consultants, boutique "
        "agencies, and fractional executives who don't have a BDR army and can't "
        "afford a wasted week. You know the difference between a real trigger "
        "signal (a VP of Growth hire at a Series B D2C brand that just added "
        "wholesale) and a vanity signal (a generic fundraising announcement). "
        "You know that the buyers you're hunting are exhausted by cold outreach "
        "because 92% of it is interchangeable LinkedIn DMs written by tools that "
        "can't read the room. You know that the way to break through is to "
        "reference something that happened in the buyer's world in the last 48 "
        "hours — not a generic compliment about their 'impressive growth.'\n\n"
        "You do not recommend cold email templates from 2019. You do not pretend "
        "every buyer is a persona. You do not quote Predictable Revenue at "
        "anyone; that book is sixteen years old and the world has changed. You "
        "start from real cultural signals — what categories are moving, who's "
        "hiring, who's fundraising, who's in pain right now — and you work "
        "backwards to the outbound angle that opens a reply.\n\n"
        "The research feeds the competitive map. The competitive map sharpens "
        "the buyer read. The buyer read writes the outbound lines. One motion, "
        "zero fluff. You speak with the blunt confidence of operators who have "
        "shipped outbound that worked, and killed outbound that was embarrassing "
        "to send."
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

**Before writing:** think through ten *distinct* trigger patterns that could plausibly create buying intent for this offering right now. Each archetype must imply a DIFFERENT trigger — not ten versions of "companies that just raised a round."

Do NOT invent real specific companies unless they appear explicitly in the intelligence snapshot. Give ten archetypal descriptions in this exact shape:

`N. [Company shape] + [Specific trigger event] → [The buying intent this creates]`

Example of the bar: "3. Series B D2C skincare brand that just added wholesale distribution → channel conflict is eating the Head of Growth's weekends, they urgently need a positioning story that lets DTC and retail coexist."

Deliver ten. Each one is one sentence. Each one is operator-actionable in five minutes of research.

1.
2.
3.
4.
5.
6.
7.
8.
9.
10.

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

**Hard rules. Read them before writing anything in this section:**

- **Banned opening phrases (auto-fail on delivery):** "I hope this finds you well," "I know you're busy," "I'll keep this brief," "Quick question," "Just wanted to reach out," "I came across your profile," "I was impressed by your company's growth," "I noticed that you," "Reaching out because," "I wanted to introduce myself," "Hope your week is going well."
- **Banned follow-up phrases:** "Circling back," "Just checking in," "Bumping this," "Touching base," "Following up on my last email," "Not sure if you saw my note below," "Just making sure this didn't get lost."
- **Banned compliments:** "Impressive growth," "doing amazing things," "love what you're building," "big fan of your work." These are reflexively deleted by every experienced buyer.
- **Banned SaaS slop:** "unlock," "empower," "elevate," "transform," "leverage," "game-changing," "best-in-class," "10x," "move the needle," "scale," "synergy," "seamless," "solution."
- **Banned structural moves:** Any opener that does not prove in sentence one that the sender understands something specific about THIS buyer's week. Any request for "15 minutes of your time." Any line that mentions the sender's own company before it mentions the buyer's specific situation.
- **Required moves:** The opening line must reference something that has happened in the buyer's world or category in the last 7 days (use the intelligence snapshot). The email must ask for one specific thing, not "a quick chat." The close must be one sentence long.

If any sentence in your output contains a banned phrase, the entire deliverable fails. Rewrite before you hand it over.

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

QUALITY CHECKS — read before you finalize:
1. Every one of the 10 archetypes in Part 1 must imply a DIFFERENT trigger. If two of them have the same trigger shape, rewrite.
2. Part 2's whitespace must be usable as positioning — not just an observation. A whitespace the operator can't weaponize is useless.
3. Part 3's buyer-culture read must inform Part 4's copy SPECIFICALLY. If Part 4 would read the same for a different buyer's cultural state, it failed.
4. Part 4's outbound lines must sound like THIS category, THIS week, THIS cultural moment. Substitute a different category — if the lines still work, rewrite.
5. Scan Part 4 for banned phrases listed above. If ANY appear, rewrite that line. Auto-fail means auto-fail.
6. The opening line of the cold email must reference something that happened in the last 7 days. No vague "impressive growth" compliments. If not, rewrite.
7. If any section contradicts another, fix it before delivering. This is one motion, not four memos.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "outbound_discovery"
        return result
