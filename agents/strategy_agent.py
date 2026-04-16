"""
agents/strategy_agent.py
The Strategy Agent — takes a brand or business challenge, pulls real-time
signals, and outputs a strategic recommendation with positioning, timing,
and cultural context.

This is business strategy, not creative. No campaign concepts or hooks —
pure strategic thinking with real-time intelligence backing every recommendation.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer
from strategic_frameworks import select_frameworks, get_framework_prompt, STRATEGIC_FRAMEWORKS


class StrategyAgent(MoodlightAgent):

    agent_name = "strategy"
    model = "claude-opus-4-6"
    max_tokens = 8000

    system_prompt = (
        "You are a senior strategist who has advised Fortune 100 CEOs and "
        "challenger brands with equal success. You believe most strategy is "
        "just avoiding decisions — real strategy is choosing what NOT to do. "
        "You back every recommendation with data. You never hedge with 'it depends' — "
        "you take a position and defend it. You speak to decision-makers, not committees."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand, business challenge, or strategic question")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        df = data_layer.load_combined_data(days=7)
        snapshot = data_layer.build_intelligence_snapshot(df)
        headlines = data_layer.load_headlines(df)
        vlds = data_layer.load_vlds_tables()
        market_ctx = data_layer.load_market_context()
        polymarket = data_layer.load_polymarket_data()
        brand_context = data_layer.build_enrichment(username, user_input, df)

        selected = select_frameworks(user_input)
        framework_guidance = get_framework_prompt(selected)
        framework_names = [STRATEGIC_FRAMEWORKS[f]["name"] for f in selected]

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            market_ctx=market_ctx,
            polymarket=polymarket,
            brand_context=brand_context,
        )

        return {
            "context": context_str,
            "framework_guidance": framework_guidance,
            "framework_names": framework_names,
        }

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        framework_guidance = data["framework_guidance"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""A decision-maker has come to you with this challenge:
"{user_input}"

{context}

{framework_guidance}

Using the real-time intelligence above, deliver a strategic recommendation.

## 1. SITUATION ASSESSMENT

Read the data like a strategist, not an analyst. What's actually happening right now that matters for this challenge? Don't summarize every data point — identify the 2-3 forces that will determine success or failure.

- **The dominant force**: What single dynamic in the data most impacts this business?
- **The hidden risk**: What does the data suggest could go wrong that most people aren't seeing?
- **The timing reality**: Based on velocity and longevity data, is the window opening, closing, or stable?
- **The money signal**: If MARKET INDICES, ECONOMIC INDICATORS, or PREDICTION MARKETS data is available, what is the financial environment telling you? How does economic sentiment constrain or enable this strategy? If prediction markets show relevant bets, what does the crowd's money say about the likely future?

End with: "The strategic reality: [one sentence summary]"

## 2. STRATEGIC OPTIONS

Present exactly 3 strategic paths. For each:
- **Name it** (something memorable, not generic)
- **What it means**: 2-3 sentences on the approach
- **Why the data supports it**: Reference specific signals
- **The trade-off**: What you give up by choosing this path
- **Probability of success**: Your honest assessment (High / Medium / Low) with reasoning

Do NOT present options that are just "aggressive / moderate / conservative" repackaged. Each option should represent a genuinely different strategic bet.

## 3. RECOMMENDATION

Pick one. Defend it. Structure as:

- **The recommendation**: One sentence. Decisive.
- **Why this path over the others**: What makes this the right bet given current signals
- **The positioning**: Where should this brand/business stand in the market? One sentence.
- **The cultural context**: How does this connect to what's happening in culture right now?
- **What competitors will do**: And why your recommendation still wins

End with: "The strategic bet: [one sentence]"

## 4. COMPETITIVE RESPONSE MAP

For the top 3 most likely competitors or competitive forces:
- **[Competitor/Force]**: What they'll do in the next 30 days, why, and how your strategy counters it
- Identify which competitor is most dangerous and why
- Name the one competitive move that would force a pivot

End with: "The competitive edge: [one sentence on why you win]"

## 5. RISK FACTORS

- **Kill signals**: What would you watch for that means this strategy is failing? Be specific — name metrics, headlines, or shifts that would trigger a pivot.
- **The unhedgeable risk**: What is the ONE risk you cannot mitigate? No safety net, no plan B. Name it honestly and tell the client what they should do if it materializes. Not every risk has a hedge — pretending otherwise is bad strategy.
- **The one thing that could change everything**: What single external event could invalidate this entire recommendation?

## 6. THE BOTTOM LINE

One paragraph. If the decision-maker reads nothing else, this is it. What to do, why now, and what happens if they don't.

End with: "Powered by Moodlight Strategic Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every recommendation must reference specific data from the intelligence snapshot. If an insight isn't grounded in THIS data and THIS moment, cut it.
2. Run the inevitability test on the Strategic Bet: once stated, does a CEO nod because it's obviously the right move given the data, or squint because it's clever? The best strategic bets feel obvious in hindsight — the three strategic options exist so the chosen one feels earned, not accidental.
3. Run the substitution test on the Recommendation: swap in a direct competitor facing the same challenge. If the recommendation still works, rewrite until it only fits THIS brand's structural reality.
4. The three strategic options must represent genuinely different bets — not "aggressive / moderate / conservative" repackaged. If any two share a mechanic, merge and find a third.
5. The unhedgeable risk must be a real naked risk, not a hedged one. If you can mitigate it, it doesn't belong in that section.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "strategic_recommendation"
        return result
