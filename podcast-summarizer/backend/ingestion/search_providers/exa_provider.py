import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from .base import SearchProvider, SearchResult

# Handle imports for both direct execution and module usage
try:
    from ...config import settings
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config import settings

logger = logging.getLogger(__name__)


class ExaProvider(SearchProvider):
    def __init__(self) -> None:
        self.api_key = settings.EXA_API_KEY
        self._client = None
        if self.api_key:
            try:
                from exa_py import Exa  # type: ignore
                self._client = Exa(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Exa SDK not available, will skip actual calls: {e}")
    
    async def search_with_contents(
        self,
        query: str,
        limit: int = 5,
        search_type: str = "auto",
        type: Optional[str] = None,  # Alias for search_type (matches Exa API naming)
        livecrawl: str = "preferred",
        summary_query: Optional[str] = None,
        max_characters: int = 1000,
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_text: Optional[List[str]] = None,
        exclude_text: Optional[List[str]] = None,
        start_published_date: Optional[str] = None,
        end_published_date: Optional[str] = None,
        user_location: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Use Exa's search_and_contents() API to get search results + content + summaries in one call.
        
        This is more efficient than separate search() + get_contents() calls.
        
        Args:
            query: Search query (can be detailed, research-quality prompt)
            limit: Number of results (default: 5)
            search_type: "auto", "neural", "keyword", or "deep" (default: "auto")
            livecrawl: "preferred", "always", or "never" (default: "preferred" for fresh news)
            summary_query: Custom query for AI summary (e.g., "Summarize for an AI PM")
            max_characters: Max characters for full text content (default: 1000)
            include_domains: Only search these domains
            exclude_domains: Exclude these domains
            include_text: Only results containing these keywords
            exclude_text: Exclude results containing these keywords
            start_published_date: ISO date string (e.g., "2025-11-06")
            end_published_date: ISO date string
            user_location: User location for geo-specific results (e.g., "US")
        
        Returns:
            List of SearchResult objects with full_text and summary populated
        """
        logger.info(f"🔎 ExaProvider.search_with_contents: query={query[:80]}...")
        
        if not self.api_key or self._client is None:
            logger.warning(f"⚠️ Exa client not available")
            return []
        
        try:
            # Use 'type' parameter if provided, otherwise use 'search_type'
            final_type = type if type is not None else search_type
            
            # Build parameters
            search_params = {
                "query": query,
                "num_results": limit,
                "type": final_type,
                "livecrawl": livecrawl,
                "text": {"max_characters": max_characters},
            }
            
            # Add summary if requested
            if summary_query:
                search_params["summary"] = {"query": summary_query}
            
            # Add filters
            if include_domains:
                search_params["include_domains"] = include_domains
            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains
            if include_text:
                search_params["include_text"] = include_text
            if exclude_text:
                search_params["exclude_text"] = exclude_text
            
            # Add date range
            if start_published_date:
                search_params["start_published_date"] = start_published_date
            if end_published_date:
                search_params["end_published_date"] = end_published_date
            
            # Add user location
            if user_location:
                search_params["user_location"] = user_location
            
            logger.info(f"🔍 Calling Exa search_and_contents with type={final_type}, livecrawl={livecrawl}")
            
            # Call Exa API
            response = self._client.search_and_contents(**search_params)
            
            results_count = len(response.results) if hasattr(response, 'results') else 0
            logger.info(f"✅ Exa returned {results_count} results with content")
            
            # Parse results
            return [self._to_result_with_contents(r, provider_mode="search_with_contents") for r in self._iter(response)]
            
        except Exception as e:
            logger.error(f"Exa search_with_contents error: {e}", exc_info=True)
            return []

    async def search(
        self,
        query: str,
        limit: int = 10,
        mode: Optional[str] = "search",
        seed_urls: Optional[List[str]] = None
    ) -> List[SearchResult]:
        logger.info(f"🔎 ExaProvider.search called: mode={mode}, query={query[:50]}...")
        
        if not self.api_key:
            logger.warning(f"⚠️ EXA_API_KEY not set (api_key={self.api_key})")
            return []
        
        if self._client is None:
            logger.warning(f"⚠️ Exa client is None")
            return []

        mode = (mode or "search").lower()
        try:
            if mode == "search":
                logger.info(f"🔍 Exa Search: {query[:50]}...")
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                results = self._client.search(
                    query,
                    num_results=limit,
                    use_autoprompt=True,
                    start_published_date=start_date
                )
                logger.info(f"🔍 Exa returned {len(results.results) if hasattr(results, 'results') else 0} results")
                return [self._to_result(r, provider_mode="search") for r in self._iter(results)]

            if mode == "research":
                logger.info(f"🔬 Exa Research Fast: Starting async job...")
                
                # Create async research job with exa-research-fast
                research_job = self._client.research.create(
                    model="exa-research-fast",
                    instructions=query
                )
                
                # Try to get research ID from different possible attributes
                research_id = None
                if hasattr(research_job, 'researchId'):
                    research_id = research_job.researchId
                elif hasattr(research_job, 'research_id'):
                    research_id = research_job.research_id
                elif hasattr(research_job, 'id'):
                    research_id = research_job.id
                else:
                    logger.error(f"Research job attributes: {dir(research_job)}")
                    logger.error(f"Research job dict: {research_job.__dict__ if hasattr(research_job, '__dict__') else 'N/A'}")
                    return []
                
                logger.info(f"📊 Research job {research_id} created, polling (30s max)...")
                
                # Poll until finished (max 30s)
                result = self._client.research.poll_until_finished(
                    research_id,
                    timeout=30
                )
                
                logger.info(f"✅ Research job completed")
                
                # Parse results
                return self._parse_research_results(result, limit)

            if mode == "find_similar":
                if not seed_urls:
                    logger.info("find_similar requested without seed_urls; returning empty")
                    return []
                logger.info(f"🔗 Exa Find Similar: {seed_urls[0][:50]}...")
                primary = seed_urls[0]
                start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                results = self._client.find_similar(
                    url=primary,
                    num_results=limit,
                    start_published_date=start_date
                )
                return [self._to_result(r, provider_mode="find_similar") for r in self._iter(results)]

            logger.warning(f"Unknown Exa mode: {mode}; returning empty")
            return []
        except Exception as e:
            logger.error(f"Exa error ({mode}): {e}")
            return []

    def _iter(self, results: Any) -> List[Any]:
        # The SDK returns SearchResponse object with .results attribute
        try:
            if hasattr(results, 'results'):
                return results.results
            if isinstance(results, dict) and "results" in results:
                return results.get("results", [])
            if isinstance(results, list):
                return results
        except Exception:
            pass
        return []

    def _to_result(self, item: Any, provider_mode: str) -> SearchResult:
        # Handle both dict and SDK result objects
        def get_attr(obj, *keys):
            for key in keys:
                if isinstance(obj, dict):
                    val = obj.get(key)
                else:
                    val = getattr(obj, key, None)
                if val:
                    return val
            return None
        
        title = get_attr(item, "title", "name") or "Untitled"
        url = get_attr(item, "url", "link") or ""
        snippet = get_attr(item, "text", "snippet", "summary")
        source = get_attr(item, "source", "siteName", "author")
        published_date = get_attr(item, "publishedDate", "published_date", "date")
        
        # Convert item to dict for raw storage
        raw_data = item if isinstance(item, dict) else (item.__dict__ if hasattr(item, '__dict__') else {})
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            source=source,
            published_date=published_date,
            provider="exa",
            mode=provider_mode,
            raw=raw_data,
        )
    
    def _to_result_with_contents(self, item: Any, provider_mode: str) -> SearchResult:
        """
        Parse Exa search_and_contents() response item into SearchResult.
        Extracts full text, summary, and highlights in addition to basic metadata.
        """
        def get_attr(obj, *keys):
            for key in keys:
                if isinstance(obj, dict):
                    val = obj.get(key)
                else:
                    val = getattr(obj, key, None)
                if val:
                    return val
            return None
        
        # Basic metadata
        title = get_attr(item, "title", "name") or "Untitled"
        url = get_attr(item, "url", "link") or ""
        source = get_attr(item, "source", "siteName", "author")
        published_date = get_attr(item, "publishedDate", "published_date", "date")
        
        # Content fields from search_and_contents()
        full_text = None
        summary = None
        highlights = None
        snippet = None
        
        # Extract text content
        if hasattr(item, 'text'):
            full_text = item.text
            snippet = full_text[:500] if full_text and len(full_text) > 500 else full_text
        
        # Extract summary
        if hasattr(item, 'summary'):
            summary = item.summary
        
        # Extract highlights
        if hasattr(item, 'highlights') and item.highlights:
            highlights = item.highlights if isinstance(item.highlights, list) else [item.highlights]
        
        # Fallback snippet
        if not snippet:
            snippet = get_attr(item, "snippet", "summary")
        
        # Convert item to dict for raw storage
        raw_data = item if isinstance(item, dict) else (item.__dict__ if hasattr(item, '__dict__') else {})
        
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            source=source,
            published_date=published_date,
            provider="exa",
            mode=provider_mode,
            raw=raw_data,
            full_text=full_text,
            summary=summary,
            highlights=highlights,
        )

    def _parse_research_results(self, result: Any, limit: int) -> List[SearchResult]:
        """Parse Exa research API results into SearchResult objects."""
        try:
            logger.info(f"Research result type: {type(result)}")
            
            # Research API returns a single formatted report with output.content
            # not individual article sources
            if hasattr(result, 'output') and hasattr(result.output, 'content'):
                content = result.output.content
                logger.info(f"Found research content ({len(content)} chars)")
                
                # Create a single SearchResult with the full research report
                research_result = SearchResult(
                    title=f"Research: {getattr(result, 'instructions', 'AI Research')[:100]}",
                    url=f"exa-research://{getattr(result, 'research_id', 'unknown')}",
                    snippet=content[:500] + "..." if len(content) > 500 else content,
                    source="exa-research",
                    published_date=None,
                    provider="exa",
                    mode="research",
                    raw={"full_content": content, "model": getattr(result, 'model', None)}
                )
                return [research_result]
            
            # Fallback: Try old format (sources/results) in case API changes
            articles = []
            if hasattr(result, 'sources'):
                articles = result.sources[:limit]
                logger.info(f"Found {len(articles)} sources in research result")
            elif hasattr(result, 'results'):
                articles = result.results[:limit]
                logger.info(f"Found {len(articles)} results in research result")
            elif isinstance(result, dict):
                articles = result.get('sources', result.get('results', []))[:limit]
                logger.info(f"Found {len(articles)} articles in dict research result")
            
            if articles:
                return [self._to_result(r, provider_mode="research") for r in articles]
            
            logger.warning(f"No content found in research result")
            return []
        except Exception as e:
            logger.error(f"Error parsing research results: {e}", exc_info=True)
            return []


