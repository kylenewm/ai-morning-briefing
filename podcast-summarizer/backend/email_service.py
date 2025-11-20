"""
Email service for sending morning briefings.
Supports multiple email providers (Gmail SMTP, SendGrid, AWS SES).
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime

try:
    from .config import settings
except ImportError:
    from config import settings

logger = logging.getLogger(__name__)


def format_briefing_as_html(briefing_text: str, stats: dict) -> str:
    """
    Format briefing text as HTML email.
    
    Args:
        briefing_text: Plain text briefing
        stats: Stats dict with story counts
        
    Returns:
        HTML formatted email
    """
    # Convert plain text to HTML with proper header parsing
    lines = briefing_text.split('\n')
    html_content = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for separator
        if line == '---':
            # Soft gradient separator - professional and calming
            html_content.append('<div style="height: 1px; background: linear-gradient(to right, transparent, #cbd5e0 20%, #cbd5e0 80%, transparent); margin: 32px 0;"></div>')
            continue
            
        # Check for different header levels
        if line.startswith('#### '):
            title = line.replace('#### ', '').strip()
            html_content.append(f'<h4 style="color: #7f8c8d; margin-top: 16px; margin-bottom: 8px; font-size: 14px; font-weight: 600;">{title}</h4>')
        elif line.startswith('### '):
            title = line.replace('### ', '').strip()
            html_content.append(f'<h3 style="color: #1a73e8; margin-top: 24px; margin-bottom: 16px; font-size: 18px; font-weight: bold;">{title}</h3>')
        elif line.startswith('## '):
            title = line.replace('## ', '').strip()
            html_content.append(f'<h2 style="color: #202124; margin-top: 36px; margin-bottom: 20px; font-size: 22px; font-weight: bold; padding: 12px 16px; background-color: #f8f9fa; border-left: 4px solid #1a73e8; border-radius: 4px;">{title}</h2>')
        elif line.startswith('# '):
            title = line.replace('# ', '').strip()
            html_content.append(f'<h1 style="color: #2c3e50; margin-top: 32px; margin-bottom: 24px; font-size: 24px; font-weight: bold;">{title}</h1>')
        elif line.startswith('**') and line.endswith('**'):
            # Bold text on its own line
            bold_text = line.strip('*')
            html_content.append(f'<p style="line-height: 1.6; color: #2c3e50; font-weight: bold; margin: 12px 0;">{bold_text}</p>')
        elif line.startswith('• '):
            # Custom styled bullet
            bullet_text = line.replace('• ', '', 1).strip()
            # Process inline bold markdown
            import re
            processed_text = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #202124;">\1</strong>', bullet_text)
            html_content.append(f'<div style="margin: 8px 0; padding-left: 20px; position: relative;"><span style="position: absolute; left: 0; color: #1a73e8; font-weight: bold;">•</span>{processed_text}</div>')
        else:
            # Regular paragraph - process inline bold markdown
            import re
            # Convert **text** to <strong>text</strong>
            processed_line = re.sub(r'\*\*(.+?)\*\*', r'<strong style="color: #2c3e50;">\1</strong>', line)
            html_content.append(f'<p style="line-height: 1.8; color: #555; margin: 8px 0;">{processed_line}</p>')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa;">
        <div style="background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); max-width: 900px; margin: 0 auto;">
            <!-- Header with subtle accent -->
            <div style="background: linear-gradient(135deg, #1a73e8 0%, #4285f4 100%); padding: 24px; margin: -40px -40px 32px -40px; border-radius: 8px 8px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px; font-weight: 600; letter-spacing: -0.5px;">Your Morning Briefing</h1>
                <p style="color: rgba(255,255,255,0.95); margin: 8px 0 0 0; font-size: 14px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <!-- Simple Stats Line -->
            <div style="color: #5f6368; font-size: 14px; margin-bottom: 24px; padding: 16px; background-color: #f8f9fa; border-radius: 6px; border-left: 3px solid #1a73e8;">
                📊 Today: {stats.get('newsletter_stories', 0)} newsletter stories{', ' + str(stats.get('agent_articles', 0)) + ' AI-curated articles' if stats.get('agent_articles', 0) > 0 else ''}, {stats.get('podcast_episodes', 0)} podcast episodes
            </div>
            
            <!-- Content -->
            <div style="font-size: 16px;">
                {''.join(html_content)}
            </div>
            
            <!-- Footer -->
            <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #ecf0f1; text-align: center; color: #95a5a6; font-size: 12px;">
                <p>Generated by your Morning Automation Workflow</p>
                <p style="margin-top: 8px;">
                    <a href="http://localhost:8000/docs" style="color: #3498db; text-decoration: none;">View API Docs</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


def send_briefing_email(
    briefing_text: str,
    stats: dict,
    recipient_email: str,
    subject: Optional[str] = None,
    use_html: bool = True
) -> bool:
    """
    Send briefing email via Gmail SMTP.
    
    Args:
        briefing_text: Briefing content
        stats: Stats dict with story counts
        recipient_email: Email address to send to
        subject: Email subject (optional)
        use_html: Send as HTML email (default: True)
        
    Returns:
        bool: True if sent successfully
    """
    try:
        # Get email settings from environment
        smtp_email = settings.SMTP_EMAIL
        smtp_password = settings.SMTP_PASSWORD
        
        if not smtp_email or not smtp_password:
            logger.error("SMTP_EMAIL or SMTP_PASSWORD not configured")
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_email
        msg['To'] = recipient_email
        msg['Subject'] = subject or f"Morning Briefing - {datetime.now().strftime('%B %d, %Y')}"
        
        # Add plain text version
        text_part = MIMEText(briefing_text, 'plain')
        msg.attach(text_part)
        
        # Add HTML version if requested
        if use_html:
            html_content = format_briefing_as_html(briefing_text, stats)
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
        
        # Send via Gmail SMTP
        logger.info(f"Sending briefing email to {recipient_email}...")
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        
        logger.info(f"✅ Email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False


async def send_briefing_from_db(
    briefing_id: Optional[int] = None,
    recipient_email: Optional[str] = None
) -> bool:
    """
    Send most recent briefing from database.
    
    Args:
        briefing_id: Specific briefing ID (optional, uses most recent if None)
        recipient_email: Email to send to (optional, uses settings default)
        
    Returns:
        bool: True if sent successfully
    """
    from .database.db import SessionLocal
    from .database.models import Briefing, ContentItem
    
    try:
        db = SessionLocal()
        
        # Get briefing
        if briefing_id:
            briefing = db.query(Briefing).filter(Briefing.id == briefing_id).first()
        else:
            briefing = db.query(Briefing).order_by(Briefing.date.desc()).first()
        
        if not briefing:
            logger.error("No briefing found in database")
            return False
        
        # Get content counts for stats
        newsletter_count = db.query(ContentItem).filter(
            ContentItem.source_type == "newsletter"
        ).count()
        
        news_count = db.query(ContentItem).filter(
            ContentItem.source_type == "news"
        ).count()
        
        podcast_count = db.query(ContentItem).filter(
            ContentItem.source_type == "podcast"
        ).count()
        
        stats = {
            'newsletter_stories': newsletter_count,
            'news_stories': news_count,
            'podcast_episodes': briefing.total_episodes or podcast_count
        }
        
        db.close()
        
        # Send email
        recipient = recipient_email or settings.EMAIL_RECIPIENT
        
        if not recipient:
            logger.error("No recipient email configured")
            return False
        
        return send_briefing_email(
            briefing_text=briefing.briefing_text,
            stats=stats,
            recipient_email=recipient,
            use_html=True
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to send briefing from DB: {e}")
        return False

