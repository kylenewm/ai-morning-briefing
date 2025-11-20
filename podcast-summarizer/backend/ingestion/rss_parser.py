"""
RSS feed parser for podcast episodes.
Handles fetching and parsing podcast RSS feeds.
"""

import feedparser
import httpx
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from ..config import settings
# youtube_fetcher has been removed - YouTube transcripts no longer used (switched to AssemblyAI)
# from .youtube_fetcher import get_youtube_transcript, extract_video_id
# youtube_search has been archived - no longer used

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_youtube_link(entry: Dict[str, Any]) -> Optional[str]:
    """
    Extract YouTube URL from RSS feed entry.
    
    Looks in:
    - Entry link field
    - Entry description/summary
    
    Args:
        entry: Feed entry dictionary
        
    Returns:
        Optional[str]: YouTube URL or None if not found
    """
    # Check the link field first
    link = entry.get("link", "")
    if "youtube.com" in link or "youtu.be" in link:
        return link
    
    # Check description for YouTube links
    description = entry.get("summary", "") + entry.get("content", [{}])[0].get("value", "")
    
    youtube_pattern = r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[a-zA-Z0-9_-]{11})'
    match = re.search(youtube_pattern, description)
    
    if match:
        return match.group(1)
    
    return None


async def parse_podcast_feed(
    feed_url: str,
    max_episodes: int = None,
    fetch_transcripts: bool = False,
    youtube_channel: str = None,
    require_youtube: bool = False
) -> List[Dict[str, Any]]:
    """
    Parse a podcast RSS feed and extract episode information.
    
    Args:
        feed_url: URL of the RSS feed to parse
        max_episodes: Maximum number of episodes to return (default: from settings)
        fetch_transcripts: Whether to fetch YouTube transcripts (default: False)
        require_youtube: If True, keep searching older episodes until finding ones with YouTube URLs
        
    Returns:
        List[Dict[str, Any]]: List of episode dictionaries containing:
            - title: Episode title
            - description: Episode description
            - pub_date: Publication date (ISO format string)
            - link: Episode webpage link
            - audio_url: Direct link to audio file
            - duration: Episode duration (if available)
            - youtube_url: YouTube video URL (if found)
            - transcript: Full transcript text (if fetch_transcripts=True and available)
            
    Raises:
        httpx.HTTPError: If the feed cannot be fetched
        Exception: For other parsing errors
    """
    if max_episodes is None:
        max_episodes = settings.MAX_EPISODES_PER_FEED
    
    try:
        # Fetch the feed content
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
            feed_content = response.text
        
        # Parse the feed
        feed = feedparser.parse(feed_content)
        
        if feed.bozo:
            logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
        
        episodes = []
        episodes_with_youtube = 0
        
        # If require_youtube, search through more episodes until we find enough with YouTube URLs
        search_limit = max_episodes * 10 if require_youtube else max_episodes
        max_to_check = min(search_limit, len(feed.entries))
        
        logger.info(f"📡 Searching through up to {max_to_check} episodes (require_youtube={require_youtube})")
        
        # Extract episode information
        for idx, entry in enumerate(feed.entries[:max_to_check]):
            # Extract YouTube URL from RSS
            youtube_url = extract_youtube_link(entry)
            
            # If require_youtube is True, skip episodes without YouTube URLs
            if require_youtube and not youtube_url:
                continue
            
            episode = {
                "title": entry.get("title", "Untitled Episode"),
                "description": _clean_description(entry.get("summary", "")),
                "pub_date": _parse_date(entry),
                "link": entry.get("link", ""),
                "audio_url": _extract_audio_url(entry),
                "duration": _extract_duration(entry),
                "youtube_url": youtube_url,
                "transcript": None,
            }
            
            # Fetch transcript if requested and YouTube URL found
            # DISABLED: YouTube transcripts no longer used - switched to AssemblyAI
            # if fetch_transcripts and youtube_url:
            #     logger.info(f"   📹 Found YouTube URL for: {episode['title'][:50]}...")
            #     cookies_path = settings.YOUTUBE_COOKIES_PATH if settings.YOUTUBE_COOKIES_PATH else None
            #     transcript = await get_youtube_transcript(youtube_url, cookies_path=cookies_path)
            #     episode["transcript"] = transcript
            #     if transcript:
            #         episodes_with_youtube += 1
            
            episodes.append(episode)
            
            # Stop when we have enough episodes
            if len(episodes) >= max_episodes:
                break
        
        logger.info(f"✅ Parsed {len(episodes)} episodes ({episodes_with_youtube} with transcripts) from {feed_url}")
        return episodes
    
    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching feed {feed_url}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error parsing feed {feed_url}: {str(e)}")
        raise


