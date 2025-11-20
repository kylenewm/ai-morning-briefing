"""
AssemblyAI Transcription Module
Handles podcast transcription using AssemblyAI API with caching
"""

import os
import asyncio
import logging
from typing import Optional, Dict, Any
import assemblyai as aai

from ..database.cache_service import CacheService
from ..database.models import ContentItem

logger = logging.getLogger(__name__)

class AssemblyAITranscriber:
    """Handles podcast transcription using AssemblyAI API"""
    
    def __init__(self):
        # Set API key
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not aai.settings.api_key:
            raise ValueError("ASSEMBLYAI_API_KEY not found in environment variables")
        
        self.cache_service = CacheService()
        
    async def transcribe_episode(self, episode_data: Dict[str, Any], test_mode: bool = False) -> Optional[str]:
        """
        Transcribe a podcast episode using AssemblyAI API
        
        Args:
            episode_data: Episode data from RSS feed
            test_mode: If True, limit to first minute for testing
            
        Returns:
            Full transcript text or None if failed
        """
        try:
            # Extract episode info
            episode_guid = episode_data.get('guid', '')
            episode_title = episode_data.get('title', 'Unknown Episode')
            
            # Get MP3 URL from episode data
            mp3_url = episode_data.get('enclosure_url', '') or episode_data.get('audio_url', '')
            
            if not mp3_url:
                logger.warning(f"No MP3 URL found for episode: {episode_title}")
                return None
                
            logger.info(f"Transcribing episode: {episode_title}")
            logger.info(f"MP3 URL: {mp3_url}")
            
            # Check cache first - use episode URL as unique identifier (more reliable than GUID)
            episode_url = episode_data.get('link', '') or episode_data.get('audio_url', '') or mp3_url
            cached_transcript = await self._get_cached_transcript(episode_url)
            if cached_transcript:
                logger.info(f"Using cached transcript for: {episode_title}")
                return cached_transcript
            
            # Create transcriber with Universal model (default)
            transcriber = aai.Transcriber()
            
            # For test mode, we could add a config to limit duration
            # but AssemblyAI doesn't have a built-in duration limit
            # We'll handle this by checking the result length
            if test_mode:
                logger.info("Test mode: Transcribing first portion of audio")
            
            # Transcribe the audio (AssemblyAI accepts URLs directly!)
            transcript = transcriber.transcribe(mp3_url)
            
            # Check if transcription was successful
            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"Transcription failed: {transcript.error}")
                return None
            
            if transcript.status != aai.TranscriptStatus.completed:
                logger.error(f"Transcription not completed. Status: {transcript.status}")
                return None
            
            transcript_text = transcript.text
            if not transcript_text:
                logger.warning(f"No transcript text returned for: {episode_title}")
                return None
            
            # For test mode, limit to first ~1000 words (roughly 1 minute)
            if test_mode and len(transcript_text.split()) > 1000:
                words = transcript_text.split()[:1000]
                transcript_text = ' '.join(words) + "... [truncated for test mode]"
                logger.info(f"Test mode: Truncated transcript to {len(words)} words")
            
            # Normalize URL before caching to prevent future lookup issues
            normalized_url = self._normalize_url(episode_url) or episode_url
            await self._cache_transcript(normalized_url, transcript_text, episode_data)
            
            logger.info(f"Successfully transcribed: {episode_title} ({len(transcript_text)} chars)")
            return transcript_text
            
        except Exception as e:
            logger.error(f"Error transcribing episode {episode_title}: {e}")
            return None
    
    async def _get_cached_transcript(self, episode_url: str) -> Optional[str]:
        """Get cached transcript from database by episode URL"""
        try:
            from ..database.db import SessionLocal
            db = SessionLocal()
            try:
                # Look up by episode URL (unique identifier)
                cached_item = db.query(ContentItem).filter(
                    ContentItem.source_type == "assemblyai_transcript",
                    ContentItem.item_url == episode_url
                ).first()
                
                if cached_item and cached_item.transcript:
                    logger.info(f"Found cached transcript for: {episode_url[:80]}")
                    return cached_item.transcript
                return None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting cached transcript: {e}")
            return None
    
    async def _cache_transcript(self, episode_url: str, transcript: str, episode_data: Dict[str, Any]):
        """Cache transcript in database using episode URL as unique identifier"""
        try:
            from ..database.db import SessionLocal
            from sqlalchemy import func
            db = SessionLocal()
            try:
                # Check if already exists
                existing = db.query(ContentItem).filter(
                    ContentItem.source_type == "assemblyai_transcript",
                    ContentItem.item_url == episode_url
                ).first()
                
                if existing:
                    # Update existing
                    existing.transcript = transcript
                    existing.transcript_fetched = True
                    existing.transcript_length = len(transcript)
                    existing.updated_at = func.now()
                else:
                    # Parse published date
                    published_date = None
                    if episode_data.get('pub_date'):
                        try:
                            from dateutil import parser
                            published_date = parser.parse(episode_data['pub_date'])
                        except Exception as e:
                            logger.warning(f"Could not parse date {episode_data.get('pub_date')}: {e}")
                    
                    # Create new
                    content_item = ContentItem(
                        source_type="assemblyai_transcript",
                        source_name=episode_data.get('podcast_name', 'Unknown Podcast'),
                        item_url=episode_url,
                        title=episode_data.get('title', 'Unknown Episode'),
                        published_date=published_date,
                        transcript=transcript,
                        transcript_fetched=True,
                        transcript_length=len(transcript),
                        created_at=func.now()
                    )
                    db.add(content_item)
                
                db.commit()
                logger.info(f"Cached transcript for: {episode_url[:80]}")
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error caching transcript: {e}")
    
    async def get_transcript_summary(self, transcript: str, episode_title: str = "Unknown", episode_url: str = "") -> Optional[str]:
        """
        Generate AI summary from transcript using OpenAI
        
        Args:
            transcript: Full transcript text
            episode_title: Title of the episode
            episode_url: URL of the episode for caching
            
        Returns:
            AI-generated summary or None if failed
        """
        try:
            # Check for cached summary first
            if episode_url:
                cached_summary = await self._get_cached_summary(episode_url)
                if cached_summary:
                    logger.info(f"Using cached summary for: {episode_title}")
                    return cached_summary
            
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Use full transcript - no truncation
            logger.info(f"Processing full transcript ({len(transcript)} chars) for: {episode_title}")
            
            prompt = f"""
            Clean this podcast transcript for an AI Product Manager briefing.
            
            REMOVE:
            - Greetings, outros, sponsor reads
            - "Today we're going to talk about..."
            - "Thanks for listening..."
            - Conversational filler ("you know", "like", "um")
            
            KEEP & ORGANIZE:
            - Core concepts and how they work
            - Specific examples with context
            - Tactical advice and workflows
            - Technical details and implementation notes
            
            Format with subheadings. Write in active voice. Present the information directly—don't narrate that "they discussed" something.
            
            Episode: {episode_title}
            
            Transcript:
            {transcript}
            """
            
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
                messages=[
                    {"role": "system", "content": "You are an expert AI Product Manager who extracts actionable insights from podcast content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content
            logger.info(f"Generated AI summary for: {episode_title}")
            
            # Generate practical tips only (enriched content removed - adds no value)
            practical_tips = await self.generate_practical_tips(transcript, summary, episode_title)
            
            # Cache summary and tips if we have an episode URL (normalize URL first)
            if episode_url and summary:
                normalized_url = self._normalize_url(episode_url) or episode_url
                await self._cache_summary(normalized_url, summary, episode_title, practical_tips, None)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for consistent cache lookups.
        Removes query params, trailing slashes, normalizes protocol.
        """
        if not url:
            return ""
        
        from urllib.parse import urlparse, urlunparse
        
        # Parse URL
        parsed = urlparse(url)
        
        # Normalize: lowercase domain, remove trailing slash, remove query/fragment
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip('/'),
            "",  # Remove params
            "",  # Remove query
            ""   # Remove fragment
        ))
        
        return normalized
    
    def get_insights_from_content_item(self, content_item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get insights from ContentItem by ID (more reliable than URL lookup).
        Returns dict with insight_text, practical_tips, enriched_content.
        
        This is the scalable, reusable method for getting cached insights.
        """
        try:
            from ..database.db import SessionLocal
            from ..database.models import Insight
            import json
            
            db = SessionLocal()
            try:
                # Get most recent insight for this content item
                insight = db.query(Insight).filter(
                    Insight.content_item_id == content_item_id
                ).order_by(Insight.created_at.desc()).first()
                
                if insight and insight.insight_text:
                    # Parse practical tips JSON
                    practical_tips_list = []
                    if insight.practical_tips:
                        try:
                            practical_tips_list = json.loads(insight.practical_tips)
                        except:
                            logger.warning(f"Could not parse practical_tips JSON for content_item_id {content_item_id}")
                    
                    return {
                        'insight_text': insight.insight_text,
                        'practical_tips': practical_tips_list,
                        'enriched_content': insight.enriched_content
                    }
                return None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting insights from content_item_id {content_item_id}: {e}")
            return None
    
    async def _get_cached_summary(self, episode_url: str) -> Optional[str]:
        """Get cached summary from database by URL (legacy method, prefer get_insights_from_content_item)"""
        try:
            from ..database.db import SessionLocal
            from ..database.models import ContentItem, Insight
            db = SessionLocal()
            try:
                # Try exact match first
                content_item = db.query(ContentItem).filter(
                    ContentItem.item_url == episode_url
                ).first()
                
                # If not found, try normalized URL
                if not content_item:
                    normalized_url = self._normalize_url(episode_url)
                    if normalized_url:
                        # Try to find by normalized URL (fuzzy match)
                        all_items = db.query(ContentItem).filter(
                            ContentItem.source_type == "assemblyai_transcript"
                        ).all()
                        
                        for item in all_items:
                            if self._normalize_url(item.item_url) == normalized_url:
                                content_item = item
                                break
                
                if content_item:
                    # Find the most recent insight for this content
                    insight = db.query(Insight).filter(
                        Insight.content_item_id == content_item.id
                    ).order_by(Insight.created_at.desc()).first()
                    
                    if insight and insight.insight_text:
                        logger.info(f"Found cached summary: {episode_url}")
                        return insight.insight_text
                return None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting cached summary: {e}")
            return None
    
    async def _cache_summary(self, episode_url: str, summary: str, episode_title: str, practical_tips: str = None, enriched_content: str = None):
        """Cache summary, practical tips, and enriched content in database"""
        try:
            from ..database.db import SessionLocal
            from ..database.models import ContentItem, Insight
            from sqlalchemy import func
            from datetime import datetime
            db = SessionLocal()
            try:
                # First find or create the content item
                content_item = db.query(ContentItem).filter(
                    ContentItem.item_url == episode_url
                ).first()
                
                if not content_item:
                    # Create new content item
                    content_item = ContentItem(
                        source_type="assemblyai_transcript",
                        source_name="AssemblyAI Transcript",
                        item_url=episode_url,
                        title=episode_title,
                        created_at=func.now()
                    )
                    db.add(content_item)
                    db.flush()  # Get the ID
                
                # Create new insight entry with all three layers
                insight = Insight(
                    content_item_id=content_item.id,
                    insight_text=summary,
                    practical_tips=practical_tips,
                    enriched_content=enriched_content,
                    model_name="gpt-4o-mini",
                    was_test_mode=False,
                    token_count=len(summary.split()),
                    created_at=func.now()
                )
                db.add(insight)
                
                db.commit()
                logger.info(f"Cached summary, tips, and enriched content: {episode_url}")
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error caching summary: {e}")
    
    async def generate_practical_tips(self, transcript: str, summary: str, episode_title: str) -> Optional[str]:
        """
        Extract practical tips from transcript that aren't in the summary
        
        Args:
            transcript: Full transcript text
            summary: Already generated concept summary
            episode_title: Title of the episode
            
        Returns:
            JSON array of 4-6 practical tip strings
        """
        try:
            from openai import AsyncOpenAI
            import json
            
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Use first 15000 chars of transcript for context
            transcript_sample = transcript[:15000]
            
            prompt = f"""You have a FULL podcast transcript and a clean summary. Extract the 
PRACTICAL LEARNING INSIGHTS that make this podcast actionable.

FULL TRANSCRIPT (first 15000 chars):
{transcript_sample}

CLEAN SUMMARY (what's already captured):
{summary}

Extract learning-focused elements that DON'T appear in the summary:

**1. WORKFLOWS & APPROACHES (1-2)**
How did someone actually do something? Look for:
- "Here's how I did it..."
- "The process was..."
- "What worked for me was..."
- Step-by-step approaches you can copy

Example: "Empty folder → Open in Cursor → Ask for skill → Get validation script automatically"

**2. TOOL INSIGHTS (1-2)**
Practical tool comparisons and tips:
- Speed differences (3x faster, 2 mins vs 10 mins)
- Which tool for which job
- Unexpected tool capabilities
- Things that don't work well

Example: "Cursor took 3 minutes vs web app's 10 minutes for skill creation"

**3. LEARNING PITFALLS (0-1)**
What's confusing or hard? What failed?
- "Spent X time confused about..."
- "The tricky part is..."
- "What doesn't work is..."
- Mistakes they made

Example: "Spent 5 mins confused - skill structure isn't documented well, expect to experiment"

**4. TACTICAL NUMBERS (1-2)**
Specific metrics that inform decisions:
- Timelines (built in 3 days)
- Performance (3x faster, 40% less memory)
- Scale (handles 1000 requests/sec)
- Cost ($0.10 vs $1.00)

Example: "Built in 2 hours, not 2 days"

**5. META-STRATEGIES (0-1)**
Smart approaches or frameworks:
- "The trick is..."
- "The pattern we found..."
- "The meta-approach is..."
- Clever solutions

Example: "Use AI to create a skill for creating skills (meta-approach)"

RULES:
- Extract, don't infer - only what's explicitly in transcript
- Focus on ACTIONABLE learning, not news
- Include WHO said it when it adds credibility
- Be specific with numbers and details
- Skip company news, market commentary, drama
- Only include items that help someone APPLY or UNDERSTAND better
- Return 4-6 total items across all categories

Return as a JSON array of strings. Each string should be a complete, self-contained tip.

Example format:
["Tool Choice: Cursor is 3x faster than web app for skill creation (3 mins vs 10 mins)", "Workflow: Empty folder → Cursor → ask for skill → validation auto-generated", "Gotcha: Skill structure isn't documented - expect 5+ mins of confusion"]

Episode: {episode_title}
"""
            
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
                messages=[
                    {"role": "system", "content": "You are an expert at extracting practical, actionable insights from educational content."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            tips_json = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if tips_json.startswith('```'):
                # Remove ```json or ``` at start and ``` at end
                lines = tips_json.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]  # Remove first line
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]  # Remove last line
                tips_json = '\n'.join(lines).strip()
            
            # Validate it's valid JSON
            try:
                tips_array = json.loads(tips_json)
                if isinstance(tips_array, list) and len(tips_array) > 0:
                    logger.info(f"Generated {len(tips_array)} practical tips for: {episode_title}")
                    return tips_json
                else:
                    logger.warning(f"Invalid tips format for: {episode_title}: {tips_json[:200]}")
                    return None
            except json.JSONDecodeError as e:
                logger.warning(f"Could not parse tips JSON for: {episode_title}: {e}")
                logger.warning(f"Raw response: {tips_json[:500]}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating practical tips: {e}")
            return None
    
    async def generate_enriched_content(self, transcript: str, summary: str, episode_title: str) -> Optional[str]:
        """
        Generate enriched content with stories, workflows, and detailed insights
        
        Args:
            transcript: Full transcript text
            summary: Already generated concept summary
            episode_title: Title of the episode
            
        Returns:
            Markdown-formatted enriched content
        """
        try:
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Use first 15000 chars of transcript for context
            transcript_sample = transcript[:15000]
            
            prompt = f"""You have a FULL podcast transcript and a clean summary. Create ENRICHED CONTENT
with stories, workflows, and detailed insights for someone who wants to learn deeply.

FULL TRANSCRIPT (first 15000 chars):
{transcript_sample}

CLEAN SUMMARY (already captured):
{summary}

Create enriched sections that add depth beyond the summary:

## 📖 Stories & Learning From the Episode

### 🚀 How It Actually Works in Practice
Extract real workflows and processes mentioned in the conversation. Include:
- Exact steps people took
- What actually happened (not just theory)
- Real examples with names, tools, timelines

### ⚡ Real Tool Comparisons & Insights
Extract specific tool mentions with context:
- Tool names and what they were used for
- Performance comparisons with numbers
- Which tools worked well, which didn't
- Unexpected tool capabilities or limitations

### 🤔 What Actually Goes Wrong
Extract pitfalls, failures, and confusing parts:
- Things that were hard or confusing
- Mistakes people made
- What took longer than expected
- Common misunderstandings

### 🧠 Smart Approaches & Strategies
Extract clever approaches and meta-strategies:
- Non-obvious ways of solving problems
- Meta-approaches (using X to build X)
- Patterns and frameworks mentioned
- Contrarian or surprising strategies

### 😲 Unexpected Discoveries
Extract surprising outcomes or counter-intuitive findings:
- Things that worked better than expected
- Unexpected side effects (good or bad)
- Counter-intuitive results
- "Wait, what?" moments

RULES:
- Extract actual quotes and stories from the transcript
- Include names, numbers, and specific details
- Focus on LEARNING value, not entertainment
- Each section should be 2-4 paragraphs
- Write in clear, direct language (not conversational)
- Skip sections if nothing interesting to extract

Episode: {episode_title}
"""
            
            response = await client.chat.completions.create(
                model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
                messages=[
                    {"role": "system", "content": "You are an expert at creating rich learning materials from podcast transcripts."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            enriched = response.choices[0].message.content
            logger.info(f"Generated enriched content for: {episode_title} ({len(enriched)} chars)")
            return enriched
                
        except Exception as e:
            logger.error(f"Error generating enriched content: {e}")
            return None
