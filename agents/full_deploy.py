"""
agents/full_deploy.py
Full Deploy Agent — all three agents working as one cohesive team.
One input, one complete battle plan: cultural strategy, creative brief,
and comms plan that are complementary, not contradictory.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer
from strategic_frameworks import select_frameworks, get_framework_prompt, STRATEGIC_FRAMEWORKS


class FullDeployAgent(MoodlightAgent):

    agent_name = "full_deploy"
    model = "claude-opus-4-6"
    max_tokens = 16000

    system_prompt = (
        "You are a three-person senior team working as one mind: "
        "a Cultural Strategist, an Executive Creative Director, and a Comms Planner. "
        "You have built your careers on work that made clients nervous before making "
        "them successful. You think together, build on each other's ideas, and never "
        "contradict each other — because you're one team with one point of view. "
        "The strategy drives the creative. The creative drives the distribution. "
        "Every section of this document is aware of every other section. "
        "You speak plainly, take positions, and back everything with data."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand, challenge, or campaign")
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
        campaign_precedents = data_layer.load_campaign_precedents(user_input, df)

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
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""A client has brought you a challenge that needs the full team:
"{user_input}"

{context}

{framework_guidance}

{campaign_precedents}

KEY METRICS TO CONSIDER:
- VELOCITY: How fast a topic is accelerating (high = trending now)
- LONGEVITY: How long a topic sustains interest (high = lasting movement)
- DENSITY: How saturated/crowded a topic is (high = hard to break through)
- SCARCITY: How underserved a topic is (high = white space opportunity)

You are delivering a FULL DEPLOY — one cohesive battle plan from three senior perspectives. Every section must be aware of every other section. The strategy drives the creative. The creative drives the comms plan. No contradictions. No repetition. One team, one point of view.

# PART 1: CULTURAL STRATEGY
*From your Cultural Strategist*

## 1.1 SITUATION ASSESSMENT

Read the data like a strategist. What's actually happening right now that matters for this challenge?

- **The dominant force**: What single dynamic most impacts this business?
- **The hidden risk**: What could go wrong that most people aren't seeing?
- **The timing reality**: Based on velocity and longevity, is the window opening, closing, or stable?
- **The money signal**: If MARKET INDICES, ECONOMIC INDICATORS, or PREDICTION MARKETS data is available, what is the financial environment telling you? How does it constrain or enable this strategy?

End with: "The strategic reality: [one sentence]"

## 1.2 STRATEGIC OPTIONS

Present exactly 3 paths. For each:
- **Name it** (memorable, not generic)
- **What it means**: 2-3 sentences
- **Why the data supports it**: Reference specific signals
- **The trade-off**: What you give up
- **Probability of success**: High / Medium / Low with reasoning

## 1.3 THE RECOMMENDATION

Pick one. Defend it.
- **The recommendation**: One decisive sentence
- **Why this path**: What makes this the right bet
- **The positioning**: Where should this brand stand? One sentence.
- **What competitors will do**: And why your recommendation still wins

End with: "The strategic bet: [one sentence]"

## 1.4 COMPETITIVE LANDSCAPE

For the top 3 competitors or competitive forces:
- **[Competitor/Force]**: What they'll likely do, and how the recommended strategy counters it
- Which competitor is most dangerous and why

## 1.5 RISK FACTORS

- **Kill signals**: What metrics or events mean this strategy is failing?
- **The unhedgeable risk**: The ONE risk with no safety net. Name it honestly and say what the client should do if it hits.
- **The one thing that could change everything**: What single event invalidates this?

# PART 2: CREATIVE BRIEF
*From your Executive Creative Director*

The creative brief MUST build directly on the strategic recommendation above. Do not introduce a new direction — extend and activate the strategy.

## 2.1 WHERE TO PLAY: Cultural Territory

Based on the strategic recommendation, map the creative territory:
- **Hot Zones**: Dominant topics — lead with authority
- **Opportunity Zones**: Emerging topics — early mover advantage
- **Avoid Zones**: Only if the client's challenge intersects with a non-obvious risk

End with: "Territory Recommendation: [specific territory] because [data-backed reason]"

## 2.2 WHEN TO MOVE: Momentum Timing

Based on empathy distribution and emotional climate:
- Identify the timing zone (Engage Now / Wait / Proceed with Caution)
- Factor in velocity and longevity

End with: "Timing Recommendation: [decision] because [data-backed reason]"

## 2.3 THE VOICE: Creative Direction

- **The Posture**: Is this brand whispering or shouting? One sentence a writer could use to gut-check every headline.
- **The Emotional Frequency**: What specific emotion should this work activate? Not "inspire" — be precise. Restlessness? Relief? Defiance?
- **Reference Point**: One real cultural artifact (show, song, meme, moment) that captures the tone. Not to copy — as a tuning fork.

End with: "This work should feel like: [one vivid sentence]"

## 2.4 THE UNEXPECTED ANGLE

This is where you earn the fee:
- **Contrarian Take**: What challenges conventional thinking
- **Data Tension**: A contradiction in the data
- **Competitor Blind Spot**: What they're missing
- **Creative Spark**: One bold idea that ONLY works in this specific moment

ANTI-STALENESS CHECK: Don't anchor on the obvious trending topic. Use the CREATIVE OPPORTUNITY MAP — [OPPORTUNITY] topics are your hunting ground, [SATURATED] topics are where you should NOT start.

End with: "The non-obvious move: [one sentence]"

## 2.5 CREATIVE PRECEDENT LENS

If CREATIVE PRECEDENTS are provided, select the 3 most relevant:
- **[Campaign] ([Brand], [Year])** — [Cultural tension]
  *Applies because:* [Structural parallel]

Then: **Structural pattern to steal:** [The underlying mechanic to apply]

## 2.6 MAKE IT REAL

**Opening Hooks (3 options):**
- One leading with tension
- One leading with aspiration
- One provocative/contrarian

**Campaign Concepts (3-4 concepts):**
For each concept:
- **Name**: A campaign name that could go on a brief
- **The Concept**: One paragraph. What is it, what does it look like, why does it work right now? Must feel like it could ONLY exist this week. Must directly activate the strategic recommendation from Part 1.
- **Why This Moment**: One sentence connecting it to a specific data signal
- **Steal This Line**: One sentence ready for a deck. Must make someone uncomfortable to say out loud.

Each concept should represent a genuinely different creative territory — not three versions of the same idea at different volume levels. One might be provocative, one might be emotional, one might be structural. Give the client real choices.

# PART 3: COMMS PLAN
*From your Comms Planner*

The comms plan MUST distribute the campaign concepts from Part 2 and support the strategic recommendation from Part 1. This is the deployment plan for the creative work above.

## 3.1 ATTENTION MAP

Using SOURCE DISTRIBUTION and engagement data:
- **Conversation centers**: Top 3-4 platforms driving volume. With data.
- **Signal quality**: Which sources generate engagement vs. just noise?
- **Dead zones**: Where NOT to spend — channels that look obvious but data shows low engagement.

End with: "Concentrate force on: [channels] because [data reason]"

## 3.2 TIMING INTELLIGENCE

- **Launch window**: Based on velocity, when to enter
- **Conversation lifecycle**: Where is this topic? (Emerging → Accelerating → Peak → Declining)
- **Counter-programming windows**: When is competition quietest?

End with: "Deploy on: [specific timing] because [data reason]"

## 3.3 CHANNEL MIX

| Channel | Role | Content Format | Investment Level | Why (cite data) |
|---------|------|---------------|-----------------|-----------------|
| Reddit | Seed / Credibility | Long-form commentary | Medium | 18% source share, 4x avg engagement |

Maximum 5 channels. Include one whitespace channel from the CREATIVE OPPORTUNITY MAP.

## 3.4 THE 72-HOUR LAUNCH SEQUENCE

Deploy the campaign concepts from Part 2:
- **Hour 0-4** (Seed): What goes out first, where, why
- **Hour 4-12** (Amplify): Second wave
- **Hour 12-24** (Respond): Reactive playbook
- **Day 2** (Sustain): Keep momentum
- **Day 3** (Pivot or Push): Double down or shift

## 3.5 WHITESPACE OPPORTUNITY

- **The gap**: A conversation no brand is participating in (use SCARCITY data and CREATIVE OPPORTUNITY MAP)
- **The angle in**: How the campaign concepts connect to that whitespace
- **The risk**: Why isn't anyone there already?

End with: "The whitespace play: [one sentence]"

## 3.6 MEASUREMENT SIGNALS

- **Green light**: What confirms the plan is working in 24 hours
- **Yellow light**: Signals to tweak
- **Red light**: Signals to pause

# THE BOTTOM LINE

One paragraph addressed directly to the decision-maker. What to do, why now, and what happens if they don't. This should synthesize all three parts into a single, urgent call to action.

End with: "Powered by Moodlight Full Deploy™"

QUALITY CHECKS:
- The creative brief must activate the strategy, not ignore it.
- The comms plan must distribute the creative concepts, not a generic message.
- Every recommendation must cite specific data from the intelligence snapshot.
- Delete any sentence that could appear in another brand's plan this week.
- If any section contradicts another section, fix it before delivering.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "full_deploy"
        return result
