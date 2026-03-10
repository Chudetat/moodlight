"""
email_templates.py
Shared email design primitives for Moodlight.
All emails use the same visual language: left-border headers, colored sections,
#fafafa content blocks, Arial typography, 700px max-width.

Extracted from generate_brief.py's design — the template for all email types.
"""

import re
from datetime import datetime, timezone

SEVERITY_COLORS = {
    "critical": "#DC143C",
    "warning": "#FFB300",
    "info": "#1976D2",
}

SECTION_COLORS = {
    # Daily brief
    "KEY THREATS": "#DC143C",
    "WATCH LIST": "#FFB300",
    "EMERGING PATTERNS": "#1976D2",
    "FORWARD LOOK": "#7B1FA2",
    "RECOMMENDED ACTIONS": "#2E7D32",
    # Weekly digest
    "EXECUTIVE SUMMARY": "#1976D2",
    "TOP PATTERNS": "#DC143C",
    "VLDS TRENDS": "#FFB300",
    "COMPETITIVE SHIFTS": "#7B1FA2",
    "FORWARD-LOOKING ASSESSMENT": "#1976D2",
    "RECOMMENDED STRATEGIC ACTIONS": "#2E7D32",
    # Alert emails
    "BOTTOM LINE": "#DC143C",
    "WHY THIS MATTERS": "#FFB300",
    "KEY EVIDENCE": "#1976D2",
    "ANALYSIS": "#1976D2",
    "IMPLICATIONS": "#FFB300",
    "WATCH ITEMS": "#2E7D32",
    # Situation reports
    "CONNECTION": "#1976D2",
    "RECOMMENDED ACTION": "#2E7D32",
}

# Cycle for sections without explicit color mapping
_DEFAULT_COLORS = ["#1976D2", "#DC143C", "#FFB300", "#7B1FA2", "#2E7D32", "#E65100"]


def render_email(badge_text, badge_color, title, body_html,
                 footer_text="Moodlight Intelligence Platform",
                 extra_badges_html=""):
    """Complete email wrapper — header + body + footer."""
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
        <div style="border-left: 4px solid {badge_color}; padding-left: 15px; margin-bottom: 20px;">
          <span style="background: {badge_color}; color: white; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: bold;">
            {badge_text}
          </span>
          {extra_badges_html}
          <h2 style="margin: 10px 0 5px 0; color: #333;">{title}</h2>
          <p style="color: #666; margin: 0;">{date_str}</p>
        </div>

        {body_html}

        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">
          {footer_text}<br>
          <a href="https://moodlight.app" style="color: #1976D2;">View Dashboard</a>
        </p>
      </body>
    </html>
    """


def render_section(title, content_html, color="#1976D2"):
    """Single section: colored left-border header + #fafafa bg content block."""
    if not content_html or not content_html.strip():
        return ""

    return (
        f'<div style="margin: 20px 0;">'
        f'<div style="border-left: 3px solid {color}; padding-left: 12px; margin-bottom: 8px;">'
        f'<h3 style="margin: 0; color: {color}; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">{title}</h3>'
        f'</div>'
        f'<div style="background: #fafafa; padding: 12px 15px; border-radius: 8px;">'
        f'<div style="font-size: 15px; color: #333; line-height: 1.6;">{content_html}</div>'
        f'</div>'
        f'</div>'
    )


def render_confidence_bar(confidence, recommendation):
    """Confidence bar + recommendation label. Returns HTML block."""
    oc = confidence or 0
    rec = recommendation or "monitor"
    rec_labels = {
        "act_now": "Act Now",
        "monitor": "Monitor",
        "investigate_further": "Investigate",
    }

    if oc >= 75:
        conf_color = "#2E7D32"
    elif oc >= 40:
        conf_color = "#F9A825"
    else:
        conf_color = "#C62828"

    filled = max(1, int(oc / 100 * 16))
    bar = "\u2588" * filled + "\u2591" * (16 - filled)

    return (
        f'<div style="margin: 12px 0 20px 0; padding: 8px 15px; background: #fafafa; border-radius: 8px;">'
        f'<span style="font-size: 13px; color: #555;">Confidence: '
        f'<strong style="color: {conf_color};">{oc}/100</strong></span>'
        f'<span style="margin-left: 12px; font-size: 13px; color: #555;">| {rec_labels.get(rec, rec)}</span>'
        f'<br>'
        f'<span style="font-family: monospace; font-size: 12px; color: {conf_color}; letter-spacing: 1px;">{bar}</span>'
        f'</div>'
    )


