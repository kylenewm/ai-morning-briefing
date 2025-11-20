"""
AssemblyAI Podcast Processing
Handles podcast transcription and processing using AssemblyAI
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..ingestion.assemblyai_transcriber import AssemblyAITranscriber
from ..ingestion.rss_parser import parse_podcast_feed
from ..ingestion.sources import get_all_podcast_sources

logger = logging.getLogger(__name__)

async def process_single_episode_with_assemblyai(
    episode: Dict[str, Any],
    podcast_name: str = "Unknown",
    test_mode: bool = False,
    include_transcript: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process a single episode with AssemblyAI transcription
    
    Args:
        episode: Episode data from RSS feed
        podcast_name: Name of the podcast
        test_mode: If True, limit to first minute for testing
        include_transcript: If True, include full transcript in response
        force_refresh: If True, ignore cache and re-transcribe
        
    Returns:
        Dict with episode data and insights
    """
    episode_title = episode.get('title', 'Unknown')[:60]
    item_url = episode.get('link') or episode.get('enclosure_url', 'unknown')
    
    try:
        # Initialize transcriber
        transcriber = AssemblyAITranscriber()
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            episode_guid = episode.get('guid', '')
            if episode_guid:
                cache_key = f"assemblyai_transcript_{episode_guid}"
                cached_transcript = await transcriber._get_cached_transcript(cache_key)
                if cached_transcript:
                    logger.info(f"   💾 Using cached AssemblyAI transcript: {episode_title}")
                    
                    # Generate insights from cached transcript
                    insights = await transcriber.get_transcript_summary(
                        cached_transcript, 
                        episode_title
                    )
                    
                    return {
                        "title": episode.get('title'),
                        "pub_date": episode.get('pub_date'),
                        "link": episode.get('link'),
                        "insights": insights,
                        "source": "assemblyai_cache",
                        "transcript_length": len(cached_transcript),
                        "cached_at": "cached",
                        "transcript": cached_transcript if include_transcript else None
                    }
        
        # Transcribe with AssemblyAI
        logger.info(f"   🎙️ Transcribing with AssemblyAI: {episode_title}")
        transcript = await transcriber.transcribe_episode(episode, test_mode=test_mode)
        
        if not transcript:
            logger.warning(f"   ⚠️ AssemblyAI transcription failed: {episode_title}")
            return {
                "title": episode.get('title'),
                "pub_date": episode.get('pub_date'),
                "link": episode.get('link'),
                "insights": None,
                "source": "assemblyai_failed",
                "transcript_length": 0,
                "error": "Transcription failed"
            }
        
        # Generate AI insights
        logger.info(f"   🤖 Generating insights: {episode_title}")
        episode_url = episode.get('link', '') or episode.get('enclosure_url', '')
        insights = await transcriber.get_transcript_summary(transcript, episode_title, episode_url)
        
        return {
            "title": episode.get('title'),
            "pub_date": episode.get('pub_date'),
            "link": episode.get('link'),
            "insights": insights,
            "source": "assemblyai_transcript",
            "transcript_length": len(transcript),
            "transcript": transcript if include_transcript else None
        }
        
    except Exception as e:
        logger.error(f"   ❌ Error processing episode {episode_title}: {e}")
        return {
            "title": episode.get('title'),
            "pub_date": episode.get('pub_date'),
            "link": episode.get('link'),
            "insights": None,
            "source": "assemblyai_error",
            "transcript_length": 0,
            "error": str(e)
        }

