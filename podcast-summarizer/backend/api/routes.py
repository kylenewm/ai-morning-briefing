"""
API routes for the podcast summarizer application.
Defines all FastAPI endpoint handlers.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from ..ingestion.sources import get_all_podcast_sources, get_podcast_by_id
from ..ingestion.rss_parser import parse_podcast_feed, fetch_all_feeds
from ..ingestion.news_search import search_all_news_categories, generate_news_briefing, NEWS_CATEGORIES
from ..services.search_evaluator import evaluate_search
from ..services.agents.search_orchestrator import search_all_categories, flatten_results
# DISABLED: news_agent and news_tavily modules not available
# from ..ingestion.news_agent import search_all_categories_with_agents
# from ..ingestion.news_tavily import search_all_categories_with_tavily
from ..ingestion.news_perplexity import search_all_categories_with_perplexity
from ..ingestion.gmail_newsletters import (
    get_all_newsletters, 
    get_newsletter_stories,
    enrich_stories_with_ai,
    generate_ai_pm_briefing
)
from ..ai.summarizer import summarize_episode, generate_briefing
from ..ai.insight_extractor import extract_insights_from_episode
from ..services.episode_processor import process_episodes_parallel, process_single_episode
from ..services.podcast_processor import process_all_podcasts_parallel
from ..services.assemblyai_processor import process_all_podcasts_with_assemblyai
from ..services.content_fallback import fallback_service

logger = logging.getLogger(__name__)

async def get_cached_podcast_summaries(limit: int = 9) -> List[Dict[str, Any]]:
    """
    Get cached podcast summaries from the database.
    
    Args:
        limit: Maximum number of summaries to return
        
    Returns:
        List of cached podcast summaries with metadata
    """
    try:
        from ..database.db import SessionLocal
        from ..database.models import ContentItem, Insight
        
        db = SessionLocal()
        try:
            # Get cached transcripts with their insights
            cached_episodes = db.query(ContentItem).filter(
                ContentItem.source_type == 'assemblyai_transcript'
            ).order_by(ContentItem.published_date.desc()).limit(limit).all()
            
            summaries = []
            for episode in cached_episodes:
                # Get the most recent insight for this episode
                insight = db.query(Insight).filter(
                    Insight.content_item_id == episode.id
                ).order_by(Insight.created_at.desc()).first()
                
                # Determine podcast name from source_name or URL
                podcast_name = episode.source_name or "Unknown Podcast"
                
                # Fallback to URL matching if source_name is "Unknown Podcast"
                if podcast_name == "Unknown Podcast":
                    url_lower = episode.item_url.lower() if episode.item_url else ""
                    if 'lennysnewsletter.com' in url_lower:
                        podcast_name = "Lenny's Podcast"
                    elif 'spotify.com/pod/show/mlops' in url_lower:
                        podcast_name = "MLOps Community"
                    elif 'twimlai.com' in url_lower:
                        podcast_name = "TWIML AI"
                    elif 'dataskeptic.com' in url_lower or 'dataskeptic.libsyn.com' in url_lower:
                        podcast_name = "Data Skeptic"
                    elif 'megaphone.fm' in url_lower or 'datacamp' in url_lower:
                        podcast_name = "DataFramed by DataCamp"
                    elif 'anchor.fm' in url_lower or 'spotify.com/pod/show/nlw' in url_lower:
                        podcast_name = "The AI Daily Brief"
                
                # If no insight, generate one on-the-fly
                if not insight or not insight.insight_text:
                    logger.info(f"Generating summary for: {episode.title[:50]}")
                    from ..ingestion.assemblyai_transcriber import AssemblyAITranscriber
                    transcriber = AssemblyAITranscriber()
                    summary_text = await transcriber.get_transcript_summary(
                        episode.transcript,
                        episode.title,
                        episode.item_url
                    )
                    if summary_text:
                        logger.info(f"✅ Generated summary: {len(summary_text)} chars")
                    else:
                        logger.warning(f"Failed to generate summary for: {episode.title[:50]}")
                        continue  # Skip episodes without summaries
                else:
                    summary_text = insight.insight_text
                
                # Validate we have content to work with
                if not summary_text or len(summary_text.strip()) < 50:
                    logger.warning(f"Summary too short for: {episode.title[:50]}")
                    continue
                
                # Extract first few sections (title + first 2-3 content sections)
                sections = summary_text.split('\n## ')
                if len(sections) >= 3:
                    # Get title and first 2 sections (more content for better summary)
                    content_to_use = sections[0] + '\n## ' + sections[1] + '\n## ' + sections[2]
                elif len(sections) >= 2:
                    content_to_use = sections[0] + '\n## ' + sections[1]
                else:
                    content_to_use = summary_text
                
                # Remove ALL headers and bullets to get actual content
                content_lines = []
                for line in content_to_use.split('\n'):
                    stripped = line.strip()
                    # Skip headers and bullet points
                    if stripped and not stripped.startswith('#') and not stripped.startswith('- '):
                        content_lines.append(stripped)
                
                content_text = ' '.join(content_lines)
                
                # Generate 3-sentence summary (get complete sentences)
                sentences = []
                for s in content_text.split('. '):
                    s = s.strip()
                    # Must be a real sentence: > 30 chars, ends logically
                    if s and len(s) > 30 and not s.endswith(':'):
                        sentences.append(s)
                
                # Join first 3 complete sentences
                if len(sentences) >= 3:
                    short_summary = '. '.join(sentences[:3]) + '.'
                else:
                    # Fallback: just truncate
                    short_summary = content_text[:500] + '...' if len(content_text) > 500 else content_text
                
                # Parse practical tips if available
                import json
                practical_tips_list = []
                if insight and insight.practical_tips:
                    try:
                        practical_tips_list = json.loads(insight.practical_tips)
                    except:
                        logger.warning(f"Could not parse practical_tips for: {episode.title[:50]}")
                
                summaries.append({
                    'episode_id': episode.id,
                    'title': episode.title,
                    'podcast_name': podcast_name,
                    'date': episode.published_date.strftime('%Y-%m-%d') if episode.published_date else 'Unknown',
                    'link': episode.item_url,
                    'summary': short_summary,
                    'full_summary': summary_text,
                    'practical_tips': practical_tips_list,
                    'transcript_length': episode.transcript_length or 0
                })
            
            return summaries
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting cached summaries: {e}")
        return []

async def get_ai_daily_brief_gap_analysis(
    tldr_stories: List[Dict[str, Any]], 
    perplexity_stories: List[Dict[str, Any]],
    yesterday_tldr_stories: List[Dict[str, Any]] = None,
    yesterday_perplexity_stories: List[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Get The AI Daily Brief and analyze what unique content it provides
    that's not covered by TLDR AI or Perplexity (today + yesterday).
    
    Args:
        tldr_stories: Today's TLDR AI stories
        perplexity_stories: Today's Perplexity stories  
        yesterday_tldr_stories: Yesterday's TLDR AI stories (optional)
        yesterday_perplexity_stories: Yesterday's Perplexity stories (optional)
        
    Returns:
        Optional[str]: Unique insights from AI Daily Brief, or None if no unique content
    """
    try:
        from ..services.assemblyai_processor import process_single_episode_with_assemblyai
        from ..ingestion.rss_parser import parse_podcast_feed
        from ..ingestion.sources import get_podcast_by_id
        from openai import AsyncOpenAI
        from ..config import settings
        
        # Get AI Daily Brief source
        ai_daily_brief_source = get_podcast_by_id('ai_daily_brief')
        if not ai_daily_brief_source:
            logger.warning("AI Daily Brief source not found")
            return None
            
        # Get today's AI Daily Brief episode
        episodes = await parse_podcast_feed(ai_daily_brief_source['rss_url'])
        if not episodes:
            logger.warning("No AI Daily Brief episodes found")
            return None
            
        # Get the most recent episode (today)
        latest_episode = episodes[0]
        
        # Transcribe the episode
        logger.info(f"🎙️ Transcribing AI Daily Brief: {latest_episode.get('title', 'Unknown')}")
        transcript = await process_single_episode_with_assemblyai(latest_episode, test_mode=False)
        
        if not transcript or not transcript.get('insights'):
            logger.warning("AI Daily Brief transcription failed")
            return None
            
        # Prepare existing content for comparison
        existing_content = []
        
        # Add today's content
        for story in tldr_stories:
            existing_content.append(f"TLDR AI: {story.get('title', '')} - {story.get('summary', '')[:200]}")
            
        for story in perplexity_stories:
            existing_content.append(f"Perplexity: {story.get('title', '')} - {story.get('summary', '')[:200]}")
            
        # Add yesterday's content if available
        if yesterday_tldr_stories:
            for story in yesterday_tldr_stories:
                existing_content.append(f"TLDR AI (Yesterday): {story.get('title', '')} - {story.get('summary', '')[:200]}")
                
        if yesterday_perplexity_stories:
            for story in yesterday_perplexity_stories:
                existing_content.append(f"Perplexity (Yesterday): {story.get('title', '')} - {story.get('summary', '')[:200]}")
        
        # Use AI to compare and extract unique insights
        openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        existing_content_text = "\n".join(existing_content)
        
        prompt = f"""
        You are analyzing The AI Daily Brief podcast to find unique insights not covered by existing sources.
        
        EXISTING CONTENT COVERED:
        {existing_content_text}
        
        AI DAILY BRIEF TRANSCRIPT:
        {transcript['insights']}
        
        TASK: Extract ONLY the topics, insights, or analysis from The AI Daily Brief that are NOT already covered in the existing content above.
        
        If The AI Daily Brief covers topics already mentioned in TLDR AI or Perplexity (today or yesterday), DO NOT include them.
        
        If The AI Daily Brief provides unique business analysis, market insights, or covers different stories, extract those.
        
        Format as a brief summary of unique insights. If there are no unique insights, return "NO_UNIQUE_CONTENT".
        
        Focus on:
        - Business implications not covered elsewhere
        - Market analysis not mentioned in other sources  
        - Different angles on the same stories
        - Completely new stories not covered by TLDR/Perplexity
        """
        
        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
            messages=[
                {"role": "system", "content": "You are an expert at analyzing content overlap and identifying unique insights."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        unique_insights = response.choices[0].message.content.strip()
        
        if unique_insights == "NO_UNIQUE_CONTENT":
            logger.info("AI Daily Brief has no unique content - skipping")
            return None
            
        logger.info(f"✅ AI Daily Brief provided unique insights: {len(unique_insights)} chars")
        return unique_insights
        
    except Exception as e:
        logger.error(f"Error in AI Daily Brief gap analysis: {e}")
        return None

# Create API router
router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    
    Returns:
        Dict[str, str]: Status message
    """
    return {
        "status": "healthy",
        "message": "Podcast Summarizer API is running",
        "version": "1.0.0"
    }


@router.get("/podcast/episode/{episode_id}/deep-dive")
async def get_episode_deep_dive(episode_id: int) -> Dict[str, Any]:
    """
    Get enriched deep-dive content for a podcast episode.
    
    Args:
        episode_id: Database ID of the content item
        
    Returns:
        Dict containing full summary, practical tips, enriched content, and transcript
    """
    try:
        from ..database.db import SessionLocal
        from ..database.models import ContentItem, Insight
        import json
        
        db = SessionLocal()
        try:
            # Get the content item
            episode = db.query(ContentItem).filter(
                ContentItem.id == episode_id
            ).first()
            
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found")
            
            # Get the most recent insight
            insight = db.query(Insight).filter(
                Insight.content_item_id == episode.id
            ).order_by(Insight.created_at.desc()).first()
            
            if not insight:
                raise HTTPException(status_code=404, detail="No insights found for this episode")
            
            # Determine podcast name
            podcast_name = episode.source_name or "Unknown Podcast"
            if podcast_name == "Unknown Podcast":
                url_lower = episode.item_url.lower() if episode.item_url else ""
                if 'lennysnewsletter.com' in url_lower:
                    podcast_name = "Lenny's Podcast"
                elif 'dataskeptic.com' in url_lower or 'dataskeptic.libsyn.com' in url_lower:
                    podcast_name = "Data Skeptic"
                elif 'megaphone.fm' in url_lower or 'datacamp' in url_lower:
                    podcast_name = "DataFramed by DataCamp"
                elif 'anchor.fm' in url_lower or 'spotify.com/pod/show/nlw' in url_lower:
                    podcast_name = "The AI Daily Brief"
            
            # Parse practical tips JSON
            practical_tips_list = []
            if insight.practical_tips:
                try:
                    practical_tips_list = json.loads(insight.practical_tips)
                except:
                    logger.warning(f"Could not parse practical_tips JSON for episode {episode_id}")
            
            return {
                "episode_id": episode.id,
                "title": episode.title,
                "podcast_name": podcast_name,
                "published_date": episode.published_date.strftime('%Y-%m-%d') if episode.published_date else 'Unknown',
                "episode_url": episode.item_url,
                "full_summary": insight.insight_text,
                "practical_tips": practical_tips_list,
                "enriched_content": insight.enriched_content or "No enriched content available yet.",
                "transcript": episode.transcript,
                "transcript_length": episode.transcript_length or 0
            }
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deep-dive content: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving deep-dive content: {str(e)}")


@router.get("/podcasts")
async def get_podcasts() -> Dict[str, Any]:
    """
    Get all configured podcast sources.
    
    Returns:
        Dict[str, Any]: Dictionary containing all podcast configurations
    """
    try:
        podcasts = get_all_podcast_sources()
        return {
            "count": len(podcasts),
            "podcasts": podcasts
        }
    except Exception as e:
        logger.error(f"Error fetching podcasts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch podcasts")


@router.post("/podcasts/cache-transcripts")
async def cache_podcast_transcripts(
    episodes_per_podcast: int = 3,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Cache transcripts for the last N episodes of each podcast.
    This is a one-time expensive operation that stores full transcripts in the database.
    
    Args:
        episodes_per_podcast: Number of recent episodes to cache per podcast (default: 3)
        force_refresh: Force re-transcription even if cached (default: False)
        
    Returns:
        Dict with status of transcription caching
    """
    try:
        from ..services.assemblyai_processor import cache_all_podcast_transcripts
        
        logger.info(f"🎙️  Starting transcript caching: {episodes_per_podcast} episodes per podcast")
        
        result = await cache_all_podcast_transcripts(
            episodes_per_podcast=episodes_per_podcast,
            force_refresh=force_refresh
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error caching transcripts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/podcasts/{podcast_id}")
async def get_podcast(podcast_id: str) -> Dict[str, Any]:
    """
    Get a specific podcast by ID.
    
    Args:
        podcast_id: The unique identifier for the podcast
        
    Returns:
        Dict[str, Any]: Podcast configuration
        
    Raises:
        HTTPException: If podcast not found
    """
    podcast = get_podcast_by_id(podcast_id)
    if not podcast:
        raise HTTPException(status_code=404, detail=f"Podcast '{podcast_id}' not found")
    
    return {
        "podcast_id": podcast_id,
        **podcast
    }


@router.get("/episodes")
async def get_all_episodes(limit: int = 5) -> Dict[str, Any]:
    """
    Get recent episodes from all configured podcasts.
    
    Args:
        limit: Maximum number of episodes per podcast (default: 5)
        
    Returns:
        Dict[str, Any]: Dictionary containing episodes grouped by podcast
    """
    try:
        podcasts = get_all_podcast_sources()
        feed_urls = [podcast["rss_url"] for podcast in podcasts.values()]
        
        # Fetch all feeds
        feed_results = await fetch_all_feeds(feed_urls)
        
        # Organize results by podcast name
        episodes_by_podcast = {}
        for podcast_id, podcast_data in podcasts.items():
            rss_url = podcast_data["rss_url"]
            if rss_url in feed_results:
                episodes_by_podcast[podcast_id] = {
                    "podcast_name": podcast_data["name"],
                    "category": podcast_data["category"],
                    "episodes": feed_results[rss_url][:limit]
                }
        
        return {
            "total_podcasts": len(episodes_by_podcast),
            "episodes": episodes_by_podcast
        }
    
    except Exception as e:
        logger.error(f"Error fetching episodes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch episodes: {str(e)}")


@router.get("/episodes/with-insights")
async def get_episodes_with_insights(
    podcast_name: str, 
    max_episodes: int = 3,
    include_transcripts: bool = False,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Fetch episodes with YouTube transcripts and extract key insights.
    
    Args:
        podcast_name: Name of the podcast (e.g., "lennys_podcast", "mlops_community", "twiml_ai")
        max_episodes: Maximum number of episodes to process (default: 3)
        include_transcripts: Whether to include full transcript text in response (default: False)
        test_mode: If True, truncates transcripts to ~5000 chars for quick testing (default: False)
        
    Returns:
        Dict[str, Any]: Episodes with transcripts and extracted insights
    """
    podcast = get_podcast_by_id(podcast_name)
    if not podcast:
        raise HTTPException(status_code=404, detail=f"Podcast '{podcast_name}' not found")
    
    try:
        logger.info(f"🎙️  Starting insight extraction for: {podcast['name']}")
        logger.info(f"📊 Fetching {max_episodes} episode(s) from RSS feed...")
        
        # Fetch RSS feed with transcripts
        youtube_channel = podcast.get("youtube_channel")
        episodes = await parse_podcast_feed(
            podcast["rss_url"],
            max_episodes=max_episodes,
            fetch_transcripts=True,
            youtube_channel=youtube_channel
        )
        
        logger.info(f"✅ Found {len(episodes)} episode(s)")
        
        # Process all episodes in parallel using service layer
        episodes_with_insights = await process_episodes_parallel(
            episodes,
            podcast_name=podcast["name"],
            use_transcripts=True,
            test_mode=test_mode,
            include_transcripts=include_transcripts
        )
        
        return {
            "podcast_id": podcast_name,
            "podcast_name": podcast["name"],
            "episode_count": len(episodes_with_insights),
            "episodes": episodes_with_insights
        }
    
    except Exception as e:
        logger.error(f"Error processing episodes with insights: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process episodes: {str(e)}")


@router.get("/episodes/{podcast_id}")
async def get_podcast_episodes(podcast_id: str, limit: int = 5) -> Dict[str, Any]:
    """
    Get recent episodes from a specific podcast.
    
    Args:
        podcast_id: The unique identifier for the podcast
        limit: Maximum number of episodes to return (default: 5)
        
    Returns:
        Dict[str, Any]: Dictionary containing podcast info and episodes
        
    Raises:
        HTTPException: If podcast not found or feed parsing fails
    """
    podcast = get_podcast_by_id(podcast_id)
    if not podcast:
        raise HTTPException(status_code=404, detail=f"Podcast '{podcast_id}' not found")
    
    try:
        # Pass YouTube channel for search if YouTube URL not in RSS
        youtube_channel = podcast.get("youtube_channel")
        episodes = await parse_podcast_feed(
            podcast["rss_url"], 
            max_episodes=limit,
            youtube_channel=youtube_channel
        )
        
        return {
            "podcast_id": podcast_id,
            "podcast_name": podcast["name"],
            "category": podcast["category"],
            "episode_count": len(episodes),
            "episodes": episodes
        }
    
    except Exception as e:
        logger.error(f"Error fetching episodes for {podcast_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch episodes from {podcast['name']}: {str(e)}"
        )


@router.get("/summarize/{podcast_id}/{episode_index}")
async def summarize_podcast_episode(podcast_id: str, episode_index: int = 0) -> Dict[str, Any]:
    """
    Summarize a specific episode from a podcast using AI.
    
    Args:
        podcast_id: The unique identifier for the podcast
        episode_index: Index of the episode (0 = most recent)
        
    Returns:
        Dict[str, Any]: Episode with AI-generated summary
    """
    podcast = get_podcast_by_id(podcast_id)
    if not podcast:
        raise HTTPException(status_code=404, detail=f"Podcast '{podcast_id}' not found")
    
    try:
        # Fetch episodes
        episodes = await parse_podcast_feed(podcast["rss_url"], max_episodes=episode_index + 1)
        
        if episode_index >= len(episodes):
            raise HTTPException(
                status_code=404,
                detail=f"Episode index {episode_index} not found (only {len(episodes)} episodes available)"
            )
        
        episode = episodes[episode_index]
        
        # Generate summary using the configured method
        method = podcast.get("method", "summarize_description")
        summary = await summarize_episode(episode, method=method)
        
        return {
            "podcast_id": podcast_id,
            "podcast_name": podcast["name"],
            "episode": {
                **episode,
                "summary": summary
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing episode: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to summarize episode: {str(e)}")


@router.get("/podcasts")
async def get_podcasts() -> Dict[str, Any]:
    """Get all configured podcasts."""
    try:
        podcasts = get_all_podcasts()
        return {"podcasts": podcasts, "total": len(podcasts)}
    except Exception as e:
        logger.error(f"Error fetching podcasts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch podcasts: {str(e)}")


@router.get("/podcasts/{podcast_id}")
async def get_podcast(podcast_id: str) -> Dict[str, Any]:
    """Get a specific podcast by ID."""
    try:
        podcast = get_podcast_by_id(podcast_id)
        if not podcast:
            raise HTTPException(status_code=404, detail=f"Podcast '{podcast_id}' not found")
        
        episodes = get_recent_episodes(podcast_id, limit=5)
        return {
            "podcast": podcast,
            "recent_episodes": episodes,
            "episode_count": len(episodes)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching podcast {podcast_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch podcast: {str(e)}")


@router.get("/episodes")
async def get_all_episodes(limit: int = 50) -> Dict[str, Any]:
    """Get all episodes across all podcasts."""
    try:
        all_episodes = []
        podcasts = get_all_podcasts()
        
        for podcast in podcasts:
            episodes = get_recent_episodes(podcast['id'], limit=limit)
            for episode in episodes:
                episode['podcast_name'] = podcast['name']
                episode['podcast_id'] = podcast['id']
            all_episodes.extend(episodes)
        
        # Sort by publication date (most recent first)
        all_episodes.sort(key=lambda x: x.get('pub_date', ''), reverse=True)
        
        return {
            "episodes": all_episodes[:limit],
            "total": len(all_episodes),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error fetching episodes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch episodes: {str(e)}")


@router.get("/episodes/{podcast_id}")
async def get_podcast_episodes(podcast_id: str, limit: int = 10) -> Dict[str, Any]:
    """Get episodes for a specific podcast."""
    try:
        podcast = get_podcast_by_id(podcast_id)
        if not podcast:
            raise HTTPException(status_code=404, detail=f"Podcast '{podcast_id}' not found")
        
        episodes = get_recent_episodes(podcast_id, limit=limit)
        
        return {
            "podcast": podcast,
            "episodes": episodes,
            "total": len(episodes),
            "limit": limit
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching episodes for {podcast_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch episodes: {str(e)}")


# Old briefing endpoint removed - use /morning-briefing instead


@router.get("/test-transcript")
async def test_transcript_fetching() -> Dict[str, Any]:
    """
    Test endpoint to verify YouTube transcript fetching works.
    Fetches ONE episode from Lenny's Podcast and returns first 1000 chars of transcript.
    
    Returns:
        Dict[str, Any]: Test results with transcript preview
    """
    try:
        podcast = get_podcast_by_id("lennys_podcast")
        if not podcast:
            raise HTTPException(status_code=404, detail="Lenny's Podcast configuration not found")
        
        # Fetch first episode with transcript
        youtube_channel = podcast.get("youtube_channel")
        episodes = await parse_podcast_feed(
            podcast["rss_url"],
            max_episodes=1,
            fetch_transcripts=True,
            youtube_channel=youtube_channel
        )
        
        if not episodes:
            raise HTTPException(status_code=404, detail="No episodes found")
        
        episode = episodes[0]
        transcript = episode.get("transcript")
        
        if not transcript:
            return {
                "status": "failed",
                "message": "No transcript found for this episode",
                "episode_title": episode.get("title"),
                "youtube_url": episode.get("youtube_url"),
                "transcript_preview": None
            }
        
        # Return first 1000 characters as preview
        transcript_preview = transcript[:1000] + "..." if len(transcript) > 1000 else transcript
        
        return {
            "status": "success",
            "message": "Transcript fetched successfully",
            "episode_title": episode.get("title"),
            "youtube_url": episode.get("youtube_url"),
            "transcript_length": len(transcript),
            "transcript_preview": transcript_preview
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test transcript error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


# Old generic news endpoint removed - use /morning-briefing or specific endpoints instead


@router.get("/news/category/{category_key}")
async def get_news_by_category(
    category_key: str,
    date: str = None
) -> Dict[str, Any]:
    """
    Get news for a specific category.
    
    Args:
        category_key: Category identifier (ai_news, economic_news, political_news, general_interest)
        date: Optional date in YYYY-MM-DD format (default: today)
        
    Returns:
        Dict[str, Any]: News stories for the specified category
    """
    from ..ingestion.news_search import search_news_with_openai, NEWS_CATEGORIES
    
    try:
        if category_key not in NEWS_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Options: {', '.join(NEWS_CATEGORIES.keys())}"
            )
        
        logger.info(f"📰 Fetching {category_key} news...")
        
        result = await search_news_with_openai(category_key, date)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching category news: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch category news: {str(e)}")


@router.get("/search/evaluate")
async def search_evaluate(
    query: Optional[str] = None,
    providers: str = "perplexity,exa",
    exa_modes: str = "search,research",
    limit: int = 3,
) -> Dict[str, Any]:
    """
    Evaluate search providers/modes with minimal scoring (relevance + recency).

    Args:
        query: Optional free-text query. If omitted, providers use defaults.
        providers: CSV of providers to run (perplexity, exa).
        exa_modes: CSV of Exa modes (search, research, find_similar).
        limit: Max results per provider/mode.
        seed_urls: Optional CSV of seed URLs for Exa find_similar.

    Returns:
        JSON with per-provider/mode results and a combined ranked list.
    """
    logger.info(f"🎯 /api/search/evaluate called: providers={providers}, exa_modes={exa_modes}, limit={limit}")
    try:
        provider_list = [p.strip() for p in providers.split(",") if p.strip()]
        exa_mode_list = [m.strip() for m in exa_modes.split(",") if m.strip()]
        logger.info(f"🎯 Calling evaluate_search with provider_list={provider_list}, exa_mode_list={exa_mode_list}")
        result = await evaluate_search(
            query=query,
            providers=provider_list,
            limit=limit,
            exa_modes=exa_mode_list,
            seed_urls=None,
        )
        logger.info(f"🎯 evaluate_search returned: {len(result)} keys")
        return result
    except Exception as e:
        logger.error(f"Search evaluate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/search/agent")
async def search_with_comprehensive_agent(
    max_iterations: int = 2
) -> Dict[str, Any]:
    """
    Run adaptive multi-search agent with LLM evaluation for comprehensive AI PM news coverage.
    
    The agent:
    1. Performs initial searches (7 detailed queries) using Exa search_and_contents()
    2. Evaluates each article with LLM (relevance, recency, clarity scores)
    3. Identifies coverage gaps and generates follow-up searches
    4. Iterates 2-3 times until sufficient high-quality articles are collected
    
    This ensures comprehensive topic coverage with quality filtering.
    
    Args:
        max_iterations: Maximum rounds of follow-up searches (default: 2)
    
    Returns:
        JSON with kept articles, evaluation stats, and iteration metadata
    """
    try:
        logger.info(f"🤖 Starting search orchestrator with max_iterations={max_iterations}")
        
        # Run orchestrator with all 3 specialist agents
        orchestrator_results = await search_all_categories(
            max_iterations=max_iterations,
            use_cache=True
        )
        
        # Flatten results for backward compatibility
        kept_articles = flatten_results(orchestrator_results)
        
        logger.info(f"✅ Orchestrator complete: {len(kept_articles)} total articles")
        logger.info(f"   Conversational AI: {orchestrator_results['by_category_count']['conversational_ai']}")
        logger.info(f"   General AI: {orchestrator_results['by_category_count']['general_ai']}")
        logger.info(f"   Research/Opinion: {orchestrator_results['by_category_count']['research_opinion']}")
        
        return {
            "kept_articles": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "summary": r.summary,
                    "source": r.source,
                    "published_date": r.published_date,
                    "provider": r.provider,
                }
                for r in kept_articles
            ],
            "total_kept": len(kept_articles),
            "by_category": orchestrator_results["by_category_count"],
            "categories": {
                "conversational_ai": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "summary": r.summary,
                    }
                    for r in orchestrator_results["conversational_ai"]
                ],
                "general_ai": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "summary": r.summary,
                    }
                    for r in orchestrator_results["general_ai"]
                ],
                "research_opinion": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "summary": r.summary,
                    }
                    for r in orchestrator_results["research_opinion"]
                ],
            },
            "message": f"Completed with {len(kept_articles)} high-quality articles across 3 categories"
        }
    except Exception as e:
        logger.error(f"Agent search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/agents")
async def get_news_with_agents(
    categories: str = "ai_news",
    date: str = None
) -> Dict[str, Any]:
    """
    Get news using AI Agents (OpenAI Assistants).
    Agents can browse and search for real news from the past 24 hours.
    
    NOTE: This uses OpenAI Assistants API which may have additional costs.
    DISABLED: news_agent module not available
    
    Args:
        categories: Comma-separated list of categories (default: just ai_news)
        date: Optional date in YYYY-MM-DD format (default: today)
        
    Returns:
        Dict[str, Any]: News stories found by agents
    """
    raise HTTPException(
        status_code=501,
        detail="AI Agents endpoint is currently disabled (news_agent module not available)"
    )
    # DISABLED: news_agent module not available
    # try:
    #     # Parse categories
    #     category_list = [c.strip() for c in categories.split(",")]
    #     
    #     # Filter to valid categories
    #     valid_categories = {
    #         k: v for k, v in NEWS_CATEGORIES.items()
    #         if k in category_list
    #     }
    #     
    #     if not valid_categories:
    #         raise HTTPException(
    #             status_code=400,
    #             detail=f"No valid categories. Options: {', '.join(NEWS_CATEGORIES.keys())}"
    #         )
    #     
    #     logger.info(f"🤖 Starting agent-based search for: {list(valid_categories.keys())}")
    #     
    #     # Use agents to search
    #     news_data = await search_all_categories_with_agents(
    #         categories=valid_categories,
    #         date=date
    #     )
    #     
    #     # Generate briefing if we have stories
    #     if news_data.get('total_stories', 0) > 0:
    #         briefing_text = await generate_news_briefing(news_data)
    #     else:
    #         briefing_text = "No news found by agents."
    #     
    #     return {
    #         "date": news_data.get('date'),
    #         "total_categories": news_data.get('total_categories'),
    #         "total_stories": news_data.get('total_stories'),
    #         "news_by_category": news_data.get('news_by_category'),
    #         "briefing": briefing_text,
    #         "errors": news_data.get('errors', []),
    #         "method": "ai_agents"
    #     }
    #     
    # except HTTPException:
    #     raise
    # except Exception as e:
    #     logger.error(f"Error with agent news search: {str(e)}")
    #     raise HTTPException(status_code=500, detail=f"Agent search failed: {str(e)}")


@router.get("/news/tavily")
async def get_news_with_tavily(
    categories: str = "ai_news",
    date: str = None
) -> Dict[str, Any]:
    """
    Get news using Tavily AI Search API - fast and optimized for AI.
    
    Get free API key at: https://tavily.com
    Cost: $0 for 1000 searches/month free tier
    DISABLED: news_tavily module not available
    
    Args:
        categories: Comma-separated list (default: ai_news)
        date: Optional date YYYY-MM-DD
        
    Returns:
        News from past 24 hours with real URLs
    """
    raise HTTPException(
        status_code=501,
        detail="Tavily endpoint is currently disabled (news_tavily module not available)"
    )
    # DISABLED: news_tavily module not available
    # try:
    #     category_list = [c.strip() for c in categories.split(",")]
    #     valid_categories = {
    #         k: v for k, v in NEWS_CATEGORIES.items()
    #         if k in category_list
    #     }
    #     
    #     if not valid_categories:
    #         raise HTTPException(status_code=400, detail="No valid categories")
    #     
    #     logger.info(f"🔍 Tavily search for: {list(valid_categories.keys())}")
    #     
    #     news_data = await search_all_categories_with_tavily(valid_categories, date)
    #     
    #     if news_data.get('total_stories', 0) > 0:
    #         briefing_text = await generate_news_briefing(news_data)
    #     else:
    #         briefing_text = "No news found."
    #     
    #     return {
    #         **news_data,
    #         "briefing": briefing_text
    #     }
    #     
    # except Exception as e:
    #     logger.error(f"Tavily error: {e}")
    #     raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/perplexity")
async def get_news_with_perplexity(
    categories: str = "ai_news",
    date: str = None
) -> Dict[str, Any]:
    """
    Get news using Perplexity AI API - real-time search with citations.
    
    Get API key at: https://perplexity.ai
    Cost: Pay per request, excellent quality
    
    Args:
        categories: Comma-separated list (default: ai_news)
        date: Optional date YYYY-MM-DD
        
    Returns:
        News from past 24 hours with citations
    """
    try:
        category_list = [c.strip() for c in categories.split(",")]
        valid_categories = {
            k: v for k, v in NEWS_CATEGORIES.items()
            if k in category_list
        }
        
        if not valid_categories:
            raise HTTPException(status_code=400, detail="No valid categories")
        
        logger.info(f"🔮 Perplexity search for: {list(valid_categories.keys())}")
        
        news_data = await search_all_categories_with_perplexity(valid_categories, date)
        
        if news_data.get('total_stories', 0) > 0:
            briefing_text = await generate_news_briefing(news_data)
        else:
            briefing_text = "No news found."
        
        return {
            **news_data,
            "briefing": briefing_text
        }
        
    except Exception as e:
        logger.error(f"Perplexity error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/gmail")
async def get_news_from_gmail(
    hours_ago: int = 24,
    max_stories: int = 10,
    generate_briefing: bool = True
) -> Dict[str, Any]:
    """
    Get AI-enriched news from Gmail newsletters (TLDR AI, etc.)
    
    This endpoint:
    1. Fetches newsletters from Gmail
    2. Extracts article URLs
    3. Uses AI to read and summarize each article with PM focus
    4. Generates a cohesive morning briefing
    
    First-time setup:
    1. Go to https://console.cloud.google.com/apis/credentials
    2. Create OAuth 2.0 Client ID for Desktop app
    3. Download as 'gmail_credentials.json' and place in project root
    4. Run this endpoint - it will open browser for authentication
    5. After auth, token saved for future use
    
    Args:
        hours_ago: How far back to search (default: 24)
        max_stories: Max stories to process with AI (default: 10)
        generate_briefing: Generate cohesive briefing narrative (default: True)
        
    Returns:
        AI-enriched newsletter stories with summaries, takeaways, and briefing
    """
    try:
        logger.info(f"📧 Fetching newsletters from Gmail (past {hours_ago} hours)...")
        
        # Get newsletters
        newsletters = await get_all_newsletters(hours_ago)
        
        if newsletters.get('total_stories', 0) == 0:
            return newsletters
        
        # Collect all stories from all newsletters
        all_stories = []
        for newsletter_data in newsletters.get('newsletters', {}).values():
            all_stories.extend(newsletter_data.get('stories', []))
        
        logger.info(f"📰 Found {len(all_stories)} total stories")
        
        # Enrich stories with AI summaries
        enriched_stories = await enrich_stories_with_ai(all_stories, max_stories)
        
        # Generate briefing narrative
        briefing_text = ""
        if generate_briefing:
            briefing_text = await generate_ai_pm_briefing(enriched_stories)
        
        return {
            **newsletters,
            'enriched_stories': enriched_stories,
            'briefing': briefing_text,
            'stories_processed': len(enriched_stories)
        }
        
    except Exception as e:
        logger.error(f"Gmail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/gmail/{newsletter_key}")
async def get_specific_newsletter(
    newsletter_key: str,
    hours_ago: int = 24
) -> Dict[str, Any]:
    """
    Get stories from a specific newsletter.
    
    Available newsletters:
    - tldr_ai: TLDR AI newsletter
    - morning_brew: Morning Brew
    
    Args:
        newsletter_key: Newsletter identifier
        hours_ago: How far back to search
        
    Returns:
        Stories from the specified newsletter
    """
    try:
        logger.info(f"📧 Fetching {newsletter_key} from Gmail...")
        
        result = await get_newsletter_stories(newsletter_key, hours_ago)
        
        return result
        
    except Exception as e:
        logger.error(f"Gmail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/news/combined")
async def get_combined_news(
    use_gmail: bool = True,
    use_perplexity: bool = True,
    categories: str = "ai_news",
    hours_ago: int = 24
) -> Dict[str, Any]:
    """
    Get news from multiple sources combined:
    - Gmail newsletters (curated)
    - Perplexity API (real-time search)
    
    Best of both worlds: trusted curation + breaking news
    
    Args:
        use_gmail: Include Gmail newsletters
        use_perplexity: Include Perplexity search
        categories: Categories for Perplexity
        hours_ago: How far back for Gmail
        
    Returns:
        Combined news from all sources
    """
    try:
        combined = {
            'date': datetime.now().strftime("%Y-%m-%d"),
            'sources': [],
            'all_stories': []
        }
        
        # Get Gmail newsletters
        if use_gmail:
            try:
                logger.info("📧 Fetching Gmail newsletters...")
                gmail_data = await get_all_newsletters(hours_ago)
                
                if gmail_data.get('total_stories', 0) > 0:
                    combined['gmail'] = gmail_data
                    combined['sources'].append('gmail')
                    
                    # Extract all stories
                    for newsletter in gmail_data.get('newsletters', {}).values():
                        for story in newsletter.get('stories', []):
                            combined['all_stories'].append({
                                **story,
                                'source_type': 'newsletter',
                                'newsletter': newsletter.get('newsletter')
                            })
            except Exception as e:
                logger.warning(f"⚠️  Gmail failed: {e}")
                combined['gmail_error'] = str(e)
        
        # Get Perplexity news
        if use_perplexity:
            try:
                logger.info("🔮 Fetching Perplexity news...")
                from ..ingestion.news_search import NEWS_CATEGORIES
                
                category_list = [c.strip() for c in categories.split(",")]
                valid_categories = {
                    k: v for k, v in NEWS_CATEGORIES.items()
                    if k in category_list
                }
                
                perplexity_data = await search_all_categories_with_perplexity(valid_categories)
                
                if perplexity_data.get('total_stories', 0) > 0:
                    combined['perplexity'] = perplexity_data
                    combined['sources'].append('perplexity')
                    
                    # Extract all stories
                    for cat_data in perplexity_data.get('news_by_category', {}).values():
                        for story in cat_data.get('stories', []):
                            combined['all_stories'].append({
                                **story,
                                'source_type': 'perplexity',
                                'category': cat_data.get('category_name')
                            })
            except Exception as e:
                logger.warning(f"⚠️  Perplexity failed: {e}")
                combined['perplexity_error'] = str(e)
        
        # Generate unified AI PM insights
        if combined['all_stories']:
            logger.info("🤖 Generating unified AI PM insights...")
            # TODO: Create unified insights across all sources
            pass
        
        combined['total_stories'] = len(combined['all_stories'])
        
        return combined
        
    except Exception as e:
        logger.error(f"Combined news error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_podcasts_from_cache(
    episodes_per_podcast: int = 1,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process podcasts using cached transcripts for fast summarization.
    
    Args:
        episodes_per_podcast: Number of episodes per podcast to process
        force_refresh: Force fresh summarization (ignore cached summaries)
        
    Returns:
        Dict with podcast processing results
    """
    try:
        from ..database.db import SessionLocal
        from ..database.models import ContentItem, Insight
        from ..ingestion.assemblyai_transcriber import AssemblyAITranscriber
        from ..ingestion.sources import get_all_podcast_sources
        
        logger.info(f"🎙️  Processing podcasts from cache: {episodes_per_podcast} episodes per podcast")
        
        # Get all podcast sources
        podcast_sources = get_all_podcast_sources()
        transcriber = AssemblyAITranscriber()
        
        episodes_by_podcast = {}
        total_episodes = 0
        
        # Get all cached transcripts (most recent first)
        db = SessionLocal()
        try:
            all_cached_episodes = db.query(ContentItem).filter(
                ContentItem.source_type == 'assemblyai_transcript'
            ).order_by(ContentItem.published_date.desc()).all()
            
            logger.info(f"📊 Found {len(all_cached_episodes)} total cached transcripts")
            
            # Distribute episodes by podcast (take most recent per podcast)
            for podcast_id, podcast_info in podcast_sources.items():
                podcast_name = podcast_info['name']
                logger.info(f"📡 Processing {podcast_name}...")
                
                # Get episodes for this podcast (by URL pattern matching)
                podcast_episodes = []
                episodes_taken = 0
                
                for content_item in all_cached_episodes:
                    if episodes_taken >= episodes_per_podcast:
                        break
                    
                    # Simple URL pattern matching to assign episodes to podcasts
                    url = content_item.item_url.lower()
                    if podcast_id == 'lennys_podcast' and 'lennysnewsletter.com' in url:
                        episode_data = {
                            'episode_id': content_item.id,
                            'title': content_item.title,
                            'pub_date': content_item.published_date.strftime('%Y-%m-%d') if content_item.published_date else 'Unknown',
                            'link': content_item.item_url,
                            'podcast_name': podcast_name,
                            'transcript_length': content_item.transcript_length or 0
                        }
                        
                        # Get cached insights directly from ContentItem ID (scalable approach)
                        cached_insights = transcriber.get_insights_from_content_item(content_item.id)
                        
                        if cached_insights and not force_refresh:
                            # Use cached insights (summary, tips, enriched content)
                            episode_data['insights'] = cached_insights['insight_text']
                            episode_data['practical_tips'] = cached_insights.get('practical_tips', [])
                            episode_data['enriched_content'] = cached_insights.get('enriched_content')
                            episode_data['source'] = 'assemblyai_cache'
                            logger.info(f"   ✅ Using cached insights: {content_item.title[:50]}")
                        elif content_item.transcript and not force_refresh:
                            # Generate new summary from cached transcript
                            logger.info(f"   🤖 Generating summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                            else:
                                episode_data['insights'] = "Summary generation failed"
                                episode_data['source'] = 'assemblyai_error'
                        elif force_refresh and content_item.transcript:
                            # Force fresh summary
                            logger.info(f"   🔄 Force refreshing summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                            else:
                                episode_data['insights'] = "Summary generation failed"
                                episode_data['source'] = 'assemblyai_error'
                        else:
                            # No transcript, no cached insights
                            episode_data['insights'] = None
                            episode_data['practical_tips'] = []
                            episode_data['enriched_content'] = None
                            episode_data['source'] = 'no_transcript'
                        
                        podcast_episodes.append(episode_data)
                        episodes_taken += 1
                        total_episodes += 1
                        
                    elif podcast_id == 'mlops_community' and 'spotify.com/pod/show/mlops' in url:
                        episode_data = {
                            'title': content_item.title,
                            'pub_date': content_item.published_date.strftime('%Y-%m-%d') if content_item.published_date else 'Unknown',
                            'link': content_item.item_url,
                            'podcast_name': podcast_name,
                            'transcript_length': content_item.transcript_length or 0
                        }
                        
                        # Get cached insights directly from ContentItem ID (scalable approach)
                        cached_insights = transcriber.get_insights_from_content_item(content_item.id)
                        
                        if cached_insights and not force_refresh:
                            # Use cached insights (summary, tips, enriched content)
                            episode_data['insights'] = cached_insights['insight_text']
                            episode_data['practical_tips'] = cached_insights.get('practical_tips', [])
                            episode_data['enriched_content'] = cached_insights.get('enriched_content')
                            episode_data['source'] = 'assemblyai_cache'
                            logger.info(f"   ✅ Using cached insights: {content_item.title[:50]}")
                        elif content_item.transcript and not force_refresh:
                            # Generate new summary from cached transcript
                            logger.info(f"   🤖 Generating summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                            else:
                                episode_data['insights'] = "Summary generation failed"
                                episode_data['source'] = 'assemblyai_error'
                        elif force_refresh and content_item.transcript:
                            # Force fresh summary
                            logger.info(f"   🔄 Force refreshing summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                            else:
                                episode_data['insights'] = "Summary generation failed"
                                episode_data['source'] = 'assemblyai_error'
                        else:
                            # No transcript, no cached insights
                            episode_data['insights'] = None
                            episode_data['practical_tips'] = []
                            episode_data['enriched_content'] = None
                            episode_data['source'] = 'no_transcript'
                        
                        podcast_episodes.append(episode_data)
                        episodes_taken += 1
                        total_episodes += 1
                        
                    elif podcast_id == 'twiml_ai' and 'twimlai.com' in url:
                        episode_data = {
                            'title': content_item.title,
                            'pub_date': content_item.published_date.strftime('%Y-%m-%d') if content_item.published_date else 'Unknown',
                            'link': content_item.item_url,
                            'podcast_name': podcast_name,
                            'transcript_length': content_item.transcript_length or 0
                        }
                        
                        # Get cached insights directly from ContentItem ID (scalable approach)
                        cached_insights = transcriber.get_insights_from_content_item(content_item.id)
                        
                        if cached_insights and not force_refresh:
                            # Use cached insights (summary, tips, enriched content)
                            episode_data['insights'] = cached_insights['insight_text']
                            episode_data['practical_tips'] = cached_insights.get('practical_tips', [])
                            episode_data['enriched_content'] = cached_insights.get('enriched_content')
                            episode_data['source'] = 'assemblyai_cache'
                            logger.info(f"   ✅ Using cached insights: {content_item.title[:50]}")
                        elif content_item.transcript and not force_refresh:
                            # Generate new summary from cached transcript
                            logger.info(f"   🤖 Generating summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                            else:
                                episode_data['insights'] = "Summary generation failed"
                                episode_data['source'] = 'assemblyai_error'
                        elif force_refresh and content_item.transcript:
                            # Force fresh summary
                            logger.info(f"   🔄 Force refreshing summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                            else:
                                episode_data['insights'] = "Summary generation failed"
                                episode_data['source'] = 'assemblyai_error'
                        else:
                            # No transcript, no cached insights
                            episode_data['insights'] = None
                            episode_data['practical_tips'] = []
                            episode_data['enriched_content'] = None
                            episode_data['source'] = 'no_transcript'
                        
                        podcast_episodes.append(episode_data)
                        episodes_taken += 1
                        total_episodes += 1
                        
                    elif podcast_id == 'ai_daily_brief' and ('anchor.fm' in url or 'f7cac464' in url or ('spotify.com/pod/show/' in url and 'ai' in content_item.title.lower())):
                        episode_data = {
                            'title': content_item.title,
                            'pub_date': content_item.published_date.strftime('%Y-%m-%d') if content_item.published_date else 'Unknown',
                            'link': content_item.item_url,
                            'podcast_name': podcast_name,
                            'transcript_length': content_item.transcript_length or 0
                        }
                        
                        cached_insights = transcriber.get_insights_from_content_item(content_item.id)
                        
                        if cached_insights and not force_refresh:
                            episode_data['insights'] = cached_insights['insight_text']
                            episode_data['practical_tips'] = cached_insights.get('practical_tips', [])
                            episode_data['enriched_content'] = cached_insights.get('enriched_content')
                            episode_data['source'] = 'assemblyai_cache'
                            logger.info(f"   ✅ Using cached insights: {content_item.title[:50]}")
                        elif content_item.transcript:
                            logger.info(f"   🤖 Generating summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                        
                        podcast_episodes.append(episode_data)
                        episodes_taken += 1
                        total_episodes += 1
                        
                    elif podcast_id == 'data_skeptic' and 'dataskeptic' in url:
                        episode_data = {
                            'title': content_item.title,
                            'pub_date': content_item.published_date.strftime('%Y-%m-%d') if content_item.published_date else 'Unknown',
                            'link': content_item.item_url,
                            'podcast_name': podcast_name,
                            'transcript_length': content_item.transcript_length or 0
                        }
                        
                        cached_insights = transcriber.get_insights_from_content_item(content_item.id)
                        
                        if cached_insights and not force_refresh:
                            episode_data['insights'] = cached_insights['insight_text']
                            episode_data['practical_tips'] = cached_insights.get('practical_tips', [])
                            episode_data['enriched_content'] = cached_insights.get('enriched_content')
                            episode_data['source'] = 'assemblyai_cache'
                            logger.info(f"   ✅ Using cached insights: {content_item.title[:50]}")
                        elif content_item.transcript:
                            logger.info(f"   🤖 Generating summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                        
                        podcast_episodes.append(episode_data)
                        episodes_taken += 1
                        total_episodes += 1
                        
                    elif podcast_id == 'dataframed' and 'datacamp' in url:
                        episode_data = {
                            'title': content_item.title,
                            'pub_date': content_item.published_date.strftime('%Y-%m-%d') if content_item.published_date else 'Unknown',
                            'link': content_item.item_url,
                            'podcast_name': podcast_name,
                            'transcript_length': content_item.transcript_length or 0
                        }
                        
                        cached_insights = transcriber.get_insights_from_content_item(content_item.id)
                        
                        if cached_insights and not force_refresh:
                            episode_data['insights'] = cached_insights['insight_text']
                            episode_data['practical_tips'] = cached_insights.get('practical_tips', [])
                            episode_data['enriched_content'] = cached_insights.get('enriched_content')
                            episode_data['source'] = 'assemblyai_cache'
                            logger.info(f"   ✅ Using cached insights: {content_item.title[:50]}")
                        elif content_item.transcript:
                            logger.info(f"   🤖 Generating summary: {content_item.title[:50]}")
                            summary = await transcriber.get_transcript_summary(
                                content_item.transcript,
                                content_item.title,
                                content_item.item_url
                            )
                            if summary:
                                episode_data['insights'] = summary
                                episode_data['practical_tips'] = []
                                episode_data['enriched_content'] = None
                                episode_data['source'] = 'assemblyai_transcript'
                        
                        podcast_episodes.append(episode_data)
                        episodes_taken += 1
                        total_episodes += 1
                
                episodes_by_podcast[podcast_name] = podcast_episodes
                logger.info(f"   📊 {len(podcast_episodes)} episodes processed")
                
        finally:
            db.close()
        
        logger.info(f"✅ Processed {total_episodes} episodes from {len(episodes_by_podcast)} podcasts")
        
        return {
            'success': True,
            'episodes_by_podcast': episodes_by_podcast,
            'total_episodes': total_episodes,
            'podcasts_processed': len(episodes_by_podcast)
        }
        
    except Exception as e:
        logger.error(f"Error processing podcasts from cache: {e}")
        return {
            'success': False,
            'error': str(e),
            'episodes_by_podcast': {},
            'total_episodes': 0
        }

async def run_search_agent() -> Dict[str, Any]:
    """
    Run the AI search orchestrator to curate articles.
    
    Returns:
        Dict with articles and stats
    """
    try:
        logger.info("🤖 Running AI search orchestrator...")
        
        # Run orchestrator with all 3 specialist agents
        orchestrator_results = await search_all_categories(
            max_iterations=1,
            use_cache=True
        )
        
        # Flatten results for backward compatibility
        articles = flatten_results(orchestrator_results)
        
        logger.info(f"✅ Orchestrator found {len(articles)} articles")
        logger.info(f"   By category: {orchestrator_results['by_category_count']}")
        
        return {
            'success': True,
            'articles': articles,
            'stats': {
                'total_found': len(articles),
                'by_category': orchestrator_results['by_category_count']
            }
        }
    except Exception as e:
        logger.error(f"Error running search orchestrator: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'articles': [],
            'stats': {}
        }

@router.get("/morning-briefing")
async def get_morning_briefing(
    episodes_per_podcast: int = 3,
    use_gmail: bool = True,
    use_perplexity: bool = False,  # CHANGED: Disabled by default (quality not good enough)
    use_agent: bool = True,  # NEW: AI agent-curated articles via Exa
    use_podcasts: bool = True,
    newsletter_stories: int = 5,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Generate unified morning briefing combining all sources.
    
    Args:
        episodes_per_podcast: Number of episodes per podcast
        use_gmail: Include Gmail newsletters
        use_perplexity: Include Perplexity real-time news
        use_podcasts: Include podcast insights
        newsletter_stories: Max newsletter stories to include
        force_refresh: Force fresh AI generation (ignore cache)
        
    Returns:
        Dict containing unified briefing with all sources
    """
    try:
        logger.info("🌅 Generating unified morning briefing...")
        
        briefing_data = {
            'date': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'sources_used': [],
            'content': {
                'newsletters': {},
                'news': {},
                'podcasts': {}
            },
            'stats': {
                'total_stories': 0,
                'newsletter_stories': 0,
                'news_stories': 0,
                'podcast_episodes': 0
            }
        }
        
        # Fetch all sources in parallel
        import asyncio
        tasks = []
        task_names = []
        
        if use_gmail:
            # Use fallback service for newsletters (tries today, then yesterday, etc.)
            async def fetch_newsletters_wrapper(hours_ago: int):
                return await get_all_newsletters(hours_ago=hours_ago, max_stories=15)
            
            tasks.append(fallback_service.fetch_newsletters_with_fallback(
                newsletter_fetcher=fetch_newsletters_wrapper,
                alternative_sources=None  # Can add Exa AI or other sources here later
            ))
            task_names.append('gmail')
        
        if use_perplexity:
            from ..ingestion.news_search import NEWS_CATEGORIES
            ai_category = {"ai_news": NEWS_CATEGORIES['ai_news']}
            tasks.append(search_all_categories_with_perplexity(ai_category))
            task_names.append('perplexity')
        
        if use_podcasts:
            # Use cached transcripts for fast podcast processing
            tasks.append(process_podcasts_from_cache(
                episodes_per_podcast=episodes_per_podcast,  # Use the parameter value
                force_refresh=force_refresh
            ))
            task_names.append('podcasts')
        
        if use_agent:
            # AI agent-curated articles via Exa
            logger.info("🤖 Adding AI agent task...")
            tasks.append(run_search_agent())
            task_names.append('agent')
        
        # Execute all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.warning(f"⚠️  {name} failed: {result}")
                briefing_data['content'][name] = {'error': str(result)}
                continue
            
            if name == 'gmail' and result.get('total_stories', 0) > 0:
                briefing_data['sources_used'].append('newsletters')
                
                # Check if fallback was used
                fallback_label = None
                if result.get('fallback_used'):
                    fallback_label = result.get('fallback_label', 'Previous Day Summary')
                    logger.info(f"   📅 Using fallback: {fallback_label}")
                
                # Extract all stories
                all_stories = []
                for newsletter_data in result.get('newsletters', {}).values():
                    all_stories.extend(newsletter_data.get('stories', []))
                
                logger.info(f"📧 Extracted {len(all_stories)} stories")
                
                # Enrich ONLY top 5 with AI (rest shown as links)
                top_k = min(5, len(all_stories))
                logger.info(f"🎯 Enriching top {top_k} stories with AI, rest shown as links")
                
                enriched_top = await enrich_stories_with_ai(all_stories[:top_k], max_stories=top_k)
                
                # Keep remaining stories as links only
                remaining_stories = []
                for story in all_stories[top_k:]:
                    remaining_stories.append({
                        'title': story.get('title', ''),
                        'url': story.get('url', ''),
                        'brief_description': story.get('brief_description', ''),  # Include description
                        'enriched': False
                    })
                
                logger.info(f"✅ {len(enriched_top)} detailed stories + {len(remaining_stories)} as links")
                
                briefing_data['content']['newsletters'] = {
                    'count': len(enriched_top),
                    'detailed_stories': enriched_top,
                    'link_stories': remaining_stories,
                    'fallback_label': fallback_label  # Add fallback label if present
                }
                briefing_data['stats']['newsletter_stories'] = len(enriched_top)
                briefing_data['stats']['newsletter_links'] = len(remaining_stories)
                briefing_data['stats']['total_stories'] += len(enriched_top)
            
            elif name == 'perplexity':
                logger.info(f"🔍 Processing Perplexity result: total_stories={result.get('total_stories', 0)}")
                
                if result.get('total_stories', 0) > 0:
                    briefing_data['sources_used'].append('news')
                    
                    # Extract all news stories
                    news_stories = []
                    for cat_data in result.get('news_by_category', {}).values():
                        news_stories.extend(cat_data.get('stories', []))
                    
                    logger.info(f"📰 Extracted {len(news_stories)} Perplexity stories")
                    
                    briefing_data['content']['news'] = {
                        'count': len(news_stories),
                        'stories': news_stories
                    }
                    briefing_data['stats']['news_stories'] = len(news_stories)
                    briefing_data['stats']['total_stories'] += len(news_stories)
            
            elif name == 'agent' and result.get('articles'):
                logger.info(f"🤖 Processing AI Agent result: {len(result['articles'])} articles")
                briefing_data['sources_used'].append('agent')
                briefing_data['content']['agent'] = {
                    'count': len(result['articles']),
                    'articles': result['articles'],
                    'stats': result.get('stats', {})
                }
                briefing_data['stats']['agent_articles'] = len(result['articles'])
                briefing_data['stats']['total_stories'] += len(result['articles'])
            
            elif name == 'podcasts' and result.get('episodes_by_podcast'):
                briefing_data['sources_used'].append('podcasts')
                
                # Group episodes by podcast (Whisper results)
                podcasts_formatted = []
                for podcast_name, episodes_list in result.get('episodes_by_podcast', {}).items():
                    episodes = episodes_list if isinstance(episodes_list, list) else []
                    
                    if episodes:
                        podcast_entry = {
                            'podcast_name': podcast_name,
                            'detailed_episode': None,
                            'link_episodes': []
                        }
                        
                        # Find episode with AssemblyAI insights
                        detailed_episode = next((e for e in episodes if e.get('insights') and e.get('source') in ('assemblyai_transcript', 'assemblyai_cache')), None)
                        
                        if detailed_episode:
                            # Detailed episode (full AssemblyAI insights)
                            podcast_entry['detailed_episode'] = {
                                'title': detailed_episode.get('title'),
                                'pub_date': detailed_episode.get('pub_date'),
                                'link': detailed_episode.get('link'),
                                'insights': detailed_episode.get('insights'),
                                'practical_tips': detailed_episode.get('practical_tips', []),
                                'enriched_content': detailed_episode.get('enriched_content'),
                                'source': detailed_episode.get('source', 'assemblyai'),
                                'transcript_length': detailed_episode.get('transcript_length', 0),
                                'enriched': True
                            }
                            
                            # Other episodes as links only
                            for episode in episodes:
                                if episode.get('link') != detailed_episode.get('link'):
                                    podcast_entry['link_episodes'].append({
                                        'title': episode.get('title'),
                                        'pub_date': episode.get('pub_date'),
                                        'link': episode.get('link'),
                                        'enriched': False
                                    })
                        
                        logger.info(f"🎙️  {podcast_name}: 1 Whisper detailed + {len(podcast_entry['link_episodes'])} links")
                        podcasts_formatted.append(podcast_entry)
                
                briefing_data['content']['podcasts'] = {
                    'count': len(podcasts_formatted),
                    'podcasts': podcasts_formatted
                }
                # Count detailed episodes + link episodes
                detailed_count = sum(1 for p in podcasts_formatted if p.get('detailed_episode'))
                link_count = sum(len(p.get('link_episodes', [])) for p in podcasts_formatted)
                briefing_data['stats']['podcast_episodes'] = detailed_count
                briefing_data['stats']['podcast_links'] = link_count
                briefing_data['stats']['total_stories'] += detailed_count
        
        # Generate unified briefing text
        logger.info("📝 Generating unified briefing narrative...")
        
        from openai import AsyncOpenAI
        from ..config import settings
        
        openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Build context for GPT
        context = "# Morning Briefing Content\n\n"
        
        if briefing_data['content']['newsletters'].get('detailed_stories'):
            context += "## Newsletter Stories (TLDR AI)\n\n"
            for story in briefing_data['content']['newsletters']['detailed_stories']:
                context += f"### {story['title']}\n"
                context += f"URL: {story.get('url', 'N/A')}\n"
                context += f"{story.get('summary', '')}\n"
                if story.get('key_points'):
                    context += f"Key Points: {', '.join(story['key_points'])}\n"
                context += "\n"
        
        if briefing_data['content']['news'].get('stories'):
            context += "## Real-Time News (Perplexity)\n\n"
            for story in briefing_data['content']['news']['stories']:
                context += f"### {story['title']}\n"
                context += f"URL: {story.get('url', 'N/A')}\n"
                context += f"{story.get('summary', '')}\n"
                if story.get('key_points') or story.get('takeaways'):
                    points = story.get('key_points', story.get('takeaways', []))
                    context += f"Key Points: {', '.join(points)}\n"
                context += "\n"
        
        if briefing_data['content']['podcasts'].get('podcasts'):
            context += "## Podcast Insights\n\n"
            for podcast in briefing_data['content']['podcasts']['podcasts']:
                context += f"### {podcast['podcast_name']}\n"
                # Include detailed episode with full insights
                if podcast.get('detailed_episode') and podcast['detailed_episode'].get('insights'):
                    ep = podcast['detailed_episode']
                    context += f"Latest: {ep['title']}\n"
                    context += f"URL: {ep.get('link', 'N/A')}\n"
                    context += f"Source: {ep.get('source', 'whisper')}\n"
                    insights_preview = ep.get('insights', '')[:500] + "..."
                    context += f"{insights_preview}\n\n"
        
        # Format briefing from already-detailed summaries
        # Start directly with content (no generic header)
        briefing_text = ""
        
        # Newsletter Stories - Detailed
        if briefing_data['content']['newsletters'].get('detailed_stories'):
            briefing_text += "## Newsletter Stories\n\n"
            
            # Add fallback notice if applicable
            fallback_label = briefing_data['content']['newsletters'].get('fallback_label')
            if fallback_label:
                briefing_text += f"*📅 {fallback_label}*\n\n"
            
            for story in briefing_data['content']['newsletters']['detailed_stories']:
                briefing_text += f"### {story['title']}\n\n"
                briefing_text += f"{story.get('summary', '')}\n\n"
                if story.get('key_points'):
                    briefing_text += "**Key Points:**\n"
                    for point in story['key_points']:
                        briefing_text += f"- {point}\n"
                    briefing_text += "\n"
                briefing_text += f"[Read more]({story.get('url', '#')})\n\n"
                briefing_text += "---\n\n"
        
        # Newsletter Stories - Links Only
        if briefing_data['content']['newsletters'].get('link_stories'):
            briefing_text += "### Additional Newsletter Stories\n\n"
            for story in briefing_data['content']['newsletters']['link_stories']:
                # Include brief description for context
                description = story.get('brief_description', '')
                if description:
                    # Truncate if too long (keep first 100 chars)
                    if len(description) > 100:
                        description = description[:97] + "..."
                    briefing_text += f"• [{story['title']}]({story.get('url', '#')})\n  *{description}*\n"
                else:
                    briefing_text += f"• [{story['title']}]({story.get('url', '#')})\n"
            briefing_text += "\n"
        
        # AI Agent-Curated Articles
        if briefing_data['content'].get('agent', {}).get('articles'):
            briefing_text += "## AI-Curated Articles\n\n"
            briefing_text += "*🤖 Curated by AI Agent using Exa semantic search*\n\n"
            
            for article in briefing_data['content']['agent']['articles']:
                briefing_text += f"### {article.title}\n\n"
                
                # Add summary if available
                if article.summary:
                    briefing_text += f"{article.summary}\n\n"
                elif article.snippet:
                    briefing_text += f"{article.snippet}\n\n"
                
                # Add highlights if available
                if article.highlights:
                    briefing_text += "**Key Highlights:**\n"
                    for highlight in article.highlights[:3]:  # Top 3 highlights
                        briefing_text += f"- {highlight}\n"
                    briefing_text += "\n"
                
                # Add metadata
                metadata_parts = []
                if article.source:
                    metadata_parts.append(f"📰 {article.source}")
                if article.published_date:
                    # Format date nicely
                    try:
                        pub_date = datetime.fromisoformat(article.published_date.replace('Z', '+00:00'))
                        date_str = pub_date.strftime('%b %d, %Y')
                        metadata_parts.append(f"📅 {date_str}")
                    except:
                        pass
                
                if metadata_parts:
                    briefing_text += f"*{' | '.join(metadata_parts)}*\n\n"
                
                briefing_text += f"[Read more]({article.url})\n\n"
                briefing_text += "---\n\n"
        
        if briefing_data['content']['news'].get('stories'):
            briefing_text += "## Real-Time News\n\n"
            for story in briefing_data['content']['news']['stories']:
                briefing_text += f"### {story['title']}\n\n"
                briefing_text += f"{story.get('summary', '')}\n\n"
                if story.get('key_points') or story.get('takeaways'):
                    points = story.get('key_points', story.get('takeaways', []))
                    briefing_text += "**Key Points:**\n"
                    for point in points:
                        briefing_text += f"- {point}\n"
                    briefing_text += "\n"
                briefing_text += f"[Read more]({story.get('url', '#')})\n\n"
                briefing_text += "---\n\n"
        
        if briefing_data['content']['podcasts'].get('podcasts'):
            briefing_text += "## Podcast Insights\n\n"
            
            for podcast in briefing_data['content']['podcasts']['podcasts']:
                briefing_text += f"### 🎙️ {podcast['podcast_name']}\n\n"
                
                # Detailed episode
                if podcast.get('detailed_episode'):
                    ep = podcast['detailed_episode']
                    briefing_text += f"**{ep['title']}**\n"
                    briefing_text += f"📅 *{ep.get('pub_date', 'Unknown date')}*\n\n"
                    
                    # Full summary
                    if ep.get('insights'):
                        briefing_text += f"{ep['insights']}\n\n"
                    
                    # Practical tips (if available)
                    if ep.get('practical_tips') and len(ep['practical_tips']) > 0:
                        briefing_text += "### 💡 Practical Tips\n"
                        for tip in ep['practical_tips']:
                            briefing_text += f"• {tip}\n"
                        briefing_text += "\n"
                    
                    # Links
                    briefing_text += f"🔗 [Listen to Episode]({ep.get('link', '#')})\n\n"
                
                # Link-only episodes
                if podcast.get('link_episodes'):
                    briefing_text += "**Other Recent Episodes:**\n"
                    for ep in podcast['link_episodes']:
                        link_text = f"[Listen]({ep['link']})" if ep.get('link') else ""
                        briefing_text += f"• {ep['title']} {link_text}\n"
                    briefing_text += "\n"
                
                briefing_text += "---\n\n"
        
        # Add AI Daily Brief gap analysis
        ai_daily_brief_insights = None
        if briefing_data['content']['newsletters'].get('detailed_stories') and briefing_data['content']['news'].get('stories'):
            logger.info("🔍 Analyzing AI Daily Brief for unique content...")
            ai_daily_brief_insights = await get_ai_daily_brief_gap_analysis(
                tldr_stories=briefing_data['content']['newsletters']['detailed_stories'],
                perplexity_stories=briefing_data['content']['news']['stories']
            )
            
        if ai_daily_brief_insights:
            briefing_text += "## Additional Analysis\n\n"
            briefing_text += "*Unique insights from The AI Daily Brief not covered above*\n\n"
            briefing_text += f"{ai_daily_brief_insights}\n\n"
            briefing_text += "---\n\n"
        
        # Add cached podcast summaries section (excluding ones already shown above)
        cached_summaries = await get_cached_podcast_summaries(limit=9)
        
        # Get titles of episodes already shown in main section
        shown_titles = set()
        if briefing_data['content']['podcasts'].get('podcasts'):
            for podcast in briefing_data['content']['podcasts']['podcasts']:
                if podcast.get('detailed_episode'):
                    shown_titles.add(podcast['detailed_episode']['title'])
        
        # Filter out duplicates
        unique_summaries = [s for s in cached_summaries if s['title'] not in shown_titles]
        
        if unique_summaries:
            briefing_text += "## Recent Podcast Archive\n\n"
            briefing_text += "*Additional episodes with full transcripts and AI insights*\n\n"
            
            for summary in unique_summaries:
                briefing_text += f"### 🎙️ {summary['podcast_name']} - {summary['title']}\n"
                briefing_text += f"📅 *{summary['date']}*\n\n"
                briefing_text += f"{summary['summary']}\n\n"
                
                # Add practical tips if available
                if summary.get('practical_tips') and len(summary['practical_tips']) > 0:
                    briefing_text += "### 💡 Practical Tips\n"
                    for tip in summary['practical_tips']:
                        briefing_text += f"• {tip}\n"
                    briefing_text += "\n"
                
                # Add listen link
                briefing_text += f"🔗 [Listen to Episode]({summary['link']})\n\n"
                briefing_text += "---\n\n"
        
        # Save briefing to database
        try:
            from ..database.db import SessionLocal
            from ..database.models import Briefing
            
            db = SessionLocal()
            
            briefing_obj = Briefing(
                date=datetime.now(),
                title=f"Morning Briefing - {datetime.now().strftime('%Y-%m-%d')}",
                briefing_text=briefing_text,
                total_episodes=briefing_data['stats']['podcast_episodes'],
                total_sources=len(briefing_data['sources_used']),
                total_cost_cents=0  # TODO: Calculate actual cost
            )
            
            db.add(briefing_obj)
            db.commit()
            db.close()
            
            logger.info("💾 Saved briefing to database")
        except Exception as db_err:
            logger.warning(f"⚠️  Failed to save briefing to DB: {db_err}")
        
        # Add briefing text to response
        briefing_data['briefing'] = briefing_text
        
        logger.info(f"✅ Generated unified briefing with {briefing_data['stats']['total_stories']} items")
        
        return briefing_data
        
    except Exception as e:
        logger.error(f"Morning briefing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/email-briefing")
async def email_briefing(
    recipient_email: str = None,
    briefing_id: int = None
) -> Dict[str, Any]:
    """
    Send the most recent (or specific) briefing via email.
    
    Args:
        recipient_email: Email address to send to (optional, uses config default)
        briefing_id: Specific briefing ID (optional, uses most recent)
        
    Returns:
        Dict with send status
    """
    try:
        from ..email_service import send_briefing_from_db
        
        logger.info(f"📧 Sending briefing email...")
        
        success = await send_briefing_from_db(
            briefing_id=briefing_id,
            recipient_email=recipient_email
        )
        
        if success:
            return {
                "success": True,
                "message": f"Briefing sent to {recipient_email or 'configured recipient'}",
                "briefing_id": briefing_id or "most recent"
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send email. Check SMTP settings in .env file."
            )
            
    except Exception as e:
        logger.error(f"Email briefing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Old test endpoint removed - use /test-transcript instead


@router.get("/api/briefing-summary")
async def get_briefing_summary(
    include_podcasts: bool = True,
    include_perplexity: bool = True,
    top_stories: int = 5
) -> Dict[str, Any]:
    """
    Get a brief summary of the morning briefing with links to additional stories.
    
    Args:
        include_podcasts: Whether to include podcast insights
        include_perplexity: Whether to include Perplexity news
        top_stories: Number of top stories to highlight (default: 5)
        
    Returns:
        Dict with brief summary and additional story links
    """
    try:
        # Generate full briefing
        briefing_data = await get_morning_briefing(
            include_podcasts=include_podcasts,
            include_perplexity=include_perplexity
        )
        
        # Extract stories from all sources
        all_stories = []
        additional_stories = []
        
        # Newsletter stories
        if 'newsletters' in briefing_data.get('content', {}):
            newsletter_stories = briefing_data['content']['newsletters'].get('stories', [])
            all_stories.extend([{**story, 'source': 'newsletter'} for story in newsletter_stories])
        
        # Perplexity news
        if 'news' in briefing_data.get('content', {}):
            news_stories = briefing_data['content']['news'].get('stories', [])
            all_stories.extend([{**story, 'source': 'news'} for story in news_stories])
        
        # Podcast stories
        if 'podcasts' in briefing_data.get('content', {}):
            podcast_stories = []
            for podcast in briefing_data['content']['podcasts'].get('podcasts', []):
                for episode in podcast.get('episodes', []):
                    if episode.get('has_summary'):
                        podcast_stories.append({
                            'title': episode['title'],
                            'url': episode.get('youtube_url') or episode.get('link', '#'),
                            'source': 'podcast',
                            'podcast_name': podcast['podcast_name']
                        })
            all_stories.extend(podcast_stories)
        
        # Split into top stories and additional
        if len(all_stories) > top_stories:
            top_stories_list = all_stories[:top_stories]
            additional_stories = all_stories[top_stories:]
        else:
            top_stories_list = all_stories
            additional_stories = []
        
        # Create brief summary
        summary_text = f"# Morning AI Briefing Summary\n\n"
        summary_text += f"*Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}*\n\n"
        summary_text += f"## Top {len(top_stories_list)} Stories\n\n"
        
        for i, story in enumerate(top_stories_list, 1):
            summary_text += f"{i}. **{story.get('title', 'No title')}**\n"
            if story.get('url'):
                summary_text += f"   🔗 [Read more]({story['url']})\n"
            summary_text += f"   📰 Source: {story.get('source', 'unknown').title()}\n\n"
        
        # Add additional stories section
        if additional_stories:
            summary_text += f"## Additional Stories ({len(additional_stories)} more)\n\n"
            for story in additional_stories:
                summary_text += f"- **{story.get('title', 'No title')}**\n"
                if story.get('url'):
                    summary_text += f"  🔗 [Read more]({story['url']})\n"
                summary_text += f"  📰 Source: {story.get('source', 'unknown').title()}\n\n"
        
        return {
            "date": briefing_data.get('date'),
            "sources_used": briefing_data.get('sources_used', []),
            "stats": briefing_data.get('stats', {}),
            "summary": summary_text,
            "top_stories": top_stories_list,
            "additional_stories": additional_stories,
            "total_stories": len(all_stories)
        }
        
    except Exception as e:
        logger.error(f"❌ Briefing summary failed: {e}")
        return {"error": str(e)}

