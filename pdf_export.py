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
    _render_markdown_to_pdf(pdf, report_text or "")

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
    label = product[:80] if product else "Brief"
    pdf.cell(0, 7, f"{label}  |  {datetime.now(timezone.utc).strftime('%B %d, %Y')}", ln=True)
    pdf.ln(5)

    _render_markdown_to_pdf(pdf, brief_text or "")

    return bytes(pdf.output())
