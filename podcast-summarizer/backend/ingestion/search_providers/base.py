from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: Optional[str]
    source: Optional[str]
    published_date: Optional[str]  # ISO YYYY-MM-DD when available
    provider: str                  # e.g., "exa", "perplexity"
    mode: Optional[str] = None     # e.g., "search", "research", "find_similar" (for Exa)
    raw: Optional[Any] = None      # Raw provider payload for debugging
    
    # Enhanced fields from search_and_contents()
    full_text: Optional[str] = None      # Full parsed page content
    summary: Optional[str] = None        # AI-generated summary
    highlights: Optional[List[str]] = None  # Key excerpts


class SearchProvider:
    async def search(
        self,
        query: str,
        limit: int = 10,
        mode: Optional[str] = None,
        seed_urls: Optional[List[str]] = None
    ) -> List[SearchResult]:
        raise NotImplementedError


