"""
agents/seo_strategist.py
The SEO Strategist — real-time cultural signals mapped to search
opportunities. Identifies what people are about to search for before
keyword tools catch up. Predictive SEO built from live data.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class SEOStrategistAgent(MoodlightAgent):

    agent_name = "seo_strategist"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are an SEO strategist who understands that every keyword "
        "tool on the market is looking in the rearview mirror. Search "
        "volume data has a 30-90 day lag — by the time Ahrefs shows you "
        "a rising keyword, ten competitors are already publishing for it. "
        "You read cultural velocity signals to predict what people will "
        "search for BEFORE the volume shows up in any tool. You believe "
        "the best SEO strategy isn't about optimizing for what people "
        "searched last month — it's about owning the rankings for what "
        "they'll search next month. You build search strategies that "
        "feel like time travel to anyone still using traditional keyword "
        "research."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand, category, or search goals")
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

        return f"""Build a predictive SEO strategy for:
"{user_input}"

{context}

Using the real-time intelligence above, deliver an SEO strategy built from cultural velocity signals — not last month's keyword data.

## 1. THE SEARCH LANDSCAPE — RIGHT NOW

What the cultural data reveals about search behavior in this space:

- **Rising Signals → Rising Searches**: Which cultural topics in this category are gaining velocity? These are the topics where search volume is about to spike. Identify 5-7 emerging search themes with evidence from the velocity and scarcity data.
- **Saturated Signals → Saturated SERPs**: Which topics have high density (everyone's talking about them)? These are the keywords where every competitor is already publishing. Competing here is expensive and slow.
- **High Scarcity = Low Competition**: Which cultural conversations have high interest but low content supply? These are the search terms where you can rank fast because nobody's publishing quality content yet.
- **Fading Signals → Fading Search Volume**: Which topics are losing cultural velocity? If you're investing SEO resources here, you're chasing declining traffic.

End with: "The search opportunity: [one sentence on where to invest]"

## 2. PREDICTIVE KEYWORD CLUSTERS

5-7 keyword clusters built from cultural velocity signals — these are the topics that will drive search volume in the next 30-60 days:

For each cluster:
- **Cluster Theme**: The cultural conversation driving this search behavior
- **Predicted Search Terms**: 5-8 specific long-tail keywords and queries people will search (frame as questions, comparisons, and "how to" queries where appropriate)
- **Search Intent**: Informational, commercial, or navigational — what does the searcher actually want?
- **Cultural Evidence**: What specific velocity, scarcity, or trend signal predicts this search demand?
- **Competition Window**: How long before traditional SEO tools pick this up and competitors flood in?
- **Content Format**: What format will win this SERP — long-form guide, comparison post, listicle, video, FAQ?

## 3. TOPIC CLUSTER ARCHITECTURE

How to structure content for maximum search authority:

- **Pillar Page**: The main topic page that establishes authority. Define the target keyword, scope, and angle.
- **Cluster Pages**: 6-8 supporting pages that link back to the pillar. Each targeting a specific long-tail keyword from the clusters above.
- **Internal Linking Strategy**: How the pages connect and pass authority.
- **Content Gaps**: What your competitors are missing that you can own — based on cultural scarcity signals.

## 4. SERP OPPORTUNITY MAP

Where to win in search results beyond just ranking #1:

- **Featured Snippet Opportunities**: Questions from the cultural conversation that Google will want to answer in a snippet. Write the exact questions.
- **People Also Ask**: Predicted PAA questions based on cultural conversation patterns.
- **Emerging Entities**: New brands, products, concepts, or terms in the cultural data that Google hasn't fully indexed yet — early-mover advantage.
- **Content Type Gaps**: Are competitors only publishing text? Could video, tools, or interactive content own this space?

## 5. THE 30-DAY SEO SPRINT

Concrete publishing plan prioritized by impact and competition window:

- **Week 1 — Grab Now**: 2-3 pieces targeting high-scarcity, rising-velocity topics. These have the shortest competition window.
- **Week 2 — Build Authority**: 2-3 pieces that establish your pillar content and topic cluster foundation.
- **Week 3 — Own the Questions**: 2-3 pieces targeting featured snippet and PAA opportunities.
- **Week 4 — Expand & Defend**: 2-3 pieces that deepen cluster coverage and target long-tail variations.

For each piece: target keyword, search intent, content format, cultural signal that justifies priority.

## 6. MEASUREMENT & VELOCITY TRACKING

How to know if this strategy is working — and when to pivot:

- **Leading Indicators**: Cultural velocity signals to watch — if these accelerate, double down. If they fade, pivot.
- **Ranking Targets**: Realistic timeline for ranking based on competition level.
- **Kill Criteria**: When to abandon a keyword cluster because the cultural signal has faded or competition has arrived.
- **Next Wave**: What to watch for as the next round of search opportunities based on early-stage cultural signals.

End with: "Powered by Moodlight Search Intelligence"

QUALITY CHECKS — read before you finalize:
1. Traditional SEO strategy can be done with a keyword tool and a spreadsheet. This strategy must deliver what those tools cannot — predictive search intelligence from cultural signals not yet in keyword data. Ahrefs-derivable recommendations fail.
2. Run the inevitability test on the top 3 predictive keyword clusters: once stated, does an SEO lead nod because it's obviously where search volume is about to spike, or squint because it's clever? Obvious wins — but only if the cluster is invisible in traditional tools today.
3. Run the substitution test on the cluster themes: swap in a direct competitor's site. If the clusters still work, rewrite until they only fit THIS brand's domain authority and content permission.
4. Each cluster must cite the specific velocity/scarcity signal that predicts it. Uncited clusters fail — they're keyword-tool output wearing a cultural wrapper.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "seo_strategy"
        return result