async def process_episodes_with_assemblyai_parallel(
    episodes: List[Dict[str, Any]],
    podcast_name: str = "Unknown",
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    Process multiple episodes in parallel with AssemblyAI
    
    Args:
        episodes: List of episode data
        podcast_name: Name of the podcast
        test_mode: If True, limit to first minute for testing
        include_transcripts: If True, include full transcripts in response
        force_refresh: If True, ignore cache and re-transcribe
        
    Returns:
        List of processed episode data
    """
    if not episodes:
        return []
    
    logger.info(f"🎙️ Processing {len(episodes)} episodes with AssemblyAI: {podcast_name}")
    
    # Process episodes in parallel
    tasks = []
    for episode in episodes:
        task = process_single_episode_with_assemblyai(
            episode=episode,
            podcast_name=podcast_name,
            test_mode=test_mode,
            include_transcript=include_transcripts,
            force_refresh=force_refresh
        )
        tasks.append(task)
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions and failed results
    processed_episodes = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Episode {i} failed with exception: {result}")
            continue
        if result and result.get('insights'):
            processed_episodes.append(result)
        elif result:
            logger.warning(f"Episode {i} processed but no insights: {result.get('title', 'Unknown')}")
    
    logger.info(f"✅ AssemblyAI processed {len(processed_episodes)} episodes successfully")
    return processed_episodes

async def process_podcast_with_assemblyai(
    podcast_id: str,
    episodes_per_podcast: int = 1,
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process a single podcast with AssemblyAI
    
    Args:
        podcast_id: ID of the podcast to process
        episodes_per_podcast: Number of episodes to process
        test_mode: If True, limit to first minute for testing
        include_transcripts: If True, include full transcripts in response
        force_refresh: If True, ignore cache and re-transcribe
        
    Returns:
        Dict with podcast processing results
    """
    try:
        # Get podcast configuration
        podcast_sources = get_all_podcast_sources()
        podcast_config = podcast_sources.get(podcast_id)
        
        if not podcast_config:
            logger.error(f"Podcast not found: {podcast_id}")
            return {"error": f"Podcast not found: {podcast_id}"}
        
        podcast_name = podcast_config.get('name', 'Unknown Podcast')
        rss_url = podcast_config.get('rss_url')
        
        if not rss_url:
            logger.error(f"No RSS URL for podcast: {podcast_name}")
            return {"error": f"No RSS URL for podcast: {podcast_name}"}
        
        logger.info(f"🎙️ Processing podcast: {podcast_name}")
        
        # Parse RSS feed
        episodes = await parse_podcast_feed(rss_url)
        if not episodes:
            logger.warning(f"No episodes found for {podcast_name}")
            return {"error": f"No episodes found for {podcast_name}"}
        
        # Limit to requested number of episodes
        episodes_to_process = episodes[:episodes_per_podcast]
        logger.info(f"Processing {len(episodes_to_process)} episodes from {podcast_name}")
        
        # Process episodes with AssemblyAI
        processed_episodes = await process_episodes_with_assemblyai_parallel(
            episodes=episodes_to_process,
            podcast_name=podcast_name,
            test_mode=test_mode,
            include_transcripts=include_transcripts,
            force_refresh=force_refresh
        )
        
        return {
            "podcast_name": podcast_name,
            "podcast_id": podcast_id,
            "episodes": processed_episodes,
            "total_episodes": len(episodes),
            "processed_episodes": len(processed_episodes),
            "success": len(processed_episodes) > 0
        }
        
    except Exception as e:
        logger.error(f"Error processing podcast {podcast_id}: {e}")
        return {"error": str(e)}

async def process_all_podcasts_with_assemblyai(
    episodes_per_podcast: int = 1,
    test_mode: bool = False,
    include_transcripts: bool = False,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Process all configured podcasts with AssemblyAI
    
    Args:
        episodes_per_podcast: Number of episodes to process per podcast
        test_mode: If True, limit to first minute for testing
        include_transcripts: If True, include full transcripts in response
        force_refresh: If True, ignore cache and re-transcribe
        
    Returns:
        Dict with all podcast processing results
    """
    try:
        podcast_sources = get_all_podcast_sources()
        logger.info(f"🎙️ Processing {len(podcast_sources)} podcasts with AssemblyAI")
        
        # Process all podcasts in parallel
        tasks = []
        for podcast_id in podcast_sources.keys():
            task = process_podcast_with_assemblyai(
                podcast_id=podcast_id,
                episodes_per_podcast=episodes_per_podcast,
                test_mode=test_mode,
                include_transcripts=include_transcripts,
                force_refresh=force_refresh
            )
            tasks.append(task)
        
        # Wait for all podcasts to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Organize results by podcast
        episodes_by_podcast = {}
        total_episodes = 0
        successful_podcasts = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Podcast {i} failed with exception: {result}")
                continue
            
            if result and result.get('success'):
                podcast_name = result.get('podcast_name', f'Podcast {i}')
                episodes_by_podcast[podcast_name] = result.get('episodes', [])
                total_episodes += len(result.get('episodes', []))
                successful_podcasts += 1
        
        logger.info(f"✅ AssemblyAI processed {successful_podcasts} podcasts, {total_episodes} episodes total")
        
        return {
            "episodes_by_podcast": episodes_by_podcast,
            "total_podcasts": len(podcast_sources),
            "successful_podcasts": successful_podcasts,
            "total_episodes": total_episodes,
            "success": successful_podcasts > 0
        }
        
    except Exception as e:
        logger.error(f"Error processing all podcasts: {e}")
        return {"error": str(e)}


async def cache_all_podcast_transcripts(
    episodes_per_podcast: int = 3,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    Cache transcripts for the last N episodes of each podcast.
    This is a standalone operation for building transcript cache.
    Does NOT generate summaries - just stores raw transcripts.
    
    Args:
        episodes_per_podcast: Number of recent episodes to cache per podcast
        force_refresh: Force re-transcription even if cached
        
    Returns:
        Dict with caching status and stats
    """
    try:
        logger.info(f"🎙️  Starting transcript caching: {episodes_per_podcast} episodes per podcast")
        
        # Get all podcast sources
        podcast_sources_dict = get_all_podcast_sources()
        podcast_sources = list(podcast_sources_dict.values())  # Convert dict to list
        transcriber = AssemblyAITranscriber()
        
        # Track stats
        stats = {
            "podcasts_processed": 0,
            "episodes_cached": 0,
            "episodes_skipped": 0,
            "episodes_failed": 0,
            "total_cost_estimate": 0.0,
            "details": []
        }
        
        # Process each podcast
        for podcast in podcast_sources:
            podcast_name = podcast['name']
            rss_url = podcast['rss_url']
            
            try:
                logger.info(f"\n📡 Processing {podcast_name}...")
                
                # Fetch RSS feed
                episodes = await parse_podcast_feed(rss_url)
                if not episodes:
                    logger.warning(f"No episodes found for {podcast_name}")
                    continue
                
                # Limit to N most recent episodes
                episodes_to_cache = episodes[:episodes_per_podcast]
                
                podcast_stats = {
                    "podcast_name": podcast_name,
                    "episodes_processed": 0,
                    "episodes_cached": 0,
                    "episodes_skipped": 0,
                    "episodes_failed": 0
                }
                
                # Process each episode
                for episode in episodes_to_cache:
                    episode_title = episode.get('title', 'Unknown')
                    episode_url = episode.get('link', '') or episode.get('enclosure_url', '')
                    
                    try:
                        # Check if transcript already exists (unless force refresh)
                        if not force_refresh:
                            cached = await transcriber._get_cached_transcript(episode_url)
                            if cached:
                                logger.info(f"   ⏭️  Skipping (cached): {episode_title[:60]}")
                                podcast_stats["episodes_skipped"] += 1
                                stats["episodes_skipped"] += 1
                                continue
                        
                        # Transcribe episode
                        logger.info(f"   🎙️  Transcribing: {episode_title[:60]}")
                        transcript = await transcriber.transcribe_episode(
                            episode,
                            test_mode=False  # Always full transcription for caching
                        )
                        
                        if transcript:
                            transcript_length = len(transcript)
                            cost_estimate = (transcript_length / 60000) * 0.15  # Rough estimate
                            
                            logger.info(f"   ✅ Cached: {transcript_length} chars (~${cost_estimate:.2f})")
                            podcast_stats["episodes_cached"] += 1
                            stats["episodes_cached"] += 1
                            stats["total_cost_estimate"] += cost_estimate
                        else:
                            logger.warning(f"   ❌ Failed: {episode_title[:60]}")
                            podcast_stats["episodes_failed"] += 1
                            stats["episodes_failed"] += 1
                        
                        podcast_stats["episodes_processed"] += 1
                        
                    except Exception as e:
                        logger.error(f"   ❌ Error processing {episode_title[:60]}: {e}")
                        podcast_stats["episodes_failed"] += 1
                        stats["episodes_failed"] += 1
                
                stats["details"].append(podcast_stats)
                stats["podcasts_processed"] += 1
                
            except Exception as e:
                logger.error(f"Error processing {podcast_name}: {e}")
                continue
        
        # Final summary
        logger.info(f"\n✅ Transcript caching complete!")
        logger.info(f"   Podcasts: {stats['podcasts_processed']}")
        logger.info(f"   Episodes cached: {stats['episodes_cached']}")
        logger.info(f"   Episodes skipped: {stats['episodes_skipped']}")
        logger.info(f"   Episodes failed: {stats['episodes_failed']}")
        logger.info(f"   Estimated cost: ${stats['total_cost_estimate']:.2f}")
        
        return {
            "success": True,
            "stats": stats,
            "message": f"Cached {stats['episodes_cached']} transcripts from {stats['podcasts_processed']} podcasts"
        }
        
    except Exception as e:
        logger.error(f"Error caching transcripts: {e}")
        return {
            "success": False,
            "error": str(e)
        }
