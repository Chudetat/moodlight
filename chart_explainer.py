"""
chart_explainer.py
Two-stage chart explanation engine: context-aware headline retrieval + Claude analysis.
Extracted from app.py for use by the API server (Phase 0C-3).
"""

import os
import pandas as pd
from anthropic import Anthropic


def _get_high_engagement(df: pd.DataFrame, n: int) -> list:
    """Pull top-N headlines by engagement/virality."""
    for col in ("virality", "retweets", "engagement"):
        if col in df.columns:
            return df.nlargest(n, col)["text"].tolist()
    return []


def _get_topic_diverse(df: pd.DataFrame, num_topics: int, per_topic: int) -> list:
    """Pull headlines spread across top topics by volume."""
    if "topic" not in df.columns:
        return []
    headlines = []
    for topic in df["topic"].value_counts().head(num_topics).index:
        headlines.extend(df[df["topic"] == topic]["text"].head(per_topic).tolist())
    return headlines


def _filter_by_summary_brands(df: pd.DataFrame, data_summary: str) -> pd.DataFrame:
    """Try to find headlines mentioning brands referenced in the data summary."""
    known_brands = ["NVIDIA", "Amazon", "Disney", "Lockheed Martin", "FIFA",
                    "Apple", "Google", "Microsoft", "Tesla", "Meta", "Netflix",
                    "AMD", "Intel", "Sony", "Samsung"]
    matches = [b for b in known_brands if b.lower() in data_summary.lower()]
    if not matches or "text" not in df.columns:
        return pd.DataFrame()
    pattern = "|".join(matches)
    mask = df["text"].str.contains(pattern, case=False, na=False)
    return df[mask]


def _filter_by_summary_topic(df: pd.DataFrame, data_summary: str) -> pd.DataFrame:
    """Try to find headlines matching the topic referenced in the data summary."""
    if "topic" not in df.columns:
        return pd.DataFrame()
    for topic in df["topic"].unique():
        if topic and topic.lower() in data_summary.lower():
            return df[df["topic"] == topic]
    return pd.DataFrame()


