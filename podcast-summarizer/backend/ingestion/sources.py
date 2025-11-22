"""
Podcast source configurations.
Contains metadata for all podcasts to be monitored and summarized.

Current Strategy:
- All podcasts use AssemblyAI transcription
- Downloads MP3 files from RSS feeds
- Transcribes using AssemblyAI API
- All transcripts cached permanently in Supabase to avoid re-transcription costs
- Extracts actionable insights using OpenAI GPT-4o-mini

Features:
- RSS feed parsing with MP3 extraction
- High-quality transcription via AssemblyAI
- Permanent caching in Supabase database
- Parallel processing of multiple podcasts
- Priority system (primary vs secondary podcasts)
"""

from typing import Dict, Any, Optional, List


PODCAST_SOURCES: Dict[str, Dict[str, Any]] = {
    "lennys_podcast": {
        "name": "Lenny's Podcast",
        "rss_url": "https://api.substack.com/feed/podcast/10845/s/198869.rss",  # Lenny's Substack podcast feed
        "has_transcripts": True,
        "method": "assemblyai_transcript",
        "category": "Product Management",
        "description": "Product | Growth | Career advice from world-class leaders",
        "priority": "primary",  # Show detailed summaries in briefing
    },
    "mlops_community": {
        "name": "MLOps.community Podcast",
        "rss_url": "https://anchor.fm/s/174cb1b8/podcast/rss",
        "has_transcripts": True,
        "method": "assemblyai_transcript",
        "category": "MLOps",
        "description": "Conversations about ML operations and production ML systems",
        "priority": "primary",  # Show detailed summaries in briefing
    },
    "twiml_ai": {
        "name": "TWiML AI Podcast",
        "rss_url": "https://feeds.megaphone.fm/MLN2155636147",  # Updated working URL
        "has_transcripts": True,
        "method": "assemblyai_transcript",
        "category": "AI/ML",
        "description": "This Week in Machine Learning & AI",
        "priority": "primary",  # Show detailed summaries in briefing
    },
    # Removed: "ai_daily_brief" - The AI Daily Brief (lacks in-depth substance, redundant with TLDR AI + Exa search)
    "data_skeptic": {
        "name": "Data Skeptic",
        "rss_url": "https://dataskeptic.libsyn.com/rss",  # Kyle Polich's Data Skeptic
        "has_transcripts": True,
        "method": "assemblyai_transcript",  # Use AssemblyAI for transcription
        "category": "Data Science",
        "description": "Data science, statistics, machine learning, and critical thinking",
        "priority": "secondary",  # Show only brief links in briefing
    },
    "dataframed": {
        "name": "DataFramed by DataCamp",
        "rss_url": "https://feeds.captivate.fm/dataframed/",  # DataCamp's DataFramed podcast
        "has_transcripts": True,
        "method": "assemblyai_transcript",  # Use AssemblyAI for transcription
        "category": "Data Science",
        "description": "Data science trends, tools, and best practices with industry experts",
        "priority": "secondary",  # Show only brief links in briefing
    },
}


def get_all_podcast_sources() -> Dict[str, Dict[str, Any]]:
    """
    Get all configured podcast sources.
    
    Returns:
        Dict[str, Dict[str, Any]]: Dictionary of all podcast configurations
    """
    return PODCAST_SOURCES


def get_podcast_by_id(podcast_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific podcast configuration by ID.
    
    Args:
        podcast_id: The unique identifier for the podcast
        
    Returns:
        Optional[Dict[str, Any]]: Podcast configuration or None if not found
    """
    return PODCAST_SOURCES.get(podcast_id)


def get_rss_feeds() -> List[str]:
    """
    Get all RSS feed URLs.
    
    Returns:
        List[str]: List of RSS feed URLs
    """
    return [source["rss_url"] for source in PODCAST_SOURCES.values()]

