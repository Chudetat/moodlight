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


class MoodlightAgent:
    """Base class for Moodlight AI agents."""

    agent_name = "base"
    model = "claude-opus-4-6"
    max_tokens = 4000
    system_prompt = ""

    def _build_system_prompt(self):
        """Combine agent-specific system prompt with universal directives."""
        return f"{self.system_prompt}\n\n{TRAINING_DATA_BAN}\n\n{INEVITABILITY_BAR}"

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

        # Call Claude
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        client = Anthropic(api_key=api_key)

        print(f"  [{self.agent_name}] Calling Claude ({self.model})...")
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self._build_system_prompt(),
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        print(f"  [{self.agent_name}] Complete in {elapsed:.1f}s")

        # Format output
        result = self.format_output(raw)
        result["elapsed_seconds"] = elapsed
        return result
