"""
Gmail newsletter integration for pulling daily news from subscribed newsletters.
Supports TLDR AI, Morning Brew, and other curated sources.
"""

import logging
import os
import pickle
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from openai import AsyncOpenAI

try:
    from ..config import settings
except ImportError:
    from config import settings

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Newsletter configurations
NEWSLETTER_CONFIGS = {
    "tldr_ai": {
        "name": "TLDR AI",
        "from_email": "dan@tldrnewsletter.com",
        "subject_contains": None,  # Don't filter by subject, from_email is enough
        "priority": 1,
        "parser": "parse_tldr_ai"
    },
    "morning_brew": {
        "name": "Morning Brew",
        "from_email": "crew@morningbrew.com",
        "subject_contains": "Morning Brew",
        "priority": 2,
        "parser": "parse_morning_brew"
    },
    # Add more newsletters as needed
}


def get_gmail_service():
    """
    Authenticate and return Gmail API service.
    Uses OAuth 2.0 with credentials stored in token.pickle.
    """
    creds = None
    # Store credentials in the podcast-summarizer directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    token_path = os.path.join(base_dir, 'gmail_token.pickle')
    credentials_path = os.path.join(base_dir, 'gmail_credentials.json')
    
    # Load existing token
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("🔄 Refreshing Gmail credentials...")
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                logger.error("❌ gmail_credentials.json not found!")
                logger.error("   Download from Google Cloud Console:")
                logger.error("   https://console.cloud.google.com/apis/credentials")
                return None
            
            logger.info("🔐 Starting OAuth flow...")
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next time
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
        logger.info("✅ Gmail credentials saved")
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        logger.error(f"❌ Gmail API error: {error}")
        return None


def search_emails(
    service,
    from_email: Optional[str] = None,
    subject_contains: Optional[str] = None,
    hours_ago: int = 24
) -> List[Dict[str, Any]]:
    """
    Search for emails matching criteria.
    
    Args:
        service: Gmail API service
        from_email: Filter by sender
        subject_contains: Filter by subject text
        hours_ago: How many hours back to search
        
    Returns:
        List of email messages
    """
    try:
        # Build query
        query_parts = []
        
        # Date filter
        after_date = datetime.now() - timedelta(hours=hours_ago)
        query_parts.append(f'after:{int(after_date.timestamp())}')
        
        if from_email:
            query_parts.append(f'from:{from_email}')
        
        if subject_contains:
            query_parts.append(f'subject:"{subject_contains}"')
        
        query = ' '.join(query_parts)
        logger.info(f"📧 Gmail query: {query}")
        
        # Search
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=10
        ).execute()
        
        messages = results.get('messages', [])
        logger.info(f"✅ Found {len(messages)} emails")
        
        return messages
        
    except HttpError as error:
        logger.error(f"❌ Error searching emails: {error}")
        return []


def get_email_content(service, message_id: str) -> Optional[Dict[str, Any]]:
    """
    Get full email content including body.
    
    Args:
        service: Gmail API service
        message_id: Email message ID
        
    Returns:
        Dict with email data
    """
    try:
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        # Extract headers
        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
        
        # Extract body
        body = extract_email_body(message['payload'])
        
        return {
            'id': message_id,
            'subject': subject,
            'from': from_email,
            'date': date,
            'body': body
        }
        
    except HttpError as error:
        logger.error(f"❌ Error getting email content: {error}")
        return None


def extract_email_body(payload: Dict[str, Any]) -> str:
    """
    Extract email body from payload (handles multipart).
    Prioritizes HTML over plain text for better link extraction.
    """
    # Try to find HTML first
    html_body = _find_html_part(payload)
    if html_body:
        return html_body
    
    # Fall back to plain text
    if 'body' in payload and 'data' in payload['body']:
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
    
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                if 'data' in part['body']:
                    return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
    
    return ""


def _find_html_part(payload: Dict[str, Any]) -> Optional[str]:
    """
    Recursively find and return HTML part of email.
    """
    if payload.get('mimeType') == 'text/html' and 'data' in payload.get('body', {}):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
    
    for part in payload.get('parts', []):
        if part.get('mimeType') == 'text/html' and 'data' in part.get('body', {}):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
        if 'parts' in part:
            result = _find_html_part(part)
            if result:
                return result
    
    return None


