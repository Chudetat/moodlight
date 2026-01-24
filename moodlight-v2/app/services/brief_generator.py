"""
Strategic Brief Generator Service.
Generates AI-powered strategic campaign briefs using Claude and Moodlight data.
"""
import pandas as pd
from anthropic import Anthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.config import get_settings
from app.models import NewsItem
from app.services.strategic_frameworks import (
    select_frameworks,
    get_framework_prompt,
    STRATEGIC_FRAMEWORKS
)

settings = get_settings()


async def get_brief_context_data(db: AsyncSession, days: int = 30) -> pd.DataFrame:
    """Load recent news data for brief context."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    stmt = select(NewsItem).where(
        NewsItem.created_at >= cutoff
    ).order_by(NewsItem.created_at.desc())

    result = await db.execute(stmt)
    items = result.scalars().all()

    if not items:
        return pd.DataFrame()

    data = []
    for item in items:
        data.append({
            "text": item.text,
            "topic": item.topic,
            "emotion_top_1": item.emotion,
            "empathy_score": item.empathy_score,
            "empathy_label": _get_empathy_label(item.empathy_score),
            "country": item.country or "Unknown",
            "source": item.source,
            "created_at": item.created_at,
            "engagement": item.engagement or 0,
        })

    return pd.DataFrame(data)


def _get_empathy_label(score: float) -> str:
    """Convert empathy score to label."""
    if score is None:
        return "Unknown"
    if score < 0.04:
        return "Low Empathy"
    elif score < 0.10:
        return "Moderate"
    elif score < 0.30:
        return "High Empathy"
    else:
        return "Very High Empathy"


def _build_context(df: pd.DataFrame) -> str:
    """Build context string from dataframe for the prompt."""
    if df.empty:
        return "No data available for analysis."

    top_topics = df['topic'].value_counts().head(5).to_string() if 'topic' in df.columns else "No topic data"
    empathy_dist = df['empathy_label'].value_counts().to_string() if 'empathy_label' in df.columns else "No empathy data"
    top_emotions = df['emotion_top_1'].value_counts().head(5).to_string() if 'emotion_top_1' in df.columns else "No emotion data"
    geo_dist = df['country'].value_counts().head(5).to_string() if 'country' in df.columns else "No geographic data"

    # Get recent headlines
    recent_headlines = ""
    viral_headlines = ""

    if 'text' in df.columns:
        # Most recent headlines
        if 'created_at' in df.columns:
            recent = df.nlargest(10, 'created_at')[['text', 'topic']].drop_duplicates('text')
            recent_headlines = "\n".join([
                f"- [{row['topic']}] {row['text'][:150]}"
                for _, row in recent.iterrows()
            ])

        # Most viral/high-engagement
        if 'engagement' in df.columns:
            viral = df.nlargest(8, 'engagement')[['text', 'topic', 'engagement']].drop_duplicates('text')
            viral_headlines = "\n".join([
                f"- [{row['topic']}] {row['text'][:150]} (engagement: {int(row['engagement'])})"
                for _, row in viral.iterrows()
            ])

    context = f"""
MOODLIGHT INTELLIGENCE SNAPSHOT
================================
TOP TOPICS:
{top_topics}

EMOTIONAL CLIMATE:
{top_emotions}

EMPATHY DISTRIBUTION:
{empathy_dist}

GEOGRAPHIC HOTSPOTS:
{geo_dist}

RECENT HEADLINES (What just happened):
{recent_headlines if recent_headlines else "No recent headlines available"}

