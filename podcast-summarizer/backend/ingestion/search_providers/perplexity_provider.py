import logging
import json
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .base import SearchProvider, SearchResult
from ..news_perplexity import search_perplexity

logger = logging.getLogger(__name__)


class PerplexityProvider(SearchProvider):
    async def search(
        self,
        query: str,
        limit: int = 10,
        mode: Optional[str] = None,
        seed_urls: Optional[List[str]] = None
    ) -> List[SearchResult]:
        try:
            # Build structured query asking for JSON with individual articles
            now = datetime.now()
            yesterday = now - timedelta(days=1)
            date_range_str = f"last 24-48 hours (focus on {yesterday.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})"
            
            structured_query = f"""{query}

Return ONLY valid JSON with {limit} most relevant articles:
{{
  "articles": [
    {{
      "title": "exact article title",
      "summary": "1-2 sentence summary",
      "source": "publication name",
      "url": "https://full-url",
      "published_date": "YYYY-MM-DD"
    }}
  ]
}}

Focus on articles from {date_range_str}. Include published_date in YYYY-MM-DD format."""

            data = await search_perplexity(query=structured_query, model="sonar")
            if not data:
                return []

            # Extract response content
            content = None
            try:
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
            except Exception:
                pass
            
            if not content:
                logger.warning("No content in Perplexity response")
                return []

            # Try to parse JSON from response
            try:
                # Extract JSON if wrapped in markdown
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    json_str = content.split("```")[1].split("```")[0].strip()
                else:
                    json_str = content
                
                parsed = json.loads(json_str)
                articles = parsed.get("articles", [])
                
                logger.info(f"✅ Perplexity returned {len(articles)} structured articles")
                
                # Convert to SearchResult objects
                results: List[SearchResult] = []
                for article in articles[:limit]:
                    results.append(
                        SearchResult(
                            title=article.get("title", "Unknown"),
                            url=article.get("url", ""),
                            snippet=article.get("summary", ""),
                            source=article.get("source"),
                            published_date=article.get("published_date"),
                            provider="perplexity",
                            mode=mode,
                            raw=article,
                        )
                    )
                return results
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from Perplexity: {e}")
                logger.debug(f"Content: {content[:500]}")
                
                # Fallback: Extract URLs from citations
                citations = data.get("citations", [])
                urls = [c for c in citations if isinstance(c, str) and c.startswith("http")]
                
                results: List[SearchResult] = []
                for u in urls[:limit]:
                    results.append(
                        SearchResult(
                            title=u,
                            url=u,
                            snippet=content[:200] if content else None,
                            source=None,
                            published_date=None,
                            provider="perplexity",
                            mode=mode,
                            raw=None,
                        )
                    )
                return results
                
        except Exception as e:
            logger.error(f"Perplexity provider error: {e}", exc_info=True)
            return []


