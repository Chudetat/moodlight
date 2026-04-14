"""
agents/gtm_researcher.py
GTM Researcher — standalone account-hunting intelligence.

Answers "who should we go after?" by reading live cultural signals, hiring
patterns, category motion, and trigger events to surface 10 account archetypes
worth reaching out to this week. This is the top-of-funnel agent the rest of
The Growth Team operates on: before you optimize a funnel, you need accounts
in it. Before you write lifecycle email, you need to know who's going to
receive it.

Single-voice, tighter output than the full Outbound Discovery bundle.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class GTMResearcherAgent(MoodlightAgent):

    agent_name = "gtm_researcher"
    model = "claude-opus-4-6"
    max_tokens = 8000

    system_prompt = (
        "You are a GTM Researcher who has built target lists for founders, "
        "consultants, fractional executives, and boutique agency owners who "
        "don't have a BDR army and can't afford a wasted week of research. "
        "Your job is to answer one question precisely: who should this operator "
        "go after, and why this week?\n\n"
        "You do not talk in TAMs — the TAM is always bigger than you can hunt "
        "in a month and smaller than the seller's founder believes. You do not "
        "ship personas; personas are fiction a consultant sold a brand team in "
        "2014. You do not cite Predictable Revenue — it is sixteen years old "
        "and the outbound world has changed twice since. You do not produce "
        "account lists that look like every other vendor's in this category.\n\n"
        "You read live cultural, market, and category signals — hiring patterns, "
        "funding events, product launches, category pain, velocity, scarcity, "
        "commodity pressure, political risk, retailer consolidation — and you "
        "work backwards to the accounts actually in motion right now. Every "
        "recommendation must map to something a human could go research on "
        "LinkedIn, Crunchbase, the trade press, or a funding feed in under five "
        "minutes. You think like a private investigator, not a marketer.\n\n"
        "You speak with the blunt confidence of a researcher who has told "
        "operators their target list was wrong, to their face, before they "
        "wasted a month on it."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe what you sell and who you want to reach")
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

        return f"""An operator needs to know who to go after. Their situation:
"{user_input}"

{context}

KEY METRICS TO CONSIDER:
- VELOCITY: How fast a topic is accelerating (high = buyer pain is loud right now)
- LONGEVITY: How long a topic sustains interest (high = durable category motion)
- DENSITY: How saturated/crowded a topic is (high = category is crowded, harder sell)
- SCARCITY: How underserved a topic is (high = unmet buyer pain, open door)

You are delivering a GTM RESEARCH BRIEF. Not a pitch, not outbound copy — research. The deliverable is a surgical account-hunting map the operator can act on in under an hour. Every section must cite specific signals from the intelligence snapshot, not abstract category thinking.

# 1. THE CATEGORY STATE THIS WEEK

Read the live data and tell me what's actually happening in this operator's target category right now.
- **Category motion**: What's accelerating, what's saturating, what's emerging? Cite velocity + density + scarcity numbers where available.
- **The buyer pressure signal**: What is making buyers in this category *uncomfortable* right now — COGS pressure, fundraising climate, hiring slowdowns, category backlash, a competitive threat? Cite the signal.
- **The timing read**: Is this a week to push hard on outbound, or a week where buyers are distracted and it's a waste of motion? Be honest.

End with: "The category reality: [one sentence]"

# 2. THE IDEAL CUSTOMER PROFILE

**Before writing:** think through the *structural* traits that separate ready buyers from not-ready-yet buyers in this category. Stage alone is not a trait. Geography alone is not a trait. You are looking for the structural pressure point — the thing about the company that makes the pain unavoidable this quarter.

Not a persona. A shape the operator can use to filter a LinkedIn Sales Nav search in 90 seconds.

- **Company stage**: e.g. Series B–C, post-PMF, pre-scale, 50–200 employees, or whatever the structural reality demands — do not default to Series B if the data says otherwise
- **The structural trait that makes them ready**: What about these companies *right now* means they need this offering? Tie directly to the category pressure from Section 1. Be specific: "they just hired a VP of X who inherits a broken Y" is a structural trait; "growing fast" is not.
- **The unseen readiness signal**: One trait most operators in this space MISS that the intelligence snapshot reveals as predictive of buying intent.
- **The disqualifier**: One trait the operator should use to screen OUT companies that look like a fit but aren't. Be specific enough to write as a negative filter.

End with: "ICP in one line: [one sentence, readable as a Sales Nav filter string]"

# 3. TRIGGER SIGNALS WORTH HUNTING

List the 5 specific triggers an operator should actually search for this week. For each:
- **The trigger**: e.g. "D2C brand just added wholesale distribution"
- **Why it means they're ready**: The reason this event creates buying intent for THIS specific offering
- **Where to find it**: LinkedIn job post, Crunchbase funding feed, trade press, retailer announcement, etc.

# 4. 10 ACCOUNT ARCHETYPES

**Before writing:** think through ten *distinct* trigger patterns. Each archetype must imply a DIFFERENT trigger — not ten versions of "companies that just raised a round." If two of your archetypes share a trigger, merge them and find a different one.

Do NOT invent real specific companies unless they appear explicitly in the intelligence snapshot. Give ten archetypal descriptions in this exact shape:

`N. [Company shape] + [Specific trigger event or structural pressure] → [The buying intent this creates]`

Example of the bar: "3. Series B D2C skincare brand that just added wholesale distribution → channel conflict is eating the Head of Growth's weekends, they urgently need a positioning story that lets DTC and retail coexist."

Operator must be able to take any archetype and translate it into a real company name in five minutes on LinkedIn Sales Nav or Crunchbase. If an archetype fails that test, it's too abstract. Rewrite.

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

# 5. THE CATEGORIES TO SKIP

One short list. Categories or account types that *look* like a fit for this offering but that the live data says are wrong for this week:
- **[Category/type]** — why the data says to skip (cite signal)

This saves the operator wasted cycles. Be specific, not "avoid enterprise." Name the pattern.

# 6. THE RESEARCH HANDOFF

One paragraph addressed directly to the operator. Tell them:
- Which of the 10 archetypes to prioritize in the first hour of research
- Which trigger signal to monitor first
- What tool/query/search they should set up to surface these accounts continuously
- What NOT to waste time on

End with: "Powered by Moodlight GTM Research™"

QUALITY CHECKS — read before you finalize:
1. Every insight must cite a specific signal (number, brand, topic, velocity/density/scarcity value, headline) from the intelligence snapshot. Unsubstantiated category wisdom is filler.
2. All 10 archetypes must imply DIFFERENT triggers. Scan the list — if any two share a trigger shape, merge and find a tenth.
3. The ICP must read as a usable LinkedIn Sales Nav filter in one line. If it reads like a persona deck, rewrite.
4. The ICP disqualifier must be specific enough to use as a negative filter, not a vibe.
5. The categories-to-skip list must name the pattern, not the category. "Avoid enterprise" fails. "Avoid CPG brands whose parent-co just announced a restructure" passes.
6. Delete any sentence that could be in a generic GTM playbook from 2019. If an operator has seen this advice before, it's wasted ink.
7. The research handoff paragraph must tell the operator EXACTLY what to do in the next hour — not a general framework.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "gtm_researcher"
        return result
