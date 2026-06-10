"""
agents/base_agent.py
Base class for all Moodlight agents.
Handles the shared orchestration: validate → load data → build prompt → call LLM → format output.
"""

import os
import re
from datetime import datetime, timezone
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

TRAINING_DATA_BAN = (
    "Your ONLY sources of truth are the Moodlight intelligence data provided in the user prompt. "
    "Do NOT inject facts, events, corporate actions, controversies, or narratives from your training data. "
    "Your training knowledge is stale — presenting it as current intelligence destroys credibility. "
    "If the data doesn't cover something, build from what IS there. Never fill gaps with training-data knowledge."
)

NO_FOURTH_WALL = (
    "The reader is the operator/strategist using the deliverable, not a peer reviewer of the engine. "
    "Never expose the engine's deliberation or its internal data instruments to the reader. "
    "The following terms are banned EVERYWHERE in the output — in body text, parentheticals, "
    "section headers, bullet labels, table captions, and footnotes: 'the intelligence snapshot', "
    "'the snapshot', 'the dataset', 'in the entire dataset', 'across our intelligence', 'the data shows', "
    "'the data indicates', and internal data source names (Polymarket, VLDS, opp_map, etc.). "
    "Do NOT use 'VLDS Gaps', 'Snapshot Highlights', 'Dataset Findings' as section headers — "
    "use plain-English labels like 'Underserved Cultural Conversations' or 'Where the Conversation Is Quiet'. "
    "Banned deliberation parentheticals: '(despite X)', '(I considered Y but)', '(the data shows Z, however)'. "
    "Cite signals as cultural facts the buyer would recognize ('on X this week...', 'the most-engaged post "
    "about this topic...'), never as system outputs ('the snapshot shows...', 'the data indicates...')."
)

NO_INSTRUMENT_LEAKS = (
    "Never quote your own metric values to the reader. Banned parenthetical and bracketed patterns: "
    "'(scarcity 0.42)', '(MEDIUM opportunity)', '(363 mentions)', '(65K engagement)', '(density 0.85)', "
    "'(velocity 0.72)', '(longevity 0.83)', '(empathy 0.1/100)', '[OPPORTUNITY]', '[HIGH OPPORTUNITY]', "
    "or any exposure of system scores, percentiles, raw counts, or data-layer tags. Cite signals as "
    "content the buyer would recognize — 'this week's most-shared piece on X', 'the cultural "
    "conversation around responsible AI is accelerating but underserved' — NOT as instrumented data "
    "points. Engagement counts and scarcity scores belong in your analysis, never in the deliverable."
)

INEVITABILITY_BAR = (
    "THE BAR — read before you write anything: Every non-trivial insight you ship must be "
    "INNOVATIVE AND INEVITABLE. Innovative means no other tool or agency in this category "
    "would reach this same answer from the same data this week — if a competitor could ship "
    "it, it is wasted ink. Inevitable means that once you state the insight, it feels like "
    "the only right answer, as if it were always sitting there waiting to be named. Think "
    "Fearless Girl, Dove Real Beauty Sketches, Whopper Detour — obvious in hindsight, "
    "invisible before. That is the bar.\n\n"
    "Before you finalize ANY claim, recommendation, line, or idea, run two checks:\n"
    "  (1) The substitution test: could a competitor reach this same conclusion from the "
    "same data? If yes, rewrite.\n"
    "  (2) The inevitability test: does it feel like the only right answer once stated, or "
    "merely clever? If merely clever, rewrite.\n\n"
    "Three failure modes to actively avoid: (a) timid output hedged into safety, (b) generic "
    "best-practice every tool would have produced, (c) contrarian-for-the-sake-of-it that "
    "feels forced rather than inevitable. All three fail this bar. Your job is not to be "
    "clever. Your job is to surface the answer the operator cannot un-see."
)

# Keywords that trigger inclusion of regulatory guidance
_REGULATED_INDUSTRY_PATTERNS = re.compile(
    r"pharma|healthcare|medical|hospital|drug|rx|fda|"
    r"financial|banking|fintech|investment|insurance|"
    r"alcohol|spirits|beer|wine|liquor|"
    r"cannabis|cbd|marijuana|"
    r"legal\s+service|law\s+firm|attorney",
    re.IGNORECASE,
)


def get_regulatory_guidance(user_input):
    """Return regulatory guidance only if the user's input involves a regulated industry."""
    if _REGULATED_INDUSTRY_PATTERNS.search(user_input):
        from generate_strategic_brief import REGULATORY_GUIDANCE
        return f"\nINDUSTRY-SPECIFIC REGULATORY CONSIDERATIONS:\n{REGULATORY_GUIDANCE}\n"
    return ""


