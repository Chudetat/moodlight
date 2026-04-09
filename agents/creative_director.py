"""
agents/creative_director.py
The Creative Director Agent — takes a brand or brief input, pulls real-time
cultural signals from Moodlight, and outputs a creative brief with the
judgment of a world-class ECD.

Extracted and extended from generate_strategic_brief.py.
"""

from .base_agent import MoodlightAgent
from . import data_layer
from generate_strategic_brief import REGULATORY_GUIDANCE
from strategic_frameworks import select_frameworks, get_framework_prompt, STRATEGIC_FRAMEWORKS


class CreativeDirectorAgent(MoodlightAgent):

    agent_name = "creative_director"
    model = "claude-opus-4-6"
    max_tokens = 4500

    system_prompt = (
        "You are the most awarded creative director in advertising history. "
        "You've built your reputation on the ideas that made clients nervous "
        "before making them successful. You find the uncomfortable truth "
        "competitors are too polite to say. You never recommend what a "
        "competitor could also do — if it's obvious, it's worthless. "
        "Your best work comes from tension, not consensus. "
        "You speak plainly and give bold recommendations."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand, brief, or challenge")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        # Load all data sources
        df = data_layer.load_combined_data(days=7)
        snapshot = data_layer.build_intelligence_snapshot(df)
        headlines = data_layer.load_headlines(df)
        vlds = data_layer.load_vlds_tables()
        velocity_df, density_df, scarcity_df = vlds
        opp_map = data_layer.build_creative_opportunity_map(velocity_df, density_df, scarcity_df)
        market_ctx = data_layer.load_market_context()
        polymarket = data_layer.load_polymarket_data()
        brand_context = data_layer.build_enrichment(username, user_input, df)
        campaign_precedents = data_layer.load_campaign_precedents(user_input, df)

        # Select strategic frameworks
        selected = select_frameworks(user_input)
        framework_guidance = get_framework_prompt(selected)
        framework_names = [STRATEGIC_FRAMEWORKS[f]["name"] for f in selected]

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

        return {
            "context": context_str,
            "framework_guidance": framework_guidance,
            "framework_names": framework_names,
            "campaign_precedents": campaign_precedents,
        }

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        framework_guidance = data["framework_guidance"]
        campaign_precedents = data["campaign_precedents"]

        return f"""A client has come to you with this request:
"{user_input}"

TRAINING DATA BAN: Your ONLY sources of truth are the Moodlight intelligence data provided below. Do NOT inject facts, events, corporate actions, controversies, or narratives from your training data. Your training knowledge is stale — presenting it as current intelligence destroys credibility. If the data doesn't cover something, build your strategy from what IS there. Never fill gaps with training-data "knowledge."

Based on the following real-time intelligence data from Moodlight (which tracks empathy, emotions, trends, and strategic metrics across news and social media), create a strategic brief.

{context}

{framework_guidance}

{campaign_precedents}

If BRAND INTELLIGENCE or RELEVANT INTELLIGENCE ALERTS data is included in the intelligence snapshot, weave those insights into your analysis: brand VLDS into territorial mapping (Section 1), competitive gaps into your unexpected angle (Section 4), and recent alerts as real-time triggers (Section 5). Do not repeat raw numbers — interpret them strategically.

KEY METRICS TO CONSIDER:
- VELOCITY: How fast a topic is accelerating (high = trending now)
- LONGEVITY: How long a topic sustains interest (high = lasting movement)
- DENSITY: How saturated/crowded a topic is (high = hard to break through)
- SCARCITY: How underserved a topic is (high = white space opportunity)

Create a brief using the Cultural Momentum Matrix (CMM)™ structure:

## 1. WHERE TO PLAY: Cultural Territory Mapping

Analyze the data and identify:
- **Hot Zones**: Dominant topics (>10K mentions) — lead with authority, expect competition
- **Active Zones**: Growing topics (2K-10K mentions) — engage strategically, build expertise
- **Opportunity Zones**: Emerging topics (<2K mentions) — early mover advantage, test and learn
- **Avoid Zones**: High conflict, high risk topics to steer clear of

End with: "Territory Recommendation: [specific territory] because [data-backed reason]"

## 2. WHEN TO MOVE: Momentum Timing

Based on the empathy distribution and emotional climate in the data, identify the timing zone:
- **Warm / Highly Empathetic dominant**: Optimal engagement window — audiences are receptive and emotionally open. Recommendation: ENGAGE NOW
- **Detached / Neutral dominant**: Audiences are disengaged; wait for a positive emotional shift or proceed with extra sensitivity
- **Cold / Hostile dominant**: Defensive positioning only — high negativity means campaigns risk backlash
- **Mixed with strong positive emotions**: Good window despite mixed empathy — lean into the dominant positive emotion

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
- **Contrarian Take**: One insight that challenges conventional thinking about this category
- **Data Tension**: A contradiction in the data — what people say vs. what they engage with
- **Cultural Parallel**: Reference one analogy from another brand, category, or cultural moment
- **Competitor Blind Spot**: What competitors in this space are likely missing right now
- **Creative Spark**: One bold campaign idea that ONLY works in this specific cultural moment

ANTI-STALENESS CHECK: Do NOT anchor your creative idea on the highest-velocity topic unless you can prove a genuinely novel angle. The obvious trending topic is where lazy strategists go. Use the CREATIVE OPPORTUNITY MAP — topics marked [OPPORTUNITY] are your hunting ground; topics marked [SATURATED] are where you should NOT start.

End with: "The non-obvious move: [one sentence summary]"

## 4.5 CREATIVE PRECEDENT LENS

If CREATIVE PRECEDENTS are provided above, select the 3 most relevant and present:
- **[Campaign Name] ([Brand], [Year])** — [One sentence on cultural tension]
  *Applies because:* [Structural parallel to today's moment]

Then identify:
- **Structural pattern to steal:** [The underlying mechanic connecting the best precedents to this brief]

Do NOT recommend recreating any precedent. The value is the THINKING behind them.

## 5. WHY NOW: The Real-Time Trigger

- **This Week's Catalyst**: Quote 2-3 specific headlines from the data that are DIRECTLY RELEVANT
- **The Window**: Why this opportunity exists RIGHT NOW but might not in 30 days
- **Cultural Collision**: What current events are colliding to create this opening

End with: "Act now because: [one sentence]"

## 6. MAKE IT REAL: Tangible Outputs

**Opening Hooks (3 options):**
- One that leads with tension
- One that leads with aspiration
- One that's provocative/contrarian

**Campaign Concept (1 paragraph):**
A single activatable idea — name it, describe it, explain why it fits this cultural moment. Must feel like it could ONLY exist this week.

**Platform Play:**
Which platform is best suited for this moment and why? One sentence.

**First 48 Hours:**
If the client said "go" right now, what's the single most important action? Be specific.

**Steal This Line:**
One sentence the client can use verbatim in a deck, ad, or pitch tomorrow. It must make someone uncomfortable to say out loud.

End with: "This is your starting point, not your ceiling."

---

Be bold and specific. Reference actual data points. Make decisions, not suggestions.

QUALITY CHECK: Before finalizing, delete any sentence a competitor's strategist could also write.

End the brief with: "---
Powered by Moodlight's Cultural Momentum Matrix™"

{REGULATORY_GUIDANCE}
"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "creative_brief"
        return result
