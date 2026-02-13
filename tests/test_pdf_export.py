"""Tests for pdf_export.py"""
from pdf_export import generate_report_pdf, generate_brief_pdf


class TestGenerateReportPdf:
    def test_returns_bytes(self):
        result = generate_report_pdf("## Test Report\n\nSome content here.", "TestBrand", 7)
        assert isinstance(result, bytes)

    def test_contains_pdf_header(self):
        result = generate_report_pdf("Test", "Brand", 7)
        assert result[:5] == b"%PDF-"

    def test_handles_empty_text(self):
        result = generate_report_pdf("", "Empty", 7)
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"

    def test_handles_markdown_formatting(self):
        md = """# Main Title
## Section One
### Subsection

- Bullet point one
- Bullet point two

1. Numbered item
2. Another item

Some **bold text** in a paragraph.

---

Another section after a rule.
"""
        result = generate_report_pdf(md, "Formatted", 30)
        assert isinstance(result, bytes)
        assert len(result) > 100


class TestGenerateBriefPdf:
    def test_returns_bytes(self):
        result = generate_brief_pdf("Brief content here", "Running Shoes")
        assert isinstance(result, bytes)

    def test_contains_pdf_header(self):
        result = generate_brief_pdf("Test brief", "Product")
        assert result[:5] == b"%PDF-"

    def test_handles_empty_text(self):
        result = generate_brief_pdf("", "")
        assert isinstance(result, bytes)
        assert result[:5] == b"%PDF-"
