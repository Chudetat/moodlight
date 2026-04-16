"""
agents/referral_architect.py
The Referral Architect — viral loop design, word-of-mouth mechanics,
advocacy programs, incentive structure, and share triggers.

Different from the Social Strategist (organic content on platforms)
and the Comms Planner (campaign channel plans). This agent engineers
the mechanics by which customers recruit other customers.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class ReferralArchitectAgent(MoodlightAgent):

    agent_name = "referral_architect"
    model = "claude-opus-4-6"
    max_tokens = 10000

    system_prompt = (
        "You are a referral architect who has designed viral loops that "
        "worked and watched dozens that didn't. You know that most "
        "referral programs fail because they're incentive structures "
        "bolted onto a product nobody is emotionally compelled to share. "
        "You design the loop first, the incentive second. You believe "
        "the best referral programs have a clear reason to share "
        "baked into the product moment — not a coupon duct-taped onto "
        "checkout. You read live cultural signals to judge whether "
        "this brand has earned enough cultural credit for customers to "
        "want to associate themselves with it publicly."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and advocacy goals")
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

        return f"""Design a referral and advocacy program for:
"{user_input}"

{context}

Using the real-time cultural intelligence above to judge whether this brand has earned the right to be shared publicly, design a referral program. Start with the psychology of why a customer would share, then build the loop around that moment.

## 1. THE ADVOCACY LANDSCAPE

Before designing a loop, diagnose whether this brand is actually advocacy-ready.

- **Cultural Permission**: Using the live data above, does this brand have enough cultural credibility for customers to want to associate with it publicly? Be honest.
- **Share Archetypes**: What kind of sharing actually happens in this category — private recommendation, public flex, identity signal, utility ping, deal sharing, or something else?
- **Why People Share in This Category**: The 2-3 dominant emotional drivers of sharing for this brand's space
- **Why People DON'T Share**: The specific barriers, embarrassments, or trust gaps that kill sharing in this category

## 2. THE REFERRAL LOOP

The core mechanic: who shares what, with whom, why, and what happens when the shared person lands.

- **The Trigger Moment**: The exact point in the customer experience where sharing feels natural — not forced. Grounded in what this brand actually does and when the customer feels most positive.
- **The Share Asset**: What the customer actually sends (link, code, gift, invite, content piece, experience). Be specific.
- **The Share Channel**: How the customer is expected to share (DM, text, social post, email, in-app, word-of-mouth IRL)
- **The Landing Experience**: What the invited person sees when they click/arrive — and why they convert instead of bouncing
- **The Loop Close**: What happens after the invitee converts — how the referrer finds out, and how the cycle can repeat

## 3. INCENTIVE STRUCTURE

Incentives are second, not first. But once you have a loop, the incentive decides whether the loop spins.

- **Incentive Type**: Monetary (credit, cash, discount), access (exclusive, early), status (recognition, tier), or intrinsic (the act of sharing is the reward). Pick the right flavor for this brand and category.
- **Symmetry**: Whether both sides get rewarded, or just one, and why
- **Unlock Logic**: When the reward pays out (on share, on invitee sign-up, on invitee first purchase, on invitee retention at day 30)
- **Margin Math**: A rough sanity check that the incentive doesn't destroy unit economics
- **Anti-Gaming**: The rules that prevent fraud, self-referral rings, and abuse — because they WILL happen

## 4. ACTIVATION TRIGGERS

When in the customer journey the brand should prompt for a referral. Over-prompting kills the program.

- **Post-Purchase Window**: Should the first ask happen immediately, after delivery, after use, or after a hero moment? Defend the timing.
- **Hero Moments**: The 2-3 specific product or service moments that are natural share triggers for this brand
- **Frequency Cap**: How often the same customer can be asked to refer before it burns out
- **Suppression**: When to NOT ask (recent complaint, return, refund, service issue)

## 5. THE 90-DAY LAUNCH PLAN

From zero to live referral program in 90 days.

- **Days 1-30**: Build phase — what to design, test, and instrument. The prototype loop.
- **Days 31-60**: Soft launch — a small cohort, tight measurement, rapid iteration on the share prompt and the landing experience
- **Days 61-90**: Scale — when to open the program broadly, what success looks like, and what the first kill-or-double-down decision looks like
- **Success Metrics**: Viral coefficient (K), share rate, invite conversion rate, referred-customer LTV vs. baseline
- **Failure Signals**: The numbers that mean the loop is broken and no amount of incentive will fix it

## 6. CROSS-SELL

End with: "Powered by Moodlight Advocacy Intelligence"

QUALITY CHECKS — read before you finalize:
1. A referral program is useful only if the loop has a real trigger moment, the incentive doesn't destroy margin, the activation has a frequency cap, and the success metric is viral coefficient — not "referrals generated." "Add a coupon at checkout" fails.
2. Run the inevitability test on the Trigger Moment: once stated, does the growth team nod because that's obviously when the customer feels most positive about sharing, or squint because it's clever? The right trigger moment feels inevitable — "of course that's when they'd share."
3. Run the substitution test on the whole loop: swap in a direct competitor's product. If the loop still works, rewrite until it only fits THIS brand's specific hero moment.
4. If the Cultural Permission diagnosis in Section 1 says this brand is not advocacy-ready, the rest of the report must reflect that reality — not pretend the loop will work anyway. Honest "no" beats optimistic "yes."
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "referral_program"
        return result
