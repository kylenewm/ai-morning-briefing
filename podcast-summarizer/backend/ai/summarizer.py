"""
AI summarization module using OpenAI API.

Supports multiple summarization methods:
- summarize_description: Summarize episode description from RSS feed
- parse_transcript: Parse and summarize transcript from web (future)
- transcribe_audio: Transcribe audio offline and summarize (future)
"""

from typing import Dict, Any
import logging
from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None


async def summarize_description(episode: Dict[str, Any]) -> str:
    """
    DEPRECATED: No longer used in main pipeline.
    
    Previously used as fallback when transcripts unavailable.
    Now we skip episodes without transcripts to maintain quality.
    Kept for reference or potential future use.
    
    Summarize a podcast episode from its RSS description.
    
    Args:
        episode: Episode dictionary with 'title' and 'description'
        
    Returns:
        str: The generated summary (3-4 key points)
    """
    logger.warning("summarize_description() is deprecated - episodes without transcripts are now skipped")
    if not client:
        logger.warning("OpenAI API key not configured")
        return "⚠️ OpenAI API key not configured. Add OPENAI_API_KEY to .env file."
    
    try:
        title = episode.get("title", "Unknown Episode")
        description = episode.get("description", "")
        
        if not description:
            return "⚠️ No description available for this episode."
        
        prompt = f"""Summarize this podcast episode in 3-4 concise bullet points for a morning briefing.

Episode Title: {title}

Episode Description:
{description}

Focus on:
- Key topics discussed
- Main insights or takeaways
- Actionable information

Format as bullet points."""

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)  # Fast and cost-effective
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates concise, informative summaries of podcast episodes for busy professionals."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=250,
            temperature=0.7,
        )
        
        summary = response.choices[0].message.content
        logger.info(f"Successfully summarized episode: {title}")
        return summary
        
    except Exception as e:
        logger.error(f"Error summarizing episode: {str(e)}")
        return f"⚠️ Error generating summary: {str(e)}"


async def summarize_episode(episode: Dict[str, Any], method: str = "summarize_description") -> str:
    """
    DEPRECATED: No longer used in main pipeline.
    
    Dispatcher function for different summarization methods.
    Previously used to provide fallback summaries when transcripts failed.
    
    Kept for backward compatibility but not called in current pipeline.
    Episodes without transcripts are now skipped to maintain quality.
    
    Args:
        episode: Episode dictionary with metadata
        method: Summarization method ("summarize_description", "parse_transcript", "transcribe_audio")
        
    Returns:
        str: The generated summary
    """
    logger.warning("summarize_episode() is deprecated - not used in current pipeline")
    if method == "summarize_description":
        return await summarize_description(episode)
    
    elif method == "parse_transcript":
        # TODO: Implement transcript parsing from web pages
        logger.warning("Transcript parsing not yet implemented")
        return "⚠️ Transcript parsing coming soon. Using description for now."
    
    elif method == "transcribe_audio":
        # TODO: Implement offline audio transcription
        logger.warning("Audio transcription not yet implemented")
        return "⚠️ Audio transcription coming soon. Using description for now."
    
    else:
        return f"⚠️ Unknown summarization method: {method}"


async def generate_briefing(episodes_by_podcast: Dict[str, list[Dict[str, Any]]]) -> str:
    """
    Generate a morning briefing from multiple podcast episodes.
    
    Args:
        episodes_by_podcast: Dictionary mapping podcast names to lists of episodes with summaries
        
    Returns:
        str: The formatted morning briefing text
    """
    if not client:
        logger.warning("OpenAI API key not configured")
        return "⚠️ OpenAI API key not configured for briefing generation."
    
    try:
        # Format all summaries into a single context
        context = "# Recent Podcast Episodes\n\n"
        
        for podcast_name, episodes in episodes_by_podcast.items():
            context += f"## {podcast_name}\n\n"
            for ep in episodes:
                context += f"### {ep.get('title', 'Unknown')}\n"
                context += f"{ep.get('summary', 'No summary available')}\n\n"
        
        prompt = f"""Write a morning briefing from these podcast episodes. 

{context}

Write naturally - like a smart colleague giving you the rundown:
- What were the most interesting points?
- Any common themes across episodes?
- Just the facts and ideas discussed, not advice

Keep it conversational and 2-3 paragraphs."""

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at synthesizing information from multiple sources into concise, engaging briefings."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=500,
            temperature=0.7,
        )
        
        briefing = response.choices[0].message.content
        logger.info("Successfully generated morning briefing")
        return briefing
        
    except Exception as e:
        logger.error(f"Error generating briefing: {str(e)}")
        return f"⚠️ Error generating briefing: {str(e)}"