def parse_tldr_ai(email_content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse TLDR AI newsletter format.
    
    Extracts article titles and URLs from the HTML email.
    The actual summarization is done by AI later.
    """
    import base64
    from urllib.parse import unquote
    
    # Get HTML content from email body
    body = email_content['body']
    soup = BeautifulSoup(body, 'html.parser')
    
    stories = []
    seen_urls = set()
    
    # Find all links in the email
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        # Decode tracking URLs (TLDR uses tracking.tldrnewsletter.com)
        if 'tracking.tldrnewsletter.com' in href:
            # Extract actual URL from tracking redirect
            match = re.search(r'https?:%2F%2F([^/]+.*?)(?:$|&)', href)
            if match:
                actual_url = 'https://' + unquote(match.group(1))
            else:
                actual_url = href
        else:
            actual_url = href
        
        # Get link text (story title) and clean it
        title = link.get_text(strip=True)
        
        # Remove "(X minute read)" or similar patterns from title
        title = re.sub(r'\s*\(\d+\s+minutes?\s+read\)\s*$', '', title, flags=re.IGNORECASE)
        
        # Clean URL: remove UTM parameters and tracking
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(actual_url)
        if parsed.query:
            # Remove utm_* parameters
            query_params = parse_qs(parsed.query)
            clean_params = {k: v for k, v in query_params.items() if not k.startswith('utm_')}
            clean_query = urlencode(clean_params, doseq=True) if clean_params else ''
            actual_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))
        
        # Look for parent context to get brief description
        parent = link.find_parent(['td', 'div', 'p'])
        brief_description = ""
        if parent:
            full_text = parent.get_text(strip=True)
            brief_description = full_text.replace(title, '').strip()[:200]
        
        # Filter for real article links
        skip_terms = ['tldr.tech', 'unsubscribe', 'sparkloop', 'advertise', 
                      'utm_campaign', 'preferences', 'view online']
        
        if (title and len(title) > 20 and 
            actual_url.startswith('http') and
            actual_url not in seen_urls and
            not any(term in actual_url.lower() for term in skip_terms)):
            
            stories.append({
                'title': title,
                'url': actual_url,
                'brief_description': brief_description,  # TLDR's description
                'source': 'TLDR AI',
                'needs_ai_summary': True  # Flag for AI processing
            })
            seen_urls.add(actual_url)
    
    logger.info(f"📰 Extracted {len(stories)} article URLs from TLDR AI")
    return stories


async def filter_and_rank_stories_for_ai_pm(stories: List[Dict[str, Any]], max_stories: int = 8) -> List[Dict[str, Any]]:
    """
    Use AI to filter out sponsor content and rank stories by relevance to AI Product Managers.
    
    Args:
        stories: List of story dictionaries with title, url, brief_description
        max_stories: Maximum number of stories to return
        
    Returns:
        List of filtered and ranked stories
    """
    if not stories:
        return []
    
    logger.info(f"🤖 AI filtering {len(stories)} stories for AI PM relevance...")
    
    # Prepare stories for AI analysis
    stories_text = ""
    for i, story in enumerate(stories):
        stories_text += f"{i+1}. {story['title']}\n"
        if story.get('brief_description'):
            stories_text += f"   Description: {story['brief_description']}\n"
        stories_text += f"   URL: {story['url']}\n\n"
    
    prompt = f"""You are an AI assistant helping to curate news for AI Product Managers. 

I have {len(stories)} stories from newsletters. Please:

1. FILTER OUT all sponsor content, advertisements, and promotional material
2. RANK the remaining stories by relevance to AI Product Managers
3. Return the top {max_stories} most relevant stories

Focus on stories relevant to AI PMs:
- Product launches and feature updates
- Technical breakthroughs and research
- Market analysis and business strategy  
- Funding rounds and acquisitions
- Regulatory developments
- User adoption trends
- Competitive analysis
- Platform/API changes

AVOID:
- Generic corporate press releases
- Sponsored content or ads
- Non-AI technology news
- Pure research without product implications

Stories to analyze:
{stories_text}

IMPORTANT: Return ONLY a valid JSON array with the story numbers (1-based) of the top {max_stories} most relevant stories, in order of relevance. Do not include any other text.

Example format:
["3", "7", "12", "1", "9", "15", "4", "8"]

If fewer than {max_stories} stories are relevant, return fewer numbers."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
            messages=[
                {"role": "system", "content": "You are an expert AI Product Manager who curates news for other AI PMs. Return only valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=200
        )
        
        # Parse AI response
        ai_response = response.choices[0].message.content.strip()
        logger.info(f"🤖 AI response: {ai_response}")
        
        # Clean up response - remove any markdown formatting
        if ai_response.startswith('```json'):
            ai_response = ai_response.replace('```json', '').replace('```', '').strip()
        elif ai_response.startswith('```'):
            ai_response = ai_response.replace('```', '').strip()
        
        # Extract story numbers from JSON response
        import json
        try:
            selected_indices = json.loads(ai_response)
            if not isinstance(selected_indices, list):
                raise ValueError("Response is not a list")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"❌ Failed to parse AI response: {e}")
            logger.error(f"❌ Raw response: {repr(ai_response)}")
            # Fallback: return first few stories
            return stories[:max_stories]
        
        # Convert 1-based indices to 0-based and get selected stories
        filtered_stories = []
        for idx_str in selected_indices:
            try:
                idx = int(idx_str) - 1  # Convert to 0-based
                if 0 <= idx < len(stories):
                    filtered_stories.append(stories[idx])
                else:
                    logger.warning(f"⚠️  Invalid story index: {idx_str}")
            except ValueError:
                logger.warning(f"⚠️  Invalid story index format: {idx_str}")
        
        logger.info(f"✅ AI filtered to {len(filtered_stories)} relevant stories for AI PMs")
        return filtered_stories
        
    except Exception as e:
        logger.error(f"❌ AI filtering failed: {e}")
        # Fallback: return first few stories
        return stories[:max_stories]


def parse_morning_brew(email_content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse Morning Brew newsletter format.
    """
    # Similar logic to TLDR but adapted for Morning Brew format
    # TODO: Implement based on Morning Brew's actual format
    return []


async def get_newsletter_stories(
    newsletter_key: str,
    hours_ago: int = 24,
    max_stories: int = 15
) -> Dict[str, Any]:
    """
    Get stories from a specific newsletter.
    
    Args:
        newsletter_key: Key from NEWSLETTER_CONFIGS
        hours_ago: How far back to search
        
    Returns:
        Dict with newsletter stories
    """
    if newsletter_key not in NEWSLETTER_CONFIGS:
        logger.error(f"❌ Unknown newsletter: {newsletter_key}")
        return {
            'newsletter': newsletter_key,
            'stories': [],
            'error': 'Unknown newsletter'
        }
    
    config = NEWSLETTER_CONFIGS[newsletter_key]
    logger.info(f"📧 Fetching {config['name']} from Gmail...")
    
    # Get Gmail service
    service = get_gmail_service()
    if not service:
        return {
            'newsletter': config['name'],
            'stories': [],
            'error': 'Gmail authentication failed'
        }
    
    # Search for emails
    messages = search_emails(
        service,
        from_email=config['from_email'],
        subject_contains=config.get('subject_contains'),
        hours_ago=hours_ago
    )
    
    if not messages:
        logger.warning(f"⚠️  No {config['name']} emails found in past {hours_ago} hours")
        return {
            'newsletter': config['name'],
            'stories': [],
            'error': f'No emails found in past {hours_ago} hours'
        }
    
    # Get most recent email
    most_recent = messages[0]
    email_content = get_email_content(service, most_recent['id'])
    
    if not email_content:
        return {
            'newsletter': config['name'],
            'stories': [],
            'error': 'Failed to fetch email content'
        }
    
    # Parse stories based on newsletter type
    parser_func = globals().get(config['parser'])
    if parser_func:
        raw_stories = parser_func(email_content)
    else:
        logger.error(f"❌ Parser not found: {config['parser']}")
        raw_stories = []
    
    # Apply AI filtering for AI PM relevance (only for TLDR AI for now)
    if newsletter_key == 'tldr_ai' and raw_stories:
        stories = await filter_and_rank_stories_for_ai_pm(raw_stories, max_stories=max_stories)
        logger.info(f"📊 Filtered from {len(raw_stories)} to {len(stories)} AI PM relevant stories")
    else:
        stories = raw_stories
    
    return {
        'newsletter': config['name'],
        'newsletter_key': newsletter_key,
        'email_date': email_content['date'],
        'stories': stories,
        'total_stories': len(stories),
        'raw_stories': len(raw_stories) if newsletter_key == 'tldr_ai' else len(stories)
    }


async def get_all_newsletters(hours_ago: int = 24, max_stories: int = 15) -> Dict[str, Any]:
    """
    Get stories from all configured newsletters.
    
    Args:
        hours_ago: How far back to search
        max_stories: Maximum stories to return per newsletter (after AI filtering)
        
    Returns:
        Dict with all newsletter stories
    """
    logger.info(f"📬 Fetching all newsletters from past {hours_ago} hours...")
    
    all_stories = {}
    errors = []
    
    for key, config in NEWSLETTER_CONFIGS.items():
        result = await get_newsletter_stories(key, hours_ago, max_stories=max_stories)
        
        if result.get('error'):
            errors.append({
                'newsletter': config['name'],
                'error': result['error']
            })
        else:
            all_stories[key] = result
    
    total = sum(len(n['stories']) for n in all_stories.values())
    
    return {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'newsletters': all_stories,
        'total_newsletters': len(all_stories),
        'total_stories': total,
        'errors': errors
    }


async def enrich_stories_with_ai(
    stories: List[Dict[str, Any]],
    max_stories: int = 10
) -> List[Dict[str, Any]]:
    """
    Use AI to fetch and summarize articles from URLs with AI PM focus.
    
    Args:
        stories: List of stories with 'url' and 'title' fields
        max_stories: Maximum number of stories to process
        
    Returns:
        List of enriched stories with AI-generated summaries and takeaways
    """
    logger.info(f"🤖 [NEW CODE V2] Enriching {min(len(stories), max_stories)} stories with FULL ARTICLE FETCHING...")
    logger.info(f"   First story URL: {stories[0].get('url', 'N/A') if stories else 'No stories'}")
    
    enriched_stories = []
    
    # Process stories in parallel (but limit to avoid rate limits)
    import asyncio
    
    async def summarize_single_story(story: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize a single article with AI"""
        try:
            logger.info(f"   🔍 Processing: {story['title'][:60]}...")
            
            # Fetch article content
            import httpx
            from bs4 import BeautifulSoup
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(story['url'], follow_redirects=True)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "footer", "header"]):
                        script.decompose()
                    
                    # Get text
                    text = soup.get_text()
                    
                    # Clean up whitespace
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    article_text = '\n'.join(chunk for chunk in chunks if chunk)
                    
                    # Truncate if too long (keep first 8000 chars)
                    if len(article_text) > 8000:
                        article_text = article_text[:8000] + "\n\n[Article continues...]"
                    
                    logger.info(f"   📄 Fetched article content ({len(article_text)} chars)")
                    
            except Exception as fetch_err:
                logger.warning(f"   ⚠️  Could not fetch article: {fetch_err}")
                article_text = None
            
            system_prompt = """Clean this article for an AI Product Manager briefing.

REMOVE:
- "Today's article discusses..."
- "The piece mentions..."
- "They explain..."
- "The author states..."
- Any conversational meta-commentary about the article
- Filler phrases and redundant context

KEEP & ORGANIZE:
- Core concepts and how they work
- Specific examples with context
- Technical details and implementation notes
- Tactical advice and workflows
- All numbers, dates, names, metrics, quotes
- Business implications and strategic insights

Format with subheadings. Write in active voice. Present the information directly—don't narrate that "the article discusses" something.

Match the article's natural length - don't pad short articles, don't truncate long ones.

Provide:
**Summary**: Write detailed paragraphs with subheadings that cover the article content directly.

Include:
- What happened/was announced/was found (state it directly)
- Companies, people, products mentioned
- Specific dates and timelines
- Technical details, methodology, architecture
- Context, background, reasoning
- All metrics, costs, performance data, growth figures
- Important statements and quotes
- Roadmaps, plans, implications

# REMOVED: Key Points (redundant with summary)
# 2. **Key Points** (3-7 items): Most important specific facts
#    - Include numbers and names
#    - Be concrete and specific

Format as JSON:
{
  "summary": "..."
}"""
            
            if article_text:
                user_content = f"Create a detailed, substantive summary of this article:\n\nTitle: {story['title']}\n\nArticle Text:\n{article_text}"
            else:
                # Fallback if we couldn't fetch the article
                user_content = f"Based on the title and brief description, provide what context you can:\n\nTitle: {story['title']}\nBrief: {story.get('brief_description', 'N/A')}"
            
            response = await openai_client.chat.completions.create(
                model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=2000  # Allow for 500+ word summaries
            )
            
            import json
            ai_analysis = json.loads(response.choices[0].message.content)
            
            enriched_story = {
                **story,
                'summary': ai_analysis.get('summary', ''),
                # 'key_points': ai_analysis.get('key_points', []),  # REMOVED: redundant with summary
                'enriched': True
            }
            
            # Save to database
            try:
                from ..database import CacheService
                
                # REMOVED: Key points formatting (redundant with summary)
                # key_points_text = "\n".join([f"• {point}" for point in enriched_story.get('key_points', [])])
                # insight_text = f"{enriched_story['summary']}\n\nKey Points:\n{key_points_text}"
                insight_text = enriched_story['summary']
                
                CacheService.save_content_and_insight(
                    source_type="newsletter",
                    source_name=story.get('newsletter', 'TLDR AI'),
                    item_url=story['url'],
                    title=story['title'],
                    transcript=None,  # No transcript for articles
                    insight=insight_text,
                    youtube_url=None,
                    published_date=None,  # Could parse from email date if needed
                    description=story.get('brief_description', ''),
                    model_name="gpt-4o-mini",
                    test_mode=False
                )
            except Exception as cache_err:
                logger.warning(f"⚠️  Failed to cache newsletter story: {cache_err}")
            
            return enriched_story
            
        except Exception as e:
            import traceback
            logger.error(f"⚠️  Failed to enrich: {story['title'][:50]}... - {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                **story,
                'summary': story.get('brief_description', ''),
                'enriched': False,
                'error': str(e)
            }
    
    # Process in batches of 5 to avoid overwhelming the API
    batch_size = 5
    for i in range(0, min(len(stories), max_stories), batch_size):
        batch = stories[i:i+batch_size]
        logger.info(f"   Processing batch {i//batch_size + 1}...")
        
        batch_results = await asyncio.gather(*[summarize_single_story(s) for s in batch])
        enriched_stories.extend(batch_results)
        
        # Small delay between batches
        if i + batch_size < min(len(stories), max_stories):
            await asyncio.sleep(1)
    
    success_count = sum(1 for s in enriched_stories if s.get('enriched'))
    logger.info(f"✅ Successfully enriched {success_count}/{len(enriched_stories)} stories")
    
    return enriched_stories


