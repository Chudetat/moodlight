"""
pdf_export.py
Generate branded PDF reports and briefs for Moodlight.
"""

import os
import re
from datetime import datetime, timezone
from fpdf import FPDF


LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")
BRAND_COLOR = (107, 70, 193)  # Moodlight purple


class MoodlightPDF(FPDF):
    """Branded PDF with Moodlight header and footer."""

    def __init__(self, title: str = "Intelligence Report"):
        super().__init__()
        self.report_title = title
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        # Logo
        if os.path.exists(LOGO_PATH):
            try:
                self.image(LOGO_PATH, 10, 8, 30)
            except Exception:
                pass
        # Brand name
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BRAND_COLOR)
        self.cell(35)  # Offset past logo
        self.cell(0, 10, "MOODLIGHT INTELLIGENCE", ln=True)
        # Rule line
        self.set_draw_color(*BRAND_COLOR)
        self.set_line_width(0.5)
        self.line(10, 20, 200, 20)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.cell(0, 10, f"Generated {date_str}  |  Page {self.page_no()}/{{nb}}", align="C")



# fpdf2's core fonts are latin-1 only, so a single em dash raises
# FPDFUnicodeEncodingException and the whole document fails. Real Ask answers
# are full of them, along with curly quotes and arrows - which is why every
# synthetic ASCII test passed and the first real send produced nothing.
#
# Transliterating rather than embedding a Unicode font is the right trade here:
# it is one function instead of a font file in the image, and plain ASCII is
# already the house rule for anything that gets pasted into a deck.
_PDF_ASCII = {
    "\u2014": " - ", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u2192": "->",
    "\u2190": "<-", "\u2022": "-", "\u00a0": " ", "\u2032": "'",
    "\u2033": '"', "\u2212": "-", "\u00b7": "-", "\u203a": ">",
    "\u2039": "<", "\u2265": ">=", "\u2264": "<=", "\u00d7": "x",
    "\u2248": "~", "\u20ac": "EUR", "\u00a3": "GBP", "\u2122": "(TM)",
    "\u00ae": "(R)", "\u00a9": "(c)",
}


def _pdf_safe(text: str) -> str:
    """Make text renderable by a latin-1 core font without losing meaning.

    Accented characters in real words are preserved: latin-1 covers them, and
    Mazatlan spelled properly matters more than tidiness. Anything still outside
    the range after substitution is dropped rather than allowed to fail the
    document.
    """
    if not text:
        return ""
    for bad, good in _PDF_ASCII.items():
        text = text.replace(bad, good)
    # An em dash usually arrives already spaced (" - " becomes "  -  "), so
    # collapse runs of spaces and tabs. Newlines are preserved: the markdown
    # renderer downstream needs them for paragraphs and bullets.
    text = re.sub(r"[ \t]{2,}", " ", text)
    try:
        text.encode("latin-1")
        return text
    except UnicodeEncodeError:
        return text.encode("latin-1", "ignore").decode("latin-1")


