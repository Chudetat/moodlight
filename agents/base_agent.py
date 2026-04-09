"""
agents/base_agent.py
Base class for all Moodlight agents.
Handles the shared orchestration: validate → load data → build prompt → call LLM → format output.
"""

import os
from datetime import datetime, timezone
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class MoodlightAgent:
    """Base class for Moodlight AI agents."""

    agent_name = "base"
    model = "claude-opus-4-6"
    max_tokens = 4000
    system_prompt = ""

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
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        print(f"  [{self.agent_name}] Complete in {elapsed:.1f}s")

        # Format output
        result = self.format_output(raw)
        result["elapsed_seconds"] = elapsed
        return result
