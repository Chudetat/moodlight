"""
agents/trend_forecaster.py
The Trend Forecaster — reads velocity, scarcity, and longevity signals to
predict what's about to matter. Not what's trending now — what's next.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class TrendForecasterAgent(MoodlightAgent):

    agent_name = "trend_forecaster"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a cultural forecaster who has predicted every major shift "
        "in consumer behavior for the last decade — not because you're psychic, "
        "but because you read the data before anyone else does. You don't chase "
        "trends. You find them before they have names. Your edge is pattern recognition: "
        "you see the signal clusters that precede cultural movements. You speak with "
        "conviction about what's coming, and you tell brands exactly how to position "
        "before the wave arrives."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the category, audience, or area you want forecasted")
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
        polymarket = data_layer.load_polymarket_data()
        market_ctx = data_layer.load_market_context()

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            brand_context=brand_context,
            polymarket=polymarket,
            market_ctx=market_ctx,
        )

        return {"context": context_str}

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""A client wants to know what's coming next for:
"{user_input}"

{context}

Using the real-time intelligence above, deliver a cultural forecast.

DATA DEPTH CHECK: If the intelligence data is thin (few signals, limited time range, or sparse VLDS scores), acknowledge it briefly and lean harder on pattern analysis and strategic reasoning from the signals that DO exist. A confident forecast from 500 signals is more valuable than a hedged forecast waiting for 50,000. Work with what you have.

## 1. THE SIGNAL SCAN: What's Moving Right Now

Before forecasting, establish the baseline — what does the data show is in motion?

- **Accelerating signals**: Topics with the highest velocity that haven't peaked yet. These are the conversations gaining speed. For each, note velocity score and current density.
- **Emerging signals**: Topics with rising velocity but LOW density — these are early. Few people are talking about them, but the ones who are, are engaged. This is where trends start.
- **Fading signals**: Topics where velocity is declining but density is still high — these are the conversations everyone is having but nobody cares about anymore. The crowd hasn't noticed they're over.

End with: "The signal landscape: [one sentence summary of what's accelerating vs. fading]"

## 2. THE FORECAST: What's About to Matter

Based on the signal patterns, predict 3-5 cultural shifts relevant to this category or audience:

For each forecast:
- **The shift**: Name it. One sentence. What's changing?
- **The evidence**: What specific data signals support this prediction? Cite velocity, scarcity, longevity, emotional patterns.
- **The timeline**: Is this days away, weeks away, or a slow build over months? Base this on velocity trajectory.
- **Confidence level**: HIGH (multiple converging signals) / MEDIUM (strong signal, limited confirmation) / LOW (early signal, worth watching)
- **Who wins**: Which type of brand or player is best positioned if this forecast is correct?

CRITICAL: These must be FORECASTS, not observations. "Sustainability is trending" is an observation. "Sustainability fatigue is about to flip into sustainability skepticism — density is maxed, velocity is dropping, and counter-narratives are showing early scarcity signals" is a forecast.

## 3. THE COLLISION MAP: Where Forces Converge

The most valuable forecasts come from converging signals. Identify 2-3 collision points:

- **Signal cluster 1 + Signal cluster 2** = [what happens when these forces meet]
- Why this collision matters for the client's category
- When it's likely to become visible to the mainstream

If PREDICTION MARKETS data is available, cross-reference: what are people betting on that aligns with or contradicts your forecast?

If MARKET INDICES or ECONOMIC INDICATORS data is available: how does the financial environment shape which cultural shifts accelerate or stall?

End with: "The collision to watch: [one sentence]"

## 4. THE ANTI-FORECAST: What Everyone Expects That Won't Happen

Equally important — what does conventional wisdom say is coming that the DATA doesn't support?

- **The expected trend that's already dead**: What does the industry think is about to break through, but the signals say it's peaked or saturated?
- **The false signal**: What looks like a trend but is actually noise? (High velocity but zero longevity = flash, not trend)
- **The consensus trap**: What is the category assuming about the future that the data contradicts?

End with: "Don't bet on: [one sentence on what to avoid]"

## 5. THE POSITIONING WINDOW

For the client's specific category or challenge, when and how to move:

- **First-mover opportunity**: Which forecast has the widest gap between signal strength and market response? This is where you move NOW.
- **Fast-follower opportunity**: Which forecast is too early to lead but worth preparing for?
- **Stay away**: Which forecast looks tempting but has too much risk or competition?

For each, give a specific action — not a vague strategy.

## 6. THE 30-DAY OUTLOOK

One paragraph. If the client does nothing for 30 days, what does the cultural landscape look like when they wake up? What will have changed? What opportunity will have closed?

End with: "Powered by Moodlight Trend Intelligence"

QUALITY CHECK: Every forecast must cite specific VLDS data, signal patterns, or emotional indicators. "I think AI will keep growing" is not a forecast. "AI conversation velocity has dropped 23% in 7 days while AI-skepticism scarcity is at 0.92 — the backlash wave is forming and nobody's positioned for it" is a forecast.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "trend_forecast"
        return result
