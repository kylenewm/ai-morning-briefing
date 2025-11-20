#!/usr/bin/env python3
"""
Send a test morning briefing email with the AI agent.
This actually sends the email to your configured recipient.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent / "podcast-summarizer" / "backend"
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
load_dotenv()

# Import with absolute imports (backend is in sys.path)
from services.search_agent import SearchAgent
from config import settings
import logging
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def send_test_briefing():
    """Generate briefing content and send email."""
    print("=" * 80)
    print("📧 SENDING TEST MORNING BRIEFING EMAIL")
    print("=" * 80)
    print()
    
    logger.info(f"Email recipient: {settings.EMAIL_RECIPIENT}")
    logger.info(f"SMTP email: {settings.SMTP_EMAIL}")
    print()
    
    # Run the agent
    logger.info("🤖 Running AI Agent (3 searches)...")
    agent = SearchAgent()
    articles = await agent.search_comprehensive(max_iterations=1)
    
    logger.info(f"✅ Agent found {len(articles)} articles")
    print()
    
    # Build HTML email content
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #1a73e8; border-bottom: 3px solid #1a73e8; padding-bottom: 10px; }}
            h2 {{ color: #1a73e8; margin-top: 30px; }}
            .article {{ background-color: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #1a73e8; }}
            .article-title {{ font-size: 18px; font-weight: bold; color: #1a73e8; margin-bottom: 15px; }}
            .summary {{ margin: 15px 0; line-height: 1.7; color: #333; font-size: 15px; max-width: 100%; overflow-wrap: break-word; }}
            .summary p {{ margin: 12px 0; }}
            .summary strong {{ color: #1a73e8; font-weight: 600; }}
            .highlights {{ background-color: #fff; padding: 15px; border-radius: 6px; margin: 15px 0; }}
            .highlights ul {{ margin: 5px 0; padding-left: 20px; line-height: 1.6; }}
            .highlights li {{ margin: 8px 0; }}
            .metadata {{ color: #5f6368; font-size: 14px; margin-top: 15px; padding-top: 15px; border-top: 1px solid #dadce0; }}
            .read-more {{ display: inline-block; margin-top: 10px; padding: 8px 16px; background-color: #1a73e8; color: white; text-decoration: none; border-radius: 4px; font-weight: 500; }}
            .read-more:hover {{ background-color: #1557b0; }}
            .stats {{ background-color: #e8f0fe; padding: 15px; border-radius: 6px; margin: 20px 0; font-size: 14px; color: #1967d2; }}
        </style>
    </head>
    <body>
        <h1>🌅 Morning AI Briefing - TEST</h1>
        
        <div class="stats">
            📊 <strong>Test Run:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br>
            🤖 <strong>AI Agent:</strong> Found {len(articles)} curated articles from 3 specialized searches<br>
            ℹ️ <strong>Note:</strong> This test only shows AI-curated articles. Your daily briefing will also include newsletter stories and podcast summaries.
        </div>
        
        <h2>🤖 AI-Curated Articles</h2>
        <p style="color: #5f6368; font-style: italic;">Curated by AI Agent using Exa semantic search</p>
    """
    
    # Add each article
    if articles:
        for i, article in enumerate(articles, 1):
            html_content += f"""
            <div class="article">
                <div class="article-title">{i}. {article.title}</div>
            """
            
            # Add summary (truncate if too long)
            summary_text = article.summary or article.snippet or ""
            if summary_text:
                # Convert Markdown formatting to HTML first
                summary_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', summary_text)
                
                # Truncate very long summaries at a sentence boundary (keep first ~1200 chars)
                if len(summary_text) > 1200:
                    # Try to truncate at a sentence boundary (period followed by space)
                    truncated = summary_text[:1200]
                    last_period = truncated.rfind('. ')
                    if last_period > 800:  # Only truncate at period if it's reasonably far along
                        summary_text = truncated[:last_period + 1] + ".."
                    else:
                        # Fall back to word boundary
                        summary_text = truncated.rsplit(' ', 1)[0] + "..."
                
                # Add paragraph breaks for better spacing
                summary_text = summary_text.replace('\n\n', '</p><p>').replace('\n', '<br>')
                
                html_content += f'<div class="summary"><p>{summary_text}</p></div>'
            
            # Add highlights
            if article.highlights and len(article.highlights) > 0:
                html_content += '<div class="highlights"><strong>Key Highlights:</strong><ul>'
                for highlight in article.highlights[:3]:
                    html_content += f'<li>{highlight}</li>'
                html_content += '</ul></div>'
            
            # Add metadata
            metadata_parts = []
            if article.source:
                metadata_parts.append(f"📰 {article.source}")
            if article.published_date:
                try:
                    pub_date = datetime.fromisoformat(article.published_date.replace('Z', '+00:00'))
                    date_str = pub_date.strftime('%b %d, %Y')
                    metadata_parts.append(f"📅 {date_str}")
                except:
                    pass
            
            html_content += f'<div class="metadata">{" | ".join(metadata_parts)}</div>'
            html_content += f'<a href="{article.url}" class="read-more">Read Full Article →</a>'
            html_content += '</div>'
    else:
        html_content += '<p>⚠️ No articles found in this test run.</p>'
    
    html_content += """
        <hr style="margin: 40px 0; border: none; border-top: 2px solid #dadce0;">
        <p style="color: #5f6368; font-size: 12px; text-align: center;">
            This is a TEST email from your Morning Automation Workflow<br>
            Sent to verify AI agent integration is working correctly
        </p>
    </body>
    </html>
    """
    
    # Send the email
    logger.info("📧 Sending email...")
    try:
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['From'] = settings.SMTP_EMAIL
        msg['To'] = settings.EMAIL_RECIPIENT
        msg['Subject'] = f"🧪 TEST: Morning AI Briefing - {datetime.now().strftime('%B %d, %Y')}"
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send via Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"✅ Email sent successfully to {settings.EMAIL_RECIPIENT}")
        print()
        print("=" * 80)
        print("✅ SUCCESS - Check your email!")
        print("=" * 80)
        print()
        print(f"📬 Email sent to: {settings.EMAIL_RECIPIENT}")
        print(f"📊 Articles included: {len(articles)}")
        print(f"💰 Estimated cost: ~$0.03 (Exa API)")
        print()
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}", exc_info=True)
        print()
        print("=" * 80)
        print("❌ FAILED - Could not send email")
        print("=" * 80)
        print()
        print(f"Error: {e}")
        print()


if __name__ == "__main__":
    asyncio.run(send_test_briefing())

