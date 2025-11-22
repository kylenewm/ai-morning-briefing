"""
Base Search Agent for AI News Discovery

Abstract base class for specialist search agents. Each specialist focuses on
one type of AI news (Conversational AI, General AI, or Research/Opinion).

Shared functionality:
- LangGraph workflow (plan → search → evaluate → refine loop)
- Exa API integration
- LLM-based article evaluation
- Query refinement
- Caching
"""
import asyncio
import json
import logging
import os
import pickle
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypedDict
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

# Import from parent modules
try:
    from ...config import settings
    from ...ingestion.search_providers.base import SearchResult
    from ...ingestion.search_providers.exa_provider import ExaProvider
    from .search_config import (
        LOW_QUALITY_DOMAINS,
        SEARCH_DAYS_LOOKBACK,
        EXA_SEARCH_TYPE,
        EXA_LIVECRAWL,
        EXA_MAX_CHARACTERS,
        EXA_MAX_CHARACTERS_DEFAULT,
        EXA_MAX_CHARACTERS_RESEARCH,
        EXA_USER_LOCATION,
        EVALUATION_THRESHOLD_ITERATION_1,
        EVALUATION_THRESHOLD_ITERATION_2_PLUS,
        SEARCH_LIMIT_ITERATION_1,
        SEARCH_LIMIT_ITERATION_2_PLUS,
    )
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config import settings
    from ingestion.search_providers.base import SearchResult
    from ingestion.search_providers.exa_provider import ExaProvider
    from services.agents.search_config import (
        LOW_QUALITY_DOMAINS,
        SEARCH_DAYS_LOOKBACK,
        EXA_SEARCH_TYPE,
        EXA_LIVECRAWL,
        EXA_MAX_CHARACTERS,
        EXA_MAX_CHARACTERS_DEFAULT,
        EXA_MAX_CHARACTERS_RESEARCH,
        EXA_USER_LOCATION,
        EVALUATION_THRESHOLD_ITERATION_1,
        EVALUATION_THRESHOLD_ITERATION_2_PLUS,
        SEARCH_LIMIT_ITERATION_1,
        SEARCH_LIMIT_ITERATION_2_PLUS,
    )

logger = logging.getLogger(__name__)


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return ""


# Article Evaluation Schema
class ArticleEvaluation(TypedDict):
    """Evaluation result for a single article."""
    url: str
    relevance_score: float
    recency_score: float
    source_quality_score: float
    summary_clarity_score: float
    overall_score: float
    decision: str  # "keep" or "discard"
    reasoning: str


# Simplified SearchState for single-agent workflow
class SearchState(TypedDict):
    """State for a single specialist agent."""
    iteration: int
    max_iterations: int
    current_query: str  # Current query text
    completed_queries: List[str]  # All queries executed
    all_raw_results: List[SearchResult]
    evaluated_results: List[ArticleEvaluation]
    kept_articles: List[SearchResult]
    discarded_urls: Set[str]


