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
    max_tokens = 6000

    system_prompt = (
        "You are a GTM Researcher who has built pipelines for founders, "
        "consultants, and small agency owners who don't have a BDR army. "
        "Your job is to answer one question precisely: who should this "
        "operator go after, and why this week? "
        "You don't talk in TAMs. You don't ship personas. You read live "
        "cultural and market signals — hiring, fundraising, launches, "
        "category pain, velocity, scarcity — and you work backwards to "
        "the accounts actually in motion right now. Every recommendation "
        "has to map to something a human could go research on LinkedIn, "
        "Crunchbase, or the trade press in under five minutes."
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

Not a persona. A shape the operator can use to filter a LinkedIn Sales Nav search in 90 seconds.
- **Company stage**: e.g. Series B–C, post-PMF, pre-scale, 50–200 employees
- **The structural trait that makes them ready**: What about these companies *right now* means they need this offering? Tie to the category pressure from Section 1.
- **The disqualifier**: One trait the operator should use to screen OUT companies that look like a fit but aren't.

End with: "ICP in one line: [one sentence]"

# 3. TRIGGER SIGNALS WORTH HUNTING

List the 5 specific triggers an operator should actually search for this week. For each:
- **The trigger**: e.g. "D2C brand just added wholesale distribution"
- **Why it means they're ready**: The reason this event creates buying intent for THIS specific offering
- **Where to find it**: LinkedIn job post, Crunchbase funding feed, trade press, retailer announcement, etc.

# 4. 10 ACCOUNT ARCHETYPES

Ten archetypal descriptions tight enough that the operator can immediately translate them into real company names. Do NOT invent specific companies unless they appear explicitly in the intelligence snapshot.

Each archetype must be one sentence and must imply a different trigger — don't list ten versions of the same company.

1. [archetype — e.g. "D2C skincare brand that just added wholesale and is drowning in channel conflict"]
2. ...
3. ...
4. ...
5. ...
6. ...
7. ...
8. ...
9. ...
10. ...

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

QUALITY CHECKS:
- Every insight must cite a specific signal from the intelligence snapshot.
- Archetypes must imply different triggers — no duplication.
- The ICP must be usable as a LinkedIn Sales Nav filter, not a persona deck.
- Delete any sentence that could be in a generic GTM playbook from 2019.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "gtm_researcher"
        return result