def _filter_by_country_mentions(df: pd.DataFrame, data_summary: str) -> list:
    """Pull headlines that mention countries referenced in the data summary."""
    import re
    if "text" not in df.columns:
        return []
    # Extract capitalized words that look like country names from data_summary
    # Data summary format: "Country: intensity X.XX (N articles), ..."
    country_pattern = re.findall(r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+)*)\b', data_summary)
    # Also catch all-caps like "CONGO", "UKRAINE"
    country_pattern += re.findall(r'\b([A-Z]{3,})\b', data_summary)
    # Filter out common non-country words
    skip = {"Intensity", "Geographic", "Hotspots", "articles", "Country", "Top", "Average"}
    countries = [c for c in country_pattern if c not in skip and len(c) > 2]
    if not countries:
        return []
    headlines = []
    for country in countries[:8]:  # Top 8 countries max
        mask = df["text"].str.contains(country, case=False, na=False)
        matched = df[mask]["text"].head(3).tolist()
        headlines.extend(matched)
    return headlines


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
        # Broad sample: extreme empathy + high-engagement + topic diversity
        if "empathy_score" in df.columns:
            # Raw RoBERTa scores cluster 0.03-0.15; use raw thresholds
            extreme_low = df[df["empathy_score"] < 0.04]["text"].head(3).tolist()
            extreme_high = df[df["empathy_score"] > 0.12]["text"].head(3).tolist()
            relevant_headlines.extend(extreme_low)
            relevant_headlines.extend(extreme_high)
        relevant_headlines.extend(_get_high_engagement(df, 5))
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(4, "created_at")["text"].tolist())
        relevant_headlines.extend(_get_topic_diverse(df, 4, 2))

    elif chart_type in ["density", "scarcity"]:
        # Headlines from crowded AND sparse topics
        if "topic" in df.columns:
            topic_counts = df["topic"].value_counts()
            top_topics = topic_counts.head(3).index.tolist()
            bottom_topics = topic_counts.tail(3).index.tolist()
            for topic in top_topics + bottom_topics:
                topic_headlines = df[df["topic"] == topic]["text"].head(3).tolist()
                relevant_headlines.extend(topic_headlines)

    elif chart_type == "velocity_longevity":
        # Recent headlines (high velocity) and older persistent ones
        if "created_at" in df.columns:
            recent = df.nlargest(5, "created_at")["text"].tolist()
            relevant_headlines.extend(recent)
        relevant_headlines.extend(_get_high_engagement(df, 5))

    elif chart_type == "virality_empathy":
        # Most viral + empathy extremes for contrast
        relevant_headlines.extend(_get_high_engagement(df, 8))
        if "empathy_score" in df.columns:
            extreme_low = df.nsmallest(3, "empathy_score")["text"].tolist()
            extreme_high = df.nlargest(3, "empathy_score")["text"].tolist()
            relevant_headlines.extend(extreme_low)
            relevant_headlines.extend(extreme_high)

    elif chart_type == "geographic_hotspots":
        # Extract country names from data_summary and filter headlines by mention
        relevant_headlines.extend(_filter_by_country_mentions(df, data_summary))
        # Backfill with recent + topic diversity if sparse
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(5, "created_at")["text"].tolist())
        relevant_headlines.extend(_get_topic_diverse(df, 3, 1))

    elif chart_type in ("empathy_by_topic", "topic_distribution"):
        # Pull from top topics by volume for representative coverage
        relevant_headlines.extend(_get_topic_diverse(df, 5, 3))

    elif chart_type == "emotional_breakdown":
        # Empathy extremes + high engagement + topic diversity for broad emotional range
        if "empathy_score" in df.columns:
            relevant_headlines.extend(df.nsmallest(4, "empathy_score")["text"].tolist())
            relevant_headlines.extend(df.nlargest(4, "empathy_score")["text"].tolist())
        relevant_headlines.extend(_get_high_engagement(df, 4))
        relevant_headlines.extend(_get_topic_diverse(df, 3, 1))

    elif chart_type == "empathy_distribution":
        # Sample across the empathy spectrum + topic diversity
        if "empathy_score" in df.columns:
            sorted_df = df.sort_values("empathy_score")
            n = len(sorted_df)
            if n >= 4:
                quartile = n // 4
                for i in range(4):
                    chunk = sorted_df.iloc[i * quartile:(i + 1) * quartile]
                    relevant_headlines.extend(chunk["text"].head(3).tolist())
        relevant_headlines.extend(_get_topic_diverse(df, 3, 1))

    elif chart_type == "trending_headlines":
        # High engagement + recent
        relevant_headlines.extend(_get_high_engagement(df, 8))
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(5, "created_at")["text"].tolist())

    elif chart_type in ("economic_indicators", "commodity_prices", "market_sentiment"):
        # Market-relevant: filter by economic/market topics + recent + engagement
        market_topics = {"economics", "business", "finance", "markets", "trade",
                         "energy", "commodities", "labor & work"}
        if "topic" in df.columns:
            mask = df["topic"].str.lower().isin(market_topics)
            market_df = df[mask]
            if not market_df.empty:
                relevant_headlines.extend(market_df["text"].head(8).tolist())
        relevant_headlines.extend(_get_high_engagement(df, 4))
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(4, "created_at")["text"].tolist())

    elif chart_type in ("brand_vlds", "brand_comparison", "competitive_war_room"):
        # Try to extract brand names from data_summary and filter
        brand_df = _filter_by_summary_brands(df, data_summary)
        if not brand_df.empty:
            relevant_headlines.extend(brand_df["text"].head(8).tolist())
        relevant_headlines.extend(_get_high_engagement(df, 4))
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(4, "created_at")["text"].tolist())

    elif chart_type == "topic_intelligence":
        # Filter by the specific topic if detectable from data_summary
        topic_df = _filter_by_summary_topic(df, data_summary)
        if not topic_df.empty:
            relevant_headlines.extend(topic_df["text"].head(10).tolist())
        relevant_headlines.extend(_get_high_engagement(df, 3))
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(3, "created_at")["text"].tolist())

    elif chart_type == "polymarket_divergence":
        # Broad like mood_vs_market: engagement + recent + topic diversity
        relevant_headlines.extend(_get_high_engagement(df, 5))
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(4, "created_at")["text"].tolist())
        relevant_headlines.extend(_get_topic_diverse(df, 4, 2))

    else:
        # Default: broad sample — recent + engagement + topic diversity
        if "created_at" in df.columns:
            relevant_headlines.extend(df.nlargest(5, "created_at")["text"].tolist())
        relevant_headlines.extend(_get_high_engagement(df, 5))
        relevant_headlines.extend(_get_topic_diverse(df, 4, 2))

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

        "geographic_hotspots": f"""Based on this geographic intensity data and the relevant headlines below, explain why the TOP-RANKED countries show elevated threat levels.

Data (sorted by intensity, highest first): {data_summary}

Relevant headlines from top countries:
{headline_context}

IMPORTANT: Format each country consistently as a short heading followed by 1-2 sentences. Only reference events that appear in the headlines — if no headlines mention a specific country, note "no matching headlines" rather than speculating. Be specific about actual events driving the scores.""",

        "mood_vs_market": f"""Based on this social mood vs market data and the headlines below, explain in 3-4 sentences why there is divergence or alignment between public sentiment and market performance.

IMPORTANT - Social Mood Score interpretation:
- The Social Mood score (0-100) measures EMPATHETIC TONE in discourse, NOT topic positivity
- Below 35 = Very Cold/Hostile tone
- 35-50 = Detached/Neutral tone
- 50-70 = Warm/Supportive tone (people discussing topics with empathy)
- Above 70 = Highly Empathetic tone
- A high score (e.g., 68) means people are discussing topics with warmth/nuance, EVEN IF the topics themselves are heavy or negative

IMPORTANT - Breadth of analysis:
- Consider the FULL range of headlines, not just 1-2 stories. Markets are driven by macro events (geopolitics, central bank policy, conflicts, commodities) not just tech/cultural news.
- If there are geopolitical, economic, or conflict-related headlines, these likely matter MORE to markets than cultural stories.
- Avoid anchoring on a single narrative — synthesize across multiple drivers.

Data: {data_summary}

Representative headlines (extreme sentiment, high engagement, recent, topic-diverse):
{headline_context}

What macro forces, geopolitical events, or sector shifts explain the divergence or alignment? Is social sentiment leading or lagging the market? Keep it concise — 3-4 sentences max, no headers or bullet points.""",

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

