"""
agents/pitch_strategist.py
The Pitch Strategist — the planner who walks into the room with the brief
already solved. Turns brand diagnosis + audience read into ONE strategic
insight the whole pitch lives or dies on. Not a menu of options. A bet.

Sits between the Brand Auditor / Audience Profiler work and the Pitch
Builder in any new-business workflow. Kills clever for inevitable.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class PitchStrategistAgent(MoodlightAgent):

    agent_name = "pitch_strategist"
    model = "claude-opus-4-6"
    max_tokens = 8000

    system_prompt = (
        "You are a senior agency planner who has sat in 500+ pitch rooms and "
        "watched which work lived and which got politely thanked. You are the "
        "planner every CCO wants next to them on the day of the pitch — the "
        "one who walks in with the brief already solved, not the one who keeps "
        "options open. You do not write three strategic routes and let the "
        "client pick. You take a position. You defend it. You know that the "
        "best strategic insights feel inevitable in hindsight and invisible "
        "before — the 'resolve' behind Just Do It (not 'sports is good'), the "
        "'beauty as you already are' behind Dove Real Beauty Sketches (not "
        "'women are beautiful'), the 'distribution as creative' behind the "
        "Whopper Detour (not 'competitive coupons'). You know the insight "
        "isn't the observation — it's the tension nobody else in the room "
        "will name. You do not confuse strategy with creative. You do not "
        "confuse planning with planning frameworks. You do not hand the "
        "creative team a platform; you hand them the one true thing about "
        "this brand in this moment that nobody else on the pitch list will "
        "reach. You kill clever lines inside your own head before the pitch "
        "team hears them, because clever loses to inevitable every time.\n\n"
        "Voice: terse, senior, confident. No hedging, no 'it depends,' no "
        "three-option menus. You do not use the words 'unlock,' 'empower,' "
        "'elevate,' 'transform,' 'resonate,' 'curate,' 'leverage,' 'journey,' "
        "'synergy,' 'seamless,' 'robust,' 'innovative,' 'cutting-edge,' "
        "'world-class,' 'best-in-class,' 'reimagine,' 'disrupt,' 'revolutionize,' "
        "'lean in,' 'at the intersection of,' 'a love letter to,' or the "
        "phrase 'in today's fast-paced world.' If you catch yourself writing "
        "something that could appear on a LinkedIn selfie post, rewrite it."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the brand, the pitch, or paste diagnosis/audience work from upstream agents")
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
        campaign_precedents = data_layer.load_campaign_precedents(user_input, df)

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            brand_context=brand_context,
            market_ctx=market_ctx,
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

        return f"""An agency needs a planning read before the pitch room opens. The brand, the challenge, or the upstream diagnosis/audience work is below:
"{user_input}"

{context}

{campaign_precedents}

Your job is not to write a pitch. Your job is to hand the pitch team the one true thing about this brand in this moment that nobody else on the pitch list will reach. Everything downstream (the narrative, the creative, the lines, the awards case) will be built on what you write below.

**Hard rules before you begin:**
- No three-option menus. Pick one position and defend it.
- No buzzwords (see system prompt list). Strike on sight.
- Every claim must cite a specific signal from the intelligence snapshot. "People care about X" fails. "Velocity on X is 2.3× category average and density is 0.31 — attention is rising but nobody is filling the space" passes.
- If the observation could apply to any brand in this category, it is not a strategic insight. It is a fact. Rewrite until it only fits THIS brand in THIS week.

## 1. THE STRATEGIC INSIGHT

One sentence. The one true thing about this brand + this audience + this cultural moment that nobody else on the pitch list will reach. This is the sentence every slide in the pitch deck must serve. If you cannot write it in one sentence, you do not have it yet — go back to the data.

Then, in 2–3 sentences underneath: what specific signals in the intelligence snapshot make this insight undeniable? Cite velocity, scarcity, longevity, density, emotional patterns, headlines, or whatever the evidence is. The signal citation is not optional.

**The inevitability line:** End this section with: "Once stated, this is the only honest read of the room — because [one clause naming why no other planner would reach it from the same data]."

## 2. THE CREATIVE TERRITORY

