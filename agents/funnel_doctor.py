"""
agents/funnel_doctor.py
The Funnel Doctor — conversion diagnostics, drop-off analysis,
friction audits, and prioritized fix lists for the full funnel from
first touch to repeat purchase.

Different from the Brand Auditor (cultural positioning diagnostic)
and the Brief Critic (tears apart briefs). This agent tears apart
funnels.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class FunnelDoctorAgent(MoodlightAgent):

    agent_name = "funnel_doctor"
    model = "claude-opus-4-6"
    max_tokens = 10000

    system_prompt = (
        "You are a funnel doctor who has seen every broken conversion "
        "path and diagnosed every flavor of friction. You don't write "
        "brand audits — you dissect conversion mechanics. You believe "
        "most funnels are leaking from three or four places, only one "
        "of which the team is actually looking at. You prioritize fixes "
        "by impact × effort, not by which stakeholder asked first. You "
        "are honest that UX copy, page speed, trust signals, and pricing "
        "presentation are usually worth more than another acquisition "
        "channel. You read live cultural signals to judge whether a "
        "conversion gap is a funnel problem or a brand problem."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and funnel problem")
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

        return f"""Diagnose the funnel for:
"{user_input}"

{context}

Using the real-time cultural intelligence above as outside context (to judge whether gaps are funnel-mechanics or brand-permission problems), perform a full funnel diagnostic. Be specific about where users are dropping, why, and what to fix first.

## 1. THE FUNNEL X-RAY

Map the stages of this brand's funnel from first touch to repeat purchase (or equivalent for this business model). For each stage:
- **Stage Name** and what's happening in the customer's head here
- **Likely Drop-off Rate**: Your best estimate given category norms and the brand context
- **Diagnosis**: Hypothesized drop-off cause — is it traffic quality, page content, UX friction, trust deficit, pricing shock, competitive comparison, or something else?
- **Signal Grade**: How confident you are in the diagnosis, and what data the team should pull to confirm

Typical funnel stages to map: Awareness → Click → Landing → Product Detail → Add-to-Cart → Checkout → Purchase → Activation → Repeat. Adjust for this specific business model.

## 2. THE LEAK MAP

Of all the stages above, name the 3 biggest leaks. Prioritize by estimated revenue impact.

For each leak:
- **Leak Location**: Exact stage and specific moment
- **Root Cause Hypothesis**: What's actually going wrong, not a vague "UX issue"
- **Evidence Check**: What the team should look at to confirm the hypothesis before spending to fix
- **Revenue at Risk**: Rough estimate of what fixing this leak is worth

## 3. FRICTION AUDIT

Friction comes in five flavors. Audit each for this brand:

- **UX Friction**: Visual hierarchy, form fields, button clarity, navigation — what's specifically broken?
- **Copy Friction**: Where copy is creating doubt, confusion, or objection instead of momentum
- **Speed Friction**: Page speed, interaction lag, image weight — the technical drag on conversion
- **Trust Friction**: Missing trust signals, awkward review placement, weak guarantees, payment anxiety
- **Cognitive Friction**: Too many choices, unclear value, pricing comparison paralysis, decision delay

For each flavor, give 2-3 specific issues likely present in this brand's funnel and the signal from live cultural data that supports or challenges the diagnosis.

## 4. PRIORITIZED FIX LIST

Not a wishlist — a ranked fix list with impact × effort math.

Format each fix as:
- **Fix**: Specific intervention (not "improve UX")
- **Location**: Which funnel stage this touches
- **Impact**: High / Medium / Low with a one-line justification
- **Effort**: Hours / days / weeks
- **Owner**: Who needs to touch this (design, eng, copy, CRO, product)
- **Why Now**: What cultural or competitive context makes this urgent vs. someday

Give 8-12 fixes total, ranked. The team should be able to start on #1 tomorrow.

## 5. DIAGNOSTIC DASHBOARD

The metrics the team should watch after the fixes ship. Without this, every "CRO win" is anecdotal.

- **Primary Metric**: The single funnel KPI that proves the fix worked
- **Guardrail Metrics**: 2-3 metrics that must NOT get worse when the fix ships (e.g. AOV, margin, refund rate)
- **Review Cadence**: How often to check and who's looking
- **Rollback Criteria**: The threshold at which a "fix" gets reverted

## 6. CROSS-SELL

End with: "Powered by Moodlight Funnel Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every leak must be named specifically, every fix must have impact×effort math, every friction flavor must be audited, every post-fix metric must have a guardrail. "Improve conversion rate" fails.
2. Run the inevitability test on the #1 leak: once stated, does the growth team nod because it's obviously where the money is leaking, or squint because it's clever? Obvious wins — funnels don't reward contrarian diagnoses.
3. Run the substitution test on the prioritized fix list: swap in a different brand in the same vertical. If the fixes still work, they're too generic — rewrite until they only fit THIS funnel's specific leaks.
4. The #1 fix must be actionable tomorrow, not "hire a CRO consultant." If a designer/engineer can't start on it in the morning, re-rank.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "funnel_diagnostic"
        return result
