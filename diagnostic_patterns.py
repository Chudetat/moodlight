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
        "stated": "We have an awareness problem. People do not know we exist.",
        "actual": "A distinctiveness problem. They have seen it and it did not register as different from anything else available.",
        "tell": "The people who have already used it stay. If retention among existing customers is healthy, the offer is fine and the noticing is broken, which more spend does not fix.",
        "ask": "Of the people who came once, how many came back? And what do they say about you that they could not say about your nearest competitor?",
        "source": "Daniel Chu, 2026-09-03",
    },
    {
        "stated": "The creative is not working.",
        "actual": "The targeting, the positioning or the brief was decided badly months earlier, and the creative is the first thing visible enough to blame.",
        "tell": "The work is being judged against a brief nobody has re-read, or an audience definition that predates the work by a quarter or more. Execution is the last decision in the chain and the first one anyone can see.",
        "ask": "When was the audience decided, and by whom? Would that brief be written the same way today?",
        "source": "Daniel Chu, 2026-09-03",
    },
    {
        "stated": "We want to build on the ritual our customers already have.",
        "actual": "The behaviour is real but the origin story is not. The brand is about to claim a heritage it does not have, and someone will check.",
        "tell": "The behaviour does not exist in the place it is said to come from. Real habit, invented provenance.",
        "ask": "Do people where this supposedly comes from actually do it, or only people here?",
        "source": "Daniel Chu, from the Corona lime brief. Confirmed 2026-09-03.",
    },
    {
        "stated": "We need a big cultural moment.",
        "actual": "They need one concrete, human-scale idea. Briefs that ask for scale produce work you can describe but not picture.",
        "tell": "Ask someone to describe the idea back. If they describe size, it is dead. If they describe a scene with one person in it, it is alive.",
        "ask": "What does one actual person do here, on an ordinary Tuesday?",
        "source": "Daniel Chu, from Modelo March Madness. Confirmed 2026-09-03.",
    },
    {
        "stated": "That line is not landing. Can we reword it.",
        "actual": "Not a wording problem. The claim does not survive the listener's arithmetic and they cannot say so politely.",
        "tell": "A knowledgeable stakeholder rejects one specific sentence and cannot say why. Reword it and they reject it again. The objection is the maths, not the language.",
        "ask": "What would have to be true for that number to hold?",
        "source": "Daniel Chu, from the SpinCo diorama scripts. Confirmed 2026-09-03.",
    },
    {
        "stated": "Engagement is good. People love it.",
        "actual": "They are interested, not dependent. The two look identical right up until the thing breaks, and then they do not.",
        "tell": "It broke and nobody said anything. People tell you when something they rely on stops working; silence measures how little the outage cost them.",
        "ask": "Who complained the last time it went down?",
        "source": "Daniel Chu, from Moodlight's own ten-day outage. Confirmed 2026-09-03.",
    },
    {
        "stated": "We need better materials. The deck, the site, the way we describe it.",
        "actual": "Nobody is asking to see anything. The problem sits upstream of the materials, and rewriting them changes nothing.",
        "tell": "Count inbound requests over the last month. If it is near zero, the materials are not what is failing.",
        "ask": "How many people asked you to send them something?",
        "source": "Daniel Chu, 2026-09-03.",
    },
    {
        "stated": "Everyone in the room loves this device. Let us use it everywhere.",
        "actual": "It works aimed outward and inverts the moment it is aimed at the brand itself. The joke stops being about the rival and starts being about you.",
        "tell": "The device is being applied to something the brand owns - its name, its mark, its core product. A negation sitting on your own asset reads as negation of the asset.",
        "ask": "Who is this pointed at, and what does it mean when it lands on us?",
        "source": "Daniel Chu, from the Modelo college football work. Confirmed 2026-09-04.",
    },
    {
        "stated": "Our audience will love taking this side.",
        "actual": "The idea needs someone to lose, and you sell to both halves of the divide it runs along.",
        "tell": "Can the other half take part without being the loser? If participation requires picking the winning side, everyone on the other side is being sold against.",
        "ask": "What does someone on the other side of this do here?",
        "source": "Daniel Chu, from the Modelo college football work (bilateral principle). Confirmed 2026-09-04.",
    },
    {
        "stated": "This is our platform.",
        "actual": "It is one excellent execution that does not travel. A platform works in six places; this works in one.",
        "tell": "Apply it to the second and third market, segment or occasion without rewriting it. If it has to be rewritten each time, it is an execution wearing a platform's job title.",
        "ask": "What does this look like in the next three places, unchanged?",
        "source": "Daniel Chu, from the Modelo college football work. Confirmed 2026-09-04.",
    },
    {
        "stated": "Carry the campaign idea through into this channel.",
        "actual": "The idea only ever existed in one channel. The others never referenced it, so on the ground it reads as invented rather than continued.",
        "tell": "Check whether the other channels actually say it. If the advertising never mentions it, nothing downstream can assume the audience has heard it.",
        "ask": "Where else has anyone actually seen this idea?",
        "source": "Daniel Chu, from the Modelo college football work. Confirmed 2026-09-04.",
    },
    {
        "stated": "We need to be in more places.",
        "actual": "They are already everywhere. The problem is being chosen, not being present. Everywhere but invisible.",
        "tell": "Check availability against performance. Present in nearly every channel with flat or falling conversion is a salience problem, and buying more presence buys nothing.",
        "ask": "At the moment of choosing, what makes someone say your name first?",
        "source": "Daniel Chu, from the Corona on-premise brief. Confirmed 2026-09-04.",
    },
    {
        "stated": "This is a modest, defensive brief. Do not over-invest.",
        "actual": "Modest in ambition and high in consequence. It is an audition that decides whether the relationship continues, and the stated scope hides that.",
        "tell": "Ask what losing it costs. If losing costs the account rather than the project, the ceiling is low and the floor risk is not.",
        "ask": "What does this decide beyond itself?",
        "source": "Daniel Chu, from the Corona on-premise brief. Confirmed 2026-09-04.",
    },
    {
        "stated": "Lean into our core strength. It is what our best customers love.",
        "actual": "The quality that wins the core reads as a weakness to the audience they are trying to add. The same word means reliable to a loyalist and forgettable to a prospect.",
        "tell": "Say the equity word to a non-customer and listen to what it means to them. If the core hears warmth and the prospect hears passivity, the strength is also the ceiling.",
        "ask": "What does your best word sound like to someone who does not buy you?",
        "source": "Daniel Chu, from the Corona on-premise brief ('easy' reading as passive). Confirmed 2026-09-04.",
    },
    {
        "stated": "We want to own this territory.",
        "actual": "A larger competitor already rents the word, so using it makes you their echo and spends your budget reinforcing them.",
        "tell": "Say the word on its own and see whose brand appears first. If it is not yours, the word is spent.",
        "ask": "Who owns this word in the customer's head already?",
        "source": "Daniel Chu, from Pacifico (refusing 'beach', which is Corona's word). Confirmed 2026-09-04.",
    },
    {
        "stated": "We want to own this feeling.",
        "actual": "Every competitor rents that feeling and none of them own it. Only a fact can be owned, and the fact has to be one only this brand has.",
        "tell": "Look for the physical, checkable thing underneath the mood. If the claim would survive a competitor copying the words, there is a fact under it. If not, it is atmosphere.",
        "ask": "What is true about us that no competitor can say without lying?",
        "source": "Daniel Chu, from Pacifico ('trying to own what every brand rents'). Confirmed 2026-09-04.",
    },
    {
        "stated": "We should buy the official rights or the premium placement.",
        "actual": "Official status buys legitimacy in a room that is shrinking, while the audience has already moved somewhere that needs no permission.",
        "tell": "Compare the official channel's audience with where the conversation actually happened. If the unofficial route reached more people, the rights are buying status rather than reach.",
        "ask": "Where is the audience actually paying attention, and does being official get us in?",
        "source": "Daniel Chu, from the CBI World Cup work. Confirmed 2026-09-04.",
    },
    {
        "stated": "Nobody has heard of us. We have no publicity.",
        "actual": "They have proof and no permission. The results exist, the customers will not be named, and the story cannot be told rather than does not exist.",
        "tell": "Revenue and results are real while public references are absent. That gap is a consent problem, not a marketing one, and no amount of campaign fixes it.",
        "ask": "Which of these customers would let us use their name, and who has actually been asked?",
        "source": "Observed in a real Ask session (a public company with revenue and no named references). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "The market is confused by our name. We should rename.",
        "actual": "The confused word belongs to the category, not to the brand. Renaming walks away from a category you were positioned to define.",
        "tell": "Ask whether people misunderstand the name or the category term inside it. If the muddy word is the one every competitor also uses, the confusion is the category's and the name is collateral.",
        "ask": "Are they confused about who we are, or about what this whole category means?",
        "source": "Observed in a real Ask session (a product rename driven by category-term confusion). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "We need to reposition the brand.",
        "actual": "The brand and its parent share a name, so every corporate decision reprices the brand and no campaign outruns it.",
        "tell": "Does the company name equal a customer-facing brand name? If so, portfolio, pricing and corporate news all land on the same word the marketing is trying to move.",
        "ask": "When people hear this name, are they thinking of the product or the company?",
        "source": "Observed in a real Ask session (a group whose house brand and holding company share a name). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "We need more reach, more views, more followers.",
        "actual": "They have credibility and no format. A recognised expert without a repeatable unit is a guest everywhere and a destination nowhere.",
        "tell": "Look for the thing someone could subscribe to. If every piece is a one-off appearance with a different shape, there is nothing for an audience to return to, and reach leaks straight back out.",
        "ask": "What is the recurring thing, and when does it arrive?",
        "source": "Observed in a real Ask session (an expert trying to become a franchise). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "These two names fit together perfectly.",
        "actual": "The logic is aesthetic rather than behavioural. Nobody is already doing it, so the idea has to manufacture a habit instead of naming one.",
        "tell": "Look for the behaviour already happening without permission. Pairings that work name something people do anyway; pairings that fail are justified by how well the two logos sit together.",
        "ask": "Who is already doing this on their own, and how would we know?",
        "source": "Observed in a real Ask session (a proposed pairing of two icons). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "We need them to take us seriously.",
        "actual": "Not a positioning problem. A proof problem. The argument is already good and the evidence of other people choosing it is missing.",
        "tell": "Ask for three named examples of someone who already chose them and why. If the answer is a description of the offer rather than a list of names, no amount of better positioning will close it.",
        "ask": "Who has already chosen us, by name, and what did they get?",
        "source": "Observed in a real Ask session (a market positioning itself to sceptical foreign investors). Substitution proposed by Claude, kept by Daniel 2026-09-04.",
    },
    {
        "stated": "Our customers have moved to competitors. We need to win them back.",
        "actual": "The competitors did not take them. The meaning of the category changed and a competitor happened to be standing where it moved to.",
        "tell": "Ask what the leavers bought instead. If it is a different KIND of thing rather than a cheaper or nearer version of the same thing, this is a category shift and win-back campaigns aimed at the old proposition will fail.",
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