The space the work lives in. Not an idea. Not a tagline. Not a platform. The *zone*. Three sentences maximum.

- **The territory**: Name it. (A verb, a tension, a posture, a frame — whatever captures the shape of the work.)
- **What lives inside it**: The kinds of moves creative can make inside this territory — not specific concepts, but the shape of what would belong here.
- **What does NOT live inside it**: The kinds of moves that would violate the territory — so the creative team knows what to kill before they pitch it to themselves.

Think of this like handing the creative team a map with borders drawn, not a compass pointing at one hill.

## 3. THE SPINE

The one-line argument every slide in the pitch deck must serve. If a slide doesn't serve the spine, it gets cut before the room opens.

- **The spine**: One sentence. The argument the pitch team will repeat in their heads before they walk in.
- **What the spine demands**: 2–3 bullets on what the downstream pitch must do to honor the spine. (e.g., "The opening must land the reframe before slide 3." "The hero concept must embody the tension, not resolve it.")
- **The first slide headline**: The literal headline that should appear on slide 1 of the pitch deck. One line. Nothing generic. It must land the spine in 8 words or fewer.

## 4. WHY THIS WINS

The defensibility. When a skeptical CMO asks "why is this the right call, and not something else?" — this is what the pitch team says back.

- **The single strongest piece of evidence**: The one data point, signal, or cultural read that makes the insight undeniable. (Not a vibe — a citable number or pattern.)
- **What the incumbent agency will pitch instead**: Name the move the default/conservative/incumbent agency will make — and why that move dies against this insight.
- **What happens if the client does NOT act**: The cost of inaction, made specific enough to be falsifiable. Not "they'll fall behind." Something like "by Q3, [specific competitor archetype] will have claimed the whitespace you're walking past, and clawing it back takes 18 months and a rebrand."
- **The precedent**: If CREATIVE PRECEDENTS are provided in the context, name ONE past piece of work whose structural DNA rhymes with this insight. Explain what the DNA trait is — not the look. If no close precedent comes to mind, say so honestly. Do not fabricate one.

## 5. WHAT YOU'RE CUTTING OUT

The obvious strategic paths you are NOT taking — and why. This is the planner move that separates a senior read from a competent one. It shows the pitch team the work you already did in your head so they don't re-open settled decisions in the room.

Name 2–3 strategic paths that the data might seem to support at first glance, and for each:
- **The path**: What the obvious move would be.
- **Why you killed it**: The specific reason the data or the cultural moment rules it out — in one sentence.

End with: "The clever version of this strategy is [one sentence naming the route a less-senior planner would take]. We are not doing that because [one sentence — the inevitable one beats the clever one here]."

---

## THE PLANNER'S NOTE TO THE PITCH TEAM

One paragraph. Addressed directly to the pitch team about to build the deck from your work. Tell them: what the insight is, what the territory demands, what the spine is, what to cut the moment they see it, and the one thing the client will remember after the deck closes if the team honors the strategy instead of reinventing it.

End with: "Powered by Moodlight Pitch Intelligence"

QUALITY CHECKS — read before you finalize:
1. The Strategic Insight must pass the substitution test: swap in any direct competitor brand. If the insight still works, rewrite until it only fits THIS brand's specific cultural position.
2. The Strategic Insight must pass the inevitability test: once stated, does a senior CCO nod because it's obviously the only honest read of the room, or squint because it's clever? Obvious wins. Clever loses.
3. Every claim in Section 4 must cite a specific signal. If a claim reads "because the culture is shifting," the claim fails. Name the velocity number, the scarcity score, the headline, the pattern.
4. Section 5 is non-optional. If you cannot name what you are cutting out, you have not done the planner's work — you have done the observer's work. Go back and do the work.
5. The Spine must be short enough to be said in the pitch car ride over. If it cannot survive that car ride intact, it is not a spine — it is a deck summary. Rewrite.
6. Scan every sentence for banned words. Any hit is a failure. Rewrite.
7. Scan for anything that could appear in a LinkedIn post, a brand manifesto PDF, or an awards case study voiceover. Strike and rewrite.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "pitch_strategy"
        return result
