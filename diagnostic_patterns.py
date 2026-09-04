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

KNOWN LIMIT - PATTERN 1 AND FABRICATED FIGURES (2026-09-04, do not re-litigate)
-------------------------------------------------------------------------------
Given a deliberately bare brief - "we have an awareness problem, nobody in our
category knows us", no other facts, no numbers - a run will sometimes invent a
retention figure and state it as the client's. Observed across four attempts to
prompt it away: "at the rate you're describing", then "with retention in that
range", then a flat "a company retaining revenue at 118%". The number was
hallucinated, not leaked; brand_topic_memory was checked and contains no such
figure, and the stored job input confirms none was supplied.

Why this pattern and no other: pattern 1's tell is a NUMBER, and a plausible
number can be generated for any category from priors. Every other tell here is
structural - does the parent share the brand's name, does the brief name a
customer, does the idea target something the brand owns - and you cannot invent
your way into those.

Four rounds of guard text each changed the phrasing and not the behaviour:
an explicit ban, a guard repeated after the list, checkable tells, then the
attribution rule. A fifth wording is not expected to win, and the escalating
guard text has its own cost.

DECISION (Daniel, 2026-09-04): keep the pattern, document the limit, stop. It is
the most valuable entry in the library and behaves correctly whenever the figure
IS supplied. The failure needs a brief with essentially no content, which is not
what real users send - the JASPAL and Old Mutual answers were dense with real,
checkable sources. Do not remove pattern 1 and do not add a fifth guard. If
fabrication is ever observed on a REAL brief, that is the trigger to revisit;
a bare adversarial test case is not.

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
        "stated": "We have an awareness problem. People do not know we exist.",
        "actual": "A distinctiveness problem. They have seen it and it did not register as different from anything else available.",
        "tell": "The brief or data STATES a retention, repeat-purchase or renewal figure and it is healthy. If no such figure is given to you, you do not have this tell - never infer healthy retention from the type of business, and never write as though the client supplied a number they did not.",
        "ask": "Of the people who came once, how many came back? And what do they say about you that they could not say about your nearest competitor?",
        "source": "Daniel Chu, 2026-09-03",
    },
    {
        "stated": "The creative is not working.",
        "actual": "The targeting, the positioning or the brief was decided badly months earlier, and the creative is the first thing visible enough to blame.",
        "tell": "The brief names when the audience or positioning was set, and it predates the work by a quarter or more. If no date is stated, you do not have this tell.",
        "ask": "When was the audience decided, and by whom? Would that brief be written the same way today?",
        "source": "Daniel Chu, 2026-09-03",
    },
    {
        "stated": "We want to build on the ritual our customers already have.",
        "actual": "The behaviour is real but the origin story is not. The brand is about to claim a heritage it does not have, and someone will check.",
        "tell": "The brief asserts a heritage or origin for the behaviour and offers no evidence for it, or the web results describe the behaviour only in the market being sold to. An origin stated as self-evident is the tell.",
        "ask": "Do people where this supposedly comes from actually do it, or only people here?",
        "source": "Daniel Chu, from the Corona lime brief. Confirmed 2026-09-03.",
    },
    {
        "stated": "We need a big cultural moment.",
        "actual": "They need one concrete, human-scale idea. Briefs that ask for scale produce work you can describe but not picture.",
        "tell": "The brief asks in the language of scale - big, major, blowout, takeover, moment, unmissable - and nowhere names one person doing one specific thing. Scale words plus no scene is the tell.",
        "ask": "What does one actual person do here, on an ordinary Tuesday?",
        "source": "Daniel Chu, from Modelo March Madness. Confirmed 2026-09-03.",
    },
    {
        "stated": "That line is not landing. Can we reword it.",
        "actual": "Not a wording problem. The claim does not survive the listener's arithmetic and they cannot say so politely.",
        "tell": "The brief reports that a specific line was rejected without a stated reason, or rejected twice after rewording. If no rejection is described, you do not have this tell.",
        "ask": "What would have to be true for that number to hold?",
        "source": "Daniel Chu, from the SpinCo diorama scripts. Confirmed 2026-09-03.",
    },
    {
        "stated": "Engagement is good. People love it.",
        "actual": "They are interested, not dependent. The two look identical right up until the thing breaks, and then they do not.",
        "tell": "The brief or data describes an outage, lapse or absence that drew no complaint. Silence has to be reported to you; do not assume it.",
        "ask": "Who complained the last time it went down?",
        "source": "Daniel Chu, from Moodlight's own ten-day outage. Confirmed 2026-09-03.",
    },
    {
        "stated": "We need better materials. The deck, the site, the way we describe it.",
        "actual": "Nobody is asking to see anything. The problem sits upstream of the materials, and rewriting them changes nothing.",
        "tell": "The brief asks for new or better materials and states no inbound demand for the existing ones, or explicitly says nobody is asking. Absence of stated demand is the tell.",
        "ask": "How many people asked you to send them something?",
        "source": "Daniel Chu, 2026-09-03.",
    },
    {
        "stated": "Everyone in the room loves this device. Let us use it everywhere.",
        "actual": "It works aimed outward and inverts the moment it is aimed at the brand itself. The joke stops being about the rival and starts being about you.",
        "tell": "The idea as described applies the device to something the brand owns: its name, its mark, its core product. Read the mechanic as written. If the target is a rival or an outside subject, this is not it.",
        "ask": "Who is this pointed at, and what does it mean when it lands on us?",
        "source": "Daniel Chu, from the Modelo college football work. Confirmed 2026-09-04.",
    },
    {
        "stated": "Our audience will love taking this side.",
        "actual": "The idea needs someone to lose, and you sell to both halves of the divide it runs along.",
        "tell": "The described idea takes one named side of a divide the brand sells across. Look at the mechanic as written: if taking part means backing one side, the tell is present.",
        "ask": "What does someone on the other side of this do here?",
        "source": "Daniel Chu, from the Modelo college football work (bilateral principle). Confirmed 2026-09-04.",
    },
    {
        "stated": "This is our platform.",
        "actual": "It is one excellent execution that does not travel. A platform works in six places; this works in one.",
        "tell": "The brief calls it a platform and describes it in exactly one market, occasion or rivalry. One named instance plus the word platform is the tell.",
        "ask": "What does this look like in the next three places, unchanged?",
        "source": "Daniel Chu, from the Modelo college football work. Confirmed 2026-09-04.",
    },
    {
        "stated": "Carry the campaign idea through into this channel.",
        "actual": "The idea only ever existed in one channel. The others never referenced it, so on the ground it reads as invented rather than continued.",
        "tell": "The brief describes the idea living in one channel and asks for it in another, with no evidence the first channel ever carried it. If other channels are described as carrying it, you do not have this tell.",
        "ask": "Where else has anyone actually seen this idea?",
        "source": "Daniel Chu, from the Modelo college football work. Confirmed 2026-09-04.",
    },
    {
        "stated": "We need to be in more places.",
        "actual": "They are already everywhere. The problem is being chosen, not being present. Everywhere but invisible.",
        "tell": "The brief states broad availability or distribution alongside flat or falling performance. Both halves must be stated; if either is missing, you do not have this tell.",
        "ask": "At the moment of choosing, what makes someone say your name first?",
        "source": "Daniel Chu, from the Corona on-premise brief. Confirmed 2026-09-04.",
    },
    {
        "stated": "This is a modest, defensive brief. Do not over-invest.",
        "actual": "Modest in ambition and high in consequence. It is an audition that decides whether the relationship continues, and the stated scope hides that.",
        "tell": "The brief describes modest or defensive goals while also signalling that the relationship, the renewal or the account rides on it. Small stated ambition next to high stated stakes is the tell.",
        "ask": "What does this decide beyond itself?",
        "source": "Daniel Chu, from the Corona on-premise brief. Confirmed 2026-09-04.",
    },
    {
        "stated": "Lean into our core strength. It is what our best customers love.",
        "actual": "The quality that wins the core reads as a weakness to the audience they are trying to add. The same word means reliable to a loyalist and forgettable to a prospect.",
        "tell": "The brief names a core strength AND a growth audience it does not yet have. One word being asked to serve both is the tell; if only one audience is described, you do not have it.",
        "ask": "What does your best word sound like to someone who does not buy you?",
        "source": "Daniel Chu, from the Corona on-premise brief ('easy' reading as passive). Confirmed 2026-09-04.",
    },
    {
        "stated": "We want to own this territory.",
        "actual": "A larger competitor already rents the word, so using it makes you their echo and spends your budget reinforcing them.",
        "tell": "The territory word appears in a competitor's positioning in the material in front of you. If no competitor is shown using it, you do not have this tell - do not decide it from memory.",
        "ask": "Who owns this word in the customer's head already?",
        "source": "Daniel Chu, from Pacifico (refusing 'beach', which is Corona's word). Confirmed 2026-09-04.",
    },
    {
        "stated": "We want to own this feeling.",
        "actual": "Every competitor rents that feeling and none of them own it. Only a fact can be owned, and the fact has to be one only this brand has.",
        "tell": "The stated territory contains no verifiable noun - no place, no date, no material, no measurable fact. A claim made entirely of adjectives is the tell.",
        "ask": "What is true about us that no competitor can say without lying?",
        "source": "Daniel Chu, from Pacifico ('trying to own what every brand rents'). Confirmed 2026-09-04.",
    },
    {
        "stated": "We should buy the official rights or the premium placement.",
        "actual": "Official status buys legitimacy in a room that is shrinking, while the audience has already moved somewhere that needs no permission.",
        "tell": "The material shows audience or attention outside the official channel that is comparable to or larger than inside it. Without that comparison in front of you, you do not have this tell.",
        "ask": "Where is the audience actually paying attention, and does being official get us in?",
        "source": "Daniel Chu, from the CBI World Cup work. Confirmed 2026-09-04.",
    },
    {
        "stated": "Nobody has heard of us. We have no publicity.",
        "actual": "They have proof and no permission. The results exist, the customers will not be named, and the story cannot be told rather than does not exist.",
        "tell": "The brief states real revenue, results or usage AND describes an absence of named customers or public references. Both halves have to be stated; one without the other is not this tell.",
        "ask": "Which of these customers would let us use their name, and who has actually been asked?",
        "source": "Observed in a real Ask session (a public company with revenue and no named references). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "The market is confused by our name. We should rename.",
        "actual": "The confused word belongs to the category, not to the brand. Renaming walks away from a category you were positioned to define.",
        "tell": "The brand name contains a generic category term, and the confusion described is about that term rather than about the company. If the confusion is about the company itself, this is not it.",
        "ask": "Are they confused about who we are, or about what this whole category means?",
        "source": "Observed in a real Ask session (a product rename driven by category-term confusion). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "We need to reposition the brand.",
        "actual": "The brand and its parent share a name, so every corporate decision reprices the brand and no campaign outruns it.",
        "tell": "The brief names both a customer-facing brand and its parent or group, and they are the same word. If the parent is not named, you do not have this tell.",
        "ask": "When people hear this name, are they thinking of the product or the company?",
        "source": "Observed in a real Ask session (a group whose house brand and holding company share a name). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "We need more reach, more views, more followers.",
        "actual": "They have credibility and no format. A recognised expert without a repeatable unit is a guest everywhere and a destination nowhere.",
        "tell": "The brief describes output as a series of one-off appearances with no recurring named format or schedule. A list of individual pieces with no unit is the tell.",
        "ask": "What is the recurring thing, and when does it arrive?",
        "source": "Observed in a real Ask session (an expert trying to become a franchise). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "These two names fit together perfectly.",
        "actual": "The logic is aesthetic rather than behavioural. Nobody is already doing it, so the idea has to manufacture a habit instead of naming one.",
        "tell": "The brief justifies the pairing with heritage, aesthetics or how well the names sit together, and names no existing behaviour. Justification by fit rather than by observed habit is the tell.",
        "ask": "Who is already doing this on their own, and how would we know?",
        "source": "Observed in a real Ask session (a proposed pairing of two icons). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "We need them to take us seriously.",
        "actual": "Not a positioning problem. A proof problem. The argument is already good and the evidence of other people choosing it is missing.",
        "tell": "The brief describes the offer at length and names no customer who has already chosen it. Length of pitch plus absence of names is the tell.",
        "ask": "Who has already chosen us, by name, and what did they get?",
        "source": "Observed in a real Ask session (a market positioning itself to sceptical foreign investors). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "Our customers have moved to competitors. We need to win them back.",
        "actual": "The competitors did not take them. The meaning of the category changed and a competitor happened to be standing where it moved to.",
        "tell": "The brief names what customers switched TO, and it is a different kind of thing rather than a cheaper or nearer version of the same thing. If the alternative is a direct substitute, this is not it.",
        "ask": "What did they buy instead, and is it even the same kind of purchase?",
        "source": "Observed in a real Ask session (a heritage retailer losing customers to a different aesthetic). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
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
        "TELL below is written, in words, in the brief or the data in front of you. A tell "
        "you inferred from the kind of company this is, or assumed because the pattern "
        "would be interesting if true, is not a tell - it is you making the evidence up. "
        "Do not reframe on suspicion, and never reframe more than one thing.",
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

    # Repeated after the list, not only before it. At seven patterns the opening
    # guard sat ~1,500 characters from the end; at 24 it is ~12,000 away, and the
    # last thing read is the most tempting substitution rather than the caution.
    # Measured 2026-09-04: with 24 patterns and a brief that named NO evidence, a
    # run opened "if customers expand their spend with you at the rate you're
    # describing" - inventing a tell and attributing it to the client. Not a
    # wrong diagnosis; a fabricated quote.
    lines.append("BEFORE YOU USE ANY OF THE ABOVE, ONE LAST CHECK.")
    lines.append(
        "Point at the words. For whichever pattern you are about to apply, find the sentence "
        "in the brief or the data that states its tell, and if you cannot find one, answer "
        "the brief exactly as written and use none of this. You may NOT infer a tell from the "
        "type of business, assume a number nobody gave you, or write phrases like 'at the "
        "rate you describe', 'given your retention' or 'with your kind of growth' unless that "
        "figure appears above. Attributing evidence to someone who never supplied it is worse "
        "than missing the diagnosis: the diagnosis can be argued with, the invented quote ends "
        "the conversation. Most briefs get no reframe at all, and that is the correct outcome."
    )
    lines.append("")
    lines.append(
        "AND IF YOU REASON FROM WHAT YOU KNOW, SAY SO IN THE SENTENCE. You are allowed to "
        "argue from how a category normally behaves - that is judgement, and it is worth "
        "paying for. What you may never do is dress your own knowledge as something the "
        "client told you. 'Businesses of this size typically retain well, which makes "
        "awareness an unlikely culprit' is honest and just as sharp. 'With retention in that "
        "range' or 'at the rate you describe' is the same thought with a false source "
        "attached, and the reader knows they never said it. Attribute a category norm to the "
        "category, a figure to whoever supplied it, and never blur the two. This is the same "
        "discipline as tagging a claim [RECALL] rather than [BRIEF]: the claim can stay, the "
        "false sourcing cannot."
    )
    lines.append("")
    return "\n".join(lines)
