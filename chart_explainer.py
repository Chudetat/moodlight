"""
chart_explainer.py
Two-stage chart explanation engine: context-aware headline retrieval + Claude analysis.
Extracted from app.py for use by the API server (Phase 0C-3).
"""

import os
import pandas as pd
from anthropic import Anthropic


def retrieve_relevant_headlines(df: pd.DataFrame, chart_type: str, data_summary: str, max_headlines: int = 15) -> str:
    """Stage 1: Context-aware headline retrieval based on chart type and anomalies."""

    if df.empty or "text" not in df.columns:
        return ""

    # Ensure we have datetime
    if "created_at" in df.columns:
        df = df.copy()
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    relevant_headlines = []

    if chart_type == "mood_history":
        # Find dates with biggest mood shifts and pull headlines from those days
        if "created_at" in df.columns and "empathy_score" in df.columns:
            daily = df.groupby(df["created_at"].dt.date).agg({
                "empathy_score": "mean",
                "text": list
            }).reset_index()
            if len(daily) > 1:
                daily["mood_shift"] = daily["empathy_score"].diff().abs()
                top_shift_days = daily.nlargest(3, "mood_shift")["created_at"].tolist()
                for day in top_shift_days:
                    day_headlines = df[df["created_at"].dt.date == day]["text"].head(5).tolist()
                    relevant_headlines.extend(day_headlines)

    elif chart_type == "mood_vs_market":
        # Pull headlines with extreme sentiment (very high or very low)
        if "empathy_score" in df.columns:
            extreme_low = df[df["empathy_score"] < 30]["text"].head(5).tolist()
            extreme_high = df[df["empathy_score"] > 70]["text"].head(5).tolist()
            relevant_headlines.extend(extreme_low)
            relevant_headlines.extend(extreme_high)

    elif chart_type in ["density", "scarcity"]:
        # Pull headlines from topics mentioned in the data summary
        if "topic" in df.columns:
            topic_counts = df["topic"].value_counts()
            top_topics = topic_counts.head(3).index.tolist()
            bottom_topics = topic_counts.tail(3).index.tolist()
            for topic in top_topics + bottom_topics:
                topic_headlines = df[df["topic"] == topic]["text"].head(3).tolist()
                relevant_headlines.extend(topic_headlines)

    elif chart_type == "velocity_longevity":
        # Pull recent headlines (high velocity) and older persistent ones
        if "created_at" in df.columns:
            recent = df.nlargest(5, "created_at")["text"].tolist()
            if "virality" in df.columns:
                viral = df.nlargest(5, "virality")["text"].tolist()
                relevant_headlines.extend(viral)
            relevant_headlines.extend(recent)

    elif chart_type == "virality_empathy":
        # Pull most viral headlines
        if "virality" in df.columns:
            viral = df.nlargest(10, "virality")["text"].tolist()
            relevant_headlines.extend(viral)
        elif "retweets" in df.columns:
            viral = df.nlargest(10, "retweets")["text"].tolist()
            relevant_headlines.extend(viral)

    elif chart_type == "geographic_hotspots":
        # Pull headlines from top intensity countries
        if "country" in df.columns and "intensity" in df.columns:
            top_countries = df.groupby("country")["intensity"].mean().nlargest(5).index.tolist()
            for country in top_countries:
                country_headlines = df[df["country"] == country]["text"].head(3).tolist()
                relevant_headlines.extend(country_headlines)

    else:
        # Default: get most recent + highest intensity mix
        if "intensity" in df.columns:
            high_intensity = df.nlargest(7, "intensity")["text"].tolist()
            relevant_headlines.extend(high_intensity)
        if "created_at" in df.columns:
            recent = df.nlargest(8, "created_at")["text"].tolist()
            relevant_headlines.extend(recent)

    # Fallback if no relevant headlines found
    if not relevant_headlines:
        relevant_headlines = df["text"].head(max_headlines).tolist()

    # Dedupe and limit
    seen = set()
    unique_headlines = []
    for h in relevant_headlines:
        if h not in seen and pd.notna(h):
            seen.add(h)
            unique_headlines.append(h)
            if len(unique_headlines) >= max_headlines:
                break

    return "\n".join(unique_headlines)