class BaseSearchAgent(ABC):
    """
    Abstract base class for specialist search agents.
    
    Subclasses must define:
    - TARGET_ARTICLES: Number of articles to find (1-2)
    - INITIAL_QUERY: Starting query text
    - QUERY_TYPE: String identifier for caching
    """
    
    @property
    @abstractmethod
    def TARGET_ARTICLES(self) -> int:
        """Target number of articles to find."""
        pass
    
    @property
    @abstractmethod
    def INITIAL_QUERY(self) -> str:
        """Initial search query."""
        pass
    
    @property
    @abstractmethod
    def QUERY_TYPE(self) -> str:
        """Identifier for this agent type (for cache naming)."""
        pass
    
    def __init__(self, enable_tracing: bool = True, run_source: str = "manual"):
        """
        Initialize the agent.
        
        Args:
            enable_tracing: Whether to enable LangSmith tracing
            run_source: "manual" for test runs, "automated" for daily briefing
        """
        self.exa = ExaProvider()
        self.llm = ChatOpenAI(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper)
            temperature=0.3,
        )
        self.run_source = run_source  # Track manual vs automated runs
        
        # Setup cache directory
        self.cache_dir = Path(__file__).parent.parent.parent.parent.parent / ".cache" / "agent_results"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Build LangGraph workflow
        self.graph = self._build_graph()
        
        logger.info(f"✅ {self.QUERY_TYPE} agent initialized (target: {self.TARGET_ARTICLES} articles)")
    
    def _get_cache_key(self) -> str:
        """Get cache key for today."""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _filter_duplicates(self, articles: List[SearchResult]) -> List[SearchResult]:
        """
        Remove articles seen in past 5 days from ANY source (agents, newsletters, news).
        Logs details about each duplicate found for transparency.
        
        Args:
            articles: List of search results to filter
            
        Returns:
            Filtered list with duplicates removed
        """
        # Import CacheService - try multiple import methods
        CacheService = None
        try:
            from ...database.cache_service import CacheService
        except (ImportError, ValueError):
            try:
                from podcast_summarizer.backend.database.cache_service import CacheService
            except ImportError:
                try:
                    from database.cache_service import CacheService
                except ImportError:
                    logger.warning("⚠️  Could not import CacheService. Deduplication disabled.")
                    return articles
        
        try:
            # Get ALL recent content (not just agent_search - includes newsletters, news, etc.)
            seen_content = CacheService.get_recent_content_urls(days=5)
            
            filtered = []
            duplicates = []
            
            for article in articles:
                if article.url in seen_content:
                    # Track duplicate with metadata for logging
                    dup_info = seen_content[article.url]
                    duplicates.append({
                        'title': article.title or 'Unknown',
                        'url': article.url,
                        'original_source': dup_info['source_type'],
                        'original_name': dup_info['source_name'],
                        'original_date': dup_info['created_at']
                    })
                else:
                    filtered.append(article)
            
            # Log each duplicate with detailed info
            if duplicates:
                logger.warning(f"⚠️  Filtered {len(duplicates)} duplicate(s) from past 5 days:")
                for dup in duplicates:
                    logger.warning(
                        f"   • '{dup['title'][:60]}...' "
                        f"(previously in {dup['original_source']}/{dup['original_name']} "
                        f"on {dup['original_date']})"
                    )
            
            return filtered
            
        except Exception as e:
            logger.warning(f"⚠️  Deduplication failed: {e}. Continuing without deduplication.")
            return articles  # On error, return all articles (fail gracefully)
    
    def _get_cache_path(self) -> Path:
        """Get path to today's cache file for this agent."""
        cache_key = self._get_cache_key()
        return self.cache_dir / f"{self.QUERY_TYPE}_{cache_key}.pkl"
    
    def _load_from_cache(self) -> Optional[List[SearchResult]]:
        """Load cached results for today if available."""
        cache_path = self._get_cache_path()
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    if cached_data.get('date') == self._get_cache_key():
                        logger.info(f"✅ Using cached results from {cached_data.get('timestamp')}")
                        return cached_data.get('articles', [])
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return None
    
    def _save_to_cache(self, articles: List[SearchResult]):
        """Save results to cache for today."""
        cache_path = self._get_cache_path()
        try:
            cache_data = {
                'date': self._get_cache_key(),
                'timestamp': datetime.now().isoformat(),
                'articles': articles
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.info(f"💾 Cached {len(articles)} articles for today")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(SearchState)
        
        # Add nodes
        workflow.add_node("plan_initial", self._plan_initial_search)
        workflow.add_node("execute_search", self._execute_search)
        workflow.add_node("evaluate_articles", self._evaluate_articles)
        workflow.add_node("finalize_results", self._finalize_results)
        workflow.add_node("plan_followup", self._plan_followup_search)
        
        # Define edges
        workflow.set_entry_point("plan_initial")
        workflow.add_edge("plan_initial", "execute_search")
        workflow.add_edge("execute_search", "evaluate_articles")
        
        # Conditional: continue or finalize?
        workflow.add_conditional_edges(
            "evaluate_articles",
            self._should_continue,
            {
                "continue": "plan_followup",
                "end": "finalize_results"
            }
        )
        workflow.add_edge("plan_followup", "execute_search")
        workflow.add_edge("finalize_results", END)
        
        return workflow.compile()
    
    async def _plan_initial_search(self, state: SearchState) -> Dict[str, Any]:
        """Node 1: Plan initial search."""
        logger.info(f"🎯 Planning initial search for {self.QUERY_TYPE}")
        return {
            "iteration": 1,
            "current_query": self.INITIAL_QUERY,
            "completed_queries": [],
            "all_raw_results": [],
            "evaluated_results": [],
            "kept_articles": [],
            "discarded_urls": set(),
        }
    
    async def _execute_search(self, state: SearchState) -> Dict[str, Any]:
        """Node 2: Execute search using Exa API."""
        query = state["current_query"]
        iteration = state["iteration"]
        discarded_urls = state.get("discarded_urls", set())
        
        # Adjust limit based on iteration
        limit = SEARCH_LIMIT_ITERATION_1 if iteration == 1 else SEARCH_LIMIT_ITERATION_2_PLUS
        
        logger.info(f"🔍 Executing search (iteration {iteration}, limit={limit})...")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=SEARCH_DAYS_LOOKBACK)
        
        # Determine max_characters based on agent type
        max_chars = (EXA_MAX_CHARACTERS_RESEARCH 
                     if self.QUERY_TYPE == "research_opinion" 
                     else EXA_MAX_CHARACTERS_DEFAULT)
        
        # TEMPORARILY DISABLED: Domain exclusion commented out while Exa API is having 500 errors
        # Theory: exclude_domains parameter might be triggering server-side issues
        # Re-enable once Exa API is stable
        # exclude_domains_list = list(LOW_QUALITY_DOMAINS)[:10]
        
        try:
            # Using simplified summary query that works with current Exa API
            # All params re-enabled except exclude_domains
            results = await self.exa.search_with_contents(
                query=query,
                limit=limit,
                type=EXA_SEARCH_TYPE,  # "deep" search for quality
                livecrawl=EXA_LIVECRAWL,  # Re-enabled - prefer fresh content
                summary_query="Please give a concise summary",  # Simple query that works (Old query: Summarize this article for an AI Product Manager, focusing on product implications and actionable insights.")
                max_characters=max_chars,  # Agent-specific length (1000 for most, 1500 for research)
                start_published_date=start_date.strftime("%Y-%m-%d"),
                end_published_date=end_date.strftime("%Y-%m-%d"),
                user_location=EXA_USER_LOCATION,  # Re-enabled - US geo preference
                # exclude_domains=exclude_domains_list,  # Still disabled
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            results = []
        
        # Filter out already discarded URLs
        unique_results = [r for r in results if r.url not in discarded_urls]
        
        # Deduplicate by URL within this search
        seen_urls = set()
        deduped_results = []
        for r in unique_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                deduped_results.append(r)
        
        logger.info(f"✅ Found {len(deduped_results)} new unique articles")
        
        # Filter out duplicates from past 5 days (ALL content types: agents, newsletters, news)
        filtered_results = self._filter_duplicates(deduped_results)
        logger.info(f"✅ {len(filtered_results)} articles remaining after cross-content deduplication")
        
        return {
            "all_raw_results": state.get("all_raw_results", []) + filtered_results,  # Use filtered results!
            "completed_queries": state.get("completed_queries", []) + [query],
        }
    
    async def _evaluate_articles(self, state: SearchState) -> Dict[str, Any]:
        """Node 3: Evaluate articles using LLM."""
        all_results = state.get("all_raw_results", [])
        already_evaluated_urls = {ev["url"] for ev in state.get("evaluated_results", [])}
        new_articles = [r for r in all_results if r.url not in already_evaluated_urls]
        
        if not new_articles:
            logger.info("📊 No new articles to evaluate")
            return {}
        
        iteration = state.get("iteration", 1)
        current_query = state.get("current_query", "")
        logger.info(f"📊 Evaluating {len(new_articles)} new articles (iteration {iteration})...")
        
        # Batch evaluate with query context for relevance scoring
        evaluations = await self._batch_evaluate_articles(new_articles, iteration, query=current_query)
        
        # Split into kept and discarded
        kept_articles = state.get("kept_articles", [])
        discarded_urls = state.get("discarded_urls", set())
        
        for evaluation, article in zip(evaluations, new_articles):
            if evaluation["decision"] == "keep":
                kept_articles.append(article)
            else:
                discarded_urls.add(article.url)
        
        logger.info(f"✅ Evaluation complete: {len([e for e in evaluations if e['decision'] == 'keep'])} kept, {len([e for e in evaluations if e['decision'] == 'discard'])} discarded")
        logger.info(f"📊 Total kept so far: {len(kept_articles)}/{self.TARGET_ARTICLES}")
        
        return {
            "evaluated_results": state.get("evaluated_results", []) + evaluations,
            "kept_articles": kept_articles,
            "discarded_urls": discarded_urls,
        }
    
    async def _batch_evaluate_articles(self, articles: List[SearchResult], iteration: int = 1, query: str = "") -> List[ArticleEvaluation]:
        """Evaluate multiple articles using LLM with structured output."""
        # Use threshold from config
        threshold = EVALUATION_THRESHOLD_ITERATION_1 if iteration == 1 else EVALUATION_THRESHOLD_ITERATION_2_PLUS
        
        # Build evaluation prompt
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"\n{i}. **{article.title}**\n"
            articles_text += f"   URL: {article.url}\n"
            articles_text += f"   Source: {article.source or 'Unknown'}\n"
            articles_text += f"   Published: {article.published_date or 'Unknown'}\n"
            if article.summary:
                articles_text += f"   Summary: {article.summary[:300]}...\n"
            elif article.snippet:
                articles_text += f"   Snippet: {article.snippet[:300]}...\n"
        
        # Add query context for relevance scoring
        query_context = f"\n**Original Search Query:**\n{query}\n" if query else ""
        
        # Calculate date cutoffs for strict recency checking (weekend-aware)
        current_date = datetime.now()
        cutoff_date = current_date - timedelta(days=4)
        current_date_str = current_date.strftime("%B %d, %Y")
        cutoff_date_str = cutoff_date.strftime("%B %d, %Y")
        
        # Weekend-aware scoring: Monday allows 72h, Tue-Fri strict 48h cutoff
        is_monday = current_date.weekday() == 0
        strict_cutoff_hours = 72 if is_monday else 48
        day_context = "Monday (weekend gap)" if is_monday else "Tuesday-Friday (daily flow)"
        
        prompt = f"""Evaluate these articles for an AI PM newsletter. Score each 1-5 on:
{query_context}
**CRITICAL: Today's date is {current_date_str} ({day_context}). We are looking for articles from the past 4 days ONLY ({cutoff_date_str} or later).**

1. **Relevance**: How relevant is this article to the search query above? Does it match what an AI PM searching for this topic would want?
   - 5 = Directly addresses the query topic, highly relevant to what was searched
   - 3 = Somewhat related to the query
   - 1 = Off-topic or tangentially related

2. **Recency**: How fresh is this article? **STRICT CUTOFF: Articles older than {strict_cutoff_hours} hours receive 0/5 automatically.**
   {"   - 5 = Published in past 24 hours" if True else ""}
   {"   - 4 = Published 24-48 hours ago" if True else ""}
   {"   - 3 = Published 48-72 hours ago (acceptable on Monday due to weekend)" if is_monday else ""}
   {"   - 0 = Published >72 hours ago - REJECT IMMEDIATELY" if is_monday else "   - 0 = Published >48 hours ago - REJECT IMMEDIATELY"}
   
   **Weekend-aware rule**: {"On Monday, articles from Friday (up to 72h) are acceptable due to weekend gap." if is_monday else "On Tuesday-Friday, only articles from past 48 hours are acceptable (strict daily flow)."}
   
   **Check the article content carefully**: If it mentions launch dates, events, or releases from before {cutoff_date_str}, score it 0 regardless of page metadata. Republished old content should be rejected.

3. **Source Quality**: Is this a newsworthy launch/update?
   - 5 = Product launch, major feature release, significant API update, official announcements
   - 3 = Standard articles about existing features or general analysis
   - 2 = Brief mentions or minor updates
   - 1 = Tweets, snippets, vague posts without substance

4. **Summary Clarity**: Can PM understand quickly? (5=clear+actionable+detailed, 1=vague/missing)

Average ≥ {threshold} → keep, else discard.

**Articles ({len(articles)} total):**
{articles_text}

Return JSON:
[{{"url": "...", "relevance_score": 4, "recency_score": 5, "source_quality_score": 4, "summary_clarity_score": 4, "overall_score": 4.25, "decision": "keep", "reasoning": "brief reason"}}]

Respond ONLY with the JSON array."""
        
        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Parse JSON
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0]
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0]
            
            evaluations = json.loads(content.strip())
            
            # Ensure we have one evaluation per article
            if len(evaluations) != len(articles):
                logger.warning(f"Evaluation count mismatch: {len(evaluations)} evaluations for {len(articles)} articles")
                while len(evaluations) < len(articles):
                    evaluations.append({
                        "url": articles[len(evaluations)].url,
                        "relevance_score": 2.5,
                        "recency_score": 2.5,
                        "source_quality_score": 2.5,
                        "summary_clarity_score": 2.5,
                        "overall_score": 2.5,
                        "decision": "discard",
                        "reasoning": "Missing evaluation"
                    })
            
            return evaluations
            
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            # Return default "discard" evaluations
            return [{
                "url": article.url,
                "relevance_score": 2.5,
                "recency_score": 2.5,
                "source_quality_score": 2.5,
                "summary_clarity_score": 2.5,
                "overall_score": 2.5,
                "decision": "discard",
                "reasoning": f"Evaluation error: {str(e)[:100]}"
            } for article in articles]
    
    def _should_continue(self, state: SearchState) -> str:
        """Decision node: Continue iterating or finish?"""
        iteration = state.get("iteration", 1)
        max_iterations = state.get("max_iterations", 2)
        kept_articles = state.get("kept_articles", [])
        
        logger.info("=" * 60)
        logger.info(f"🤔 DECISION POINT (Iteration {iteration}/{max_iterations})")
        logger.info(f"   Articles kept: {len(kept_articles)}/{self.TARGET_ARTICLES}")
        
        # Stop if target reached
        if len(kept_articles) >= self.TARGET_ARTICLES:
            logger.info(f"   → ✅ STOP: Target reached")
            logger.info("=" * 60)
            return "end"
        
        # Stop if max iterations reached
        if iteration >= max_iterations:
            logger.info(f"   → 🛑 STOP: Max iterations reached")
            logger.info("=" * 60)
            return "end"
        
        logger.info(f"   → 🔄 CONTINUE: Need more articles")
        logger.info("=" * 60)
        return "continue"
    
    async def _plan_followup_search(self, state: SearchState) -> Dict[str, Any]:
        """Node 4: Generate refined follow-up query using LLM."""
        iteration = state.get("iteration", 1)
        kept_articles = state.get("kept_articles", [])
        evaluated_results = state.get("evaluated_results", [])
        
        logger.info(f"🎯 Planning follow-up search for iteration {iteration + 1}...")
        
        # Get discarded articles for learning
        discarded = [
            ev for ev in evaluated_results
            if ev["decision"] == "discard"
        ][-10:]  # Last 10
        
        # Build context for refinement
        discarded_context = "\n".join([
            f"- {ev['url']} (Score: {ev['overall_score']:.1f}) - {ev['reasoning']}"
            for ev in discarded
        ])
        
        original_query = state["current_query"]
        
        prompt = f"""Refine this search query to find better articles.

ORIGINAL QUERY:
{original_query}

RECENT DISCARDED RESULTS (to avoid):
{discarded_context or "None"}

TASK:
Refine the query to avoid low-quality results. Keep the core focus but add specificity to get better articles.

RULES:
1. Remove terms that led to poor results
2. Add phrases to emphasize product announcements, APIs, launches
3. Explicitly avoid tutorials, getting started guides
4. Keep query concise (2-3 sentences max)

Return ONLY the refined query text (no JSON, no explanation)."""
        
        try:
            response = await self.llm.ainvoke(prompt, config={"temperature": 0.3})
            refined = response.content.strip()
            
            # Remove markdown formatting if present
            if refined.startswith("```") and refined.endswith("```"):
                refined = refined.split("```")[1].strip()
            
            logger.info(f"   🎯 Refined query generated")
            
            return {
                "current_query": refined,
                "iteration": iteration + 1,
            }
            
        except Exception as e:
            logger.error(f"LLM refinement failed: {e}")
            # Fallback: use original query
            return {
                "current_query": original_query,
                "iteration": iteration + 1,
            }
    
    async def _finalize_results(self, state: SearchState) -> Dict[str, Any]:
        """Node 5: Finalize results - sort by score and keep only top N."""
        kept_articles = state.get("kept_articles", [])
        evaluated_results = state.get("evaluated_results", [])
        
        logger.info(f"🏁 Finalizing results...")
        
        # Create a map of URL -> evaluation for scoring
        url_to_eval = {ev["url"]: ev for ev in evaluated_results}
        
        # Sort kept articles by overall_score (highest first)
        kept_with_scores = []
        for article in kept_articles:
            ev = url_to_eval.get(article.url, {})
            score = ev.get("overall_score", 0)
            kept_with_scores.append((article, score))
        
        kept_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Take only top N
        top_n_articles = [article for article, score in kept_with_scores[:self.TARGET_ARTICLES]]
        
        logger.info(f"✅ Finalized: {len(top_n_articles)}/{self.TARGET_ARTICLES} articles (from {len(kept_articles)} kept)")
        
        # Save finalized articles to Supabase for deduplication
        if top_n_articles:
            # Import CacheService - try multiple import methods
            CacheService = None
            try:
                from ...database.cache_service import CacheService
            except (ImportError, ValueError):
                try:
                    from podcast_summarizer.backend.database.cache_service import CacheService
                except ImportError:
                    try:
                        from database.cache_service import CacheService
                    except ImportError:
                        logger.warning("⚠️  Could not import CacheService. Skipping save to Supabase.")
                        CacheService = None
            
            if CacheService:
                try:
                    # Convert SearchResult objects to dicts for storage
                    articles_to_save = []
                    for article in top_n_articles:
                        articles_to_save.append({
                            'url': article.url,
                            'title': article.title,
                            'summary': article.summary,
                            'domain': _extract_domain(article.url),
                            'score': url_to_eval.get(article.url, {}).get("overall_score", 0)
                        })
                    
                    CacheService.save_agent_articles(
                        articles=articles_to_save,
                        query_type=self.QUERY_TYPE,
                        run_source=self.run_source  # Pass through for tracking
                    )
                except Exception as e:
                    logger.warning(f"⚠️  Failed to save articles to Supabase: {e}")
                    # Don't fail the whole process if save fails
        
        return {
            "kept_articles": top_n_articles
        }
    
    async def search(self, max_iterations: int = 2, use_cache: bool = True) -> List[SearchResult]:
        """
        Run the search agent workflow.
        
        Args:
            max_iterations: Maximum rounds of refinement
            use_cache: Use cached results if available for today
        
        Returns:
            List of high-quality SearchResult objects
        """
        # Try cache first
        if use_cache:
            cached_articles = self._load_from_cache()
            if cached_articles is not None:
                logger.info(f"📦 Using {len(cached_articles)} cached articles (no API calls)")
                return cached_articles
        
        logger.info(f"🚀 Starting {self.QUERY_TYPE} agent (target: {self.TARGET_ARTICLES} articles)...")
        
        initial_state: SearchState = {
            "iteration": 0,
            "max_iterations": max_iterations,
            "current_query": "",
            "completed_queries": [],
            "all_raw_results": [],
            "evaluated_results": [],
            "kept_articles": [],
            "discarded_urls": set(),
        }
        
        # Run the LangGraph workflow
        final_state = await self.graph.ainvoke(initial_state)
        
        kept_articles = final_state["kept_articles"]
        logger.info(f"✅ {self.QUERY_TYPE} agent complete: {len(kept_articles)} articles from {len(final_state['completed_queries'])} searches")
        
        # Save to cache
        if use_cache:
            self._save_to_cache(kept_articles)
        
        return kept_articles

