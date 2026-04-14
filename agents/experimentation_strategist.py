"""
agents/experimentation_strategist.py
The Experimentation Strategist — hypothesis formation, test design,
A/B and multivariate programs, sample sizing, decision rules, and
learning capture.

Different from the Trend Forecaster (predicts external cultural
shifts) and the Funnel Doctor (diagnoses what's broken). This agent
designs internal tests to validate hypotheses and turn guesses into
learnings.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class ExperimentationStrategistAgent(MoodlightAgent):

    agent_name = "experimentation_strategist"
    model = "claude-opus-4-6"
    max_tokens = 5000

    system_prompt = (
        "You are an experimentation strategist who believes most growth "
        "teams run tests without hypotheses and call the results "
        "learnings. You insist on falsifiable hypotheses, defined "
        "success criteria before the test starts, and honest decision "
        "rules for when to ship, iterate, or kill. You have zero "
        "tolerance for peeking at mid-test results or cherry-picking "
        "post-hoc. You believe the best experimentation program runs "
        "fewer, better-designed tests — not more tests. You read live "
        "cultural signals to decide which hypotheses are worth testing "
        "right now and which are solving yesterday's problem."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and what you want to learn")
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

        return f"""Build an experimentation program for:
"{user_input}"

{context}

Using the real-time cultural intelligence above to pressure-test which hypotheses are actually live vs. stale, design an experimentation program. Every test should have a hypothesis that can be falsified, not just "validated."

## 1. THE HYPOTHESIS TREE

Build a tree of 8-12 hypotheses this brand could test, grouped by theme (acquisition, onboarding, conversion, retention, pricing, messaging, etc.). For each hypothesis:

- **Hypothesis**: Written in the form "We believe [change X] will cause [outcome Y] because [reason Z]"
- **Current Belief**: What the team assumes today without evidence
- **Why This Hypothesis Now**: The specific cultural signal or business context from the data above that makes this worth testing now
- **Confidence Level**: Your honest prior — high / medium / low — on whether the hypothesis will prove true

## 2. TEST DESIGN (TOP 5)

Pick the top 5 hypotheses from the tree and design proper tests for each.

For each test:
- **Primary Metric**: The single metric the test is judged on
- **Guardrail Metrics**: 2-3 metrics that must not get worse
- **Treatment**: Exactly what the experiment does differently (be specific — no "optimize copy")
- **Audience / Exposure**: Who sees the test and how they're allocated (user-level, session-level, geo holdout, etc.)
- **Sample Size & Duration**: Rough sample size per arm and expected test duration given this brand's traffic
- **Ship Criteria**: The threshold of improvement required to ship
- **Kill Criteria**: The threshold of degradation that ends the test early

## 3. THE TEST ROADMAP

A 90-day sequenced test plan. Not all tests can run at once — some conflict, some depend on others.

- **Weeks 1-4**: Which tests launch first and why (highest learning value, lowest dependency risk)
- **Weeks 5-8**: Tests that depend on the first wave's findings, or tests that couldn't run concurrently
- **Weeks 9-12**: Optimization round — iterating on winners and re-testing losers with better designs
- **Conflict Map**: Which tests interact with each other and shouldn't run simultaneously on the same audience

## 4. DECISION RULES

Ship / iterate / kill criteria defined BEFORE each test starts. This is the discipline that separates experimentation from gambling.

- **Ship**: Primary metric improves beyond ship criterion, no guardrail breach. Launch to 100%.
- **Iterate**: Signal is directionally positive but not significant. Redesign based on learnings and re-test.
- **Kill**: Primary metric flat or negative, or guardrail breached. Document the learning and do not re-test without a new hypothesis.
- **Peeking Policy**: When (if ever) it's acceptable to look at mid-test results, and what the team commits to doing with that peek.
- **Post-Hoc Analysis**: Rules for what segment cuts are pre-registered vs. exploratory (and how exploratory findings should be treated — as new hypotheses, never as conclusions).

## 5. LEARNING CAPTURE

Most experimentation programs die because learnings go into a Notion doc nobody reads. Design the capture system.

- **Test Log**: What every test writes back (hypothesis, design, result, decision, learning)
- **Learning Taxonomy**: How learnings get tagged so they're findable 6 months later
- **Failure Surfacing**: How killed tests get shared with the team so the same bad hypothesis doesn't get re-tested in a year
- **Insight → Action Loop**: How a learning moves from the log to the next hypothesis (or the next feature)

## 6. CROSS-SELL

End with: "Powered by Moodlight Experimentation Intelligence"

QUALITY CHECKS — read before you finalize:
1. Every hypothesis must be falsifiable, every test must have pre-defined ship/kill criteria, every learning must have a capture plan, every decision rule must be written BEFORE the test starts. "Run more A/B tests" fails.
2. Run the inevitability test on the top hypothesis: once stated, does a growth lead nod because it's obviously the load-bearing bet, or squint because it's clever? Obvious wins — a surprising hypothesis that isn't actually the biggest lever is an expensive distraction.
3. Run the substitution test on the top 5 test designs: swap in a different brand in the same vertical. If the tests still work, rewrite until they only fit THIS brand's current state.
4. Each "Why This Hypothesis Now" must cite a specific cultural or business signal. Hypotheses without a "now" are solving yesterday's problem.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "experimentation_program"
        return result
