# backend/app/services/report_generator.py
import os
import json
import csv
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
    KeepTogether,
    Frame,
    Flowable,
    PageTemplate,
    BaseDocTemplate,
    FrameBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Group
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import LineChart
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.pdfgen import canvas
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")
from matplotlib.ticker import FuncFormatter
import io
import base64
import math

logger = logging.getLogger(__name__)

# Register fonts for better PDF rendering
try:
    pdfmetrics.registerFont(TTFont("Helvetica", "Helvetica"))
    pdfmetrics.registerFont(TTFont("Helvetica-Bold", "Helvetica-Bold"))
    pdfmetrics.registerFont(TTFont("Helvetica-Oblique", "Helvetica-Oblique"))
except Exception as e:
    logger.warning(f"Failed to register fonts: {e}")


class WatermarkCanvas(canvas.Canvas):
    """Custom canvas with watermark and page numbers"""

    def __init__(self, *args, **kwargs):
        self.watermark_text = kwargs.pop("watermark_text", "Pesa Analyser")
        self.show_watermark = kwargs.pop("show_watermark", True)
        super().__init__(*args, **kwargs)
        self.page_count = 0

    def showPage(self):
        self.page_count += 1
        super().showPage()

    def drawWatermark(self):
        """Draw faint watermark on each page"""
        if not self.show_watermark:
            return

        self.saveState()
        self.setFillColor(colors.HexColor("#1a1a2e"))
        self.setFillAlpha(0.03)
        self.setFont("Helvetica", 60)
        self.rotate(45)

        text_width = pdfmetrics.stringWidth(self.watermark_text, "Helvetica", 60)
        x = (self._pagesize[0] - text_width) / 2 - 100
        y = (self._pagesize[1] - 60) / 2 - 100

        self.drawString(x, y, self.watermark_text)
        self.restoreState()

    def drawPageNumber(self):
        """Draw page number at bottom of each page"""
        self.saveState()
        self.setFillColor(colors.HexColor("#64748b"))
        self.setFont("Helvetica", 8)

        page_text = f"Page {self.page_count}"
        text_width = pdfmetrics.stringWidth(page_text, "Helvetica", 8)
        x = (self._pagesize[0] - text_width) / 2
        y = 0.35 * inch

        self.drawString(x, y, page_text)
        self.restoreState()

    def drawFooter(self):
        """Draw footer with company info"""
        self.saveState()
        self.setFillColor(colors.HexColor("#64748b"))
        self.setFont("Helvetica", 7)

        footer_text = "Pesa Analyser - Financial Intelligence Platform | support@pesa-analyser.com | +254 700 000 000"
        text_width = pdfmetrics.stringWidth(footer_text, "Helvetica", 7)
        x = (self._pagesize[0] - text_width) / 2
        y = 0.2 * inch

        self.drawString(x, y, footer_text)

        # Draw decorative line
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(0.5 * inch, 0.4 * inch, self._pagesize[0] - 0.5 * inch, 0.4 * inch)

        self.restoreState()

    def drawPageFrame(self):
        """Draw a subtle page frame"""
        self.saveState()
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setStrokeAlpha(0.3)
        self.setLineWidth(0.5)

        margin = 0.4 * inch
        width = self._pagesize[0] - (2 * margin)
        height = self._pagesize[1] - (2 * margin)

        self.roundRect(margin, margin, width, height, 5, stroke=1, fill=0)

        self.restoreState()

    def afterPage(self):
        """Called after each page is drawn"""
        self.drawWatermark()
        self.drawPageNumber()
        self.drawFooter()
        self.drawPageFrame()


class CustomDocTemplate(BaseDocTemplate):
    """Custom document template with frames"""

    def __init__(self, filename, **kwargs):
        self.watermark_text = kwargs.pop("watermark_text", "Pesa Analyser")
        self.show_watermark = kwargs.pop("show_watermark", True)

        frame_margin = 0.6 * inch
        frame_width = A4[0] - (2 * frame_margin)
        frame_height = A4[1] - (2 * frame_margin)

        frames = [
            Frame(
                frame_margin,
                frame_margin,
                frame_width,
                frame_height,
                id="main",
                showBoundary=0,
                leftPadding=0,
                rightPadding=0,
                topPadding=0,
                bottomPadding=0,
            )
        ]

        super().__init__(filename, **kwargs)
        self.addPageTemplates(
            [
                PageTemplate(
                    id="main",
                    frames=frames,
                    onPage=self._on_page,
                )
            ]
        )

    def _on_page(self, canvas, doc):
        """Custom page rendering"""
        canvas.saveState()

        # Watermark
        if self.show_watermark:
            canvas.setFillColor(colors.HexColor("#1a1a2e"))
            canvas.setFillAlpha(0.03)
            canvas.setFont("Helvetica", 50)
            canvas.rotate(45)

            text_width = pdfmetrics.stringWidth(self.watermark_text, "Helvetica", 50)
            x = (A4[0] - text_width) / 2 - 150
            y = (A4[1] - 50) / 2 - 150

            canvas.drawString(x, y, self.watermark_text)

        # Page number
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.setFont("Helvetica", 8)

        page_num = canvas.getPageNumber()
        page_text = f"Page {page_num}"
        text_width = pdfmetrics.stringWidth(page_text, "Helvetica", 8)
        x = (A4[0] - text_width) / 2
        y = 0.35 * inch

        canvas.drawString(x, y, page_text)

        # Footer
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.setFont("Helvetica", 7)

        footer_text = "Pesa Analyser - Financial Intelligence Platform | support@pesa-analyser.com | +254 700 000 000"
        text_width = pdfmetrics.stringWidth(footer_text, "Helvetica", 7)
        x = (A4[0] - text_width) / 2
        y = 0.2 * inch

        canvas.drawString(x, y, footer_text)

        # Decorative line
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setLineWidth(0.5)
        canvas.line(0.5 * inch, 0.4 * inch, A4[0] - 0.5 * inch, 0.4 * inch)

        # Page frame
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setStrokeAlpha(0.3)
        canvas.setLineWidth(0.5)

        margin = 0.4 * inch
        width = A4[0] - (2 * margin)
        height = A4[1] - (2 * margin)
        canvas.roundRect(margin, margin, width, height, 5, stroke=1, fill=0)

        canvas.restoreState()


