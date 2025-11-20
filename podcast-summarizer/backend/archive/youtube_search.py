"""
YouTube search functionality to find podcast episodes when not in RSS.
Searches YouTube by episode title + channel name.
"""

import httpx
import re
import logging
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


async def search_youtube_for_episode(
    episode_title: str,
    channel_name: str,
    max_results: int = 5
) -> Optional[str]:
    """
    Search YouTube for a podcast episode by title and channel.
    
    Uses YouTube's search page scraping as a fallback when API is not available.
    
    Args:
        episode_title: Title of the podcast episode
        channel_name: YouTube channel name (e.g., "@lennyspodcast")
        max_results: Number of results to check (default: 5)
        
    Returns:
        Optional[str]: YouTube video URL if found, None otherwise
    """
    try:
        # Clean up title for search
        search_query = f"{episode_title} {channel_name}"
        
        # Simple YouTube search URL (no API needed)
        search_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(search_url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            
            if response.status_code != 200:
                logger.warning(f"YouTube search returned {response.status_code}")
                return None
            
            # Extract video IDs from the HTML
            html_content = response.text
            video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html_content)
            
            if video_ids:
                # Return first result as YouTube URL
                video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
                logger.info(f"Found YouTube video: {video_url}")
                return video_url
            
            logger.warning(f"No YouTube results found for: {episode_title}")
            return None
            
    except Exception as e:
        logger.error(f"Error searching YouTube: {str(e)}")
        return None


async def get_youtube_url_for_episode(
    episode_title: str,
    episode_link: str,
    channel_name: Optional[str] = None
) -> Optional[str]:
    """
    Get YouTube URL for an episode using multiple methods.
    
    1. Check if episode link is already a YouTube URL
    2. Search YouTube by episode title
    
    Args:
        episode_title: Episode title
        episode_link: RSS episode link
        channel_name: YouTube channel name for searching
        
    Returns:
        Optional[str]: YouTube URL if found
    """
    # Method 1: Check if link is already YouTube
    if "youtube.com" in episode_link or "youtu.be" in episode_link:
        return episode_link
    
    # Method 2: Search YouTube if we have a channel name
    if channel_name:
        return await search_youtube_for_episode(episode_title, channel_name)
    
    return None


def extract_key_terms_from_title(title: str) -> str:
    """
    Extract key search terms from episode title.
    Removes common podcast intro words to improve search accuracy.
    
    Args:
        title: Episode title
        
    Returns:
        str: Cleaned title for searching
    """
    # Remove common podcast prefixes
    prefixes_to_remove = [
        r'^Episode \d+:?\s*',
        r'^#\d+:?\s*',
        r'^\d+\.\s*',
        r'^Ep\s*\d+:?\s*',
    ]
    
    cleaned = title
    for pattern in prefixes_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()

