"""
News search using Perplexity AI API.
Perplexity provides real-time search with citations and sources.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Perplexity API
PERPLEXITY_API_BASE = "https://api.perplexity.ai"


async def search_perplexity(
    query: str,
    api_key: Optional[str] = None,
    model: str = "sonar"  # Online search model
) -> Dict[str, Any]:
    """
    Search using Perplexity AI API.
    
    Args:
        query: Search query
        api_key: Perplexity API key
        model: Model to use (sonar models have online search)
        
    Returns:
        Dict with response and citations
    """
    api_key = api_key or settings.PERPLEXITY_API_KEY
    
    if not api_key:
        logger.warning("⚠️  No PERPLEXITY_API_KEY set")
        return {}
    
    url = f"{PERPLEXITY_API_BASE}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": query
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"✅ Perplexity search completed")
            return data
            
    except httpx.HTTPError as e:
        logger.error(f"❌ Perplexity HTTP error: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Perplexity error: {e}")
        return {}


async def search_news_with_perplexity(
    category_key: str,
    category_config: Dict[str, Any],
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search for news in a category using Perplexity.
    
    Args:
        category_key: Category identifier
        category_config: Category configuration dict
        date: Optional date filter
        
    Returns:
        Dict with category news
    """
    logger.info(f"🔮 Perplexity searching {category_config['name']}...")
    
    # Calculate target date range (handle Monday = weekend news)
    now = datetime.now()
    
    # If Monday, get Friday-Sunday news. Otherwise just yesterday.
    if now.weekday() == 0:  # Monday
        # Get Friday, Saturday, Sunday
        start_date = now - timedelta(days=3)  # Friday
        date_range_str = f"{start_date.strftime('%A %B %d')} through {(now - timedelta(days=1)).strftime('%A %B %d, %Y')}"
        target_dates = [
            (now - timedelta(days=3)).strftime("%Y-%m-%d"),  # Friday
            (now - timedelta(days=2)).strftime("%Y-%m-%d"),  # Saturday  
            (now - timedelta(days=1)).strftime("%Y-%m-%d")   # Sunday
        ]
    else:
        # Just yesterday
        yesterday = now - timedelta(days=1)
        date_range_str = yesterday.strftime("%A, %B %d, %Y")
        target_dates = [yesterday.strftime("%Y-%m-%d")]
    
    today_str = now.strftime("%A, %B %d, %Y")
    
    search_query = f"""Search for AI news published on {date_range_str} (today is {today_str}).

TARGET: AI Product Manager who needs strategic insights.

FIND 10-15 articles about:
- AI product launches with metrics, adoption, or competitive impact
- Technical breakthroughs and research with business implications
- Market analysis, funding rounds, valuations, business model changes
- Regulatory developments affecting AI products
- User adoption trends, performance data, market share
- Strategic partnerships with measurable impact
- Controversies, challenges, or failures in AI
- Competitive dynamics between major AI companies

INCLUDE business-relevant news even if it's announcements, but prioritize:
- Stories with specific numbers, metrics, or data
- Analysis and commentary over pure press releases
- Strategic implications for AI product development
- Market impact and competitive positioning

Return ONLY valid JSON:
{{
  "stories": [
    {{
      "title": "exact article title",
      "summary": "2-3 sentence summary with key details/numbers",
      "takeaways": ["strategic insight 1", "strategic insight 2"],
      "source": "publication name",
      "url": "https://full-url",
      "published_date": "YYYY-MM-DD"
    }}
  ]
}}

Include published_date in YYYY-MM-DD format."""
    
    # Search with Perplexity
    result = await search_perplexity(
        query=search_query,
        model="sonar"  # Online search model
    )
    
    if not result:
        logger.warning(f"⚠️  No Perplexity results for {category_config['name']}")
        return {
            "category_key": category_key,
            "category_name": category_config['name'],
            "priority": category_config['priority'],
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "stories": []
        }
    
    # Extract response and citations
    try:
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = result.get("citations", [])
        
        # Try to parse JSON from response
        import json
        
        # Extract JSON if wrapped in markdown
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content
        
        parsed = json.loads(json_str)
        all_stories = parsed.get("stories", [])
        
        logger.info(f"📰 Perplexity returned {len(all_stories)} articles, filtering for date range...")
        
        # Add citations to stories if available
        if citations and all_stories:
            for story in all_stories:
                if not story.get("url") and citations:
                    story["url"] = citations[0]  # Add first citation if no URL
        
        # Filter and score stories by date relevance
        scored_stories = []
        for story in all_stories:
            score = 0
            story_date = story.get("published_date", "")
            
            # Check if date matches our target dates
            if story_date in target_dates:
                score += 10  # Perfect match
            elif story_date:
                # Parse and check if within last 3 days
                try:
                    from dateutil import parser as date_parser
                    parsed_date = date_parser.parse(story_date)
                    days_old = (now - parsed_date).days
                    if days_old <= 1:
                        score += 8  # Yesterday
                    elif days_old <= 3:
                        score += 5  # Last 3 days
                    elif days_old <= 7:
                        score += 2  # Last week
                except:
                    score += 1  # Has a date but couldn't parse
            
            # Check URL for date indicators
            url = story.get("url", "")
            for target_date in target_dates:
                # Check for YYYY/MM/DD or YYYY-MM-DD in URL
                if target_date.replace("-", "/") in url or target_date in url:
                    score += 5
                    break
            
            scored_stories.append((score, story))
        
        # Sort by score (highest first) and take top 5
        scored_stories.sort(key=lambda x: x[0], reverse=True)
        stories = [story for score, story in scored_stories[:5]]
        
        logger.info(f"✅ Filtered to {len(stories)} stories from target date range")
        if stories:
            logger.info(f"   Top story: {stories[0].get('title', 'Unknown')[:60]}... (date: {stories[0].get('published_date', 'N/A')})")
        
        # Save stories to database
        for story in stories:
            try:
                from ..database import CacheService
                
                # Format key points as text
                key_points = story.get('key_points', story.get('takeaways', []))
                key_points_text = "\n".join([f"• {point}" for point in key_points])
                insight_text = f"{story.get('summary', '')}\n\nKey Points:\n{key_points_text}"
                
                CacheService.save_content_and_insight(
                    source_type="news",
                    source_name="Perplexity",
                    item_url=story.get('url', f"perplexity_{category_key}_{story.get('title', '')[:50]}"),
                    title=story.get('title', 'Unknown'),
                    transcript=None,
                    insight=insight_text,
                    youtube_url=None,
                    published_date=story.get('published_date'),
                    description=story.get('summary', ''),
                    model_name="perplexity-sonar",
                    test_mode=False
                )
            except Exception as cache_err:
                logger.warning(f"⚠️  Failed to cache Perplexity story: {cache_err}")
        
        logger.info(f"✅ Perplexity found {len(stories)} stories for {category_config['name']}")
        
        return {
            "category_key": category_key,
            "category_name": category_config['name'],
            "priority": category_config['priority'],
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "stories": stories,
            "citations": citations
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️  Could not parse JSON from Perplexity response: {e}")
        logger.warning(f"   Response content (first 500 chars): {content[:500]}")
        return {
            "category_key": category_key,
            "category_name": category_config['name'],
            "priority": category_config['priority'],
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "stories": []
        }
    except Exception as e:
        logger.error(f"❌ Error processing Perplexity results: {e}")
        return {
            "category_key": category_key,
            "category_name": category_config['name'],
            "priority": category_config['priority'],
            "date": date or datetime.now().strftime("%Y-%m-%d"),
            "stories": []
        }


async def search_all_categories_with_perplexity(
    categories: Dict[str, Dict[str, Any]],
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search all news categories using Perplexity in parallel.
    
    Args:
        categories: Dict of category configs
        date: Optional date filter
        
    Returns:
        Dict with all news results
    """
    import asyncio
    
    logger.info(f"🔮 Perplexity searching {len(categories)} categories...")
    
    # Create tasks for parallel execution
    tasks = [
        search_news_with_perplexity(cat_key, cat_config, date)
        for cat_key, cat_config in categories.items()
    ]
    
    # Run all searches in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    news_by_category = {}
    total_stories = 0
    errors = []
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Perplexity search failed: {result}")
            errors.append(str(result))
            continue
        
        category_key = result["category_key"]
        news_by_category[category_key] = result
        total_stories += len(result.get("stories", []))
    
    logger.info(f"✅ Perplexity collected {total_stories} stories across {len(news_by_category)} categories")
    
    return {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "total_categories": len(news_by_category),
        "total_stories": total_stories,
        "news_by_category": news_by_category,
        "errors": errors,
        "method": "perplexity"
    }