def _clean_description(description: str) -> str:
    """
    Clean HTML tags and extra whitespace from description.
    
    Args:
        description: Raw description text
        
    Returns:
        str: Cleaned description text
    """
    from bs4 import BeautifulSoup
    
    # Remove HTML tags
    soup = BeautifulSoup(description, "html.parser")
    text = soup.get_text()
    
    # Clean up whitespace
    text = " ".join(text.split())
    
    return text


def _parse_date(entry: Dict[str, Any]) -> str:
    """
    Parse publication date from feed entry.
    
    Args:
        entry: Feed entry dictionary
        
    Returns:
        str: ISO format date string
    """
    try:
        # Try to get published_parsed or updated_parsed
        time_tuple = entry.get("published_parsed") or entry.get("updated_parsed")
        
        if time_tuple:
            dt = datetime(*time_tuple[:6])
            return dt.isoformat()
        
        # Fallback to raw string
        return entry.get("published", entry.get("updated", ""))
    
    except Exception as e:
        logger.warning(f"Error parsing date: {str(e)}")
        return ""


def _extract_audio_url(entry: Dict[str, Any]) -> str:
    """
    Extract audio file URL from feed entry.
    
    Args:
        entry: Feed entry dictionary
        
    Returns:
        str: Audio file URL or empty string if not found
    """
    # Check for enclosures (most common for podcasts)
    if "enclosures" in entry and entry.enclosures:
        for enclosure in entry.enclosures:
            if "audio" in enclosure.get("type", ""):
                return enclosure.get("href", "")
    
    # Check for media_content
    if "media_content" in entry:
        for media in entry.media_content:
            if "audio" in media.get("type", ""):
                return media.get("url", "")
    
    # Check for links with audio type
    if "links" in entry:
        for link in entry.links:
            if "audio" in link.get("type", ""):
                return link.get("href", "")
    
    return ""


def _extract_duration(entry: Dict[str, Any]) -> Optional[str]:
    """
    Extract episode duration from feed entry.
    
    Args:
        entry: Feed entry dictionary
        
    Returns:
        Optional[str]: Duration string (e.g., "01:23:45") or None
    """
    # Check iTunes duration
    if "itunes_duration" in entry:
        return entry["itunes_duration"]
    
    # Check other common duration fields
    if "duration" in entry:
        return entry["duration"]
    
    return None


async def fetch_all_feeds(feed_urls: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch and parse multiple podcast feeds concurrently.
    
    Args:
        feed_urls: List of RSS feed URLs to parse
        
    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary mapping feed URLs to episode lists
    """
    import asyncio
    
    results = {}
    
    async def fetch_one(url: str) -> tuple[str, List[Dict[str, Any]] | None]:
        try:
            episodes = await parse_podcast_feed(url)
            return url, episodes
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return url, None
    
    # Fetch all feeds concurrently
    tasks = [fetch_one(url) for url in feed_urls]
    feed_results = await asyncio.gather(*tasks)
    
    # Build results dictionary
    for url, episodes in feed_results:
        if episodes is not None:
            results[url] = episodes
    
    return results