def _extract_text(response):
    """Concatenate the response's text blocks, skipping any non-text blocks.

    Opus models return a single text block (content[0]). Adaptive-thinking
    models (e.g. Fable 5) prepend a thinking block, so content[0] is NOT the
    deliverable — we must select by block type rather than position.
    """
    return "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    ).strip()


class MoodlightAgent:
    """Base class for Moodlight AI agents."""

    agent_name = "base"
    model = "claude-opus-4-6"
    fallback_model = None  # if set, used when the primary model refuses or returns no text
    max_tokens = 4000
    system_prompt = ""

    def _build_system_prompt(self):
        """Combine agent-specific system prompt with universal directives."""
        return (
            f"{self.system_prompt}\n\n{TRAINING_DATA_BAN}\n\n"
            f"{NO_FOURTH_WALL}\n\n{NO_INSTRUMENT_LEAKS}\n\n{INEVITABILITY_BAR}"
        )

    def _render_upstream_context(self, upstream_context):
        """Render upstream agent outputs from prior runs in this session as
        an additive preamble for the user prompt. The brief in the prompt
        below remains the source of truth; this is grounding, not replacement."""
        if not upstream_context:
            return ""
        # Cap payload per entry to prevent prompt bloat / abuse
        MAX_CHARS_PER_ENTRY = 8000
        MAX_ENTRIES = 5
        entries = [e for e in upstream_context if isinstance(e, dict) and e.get("output")]
        if not entries:
            return ""
        entries = entries[-MAX_ENTRIES:]  # keep most-recent if the list is longer
        parts = [
            "# PRIOR ANALYSIS FROM UPSTREAM AGENTS IN THIS SESSION",
            "",
            "The user has already run one or more Moodlight agents on this same brief. "
            "Their outputs are included below as additional grounding. Use this prior work "
            "to sharpen and build on — do NOT repeat it. The brief that follows in the main "
            "user prompt is still the source of truth; this section is additive context, not "
            "a replacement for the brief.",
            "",
        ]
        for item in entries:
            label = item.get("agent_label") or item.get("agent_id") or "Upstream Agent"
            output = str(item.get("output", "")).strip()
            if len(output) > MAX_CHARS_PER_ENTRY:
                output = output[:MAX_CHARS_PER_ENTRY] + "\n\n[... truncated ...]"
            parts.append(f"## From {label}")
            parts.append(output)
            parts.append("")
        parts.append("---")
        parts.append("")
        return "\n".join(parts)

    def validate_input(self, request):
        """Validate the incoming request. Override in subclass."""
        if not request.get("user_input"):
            raise ValueError("user_input is required")
        return request

    def load_data(self, request):
        """Load data from the Moodlight data layer. Override in subclass."""
        raise NotImplementedError

    def build_prompt(self, request, context):
        """Build the full prompt for Claude. Override in subclass."""
        raise NotImplementedError

    def format_output(self, raw_response):
        """Format the raw LLM response. Override in subclass if needed."""
        return {
            "output": raw_response,
            "agent": self.agent_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def run(self, request):
        """Orchestrate the full agent pipeline."""
        print(f"  [{self.agent_name}] Starting...")
        start = datetime.now(timezone.utc)

        # Validate
        request = self.validate_input(request)

        # Load data
        context = self.load_data(request)
        print(f"  [{self.agent_name}] Data loaded")

        # Build prompt
        prompt = self.build_prompt(request, context)

        # Prepend upstream context from prior agents in this session (additive, not replacement)
        upstream_preamble = self._render_upstream_context(request.get("upstream_context"))
        if upstream_preamble:
            prompt = upstream_preamble + prompt

        # Call Claude
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = Anthropic(api_key=api_key)
        system = self._build_system_prompt()

        def _call(model):
            print(f"  [{self.agent_name}] Calling Claude ({model})...")
            return client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )

        response = _call(self.model)
        raw = _extract_text(response)

        # Adaptive-thinking models (e.g. Fable 5) return a refusal as a successful
        # response (stop_reason == "refusal"), and could in rare cases yield no text
        # block. Fall back to the configured model so the user never gets empty output.
        if self.fallback_model and (response.stop_reason == "refusal" or not raw):
            print(f"  [{self.agent_name}] {self.model} returned stop_reason="
                  f"{response.stop_reason!r}; falling back to {self.fallback_model}")
            response = _call(self.fallback_model)
            raw = _extract_text(response)

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        print(f"  [{self.agent_name}] Complete in {elapsed:.1f}s")

        # Format output
        result = self.format_output(raw)
        result["elapsed_seconds"] = elapsed
        return result