HIGH-ENGAGEMENT CONTENT (What's resonating now):
{viral_headlines if viral_headlines else "No engagement data available"}

Total Posts Analyzed: {len(df)}
"""
    return context


def _build_cmm_prompt(user_need: str, context: str, framework_guidance: str) -> str:
    """Build the Cultural Momentum Matrix prompt."""
    return f"""You are a senior partner at the intersection of strategy consulting, and cultural intelligence, with the foresight of a futurist. You have the analytical rigor of McKinsey and the creative boldness of Wieden+Kennedy. You've shaped campaigns that move markets, see patterns others miss and turn data into unfair advantage. Your briefs have launched billion-dollar brands and repositioned struggling icons.

A client has come to you with this request:
"{user_need}"

Based on the following real-time intelligence data from Moodlight (which tracks empathy, emotions, trends, and strategic metrics across news and social media), create a strategic brief.

{context}

{framework_guidance}

KEY METRICS TO CONSIDER:
- VELOCITY: How fast a topic is accelerating (high = trending now)
- LONGEVITY: How long a topic sustains interest (high = lasting movement)
- DENSITY: How saturated/crowded a topic is (high = hard to break through)
- SCARCITY: How underserved a topic is (high = white space opportunity)


Create a brief using the Cultural Momentum Matrix (CMM) structure:

## 1. WHERE TO PLAY: Cultural Territory Mapping

Analyze the data and identify:
- **Hot Zones**: Dominant topics (>10K mentions) — lead with authority, expect competition
- **Active Zones**: Growing topics (2K-10K mentions) — engage strategically, build expertise
- **Opportunity Zones**: Emerging topics (<2K mentions) — early mover advantage, test and learn
- **Avoid Zones**: High conflict, high risk topics to steer clear of

End with: "Territory Recommendation: [specific territory] because [data-backed reason]"

## 2. WHEN TO MOVE: Momentum Timing

Based on the current Mood Score, identify the timing zone:
- **Strike Zone (60-80)**: Optimal engagement window — audiences receptive but not oversaturated. Recommendation: ENGAGE NOW
- **Caution Zone (40-59)**: Wait for positive shift or proceed with extra sensitivity
- **Storm Zone (<40)**: Defensive positioning only
- **Peak Zone (80+)**: High competition, premium content required

Factor in Velocity (how fast topics are moving) and Longevity (how long they'll last).

End with: "Timing Recommendation: [ENGAGE NOW / WAIT / PROCEED WITH CAUTION] because [data-backed reason]"

## 3. WHAT TO SAY: Message Architecture

Based on the empathy score and emotional climate:
- **Empathy Calibration**: Match message warmth to current cultural mood
- **Tone Recommendation**: Specific guidance on voice and approach
- **Message Hierarchy**: What to lead with, what to support with
- **Creative Thought-Starter**: One campaign idea or hook that fits this moment

End with: "Consider: '[specific campaign thought-starter]'"

## 4. UNEXPECTED ANGLE: The Insight They Didn't See Coming

This is where you earn your fee. Include ALL of the following:

- **Contrarian Take**: One insight that challenges conventional thinking about this category. What would surprise the client? What do they NOT expect to hear but need to?

- **Data Tension**: Look for contradictions (what people say vs. what they engage with, stated values vs. actual behavior). Call out one paradox in the data.

- **Cultural Parallel**: Reference one analogy from another brand, category, or cultural moment that illuminates the current opportunity.

- **Competitor Blind Spot**: What is one thing competitors in this space are likely missing right now?

- **Creative Spark**: One bold campaign idea or hook that ONLY works in this specific cultural moment. Not generic. Not safe. Something that makes the client lean forward.

End with: "The non-obvious move: [one sentence summary of the unexpected angle]"

## 5. WHY NOW: The Real-Time Trigger

This brief must feel URGENT and TIMELY. Use the RECENT HEADLINES and HIGH-ENGAGEMENT CONTENT sections above. Include:

- **This Week's Catalyst**: Quote or paraphrase 2-3 specific headlines from the data above that are DIRECTLY RELEVANT to the client's request. Skip unrelated headlines even if they're high-engagement. Be specific - "The [topic] story about [specifics]" not generic references.

- **The Window**: Why does this opportunity exist RIGHT NOW but might not in 30 days? What's the expiration date on this insight?

- **Cultural Collision**: What current events from the headlines are colliding to create this specific opening?

End with: "Act now because: [one sentence on why timing matters]"

Be bold and specific. Reference actual data points. Make decisions, not suggestions.

IMPORTANT: Do NOT include obvious "avoid" recommendations that any brand strategist already knows (e.g., "avoid war & foreign policy for brand safety"). Only mention Avoid Zones if:
1. The client's specific product/challenge intersects with that topic, OR
2. There's a non-obvious risk the client might miss

Focus on actionable opportunities, not generic warnings.

End the brief with: "---
Powered by Moodlight's Cultural Momentum Matrix"

HEALTHCARE / PHARMA / MEDICAL DEVICES:
- Flag emotional tones (fear, nervousness, anger, grief, sadness, disappointment) that may face Medical Legal Review (MLR) scrutiny
- Prioritize "safe white space" — culturally appropriate AND unlikely to trigger regulatory concerns
- Recommend messaging that builds trust and credibility over provocative hooks
- Note velocity spikes that could indicate emerging issues requiring compliance awareness
- Frame recommendations as "MLR-friendly" where appropriate
- Ensure fair balance when discussing benefits vs. risks

FINANCIAL SERVICES / BANKING / INVESTMENTS:
- Never promise or imply guaranteed returns
- Flag any claims that could be seen as misleading by SEC, FINRA, or CFPB
- Include appropriate risk disclosure language in recommendations
- Avoid superlatives ("best," "guaranteed," "risk-free") without substantiation
- Be cautious with testimonials — results not typical disclaimers required
- Fair lending language required — no discriminatory implications

ALCOHOL / SPIRITS / BEER / WINE:
- Never target or appeal to audiences under 21
- No health benefit claims whatsoever
- Include responsible drinking messaging considerations
- Avoid associating alcohol with success, social acceptance, or sexual prowess
- Cannot show excessive consumption or intoxication positively
- Platform restrictions: Meta/Google have strict alcohol ad policies

CANNABIS / CBD:
- Highly fragmented state-by-state regulations — recommend geo-specific strategies
- No medical or health claims unless FDA-approved
- Strict age-gating requirements in all messaging
- Major platform restrictions: Meta, Google, TikTok prohibit cannabis ads
- Recommend owned media and experiential strategies over paid social
- Cannot target or appeal to minors in any way

INSURANCE:
- No guaranteed savings claims without substantiation
- State DOI regulations vary — flag need for state-specific compliance review
- Required disclosures on coverage limitations
- Fair treatment language required — no discriminatory implications
- Testimonials require "results may vary" disclaimers
- Avoid fear-based messaging that could be seen as coercive

LEGAL SERVICES:
- No guarantees of case outcomes whatsoever
- State bar regulations vary — recommend jurisdiction-specific review
- Required disclaimers on attorney advertising
- Restrictions on client testimonials in many states
- Cannot create unjustified expectations
- Avoid comparative claims against other firms without substantiation

For all industries: Consider regulatory and reputational risk when recommending bold creative angles. When in doubt, recommend client consult with their legal/compliance team before execution.
"""


async def generate_strategic_brief(
    user_need: str,
    db: AsyncSession,
    days: int = 30
) -> tuple[str, list[str]]:
    """
    Generate a strategic campaign brief using AI and Moodlight data.

    Args:
        user_need: The client's brief request
        db: Database session
        days: Number of days of data to analyze

    Returns:
        Tuple of (brief_content, list_of_framework_names)
    """
    # Initialize Anthropic client
    client = Anthropic(api_key=settings.anthropic_api_key)

    # Get data context
    df = await get_brief_context_data(db, days)
    context = _build_context(df)

    # Select best frameworks for this request
    selected_frameworks = select_frameworks(user_need)
    framework_guidance = get_framework_prompt(selected_frameworks)

    # Build prompt
    prompt = _build_cmm_prompt(user_need, context, framework_guidance)

    # Generate brief
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2500,
        system="You are a senior strategist who combines data intelligence with creative intuition. You speak plainly and give bold recommendations.",
        messages=[{"role": "user", "content": prompt}]
    )

    # Get framework names for display
    framework_names = [STRATEGIC_FRAMEWORKS[f]["name"] for f in selected_frameworks]

    return response.content[0].text, framework_names


def get_available_frameworks() -> list[dict]:
    """Get list of all available frameworks for display."""
    return [
        {
            "key": key,
            "name": framework["name"],
            "source": framework["source"],
            "description": framework["description"],
            "use_when": framework["use_when"]
        }
        for key, framework in STRATEGIC_FRAMEWORKS.items()
    ]
