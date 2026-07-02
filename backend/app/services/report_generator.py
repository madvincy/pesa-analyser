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
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, 
    Image, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from matplotlib.ticker import FuncFormatter
import io

logger = logging.getLogger(__name__)

# Register fonts for better PDF rendering
try:
    pdfmetrics.registerFont(TTFont('Helvetica', 'Helvetica'))
    pdfmetrics.registerFont(TTFont('Helvetica-Bold', 'Helvetica-Bold'))
    pdfmetrics.registerFont(TTFont('Helvetica-Oblique', 'Helvetica-Oblique'))
except:
    pass


class ReportGenerator:
    """Professional PDF Report Generator with Charts and Visualizations"""
    
    def __init__(self):
        self.report_dir = "./reports"
        os.makedirs(self.report_dir, exist_ok=True)
        
        # Color palette matching the dashboard
        self.colors = {
            'primary': colors.HexColor('#1a1a2e'),
            'secondary': colors.HexColor('#16213e'),
            'accent': colors.HexColor('#0f3460'),
            'success': colors.HexColor('#22c55e'),
            'warning': colors.HexColor('#f59e0b'),
            'danger': colors.HexColor('#ef4444'),
            'info': colors.HexColor('#3b82f6'),
            'purple': colors.HexColor('#8b5cf6'),
            'light_bg': colors.HexColor('#f8fafc'),
            'border': colors.HexColor('#e2e8f0'),
            'text_muted': colors.HexColor('#64748b'),
            'text_dark': colors.HexColor('#0f172a'),
        }
        
        # Chart color palette
        self.chart_colors = [
            '#0088FE', '#00C49F', '#FFBB28', '#FF8042', 
            '#8884d8', '#82ca9d', '#ffc658', '#ff6b6b'
        ]
    
    def generate_pdf_report(self, data: Dict[str, Any]) -> str:
        """
        Generate comprehensive PDF report with professional charts and styling
        
        Args:
            data: Dictionary containing analysis results from AIAnalyzer
        
        Returns:
            Path to the generated PDF file
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.report_dir}/financial_report_{timestamp}.pdf"
            
            # Create document with professional margins
            doc = SimpleDocTemplate(
                filename, 
                pagesize=A4,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch,
            )
            
            styles = self._create_styles()
            story = []
            
            # ========== COVER PAGE ==========
            story.extend(self._build_cover_page(data, styles))
            story.append(PageBreak())
            
            # ========== EXECUTIVE SUMMARY ==========
            story.extend(self._build_executive_summary(data, styles))
            story.append(PageBreak())
            
            # ========== HEALTH SCORE ==========
            story.extend(self._build_health_score_section(data, styles))
            
            # ========== KEY METRICS ==========
            story.extend(self._build_key_metrics_section(data, styles))
            story.append(PageBreak())
            
            # ========== CHARTS SECTION ==========
            story.extend(self._build_charts_section(data, styles))
            
            # ========== CATEGORY BREAKDOWN ==========
            story.extend(self._build_category_breakdown(data, styles))
            
            # ========== INSIGHTS & RECOMMENDATIONS ==========
            story.extend(self._build_insights_section(data, styles))
            
            # ========== TRANSACTION SUMMARY ==========
            story.extend(self._build_transaction_summary(data, styles))
            
            # ========== FOOTER ==========
            story.append(Spacer(1, 0.5*inch))
            story.extend(self._build_footer(styles))
            
            # Build the document
            doc.build(story)
            logger.info(f"✅ PDF report generated: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ PDF generation error: {str(e)}", exc_info=True)
            raise
    
    def _create_styles(self):
        """Create professional paragraph styles"""
        styles = getSampleStyleSheet()
        
        # Custom styles - add each style individually
        cover_title = ParagraphStyle(
            'CoverTitle',
            parent=styles['Title'],
            fontSize=32,
            textColor=self.colors['primary'],
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Helvetica-Bold',
        )
        styles.add(cover_title)
        
        cover_subtitle = ParagraphStyle(
            'CoverSubtitle',
            parent=styles['Normal'],
            fontSize=16,
            textColor=self.colors['text_muted'],
            alignment=TA_CENTER,
            spaceAfter=30,
            fontName='Helvetica',
        )
        styles.add(cover_subtitle)
        
        section_title = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=self.colors['primary'],
            spaceAfter=15,
            spaceBefore=20,
            fontName='Helvetica-Bold',
        )
        styles.add(section_title)
        
        section_subtitle = ParagraphStyle(
            'SectionSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=self.colors['text_muted'],
            spaceAfter=10,
            fontName='Helvetica',
        )
        styles.add(section_subtitle)
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=self.colors['text_muted'],
            alignment=TA_CENTER,
            fontName='Helvetica',
        )
        styles.add(info_style)
        
        score_style = ParagraphStyle(
            'ScoreStyle',
            parent=styles['Normal'],
            fontSize=28,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
        )
        styles.add(score_style)
        
        summary_style = ParagraphStyle(
            'SummaryStyle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=self.colors['text_dark'],
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            spaceAfter=10,
        )
        styles.add(summary_style)
        
        insight_style = ParagraphStyle(
            'InsightStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=self.colors['text_dark'],
            alignment=TA_LEFT,
            fontName='Helvetica',
            leftIndent=12,
            spaceAfter=4,
        )
        styles.add(insight_style)
        
        warning_style = ParagraphStyle(
            'WarningStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=self.colors['danger'],
            alignment=TA_LEFT,
            fontName='Helvetica',
            leftIndent=12,
            spaceAfter=4,
        )
        styles.add(warning_style)
        
        rec_style = ParagraphStyle(
            'RecStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=self.colors['text_dark'],
            alignment=TA_LEFT,
            fontName='Helvetica',
            leftIndent=12,
            spaceAfter=4,
        )
        styles.add(rec_style)
        
        footer_style = ParagraphStyle(
            'FooterStyle',
            parent=styles['Normal'],
            fontSize=8,
            textColor=self.colors['text_muted'],
            alignment=TA_CENTER,
        )
        styles.add(footer_style)
        
        return styles
    
    # ========== SECTION BUILDERS ==========
    
    def _build_cover_page(self, data: Dict[str, Any], styles) -> List:
        """Build the cover page"""
        story = []
        
        # Logo/Header area
        story.append(Spacer(1, 2*inch))
        
        # Title
        story.append(Paragraph("Pesa Analyser", styles['CoverTitle']))
        story.append(Paragraph("Financial Analysis Report", styles['CoverSubtitle']))
        story.append(Spacer(1, 0.5*inch))
        
        # Separator line
        story.append(Spacer(1, 0.2*inch))
        story.append(self._create_separator_line())
        story.append(Spacer(1, 0.5*inch))
        
        # File info
        story.append(Paragraph(f"<b>File:</b> {data.get('file_name', 'N/A')}", styles['InfoStyle']))
        story.append(Paragraph(f"<b>Generated:</b> {data.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}", styles['InfoStyle']))
        story.append(Paragraph(f"<b>Analysis ID:</b> {data.get('id', 'N/A')}", styles['InfoStyle']))
        
        # Health score on cover
        health_score = data.get('health_score', 0)
        story.append(Spacer(1, 0.5*inch))
        
        score_color = (
            self.colors['success'] if health_score > 70 
            else self.colors['warning'] if health_score > 40 
            else self.colors['danger']
        )
        
        # Create a new style with the color
        cover_score_style = ParagraphStyle(
            'CoverScoreStyle',
            parent=styles['ScoreStyle'],
            textColor=score_color,
        )
        story.append(Paragraph(f"Financial Health Score: {health_score}/100", cover_score_style))
        
        # Health bar
        story.append(Spacer(1, 0.2*inch))
        story.append(self._create_progress_bar(health_score, 3*inch))
        
        story.append(Spacer(1, 1.5*inch))
        
        # Footer
        story.append(Paragraph("Confidential - For Internal Use Only", styles['FooterStyle']))
        story.append(Paragraph("© 2026 Pesa Analyser - All Rights Reserved", styles['FooterStyle']))
        
        return story
    
    def _build_executive_summary(self, data: Dict[str, Any], styles) -> List:
        """Build the executive summary section"""
        story = []
        
        story.append(Paragraph("Executive Summary", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        # Summary text
        total_income = data.get('total_income', 0)
        total_expenses = data.get('total_expenses', 0)
        net_cash_flow = data.get('net_cash_flow', 0)
        health_score = data.get('health_score', 0)
        total_tx = data.get('total_transactions', 0)
        
        summary_text = f"""
        This financial analysis report provides a comprehensive overview of your financial activities.
        Based on the analysis of {total_tx} transactions, your total income was KES {total_income:,.0f} 
        and total expenses were KES {total_expenses:,.0f}, resulting in a net cash flow of KES {net_cash_flow:,.0f}.
        """
        
        story.append(Paragraph(summary_text, styles['SummaryStyle']))
        story.append(Spacer(1, 0.2*inch))
        
        # Quick stats in a table
        stats_data = [
            ['Metric', 'Value', 'Status'],
            ['Total Income', f'KES {total_income:,.0f}', '▲' if total_income > total_expenses else '▼'],
            ['Total Expenses', f'KES {total_expenses:,.0f}', '▼'],
            ['Net Cash Flow', f'KES {net_cash_flow:,.0f}', '✓' if net_cash_flow > 0 else '✗'],
            ['Savings Rate', f"{data.get('savings_rate', 0):.1f}%", '✓' if data.get('savings_rate', 0) > 10 else '⚠'],
            ['Health Score', f"{health_score}/100", '✓' if health_score > 70 else '⚠'],
        ]
        
        stats_table = Table(stats_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), self.colors['light_bg']),
            ('GRID', (0, 0), (-1, -1), 1, self.colors['border']),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        story.append(stats_table)
        
        return story
    
    def _build_health_score_section(self, data: Dict[str, Any], styles) -> List:
        """Build the health score section with breakdown"""
        story = []
        
        story.append(Paragraph("Financial Health Score", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        health_score = data.get('health_score', 0)
        breakdown = data.get('health_breakdown', {})
        
        # Create a table with score and breakdown
        health_data = [
            ['Component', 'Score', 'Contribution'],
        ]
        
        # Add breakdown items
        components = breakdown.items() if breakdown else [
            ('Fuliza Dependency', 0),
            ('Income Quality', 0),
            ('Savings Rate', 0),
            ('Betting Behavior', 0),
            ('Transaction Volume', 0),
        ]
        
        for comp, value in components:
            if isinstance(value, int):
                display_value = f"{value:+d}"
                health_data.append([
                    comp.replace('_', ' ').title(),
                    display_value,
                    '✓' if value > 0 else '⚠' if value > -10 else '✗'
                ])
        
        # Add total score
        health_data.append(['Total Score', f"{health_score}/100", ''])
        
        health_table = Table(health_data, colWidths=[2.5*inch, 1.5*inch, 1*inch])
        health_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -2), self.colors['light_bg']),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, self.colors['border']),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        story.append(health_table)
        story.append(Spacer(1, 0.2*inch))
        
        # Health score bar
        story.append(self._create_progress_bar(health_score, 5*inch, show_percentage=True))
        
        return story
    
    def _build_key_metrics_section(self, data: Dict[str, Any], styles) -> List:
        """Build the key metrics section"""
        story = []
        
        story.append(Paragraph("Key Financial Metrics", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        # Metrics in a grid format using tables
        metrics = [
            ['Metric', 'Value'],
            ['Total Income', f"KES {data.get('total_income', 0):,.0f}"],
            ['Total Expenses', f"KES {data.get('total_expenses', 0):,.0f}"],
            ['Net Cash Flow', f"KES {data.get('net_cash_flow', 0):,.0f}"],
            ['Average Balance', f"KES {data.get('average_balance', 0):,.0f}"],
            ['Total Fees', f"KES {data.get('total_fees', 0):,.0f}"],
            ['Total Transactions', f"{data.get('total_transactions', 0)}"],
            ['Savings Rate', f"{data.get('savings_rate', 0):.1f}%"],
            ['Burn Rate (Daily)', f"KES {data.get('burn_rate_daily', 0):,.0f}"],
        ]
        
        # Create a nice metrics table
        metrics_table = Table(metrics, colWidths=[2.5*inch, 2.5*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), self.colors['light_bg']),
            ('GRID', (0, 0), (-1, -1), 1, self.colors['border']),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        story.append(metrics_table)
        
        # Additional metrics in a row
        story.append(Spacer(1, 0.2*inch))
        
        additional_metrics = [
            ['Fuliza Usage', f"{data.get('fuliza_count', 0)} transactions (KES {data.get('fuliza_total', 0):,.0f})"],
            ['Betting', f"{data.get('betting_pct', 0):.1f}% of expenses"],
            ['P2P Transfers', f"{data.get('p2p_count', 0)} transactions"],
            ['Top Category', f"{data.get('top_category', 'N/A')}"],
        ]
        
        add_metrics_table = Table(additional_metrics, colWidths=[2.5*inch, 2.5*inch])
        add_metrics_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(add_metrics_table)
        
        return story
    
    def _build_charts_section(self, data: Dict[str, Any], styles) -> List:
        """Build the charts section with matplotlib charts embedded as images"""
        story = []
        
        story.append(Paragraph("Visual Analysis", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        # Generate matplotlib charts
        try:
            # Monthly Income vs Expenses Chart
            monthly_data = data.get('monthly_data', [])
            if monthly_data:
                chart_img = self._create_monthly_chart(monthly_data)
                if chart_img:
                    story.append(Paragraph("<b>Monthly Income vs Expenses</b>", styles['SectionSubtitle']))
                    story.append(chart_img)
                    story.append(Spacer(1, 0.2*inch))
            
            # Category Pie Chart
            category_data = data.get('category_data', [])
            if category_data:
                pie_img = self._create_category_pie_chart(category_data)
                if pie_img:
                    story.append(Paragraph("<b>Category Breakdown</b>", styles['SectionSubtitle']))
                    story.append(pie_img)
                    story.append(Spacer(1, 0.2*inch))
            
            # Trend Chart
            trend_data = data.get('trend_data', [])
            if trend_data:
                trend_img = self._create_trend_chart(trend_data)
                if trend_img:
                    story.append(Paragraph("<b>Transaction Trends</b>", styles['SectionSubtitle']))
                    story.append(trend_img)
                    story.append(Spacer(1, 0.2*inch))
            
            # Radar Chart
            radar_img = self._create_radar_chart(data)
            if radar_img:
                story.append(Paragraph("<b>Financial Health Radar</b>", styles['SectionSubtitle']))
                story.append(radar_img)
                story.append(Spacer(1, 0.2*inch))
                
        except Exception as e:
            logger.warning(f"Chart generation error: {e}")
            story.append(Paragraph("Charts could not be generated", styles['Normal']))
        
        return story
    
    def _build_category_breakdown(self, data: Dict[str, Any], styles) -> List:
        """Build category breakdown section"""
        story = []
        
        story.append(Paragraph("Category Breakdown", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        category_data = data.get('category_data', [])
        total_expenses = data.get('total_expenses', 0)
        
        if category_data:
            # Top categories table
            cat_data = [['Category', 'Amount (KES)', '% of Total']]
            
            for cat in category_data[:8]:
                amount = cat.get('value', 0)
                pct = (amount / total_expenses * 100) if total_expenses > 0 else 0
                cat_data.append([
                    cat.get('name', 'N/A'),
                    f"{amount:,.0f}",
                    f"{pct:.1f}%",
                ])
            
            cat_table = Table(cat_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            cat_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.colors['primary']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), self.colors['light_bg']),
                ('GRID', (0, 0), (-1, -1), 1, self.colors['border']),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ]))
            story.append(cat_table)
        else:
            story.append(Paragraph("No category data available", styles['Normal']))
        
        return story
    
    def _build_insights_section(self, data: Dict[str, Any], styles) -> List:
        """Build insights and recommendations section"""
        story = []
        
        # Insights
        story.append(Paragraph("Key Insights", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        insights = data.get('insights', [])
        if insights:
            for insight in insights[:8]:
                story.append(Paragraph(f"• {insight}", styles['InsightStyle']))
        else:
            story.append(Paragraph("No insights available", styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Warnings
        warnings = data.get('warnings', [])
        if warnings:
            story.append(Paragraph("⚠️ Warnings", styles['SectionTitle']))
            story.append(Spacer(1, 0.1*inch))
            
            for warning in warnings[:5]:
                story.append(Paragraph(f"• {warning}", styles['WarningStyle']))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Recommendations
        story.append(Paragraph("💡 Recommendations", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        recommendations = data.get('recommendations', [])
        if recommendations:
            for rec in recommendations[:6]:
                story.append(Paragraph(f"✦ {rec}", styles['RecStyle']))
        else:
            story.append(Paragraph("No recommendations available", styles['Normal']))
        
        return story
    
    def _build_transaction_summary(self, data: Dict[str, Any], styles) -> List:
        """Build transaction summary section"""
        story = []
        
        story.append(Paragraph("Transaction Summary", styles['SectionTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        # Transaction stats
        tx_data = [
            ['Statistic', 'Value'],
            ['Total Transactions', f"{data.get('total_transactions', 0)}"],
            ['Income Transactions', f"{data.get('income_count', 0)}"],
            ['Expense Transactions', f"{data.get('expense_count', 0)}"],
            ['Highest Transaction', f"KES {data.get('highest_transaction', 0):,.0f}"],
            ['Top Category', data.get('top_category', 'N/A')],
            ['Top Income Source', data.get('top_income_source', 'N/A')],
            ['Income Concentration', f"{data.get('income_concentration', 0):.1f}%"],
        ]
        
        tx_table = Table(tx_data, colWidths=[2.5*inch, 2.5*inch])
        tx_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.colors['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), self.colors['light_bg']),
            ('GRID', (0, 0), (-1, -1), 1, self.colors['border']),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        story.append(tx_table)
        
        return story
    
    def _build_footer(self, styles) -> List:
        """Build the report footer"""
        story = []
        
        story.append(self._create_separator_line())
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("Generated by Pesa Analyser - Financial Intelligence Platform", styles['FooterStyle']))
        story.append(Paragraph(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['FooterStyle']))
        
        return story
    
    # ========== UTILITY FUNCTIONS ==========
    
    def _create_separator_line(self) -> Paragraph:
        """Create a decorative separator line"""
        style = ParagraphStyle(
            'Separator',
            parent=getSampleStyleSheet()['Normal'],
            fontSize=6,
            textColor=self.colors['border'],
            alignment=TA_CENTER,
        )
        return Paragraph("━" * 80, style)
    
    def _create_progress_bar(self, value: float, width: float, show_percentage: bool = False) -> Table:
        """Create a visual progress bar"""
        percentage = min(max(value, 0), 100)
        bar_width = (percentage / 100) * width
        
        # Determine color
        if percentage > 70:
            color = self.colors['success']
        elif percentage > 40:
            color = self.colors['warning']
        else:
            color = self.colors['danger']
        
        # Create the progress bar as a table with percentage text
        if show_percentage:
            # Two row table: bar then percentage text
            bar_data = [
                [''],
                [f"{percentage:.0f}%"],
            ]
            bar_table = Table(bar_data, colWidths=[width])
            bar_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), color),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('ALIGN', (0, 1), (0, 1), 'CENTER'),
                ('FONTSIZE', (0, 1), (0, 1), 12),
                ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
                ('TOPPADDING', (0, 1), (0, 1), 2),
            ]))
            return bar_table
        else:
            # Simple bar
            bar_data = [
                ['', ''],
            ]
            bar_table = Table(bar_data, colWidths=[bar_width, width - bar_width])
            bar_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), color),
                ('BACKGROUND', (1, 0), (1, 0), self.colors['border']),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            return bar_table
    
    # ========== CHART GENERATION ==========
    
    def _create_monthly_chart(self, monthly_data: List[Dict]) -> Optional[Image]:
        """Create a matplotlib monthly income vs expenses chart"""
        try:
            fig, ax = plt.subplots(figsize=(8, 4))
            
            months = [d.get('month', '')[:7] for d in monthly_data]
            incomes = [d.get('income', 0) for d in monthly_data]
            expenses = [d.get('expenses', 0) for d in monthly_data]
            
            x = range(len(months))
            width = 0.35
            
            ax.bar(x, incomes, width, label='Income', color='#22c55e')
            ax.bar([i + width for i in x], expenses, width, label='Expenses', color='#ef4444')
            
            ax.set_xlabel('Month')
            ax.set_ylabel('Amount (KES)')
            ax.set_title('Monthly Income vs Expenses')
            ax.set_xticks([i + width/2 for i in x])
            ax.set_xticklabels(months, rotation=45, ha='right')
            ax.legend()
            
            # Format y-axis with KES
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'KES {x:,.0f}'))
            
            plt.tight_layout()
            
            # Convert to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            # Create ReportLab Image
            img = Image(buf, width=6*inch, height=3.2*inch)
            plt.close()
            return img
            
        except Exception as e:
            logger.warning(f"Monthly chart generation failed: {e}")
            return None
    
    def _create_category_pie_chart(self, category_data: List[Dict]) -> Optional[Image]:
        """Create a matplotlib pie chart for categories"""
        try:
            if not category_data:
                return None
            
            # Take top 7 categories, group rest as 'Other'
            top_categories = category_data[:7]
            if len(category_data) > 7:
                other_total = sum(c['value'] for c in category_data[7:])
                top_categories.append({'name': 'Other', 'value': other_total})
            
            fig, ax = plt.subplots(figsize=(8, 4))
            
            labels = [c.get('name', 'N/A')[:20] for c in top_categories]
            values = [c.get('value', 0) for c in top_categories]
            
            colors = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#ff6b6b']
            
            wedges, texts, autotexts = ax.pie(
                values, 
                labels=labels,
                colors=colors[:len(labels)],
                autopct=lambda pct: f'{pct:.1f}%' if pct > 2 else '',
                startangle=90
            )
            
            ax.set_title('Category Breakdown')
            
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            img = Image(buf, width=6*inch, height=3.2*inch)
            plt.close()
            return img
            
        except Exception as e:
            logger.warning(f"Pie chart generation failed: {e}")
            return None
    
    def _create_trend_chart(self, trend_data: List[Dict]) -> Optional[Image]:
        """Create a matplotlib trend chart"""
        try:
            if not trend_data:
                return None
            
            fig, ax = plt.subplots(figsize=(8, 4))
            
            dates = [d.get('date', '') for d in trend_data]
            amounts = [d.get('amount', 0) for d in trend_data]
            tx_counts = [d.get('transactions', 0) for d in trend_data]
            
            ax2 = ax.twinx()
            
            # Plot and get line objects
            line1, = ax.plot(dates, amounts, color='#3b82f6', marker='o', linewidth=2, label='Amount')
            line2, = ax2.plot(dates, tx_counts, color='#ef4444', marker='s', linewidth=2, label='Transactions')
            
            ax.set_xlabel('Date')
            ax.set_ylabel('Amount (KES)', color='#3b82f6')
            ax2.set_ylabel('Transactions', color='#ef4444')
            
            ax.tick_params(axis='y', labelcolor='#3b82f6')
            ax2.tick_params(axis='y', labelcolor='#ef4444')
            
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'KES {x:,.0f}'))
            
            # Create legend with explicit handles and labels
            ax.legend(handles=[line1, line2], labels=['Amount', 'Transactions'], loc='upper left')
            
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            img = Image(buf, width=6*inch, height=3.2*inch)
            plt.close()
            return img
            
        except Exception as e:
            logger.warning(f"Trend chart generation failed: {e}")
            return None
    
    def _create_radar_chart(self, data: Dict[str, Any]) -> Optional[Image]:
        """Create a matplotlib radar chart for financial health"""
        try:
            fig, ax = plt.subplots(figsize=(8, 4), subplot_kw=dict(polar=True))
            
            # Calculate metrics for radar
            total_income = data.get('total_income', 0)
            net_cash_flow = data.get('net_cash_flow', 0)
            total_expenses = data.get('total_expenses', 0)
            avg_balance = data.get('average_balance', 0)
            income_change = data.get('income_change', 0)
            
            categories = ['Income', 'Savings', 'Spending', 'Stability', 'Growth']
            values = [
                min(100, (total_income / 150000) * 100),
                min(100, max(0, (net_cash_flow / 50000) * 100)),
                min(100, max(0, 100 - (total_expenses / 100000) * 100)),
                min(100, (avg_balance / 50000) * 100),
                min(100, max(0, income_change + 50)),
            ]
            
            # Close the polygon
            values += values[:1]
            angles = [n / float(len(categories)) * 2 * 3.14159 for n in range(len(categories))]
            angles += angles[:1]
            
            ax.plot(angles, values, 'o-', linewidth=2, color='#3b82f6')
            ax.fill(angles, values, alpha=0.25, color='#3b82f6')
            
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories)
            ax.set_ylim(0, 100)
            ax.set_yticks([20, 40, 60, 80, 100])
            ax.set_yticklabels(['20', '40', '60', '80', '100'])
            ax.grid(True)
            
            plt.title('Financial Health Radar', size=14, pad=20)
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            
            img = Image(buf, width=6*inch, height=3.2*inch)
            plt.close()
            return img
            
        except Exception as e:
            logger.warning(f"Radar chart generation failed: {e}")
            return None
    
    # ========== CSV EXPORT ==========
    
    def generate_csv_export(self, data: Dict[str, Any]) -> str:
        """Generate CSV export of financial data"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.report_dir}/financial_data_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Header
                writer.writerow(['Pesa Analyser - Financial Data Export'])
                writer.writerow([f"Generated: {data.get('generated_at', datetime.now().isoformat())}"])
                writer.writerow([])
                
                # Summary metrics
                writer.writerow(['SUMMARY METRICS'])
                writer.writerow(['Metric', 'Value'])
                writer.writerow(['Total Income', data.get('total_income', 0)])
                writer.writerow(['Total Expenses', data.get('total_expenses', 0)])
                writer.writerow(['Net Cash Flow', data.get('net_cash_flow', 0)])
                writer.writerow(['Savings Rate (%)', data.get('savings_rate', 0)])
                writer.writerow(['Health Score', data.get('health_score', 0)])
                writer.writerow(['Total Transactions', data.get('total_transactions', 0)])
                writer.writerow(['Average Balance', data.get('average_balance', 0)])
                writer.writerow(['Total Fees', data.get('total_fees', 0)])
                writer.writerow([])
                
                # Monthly data
                writer.writerow(['MONTHLY BREAKDOWN'])
                writer.writerow(['Month', 'Income', 'Expenses', 'Balance', 'Transactions'])
                for month in data.get('monthly_data', []):
                    writer.writerow([
                        month.get('month', ''),
                        month.get('income', 0),
                        month.get('expenses', 0),
                        month.get('balance', 0),
                        month.get('transaction_count', 0)
                    ])
                writer.writerow([])
                
                # Category data
                writer.writerow(['CATEGORY BREAKDOWN'])
                writer.writerow(['Category', 'Amount'])
                for category in data.get('category_data', []):
                    writer.writerow([
                        category.get('name', ''),
                        category.get('value', 0)
                    ])
                writer.writerow([])
                
                # Insights
                writer.writerow(['INSIGHTS'])
                for insight in data.get('insights', []):
                    writer.writerow([insight])
                writer.writerow([])
                
                # Recommendations
                writer.writerow(['RECOMMENDATIONS'])
                for rec in data.get('recommendations', []):
                    writer.writerow([rec])
                writer.writerow([])
                
                # Warnings
                writer.writerow(['WARNINGS'])
                for warning in data.get('warnings', []):
                    writer.writerow([warning])
                
            logger.info(f"✅ CSV export generated: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"❌ CSV generation error: {str(e)}")
            raise