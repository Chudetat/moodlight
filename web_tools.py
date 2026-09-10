"""
web_tools.py — the web tools both Ask surfaces attach, defined in one place.

There are two Ask twins: ask_moodlight_api.py behind the Squarespace widget,
and ask_engine.py behind the dashboard. They share prompts through
shared_prompts.py and they used to share nothing else, which is how the
dashboard ended up with no web access at all while the widget had it.

WHY THERE IS NO CONDITION ON WEB SEARCH
---------------------------------------
There was, twice, and both were wrong in the same direction.

First it fired only when the user pasted a URL, on the reasoning that the tools
were useless otherwise. Then it fired only when a classifier had already
resolved a brand name. That second one reads as reasonable and is worse than it
sounds: the classifier is a Haiku call, and on the bare token a real person
actually types ("MSQDX") it resolves nothing, so the gate stayed shut for
exactly the queries that needed the web most. On 2026-09-10 someone from MSQ DX
- 600 people, inside a 1,900-person group - typed their own company name in and
Moodlight asked them to explain who they were.

Attaching a tool is not calling it. An unused tool costs nothing. The model,
holding the question and the substrate, is a better judge of whether it needs
the web than a Python condition guessing beforehand. So the decision belongs to
the model, on every query, on both surfaces.

web_fetch is the one exception, and it is not a gate on capability: it needs a
URL to point at, so it is attached when there is one.
"""

import re

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.I)

WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search"}
WEB_FETCH = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 4}


def urls_in(text: str, limit: int = 3) -> list:
    """URLs the user pasted into their question.

    People paste their own site when the name alone is ambiguous - "wrong
    product, https://ao2clear.com/", "Wrong store, instead do
    https://www.lowesmarket.com/". Both were a second attempt after the first
    answer picked the wrong company. Every question carrying a URL is someone
    saying exactly who they are, and they are almost always brands the substrate
    cannot see: name-based retrieval is weakest precisely where a URL helps most.
    """
    if not text:
        return []
    out, seen = [], set()
    for u in URL_RE.findall(text):
        u = u.rstrip(".,);:]")
        if u.lower() in seen:
            continue
        seen.add(u.lower())
        out.append(u)
        if len(out) >= limit:
            break
    return out


def attach(kwargs: dict, question: str, brand_name: str = "",
           brand_has_signal: bool = False, has_web_articles: bool = False) -> str:
    """Put the web tools on a messages.create() kwargs dict. Always.

    Returns a short reason string for the log line. The reason is diagnostic
    only - it never decides whether the tools go on. Do not turn it back into a
    condition.
    """
    pasted = urls_in(question)
    tools = [dict(WEB_SEARCH)]
    if pasted:
        tools.insert(0, dict(WEB_FETCH))
    kwargs["tools"] = tools

    if pasted:
        return "pasted URL + search"
    if brand_name and not brand_has_signal:
        return "no tracked signal on the brand"
    if not has_web_articles:
        return "no news results"
    return "standing"