async def generate_ai_pm_briefing(
    enriched_stories: List[Dict[str, Any]]
) -> str:
    """
    Generate a cohesive AI PM briefing from enriched stories.
    
    Args:
        enriched_stories: List of stories with AI summaries
        
    Returns:
        Formatted briefing text
    """
    logger.info("📝 Generating briefing...")
    
    # Build context for GPT
    stories_context = ""
    for i, story in enumerate(enriched_stories, 1):
        stories_context += f"\n{i}. {story['title']}\n"
        stories_context += f"   URL: {story.get('url', 'N/A')}\n"
        stories_context += f"   {story.get('summary', '')}\n"
        # REMOVED: Key points (redundant with summary)
        # if story.get('key_points'):
        #     stories_context += f"   Key points: {'; '.join(story.get('key_points', []))}\n"
    
    system_prompt = """You are creating a detailed news briefing. Write highly detailed, substantive summaries of each story.

CRITICAL REQUIREMENTS:
- Cover EACH story separately with substantial depth (3-5 paragraphs per story)
- Write 1500-2000 words total
- Extract and present ALL key details from the source material
- Include specific numbers, dates, names, technical details, quotes
- Let the content dictate what's important - don't force a structure
- Include source link at the end of each story

YOUR JOB:
Read each article and write a detailed summary that captures:
- All important facts, announcements, findings
- Specific details: numbers, dates, names, metrics, quotes
- Technical specifics: how things work, architecture, methodology
- Context provided: background, comparisons, market position
- Forward-looking statements: roadmaps, implications mentioned

Write like detailed journalism - present what the article says, don't add your own analysis or opinions.

TONE:
- Direct and factual, like detailed news reporting
- NOT conversational, analytical, or prescriptive
- Focus on substance: specifics, data, details
- Professional and clear

DO NOT:
- Add your own analysis, opinions, or "implications"
- Group multiple stories together
- Use casual phrases or conversational style
- Be brief or skip important details
- Forget source links

FORMAT:
## [Article Title]

[3-5 detailed paragraphs covering all key information from the article]

[Source: url]"""
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create a detailed in-depth briefing covering each story separately:\n\n{stories_context}"}
            ],
            temperature=0.5,
            max_tokens=3500
        )
        
        briefing = response.choices[0].message.content
        logger.info("✅ Generated AI PM briefing")
        return briefing
        
    except Exception as e:
        logger.error(f"❌ Error generating briefing: {e}")
        return "Error generating briefing"