def markdown_to_html(text):
    """Convert bold, bullets, numbered lists, styled tags, arrows to HTML."""
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Numbered list items
    text = re.sub(
        r'^(\d+)\.\s+(.+)$',
        r'<div style="margin: 6px 0; padding-left: 8px;">'
        r'<span style="color: #999; font-size: 13px;">\1.</span> \2</div>',
        text,
        flags=re.MULTILINE,
    )

    # Bullet items
    text = re.sub(
        r'^[-\u2022]\s+(.+)$',
        r'<div style="margin: 4px 0; padding-left: 12px;">'
        r'<span style="color: #999;">&#8226;</span> \1</div>',
        text,
        flags=re.MULTILINE,
    )

    # Tags: [NEW], [ONGOING], [HIGH CONFIDENCE], etc.
    def _style_tag(m):
        tag = m.group(1)
        if tag in ("NEW",):
            return (
                f'<span style="background: #E8F5E9; color: #2E7D32; padding: 1px 6px; '
                f'border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
            )
        elif tag in ("ONGOING",):
            return (
                f'<span style="background: #FFF3E0; color: #E65100; padding: 1px 6px; '
                f'border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
            )
        elif "CONFIDENCE" in tag:
            return (
                f'<span style="background: #E3F2FD; color: #1565C0; padding: 1px 6px; '
                f'border-radius: 3px; font-size: 11px;">{tag}</span>'
            )
        elif tag in ("IMMEDIATE", "SHORT-TERM", "MONITOR"):
            return (
                f'<span style="background: #F3E5F5; color: #7B1FA2; padding: 1px 6px; '
                f'border-radius: 3px; font-size: 11px; font-weight: bold;">{tag}</span>'
            )
        return (
            f'<span style="background: #ECEFF1; color: #546E7A; padding: 1px 6px; '
            f'border-radius: 3px; font-size: 11px;">{tag}</span>'
        )

    text = re.sub(r'\[([A-Z][A-Z \-]+?)\]', _style_tag, text)

    # Arrows
    text = text.replace("\u2191", '<span style="color: #DC143C;">&#8593;</span>')
    text = text.replace("\u2193", '<span style="color: #2E7D32;">&#8595;</span>')

    # Paragraph breaks
    text = re.sub(r'\n\s*\n', '</p><p style="margin: 8px 0;">', text)
    text = text.replace("\n", "<br>")

    return text


def parse_and_render_sections(text, section_colors=None):
    """Parse section headers from plain text and render as styled sections.

    Recognises two header patterns:
      1. ALL-CAPS lines (e.g. ``KEY THREATS:``), used by daily briefs and digests.
      2. Markdown ``## `` headers (e.g. ``## 1. WHERE TO PLAY: ...``), used by
         strategic briefs.

    Returns body HTML string ready to embed inside ``render_email()``.
    """
    colors = {**SECTION_COLORS, **(section_colors or {})}
    default_idx = 0

    sections_html = []
    current_section = None
    current_lines = []

    def _save_section():
        nonlocal default_idx
        content = "\n".join(current_lines).strip()
        if not content:
            return
        color = colors.get(current_section.upper() if current_section else "", None)
        if color is None:
            color = _DEFAULT_COLORS[default_idx % len(_DEFAULT_COLORS)]
            default_idx += 1
        sections_html.append(
            render_section(current_section, markdown_to_html(content), color)
        )

    for line in text.split("\n"):
        stripped = line.strip()

        # Skip known title lines
        if (stripped.startswith("DAILY INTELLIGENCE BRIEF")
                or stripped.startswith("WEEKLY STRATEGIC DIGEST")):
            continue
        if stripped.startswith("==="):
            continue
        # Skip bare --- separators (but not inside content)
        if re.match(r'^-{3,}\s*$', stripped) and not current_section:
            continue

        header_title = None

        # Pattern 1: ALL-CAPS header (e.g. "KEY THREATS:" or "EXECUTIVE SUMMARY")
        if (stripped
                and re.match(r'^[A-Z][A-Z &\-/]+:?\s*$', stripped)
                and len(stripped) > 3
                and stripped not in ("DATA:", "FORMAT:")):
            header_title = stripped.rstrip(":")

        # Pattern 2: Markdown ## header (e.g. "## 1. WHERE TO PLAY: ...")
        elif re.match(r'^#{1,3}\s+', stripped):
            title = re.sub(r'^#{1,3}\s+', '', stripped)
            title = re.sub(r'^\d+\.\s*', '', title)
            # Strip leading emojis
            title = re.sub(
                r'^[\U0001F300-\U0001F9FF\u2600-\u26FF\u2700-\u27BF\uFE0F]+\s*',
                '', title,
            )
            header_title = title.strip()

        if header_title:
            if current_section:
                _save_section()
            current_section = header_title
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    if current_section:
        _save_section()
    elif current_lines:
        # No sections detected — render as single block
        content = "\n".join(current_lines).strip()
        if content:
            sections_html.append(
                f'<div style="margin: 15px 0;">'
                f'<p style="font-size: 15px; color: #333; line-height: 1.6;">'
                f'{markdown_to_html(content)}</p>'
                f'</div>'
            )

    return "\n".join(sections_html)
