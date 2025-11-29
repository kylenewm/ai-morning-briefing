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
    Format briefing text as HTML email with Dark Mode / Cyberpunk aesthetic.
    
    Args:
        briefing_text: Plain text briefing
        stats: Stats dict with story counts
        
    Returns:
        HTML formatted email
    """
    lines = briefing_text.split('\n')
    html_content = []
    
    import re
    
    # -- Design Tokens --
    COLORS = {
        'bg_page': '#050505',         # Deep black outer
        'bg_card': '#0a0a0a',         # Dark container
        'bg_subcard': '#161b22',      # Lighter sub-card (inverted contrast)
        'text_primary': '#e0e0e0',    # High readability gray-white
        'text_secondary': '#a0a0a0',  # Muted gray
        'accent': '#00f2ff',          # Electric Turquoise / Cyan
        'accent_podcast': '#8b5cf6',  # Violet/Purple for Podcasts
        'accent_ai': '#f59e0b',       # Orange for AI Articles
        'border': '#30363d',          # Standard border
        'border_active': 'rgba(0, 242, 255, 0.3)', # Turquoise glow border
        'border_podcast': 'rgba(139, 92, 246, 0.3)', # Violet glow border
        'border_ai': 'rgba(245, 158, 11, 0.3)',     # Orange glow border
        'header': '#ffffff',          # Pure white
        'code_bg': '#111111',
        'success': '#00ff9d',
    }
    
    def process_markdown_links(text: str, accent_color: str, border_color: str) -> str:
        """Convert markdown links [text](url) to styled HTML <a> tags."""
        return re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            f'<a href="\\2" style="color: {accent_color}; text-decoration: none; border-bottom: 1px solid {border_color}; transition: all 0.2s ease;">\\1</a>',
            text
        )
    
    def process_inline_formatting(text: str, accent_color: str = COLORS['accent'], border_color: str = COLORS['border_active']) -> str:
        """Process bold markdown and links."""
        # Convert **text** to <strong style="color: white;">text</strong>
        text = re.sub(r'\*\*(.+?)\*\*', f'<strong style="color: {COLORS["header"]}; font-weight: 600;">\\1</strong>', text)
        # Convert markdown links
        text = process_markdown_links(text, accent_color, border_color)
        return text
    
    in_story_card = False
    in_podcast_section = False # Track if we are processing podcast items
    in_ai_section = False      # Track if we are processing AI articles

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for separator
        if line == '---':
            # If inside a card, close it
            if in_story_card:
                html_content.append('</div></div>')
                in_story_card = False
            else:
                # Standalone separator if not in card
                html_content.append(f'<div style="height: 1px; background-color: {COLORS["border"]}; margin: 40px 0;"></div>')
            continue
        
        # Determine current accent colors based on section
        if in_podcast_section:
            current_accent = COLORS['accent_podcast']
            current_border = COLORS['border_podcast']
            current_bg_btn = "rgba(139, 92, 246, 0.1)"
            current_shadow = "rgba(139, 92, 246, 0.1)"
        elif in_ai_section:
            current_accent = COLORS['accent_ai']
            current_border = COLORS['border_ai']
            current_bg_btn = "rgba(245, 158, 11, 0.1)"
            current_shadow = "rgba(245, 158, 11, 0.1)"
        else:
            current_accent = COLORS['accent']
            current_border = COLORS['border_active']
            current_bg_btn = "rgba(0, 242, 255, 0.1)"
            current_shadow = "rgba(0, 242, 255, 0.1)"

        # Check for Button Link (Action button)
        # Matches lines like "[Read Full Story →](url)" or "[Listen to Episode →](url)"
        button_match = re.match(r'^\[([^\]]+)\]\(([^)]+)\)$', line)
        if button_match:
            text, url = button_match.groups()
            html_content.append(f'''
                <div style="margin-top: 24px;">
                    <a href="{url}" style="
                        display: inline-block;
                        padding: 12px 24px;
                        background-color: {current_bg_btn};
                        border: 1px solid {current_border};
                        color: {current_accent};
                        text-decoration: none;
                        border-radius: 6px;
                        font-size: 13px;
                        font-weight: 600;
                        letter-spacing: 0.5px;
                        text-transform: uppercase;
                        box-shadow: 0 0 10px {current_shadow};
                    ">{text}</a>
                </div>
            ''')
            continue

        # Check for headers
        # H3 and H4 starts a new "Story Card"
        if line.startswith('### ') or line.startswith('#### '):
            # Close previous card if open
            if in_story_card:
                html_content.append('</div></div>')
                in_story_card = False
            
            # Start new card
            in_story_card = True
            
            level = 3 if line.startswith('### ') else 4
            prefix = '### ' if level == 3 else '#### '
            raw_title = line.replace(prefix, '').strip()
            
            # Check for Podcast Tag
            is_podcast_item = False
            if '[TAG:PODCAST]' in raw_title:
                is_podcast_item = True
                raw_title = raw_title.replace('[TAG:PODCAST]', '').strip()
                # Ensure we are in podcast mode for colors
                in_podcast_section = True
                # Update colors for this card
                current_accent = COLORS['accent_podcast']
                current_border = COLORS['border_podcast']
            
            title = process_inline_formatting(raw_title, current_accent, current_border)
            
            font_size = "20px" if level == 3 else "18px"
            margin_top = "0" # No margin top because it's start of card
            
            # Add Badge if it's a podcast item
            badge_html = ""
            if is_podcast_item:
                badge_html = f'''
                    <div style="
                        display: inline-block;
                        background-color: {COLORS["accent_podcast"]};
                        color: white;
                        font-size: 10px;
                        font-weight: 700;
                        padding: 4px 8px;
                        border-radius: 4px;
                        text-transform: uppercase;
                        margin-bottom: 12px;
                        letter-spacing: 0.5px;
                    ">PODCAST</div>
                '''
            
            html_content.append(f'''
                <div style="
                    background-color: {COLORS["bg_subcard"]};
                    border: 1px solid {current_border};
                    border-top: 2px solid {current_border};
                    border-radius: 8px;
                    padding: 24px;
                    margin-bottom: 24px;
                    box-shadow: 0 0 15px {current_shadow};
                ">
                {badge_html}
                <div style="color: {COLORS["header"]}; margin-top: {margin_top}; margin-bottom: 16px; font-size: {font_size}; font-weight: 600; letter-spacing: -0.3px;">{title}</div>
                <div style="font-size: 15px; line-height: 1.6;">
            ''')
            continue

        # Section Headers (H1, H2) - Not inside cards
        if line.startswith('## '):
            if in_story_card:
                html_content.append('</div></div>')
                in_story_card = False
            
            # Detect section change to set appropriate color scheme
            section_title = line.replace('## ', '').strip()
            if "Podcast" in section_title:
                in_podcast_section = True
                in_ai_section = False
            elif "AI" in section_title and "Article" in section_title:
                in_ai_section = True
                in_podcast_section = False
            else:
                in_podcast_section = False
                in_ai_section = False
                
            title = process_inline_formatting(section_title, current_accent, current_border)
            # Section header with distinct bottom border
            html_content.append(f'''
                <h2 style="
                    color: {COLORS["header"]};
                    margin-top: 48px;
                    margin-bottom: 24px;
                    font-size: 24px;
                    font-weight: 700;
                    letter-spacing: -0.5px;
                    padding-bottom: 12px;
                    border-bottom: 2px solid {COLORS["border"]};
                ">{title}</h2>
            ''')
            continue
            
        elif line.startswith('# '):
            if in_story_card:
                html_content.append('</div></div>')
                in_story_card = False

            title = process_inline_formatting(line.replace('# ', '').strip(), current_accent, current_border)
            html_content.append(f'<h1 style="color: {COLORS["header"]}; margin-top: 0; margin-bottom: 32px; font-size: 32px; font-weight: 800; letter-spacing: -1px;">{title}</h1>')
            continue
        
        # Check for Metadata/Source (Blockquote style)
        if line.startswith('> '):
            meta_text = process_inline_formatting(line.replace('> ', '').strip(), current_accent, current_border)
            html_content.append(f'''
                <div style="
                    margin: 12px 0;
                    font-size: 12px;
                    color: {COLORS["text_secondary"]};
                    font-style: italic;
                ">{meta_text}</div>
            ''')
            continue
            
        # Context Block
        if line.startswith('**Context:**'):
            context_text = line.replace('**Context:**', '').strip()
            html_content.append(f'''
                <div style="
                    background-color: #0d1117; /* Darker inside the lighter card */
                    border-left: 3px solid {current_accent};
                    padding: 16px;
                    margin: 20px 0;
                    border-radius: 4px;
                ">
                    <div style="
                        color: {current_accent};
                        font-size: 11px;
                        font-weight: 700;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                        margin-bottom: 6px;
                    ">CONTEXT</div>
                    <div style="
                        color: {COLORS["text_primary"]};
                        line-height: 1.6;
                        font-size: 14px;
                    ">{context_text}</div>
                </div>
            ''')
            continue
            
        # Bold text on its own line
        if line.startswith('**') and line.endswith('**'):
            bold_text = line.strip('*')
            processed_text = process_inline_formatting(bold_text, current_accent, current_border)
            html_content.append(f'<p style="line-height: 1.6; color: {COLORS["header"]}; font-weight: 600; margin: 20px 0 12px 0;">{processed_text}</p>')
            continue
            
        # Bullets
        if line.startswith('• ') or line.startswith('- '):
            bullet_text = line[2:].strip()
            processed_text = process_inline_formatting(bullet_text, current_accent, current_border)
            html_content.append(f'''
                <div style="
                    margin: 12px 0;
                    padding-left: 20px;
                    position: relative;
                    line-height: 1.6;
                    color: {COLORS["text_primary"]};
                ">
                    <span style="
                        position: absolute;
                        left: 0;
                        top: 7px;
                        width: 5px;
                        height: 5px;
                        border-radius: 50%;
                        background-color: {current_accent};
                        box-shadow: 0 0 5px {current_accent};
                    "></span>
                    {processed_text}
                </div>
            ''')
            continue
            
        # Regular paragraph
        processed_line = process_inline_formatting(line, current_accent, current_border)
        html_content.append(f'<p style="line-height: 1.7; color: {COLORS["text_primary"]}; margin: 12px 0; font-size: 15px;">{processed_line}</p>')

    # Close any lingering card
    if in_story_card:
        html_content.append('</div></div>')
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="color-scheme" content="dark">
        <style>
            /* Dark mode resets */
            body {{ background-color: {COLORS["bg_page"]} !important; color: {COLORS["text_primary"]} !important; }}
            a {{ color: {COLORS["accent"]} !important; }}
        </style>
    </head>
    <body style="
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        margin: 0;
        padding: 40px 20px;
        background-color: {COLORS["bg_page"]};
        background-image: radial-gradient(circle at top center, #111111 0%, #050505 100%);
        color: {COLORS["text_primary"]};
        -webkit-font-smoothing: antialiased;
    ">
        <div style="
            background-color: {COLORS["bg_card"]};
            padding: 0;
            border-radius: 12px;
            box-shadow: 0 0 50px rgba(0, 242, 255, 0.05);
            max-width: 750px;
            margin: 0 auto;
            overflow: hidden;
            border: 1px solid #222;
        ">
            <!-- Hero Header -->
            <div style="
                background: {COLORS["bg_card"]};
                padding: 48px 40px;
                border-bottom: 1px solid {COLORS["border"]};
                text-align: center;
                position: relative;
            ">
                <!-- Top Accent Bar (short, centered) -->
                <div style="
                    width: 60px;
                    height: 2px;
                    background-color: {COLORS["accent"]};
                    margin: 0 auto 20px;
                "></div>

                <h1 style="
                    color: {COLORS["header"]};
                    margin: 0;
                    font-size: 42px;
                    font-weight: 600;
                    letter-spacing: -1px;
                ">Morning Briefing</h1>
                <p style="
                    color: {COLORS["text_secondary"]};
                    margin: 14px 0 0 0;
                    font-size: 15px;
                ">{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
            
            <!-- Stats Bar -->
            <div style="
                background-color: {COLORS["bg_page"]};
                padding: 16px 40px;
                border-bottom: 1px solid {COLORS["border"]};
                text-align: center;
                font-size: 15px;
                color: {COLORS["text_secondary"]};
            ">
                <span style="color: {COLORS["accent"]}; font-weight: 600;">{stats.get('newsletter_stories', 0)}</span> Stories
                <span style="margin: 0 16px; color: #444;">•</span>
                <span style="color: {COLORS["accent_ai"]}; font-weight: 600;">{stats.get('agent_articles', 0)}</span> AI Articles
                <span style="margin: 0 16px; color: #444;">•</span>
                <span style="color: {COLORS["accent_podcast"]}; font-weight: 600;">{stats.get('podcast_episodes', 0)}</span> Podcasts
            </div>
            
            <!-- Main Content -->
            <div style="padding: 16px 40px 40px;">
                {''.join(html_content)}
            </div>
            
            <!-- Footer -->
            <div style="
                background-color: {COLORS["bg_page"]};
                padding: 32px;
                border-top: 1px solid {COLORS["border"]};
                text-align: center;
                color: {COLORS["text_secondary"]};
                font-size: 12px;
            ">
                <p style="margin: 0;">Generated by AI PM Agent</p>
                <div style="margin-top: 16px;">
                    <a href="http://localhost:8000/docs" style="color: {COLORS["text_secondary"]}; text-decoration: none; margin: 0 10px;">API Docs</a>
                </div>
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
