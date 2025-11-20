"""
AI insight extraction module using OpenAI API.
Extracts actionable insights from podcast transcripts.
"""

from typing import Dict, Any, Optional
import logging
from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None


async def extract_key_insights(transcript: str, episode_title: str, test_mode: bool = False) -> Dict[str, Any]:
    """
    Extract 8-10 key actionable insights from a podcast transcript using OpenAI.
    
    Args:
        transcript: Full transcript text
        episode_title: Title of the episode
        test_mode: If True, truncates transcript to TEST_TRANSCRIPT_LENGTH for quick testing
        
    Returns:
        Dict[str, Any]: Structured response with insights and metadata
    """
    if not client:
        logger.error("OpenAI API key not configured")
        return {
            "success": False,
            "error": "OpenAI API key not configured. Add OPENAI_API_KEY to .env file.",
            "insights": None
        }
    
    if not transcript:
        return {
            "success": False,
            "error": "No transcript provided",
            "insights": None
        }
    
    try:
        # Use full transcript unless in test mode
        if test_mode:
            test_length = settings.TEST_TRANSCRIPT_LENGTH
            full_transcript = transcript[:test_length]
            logger.info(f"🧪 TEST MODE: Truncating transcript to {test_length} chars (original: {len(transcript)} chars)")
        else:
            full_transcript = transcript
        
        system_prompt = """You are analyzing a podcast transcript. Extract the most interesting and useful insights.

Don't tell people what to think or do - just extract what was said clearly and accurately.
Let the content speak for itself."""

        user_prompt = f"""Extract 5-7 key insights from this podcast. Write naturally - like you're telling a friend what you learned.

Episode: {episode_title}

Transcript:
{full_transcript}

---

For each insight, use this structure:

## [NUMBER]. [CLEAR TITLE]

**The Idea:**
A paragraph (4-6 sentences) explaining:
- What the concept/framework/tactic actually is
- The context and why the speaker thinks it's important
- The underlying logic or reasoning

**Example/Evidence:**
A paragraph (3-4 sentences) with:
- Specific examples, data, or stories mentioned
- Real companies, products, or people discussed
- Actual numbers, metrics, or results if given

**Practical Details:**
A paragraph (3-4 sentences) covering:
- How to actually do this or apply it
- Challenges or nuances mentioned
- Tips or variations discussed

---

FOCUS ON:
✓ Named frameworks or mental models mentioned
✓ Specific tactics with numbers/outcomes
✓ Data points and metrics with context
✓ Step-by-step processes explained
✓ Surprising or counterintuitive points
✓ Tools, products, or resources discussed

PRIORITIZE:
• Non-obvious insights over common knowledge
• Specific details over generic advice
• Real numbers and examples over vague statements
• What actually happened vs what "should" happen

FORMAT:
- Number each insight (1-7)
- Use the 3 sections (Idea/Example/Practical) for each
- Write in paragraphs, not bullet points
- Be accurate to what was actually said

Don't add your own strategic advice or interpretations - just capture what the podcast covered clearly and thoroughly."""

        response = await client.chat.completions.create(
            model="gpt-5-mini",  # Reasoning model with internal thinking (like o1-mini)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # Note: gpt-5-mini is a reasoning model - no temperature/max_tokens params
            # It uses internal reasoning tokens before generating output
        )
        
        insights_text = response.choices[0].message.content
        
        logger.info(f"Successfully extracted insights from transcript ({len(transcript)} chars)")
        
        return {
            "success": True,
            "insights": insights_text,
            "transcript_length": len(full_transcript),
            "original_transcript_length": len(transcript),
            "truncated": test_mode,
            "test_mode": test_mode,
            "model": "gpt-5-mini"
        }
        
    except Exception as e:
        logger.error(f"Error extracting insights: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "insights": None
        }


async def extract_insights_from_episode(episode: Dict[str, Any], test_mode: bool = False) -> Dict[str, Any]:
    """
    Extract insights from an episode dictionary that includes a transcript.
    
    Args:
        episode: Episode dictionary with 'title' and 'transcript' fields
        test_mode: If True, truncates transcript for quick testing
        
    Returns:
        Dict[str, Any]: Episode data enriched with insights
    """
    title = episode.get("title", "Unknown Episode")
    transcript = episode.get("transcript")
    
    if not transcript:
        return {
            **episode,
            "insights": {
                "success": False,
                "error": "No transcript available for this episode",
                "insights": None
            }
        }
    
    insights_result = await extract_key_insights(transcript, title, test_mode=test_mode)
    
    return {
        **episode,
        "insights": insights_result
    }