What does this divergence signal? Is the crowd wrong or are markets ahead? Any opportunity for contrarian positioning? Match your tone interpretation to the actual score. Be specific and actionable.""",

        "market_sentiment": f"""Based on this market index data and the relevant headlines below, explain in 2-3 sentences what's driving market moves today.

Data: {data_summary}

Relevant headlines:
{headline_context}

What macro events or sector shifts explain these movements? Any notable divergences between indices? Be specific.""",

        "brand_vlds": f"""Based on this brand's VLDS (Velocity, Longevity, Density, Scarcity) metrics and the relevant headlines below, explain in 2-3 sentences what the brand's current narrative position looks like.

Data: {data_summary}

Relevant headlines:
{headline_context}

What do these metrics mean for the brand's cultural relevance? Where are the opportunities and risks? Be strategic.""",

        "competitive_war_room": f"""Based on this competitive landscape data (share of voice and competitive gaps) and relevant headlines, explain in 2-3 sentences the competitive dynamics.

Data: {data_summary}

Relevant headlines:
{headline_context}

Which competitors are gaining ground and why? Where are the strategic opportunities? Be specific about competitive positioning.""",

        "brand_comparison": f"""Based on this brand comparison data and headlines, explain in 2-3 sentences the key differences between these brands' cultural positioning.

Data: {data_summary}

Relevant headlines:
{headline_context}

How do these brands differ in audience perception? Where does each have an advantage? Be specific and actionable.""",
    }

    prompt = prompts.get(chart_type, "Explain this data pattern in 2-3 sentences.")

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=800,
            system="You are a senior intelligence analyst. Give concise, specific insights that connect the quantitative data to actual events in the headlines. Show your work - explain WHAT happened, not just what the numbers show. No fluff.",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"Unable to generate insight: {str(e)}"
