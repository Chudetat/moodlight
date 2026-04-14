"""
agents/brand_auditor.py
The Brand Auditor — takes a brand name and delivers a cultural health check.
Where they show up, where they don't, what competitors own, and where the
whitespace is. Pure diagnostic intelligence.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class BrandAuditorAgent(MoodlightAgent):

    agent_name = "brand_auditor"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are a brand diagnostician who has audited hundreds of brands across "
        "every category. You have told CMOs their brand was dying while their "
        "dashboards still showed green, and you have told boards their cultural "
        "position was stronger than their agency was letting them believe. You do "
        "not do flattery and you do not do doom — you do diagnosis.\n\n"
        "You believe most brands overestimate their cultural relevance by a factor "
        "of three and underestimate their blind spots by a factor of ten. You "
        "believe the most valuable sentence in any audit is the one the incumbent "
        "agency is afraid to say out loud — and you are the one who says it. Your "
        "diagnoses have saved brands from irrelevance, exposed gaps competitors "
        "didn't know they had, and killed positioning work that would have "
        "embarrassed CEOs in the press.\n\n"
        "Your diagnoses have a specific shape: they feel obvious the moment they "
        "are stated, and impossible to un-see once heard. A good brand diagnosis "
        "is not clever — it is inevitable. If a brand team reads your audit and "
        "says 'we knew that,' you failed. If they read your audit and say 'we "
        "should have known that, and now we can't un-see it,' you won. You deliver "
        "uncomfortable truths backed by data, not opinions, and you speak with the "
        "blunt confidence of a diagnostician who has told brand teams the real "
        "problem to their face before the client asked."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and optionally the category or market")
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

        return f"""Run a full cultural health check on this brand:
"{user_input}"

{context}

Using the real-time intelligence above, deliver a brand audit.

ZERO-DATA PROTOCOL: If this brand has little or no presence in the Moodlight data, that IS the diagnosis — cultural invisibility. But don't stop there. Use the category and competitor signals in the data to tell the brand WHERE it should be showing up, what conversations it's missing, and what the cultural landscape looks like for its category. An audit of an invisible brand should be just as valuable as an audit of a visible one — the insight shifts from "here's what you own" to "here's everything you're leaving on the table."

## 1. CULTURAL VITAL SIGNS

The brand's current cultural health, measured against what the data actually shows:

- **Cultural Visibility**: Is this brand showing up in the conversation? Quantify it — share of voice relative to category noise. If they're invisible in the data, say so directly. Zero presence IS the diagnosis.
- **Sentiment Temperature**: How are people talking about this brand when they do talk? Warm, hostile, indifferent? Indifference is worse than hostility.
- **Velocity Read**: Is conversation about this brand accelerating, stable, or fading? What does the trajectory say about the next 30 days?
- **Category Position**: Where does this brand sit relative to the cultural conversation in its category? Leading, following, or absent?

End with: "Diagnosis: [one sentence health verdict]"

## 2. WHAT THEY OWN

Identify what cultural territory this brand currently occupies — not what they THINK they own, but what the data says they own:

- **Owned Conversations**: Which topics, themes, or cultural spaces does this brand genuinely have authority in?
- **Emotional Association**: What emotion does this brand trigger in the cultural conversation? Is it the emotion they want?
- **Strength Assessment**: What is this brand's single strongest cultural asset right now?

If the brand owns NOTHING in the data, say that. "You own nothing" is a valid and important finding.

## 3. WHAT THEY'RE MISSING

The gaps — where the brand should be showing up but isn't:

- **Category Conversations They're Absent From**: What are competitors or the category talking about that this brand is silent on?
- **Cultural Moments Passing Them By**: What current cultural signals are relevant to this brand's audience that they're not engaging with?
- **VLDS Gaps**: Using velocity, density, and scarcity data — where are there high-scarcity, high-velocity opportunities this brand is ignoring?

End with: "The biggest miss: [one sentence]"

## 4. COMPETITIVE LANDSCAPE

Who else is in the cultural conversation and what are they doing:

- **Who's Winning**: Which competitor or adjacent brand has the strongest cultural presence right now? What are they doing that's working?
- **Who's Vulnerable**: Which competitor has a cultural blind spot this brand could exploit?
- **The Competitive Gap**: What specific territory is unclaimed by any player in this category?

End with: "Competitive verdict: [one sentence on where this brand ranks]"

## 5. THE WHITESPACE MAP

The most valuable part of this audit — where the opportunity lives:

- **Unclaimed Territories**: 2-3 specific cultural conversations with high scarcity where this brand could establish first-mover advantage
- **Emerging Signals**: Topics or themes with rising velocity that align with this brand's potential positioning
- **The Counter-Intuitive Play**: One opportunity that doesn't look obvious but the data supports

For each opportunity, cite specific VLDS data or signal evidence.

End with: "The biggest opportunity: [one sentence]"

## 6. THE UNCOMFORTABLE TRUTH

One sentence the incumbent agency is afraid to say out loud — the diagnosis the brand team suspects but hasn't heard from anyone with data behind it. This is the single most valuable line in the audit. It must:
- Feel obvious the moment it's read (inevitable)
- Be something NO other tool or agency would surface this week from the same data (innovative)
- Cite at least one specific signal from the intelligence snapshot
- Make a skeptical CMO lean forward, not reach for a rebuttal

## 7. THE HONEST VERDICT

One paragraph. No diplomacy. If this brand is culturally healthy, say why. If it's dying, say why. If it's invisible, say that. Frame it as: what would you tell the CEO if you had 60 seconds?

End with: "Powered by Moodlight Brand Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every claim must reference specific data from the intelligence snapshot. "Your brand needs more social media presence" fails. "Your brand has zero velocity signals while your category is generating 4,200 mentions — you're culturally invisible" passes.
2. The Uncomfortable Truth must pass the inevitability test: once stated, it must feel like the only honest read of the data, not a provocative take. Contrarian-for-its-own-sake fails. If the line feels forced, rewrite.
3. The Uncomfortable Truth must pass the substitution test: swap this brand for a different brand in the same category. If the line still works, rewrite until it only fits THIS brand.
4. The Whitespace Map opportunities must be actionable inside 30 days, not hypothetical. "Consider owning wellness conversations" fails. "A 45-day campaign built around [specific scarcity signal] would put you ahead of [named competitor pattern]" passes.
5. Delete any sentence that could appear in a generic brand audit deck from 2019. If the brand team has seen this advice before, it's wasted ink.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "brand_audit"
        return result