class ReportGenerator:
    """Professional PDF Report Generator with Charts and Visualizations"""

    def __init__(self):
        self.report_dir = "./reports"
        os.makedirs(self.report_dir, exist_ok=True)

        self.colors = {
            "primary": colors.HexColor("#1a1a2e"),
            "secondary": colors.HexColor("#16213e"),
            "accent": colors.HexColor("#0f3460"),
            "success": colors.HexColor("#22c55e"),
            "warning": colors.HexColor("#f59e0b"),
            "danger": colors.HexColor("#ef4444"),
            "info": colors.HexColor("#3b82f6"),
            "purple": colors.HexColor("#8b5cf6"),
            "pink": colors.HexColor("#ec4899"),
            "indigo": colors.HexColor("#6366f1"),
            "teal": colors.HexColor("#14b8a6"),
            "light_bg": colors.HexColor("#f8fafc"),
            "border": colors.HexColor("#e2e8f0"),
            "text_muted": colors.HexColor("#64748b"),
            "text_dark": colors.HexColor("#0f172a"),
            "card_bg": colors.HexColor("#ffffff"),
            "shadow": colors.HexColor("#e2e8f0"),
        }

        self.chart_colors = [
            "#0088FE",
            "#00C49F",
            "#FFBB28",
            "#FF8042",
            "#8884d8",
            "#82ca9d",
            "#ffc658",
            "#ff6b6b",
            "#a855f7",
            "#ec4899",
            "#14b8a6",
            "#f59e0b",
        ]

    def generate_pdf_report(self, data: Dict[str, Any]) -> str:
        """Generate a professional PDF report"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.report_dir}/financial_report_{timestamp}.pdf"

            doc = CustomDocTemplate(
                filename,
                pagesize=A4,
                rightMargin=0.75 * inch,
                leftMargin=0.75 * inch,
                topMargin=0.75 * inch,
                bottomMargin=0.75 * inch,
                watermark_text="Pesa Analyser",
                show_watermark=True,
            )

            styles = self._create_styles()
            story = []

            # Sections
            story.extend(self._build_cover_page(data, styles))
            story.append(PageBreak())

            story.extend(self._build_executive_summary(data, styles))
            story.append(PageBreak())

            story.extend(self._build_health_score_section(data, styles))
            story.append(PageBreak())

            story.extend(self._build_key_metrics_section(data, styles))
            story.append(PageBreak())

            story.extend(self._build_charts_section(data, styles))
            story.append(PageBreak())

            story.extend(self._build_category_breakdown(data, styles))
            story.append(PageBreak())

            story.extend(self._build_top_depositors_creditors(data, styles))
            story.append(PageBreak())

            story.extend(self._build_recurring_payments_anomalies(data, styles))
            story.append(PageBreak())

            story.extend(self._build_insights_section(data, styles))
            story.append(PageBreak())

            story.extend(self._build_transaction_summary(data, styles))

            story.append(Spacer(1, 0.5 * inch))

            doc.build(story)
            logger.info(f"✅ PDF report generated: {filename}")
            return filename

        except Exception as e:
            logger.error(f"❌ PDF generation error: {str(e)}", exc_info=True)
            raise

    def _create_styles(self):
        """Create custom styles for the report"""
        styles = getSampleStyleSheet()

        cover_title = ParagraphStyle(
            "CoverTitle",
            parent=styles["Title"],
            fontSize=36,
            textColor=self.colors["primary"],
            alignment=TA_CENTER,
            spaceAfter=15,
            fontName="Helvetica-Bold",
            leading=40,
        )
        styles.add(cover_title)

        cover_subtitle = ParagraphStyle(
            "CoverSubtitle",
            parent=styles["Normal"],
            fontSize=18,
            textColor=self.colors["text_muted"],
            alignment=TA_CENTER,
            spaceAfter=30,
            fontName="Helvetica",
            leading=22,
        )
        styles.add(cover_subtitle)

        section_title = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading1"],
            fontSize=22,
            textColor=self.colors["primary"],
            spaceAfter=15,
            spaceBefore=20,
            fontName="Helvetica-Bold",
            leading=28,
        )
        styles.add(section_title)

        section_subtitle = ParagraphStyle(
            "SectionSubtitle",
            parent=styles["Heading2"],
            fontSize=16,
            textColor=self.colors["text_muted"],
            spaceAfter=12,
            fontName="Helvetica",
            leading=20,
        )
        styles.add(section_subtitle)

        info_style = ParagraphStyle(
            "InfoStyle",
            parent=styles["Normal"],
            fontSize=12,
            textColor=self.colors["text_muted"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            leading=16,
        )
        styles.add(info_style)

        score_style = ParagraphStyle(
            "ScoreStyle",
            parent=styles["Normal"],
            fontSize=32,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            leading=38,
        )
        styles.add(score_style)

        summary_style = ParagraphStyle(
            "SummaryStyle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=self.colors["text_dark"],
            alignment=TA_JUSTIFY,
            fontName="Helvetica",
            spaceAfter=12,
            leading=16,
        )
        styles.add(summary_style)

        insight_style = ParagraphStyle(
            "InsightStyle",
            parent=styles["Normal"],
            fontSize=10.5,
            textColor=self.colors["text_dark"],
            alignment=TA_LEFT,
            fontName="Helvetica",
            leftIndent=15,
            spaceAfter=5,
            leading=14,
        )
        styles.add(insight_style)

        warning_style = ParagraphStyle(
            "WarningStyle",
            parent=styles["Normal"],
            fontSize=10.5,
            textColor=self.colors["danger"],
            alignment=TA_LEFT,
            fontName="Helvetica",
            leftIndent=15,
            spaceAfter=5,
            leading=14,
        )
        styles.add(warning_style)

        rec_style = ParagraphStyle(
            "RecStyle",
            parent=styles["Normal"],
            fontSize=10.5,
            textColor=self.colors["text_dark"],
            alignment=TA_LEFT,
            fontName="Helvetica",
            leftIndent=15,
            spaceAfter=5,
            leading=14,
        )
        styles.add(rec_style)

        footer_style = ParagraphStyle(
            "FooterStyle",
            parent=styles["Normal"],
            fontSize=8,
            textColor=self.colors["text_muted"],
            alignment=TA_CENTER,
            leading=10,
        )
        styles.add(footer_style)

        metric_value_style = ParagraphStyle(
            "MetricValueStyle",
            parent=styles["Normal"],
            fontSize=20,
            textColor=self.colors["primary"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            leading=24,
        )
        styles.add(metric_value_style)

        metric_label_style = ParagraphStyle(
            "MetricLabelStyle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=self.colors["text_muted"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            leading=12,
        )
        styles.add(metric_label_style)

        return styles

    def _create_decorative_line(self, color, height):
        """Create a decorative line for the report"""
        drawing = Drawing(400, height)
        drawing.add(Rect(0, 0, 400, height, fillColor=color, strokeColor=None))
        return drawing

    def _create_section_icon(self, icon):
        """Create a section icon"""
        style = ParagraphStyle(
            "IconStyle",
            parent=getSampleStyleSheet()["Normal"],
            fontSize=24,
            alignment=TA_LEFT,
        )
        return Paragraph(icon, style)

    def _create_progress_bar(
        self, value: float, width: float, show_percentage: bool = False
    ):
        """Create a progress bar for the report"""
        percentage = min(max(value, 0), 100)
        bar_width = (percentage / 100) * width

        if percentage > 70:
            color = self.colors["success"]
        elif percentage > 40:
            color = self.colors["warning"]
        else:
            color = self.colors["danger"]

        if show_percentage:
            bar_data = [[""], [f"{percentage:.0f}%"]]
            bar_table = Table(bar_data, colWidths=[width])
            bar_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), color),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("ALIGN", (0, 1), (0, 1), "CENTER"),
                        ("FONTSIZE", (0, 1), (0, 1), 12),
                        ("FONTNAME", (0, 1), (0, 1), "Helvetica-Bold"),
                        ("TOPPADDING", (0, 1), (0, 1), 2),
                    ]
                )
            )
            return bar_table
        else:
            bar_data = [["", ""]]
            bar_table = Table(bar_data, colWidths=[bar_width, width - bar_width])
            bar_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, 0), color),
                        ("BACKGROUND", (1, 0), (1, 0), self.colors["border"]),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            return bar_table

    def _build_cover_page(self, data: Dict[str, Any], styles) -> List:
        """Build the cover page"""
        story = []
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph("💰 Pesa Analyser", styles["CoverTitle"]))
        story.append(Spacer(1, 0.1 * inch))
        story.append(
            Paragraph("Financial Intelligence Report", styles["CoverSubtitle"])
        )
        story.append(Spacer(1, 0.3 * inch))

        story.append(self._create_decorative_line(self.colors["success"], 0.08 * inch))
        story.append(Spacer(1, 0.3 * inch))

        metadata = [
            [
                "File Name",
                (
                    data.get("file_name", "N/A")[:60] + "..."
                    if len(data.get("file_name", "")) > 60
                    else data.get("file_name", "N/A")
                ),
            ],
            [
                "Analysis Date",
                data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M")),
            ],
            ["Analysis ID", data.get("id", "N/A")[:12] + "..."],
            ["Statement Type", data.get("statement_type", "N/A").upper()],
        ]

        meta_table = Table(metadata, colWidths=[2 * inch, 3.5 * inch])
        meta_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                    ("ALIGN", (1, 0), (1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (0, -1), self.colors["text_muted"]),
                    ("TEXTCOLOR", (1, 0), (1, -1), self.colors["text_dark"]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 0.5 * inch))

        health_score = data.get("health_score", 0)
        score_color = (
            self.colors["success"]
            if health_score > 70
            else self.colors["warning"] if health_score > 40 else self.colors["danger"]
        )

        score_style = ParagraphStyle(
            "CoverScoreStyle", parent=styles["ScoreStyle"], textColor=score_color
        )
        story.append(
            Paragraph(f"Financial Health Score: {health_score}/100", score_style)
        )
        story.append(Spacer(1, 0.1 * inch))
        story.append(
            self._create_progress_bar(health_score, 4 * inch, show_percentage=True)
        )
        story.append(Spacer(1, 1.5 * inch))

        return story

    def _build_executive_summary(self, data: Dict[str, Any], styles) -> List:
        """Build the executive summary section"""
        story = []
        story.append(self._create_section_icon("📊"))
        story.append(Paragraph("Executive Summary", styles["SectionTitle"]))
        story.append(Spacer(1, 0.1 * inch))

        total_income = data.get("total_income", 0)
        total_expenses = data.get("total_expenses", 0)
        net_cash_flow = data.get("net_cash_flow", 0)
        total_tx = data.get("total_transactions", 0)
        savings_rate = data.get("savings_rate", 0)

        summary_text = f"""
        This comprehensive financial analysis report provides deep insights into your 
        financial activities. Based on the analysis of <b>{total_tx:,}</b> transactions 
        from <b>{data.get('statement_type', 'N/A').upper()}</b> statements, we've identified 
        key patterns and opportunities for financial optimization.
        """

        story.append(Paragraph(summary_text, styles["SummaryStyle"]))
        story.append(Spacer(1, 0.2 * inch))

        # Key metrics cards
        highlight_data = [
            ["", "Total Income", "Total Expenses", "Net Flow"],
            [
                "📈",
                f"KES {total_income:,.0f}",
                f"KES {total_expenses:,.0f}",
                f"KES {net_cash_flow:,.0f}",
            ],
            ["", "⬆️ Income", "⬇️ Expenses", "📊 Balance"],
        ]

        highlight_table = Table(
            highlight_data, colWidths=[0.8 * inch, 1.8 * inch, 1.8 * inch, 1.8 * inch]
        )
        highlight_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, 1), self.colors["light_bg"]),
                    ("TEXTCOLOR", (0, 1), (-1, 1), self.colors["primary"]),
                    ("FONTSIZE", (0, 1), (-1, 1), 14),
                    ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 2), (-1, 2), self.colors["light_bg"]),
                    ("FONTSIZE", (0, 2), (-1, 2), 9),
                    ("TEXTCOLOR", (0, 2), (-1, 2), self.colors["text_muted"]),
                    ("GRID", (0, 0), (-1, -1), 1, self.colors["border"]),
                    ("TOPPADDING", (0, 1), (-1, 1), 8),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                ]
            )
        )
        story.append(highlight_table)
        story.append(Spacer(1, 0.3 * inch))

        # Additional stats
        stats_data = [
            ["📊 Savings Rate", "💳 Avg Balance", "🔥 Burn Rate", "⭐ Health Score"],
            [
                f"{savings_rate:.1f}%",
                f"KES {data.get('average_balance', 0):,.0f}",
                f"KES {data.get('burn_rate_daily', 0):,.0f}/day",
                f"{data.get('health_score', 0)}/100",
            ],
        ]

        stats_table = Table(
            stats_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch, 1.8 * inch]
        )
        stats_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.colors["accent"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, 1), 14),
                    ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 1), (-1, 1), self.colors["primary"]),
                    ("BACKGROUND", (0, 1), (-1, 1), self.colors["light_bg"]),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                    ("TOPPADDING", (0, 1), (-1, 1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, self.colors["border"]),
                ]
            )
        )
        story.append(stats_table)

        return story

    def _build_health_score_section(self, data: Dict[str, Any], styles) -> List:
        """Build the health score section"""
        story = []
        story.append(self._create_section_icon("❤️"))
        story.append(
            Paragraph("Financial Health Score Breakdown", styles["SectionTitle"])
        )
        story.append(Spacer(1, 0.1 * inch))

        health_score = data.get("health_score", 0)
        breakdown = data.get("health_breakdown", {})

        story.append(
            Paragraph(
                f"Overall Score: <b>{health_score}/100</b>", styles["SectionSubtitle"]
            )
        )

        health_data = [["Component", "Score", "Status"]]

        components = (
            breakdown.items()
            if breakdown
            else [
                ("Fuliza Dependency", 0),
                ("Income Quality", 0),
                ("Savings Rate", 0),
                ("Betting", 0),
                ("Transaction Volume", 0),
            ]
        )

        for comp, value in components:
            if isinstance(value, int):
                status = "✅" if value > 10 else "⚠️" if value > 0 else "❌"
                health_data.append([comp.replace("_", " ").title(), f"{value}", status])

        health_table = Table(health_data, colWidths=[2.5 * inch, 1.5 * inch, 1 * inch])
        health_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                    ("GRID", (0, 0), (-1, -1), 1, self.colors["border"]),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ]
            )
        )
        story.append(health_table)

        return story

    def _build_key_metrics_section(self, data: Dict[str, Any], styles) -> List:
        """Build the key metrics section"""
        story = []
        story.append(self._create_section_icon("📈"))
        story.append(Paragraph("Key Financial Metrics", styles["SectionTitle"]))
        story.append(Spacer(1, 0.1 * inch))

        metrics = [
            ["Metric", "Value"],
            ["Total Income", f"KES {data.get('total_income', 0):,.0f}"],
            ["Total Expenses", f"KES {data.get('total_expenses', 0):,.0f}"],
            ["Net Cash Flow", f"KES {data.get('net_cash_flow', 0):,.0f}"],
            ["Average Balance", f"KES {data.get('average_balance', 0):,.0f}"],
            ["Total Fees", f"KES {data.get('total_fees', 0):,.0f}"],
            ["Total Transactions", f"{data.get('total_transactions', 0)}"],
            ["Savings Rate", f"{data.get('savings_rate', 0):.1f}%"],
            ["Burn Rate (Daily)", f"KES {data.get('burn_rate_daily', 0):,.0f}"],
            [
                "Fuliza Usage",
                f"{data.get('fuliza_count', 0)} tx (KES {data.get('fuliza_total', 0):,.0f})",
            ],
            ["Betting", f"{data.get('betting_pct', 0):.1f}% of expenses"],
            ["P2P Transfers", f"{data.get('p2p_count', 0)} transactions"],
            ["Top Category", data.get("top_category", "N/A").title()],
            ["Top Income Source", data.get("top_income_source", "N/A").title()],
        ]

        metrics_table = Table(metrics, colWidths=[2.5 * inch, 2.5 * inch])
        metrics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                    ("GRID", (0, 0), (-1, -1), 1, self.colors["border"]),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("LEFTPADDING", (0, 1), (0, -1), 10),
                ]
            )
        )
        story.append(metrics_table)

        return story

    def _build_charts_section(self, data: Dict[str, Any], styles) -> List:
        """Build the charts section"""
        story = []
        story.append(self._create_section_icon("📊"))
        story.append(Paragraph("Visual Analysis", styles["SectionTitle"]))
        story.append(Spacer(1, 0.1 * inch))

        try:
            monthly_data = data.get("monthly_data", [])
            if monthly_data:
                chart_img = self._create_monthly_chart(monthly_data)
                if chart_img:
                    story.append(
                        Paragraph(
                            "Monthly Income vs Expenses", styles["SectionSubtitle"]
                        )
                    )
                    story.append(chart_img)
                    story.append(Spacer(1, 0.2 * inch))

            category_data = data.get("category_data", [])
            if category_data:
                pie_img = self._create_category_pie_chart(category_data)
                if pie_img:
                    story.append(
                        Paragraph(
                            "Spending Category Breakdown", styles["SectionSubtitle"]
                        )
                    )
                    story.append(pie_img)
                    story.append(Spacer(1, 0.2 * inch))

            day_of_week = data.get("day_of_week_spend", [])
            if day_of_week:
                day_img = self._create_day_of_week_chart(day_of_week)
                if day_img:
                    story.append(
                        Paragraph("Spending by Day of Week", styles["SectionSubtitle"])
                    )
                    story.append(day_img)
                    story.append(Spacer(1, 0.2 * inch))

        except Exception as e:
            logger.warning(f"Chart generation error: {e}")
            story.append(Paragraph("Charts could not be generated", styles["Normal"]))

        return story

    def _build_category_breakdown(self, data: Dict[str, Any], styles) -> List:
        """Build the category breakdown section"""
        story = []
        story.append(self._create_section_icon("📂"))
        story.append(Paragraph("Category Breakdown", styles["SectionTitle"]))
        story.append(Spacer(1, 0.1 * inch))

        category_data = data.get("category_data", [])
        total_expenses = data.get("total_expenses", 0)

        if category_data:
            cat_data = [["Category", "Amount (KES)", "% of Total"]]

            for cat in category_data[:10]:
                amount = cat.get("value", 0)
                pct = (amount / total_expenses * 100) if total_expenses > 0 else 0
                cat_data.append(
                    [
                        cat.get("name", "N/A").title(),
                        f"{amount:,.0f}",
                        f"{pct:.1f}%",
                    ]
                )

            cat_table = Table(cat_data, colWidths=[2.5 * inch, 1.8 * inch, 1.2 * inch])
            cat_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                        ("TOPPADDING", (0, 0), (-1, 0), 8),
                        ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                        ("GRID", (0, 0), (-1, -1), 1, self.colors["border"]),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 10),
                        ("TOPPADDING", (0, 1), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                    ]
                )
            )
            story.append(cat_table)

            # Top category info
            if data.get("top_category"):
                story.append(Spacer(1, 0.1 * inch))
                story.append(
                    Paragraph(
                        f"<b>Top Category:</b> {data.get('top_category', 'N/A').title()} "
                        f"(KES {data.get('top_category_amount', 0):,.0f} - {data.get('top_category_percent', 0):.1f}% of expenses)",
                        styles["SummaryStyle"],
                    )
                )
        else:
            story.append(Paragraph("No category data available", styles["Normal"]))

        return story

    def _build_top_depositors_creditors(self, data: Dict[str, Any], styles) -> List:
        """Build the top depositors and creditors section"""
        story = []
        story.append(self._create_section_icon("👥"))
        story.append(Paragraph("Top Depositors & Creditors", styles["SectionTitle"]))
        story.append(Spacer(1, 0.1 * inch))

        top_depositors = data.get("top_depositors", [])
        top_creditors = data.get("top_creditors", [])

        if top_depositors or top_creditors:
            # Depositors
            if top_depositors:
                story.append(
                    Paragraph("<b>Top 5 Depositors</b>", styles["SectionSubtitle"])
                )
                depositor_data = [["#", "Who", "Amount (KES)"]]
                for i, dep in enumerate(top_depositors[:5], 1):
                    name = (
                        dep.get("who", "N/A")[:40] + "..."
                        if len(dep.get("who", "")) > 40
                        else dep.get("who", "N/A")
                    )
                    depositor_data.append(
                        [str(i), name, f"{dep.get('amount', 0):,.0f}"]
                    )

                dep_table = Table(
                    depositor_data, colWidths=[0.5 * inch, 3.5 * inch, 1.5 * inch]
                )
                dep_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), self.colors["success"]),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 9),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                            ("TOPPADDING", (0, 0), (-1, 0), 6),
                            ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                            ("GRID", (0, 0), (-1, -1), 0.5, self.colors["border"]),
                            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 1), (-1, -1), 8),
                            ("TOPPADDING", (0, 1), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                            ("ALIGN", (0, 1), (0, -1), "CENTER"),
                            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                        ]
                    )
                )
                story.append(dep_table)
                story.append(Spacer(1, 0.1 * inch))

            # Creditors
            if top_creditors:
                story.append(
                    Paragraph("<b>Top 5 Creditors</b>", styles["SectionSubtitle"])
                )
                creditor_data = [["#", "Who", "Amount (KES)"]]
                for i, cred in enumerate(top_creditors[:5], 1):
                    name = (
                        cred.get("who", "N/A")[:40] + "..."
                        if len(cred.get("who", "")) > 40
                        else cred.get("who", "N/A")
                    )
                    creditor_data.append(
                        [str(i), name, f"{cred.get('amount', 0):,.0f}"]
                    )

                cred_table = Table(
                    creditor_data, colWidths=[0.5 * inch, 3.5 * inch, 1.5 * inch]
                )
                cred_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), self.colors["danger"]),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 9),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                            ("TOPPADDING", (0, 0), (-1, 0), 6),
                            ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                            ("GRID", (0, 0), (-1, -1), 0.5, self.colors["border"]),
                            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 1), (-1, -1), 8),
                            ("TOPPADDING", (0, 1), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                            ("ALIGN", (0, 1), (0, -1), "CENTER"),
                            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                        ]
                    )
                )
                story.append(cred_table)
        else:
            story.append(
                Paragraph("No depositor or creditor data available", styles["Normal"])
            )

        return story

    def _build_recurring_payments_anomalies(self, data: Dict[str, Any], styles) -> List:
        """Build the recurring payments and anomalies section"""
        story = []
        story.append(self._create_section_icon("🔄"))
        story.append(
            Paragraph("Recurring Payments & Anomalies", styles["SectionTitle"])
        )
        story.append(Spacer(1, 0.1 * inch))

        recurring = data.get("recurring_payments", [])
        anomalies = data.get("anomalies", [])

        # Recurring Payments
        if recurring:
            story.append(
                Paragraph("<b>Recurring Payments</b>", styles["SectionSubtitle"])
            )
            rec_data = [
                ["Description", "Avg (KES)", "Total (KES)", "Occurrences", "Frequency"]
            ]
            for r in recurring[:8]:
                rec_data.append(
                    [
                        (
                            r.get("description", "N/A")[:25] + "..."
                            if len(r.get("description", "")) > 25
                            else r.get("description", "N/A")
                        ),
                        f"{r.get('average_amount', 0):,.0f}",
                        f"{r.get('total', 0):,.0f}",
                        str(r.get("occurrences", 0)),
                        r.get("frequency", "N/A"),
                    ]
                )

            rec_table = Table(
                rec_data,
                colWidths=[2.2 * inch, 1 * inch, 1.2 * inch, 0.8 * inch, 1 * inch],
            )
            rec_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.colors["purple"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                        ("TOPPADDING", (0, 0), (-1, 0), 6),
                        ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                        ("GRID", (0, 0), (-1, -1), 0.5, self.colors["border"]),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                        ("TOPPADDING", (0, 1), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                        ("ALIGN", (1, 1), (4, -1), "CENTER"),
                    ]
                )
            )
            story.append(rec_table)
            story.append(Spacer(1, 0.1 * inch))

        # Anomalies
        if anomalies:
            story.append(
                Paragraph(
                    "<b>Unusually Large Transactions</b>", styles["SectionSubtitle"]
                )
            )
            anom_data = [["Date", "Description", "Amount (KES)", "Reason"]]
            for a in anomalies[:6]:
                desc = (
                    a.get("description", "N/A")[:30] + "..."
                    if len(a.get("description", "")) > 30
                    else a.get("description", "N/A")
                )
                anom_data.append(
                    [
                        a.get("date", "N/A"),
                        desc,
                        f"{a.get('amount', 0):,.0f}",
                        a.get("reason", "N/A"),
                    ]
                )

            anom_table = Table(
                anom_data, colWidths=[1.2 * inch, 2 * inch, 1.2 * inch, 1.5 * inch]
            )
            anom_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), self.colors["warning"]),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                        ("TOPPADDING", (0, 0), (-1, 0), 6),
                        ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                        ("GRID", (0, 0), (-1, -1), 0.5, self.colors["border"]),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                        ("TOPPADDING", (0, 1), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                    ]
                )
            )
            story.append(anom_table)

        if not recurring and not anomalies:
            story.append(
                Paragraph(
                    "No recurring payments or anomalies detected", styles["Normal"]
                )
            )

        return story

    def _build_insights_section(self, data: Dict[str, Any], styles) -> List:
        """Build the insights section"""
        story = []

        insights = data.get("insights", [])
        if insights:
            story.append(self._create_section_icon("💡"))
            story.append(Paragraph("Key Insights", styles["SectionTitle"]))
            story.append(Spacer(1, 0.1 * inch))
            for i, insight in enumerate(insights[:8], 1):
                story.append(
                    Paragraph(f"<b>{i}.</b> {insight}", styles["InsightStyle"])
                )

        warnings = data.get("warnings", [])
        if warnings:
            story.append(Spacer(1, 0.3 * inch))
            story.append(self._create_section_icon("⚠️"))
            story.append(Paragraph("Warnings", styles["SectionTitle"]))
            story.append(Spacer(1, 0.1 * inch))
            for warning in warnings[:5]:
                story.append(Paragraph(f"⚠ {warning}", styles["WarningStyle"]))

        recommendations = data.get("recommendations", [])
        if recommendations:
            story.append(Spacer(1, 0.3 * inch))
            story.append(self._create_section_icon("🎯"))
            story.append(Paragraph("Recommendations", styles["SectionTitle"]))
            story.append(Spacer(1, 0.1 * inch))
            for rec in recommendations[:6]:
                story.append(Paragraph(f"✦ {rec}", styles["RecStyle"]))

        if not insights and not warnings and not recommendations:
            story.append(
                Paragraph("No insights or recommendations available", styles["Normal"])
            )

        return story

    def _build_transaction_summary(self, data: Dict[str, Any], styles) -> List:
        """Build the transaction summary section"""
        story = []
        story.append(self._create_section_icon("📋"))
        story.append(Paragraph("Transaction Summary", styles["SectionTitle"]))
        story.append(Spacer(1, 0.1 * inch))

        tx_data = [
            ["📊 Total Transactions", f"{data.get('total_transactions', 0)}"],
            ["💰 Income Transactions", f"{data.get('income_count', 0)}"],
            ["💳 Expense Transactions", f"{data.get('expense_count', 0)}"],
            [
                "🏆 Highest Transaction",
                f"KES {data.get('highest_transaction', 0):,.0f}",
            ],
            [
                "📅 Highest Transaction Date",
                data.get("highest_transaction_date", "N/A"),
            ],
            ["📂 Top Category", data.get("top_category", "N/A").title()],
            ["💼 Top Income Source", data.get("top_income_source", "N/A").title()],
            ["📈 Income Concentration", f"{data.get('income_concentration', 0):.1f}%"],
            [
                "💳 Fuliza Usage",
                f"{data.get('fuliza_count', 0)} tx (KES {data.get('fuliza_total', 0):,.0f})",
            ],
            ["🎰 Betting", f"{data.get('betting_pct', 0):.1f}% of expenses"],
            ["🔄 P2P Transfers", f"{data.get('p2p_count', 0)} transactions"],
            ["💰 Total Fees", f"KES {data.get('total_fees', 0):,.0f}"],
            ["🏦 Salary Day", data.get("salary_day", "N/A")],
        ]

        tx_table = Table(tx_data, colWidths=[2.5 * inch, 2.5 * inch])
        tx_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self.colors["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), self.colors["light_bg"]),
                    ("GRID", (0, 0), (-1, -1), 1, self.colors["border"]),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    ("LEFTPADDING", (0, 1), (0, -1), 10),
                    ("TEXTCOLOR", (1, 1), (1, -1), self.colors["primary"]),
                    ("FONTSIZE", (1, 1), (1, -1), 10),
                ]
            )
        )
        story.append(tx_table)

        return story

    # ========== CHART GENERATION ==========

    def _create_monthly_chart(self, monthly_data: List[Dict]) -> Optional[Image]:
        """Create a monthly income vs expenses chart"""
        try:
            fig, ax = plt.subplots(figsize=(10, 5))
            fig.patch.set_facecolor("#f8fafc")
            ax.set_facecolor("#f8fafc")

            months = [d.get("month", "")[:7] for d in monthly_data]
            incomes = [d.get("income", 0) for d in monthly_data]
            expenses = [d.get("expenses", 0) for d in monthly_data]

            x = range(len(months))
            width = 0.35

            bars1 = ax.bar(
                x, incomes, width, label="Income", color="#22c55e", alpha=0.8
            )
            bars2 = ax.bar(
                [i + width for i in x],
                expenses,
                width,
                label="Expenses",
                color="#ef4444",
                alpha=0.8,
            )

            ax.set_xlabel("Month", fontsize=11, fontweight="bold")
            ax.set_ylabel("Amount (KES)", fontsize=11, fontweight="bold")
            ax.set_title(
                "Monthly Income vs Expenses", fontsize=14, fontweight="bold", pad=15
            )
            ax.set_xticks([i + width / 2 for i in x])
            ax.set_xticklabels(months, rotation=45, ha="right")
            ax.legend(loc="upper left", fontsize=10)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"KES {x:,.0f}"))
            ax.grid(True, alpha=0.3, linestyle="--")
            ax.set_axisbelow(True)

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(
                buf, format="png", dpi=150, bbox_inches="tight", facecolor="#f8fafc"
            )
            buf.seek(0)

            img = Image(buf, width=6 * inch, height=3.5 * inch)
            plt.close()
            return img
        except Exception as e:
            logger.warning(f"Monthly chart generation failed: {e}")
            return None

    def _create_category_pie_chart(self, category_data: List[Dict]) -> Optional[Image]:
        """Create a category pie chart"""
        try:
            if not category_data:
                return None

            fig, ax = plt.subplots(figsize=(8, 6))
            fig.patch.set_facecolor("#f8fafc")
            ax.set_facecolor("#f8fafc")

            top_categories = category_data[:7]
            if len(category_data) > 7:
                other_total = sum(c["value"] for c in category_data[7:])
                top_categories.append({"name": "Other", "value": other_total})

            labels = [c.get("name", "N/A")[:20].title() for c in top_categories]
            values = [c.get("value", 0) for c in top_categories]

            colors = [
                "#0088FE",
                "#00C49F",
                "#FFBB28",
                "#FF8042",
                "#8884d8",
                "#82ca9d",
                "#ffc658",
            ]

            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                colors=colors[: len(labels)],
                autopct=lambda pct: f"{pct:.1f}%" if pct > 2 else "",
                startangle=90,
                explode=[0.02] * len(labels),
                shadow=True,
                textprops={"fontsize": 10},
            )

            for autotext in autotexts:
                autotext.set_color("white")
                autotext.set_fontweight("bold")
                autotext.set_fontsize(10)

            ax.set_title(
                "Spending Category Breakdown", fontsize=14, fontweight="bold", pad=15
            )
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(
                buf, format="png", dpi=150, bbox_inches="tight", facecolor="#f8fafc"
            )
            buf.seek(0)

            img = Image(buf, width=5.5 * inch, height=4 * inch)
            plt.close()
            return img
        except Exception as e:
            logger.warning(f"Pie chart generation failed: {e}")
            return None

    def _create_day_of_week_chart(self, day_data: List[Dict]) -> Optional[Image]:
        """Create a day of week spending chart"""
        try:
            if not day_data:
                return None

            fig, ax = plt.subplots(figsize=(10, 5))
            fig.patch.set_facecolor("#f8fafc")
            ax.set_facecolor("#f8fafc")

            days = [d.get("day", "")[:3] for d in day_data]
            spends = [d.get("spend", 0) for d in day_data]

            bars = ax.bar(days, spends, color="#8b5cf6", alpha=0.8)

            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"KES {height:,.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

            ax.set_xlabel("Day of Week", fontsize=11, fontweight="bold")
            ax.set_ylabel("Amount (KES)", fontsize=11, fontweight="bold")
            ax.set_title(
                "Spending by Day of Week", fontsize=14, fontweight="bold", pad=15
            )
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"KES {x:,.0f}"))
            ax.grid(True, alpha=0.3, linestyle="--", axis="y")
            ax.set_axisbelow(True)

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(
                buf, format="png", dpi=150, bbox_inches="tight", facecolor="#f8fafc"
            )
            buf.seek(0)

            img = Image(buf, width=6 * inch, height=3.5 * inch)
            plt.close()
            return img
        except Exception as e:
            logger.warning(f"Day of week chart generation failed: {e}")
            return None

    def generate_csv_export(self, data: Dict[str, Any]) -> str:
        """Generate a CSV export of the financial data"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.report_dir}/financial_data_{timestamp}.csv"

            with open(filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                writer.writerow(["Pesa Analyser - Financial Data Export"])
                writer.writerow(
                    [
                        f"Generated: {data.get('generated_at', datetime.now().isoformat())}"
                    ]
                )
                writer.writerow([])

                writer.writerow(["SUMMARY METRICS"])
                writer.writerow(["Metric", "Value"])
                writer.writerow(["Total Income", data.get("total_income", 0)])
                writer.writerow(["Total Expenses", data.get("total_expenses", 0)])
                writer.writerow(["Net Cash Flow", data.get("net_cash_flow", 0)])
                writer.writerow(["Savings Rate (%)", data.get("savings_rate", 0)])
                writer.writerow(["Health Score", data.get("health_score", 0)])
                writer.writerow(
                    ["Total Transactions", data.get("total_transactions", 0)]
                )
                writer.writerow(["Average Balance", data.get("average_balance", 0)])
                writer.writerow(["Total Fees", data.get("total_fees", 0)])
                writer.writerow(["Burn Rate (Daily)", data.get("burn_rate_daily", 0)])
                writer.writerow([])

                writer.writerow(["MONTHLY BREAKDOWN"])
                writer.writerow(
                    ["Month", "Income", "Expenses", "Balance", "Transactions"]
                )
                for month in data.get("monthly_data", []):
                    writer.writerow(
                        [
                            month.get("month", ""),
                            month.get("income", 0),
                            month.get("expenses", 0),
                            month.get("balance", 0),
                            month.get("transaction_count", 0),
                        ]
                    )
                writer.writerow([])

                writer.writerow(["CATEGORY BREAKDOWN"])
                writer.writerow(["Category", "Amount"])
                for category in data.get("category_data", []):
                    writer.writerow(
                        [category.get("name", ""), category.get("value", 0)]
                    )
                writer.writerow([])

                writer.writerow(["TOP DEPOSITORS"])
                writer.writerow(["Who", "Amount"])
                for dep in data.get("top_depositors", []):
                    writer.writerow([dep.get("who", ""), dep.get("amount", 0)])
                writer.writerow([])

                writer.writerow(["TOP CREDITORS"])
                writer.writerow(["Who", "Amount"])
                for cred in data.get("top_creditors", []):
                    writer.writerow([cred.get("who", ""), cred.get("amount", 0)])
                writer.writerow([])

                writer.writerow(["RECURRING PAYMENTS"])
                writer.writerow(
                    [
                        "Description",
                        "Average Amount",
                        "Total",
                        "Occurrences",
                        "Frequency",
                    ]
                )
                for rec in data.get("recurring_payments", []):
                    writer.writerow(
                        [
                            rec.get("description", ""),
                            rec.get("average_amount", 0),
                            rec.get("total", 0),
                            rec.get("occurrences", 0),
                            rec.get("frequency", ""),
                        ]
                    )
                writer.writerow([])

                writer.writerow(["ANOMALIES"])
                writer.writerow(["Date", "Description", "Amount", "Reason"])
                for anom in data.get("anomalies", []):
                    writer.writerow(
                        [
                            anom.get("date", ""),
                            anom.get("description", ""),
                            anom.get("amount", 0),
                            anom.get("reason", ""),
                        ]
                    )
                writer.writerow([])

                writer.writerow(["INSIGHTS"])
                for insight in data.get("insights", []):
                    writer.writerow([insight])
                writer.writerow([])

                writer.writerow(["RECOMMENDATIONS"])
                for rec in data.get("recommendations", []):
                    writer.writerow([rec])
                writer.writerow([])

                writer.writerow(["WARNINGS"])
                for warning in data.get("warnings", []):
                    writer.writerow([warning])

            logger.info(f"✅ CSV export generated: {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ CSV generation error: {str(e)}")
            raise
