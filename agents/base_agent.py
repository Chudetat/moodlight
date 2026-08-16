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
    "For anything RECENT, VOLATILE, or NUMERIC, the Moodlight intelligence data in the user prompt is your "
    "ONLY source of truth. Do NOT inject from training data any current or recent events, corporate actions "
    "(launches, deals, exits, hires), controversies, executive quotes, financial figures, valuations, stock "
    "prices, stats, percentages, market-share numbers, or dated milestones — that knowledge is stale and "
    "presenting it as current intelligence destroys credibility.\n\n"
    "BUT you MUST use stable, foundational, verifiable knowledge to GROUND the work — vague strategy that "
    "won't name what it's talking about is worthless. It is REQUIRED to state timeless facts any well-read "
    "strategist obviously knows: where a brand comes from and what it makes (e.g. Pacifico is a Mexican "
    "pilsner brewed in Mazatlán on Mexico's Pacific coast), a brand's enduring heritage and equity, and how "
    "a category or event fundamentally works (e.g. March Madness is a single-elimination tournament whose "
    "first-round games tip midday on Thursday and Friday — it is largely a daytime event). The test: if a "
    "fact was equally true three years ago and will still be true three years from now, and it is common, "
    "checkable, foundational knowledge — USE it; if it is a number, a recent event, or a this-quarter fact — "
    "leave it out. When you invoke provenance or heritage, NAME it specifically — saying 'lean into "
    "provenance' without naming the actual origin is a failure, not discipline."
)

NO_FOURTH_WALL = (
    "The reader is the operator/strategist using the deliverable, not a peer reviewer of the engine. "
    "Never expose the engine's deliberation or its internal data instruments to the reader. "
    "The following terms are banned EVERYWHERE in the output — in body text, parentheticals, "
    "section headers, bullet labels, table captions, and footnotes: 'the intelligence snapshot', "
    "'the snapshot', 'the dataset', 'in the entire dataset', 'across our intelligence', 'the data shows', "
    "'the data indicates', and internal data source names (Polymarket, VLDS, opp_map, etc.). "
    "ALSO BANNED — the 'tracked' family, which is the same leak said politely: 'tracked "
    "conversation', 'the tracked climate', 'tracked media conversation', 'in tracked data', "
    "'the conversation we track', 'our tracking'. Any adjective that describes the act of "
    "observation points at the instrument. The reader does not know a corpus exists and must not "
    "learn it here. Say 'the conversation' or 'right now' and stop — the qualifier adds nothing "
    "except a glimpse of the machinery. "
    "Do NOT use 'VLDS Gaps', 'Snapshot Highlights', 'Dataset Findings' as section headers — "
    "use plain-English labels like 'Underserved Cultural Conversations' or 'Where the Conversation Is Quiet'. "
    "Banned deliberation parentheticals: '(despite X)', '(I considered Y but)', '(the data shows Z, however)'. "
    "Cite signals as cultural facts the buyer would recognize ('on X this week...', 'the most-engaged post "
    "about this topic...'), never as system outputs ('the snapshot shows...', 'the data indicates...'). "
    "ONE EXCEPTION: the SOURCE CHECK block specified below. That block is a provenance appendix for the "
    "operator, not engine deliberation, and it is required. It must still obey this rule internally — use "
    "the [SUBSTRATE] tag, never an internal data-source name."
)

SOURCE_CHECK = (
    "SOURCE CHECK — the final section of every output, placed after the closing line:\n"
    "End with a short block titled 'SOURCE CHECK' listing every LOAD-BEARING factual claim you made "
    "about the real world — the claims the strategy collapses without. Always include, when present: "
    "the brand's origin, founding date, founder, and what its name means; any claim about a competitor's "
    "history, campaigns, or past strategy; any figure, percentage, share, count, or ranking; and any "
    "claim about a law, holiday, tradition, or category convention.\n"
    "One line per claim, stated as the bare claim with no commentary, each tagged:\n"
    "  [SUBSTRATE] — it is present in the intelligence material in this prompt.\n"
    "  [BRIEF] — it is present in the brief the user wrote.\n"
    "  [RECALL] — you are stating it from your own knowledge and it is NOT in the material above.\n"
    "If you cannot point to where a claim appears in this prompt, it is [RECALL] — including claims you "
    "are certain of, and especially founding dates, anniversaries, and origin stories. Confidence is not "
    "a source. A wrong origin story tagged [RECALL] costs a human ten seconds; the same claim untagged "
    "reaches a client.\n"
    "Keep it to twelve lines or fewer. Do NOT hedge the body of the work to compensate — the deliverable "
    "stays declarative and in voice, and every piece of uncertainty lives in this block and nowhere else. "
    "A load-bearing [RECALL] claim still belongs in the work. It just has to be checkable."
)

