import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
import logging
from jinja2 import Template
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = os.getenv("SMTP_FROM", smtp_user)
    
    def send_email(self, to_email: str, subject: str, body: str, 
                   html_body: Optional[str] = None, attachments: Optional[List[str]] = None) -> bool:
        """Send email with optional attachments"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Attach plain text body
            part1 = MIMEText(body, 'plain')
            msg.attach(part1)
            
            # Attach HTML body if provided
            if html_body:
                part2 = MIMEText(html_body, 'html')
                msg.attach(part2)
            
            # Attach files if any
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename={os.path.basename(file_path)}'
                            )
                            msg.attach(part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Email send error: {str(e)}")
            return False
    
    def send_report_email(self, to_email: str, report_data: dict, report_path: Optional[str] = None) -> bool:
        """Send financial report via email"""
        try:
            template = Template("""
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; background: #f5f5f5; }
                    .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
                    .header { background: #1a1a2e; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }
                    .content { padding: 20px; }
                    .metric { display: inline-block; width: 45%; padding: 10px; margin: 5px; background: #f5f5f5; border-radius: 5px; }
                    .metric-value { font-size: 20px; font-weight: bold; color: #2d3436; }
                    .metric-label { color: #636e72; font-size: 14px; }
                    .insights { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }
                    .footer { text-align: center; padding: 20px; color: #636e72; font-size: 12px; }
                    .button { display: inline-block; padding: 10px 20px; background: #1a1a2e; color: white; 
                             text-decoration: none; border-radius: 5px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Pesa Analyser - Financial Report</h1>
                        <p>Generated on {{ generated_date }}</p>
                    </div>
                    
                    <div class="content">
                        <h2>Financial Summary</h2>
                        <div>
                            <div class="metric">
                                <div class="metric-label">Total Income</div>
                                <div class="metric-value">KES {{ total_income|format_currency }}</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Total Expenses</div>
                                <div class="metric-value">KES {{ total_expenses|format_currency }}</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Net Cash Flow</div>
                                <div class="metric-value" style="color: {{ 'green' if net_cash_flow > 0 else 'red' }}">
                                    KES {{ net_cash_flow|format_currency }}
                                </div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Average Balance</div>
                                <div class="metric-value">KES {{ average_balance|format_currency }}</div>
                            </div>
                        </div>
                        
                        {% if insights %}
                        <div class="insights">
                            <h3>Key Insights</h3>
                            <ul>
                                {% for insight in insights %}
                                <li>{{ insight }}</li>
                                {% endfor %}
                            </ul>
                        </div>
                        {% endif %}
                        
                        {% if recommendations %}
                        <div class="insights">
                            <h3>Recommendations</h3>
                            <ul>
                                {% for rec in recommendations %}
                                <li>{{ rec }}</li>
                                {% endfor %}
                            </ul>
                        </div>
                        {% endif %}
                        
                        <div style="text-align: center; margin-top: 20px;">
                            <a href="{{ app_url }}" class="button">View Full Report</a>
                        </div>
                    </div>
                    
                    <div class="footer">
                        This report was generated by Pesa Analyser.<br>
                        For more insights, visit our platform.
                    </div>
                </div>
            </body>
            </html>
            """)
            
            def format_currency(value):
                return f"{value:,.2f}" if value else "0.00"
            
            html_content = template.render(
                generated_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                total_income=report_data.get('total_income', 0),
                total_expenses=report_data.get('total_expenses', 0),
                net_cash_flow=report_data.get('net_cash_flow', 0),
                average_balance=report_data.get('average_balance', 0),
                insights=report_data.get('insights', []),
                recommendations=report_data.get('recommendations', []),
                app_url=os.getenv("APP_URL", "http://localhost:3000")
            )
            
            attachments = [report_path] if report_path and os.path.exists(report_path) else []
            
            return self.send_email(
                to_email=to_email,
                subject="Pesa Analyser - Your Financial Report",
                body="Please find your financial analysis report attached.",
                html_body=html_content,
                attachments=attachments
            )
            
        except Exception as e:
            logger.error(f"Send report email error: {str(e)}")
            return False
