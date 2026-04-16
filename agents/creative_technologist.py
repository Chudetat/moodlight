"""
agents/creative_technologist.py
The Creative Technologist — tech stack recommendations, prototype
specs, feasibility and build-risk analysis, build-vs-buy calls, and
implementation roadmaps for creative concepts grounded in real-time
cultural signals.

Different from the CCO (what the idea is) and the Pitch Builder (how
to sell the idea). This agent answers: can we actually build it, with
what, how fast, and what breaks along the way.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class CreativeTechnologistAgent(MoodlightAgent):

    agent_name = "creative_technologist"
    model = "claude-opus-4-6"
    max_tokens = 8000

    system_prompt = (
        "You are a creative technologist who has shipped interactive "
        "work into the real world and watched just as many concepts die "
        "in the build phase. You translate cultural ideas into technical "
        "plans. You know the difference between a prototype and a "
        "production system, between a feature that demos well and one "
        "that actually scales, and between a platform that's hype and a "
        "platform that's load-bearing. You are brutally honest about "
        "build risk, you always push for the smallest prototype that "
        "proves the idea, and you never confuse novelty for feasibility. "
        "You read live cultural signals to pressure-test whether a "
        "concept will still matter by the time it ships."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — describe the concept, brand, or build question")
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

        return f"""Build a creative technology plan for:
"{user_input}"

{context}

Using the real-time intelligence above to pressure-test cultural timing and relevance, translate this brief or concept into a technical execution plan. If the input is a concept, figure out how to build it. If the input is a brand with no concept, propose the most technically interesting build that the live cultural signals support.

## 1. TECH STACK RECOMMENDATION

Name the specific stack this build needs. No generic "use a modern framework" hand-waving.

- **Core Stack**: The frontend, backend, and data layer components. Name specific technologies (e.g. Next.js 16, Supabase, Vercel Edge Functions, Cloudflare R2, pgvector) and explain why each was chosen for this specific build.
- **AI / ML Components**: If the concept involves AI, name the models (e.g. Claude Opus 4.6, Whisper, Stable Diffusion 3, a custom fine-tune) and the inference pattern (real-time, batch, edge, server). Justify the cost/latency trade-off.
- **Creative / Rendering Layer**: If the build involves generative visuals, interactive media, AR/VR, WebGL, or real-time graphics, name the specific engines, libraries, or SDKs (e.g. Three.js, Unreal, TouchDesigner, Unity, 8thWall).
- **Integrations**: External APIs and platforms this build depends on. For each, flag rate limits, pricing tiers, and the risk of the platform changing terms mid-build.
- **Stack Risk**: Which components of this stack are load-bearing vs. swappable, and which vendors would be catastrophic to lose mid-build.

## 2. PROTOTYPE SPEC

Define the smallest thing that proves the idea works. The goal is a prototype that can be built in days, not months.

- **The One Thing to Prove**: Name the single technical or experiential risk the prototype exists to de-risk. Everything else is out of scope.
- **Prototype Scope**: What the prototype does and — more importantly — what it doesn't do. Be ruthless.
- **Success Criteria**: How the team will know the prototype succeeded or failed. Quantify where possible.
- **Estimated Build**: Team shape (how many eng/design/producer), rough duration, and what gets cut if the build slips.
- **What Gets Learned**: The specific question the prototype answers that no desk research could.

## 3. FEASIBILITY & BUILD RISK

Be brutally honest. If this concept is technically reckless, say so.

- **Green-Lit**: Components of this build that are well-understood and low-risk. The team has shipped this before.
- **Yellow**: Components that work in isolation but create risk when combined or scaled. Name the integration risks specifically.
- **Red Flags**: Components that will likely break, miss deadline, or cost 5x the estimate. For each red flag, name the fallback.
- **Cultural Obsolescence Risk**: Using the live data above, judge whether the cultural moment this concept is tied to will still be relevant by the time the build ships. If velocity is already declining, flag it.
- **Regulatory / Platform Risk**: Any app store, ad platform, accessibility, or privacy constraint that could block the build or force a redesign late.

## 4. BUILD VS. BUY

Not everything should be built from scratch. Not everything should be bought.

- **Build**: Components of this concept that must be custom because they are the differentiator or the proprietary moment.
- **Buy**: Components that should be off-the-shelf because commoditized tools exist and custom-building them is pure cost.
- **Partner**: Components best handled through a specialist vendor or creative studio rather than in-house or off-the-shelf. Name the type of partner, not a specific company.
- **Build/Buy Decision Matrix**: For each major component, a one-line justification citing cost, speed, differentiation, and maintenance burden.

## 5. IMPLEMENTATION ROADMAP

A staged plan from green light to launch, not a vague timeline.

- **Phase 0 — Pre-Build (1-2 weeks)**: Discovery, technical spikes, vendor contracts, prototype sign-off.
- **Phase 1 — Prototype (time-boxed, see above)**: The de-risking build.
- **Phase 2 — Production Build**: Core functionality, integration, QA, load testing. Call out the specific gates that must clear before phase 3.
- **Phase 3 — Launch**: Soft launch, monitoring, feedback loop, public release.
- **Phase 4 — Post-Launch**: The first 30 days of live operation — what the team watches, what gets patched, what gets killed.
- **Kill-Switch Points**: At which phase gates the team should be willing to walk away if the build isn't working.

## 6. CROSS-SELL

End with: "Powered by Moodlight Creative Technology Intelligence"

QUALITY CHECKS — read before you finalize:
1. A creative technology plan is only useful if it names specific technologies, quantifies specific risks, proposes a specific prototype, and tells the team exactly when to walk away. Generic "use AI to do something with data" memos fail. Be honest about what will break.
2. Run the inevitability test on the "One Thing to Prove" in the prototype spec: once stated, does the team nod because it's obviously the load-bearing risk, or squint because it's clever? Obvious wins — if you're prototyping the wrong risk, you wasted the week.
3. Run the substitution test on the tech stack: could this same stack be recommended for a different brand's concept? If yes, rewrite until each choice is specifically justified by THIS concept's technical bet.
4. Every red flag must name a concrete failure mode AND a fallback. "This is risky" fails. "The 8thWall tracking won't hold above 60fps on iOS 17.3 — fallback is a static AR overlay with motion trigger" passes.
5. Kill-switch points must be specific phase gates, not vibes. If a producer can't point to the gate and say "we're at it," the plan failed.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "creative_technology_plan"
        return result