NO_INSTRUMENT_LEAKS = (
    "Never quote your own metric values to the reader.\n"
    "THE TEST — apply it to every number you are about to write: could the reader have found this "
    "number without this engine? If YES, use it freely — externally reported and citable figures "
    "(market data, published research, a platform's own disclosure) are encouraged and make the work "
    "stronger. If NO — if it exists only because this system measured its own corpus — cut it.\n"
    "THE BAN IS ON THE NUMBER, NOT THE PUNCTUATION. It applies in body prose, mid-sentence, in a "
    "clause, in a header, in a footnote — everywhere, not only in parentheses or brackets. Writing "
    "'(65K engagement)' and writing 'a post with 54,000 engagements' are the same violation; the "
    "second is worse because it reads as reportage. Spelling it out does not help either: "
    "'fifty-odd thousand people', 'tens of thousands of engagements' and 'over 50k' are all the same "
    "leak wearing different clothes. Rounding, approximating and hedging do not launder it.\n"
    "Concretely banned however they are written: engagement counts, mention counts, post counts, "
    "scarcity/velocity/longevity/density scores, empathy scores, percentiles, sample sizes, and "
    "data-layer tags such as '[OPPORTUNITY]' or '(MEDIUM opportunity)'.\n"
    "Say the same thing qualitatively instead. 'The most-shared piece on this topic this week was a "
    "joke about AI-generated flyers' carries the whole point and leaks nothing. The size of a signal "
    "belongs in your reasoning about what to say; it must never become the sentence you say."
)

NO_DATA_RECAP = (
    "Lead with your thinking, not a summary of the inputs. The reader has the brief and does NOT "
    "want the data read back to them. Do NOT open with — or dedicate a section to — a recap of the "
    "situation, the signals, the emotional climate, the market data, or the headlines. If the "
    "instructions below mandate a 'situation assessment', 'landscape', 'where to play', or 'timing' "
    "section, keep it to two or three sentences of pointed insight and move on — never a full recap. "
    "Use every data point as FUEL for a conclusion, cited in-line only where it drives a specific "
    "point, never as standalone summary. Your first paragraph must be an insight the reader could not "
    "have written themselves — not a description of what the data says."
)

INEVITABILITY_BAR = (
    "THE AUDACITY BAR — this governs every idea you ship:\n"
    "Reach for the idea that makes the client's stomach drop — the one so audacious AND obvious they "
    "can't believe no one has done it yet (Fearless Girl, Whopper Detour). Timid, safe, best-practice "
    "work fails this bar. But 'audacious' means audacious-and-OBVIOUS, never precious-and-weird: an idea "
    "that is clever for its own sake, needs a manifesto to justify it, or spends real money on nothing "
    "fails just as hard as the timid one. Do not confuse strange with bold.\n\n"
    "How you actually get there: ANCHOR THE AUDACITY IN A LIVE SIGNAL. Do not reach for 'the boldest "
    "idea' in the abstract — reach for the most audacious thing THIS week's specific, real-time signal in "
    "the material above lets you do that no competitor is acting on. Name the exact signal the idea is "
    "built on. Boldness must be EARNED by a real, surprising, current data point — that is what makes an "
    "audacious idea feel inevitable instead of random, and it is the one advantage this tool has that no "
    "agency does. If the idea would be just as possible without today's signal, it isn't using that edge — "
    "push harder until the signal is load-bearing.\n\n"
    "Two gates before anything ships: the substitution test (could a competitor reach this from the same "
    "signal? if yes, rewrite) and the boardroom test (would a real brand actually buy and build it? if it "
    "gets laughed out of the room, cut it). Your job is the audacious move that, the moment it's said, is "
    "obviously right."
)

ONE_SPINE = (
    "IDEA DISCIPLINE — applies whenever you propose ideas, concepts, or executions:\n"
    "- ONE SPINE. Everything ladders to a single platform idea — one ownable territory, one mechanic. "
    "Pick the strongest, most ownable, most buildable idea and make it the spine; every other idea must "
    "be a proof or execution OF that spine, never a separate concept in a different territory. If two "
    "ideas serve different insights, keep the stronger and cut the other. A scatter of half-connected "
    "concepts across different territories reads as NO idea at all — it is the most common failure. "
    "Fewer and deeper beats a menu: one platform plus two or three executions that prove it.\n"
    "- THE BOARDROOM TEST. Every idea must survive a skeptical CMO asking 'would we actually buy and "
    "build this?' Kill precious conceptual flexes ('spend real money on nothing'), commercially "
    "illiterate stunts, and anything that would get laughed out of the room.\n"
    "- THE NAME IS THE PITCH, AND IT READS LIKE A TENSION LINE — NOT A LABEL. Each idea's title must carry "
    "the whole idea AND its edge in one line a stranger gets instantly, written like a hook with tension, "
    "never a description of the activation. PASS: 'The contest starts at 10. Surfing starts at 5.' — the "
    "whole idea and the tension in eight words. NEAR-MISS that only labels the mechanic: 'The 5AM Heat Has "
    "No Judges.' FAIL — a topic label ('Miles to Mazatlán') or a mood ('Kilometer Zero', 'First Light'). "
    "STRUCTURAL RULE: the single sharpest line you write IS the name. If any line anywhere in your output "
    "— a hook, a headline, a throwaway — is sharper than your idea's name, you named it wrong; that line "
    "should have BEEN the name. Never bury your best line in a separate 'hooks' slot. If the name needs "
    "the paragraph to make sense, rewrite the name until it doesn't.\n"
    "- THE PLAIN-SENTENCE TEST. State each idea in ONE plain sentence a non-creative could repeat back "
    "correctly. If it needs decoding — a cryptic gesture, an oblique metaphor — rewrite until it lands "
    "instantly. Clear and buildable beats clever and oblique, every time."
)

