#!/usr/bin/env python
"""
mood_report_publisher.py
Publishing integrations for The Mood Report.

Handles:
  - Beehiiv draft publishing (REST API)
  - X/Twitter thread posting (tweepy, when enabled)
  - Markdown → styled HTML conversion for newsletter
"""

import os
import re
import requests


# ---------------------------------------------------------------------------
# Markdown → Newsletter HTML
# ---------------------------------------------------------------------------

def markdown_to_newsletter_html(md_text):
    """Convert newsletter markdown to styled HTML for Beehiiv and email."""

    # Split into lines for processing
    lines = md_text.split("\n")
    html_parts = []
    in_table = False
    table_rows = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines (add spacing)
        if not stripped:
            if in_table:
                html_parts.append(_render_table(table_rows))
                table_rows = []
                in_table = False
            html_parts.append("")
            continue

        # Table rows
        if stripped.startswith("|") and stripped.endswith("|"):
            # Skip separator rows like |---|---|---|
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                continue
            in_table = True
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            table_rows.append(cells)
            continue

        # Close table if we were in one
        if in_table:
            html_parts.append(_render_table(table_rows))
            table_rows = []
            in_table = False

        # H1: # THE MOOD REPORT
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:]
            html_parts.append(
                f'<h1 style="color: #1a1a2e; font-size: 28px; margin: 0 0 5px 0; '
                f'letter-spacing: 1px;">{title}</h1>'
            )
            continue

        # H2: ## SECTION NAME
        if stripped.startswith("## "):
            section = stripped[3:]
            color = _section_color(section)
            html_parts.append(
                f'<div style="margin: 25px 0 10px 0;">'
                f'<span style="background: {color}; color: white; padding: 4px 12px; '
                f'border-radius: 4px; font-size: 12px; font-weight: bold; '
                f'letter-spacing: 0.5px;">{section}</span>'
                f'</div>'
            )
            continue

        # H3: ### subsection
        if stripped.startswith("### "):
            html_parts.append(
                f'<h3 style="color: #444; font-size: 16px; margin: 15px 0 5px 0;">'
                f'{stripped[4:]}</h3>'
            )
            continue

        # Italic line: *text*
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            inner = stripped[1:-1]
            html_parts.append(
                f'<p style="color: #888; font-style: italic; font-size: 14px; '
                f'margin: 2px 0;">{inner}</p>'
            )
            continue

        # Horizontal rule
        if stripped == "---":
            html_parts.append('<hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">')
            continue

        # Bullet points
        if stripped.startswith("- "):
            content = _inline_format(stripped[2:])
            html_parts.append(
                f'<div style="margin: 4px 0; padding-left: 15px;">'
                f'<span style="color: #1976D2;">&#8226;</span> {content}</div>'
            )
            continue

        # Regular paragraph
        html_parts.append(
            f'<p style="font-size: 15px; color: #333; line-height: 1.6; '
            f'margin: 8px 0;">{_inline_format(stripped)}</p>'
        )

    # Close any open table
    if in_table and table_rows:
        html_parts.append(_render_table(table_rows))

    body = "\n".join(html_parts)

    return f"""
    <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      {body}
    </div>
    """


def _render_table(rows):
    """Render a markdown table as styled HTML."""
    if not rows:
        return ""

    header = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []

    th_cells = "".join(
        f'<th style="padding: 8px 12px; text-align: left; border-bottom: 2px solid #1976D2; '
        f'color: #1976D2; font-size: 12px; font-weight: bold; letter-spacing: 0.5px;">{c}</th>'
        for c in header
    )

    tr_rows = []
    for i, row in enumerate(data_rows):
        bg = "#f8f9fa" if i % 2 == 0 else "white"
        td_cells = "".join(
            f'<td style="padding: 8px 12px; font-size: 14px; color: #333; '
            f'border-bottom: 1px solid #eee;">{_inline_format(c)}</td>'
            for c in row
        )
        tr_rows.append(f'<tr style="background: {bg};">{td_cells}</tr>')

    return (
        f'<table style="width: 100%; border-collapse: collapse; margin: 10px 0;">'
        f'<thead><tr>{th_cells}</tr></thead>'
        f'<tbody>{"".join(tr_rows)}</tbody>'
        f'</table>'
    )


def _section_color(name):
    """Return brand color for each newsletter section."""
    colors = {
        "BOTTOM LINE": "#1a1a2e",
        "MOOD DASHBOARD": "#1976D2",
        "WHAT MOVED": "#E65100",
        "SIGNAL TRACKER": "#7B1FA2",
        "EMOTION MAP": "#00897B",
        "FORWARD LOOK": "#2E7D32",
    }
    return colors.get(name, "#1976D2")