def generate_chart_explanation(chart_type: str, data_summary: str, df: pd.DataFrame) -> str:
    """Generate dynamic explanation for chart insights using AI — two-stage architecture."""

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Stage 1: Context-aware headline retrieval
    relevant_headlines = retrieve_relevant_headlines(df, chart_type, data_summary)

    if not relevant_headlines:
        headline_context = "No headlines available for this time period."
    else:
        headline_context = relevant_headlines

    prompts = {
        "empathy_by_topic": f"""Based on this empathy-by-topic data and the relevant headlines below, explain in 2-3 sentences why certain topics score higher/lower on empathy.

IMPORTANT - Empathy Score interpretation:
- Empathy scores measure how WARMLY/SUPPORTIVELY people discuss a topic, NOT whether the topic itself is positive
- Higher scores = people engaging with nuance, compassion, constructive dialogue
- Lower scores = hostile, dismissive, or inflammatory discourse
- A tragic topic (e.g., disaster) can have HIGH empathy if people discuss it with compassion

Data: {data_summary}

Relevant headlines:
{headline_context}

Be specific about what is driving the scores. Reference actual events from the headlines. Keep it insightful and actionable.""",

        "emotional_breakdown": f"""Based on this emotional distribution data and the relevant headlines below, explain in 2-3 sentences why certain emotions dominate.\n\nData: {data_summary}\n\nRelevant headlines:\n{headline_context}\n\nReference specific events driving emotions like curiosity, admiration, excitement, fear, sadness, anger, etc. Keep it insightful.""",

        "empathy_distribution": f"""Based on this empathy distribution and the relevant headlines below, explain in 2-3 sentences why discourse skews warm or cold.

IMPORTANT - Empathy Score interpretation (0-100 scale):
- Below 35 = Very Cold/Hostile tone (inflammatory, dismissive discourse)
- 35-50 = Detached/Neutral tone
- 50-70 = Warm/Supportive tone (constructive, empathetic discussion)
- Above 70 = Highly Empathetic tone
- This measures HOW people discuss topics, not whether topics are positive/negative

Data: {data_summary}

Relevant headlines:
{headline_context}

What events or dynamics are driving the tone of coverage? Be specific about what's making discourse warm or hostile.""",

        "topic_distribution": f"""Based on this topic distribution and the relevant headlines below, explain in 2-3 sentences why certain topics dominate the news cycle.\n\nData: {data_summary}\n\nRelevant headlines:\n{headline_context}\n\nWhat events or trends are driving topic volume? Be specific.""",

        "geographic_hotspots": f"""Based on this geographic intensity data and the relevant headlines below, explain why the TOP-RANKED countries show elevated threat levels.\n\nData (sorted by intensity, highest first): {data_summary}\n\nRelevant headlines from top countries:\n{headline_context}\n\nIMPORTANT: Format each country consistently. Be specific about actual events driving the scores.""",

        "mood_vs_market": f"""Based on this social mood vs market data and the relevant headlines below, explain in 2-3 sentences why there is divergence or alignment between public sentiment and market performance.

IMPORTANT - Social Mood Score interpretation:
- The Social Mood score (0-100) measures EMPATHETIC TONE in discourse, NOT topic positivity
- Below 35 = Very Cold/Hostile tone
- 35-50 = Detached/Neutral tone
- 50-70 = Warm/Supportive tone (people discussing topics with empathy)
- Above 70 = Highly Empathetic tone
- A high score (e.g., 68) means people are discussing topics with warmth/nuance, EVEN IF the topics themselves are heavy or negative

Data: {data_summary}

Headlines driving sentiment extremes:
{headline_context}

Is social sentiment leading or lagging the market? What specific events explain the gap or alignment? Match your tone interpretation to the actual score. Be specific and actionable for investors.""",

        "trending_headlines": f"""Based on these trending headlines and their engagement metrics, explain in 2-3 sentences what common themes or events are driving virality.\n\nData: {data_summary}\n\nTop trending headlines:\n{headline_context}\n\nWhat patterns do you see? Why are these resonating with audiences right now?""",

        "velocity_longevity": f"""Based on this velocity and longevity data for topics and the relevant headlines below, explain in 2-3 sentences which topics are emerging movements vs flash trends.\n\nData: {data_summary}\n\nRecent and persistent headlines:\n{headline_context}\n\nWhich topics should brands invest in long-term vs. capitalize on quickly? Be strategic.""",

        "virality_empathy": f"""Based on this virality vs empathy data and the most viral headlines below, explain in 2-3 sentences what makes certain posts go viral and whether empathetic or hostile content spreads faster.

IMPORTANT - Empathy Score context:
- High empathy = warm, supportive, nuanced tone in how people engage
- Low empathy = hostile, inflammatory, dismissive tone
- This measures discourse tone, not topic positivity

Data: {data_summary}

Most viral headlines:
{headline_context}

What patterns emerge about viral mechanics? Does warmth or hostility drive more engagement? Any insights for content strategy?""",

        "mood_history": f"""Based on this 7-day mood history and headlines from days with significant mood shifts, explain in 2-3 sentences what events caused the changes in public sentiment.

IMPORTANT - Mood Score interpretation (0-100 scale):
- Below 35 = Very Cold/Hostile discourse
- 35-50 = Detached/Neutral
- 50-70 = Warm/Supportive
- Above 70 = Highly Empathetic
- A spike UP means discourse became MORE empathetic/constructive
- A dip DOWN means discourse became MORE hostile/inflammatory
- This measures tone, not whether news was good or bad

Data: {data_summary}

Headlines from days with mood shifts:
{headline_context}

Identify specific events that drove mood spikes or dips. Why did discourse become warmer or colder on those days?""",

        "density": f"""Based on this density data for topics and headlines from crowded vs sparse topics, explain in 2-3 sentences which topics are oversaturated vs which have white space opportunity.\n\nData: {data_summary}\n\nHeadlines from high and low density topics:\n{headline_context}\n\nWhich topics are oversaturated and which represent open territory for brands? Be strategic.""",

        "scarcity": f"""Based on this scarcity data for topics and the relevant headlines below, explain in 2-3 sentences which topics are underserved and represent first-mover opportunities.\n\nData: {data_summary}\n\nHeadlines showing coverage gaps:\n{headline_context}\n\nWhich topics should brands jump on before competitors? What gaps exist in the conversation?""",

        "economic_indicators": f"""Based on these economic indicator values and the relevant headlines below, explain in 2-3 sentences what the current economic picture looks like and what investors should watch for.

Key context for interpreting these indicators:
- CPI (YoY): Consumer Price Index year-over-year change. Above 3% = elevated inflation, below 2% = deflationary pressure
- Fed Funds Rate: Set by the FOMC, only changes at Fed meetings. Reflects monetary policy tightness
- 10Y Treasury: Market-determined, reflects growth/inflation expectations. Rising = markets expect growth or inflation
- Unemployment Rate: Below 4% = tight labor market, above 5% = weakening
- Inflation Rate: Annual inflation from AlphaVantage (may differ slightly from CPI YoY)
- Nonfarm Payroll: Total US non-farm employed workers (non-seasonally-adjusted). January typically shows large seasonal drops from holiday layoffs ending — this is normal and NOT a recession signal

Data: {data_summary}

Relevant headlines:
{headline_context}

Connect the numbers to real-world events. What story do these indicators tell together? What should someone monitoring brands and markets watch for next? Be specific and actionable.""",

        "topic_intelligence": f"""Based on this topic's VLDS metrics, empathy data, and relevant headlines, give 2-3 sentences of specific, actionable strategic advice.

VLDS Framework:
- Velocity (0-1): How fast the topic is growing. High = spiking now
- Longevity (0-1): Will it last? High = sustained interest, not a flash trend
- Density (0-1): How crowded is the conversation? High = many competing voices
- Scarcity (0-1): How underserved is the topic? High = gaps in quality coverage

Strategic interpretation:
- High V + High L + Low D + High S = First mover opportunity (get in now)
- High V + Low L = Flash trend (act fast or skip)
- High D + Low S = Red ocean (hard to differentiate)
- High D + High S = Niche opportunity (quality can break through)

Data: {data_summary}

Relevant headlines:
{headline_context}

Give SPECIFIC advice: Should a brand invest in this topic? What angle should they take? What's the window of opportunity? What risks exist? Reference actual headlines driving the numbers.""",

        "commodity_prices": f"""Based on these commodity price movements and the relevant headlines below, explain in 2-3 sentences what's driving prices and the implications for businesses.

Brand relevance mapping (which watchlist brands are affected):
- WTI & Brent Crude → Lockheed Martin (defense/aerospace fuel costs)
- Copper → NVIDIA (semiconductor manufacturing, PCB components)
- Aluminum → NVIDIA (heat sinks, chassis), Amazon (logistics fleet, packaging, data center construction)
- Natural Gas → General energy/manufacturing costs

Data: {data_summary}

Relevant headlines:
{headline_context}

What's driving the biggest movers? How do these price changes specifically impact the watchlist brands above? Be specific about supply chain and cost implications. Keep it actionable.""",

        "polymarket_divergence": f"""Based on this prediction market vs social sentiment data and headlines below, explain in 2-3 sentences why prediction markets and social mood diverge (or align).

IMPORTANT - Social Mood Score interpretation:
- The Social Mood score (0-100) measures EMPATHETIC TONE in discourse, NOT topic positivity
- Below 35 = Very Cold/Hostile tone
- 35-50 = Detached/Neutral tone
- 50-70 = Warm/Supportive tone (people discussing topics with empathy)
- Above 70 = Highly Empathetic tone
- A high score means people are discussing topics with warmth/nuance, EVEN IF the topics themselves are heavy or negative

Data: {data_summary}

Headlines driving sentiment:
{headline_context}

What does this divergence signal? Is the crowd wrong or are markets ahead? Any opportunity for contrarian positioning? Match your tone interpretation to the actual score. Be specific and actionable."""
    }

    prompt = prompts.get(chart_type, "Explain this data pattern in 2-3 sentences.")

    try:
        response = client.messages.create(
            model="claude-opus-4-20250514",
            max_tokens=800,
            system="You are a senior intelligence analyst. Give concise, specific insights that connect the quantitative data to actual events in the headlines. Show your work - explain WHAT happened, not just what the numbers show. No fluff.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Unable to generate insight: {str(e)}"
