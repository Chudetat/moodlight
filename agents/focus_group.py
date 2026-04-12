"""
agents/focus_group.py
The Focus Group — synthetic focus group grounded in live cultural signals.
Convenes a panel of personas anchored in what real audiences are actually
talking about this week, reacts to your creative, and tells you which
hypotheses still need to go to real humans.
Directional pre-research gut check, NOT a replacement for real research.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class FocusGroupAgent(MoodlightAgent):

    agent_name = "focus_group"
    model = "claude-opus-4-6"
    max_tokens = 5500

    system_prompt = (
        "You run a synthetic focus group grounded in Moodlight's live "
        "cultural signal data. You convene a panel of 5-7 personas, each "
        "anchored in what real audiences in that demographic are ACTUALLY "
        "talking about this week in the data — not generic demographic "
        "stereotypes, not training-data caricatures. Every persona you "
        "build must reference at least one specific live signal (a topic, "
        "a theme, a story, a conversation trend) that real people like "
        "them are currently engaging with. You react to creative work the "
        "way real humans do: with contradictions, hesitations, tangents, "
        "second thoughts, and occasional bluntness. You never smooth the "
        "panel into consensus. You let the outliers stay outlier. You "
        "include at least one skeptic who picks the work apart. You "
        "include at least one uncomfortable truth about how the work "
        "might land. You NEVER produce quantitative scores (no '67% "
        "would buy this') — that's false precision and it misleads teams. "
        "You frame everything qualitatively. And you always end every "
        "session with an explicit reminder that this is a directional "
        "pre-research gut check, NOT a replacement for real research — "
        "and you name the top 5 hypotheses this synthetic panel could not "
        "resolve that the team must put to actual humans before shipping."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — paste the creative asset and name the brand")
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

        return f"""Convene a synthetic focus group for this creative work:
"{user_input}"

{context}

Using the live cultural intelligence above to ground each persona in what real audiences are ACTUALLY talking about this week, run a full session.

## 1. PANEL COMPOSITION

Build 5-7 personas for this session. For each:

- **Name, age, occupation, location** — specific, not generic
- **Demo snapshot**: Household, income range, relationship status, education if relevant
- **Media diet**: What they actually consume (specific shows, creators, podcasts, platforms)
- **Current cultural anxieties**: What's on their mind this month — not generic, specific
- **Live-signal anchor (non-negotiable)**: One specific topic, theme, story, or conversation from the Moodlight data above that people like this persona are engaging with right now. Cite the signal. This is what separates a grounded persona from a stereotype.

Include:
- At least one deliberate SKEPTIC / outlier who will push back hard
- Demographic range that matches the brief (or, if auto-selecting, tell the team who you picked and why)

End this section with a **Source Transparency Block**: Which specific live signals from the data shaped this panel? Name 3-5 signals and which personas they informed.

## 2. FIRST-IMPRESSION REACTIONS

For each persona, 3-5 verbatim-style reactions to the creative work. Not averaged. Not aggregated. Individual voices.

Format each reaction like you would in a real focus group transcript:
- Include tone, hesitation, body-language cues where relevant ("pauses, then:", "half-laughs", "rereads it twice")
- Let personas contradict themselves — real people do
- Let them go on tangents that reveal what they actually care about
- Do NOT smooth into clean ad-friendly quotes

End each persona's section with a **"Walk-Away Sentence"** — the single sentence this person would tell a friend about the work over coffee tomorrow. This is the only thing they'll remember.

## 3. WHAT LANDS / WHAT DOESN'T

Patterns across the panel — but NOT averages. Named observations:

- **What Multiple People Responded To**: Specific elements (a line, a visual, a premise) that got positive reactions from more than one persona. Cite which personas.
- **What Fell Flat**: Specific elements nobody cared about or didn't notice. Cite the silence.
- **Generational or Cultural Splits**: Where the panel divided cleanly along demographic or psychographic lines. Name the split.
- **Cultural Mismatches**: Things the creative team almost certainly didn't realize would read differently to this audience than intended. These are the most valuable findings.

## 4. THE SKEPTIC READ

Hand the mic to the skeptic persona from section 1 and let them go. Brutal, specific pushback:

- What do they think the work is REALLY saying? (Often uncomfortable — let it be uncomfortable.)
- Where does it feel inauthentic, corporate, or trying too hard?
- What would it take to win them over? (Sometimes the answer is "nothing" — and that's okay. Not every audience needs to be won over.)
- One uncomfortable truth about the work that the skeptic surfaces that the rest of the panel wouldn't say out loud.

## 5. RISK FLAGS

Where this creative could go sideways culturally, informed by live signals:

- **Cultural Timing Risk**: Is there anything in this week's culture (cite the signal) that could make this work land wrong RIGHT NOW? (Headlines, current events, ongoing controversies, community conversations.)
- **Groups Who Might React Badly**: Specific communities, subcultures, or demographics who might read this differently than intended. Why.
- **Phrases, Images, or Framings at Risk**: Elements that could get misread, screenshot-dunked, or recontextualized hostilely. Call them out specifically.
- **The Likelihood & Severity Read**: For each risk — is it a small chance of small damage, or a real chance of real damage? Don't cry wolf, but don't hide the wolf either.

## 6. THE RESEARCH AGENDA + CROSS-SELL

Explicit framing reminder: **This was a directional pre-research gut check. It is NOT a substitute for real human research.** A synthetic panel cannot replace real interviews, diary studies, or observation. Its job is to help you ask better questions faster, cheaper.

**Top 5 questions this synthetic panel couldn't resolve** — the real hypotheses the team now needs to put to actual humans before shipping:

For each question:
- The question itself, phrased clearly
- Why the synthetic panel couldn't resolve it (what's the ambiguity?)
- What kind of real research would answer it (in-depth interviews, diary study, quant survey, social listening, co-creation session) — pick the cheapest format that credibly settles the question

End with: "Powered by Moodlight Focus Group — grounded in live cultural signals. Directional, not definitive."

QUALITY CHECK: A synthetic focus group that sounds like a clean ad testimonial has failed. Real people hedge, contradict, drift, get defensive, and say surprising things. If every persona reacts the same way or speaks in marketing language, rebuild the panel. Each persona must feel like a specific human shaped by a specific live signal, not a demographic checkbox.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "focus_group"
        return result