def _inline_format(text):
    """Apply inline markdown formatting (bold, etc.)."""
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Arrows
    text = text.replace("↑", '<span style="color: #2E7D32;">&#8593;</span>')
    text = text.replace("↓", '<span style="color: #DC143C;">&#8595;</span>')
    return text


# ---------------------------------------------------------------------------
# Chart Image Insertion
# ---------------------------------------------------------------------------

def insert_chart_images(html, chart_urls):
    """Insert QuickChart.io chart images into newsletter HTML after sections.

    Finds section badge <span> elements by text and inserts <img> tags
    before the next section. Supports dynamic placements via _placements key,
    falling back to legacy hardcoded positions.
    """
    if not chart_urls:
        return html

    # Dynamic placements from build_chart_urls, or legacy fallback
    placements = chart_urls.get("_placements", {})
    if not placements:
        placements = {
            "market_performance": "MARKETS & MOOD",
            "empathy_trend": "WHAT'S INTERESTING",
            "emotion_distribution": "ALSO WORTH NOTICING",
        }

    # Build (key, section) pairs, process in reverse to preserve insert positions
    chart_list = [(k, placements[k]) for k in placements if k in chart_urls]

    img_style = "max-width: 100%; height: auto; border-radius: 8px; margin: 15px 0;"

    for chart_key, section_name in reversed(chart_list):
        url = chart_urls.get(chart_key)
        if not url:
            continue

        # Find the section badge span
        pattern = re.escape(f">{section_name}</span>")
        match = re.search(pattern, html)
        if not match:
            continue

        # Find the next section div after this one
        rest_start = match.end()
        next_section = re.search(
            r'<div style="margin: 25px 0 10px 0;">',
            html[rest_start:],
        )

        img_tag = (
            f'<div style="text-align: center; margin: 15px 0;">'
            f'<img src="{url}" '
            f'alt="{chart_key.replace("_", " ").title()}" '
            f'style="{img_style}" />'
            f"</div>"
        )

        if next_section:
            insert_pos = rest_start + next_section.start()
        else:
            # Insert before the <hr> footer or at end
            hr_match = re.search(r"<hr ", html[rest_start:])
            if hr_match:
                insert_pos = rest_start + hr_match.start()
            else:
                insert_pos = len(html)

        html = html[:insert_pos] + img_tag + html[insert_pos:]

    return html


# ---------------------------------------------------------------------------
# Beehiiv Publishing
# ---------------------------------------------------------------------------

def publish_to_beehiiv(html, title, subtitle):
    """Post newsletter to Beehiiv as a draft."""
    api_key = os.getenv("BEEHIIV_API_KEY")
    pub_id = os.getenv("BEEHIIV_PUB_ID")

    if not api_key or not pub_id:
        print("  Beehiiv credentials not configured. Skipping.")
        return None

    resp = requests.post(
        f"https://api.beehiiv.com/v2/publications/{pub_id}/posts",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "title": title,
            "subtitle": subtitle,
            "status": "draft",
            "content_tags": ["economic-sentiment", "markets"],
            "body": {
                "html": html,
            },
        },
        timeout=30,
    )

    if resp.status_code in (200, 201):
        post_data = resp.json().get("data", {})
        post_id = post_data.get("id", "unknown")
        print(f"  Beehiiv draft created: {post_id}")
        return post_id
    else:
        print(f"  Beehiiv API error {resp.status_code}: {resp.text[:200]}")
        return None


# ---------------------------------------------------------------------------
# X/Twitter Publishing (stub — activated when OAuth configured)
# ---------------------------------------------------------------------------

def publish_to_x(thread_texts):
    """Post thread to X/Twitter. Requires OAuth 1.0a credentials.

    thread_texts: list of tweet strings (each <=280 chars)
    """
    consumer_key = os.getenv("X_CONSUMER_KEY")
    consumer_secret = os.getenv("X_CONSUMER_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        print("  X/Twitter OAuth credentials not configured. Skipping.")
        return None

    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

        # Post thread: first tweet, then replies
        previous_id = None
        posted_ids = []

        for tweet_text in thread_texts:
            if previous_id:
                resp = client.create_tweet(
                    text=tweet_text,
                    in_reply_to_tweet_id=previous_id,
                )
            else:
                resp = client.create_tweet(text=tweet_text)

            tweet_id = resp.data["id"]
            posted_ids.append(tweet_id)
            previous_id = tweet_id
            print(f"  Posted tweet: {tweet_id}")

        print(f"  X thread posted: {len(posted_ids)} tweets")
        return posted_ids

    except ImportError:
        print("  tweepy not installed. Skipping X posting.")
        return None
    except Exception as e:
        print(f"  X posting failed: {e}")
        return None
