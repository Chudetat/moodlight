"""PDF report generation service."""
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.widgets.markers import makeMarker


class PDFReportService:
    """Service for generating post-event PDF reports."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Add custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='EventTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=20,
            textColor=colors.HexColor('#1a1a2e'),
        ))
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#16213e'),
        ))
        self.styles.add(ParagraphStyle(
            name='StatLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
        ))
        self.styles.add(ParagraphStyle(
            name='StatValue',
            parent=self.styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a2e'),
        ))

    def generate_report(
        self,
        event_name: str,
        event_start: datetime,
        event_end: datetime,
        location: Optional[str],
        participant_count: int,
        heart_rate_timeline: List[Dict[str, Any]],
        peak_moments: List[Dict[str, Any]],
        overall_avg_bpm: float,
        overall_max_bpm: int,
    ) -> bytes:
        """Generate a PDF report for an event."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        story = []

        # Title
        story.append(Paragraph(f"Dopa Event Report", self.styles['EventTitle']))
        story.append(Paragraph(event_name, self.styles['Heading2']))
        story.append(Spacer(1, 10))

        # Event info
        event_info = f"""
        <b>Date:</b> {event_start.strftime('%B %d, %Y')}<br/>
        <b>Time:</b> {event_start.strftime('%I:%M %p')} - {event_end.strftime('%I:%M %p')}<br/>
        <b>Location:</b> {location or 'Not specified'}<br/>
        <b>Participants:</b> {participant_count}
        """
        story.append(Paragraph(event_info, self.styles['Normal']))
        story.append(Spacer(1, 20))

        # Summary statistics
        story.append(Paragraph("Summary Statistics", self.styles['SectionTitle']))
        stats_data = [
            ['Average Heart Rate', 'Peak Heart Rate', 'Participants'],
            [f'{overall_avg_bpm:.0f} BPM', f'{overall_max_bpm} BPM', str(participant_count)],
        ]
        stats_table = Table(stats_data, colWidths=[2.2 * inch, 2.2 * inch, 2.2 * inch])
        stats_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#666666')),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 18),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#1a1a2e')),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            ('TOPPADDING', (0, 1), (-1, 1), 5),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 30))

        # Heart rate timeline chart
        if heart_rate_timeline:
            story.append(Paragraph("Heart Rate Timeline", self.styles['SectionTitle']))
            chart_drawing = self._create_timeline_chart(heart_rate_timeline)
            story.append(chart_drawing)
            story.append(Spacer(1, 20))

        # Peak moments
        if peak_moments:
            story.append(Paragraph("Peak Moments", self.styles['SectionTitle']))
            story.append(Paragraph(
                "Times when collective heart rate spiked, indicating high engagement:",
                self.styles['Normal']
            ))
            story.append(Spacer(1, 10))

            peaks_data = [['Time', 'Avg BPM', 'Description']]
            for peak in peak_moments[:10]:  # Top 10 peaks
                peaks_data.append([
                    peak['timestamp'].strftime('%I:%M %p'),
                    f"{peak['avg_bpm']:.0f}",
                    peak.get('description', '-'),
                ])

            peaks_table = Table(peaks_data, colWidths=[1.5 * inch, 1 * inch, 4 * inch])
            peaks_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ]))
            story.append(peaks_table)

        # Footer
        story.append(Spacer(1, 40))
        story.append(Paragraph(
            f"Report generated on {datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')}",
            self.styles['StatLabel']
        ))
        story.append(Paragraph("Powered by Dopa - Biometric Event Measurement", self.styles['StatLabel']))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def _create_timeline_chart(self, timeline_data: List[Dict[str, Any]]) -> Drawing:
        """Create a line chart showing heart rate over time."""
        drawing = Drawing(500, 200)

        # Prepare data - aggregate by minute for readability
        if not timeline_data:
            return drawing

        # Sample data points for chart (max 60 points)
        step = max(1, len(timeline_data) // 60)
        sampled_data = timeline_data[::step]

        bpm_values = [d['bpm'] for d in sampled_data]

        chart = HorizontalLineChart()
        chart.x = 50
        chart.y = 30
        chart.width = 400
        chart.height = 150

        chart.data = [bpm_values]

        chart.valueAxis.valueMin = max(40, min(bpm_values) - 10)
        chart.valueAxis.valueMax = min(200, max(bpm_values) + 10)
        chart.valueAxis.valueStep = 20

        chart.categoryAxis.labels.boxAnchor = 'n'
        chart.categoryAxis.labels.angle = 0
        chart.categoryAxis.labels.visible = False

        chart.lines[0].strokeColor = colors.HexColor('#e94560')
        chart.lines[0].strokeWidth = 2

        drawing.add(chart)

        # Add axis labels
        from reportlab.graphics.shapes import String
        drawing.add(String(250, 5, 'Time', fontSize=10, textAnchor='middle'))
        drawing.add(String(15, 100, 'BPM', fontSize=10, textAnchor='middle'))

        return drawing


def get_pdf_service() -> PDFReportService:
    """Dependency for getting PDF service instance."""
    return PDFReportService()
