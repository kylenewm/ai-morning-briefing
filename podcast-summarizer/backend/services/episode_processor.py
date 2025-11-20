"""
Episode processing service.
Centralizes episode processing logic for reusability and parallel execution.
Integrates with database cache to avoid re-processing.
Now includes Whisper transcription for podcast episodes.
"""

import asyncio
import logging
from typing import Dict, Any, List

from ..ai.insight_extractor import extract_insights_from_episode
from ..database import CacheService
from ..database.models import ContentItem
# DISABLED: WhisperTranscriber not available - using AssemblyAI instead
# from ..ingestion.whisper_transcriber import WhisperTranscriber

logger = logging.getLogger(__name__)


async def process_single_episode_with_whisper(
    episode: Dict[str, Any],
    podcast_name: str = "Unknown",
    test_mode: bool = False,
    include_transcript: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process a single episode using Whisper transcription.
    Downloads MP3, transcribes with Whisper, then extracts insights.
    
    Args:
        episode: Episode dictionary with metadata and MP3 URL
        podcast_name: Name of the podcast (for logging)
        test_mode: Whether to truncate transcripts for testing
        include_transcript: Whether to include full transcript in response
        force_refresh: Skip cache and re-process content
        
    Returns:
        Dict with episode data and insights/summary
    """
    episode_title = episode.get('title', 'Unknown')[:60]
    item_url = episode.get('link') or episode.get('enclosure_url', 'unknown')
    
    # Check cache first (unless force refresh)
    if not force_refresh:
        # Use episode GUID as cache key
        episode_guid = episode.get('guid', '')
        if episode_guid:
            # Try to find cached content by source_id (which should be the GUID)
            db = CacheService.SessionLocal()
            try:
                cached_item = db.query(ContentItem).filter(
                    ContentItem.source_id == episode_guid
                ).first()
                if cached_item:
                    cached = {
                        'title': cached_item.title,
                        'url': cached_item.item_url,
                        'insight': cached_item.insight,
                        'transcript': cached_item.content,
                        'transcript_length': len(cached_item.content) if cached_item.content else 0,
                        'cached_at': cached_item.created_at,
                        'published_date': cached_item.published_date
                    }
                else:
                    cached = None
            finally:
                db.close()
            cached = cached
        else:
            cached = None
        
        if cached and cached.get('insight'):
            logger.info(f"   💾 Using cached Whisper insights: {episode_title}")
            return {
                "title": cached['title'],
                "pub_date": cached.get('published_date'),
                "link": cached['url'],
                "insights": cached['insight'],
                "source": "whisper_cache",
                "transcript_length": cached.get('transcript_length'),
                "cached_at": cached.get('cached_at'),
                "transcript": cached['transcript'] if include_transcript else None
            }
    
    # Build base episode data
    episode_data = {
        "title": episode.get("title"),
        "pub_date": episode.get("pub_date"),
        "link": episode.get("link"),
    }
    
    try:
        # Initialize Whisper transcriber
        transcriber = WhisperTranscriber()
        
        # Transcribe episode
        logger.info(f"   🎙️  Transcribing with Whisper: {episode_title}...")
        transcript = await transcriber.get_episode_transcript(episode)
        
        if not transcript:
            logger.warning(f"   ⚠️  Whisper transcription failed: {episode_title}")
            episode_data["insights"] = None
            episode_data["source"] = "whisper_failed"
            episode_data["error"] = "Whisper transcription failed"
            return episode_data
        
        # Generate summary from transcript
        logger.info(f"   📝 Generating summary: {episode_title}...")
        summary = await transcriber.get_transcript_summary(transcript, episode_title)
        
        episode_data["insights"] = summary
        episode_data["source"] = "whisper_transcript"
        episode_data["transcript_length"] = len(transcript)
        
        if include_transcript:
            episode_data["transcript"] = transcript
        
        logger.info(f"   ✅ Whisper processing completed: {episode_title}")
        return episode_data
        
    except Exception as e:
        logger.error(f"   ❌ Whisper processing failed: {str(e)}")
        episode_data["insights"] = None
        episode_data["source"] = "whisper_error"
        episode_data["error"] = str(e)
        return episode_data


async def process_single_episode(
    episode: Dict[str, Any],
    podcast_name: str = "Unknown",
    use_transcripts: bool = True,
    test_mode: bool = False,
    include_transcript: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process a single episode: extract insights from transcript or fall back to description summary.
    Checks cache first unless force_refresh is True.
    
    Args:
        episode: Episode dictionary with metadata and optionally transcript
        podcast_name: Name of the podcast (for logging)
        use_transcripts: Whether to use transcript-based insights
        test_mode: Whether to truncate transcripts for testing
        include_transcript: Whether to include full transcript in response
        force_refresh: Skip cache and re-process content
        
    Returns:
        Dict with episode data and insights/summary
    """
    episode_title = episode.get('title', 'Unknown')[:60]
    item_url = episode.get('link') or episode.get('youtube_url', 'unknown')
    
    # Check cache first (unless force refresh)
    if not force_refresh and use_transcripts:
        # If this is a cached episode, get full cached data
        if episode.get('from_cache') and episode.get('cached_id'):
            cached = CacheService.get_cached_content_by_id(episode['cached_id'])
        else:
            cached = CacheService.get_cached_content(
                source_name=podcast_name,
                item_url=item_url,
                force_refresh=force_refresh
            )
        
        if cached and cached.get('insight'):
            logger.info(f"   💾 Using cached insights: {episode_title}")
            return {
                "title": cached['title'],
                "pub_date": cached.get('published_date'),
                "link": cached['url'],
                "youtube_url": cached.get('youtube_url'),
                "insights": cached['insight'],
                "source": "cache",
                "transcript_length": cached.get('transcript_length'),
                "cached_at": cached.get('cached_at'),
                "transcript": cached['transcript'] if include_transcript else None
            }
    
    # Build base episode data
    episode_data = {
        "title": episode.get("title"),
        "pub_date": episode.get("pub_date"),
        "link": episode.get("link"),
        "youtube_url": episode.get("youtube_url"),
    }
    
    # Try transcript-based insights first
    if use_transcripts and episode.get("transcript"):
        try:
            mode_indicator = "🧪 TEST MODE" if test_mode else "🎯"
            logger.info(f"   {mode_indicator} Extracting insights: {episode_title}...")
            
            # Extract insights from transcript
            insights_result = await extract_insights_from_episode(episode, test_mode=test_mode)
            
            # Extract the insights text from nested dict structure
            # insights_result = {**episode, "insights": {"success": True, "insights": "text..."}}
            insights_obj = insights_result.get("insights", {})
            if isinstance(insights_obj, dict):
                insights_text = insights_obj.get("insights", "")
            else:
                insights_text = insights_obj
            
            episode_data["insights"] = insights_text  # Store as string, not dict
            episode_data["source"] = "transcript" if not test_mode else "transcript_test"
            episode_data["transcript_length"] = len(episode.get("transcript", ""))
            
            if test_mode:
                episode_data["test_mode"] = True
                episode_data["truncated_length"] = insights_result.get("transcript_length")
            
            # Include transcript if requested
            if include_transcript:
                episode_data["transcript"] = episode.get("transcript")
            
            # Save to cache
            try:
                
                CacheService.save_content_and_insight(
                    source_type="podcast",
                    source_name=podcast_name,
                    item_url=item_url,
                    title=episode.get("title", "Unknown"),
                    transcript=episode.get("transcript"),
                    insight=insights_text,
                    youtube_url=episode.get("youtube_url"),
                    published_date=episode.get("pub_date"),
                    description=episode.get("description"),
                    model_name="gpt-5-mini",
                    test_mode=test_mode
                )
            except Exception as cache_err:
                logger.warning(f"   ⚠️  Failed to cache: {cache_err}")
            
            logger.info(f"   ✅ Insights extracted and cached")
            
            return episode_data
            
        except Exception as e:
            logger.error(f"   ❌ Insight extraction failed: {str(e)}")
            
            # Mark as failed - no fallback to description
            episode_data["insights"] = None
            episode_data["source"] = "transcript_failed"
            episode_data["error"] = str(e)
            
            return episode_data
    
    # No transcript available
    elif use_transcripts:
        logger.warning(f"   ⚠️  No transcript available: {episode_title}")
        episode_data["insights"] = None
        episode_data["source"] = "no_transcript"
        episode_data["error"] = "No transcript available"
        
        return episode_data
    
    # Transcripts disabled - return metadata only
    else:
        episode_data["insights"] = None
        episode_data["source"] = "metadata_only"
        
        return episode_data


async def process_episodes_parallel(
    episodes: List[Dict[str, Any]],
    podcast_name: str = "Unknown",
    use_transcripts: bool = True,
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Process multiple episodes in parallel.
    
    Args:
        episodes: List of episode dictionaries
        podcast_name: Name of the podcast (for logging)
        use_transcripts: Whether to use transcript-based insights
        test_mode: Whether to truncate transcripts for testing
        include_transcripts: Whether to include full transcripts in response
        force_refresh: Skip cache and re-process all content
        
    Returns:
        List of processed episodes with insights/summaries
    """
    if not episodes:
        return []
    
    logger.info(f"   🚀 Processing {len(episodes)} episode(s) in parallel...")
    
    # Create tasks for parallel execution
    tasks = [
        process_single_episode(
            episode,
            podcast_name=podcast_name,
            use_transcripts=use_transcripts,
            test_mode=test_mode,
            include_transcript=include_transcripts,
            force_refresh=force_refresh
        )
        for episode in episodes
    ]
    
    # Execute all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions and log errors
    processed_episodes = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"   ❌ Episode {idx+1} failed: {str(result)}")
            # Add error episode
            processed_episodes.append({
                **episodes[idx],
                "error": str(result),
                "source": "error"
            })
        else:
            processed_episodes.append(result)
    
    logger.info(f"   ✅ Completed {len(processed_episodes)}/{len(episodes)} episode(s)")
    
    return processed_episodes


async def process_episodes_with_whisper_parallel(
    episodes: List[Dict[str, Any]],
    podcast_name: str = "Unknown",
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Process multiple episodes in parallel using Whisper transcription.
    
    Args:
        episodes: List of episode dictionaries with MP3 URLs
        podcast_name: Name of the podcast (for logging)
        test_mode: Whether to truncate transcripts for testing
        include_transcripts: Whether to include full transcripts in response
        force_refresh: Skip cache and re-process all content
        
    Returns:
        List of processed episodes with Whisper insights/summaries
    """
    if not episodes:
        return []
    
    logger.info(f"   🚀 Processing {len(episodes)} episode(s) with Whisper in parallel...")
    
    # Create tasks for parallel execution
    tasks = [
        process_single_episode_with_whisper(
            episode,
            podcast_name=podcast_name,
            test_mode=test_mode,
            include_transcript=include_transcripts,
            force_refresh=force_refresh
        )
        for episode in episodes
    ]
    
    # Execute all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions and log errors
    processed_episodes = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"   ❌ Episode {idx+1} failed: {str(result)}")
            # Add error episode
            processed_episodes.append({
                **episodes[idx],
                "error": str(result),
                "source": "whisper_error"
            })
        else:
            processed_episodes.append(result)
    
    logger.info(f"   ✅ Completed {len(processed_episodes)}/{len(episodes)} episode(s) with Whisper")
    
    return processed_episodes


async def process_episodes_sequential(
    episodes: List[Dict[str, Any]],
    podcast_name: str = "Unknown",
    use_transcripts: bool = True,
    test_mode: bool = False,
    include_transcripts: bool = False
) -> List[Dict[str, Any]]:
    """
    Process multiple episodes sequentially (for debugging or rate limiting).
    
    Args:
        episodes: List of episode dictionaries
        podcast_name: Name of the podcast (for logging)
        use_transcripts: Whether to use transcript-based insights
        test_mode: Whether to truncate transcripts for testing
        include_transcripts: Whether to include full transcripts in response
        
    Returns:
        List of processed episodes with insights/summaries
    """
    if not episodes:
        return []
    
    logger.info(f"   📝 Processing {len(episodes)} episode(s) sequentially...")
    
    processed_episodes = []
    for idx, episode in enumerate(episodes, 1):
        logger.info(f"   [{idx}/{len(episodes)}] {episode.get('title', 'Unknown')[:50]}...")
        
        try:
            result = await process_single_episode(
                episode,
                podcast_name=podcast_name,
                use_transcripts=use_transcripts,
                test_mode=test_mode,
                include_transcript=include_transcripts
            )
            processed_episodes.append(result)
        except Exception as e:
            logger.error(f"   ❌ Episode {idx} failed: {str(e)}")
            processed_episodes.append({
                **episode,
                "error": str(e),
                "source": "error"
            })
    
    return processed_episodes