# Shared with the standalone report generators — single source of truth in shared_prompts.py
from shared_prompts import CULTURAL_PRESENCE_NOT_SALIENCE

# Alcohol CATEGORY names. The abstract terms below ("alcohol", "spirits",
# "beer", "wine", "liquor") were the only alcohol triggers, so a brief that
# simply named its category — "tequila" fifteen times, "bourbon", "vodka" —
# matched nothing and the agent ran with no regulatory guidance at all.
# Word-anchored on purpose: unanchored, "gin" matches engine/imagine/origin,
# "rum" matches forum/drum/instrument, "cider" matches decider.
_ALCOHOL_CATEGORY_TERMS = (
    "tequila", "mezcal", "whiskey", "whisky", "bourbon", "scotch",
    "vodka", "gin", "rum", "cognac", "brandy", "vermouth",
    "prosecco", "champagne", "cider", "seltzer", "cocktail", "cocktails",
    "distillery", "distilleries", "brewery", "breweries",
    "winery", "wineries", "abv",
)

# Keywords that trigger inclusion of regulatory guidance
_REGULATED_INDUSTRY_PATTERNS = re.compile(
    r"pharma|healthcare|medical|hospital|drug|rx|fda|"
    r"financial|banking|fintech|investment|insurance|"
    r"alcohol|spirits|beer|wine|liquor|"
    r"cannabis|cbd|marijuana|"
    r"legal\s+service|law\s+firm|attorney|"
    r"\b(?:" + "|".join(_ALCOHOL_CATEGORY_TERMS) + r")\b",
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
    effort = None  # "low"|"medium"|"high"|"xhigh"|"max"; None = API default (high). Used by effort-capable models (Opus 5, Opus 4.6+, Sonnet 5, etc.)
    max_tokens = 4000
    system_prompt = ""

    def _build_system_prompt(self):
        """Combine agent-specific system prompt with universal directives."""
        return (
            f"{self.system_prompt}\n\n{TRAINING_DATA_BAN}\n\n"
            f"{CULTURAL_PRESENCE_NOT_SALIENCE}\n\n"
            f"{NO_FOURTH_WALL}\n\n{NO_INSTRUMENT_LEAKS}\n\n{NO_DATA_RECAP}\n\n{INEVITABILITY_BAR}\n\n{ONE_SPINE}"
            f"\n\n{SOURCE_CHECK}"
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
            "The reader has ALREADY seen the agent output(s) below — on this same brief, moments "
            "ago. They already have the situation, the signals, the emotional climate, the "
            "headlines, and every data point cited. Your job is to ADVANCE the thinking, not "
            "re-lay the groundwork. Hard rules:\n"
            "1. Do NOT open with a situation assessment, landscape read, or data recap. If the "
            "instructions below ask for one (a 'situation assessment', 'where to play', or "
            "'timing' section), COMPRESS it to a single sentence that points back to the prior "
            "agents' read — do not reproduce it. The agents above already set the table.\n"
            "2. Do NOT re-cite signals, statistics, headlines, market moves, or framings the prior "
            "agents already used. Assume the reader remembers them. Reference one in a few words "
            "ONLY to build on it (e.g. 'given the flat emotional read already established…'), never "
            "to re-explain it.\n"
            "3. Every paragraph you write must be NET-NEW — the layer the prior agents did not "
            "reach. If a paragraph could have appeared in one of their outputs, cut it.\n"
            "Treat their work as established and build the next floor on top of it. The brief in "
            "the main user prompt below is still the source of truth.",
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
            eff = f", effort={self.effort}" if self.effort else ""
            print(f"  [{self.agent_name}] Calling Claude ({model}{eff})...")
            kwargs = {
                "model": model,
                "max_tokens": self.max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
            if self.effort:
                # output_config passed via extra_body for compatibility with the pinned SDK
                kwargs["extra_body"] = {"output_config": {"effort": self.effort}}
            # Streamed, not create(). The SDK refuses a non-streamed call whose
            # estimated duration crosses ten minutes, and it estimates from
            # max_tokens - so full_deploy (24k) died instantly with
            # "Streaming is required for operations that may take longer than
            # 10 minutes" while every 16k agent squeaked under the bar. That
            # killed the heaviest agent on the site from 5 May onward, and the
            # user-facing message ("temporarily unavailable") made a permanent
            # break look transient.
            #
            # Streaming is the documented way to run long generations and is
            # correct for every agent here, not just the big one. Same Message
            # object comes back, so stop_reason and content are unchanged.
            with client.messages.stream(**kwargs) as stream:
                return stream.get_final_message()

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