def _render_markdown_to_pdf(pdf: MoodlightPDF, text: str):
    """Parse markdown text and render to PDF."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Horizontal rule
        if stripped in ("---", "***", "___"):
            pdf.set_draw_color(200, 200, 200)
            pdf.set_line_width(0.3)
            y = pdf.get_y()
            pdf.line(10, y, 200, y)
            pdf.ln(4)
            i += 1
            continue

        # H1 header (# )
        if stripped.startswith("# ") and not stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(*BRAND_COLOR)
            pdf.multi_cell(0, 8, stripped[2:].strip())
            pdf.ln(2)
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        # H2 header (## )
        if stripped.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(*BRAND_COLOR)
            pdf.multi_cell(0, 7, stripped[3:].strip())
            pdf.ln(2)
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        # H3 header (### )
        if stripped.startswith("### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(0, 6, stripped[4:].strip())
            pdf.ln(1)
            pdf.set_text_color(0, 0, 0)
            i += 1
            continue

        # Bullet list item
        if stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            content = _strip_bold(stripped[2:])
            pdf.cell(8)
            pdf.multi_cell(0, 5, f"-  {content}")
            pdf.ln(1)
            i += 1
            continue

        # Numbered list item
        num_match = re.match(r"^(\d+)\.\s+(.+)", stripped)
        if num_match:
            pdf.set_font("Helvetica", "", 10)
            num, content = num_match.group(1), _strip_bold(num_match.group(2))
            pdf.cell(8)
            pdf.multi_cell(0, 5, f"{num}.  {content}")
            pdf.ln(1)
            i += 1
            continue

        # Empty line
        if not stripped:
            pdf.ln(3)
            i += 1
            continue

        # Regular paragraph — collect consecutive non-empty, non-special lines
        para_lines = []
        while i < len(lines):
            l = lines[i].strip()
            if not l or l.startswith("#") or l.startswith("- ") or l.startswith("* ") or l in ("---", "***", "___"):
                break
            if re.match(r"^\d+\.\s+", l):
                break
            para_lines.append(l)
            i += 1

        if para_lines:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 30)
            text_block = _strip_bold(" ".join(para_lines))
            pdf.multi_cell(0, 5, text_block)
            pdf.ln(2)
            pdf.set_text_color(0, 0, 0)
            continue

        i += 1


def _strip_bold(text: str) -> str:
    """Remove markdown bold markers (**text**) for PDF rendering."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def generate_report_pdf(report_text: str, subject: str, days: int = 7) -> bytes:
    """Generate branded PDF from intelligence report markdown.
    Returns PDF file contents as bytes."""
    pdf = MoodlightPDF(title=f"Intelligence Report: {subject}")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title page heading
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*BRAND_COLOR)
    pdf.cell(0, 12, f"Intelligence Report: {subject}", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7, f"Last {days} days  |  {datetime.now(timezone.utc).strftime('%B %d, %Y')}", ln=True)
    pdf.ln(5)

    # Render report content
    _render_markdown_to_pdf(pdf, _pdf_safe(report_text or ""))

    return bytes(pdf.output())


def generate_brief_pdf(brief_text: str, product: str) -> bytes:
    """Generate branded PDF from strategic brief.
    Returns PDF file contents as bytes."""
    pdf = MoodlightPDF(title=f"Strategic Brief: {product}")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*BRAND_COLOR)
    pdf.cell(0, 12, "Strategic Brief", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    label = _pdf_safe(product[:80] if product else "Brief")
    pdf.cell(0, 7, f"{label}  |  {datetime.now(timezone.utc).strftime('%B %d, %Y')}", ln=True)
    pdf.ln(5)

    _render_markdown_to_pdf(pdf, _pdf_safe(brief_text or ""))

    return bytes(pdf.output())


def generate_ask_pdf(answer_text: str, question: str = "") -> bytes:
    """The read a visitor asked for, as a document they can keep.

    Deliberately NOT generate_brief_pdf: that titles everything "Strategic
    Brief", which is the brief generator's name for its own output and wrong for
    an answer to a question somebody typed. It also printed the raw question as
    a subtitle, and a real Ask question runs to hundreds of characters - the
    GoodNews one was 1,800 - so it overflowed.

    Carries the site in the footer. The whole point of this document is that
    someone keeps it and can find their way back three weeks later; without a
    URL on the page it is an orphan.
    """
    pdf = MoodlightPDF(title="Moodlight Read")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*BRAND_COLOR)
    pdf.cell(0, 12, "Moodlight Read", ln=True)

    # Measure the string instead of guessing a character count. A 92-char cap
    # looked safe and still ran off the page, because the date that follows it
    # was never counted - the first real two-page read came out reading
    # "September 10, 20" with the rest past the right margin.
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    stamp = datetime.now(timezone.utc).strftime("%B %d, %Y")
    q = _pdf_safe(" ".join((question or "").split()))
    avail = pdf.w - pdf.l_margin - pdf.r_margin
    sep = "  |  "
    if q:
        # Trim the question, on word boundaries, until the whole line fits.
        while q and pdf.get_string_width(q + sep + stamp) > avail:
            cut = q.rsplit(" ", 1)[0] if " " in q else ""
            q = (cut + "...") if cut else ""
            if q.endswith("......"):
                q = q[:-3]
        line = f"{q}{sep}{stamp}" if q else stamp
    else:
        line = stamp
    pdf.cell(0, 7, line, ln=True)
    pdf.ln(5)

    _render_markdown_to_pdf(pdf, _pdf_safe(answer_text or ""))

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, "Generated from live cultural signal at moodlightintel.com", ln=True)

    return bytes(pdf.output())
