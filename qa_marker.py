"""
qa_marker.py — one definition of "this row is our own testing, not a visitor."

Every surface that reads ask_queries has to answer the same question: is this a
stranger, or is it us poking production. Until now only ask_alerts.py answered
it, and it answered narrowly - it excluded the literal string "[qa]" and
nothing else.

That was not enough. Real test rows written on 2026-09-10 were tagged "(Qa)",
"[qa2]" and "[qa live]". None of them contain "[qa]", so all three counted as
inbound visitor traffic: they were eligible to be emailed to Daniel as leads,
and they landed in the monthly query_log_sweep as real sessions from real
people. A convention nobody can remember exactly is not a convention.

WHY PREFIXES, ANCHORED AT THE START
-----------------------------------
Matching "%qa%" anywhere in a question would eventually swallow a genuine one -
someone asking about QA processes, a brand with those letters in it - and the
cost of that mistake is asymmetric: a real lead silently dropped from the alert
that exists to surface it. Nobody types "[qa" or "(qa" at the START of a real
question. Anchoring makes a false exclusion effectively impossible while still
catching every marker actually in use.

To tag a test, start the question with [qa or (qa. Anything after that is free
form - "[qa2]", "[qa live]", "(Qa) round three" all work.
"""

QA_PREFIXES = ("[qa", "(qa")

# Postgres LIKE treats "[" and "(" as ordinary characters, so these patterns
# need no escaping. No leading "%" - that is the whole point.
SQL_EXCLUDE_QA = "(question NOT ILIKE '[qa%' AND question NOT ILIKE '(qa%')"
SQL_ONLY_QA = "(question ILIKE '[qa%' OR question ILIKE '(qa%')"


def is_qa(question: str) -> bool:
    """True if this question is one of ours, not a visitor's."""
    return (question or "").lstrip().lower().startswith(QA_PREFIXES)
