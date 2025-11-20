"""
Podcast processing service.
Handles processing multiple podcasts and aggregating results.
"""

import asyncio
import logging
from typing import Dict, Any, List, Tuple

from ..ingestion.sources import get_all_podcast_sources
from ..ingestion.rss_parser import parse_podcast_feed
from .episode_processor import process_episodes_parallel, process_episodes_with_whisper_parallel
from ..database.cache_service import CacheService

logger = logging.getLogger(__name__)


async def process_podcast(
    podcast_id: str,
    podcast_data: Dict[str, Any],
    episodes_per_podcast: int = 3,  # Try up to 3 episodes
    use_transcripts: bool = True,
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> Tuple[str, Dict[str, Any]]:
    """
    Process a single podcast: fetch RSS and process episodes.
    
    Args:
        podcast_id: Unique identifier for the podcast
        podcast_data: Podcast configuration dictionary
        episodes_per_podcast: Number of episodes to fetch
        use_transcripts: Whether to use transcript-based insights
        test_mode: Whether to truncate transcripts for testing
        include_transcripts: Whether to include full transcripts in response
        
    Returns:
        Tuple of (podcast_name, result_dict) where result_dict contains:
            - episodes: List of processed episodes
            - failed_transcripts: List of episodes that failed
    """
    podcast_name = podcast_data['name']
    
    try:
        logger.info(f"🎙️  Processing: {podcast_name}")
        
        # Fetch episodes from RSS (with or without transcripts)
        logger.info(f"   📡 Fetching RSS feed...")
        youtube_channel = podcast_data.get("youtube_channel")
        
        episodes = await parse_podcast_feed(
            podcast_data["rss_url"],
            max_episodes=episodes_per_podcast,
            fetch_transcripts=use_transcripts,
            youtube_channel=youtube_channel,
            require_youtube=False  # We use AssemblyAI transcription, not YouTube
        )
        
        logger.info(f"   ✅ Found {len(episodes)} episode(s)")
        
        # If no episodes with transcripts found and we need transcripts, try cache
        if use_transcripts and len(episodes) == 0 and not force_refresh:
            logger.info(f"   🔍 No episodes with transcripts found, checking cache...")
            cached_episodes = CacheService.get_recent_episodes(podcast_name, limit=5)
            
            # Find cached episodes that have transcripts
            episodes_with_transcripts = [
                ep for ep in cached_episodes 
                if ep.get('has_transcript') and ep.get('has_insight')
            ]
            
            if episodes_with_transcripts:
                # Use the most recent cached episode with transcript
                cached_ep = episodes_with_transcripts[0]
                logger.info(f"   📦 Using cached episode: {cached_ep['title'][:50]}...")
                
                # Convert cached episode to the format expected by episode processor
                episodes = [{
                    "title": cached_ep['title'],
                    "description": "",
                    "pub_date": cached_ep['published_date'].isoformat() if cached_ep['published_date'] else "",
                    "link": cached_ep['url'],
                    "audio_url": "",
                    "duration": None,
                    "youtube_url": cached_ep['youtube_url'],
                    "transcript": None,  # Will be loaded from cache in episode processor
                    "from_cache": True,
                    "cached_id": cached_ep['id']
                }]
            else:
                logger.warning(f"   ⚠️  No cached episodes with transcripts found for {podcast_name}")
        
        # Process all episodes in parallel
        processed_episodes = await process_episodes_parallel(
            episodes,
            podcast_name=podcast_name,
            use_transcripts=use_transcripts,
            test_mode=test_mode,
            include_transcripts=include_transcripts,
            force_refresh=force_refresh
        )
        
        # Track failed transcripts
        failed_transcripts = []
        for episode in processed_episodes:
            if episode.get("error"):
                failed_transcripts.append({
                    "podcast": podcast_name,
                    "title": episode.get("title", "Unknown"),
                    "youtube_url": episode.get("youtube_url"),
                    "reason": episode.get("error")
                })
        
        return podcast_name, {
            "episodes": processed_episodes,
            "failed_transcripts": failed_transcripts
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing {podcast_name}: {str(e)}")
        # Return empty result on error
        return podcast_name, {
            "episodes": [],
            "failed_transcripts": [{
                "podcast": podcast_name,
                "title": "All episodes",
                "reason": f"Podcast processing failed: {str(e)}"
            }]
        }


async def process_podcast_with_whisper(
    podcast_id: str,
    podcast_data: Dict[str, Any],
    episodes_per_podcast: int = 1,  # Start with 1 episode for Whisper (expensive)
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> Tuple[str, Dict[str, Any]]:
    """
    Process a single podcast using Whisper transcription.
    
    Args:
        podcast_id: Unique identifier for the podcast
        podcast_data: Podcast configuration dictionary
        episodes_per_podcast: Number of episodes to fetch (default 1 for cost control)
        test_mode: Whether to truncate transcripts for testing
        include_transcripts: Whether to include full transcripts in response
        force_refresh: Skip cache and re-process content
        
    Returns:
        Tuple of (podcast_name, result_dict) where result_dict contains:
            - episodes: List of processed episodes
            - failed_transcripts: List of episodes that failed
    """
    podcast_name = podcast_data['name']
    
    try:
        logger.info(f"🎙️  Processing with Whisper: {podcast_name}")
        
        # Fetch episodes from RSS (no YouTube needed for Whisper)
        logger.info(f"   📡 Fetching RSS feed...")
        
        episodes = await parse_podcast_feed(
            podcast_data["rss_url"],
            max_episodes=episodes_per_podcast,
            fetch_transcripts=False,  # We'll use Whisper instead
            youtube_channel=None,
            require_youtube=False
        )
        
        logger.info(f"   ✅ Found {len(episodes)} episode(s)")
        
        if not episodes:
            logger.warning(f"   ⚠️  No episodes found for {podcast_name}")
            return podcast_name, {
                "episodes": [],
                "failed_transcripts": [{
                    "podcast": podcast_name,
                    "title": "No episodes",
                    "reason": "No episodes found in RSS feed"
                }]
            }
        
        # Process episodes with Whisper
        processed_episodes = await process_episodes_with_whisper_parallel(
            episodes,
            podcast_name=podcast_name,
            test_mode=test_mode,
            include_transcripts=include_transcripts,
            force_refresh=force_refresh
        )
        
        # Track failed transcripts
        failed_transcripts = []
        for episode in processed_episodes:
            if episode.get("error"):
                failed_transcripts.append({
                    "podcast": podcast_name,
                    "title": episode.get("title", "Unknown"),
                    "reason": episode.get("error")
                })
        
        return podcast_name, {
            "episodes": processed_episodes,
            "failed_transcripts": failed_transcripts
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing {podcast_name} with Whisper: {str(e)}")
        # Return empty result on error
        return podcast_name, {
            "episodes": [],
            "failed_transcripts": [{
                "podcast": podcast_name,
                "title": "All episodes",
                "reason": f"Whisper processing failed: {str(e)}"
            }]
        }


async def process_all_podcasts_parallel(
    episodes_per_podcast: int = 2,
    use_transcripts: bool = True,
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process all configured podcasts in parallel.
    
    Args:
        episodes_per_podcast: Number of episodes to fetch per podcast
        use_transcripts: Whether to use transcript-based insights
        test_mode: Whether to truncate transcripts for testing
        include_transcripts: Whether to include full transcripts in response
        
    Returns:
        Dictionary with:
            - episodes_by_podcast: Dict mapping podcast names to episode lists
            - failed_transcripts: List of all failed episodes across podcasts
            - total_episodes: Total number of episodes processed
            - transcript_success_count: Number of episodes with successful transcript insights
    """
    podcasts = get_all_podcast_sources()
    
    logger.info(f"🌅 Starting parallel podcast processing...")
    logger.info(f"📻 Processing {len(podcasts)} podcast(s) in parallel, {episodes_per_podcast} episode(s) each")
    
    # Create tasks for parallel execution
    tasks = [
        process_podcast(
            podcast_id,
            podcast_data,
            episodes_per_podcast,
            use_transcripts,
            test_mode,
            include_transcripts,
            force_refresh
        )
        for podcast_id, podcast_data in podcasts.items()
    ]
    
    # Execute all podcast processing in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate results
    episodes_by_podcast = {}
    all_failed_transcripts = []
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"❌ Podcast processing exception: {str(result)}")
            continue
        
        podcast_name, data = result
        episodes_by_podcast[podcast_name] = data["episodes"]
        all_failed_transcripts.extend(data["failed_transcripts"])
    
    # Calculate statistics
    total_episodes = sum(len(eps) for eps in episodes_by_podcast.values())
    transcript_success_count = len([
        e for eps in episodes_by_podcast.values() 
        for e in eps 
        if e.get('source') in ('transcript', 'transcript_test')
    ])
    
    logger.info(f"✅ Parallel processing complete!")
    logger.info(f"   📊 Total episodes: {total_episodes}")
    logger.info(f"   🎯 Transcript-based insights: {transcript_success_count}/{total_episodes}")
    logger.info(f"   ⚠️  Failed transcripts: {len(all_failed_transcripts)}")
    
    return {
        "episodes_by_podcast": episodes_by_podcast,
        "failed_transcripts": all_failed_transcripts,
        "total_episodes": total_episodes,
        "transcript_success_count": transcript_success_count,
        "transcript_success_rate": f"{transcript_success_count}/{total_episodes}",
        "manual_review_needed": len(all_failed_transcripts) > 0
    }


async def process_all_podcasts_with_whisper(
    episodes_per_podcast: int = 1,  # Default 1 for cost control
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process all configured podcasts using Whisper transcription.
    
    Args:
        episodes_per_podcast: Number of episodes to fetch per podcast (default 1 for cost)
        test_mode: Whether to truncate transcripts for testing
        include_transcripts: Whether to include full transcripts in response
        force_refresh: Skip cache and re-process all content
        
    Returns:
        Dictionary with:
            - episodes_by_podcast: Dict mapping podcast names to episode lists
            - failed_transcripts: List of all failed episodes across podcasts
            - total_episodes: Total number of episodes processed
            - whisper_success_count: Number of episodes with successful Whisper insights
    """
    podcasts = get_all_podcast_sources()
    
    logger.info(f"🌅 Starting Whisper podcast processing...")
    logger.info(f"📻 Processing {len(podcasts)} podcast(s) with Whisper, {episodes_per_podcast} episode(s) each")
    logger.info(f"💰 Estimated cost: ${len(podcasts) * episodes_per_podcast * 0.16:.2f} per run")
    
    # Create tasks for parallel execution
    tasks = [
        process_podcast_with_whisper(
            podcast_id,
            podcast_data,
            episodes_per_podcast,
            test_mode,
            include_transcripts,
            force_refresh
        )
        for podcast_id, podcast_data in podcasts.items()
    ]
    
    # Execute all podcast processing in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Aggregate results
    episodes_by_podcast = {}
    all_failed_transcripts = []
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"❌ Whisper podcast processing exception: {str(result)}")
            continue
        
        podcast_name, data = result
        episodes_by_podcast[podcast_name] = data["episodes"]
        all_failed_transcripts.extend(data["failed_transcripts"])
    
    # Calculate statistics
    total_episodes = sum(len(eps) for eps in episodes_by_podcast.values())
    whisper_success_count = len([
        e for eps in episodes_by_podcast.values() 
        for e in eps 
        if e.get('source') in ('whisper_transcript', 'whisper_cache')
    ])
    
    logger.info(f"✅ Whisper processing complete!")
    logger.info(f"   📊 Total episodes: {total_episodes}")
    logger.info(f"   🎯 Whisper insights: {whisper_success_count}/{total_episodes}")
    logger.info(f"   ⚠️  Failed transcripts: {len(all_failed_transcripts)}")
    
    return {
        "episodes_by_podcast": episodes_by_podcast,
        "failed_transcripts": all_failed_transcripts,
        "total_episodes": total_episodes,
        "whisper_success_count": whisper_success_count,
        "whisper_success_rate": f"{whisper_success_count}/{total_episodes}",
        "manual_review_needed": len(all_failed_transcripts) > 0
    }

