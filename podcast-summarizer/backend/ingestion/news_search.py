"""
News search and summarization using OpenAI.
Searches the web for latest news and generates summaries with takeaways.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# News category configurations
NEWS_CATEGORIES = {
    "ai_news": {
        "name": "AI Product & Strategy News",
        "query": "AI product launch OR AI feature release OR ChatGPT OR Claude OR Gemini OR AI startup OR AI business strategy OR conversational AI OR chatbot OR voice AI OR AI assistant",
        "search_query": "AI product launch feature announcement conversational AI",  # For NewsAPI
        "priority": 1,
        "weight": "heavily focused",
        "focus": "AI product launches, new features, competitive moves, go-to-market strategies, user adoption metrics, pricing changes, API releases, partnership announcements, funding rounds, product-market fit insights, customer case studies, enterprise AI adoption, conversational AI developments, chatbot innovations, voice AI breakthroughs"
    },
    "economic_news": {
        "name": "Economic & Business News",
        "query": "economy OR market OR business OR financial OR stocks",
        "search_query": "economy business market",
        "priority": 2,
        "weight": "medium coverage",
        "focus": "Market trends, economic indicators, major business developments, financial policy"
    },
    "political_news": {
        "name": "Political News",
        "query": "politics OR government OR policy OR election",
        "search_query": "politics government",
        "priority": 3,
        "weight": "brief coverage",
        "focus": "Major political developments, policy changes, government decisions"
    },
    "general_interest": {
        "name": "General Interest & Trending",
        "query": "trending OR viral OR interesting OR breakthrough",
        "search_query": "trending news",
        "priority": 4,
        "weight": "minimal coverage",
        "focus": "Noteworthy stories, cultural trends, unique developments"
    }
}


async def search_news_with_openai(
    category_key: str,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search for news using OpenAI's web search tool.
    Cost: $10/1k calls + input tokens at model rate for gpt-4o-mini
    
    Args:
        category_key: Key from NEWS_CATEGORIES dict
        date: Optional date string for filtering (YYYY-MM-DD)
        
    Returns:
        Dict with search results and summaries
    """
    if category_key not in NEWS_CATEGORIES:
        raise ValueError(f"Unknown category: {category_key}")
    
    category = NEWS_CATEGORIES[category_key]
    
    # If no date provided, use today
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    logger.info(f"🔍 Searching {category['name']} for {date}...")
    
    # Construct search query for past 24 hours
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    search_query = f"{category['query']} news from {yesterday} to {date}"
    
    # System prompt for structured output
    system_prompt = f"""You are a news analyst. Search the web and create a structured summary.

Find 3-5 top news stories about: {category['focus']}
From the past 24 hours.

For each story provide:
- Title
- 2-3 sentence summary
- 1-2 key takeaways
- Source name and URL

Return ONLY valid JSON in this exact format:
{{
  "category": "{category['name']}",
  "date": "{date}",
  "stories": [
    {{
      "title": "Exact headline",
      "summary": "2-3 sentences",
      "takeaways": ["Takeaway 1", "Takeaway 2"],
      "source": "Source name",
      "url": "https://actual-url.com"
    }}
  ]
}}

Focus on credible sources and significant developments."""
    
    user_prompt = f"Search the web for: {search_query}"
    
    try:
        # Use OpenAI's web search tool
        # According to https://platform.openai.com/docs/guides/tools-web-search
        # Web search is enabled by adding the web_search tool
        # Supported models: gpt-4o, gpt-4o-mini, o1-preview, o1-mini
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Most cost-effective model with web search
            messages=[
                {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
            ],
            tools=[{"type": "web_search"}],
            temperature=0.5
        )
        
        # Get the final message content
        message = response.choices[0].message
        content = message.content
        
        # Parse JSON response
        import json
        try:
            result = json.loads(content) if content else {"stories": []}
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON for {category['name']}, trying to extract manually")
            result = {"stories": []}
        
        logger.info(f"✅ Found {len(result.get('stories', []))} stories for {category['name']}")
        
        return {
            "category_key": category_key,
            "category_name": category['name'],
            "priority": category['priority'],
            "date": date,
            "stories": result.get('stories', []),
            "raw_response": content
        }
        
    except Exception as e:
        logger.error(f"❌ Error searching {category['name']}: {e}")
        return {
            "category_key": category_key,
            "category_name": category['name'],
            "priority": category['priority'],
            "date": date,
            "stories": [],
            "error": str(e)
        }


async def search_all_news_categories(
    categories: Optional[List[str]] = None,
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search all news categories in parallel.
    
    Args:
        categories: List of category keys to search (None = all)
        date: Optional date string (YYYY-MM-DD)
        
    Returns:
        Dict with results from all categories
    """
    import asyncio
    
    # Default to all categories if none specified
    if categories is None:
        categories = list(NEWS_CATEGORIES.keys())
    
    logger.info(f"🌍 Searching {len(categories)} news categories...")
    
    # Search all categories in parallel
    tasks = [
        search_news_with_openai(category, date)
        for category in categories
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    news_by_category = {}
    total_stories = 0
    errors = []
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Category search failed: {result}")
            errors.append(str(result))
            continue
        
        category_key = result['category_key']
        news_by_category[category_key] = result
        total_stories += len(result.get('stories', []))
    
    logger.info(f"✅ Collected {total_stories} total stories across {len(news_by_category)} categories")
    
    return {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "total_categories": len(news_by_category),
        "total_stories": total_stories,
        "news_by_category": news_by_category,
        "errors": errors
    }


async def generate_news_briefing(
    news_data: Dict[str, Any]
) -> str:
    """
    Generate a consolidated news briefing from search results.
    
    Args:
        news_data: Output from search_all_news_categories
        
    Returns:
        Formatted briefing text
    """
    system_prompt = """You are a morning briefing writer creating a concise, engaging news summary.

Create a narrative briefing that:
1. Starts with AI news (most detail - this is the primary focus)
2. Includes economic news (moderate detail)
3. Mentions political news (brief)
4. Highlights any unique/interesting stories (minimal)

Style:
- Professional but engaging
- Connect related stories
- Focus on "what this means" not just "what happened"
- Use bullet points for key takeaways
- Include source links where relevant

Keep it concise but insightful. AI news should be 60-70% of the content."""
    
    # Build user prompt with all news data
    news_by_category = news_data.get('news_by_category', {})
    
    prompt_parts = [f"Create a morning news briefing for {news_data.get('date')}.\n\nNews by category:\n"]
    
    # Sort by priority
    sorted_categories = sorted(
        news_by_category.items(),
        key=lambda x: x[1].get('priority', 999)
    )
    
    for category_key, category_data in sorted_categories:
        prompt_parts.append(f"\n## {category_data['category_name']}")
        for story in category_data.get('stories', []):
            prompt_parts.append(f"\n### {story.get('title', 'Untitled')}")
            prompt_parts.append(f"Summary: {story.get('summary', 'No summary')}")
            if story.get('takeaways'):
                prompt_parts.append(f"Takeaways: {', '.join(story['takeaways'])}")
            if story.get('url'):
                prompt_parts.append(f"Link: {story['url']}")
    
    user_prompt = "\n".join(prompt_parts)
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap for briefing generation
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        briefing = response.choices[0].message.content
        logger.info(f"✅ Generated news briefing ({len(briefing)} chars)")
        return briefing
        
    except Exception as e:
        logger.error(f"❌ Error generating briefing: {e}")
        return f"Error generating briefing: {str(e)}"

