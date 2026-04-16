"""
agents/creative_director.py
The Creative Director Agent — takes a brand or brief input, pulls real-time
cultural signals from Moodlight, and outputs a creative brief with the
judgment of a world-class ECD.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CreativeDirectorAgent(MoodlightAgent):

    agent_name = "creative_director"
    model = "claude-opus-4-6"
    max_tokens = 10000

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

        df = data_layer.load_combined_data(days=7)
        snapshot = data_layer.build_intelligence_snapshot(df)
        headlines = data_layer.load_headlines(df)
        vlds = data_layer.load_vlds_tables()
        velocity_df, density_df, scarcity_df = vlds
        opp_map = data_layer.build_creative_opportunity_map(velocity_df, density_df, scarcity_df)
        brand_context = data_layer.build_enrichment(username, user_input, df)
        campaign_precedents = data_layer.load_campaign_precedents(user_input, df)

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            brand_context=brand_context,
        )

        return {
            "context": context_str,
            "campaign_precedents": campaign_precedents,
        }

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        campaign_precedents = data["campaign_precedents"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""A client has come to you with this request:
"{user_input}"

Based on the following real-time intelligence data from Moodlight (which tracks empathy, emotions, trends, and strategic metrics across news and social media), create a creative brief.

{context}

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

## 3. THE VOICE: Creative Direction

This is not a messaging framework. This is how the work should FEEL.

- **The Posture**: Is this brand whispering or shouting? Leaning in or standing back? One sentence that a writer could use to gut-check every headline.
- **The Emotional Frequency**: Based on the cultural mood, what emotion should this work ACTIVATE in the audience? Not "inspire" — be specific. Restlessness? Relief? Defiance? Complicity?
- **The Line You Can't Cross**: What would make this tone wrong? Where does the edge become a cliff?
- **Reference Point**: Name one real cultural artifact (a show, a song, a meme, a moment) that captures the tone you're recommending. Not as content to copy — as a tuning fork.

End with: "This work should feel like: [one vivid sentence]"

## 4. THE UNEXPECTED ANGLE: The Insight They Didn't See Coming

This is where you earn your fee. Include ALL of the following:
- **Contrarian Take**: One insight that challenges conventional thinking about this category
- **Data Tension**: A contradiction in the data — what people say vs. what they engage with
- **Cultural Parallel**: Reference one analogy from another brand, category, or cultural moment
- **Competitor Blind Spot**: What competitors in this space are likely missing right now

ANTI-STALENESS CHECK: Do NOT anchor your creative idea on the highest-velocity topic unless you can prove a genuinely novel angle. The obvious trending topic is where lazy strategists go. Use the CREATIVE OPPORTUNITY MAP — topics marked [OPPORTUNITY] are your hunting ground; topics marked [SATURATED] are where you should NOT start.

End with: "The non-obvious move: [one sentence summary]"

## 5. CREATIVE PRECEDENT LENS

If CREATIVE PRECEDENTS are provided above, select the 3 most relevant and present:
- **[Campaign Name] ([Brand], [Year])** — [One sentence on cultural tension]
  *Applies because:* [Structural parallel to today's moment]

Then identify:
- **Structural pattern to steal:** [The underlying mechanic connecting the best precedents to this brief]

Do NOT recommend recreating any precedent. The value is the THINKING behind them.

## 6. WHY NOW: The Real-Time Trigger

- **This Week's Catalyst**: Quote 2-3 specific headlines from the data that are DIRECTLY RELEVANT
- **The Window**: Why this opportunity exists RIGHT NOW but might not in 30 days
- **Cultural Collision**: What current events are colliding to create this opening

End with: "Act now because: [one sentence]"

## 7. MAKE IT REAL: Tangible Outputs

**Opening Hooks (3 options):**
- One that leads with tension
- One that leads with aspiration
- One that's provocative/contrarian

**Campaign Concepts (3-4 concepts):**
For each concept:
- **Name**: A campaign name that could go on a brief
- **The Concept**: One paragraph. What is it, what does it look like, why does it work right now? Must feel like it could ONLY exist this week.
- **Why This Moment**: One sentence connecting it to a specific data signal
- **Steal This Line**: One sentence ready for a deck. Must make someone uncomfortable to say out loud.

Each concept should represent a genuinely different creative territory — not three versions of the same idea at different volume levels.

End with: "This is your starting point, not your ceiling."

Be bold and specific. Reference actual data points. Make decisions, not suggestions.

QUALITY CHECKS — read before you finalize:
1. Substitution test: delete any sentence a competitor's strategist could also write. If a claim works for a different brand in the same category, rewrite until it only fits THIS brand in THIS week.
2. Inevitability test on the Non-Obvious Move: once stated, does it feel like the only right answer given the data, or merely clever? Contrarian-for-its-own-sake fails. The best moves feel obvious in hindsight.
3. Each of the 3-4 campaign concepts must represent a genuinely different creative territory — not three volume levels of the same idea. If any two concepts share a mechanic, merge and find a different one.
4. The "Steal This Line" sentences must be defensible in a boardroom — a skeptical CMO asks "why THIS line?" and the answer must cite the data, not "it sounds powerful."
5. Delete any sentence that could appear in a generic creative deck from 2019. If a planner has seen this advice before, it's wasted ink.

End the brief with: "Powered by Moodlight's Cultural Momentum Matrix™"
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "creative_brief"
        return result
