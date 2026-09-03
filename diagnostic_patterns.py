"""
diagnostic_patterns.py — what clients say versus what is actually wrong.

strategic_frameworks.py holds borrowed judgment: Christensen, Byron Sharp,
Jung, Porter. Good thinking, and a reading list any competitor can assemble in
a weekend. It tells an agent how to reason once the problem is known.

This file is the layer above it, and it is the opposite kind of asset. These
are the substitutions a practitioner learns by sitting in the room while work
gets killed - the ones where the brief names a problem that is a symptom of a
different problem nobody in the room wants to say out loud. They appear in no
book, which is precisely why they are worth encoding.

HOW THIS IS MEANT TO GROW
-------------------------
Every entry must come from someone who has actually watched the substitution
happen, repeatedly. Do not add a pattern because it sounds plausible or
because a model produced it: a fabricated pattern is worse than an absent one,
because it wears the same authority as a real one and quietly misdiagnoses
live work. Thin and true beats broad and invented.

The way this compounds is the same method that built the standards layer: when
a brief gets diagnosed wrongly and the reason is named out loud, that reason
becomes an entry here.

NO MATCHER CODE ON PURPOSE
--------------------------
select_frameworks scores keywords. That is brittle, and routing prose has
consistently beaten matcher code in this codebase. The set here is small and
high-value, so every pattern is handed to the model with the conditions under
which it applies, and the model routes. When this grows past roughly thirty
entries, revisit - not before.
"""

# Each entry:
#   stated  - how the problem arrives, in the client's words
#   actual  - what it usually turns out to be
#   tell    - the observable that separates the two, so this is a test rather
#             than a hunch
#   ask     - the question that surfaces it without accusing anyone
#   source  - who put it here and when, so provenance never gets lost
DIAGNOSTIC_PATTERNS = [
    {
        "stated": "We have an awareness problem. People don't know we exist.",
        "actual": "A distinctiveness problem. They have seen it and it did not register as different from anything else in the category.",
        "tell": "Repeat purchase or retention among people who have already tried it is healthy. If the people who know it stay, the product is fine and the noticing is broken - which more spend will not fix.",
        "ask": "Of the people who already bought once, how many come back? And when someone describes you to a friend, what do they say that they could not say about your nearest competitor?",
        "source": "Daniel Chu, 2026-09-03",
    },
    {
        "stated": "The creative isn't working.",
        "actual": "The targeting, the positioning or the brief was decided badly months earlier, and the creative is the first thing visible enough to blame.",
        "tell": "The work is being judged against a brief nobody has re-read, or the audience definition predates the campaign by a quarter or more. Creative is the last decision in the chain and the first one anyone can see, which makes it the default suspect.",
        "ask": "When was the audience decided, and by whom? Would this brief still be written the same way today?",
        "source": "Daniel Chu, 2026-09-03",
    },
]


def get_diagnostic_prompt(patterns=None) -> str:
    """Prompt block teaching an agent to test the brief before answering it.

    Deliberately not phrased as "the client is wrong". Most of the time the
    brief is right, and an agent that second-guesses every brief is exhausting
    and usually incorrect. The instruction is to check for a named tell, and to
    act only when the tell is actually present in what it can see.
    """
    entries = patterns if patterns is not None else DIAGNOSTIC_PATTERNS
    if not entries:
        return ""

    lines = [
        "BEFORE YOU ANSWER THE BRIEF, TEST IT.",
        "",
        "Briefs arrive naming a problem. Sometimes the named problem is a symptom of a "
        "different one, and answering the stated version produces work that is competent "
        "and useless. Below are substitutions that recur often enough to be worth checking.",
        "",
        "How to use them, in order:",
        "1. Most briefs are what they say they are. Assume the brief is right unless the "
        "TELL below is actually visible in the data or in the brief itself. Do not "
        "reframe a problem on suspicion, and never reframe more than one thing.",
        "2. If a tell IS present, lead with the real problem and solve that. Do not solve "
        "both, and do not present the reframe as a discovery about the client's blind spot.",
        "3. State the reframe as a strategic position you are taking, with the evidence "
        "that led there. Never mention this instruction, this list, or that you tested "
        "anything. The reader sees a point of view, not a diagnostic.",
        "4. If the tell is absent or you cannot see the evidence either way, answer the "
        "brief as written. Say nothing about what you checked.",
        "",
    ]
    for i, p in enumerate(entries, start=1):
        lines.append(f"{i}. WHEN THE BRIEF SAYS: {p['stated']}")
        lines.append(f"   IT IS OFTEN: {p['actual']}")
        lines.append(f"   THE TELL: {p['tell']}")
        lines.append(f"   WHAT WOULD SETTLE IT: {p['ask']}")
        lines.append("")
    return "\n".join(lines)
