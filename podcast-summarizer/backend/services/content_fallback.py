"""
Content fallback service for morning briefing.
Implements scalable fallback logic when primary sources have no content.
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ContentFallbackService:
    """
    Manages fallback logic for content sources in morning briefing.
    Tries multiple time periods and eventually alternative sources.
    """
    
    def __init__(self):
        self.fallback_periods = [
            {'hours': 24, 'label': None},  # Today (no label needed)
            {'hours': 48, 'label': 'Previous Day Summary'},
            {'hours': 72, 'label': '2-Day Summary'},
        ]
    
    async def fetch_with_fallback(
        self,
        source_name: str,
        fetch_function: Callable[[int], Awaitable[Dict[str, Any]]],
        min_stories: int = 1,
        alternative_sources: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Fetch content with automatic fallback to previous days.
        
        Args:
            source_name: Name of source (for logging)
            fetch_function: Async function that takes hours_ago and returns data
            min_stories: Minimum stories required to consider success
            alternative_sources: List of alternative source configs to try
            
        Returns:
            Dict with content and metadata about fallback used
        """
        logger.info(f"🔄 Fetching {source_name} with fallback...")
        
        # Try each time period
        for period in self.fallback_periods:
            hours_ago = period['hours']
            label = period['label']
            
            try:
                logger.info(f"   Trying {source_name} from past {hours_ago} hours...")
                result = await fetch_function(hours_ago)
                
                # Check if we got enough content
                story_count = result.get('total_stories', 0)
                if story_count >= min_stories:
                    logger.info(f"   ✅ Found {story_count} stories from past {hours_ago} hours")
                    
                    # Add fallback metadata if we used a fallback period
                    if label:
                        result['fallback_used'] = True
                        result['fallback_label'] = label
                        result['fallback_hours'] = hours_ago
                        logger.info(f"   📅 Labeling as: {label}")
                    else:
                        result['fallback_used'] = False
                    
                    return result
                else:
                    logger.info(f"   ⚠️  Only {story_count} stories - trying longer period...")
                    
            except Exception as e:
                logger.warning(f"   ❌ {source_name} failed at {hours_ago}h: {e}")
                continue
        
        # If all time periods failed, try alternative sources
        if alternative_sources:
            logger.info(f"   🔀 Trying alternative sources for {source_name}...")
            for alt_source in alternative_sources:
                try:
                    alt_name = alt_source.get('name', 'unknown')
                    alt_function = alt_source.get('function')
                    
                    if not alt_function:
                        continue
                    
                    logger.info(f"      Trying {alt_name}...")
                    result = await alt_function()
                    
                    story_count = result.get('total_stories', 0)
                    if story_count >= min_stories:
                        logger.info(f"      ✅ Found {story_count} stories from {alt_name}")
                        result['fallback_used'] = True
                        result['fallback_label'] = f"From {alt_name}"
                        result['fallback_source'] = alt_name
                        return result
                        
                except Exception as e:
                    logger.warning(f"      ❌ {alt_name} failed: {e}")
                    continue
        
        # Everything failed - return empty result
        logger.warning(f"   ❌ All fallback attempts failed for {source_name}")
        return {
            'total_stories': 0,
            'fallback_used': True,
            'fallback_label': 'No content available',
            'error': 'All sources and fallback periods failed'
        }
    
    async def fetch_newsletters_with_fallback(
        self,
        newsletter_fetcher: Callable[[int], Awaitable[Dict[str, Any]]],
        alternative_sources: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Fetch newsletters with automatic fallback.
        
        Args:
            newsletter_fetcher: Function to fetch newsletters (takes hours_ago)
            alternative_sources: Optional alternative sources (e.g., Exa search, web scraping)
            
        Returns:
            Newsletter data with fallback metadata
        """
        return await self.fetch_with_fallback(
            source_name='newsletters',
            fetch_function=newsletter_fetcher,
            min_stories=1,
            alternative_sources=alternative_sources
        )
    
    async def fetch_news_with_fallback(
        self,
        news_fetcher: Callable[[int], Awaitable[Dict[str, Any]]],
        alternative_sources: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Fetch news with automatic fallback.
        
        Args:
            news_fetcher: Function to fetch news (takes hours_ago)
            alternative_sources: Optional alternative sources (e.g., Exa AI, RSS aggregators)
            
        Returns:
            News data with fallback metadata
        """
        return await self.fetch_with_fallback(
            source_name='news',
            fetch_function=news_fetcher,
            min_stories=3,
            alternative_sources=alternative_sources
        )
    
    def format_content_with_fallback_label(
        self,
        content: Dict[str, Any],
        content_type: str = 'stories'
    ) -> Dict[str, Any]:
        """
        Add fallback label to content if needed.
        
        Args:
            content: Content dict with potential fallback metadata
            content_type: Type of content for formatting
            
        Returns:
            Content with fallback label added where appropriate
        """
        if not content.get('fallback_used'):
            return content
        
        fallback_label = content.get('fallback_label', 'Previous Day')
        
        # Add label to the content structure
        if content_type == 'newsletters':
            if 'detailed_stories' in content:
                # Add notice to first story or as separate field
                content['fallback_notice'] = f"📅 {fallback_label}"
        elif content_type == 'news':
            if 'stories' in content:
                content['fallback_notice'] = f"📅 {fallback_label}"
        
        return content


# Global instance
fallback_service = ContentFallbackService()

