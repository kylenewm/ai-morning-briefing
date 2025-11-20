"""
AI Newsletter Search Agent with LangGraph - LEGACY VERSION

⚠️ DEPRECATED: This is the legacy monolithic search agent.
⚠️ Use the new specialist agents instead:
⚠️   - /services/agents/conversational_ai_agent.py
⚠️   - /services/agents/general_ai_agent.py
⚠️   - /services/agents/research_opinion_agent.py
⚠️   - /services/agents/search_orchestrator.py (coordinator)
⚠️
⚠️ This file is kept as a backup only. Do not use for new development.

This agent performs iterative search and evaluation to find high-quality AI news articles.
Uses Exa's search_and_contents() API and LLM-based evaluation to ensure relevance.

LangGraph Concepts Demonstrated:
- StateGraph workflow definition
- Conditional routing (should_continue)
- Async parallel execution
- State management across nodes
- LangSmith tracing for observability
"""
import asyncio
import json
import logging
import os
import pickle
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TypedDict
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

# Handle imports for both direct execution and module usage
try:
    from ..config import settings
    from ..ingestion.search_providers.base import SearchResult
    from ..ingestion.search_providers.exa_provider import ExaProvider
    from .search_queries import (
        ALL_INITIAL_QUERIES,
        CONVERSATIONAL_AI_QUERY,
        GENERAL_AI_QUERY,
        RESEARCH_OPINION_QUERY,
    )
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import settings
    from ingestion.search_providers.base import SearchResult
    from ingestion.search_providers.exa_provider import ExaProvider
    from services.search_queries import (
        ALL_INITIAL_QUERIES,
        CONVERSATIONAL_AI_QUERY,
        GENERAL_AI_QUERY,
        RESEARCH_OPINION_QUERY,
    )

logger = logging.getLogger(__name__)


def _extract_domain(url: str) -> str:
    """Extract domain from URL (e.g., 'https://techcrunch.com/article' -> 'techcrunch.com')."""
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return ""


# Article Evaluation Schema
class ArticleEvaluation(TypedDict):
    """Evaluation result for a single article."""
    url: str
    relevance_score: float        # 1-5: Useful for AI PM?
    recency_score: float          # 1-5: Is this fresh news?
    source_quality_score: float   # 1-5: Trustworthy source?
    summary_clarity_score: float  # 1-5: Can you understand it quickly?
    overall_score: float          # Average of 4 scores
    decision: str                 # "keep" (≥4.0) or "discard" (<4.0)
    reasoning: str                # One sentence explanation


# LangGraph State Definition
class SearchState(TypedDict):
    """State passed between LangGraph nodes."""
    # Iteration control
    iteration: int                    # Current iteration (1-3)
    max_iterations: int              # Max iterations allowed
    
    # Query tracking
    initial_queries: List[Dict[str, str]]  # Starting queries with source tags: [{"query": "...", "source": "conversational_ai"}]
    completed_queries: List[str]           # All queries executed
    next_queries: List[Dict[str, str]]     # Queries for next iteration with sources
    
    # Results
    all_raw_results: List[SearchResult]           # All articles found
    evaluated_results: List[ArticleEvaluation]    # Articles with scores
    kept_articles: List[SearchResult]             # Final "keep" decisions (flat list for final output)
    kept_by_source: Dict[str, List[Dict]]         # Kept articles grouped by source for refinement
    discarded_by_source: Dict[str, List[Dict]]    # Discarded articles grouped by source for refinement
    discarded_urls: Set[str]                      # URLs to exclude
    query_distribution: Dict[str, int]            # Count by query source (conversational_ai, general_ai, research_opinion)
    
    # Learning context
    discarded_patterns: Dict[str, List[str]]      # Patterns to avoid per source: {"general_ai": ["tutorials", "old content"]}
    refined_queries: Dict[str, str]               # Track refined queries for iteration 3: {"general_ai": "refined query text"}
    low_quality_domains: Set[str]                 # Domains to exclude (max 10)
    
    # Feedback
    feedback_summary: str            # What to refine next (used for logging only, not LLM-based anymore)


class SearchAgent:
    """
    Intelligent search agent that iteratively finds and evaluates AI news.
    
    Workflow:
    1. Execute initial searches (7 queries in parallel)
    2. Evaluate each article with LLM (relevance, recency, clarity)
    3. Aggregate feedback (what topics are missing?)
    4. Generate follow-up searches if needed
    5. Repeat 2-3 times until sufficient coverage
    """
    
    def __init__(self, cache_dir: Optional[str] = None, enable_tracing: bool = True):
        # Enable LangSmith tracing if API key is available
        if enable_tracing and hasattr(settings, 'LANGSMITH_API_KEY'):
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_PROJECT"] = "morning-automation"
            os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
            logger.info("✅ LangSmith tracing enabled")
        
        self.exa = ExaProvider()
        self.llm = ChatOpenAI(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini (cheaper than 4o-mini)
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )
        self.graph = self._build_graph()
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "agent")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self) -> str:
        """Get cache key based on today's date."""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_cache_path(self) -> Path:
        """Get path to today's cache file."""
        cache_key = self._get_cache_key()
        return self.cache_dir / f"agent_results_{cache_key}.pkl"
    
    def _load_from_cache(self) -> Optional[List[SearchResult]]:
        """Load cached results for today if available."""
        cache_path = self._get_cache_path()
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    # Verify cache is from today
                    if cached_data.get('date') == self._get_cache_key():
                        logger.info(f"✅ Using cached agent results from {cached_data.get('timestamp')}")
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
        """
        Build the LangGraph workflow.
        
        LangGraph Concept: StateGraph with nodes and conditional edges
        """
        workflow = StateGraph(SearchState)
        
        # Add nodes (functions that process state)
        workflow.add_node("plan_initial_searches", self._plan_initial_searches)
        workflow.add_node("execute_searches", self._execute_searches)
        workflow.add_node("evaluate_articles", self._evaluate_articles)
        workflow.add_node("aggregate_feedback", self._aggregate_feedback)
        workflow.add_node("plan_followup_searches", self._plan_followup_searches)
        
        # Define edges (flow between nodes)
        workflow.set_entry_point("plan_initial_searches")
        workflow.add_edge("plan_initial_searches", "execute_searches")
        workflow.add_edge("execute_searches", "evaluate_articles")
        workflow.add_edge("evaluate_articles", "aggregate_feedback")
        
        # Conditional edge: decide whether to continue or finish
        # LangGraph Concept: Conditional routing based on state
        workflow.add_conditional_edges(
            "aggregate_feedback",
            self._should_continue,
            {
                "continue": "plan_followup_searches",
                "end": END
            }
        )
        workflow.add_edge("plan_followup_searches", "execute_searches")
        
        return workflow.compile()
    
    async def _plan_initial_searches(self, state: SearchState) -> Dict[str, Any]:
        """
        Node 1: Generate initial search queries with source tags.
        
        LangGraph Concept: Nodes return dict updates (not full state).
        """
        logger.info("🎯 Planning initial searches...")
        
        # Use the detailed queries from search_queries.py, tagged by source
        # ALL_INITIAL_QUERIES is a list of 3 query strings, map them to sources
        initial_queries_with_sources = [
            {"query": ALL_INITIAL_QUERIES[0], "source": "conversational_ai"},
            {"query": ALL_INITIAL_QUERIES[1], "source": "general_ai"},
            {"query": ALL_INITIAL_QUERIES[2], "source": "research_opinion"},
        ]
        
        logger.info(f"📋 Planned {len(initial_queries_with_sources)} initial searches")
        
        return {
            "initial_queries": initial_queries_with_sources,
            "next_queries": initial_queries_with_sources,
            "iteration": 1,
            "completed_queries": [],
            "all_raw_results": [],
            "evaluated_results": [],
            "kept_articles": [],
            "kept_by_source": {},
            "discarded_by_source": {},
            "discarded_urls": set(),
            "query_distribution": {},
            "discarded_patterns": {},
            "refined_queries": {},
            "low_quality_domains": set(),
            "feedback_summary": "",
        }
    
    async def _execute_searches(self, state: SearchState) -> Dict[str, Any]:
        """
        Node 2: Execute searches in parallel using Exa search_and_contents().
        Tags each result with query_source for distribution tracking.
        Boosts limit and enhances queries on iteration 2+ based on learned patterns.
        
        LangGraph Concept: Async parallel execution with asyncio.gather.
        """
        query_objects = state["next_queries"]  # List of {"query": "...", "source": "..."}
        discarded_urls = state.get("discarded_urls", set())
        iteration = state.get("iteration", 1)
        discarded_patterns = state.get("discarded_patterns", {})
        low_quality_domains = state.get("low_quality_domains", set())
        
        # Boost limit on retries: 3 → 5
        limit = 3 if iteration == 1 else 5
        
        logger.info(f"🔍 Executing {len(query_objects)} searches in parallel (iteration {iteration}, limit={limit})...")
        if low_quality_domains:
            logger.info(f"   🚫 Excluding {len(low_quality_domains)} low-quality domains")
        
        # Calculate date range (past 48-96 hours)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=4)  # 96 hours
        
        # Run all searches concurrently
        # LangGraph Concept: Async execution for performance
        tasks = []
        for query_obj in query_objects:
            # Enhance query with learned patterns on iteration 2+
            query_text = query_obj["query"]
            if iteration > 1:
                source = query_obj["source"]
                patterns = discarded_patterns.get(source, [])
                if patterns:
                    avoid_text = ", ".join(patterns)
                    query_text = f"{query_text}. Focus on announcements, APIs, pricing. AVOID: {avoid_text}"
                    logger.info(f"   🎯 Enhanced query [{source}]: ...AVOID: {avoid_text}")
            
            # Prepare exclude_domains list (cap at 10)
            exclude_domains_list = list(low_quality_domains)[:10] if low_quality_domains else None
            
            task = self.exa.search_with_contents(
                query=query_text,
                limit=limit,
                type="deep",  # Deep search for comprehensive, high-quality results
                livecrawl="preferred",
                summary_query="Summarize this article for an AI Product Manager, focusing on product implications and actionable insights.",
                max_characters=1000,
                start_published_date=start_date.strftime("%Y-%m-%d"),
                end_published_date=end_date.strftime("%Y-%m-%d"),
                user_location="US",
                exclude_domains=exclude_domains_list,
            )
            tasks.append((task, query_obj["source"]))
        
        # Execute all tasks
        search_results = await asyncio.gather(*[t[0] for t in tasks], return_exceptions=True)
        
        # Flatten results, tag with source, and handle exceptions
        all_new_results = []
        for i, (results, (_, query_source)) in enumerate(zip(search_results, tasks)):
            if isinstance(results, Exception):
                logger.error(f"Search {i+1} failed: {results}")
                continue
            # Tag each result with query_source
            for result in results:
                result.query_source = query_source  # Add source tag to SearchResult
                all_new_results.append(result)
        
        # Filter out already discarded URLs
        unique_results = [r for r in all_new_results if r.url not in discarded_urls]
        
        # Deduplicate by URL within this batch
        seen_urls = set()
        deduped_results = []
        for r in unique_results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                deduped_results.append(r)
        
        logger.info(f"✅ Found {len(all_new_results)} total results, {len(deduped_results)} new unique articles")
        
        # Track completed queries (just the query strings for logging)
        completed_query_strings = [q["query"] for q in query_objects]
        
        return {
            "all_raw_results": state.get("all_raw_results", []) + deduped_results,
            "completed_queries": state.get("completed_queries", []) + completed_query_strings,
            "next_queries": [],  # Clear for next iteration
        }
    
    async def _evaluate_articles(self, state: SearchState) -> Dict[str, Any]:
        """
        Node 3: Evaluate articles with LLM scoring using aggressive thresholds.
        Updates query_distribution based on kept articles.
        
        LangGraph Concept: LLM integration within workflow nodes.
        """
        # Get only the NEW articles that haven't been evaluated yet
        all_results = state.get("all_raw_results", [])
        already_evaluated_urls = {ev["url"] for ev in state.get("evaluated_results", [])}
        new_articles = [r for r in all_results if r.url not in already_evaluated_urls]
        
        if not new_articles:
            logger.info("📊 No new articles to evaluate")
            return {}
        
        iteration = state.get("iteration", 1)
        logger.info(f"📊 Evaluating {len(new_articles)} new articles (iteration {iteration})...")
        
        # Batch evaluate all articles with iteration-based threshold
        evaluations = await self._batch_evaluate_articles(new_articles, iteration)
        
        # Split into kept and discarded, extract patterns from discarded
        kept_articles = state.get("kept_articles", [])
        kept_by_source = state.get("kept_by_source", {})
        discarded_by_source = state.get("discarded_by_source", {})
        discarded_urls = state.get("discarded_urls", set())
        query_distribution = state.get("query_distribution", {})
        discarded_patterns = state.get("discarded_patterns", {})
        low_quality_domains = state.get("low_quality_domains", set())
        
        # Clear discarded_by_source for this iteration (only track most recent)
        discarded_by_source = {}
        
        for i, evaluation in enumerate(evaluations):
            article = new_articles[i]
            query_source = getattr(article, 'query_source', 'unknown')
            
            if evaluation["decision"] == "keep":
                kept_articles.append(article)
                # Update query distribution
                query_distribution[query_source] = query_distribution.get(query_source, 0) + 1
                
                # Group kept articles by source
                if query_source not in kept_by_source:
                    kept_by_source[query_source] = []
                kept_by_source[query_source].append({
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "summary": article.summary,
                    "overall_score": evaluation.get("overall_score"),
                })
            else:
                discarded_urls.add(evaluation["url"])
                
                # Group discarded articles by source
                if query_source not in discarded_by_source:
                    discarded_by_source[query_source] = []
                discarded_by_source[query_source].append({
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "summary": article.summary,
                    "reasoning": evaluation.get("reasoning", ""),
                    "scores": {
                        "relevance": evaluation.get("relevance_score"),
                        "recency": evaluation.get("recency_score"),
                        "source_quality": evaluation.get("source_quality_score"),
                        "summary_clarity": evaluation.get("summary_clarity_score"),
                    }
                })
                
                # Track low-quality domains (cap at 10)
                source_quality = evaluation.get("source_quality_score", 5)
                if source_quality < 3:
                    domain = _extract_domain(article.url)
                    if domain:
                        low_quality_domains.add(domain)
                        # Cap at 10 most recent
                        if len(low_quality_domains) > 10:
                            low_quality_domains = set(list(low_quality_domains)[-10:])
                
                # Extract patterns to avoid from reasoning
                reasoning = evaluation.get("reasoning", "").lower()
                patterns = []
                
                if "tutorial" in reasoning or "getting started" in reasoning:
                    patterns.append("tutorials")
                if "old" in reasoning or "stale" in reasoning or "outdated" in reasoning:
                    patterns.append("outdated content")
                if "generic" in reasoning or "basic" in reasoning:
                    patterns.append("generic content")
                if "technical" in reasoning and "too" in reasoning:
                    patterns.append("overly technical content")
                if "narrow" in reasoning or "niche" in reasoning:
                    patterns.append("niche topics")
                
                # Add to discarded_patterns for this source
                if patterns and query_source != 'unknown':
                    if query_source not in discarded_patterns:
                        discarded_patterns[query_source] = []
                    discarded_patterns[query_source].extend(patterns)
        
        # Deduplicate patterns per source
        for source in discarded_patterns:
            discarded_patterns[source] = list(set(discarded_patterns[source]))
        
        logger.info(f"✅ Evaluation complete: {len([e for e in evaluations if e['decision'] == 'keep'])} kept, {len([e for e in evaluations if e['decision'] == 'discard'])} discarded")
        logger.info(f"📊 Query distribution: {query_distribution}")
        if discarded_patterns:
            logger.info(f"🧠 Learned patterns to avoid: {discarded_patterns}")
        if low_quality_domains:
            logger.info(f"🚫 Low-quality domains to exclude: {low_quality_domains}")
        
        # Enhanced logging for better traceability
        iteration = state.get("iteration", 0)
        logger.info("=" * 80)
        logger.info(f"📊 EVALUATION COMPLETE (Iteration {iteration})")
        logger.info("=" * 80)
        logger.info(f"   Total kept: {len(kept_articles)} articles")
        logger.info(f"   Distribution by source:")
        for source, count in sorted(query_distribution.items()):
            logger.info(f"      - {source}: {count}")
        logger.info(f"   Total discarded: {len(discarded_urls)}")
        logger.info(f"   Low-quality domains tracked: {len(low_quality_domains)}")
        logger.info("=" * 80)
        
        return {
            "evaluated_results": state.get("evaluated_results", []) + evaluations,
            "kept_articles": kept_articles,
            "kept_by_source": kept_by_source,
            "discarded_by_source": discarded_by_source,
            "discarded_urls": discarded_urls,
            "query_distribution": query_distribution,
            "discarded_patterns": discarded_patterns,
            "low_quality_domains": low_quality_domains,
        }
    
    async def _batch_evaluate_articles(self, articles: List[SearchResult], iteration: int = 1) -> List[ArticleEvaluation]:
        """
        Evaluate multiple articles in one LLM call using structured output.
        Uses very aggressive thresholds to force iterations and query refinement.
        """
        # Very aggressive threshold: 4.5 for all iterations to trigger refinement
        threshold = 4.5
        
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
        
        prompt = f"""Evaluate these articles for an AI PM newsletter. Score each 1-5 on:

1. **Relevance**: Useful for AI PMs? (5=launches/APIs/technical deep-dives, 3=analysis, 1=tutorials/basic explainers)
2. **Recency**: How fresh? (5=<24h, 4=24-48h, 3=48-72h, 2=72-96h, 1=>96h)
3. **Source Quality**: Is this a DETAILED article or just a brief update? 
   - 5 = Long-form articles, official blog posts, technical documentation with depth
   - 3 = Standard tech blog posts, medium-depth content
   - 2 = Brief announcements, short news items
   - 1 = Tweets, release note snippets, vague social posts, email newsletters without substance
4. **Summary Clarity**: Can PM understand quickly? (5=clear+actionable+detailed, 1=vague/missing)

**CRITICAL: Prefer detailed articles over brief updates. Discard tweets, short release notes, and vague announcements.**

Average ≥ {threshold} → keep, else discard. (Iteration {iteration}: Be VERY selective! Only keep substantial, detailed sources.)

**Articles ({len(articles)} total):**
{articles_text}

Return JSON:
[{{"url": "...", "relevance_score": 4, "recency_score": 5, "source_quality_score": 4, "summary_clarity_score": 4, "overall_score": 4.25, "decision": "keep", "reasoning": "brief reason"}}]

Respond ONLY with the JSON array."""
        
        try:
            # Call LLM with JSON mode for structured output
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
                # Fill missing evaluations with defaults
                while len(evaluations) < len(articles):
                    evaluations.append({
                        "url": articles[len(evaluations)].url,
                        "relevance_score": 2.5,
                        "recency_score": 2.5,
                        "summary_clarity_score": 2.5,
                        "overall_score": 2.5,
                        "decision": "discard",
                        "reasoning": "Evaluation failed, defaulted to discard"
                    })
            
            return evaluations
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}", exc_info=True)
            # Return default "discard" for all articles on error
            return [
                {
                    "url": article.url,
                    "relevance_score": 2.5,
                    "recency_score": 2.5,
                    "source_quality_score": 2.5,
                    "summary_clarity_score": 2.5,
                    "overall_score": 2.5,
                    "decision": "discard",
                    "reasoning": f"Evaluation failed: {str(e)}"
                }
                for article in articles
            ]
    
    async def _aggregate_feedback(self, state: SearchState) -> Dict[str, Any]:
        """
        Node 4: Analyze query distribution and identify gaps.
        Uses deterministic logic instead of LLM to identify which query sources need more articles.
        
        LangGraph Concept: State analysis to guide next steps.
        """
        kept_articles = state.get("kept_articles", [])
        query_distribution = state.get("query_distribution", {})
        
        logger.info(f"🧠 Aggregating feedback: {len(kept_articles)} kept articles so far")
        
        # Define targets
        query_targets = {
            "conversational_ai": 2,
            "general_ai": 2,
            "research_opinion": 1
        }
        
        # Identify gaps
        gaps = []
        for query_name, target in query_targets.items():
            actual = query_distribution.get(query_name, 0)
            if actual < target:
                gap_size = target - actual
                gaps.append(f"Need {gap_size} more from {query_name.replace('_', ' ')} (have {actual}/{target})")
        
        if gaps:
            feedback_summary = f"Gaps identified: {'; '.join(gaps)}"
            logger.info(f"⚠️  {feedback_summary}")
        else:
            feedback_summary = "All query targets met (conversational_ai≥2, general_ai≥2, research_opinion≥1)"
            logger.info(f"✅ {feedback_summary}")
        
        # Enhanced gap analysis logging
        logger.info("=" * 80)
        logger.info("🎯 GAP ANALYSIS")
        logger.info("=" * 80)
        logger.info(f"   Targets: conversational_ai≥2, general_ai≥2, research_opinion≥1")
        logger.info(f"   Current distribution:")
        for query_name, target in query_targets.items():
            actual = query_distribution.get(query_name, 0)
            status = "✅" if actual >= target else "❌"
            logger.info(f"      {status} {query_name}: {actual}/{target}")
        if gaps:
            logger.info(f"   Gaps to fill: {len(gaps)}")
        else:
            logger.info(f"   All targets met!")
        logger.info("=" * 80)
        
        return {"feedback_summary": feedback_summary}
    
    def _should_continue(self, state: SearchState) -> str:
        """
        Decision node: Should we continue iterating or finish?
        Prioritizes balanced query distribution over raw quantity.
        
        LangGraph Concept: Conditional routing returns string key.
        """
        iteration = state.get("iteration", 1)
        max_iterations = state.get("max_iterations", 2)
        kept_articles = state.get("kept_articles", [])
        query_distribution = state.get("query_distribution", {})
        
        # Enhanced decision logging
        logger.info("=" * 80)
        logger.info(f"🤔 DECISION POINT (Iteration {iteration}/{max_iterations})")
        logger.info("=" * 80)
        logger.info(f"   Articles kept: {len(kept_articles)}")
        logger.info(f"   Query distribution: {query_distribution}")
        
        # Check if query targets are met
        query_targets = {
            "conversational_ai": 2,
            "general_ai": 2,
            "research_opinion": 1
        }
        
        targets_met = all(
            query_distribution.get(query_name, 0) >= target
            for query_name, target in query_targets.items()
        )
        
        logger.info(f"   Query targets met: {'✅ YES' if targets_met else '❌ NO'}")
        
        # Stop conditions
        if iteration >= max_iterations:
            logger.info(f"   → 🛑 STOP: Reached max iterations")
            logger.info("=" * 80)
            return "end"
        
        if targets_met and len(kept_articles) >= 5:
            logger.info(f"   → ✅ STOP: Targets met with sufficient articles")
            logger.info("=" * 80)
            return "end"
        
        if len(kept_articles) >= 25:
            logger.info(f"   → 🛑 STOP: Safety limit reached (25 articles)")
            logger.info("=" * 80)
            return "end"
        
        logger.info(f"   → 🔄 CONTINUE: Need more articles or targets not met")
        logger.info("=" * 80)
        return "continue"
    
    async def _plan_followup_searches(self, state: SearchState) -> Dict[str, Any]:
        """
        Node 5: Generate refined follow-up queries using LLM for sources below target.
        
        LangGraph Concept: Dynamic LLM-based query refinement based on state.
        """
        query_distribution = state.get("query_distribution", {})
        iteration = state.get("iteration", 1)
        
        logger.info(f"🎯 Planning follow-up searches for iteration {iteration + 1}...")
        
        # Define targets and original queries
        query_targets = {
            "conversational_ai": 2,
            "general_ai": 2,
            "research_opinion": 1
        }
        
        query_map = {
            "conversational_ai": CONVERSATIONAL_AI_QUERY,
            "general_ai": GENERAL_AI_QUERY,
            "research_opinion": RESEARCH_OPINION_QUERY
        }
        
        # Identify which categories need more articles
        gaps = []
        for query_name, target in query_targets.items():
            actual = query_distribution.get(query_name, 0)
            if actual < target:
                gap_size = target - actual
                gaps.append((query_name, gap_size, actual, target))
        
        if not gaps:
            logger.info("   ✅ All query targets met, no follow-up queries needed")
            return {
                "next_queries": [],
                "iteration": iteration + 1,
            }
        
        logger.info(f"   ⚠️  {len(gaps)} sources below target: {[g[0] for g in gaps]}")
        
        # Enhanced query refinement logging
        logger.info("=" * 80)
        logger.info("🔄 QUERY REFINEMENT")
        logger.info("=" * 80)
        logger.info(f"   Refining {len(gaps)} queries for next iteration")
        
        # Refine queries for sources below target using LLM
        followup_queries = []
        
        for query_name, gap_size, actual, target in gaps:
            # Get base query (iteration 1: original, iteration 2+: refined)
            refined_queries = state.get("refined_queries", {})
            if iteration > 1 and query_name in refined_queries:
                base_query = refined_queries[query_name]
                logger.info(f"   📝 Using refined query from previous iteration for [{query_name}]")
            else:
                base_query = query_map[query_name]
                logger.info(f"   📝 Using original query for [{query_name}]")
            
            # Get context for this source
            kept_by_source = state.get("kept_by_source", {})
            discarded_by_source = state.get("discarded_by_source", {})
            kept = kept_by_source.get(query_name, [])
            discarded = discarded_by_source.get(query_name, [])
            
            if not discarded:
                # No bad results for this source, use base query unchanged
                logger.info(f"   ✅ No discarded articles for [{query_name}], using base query")
                followup_queries.append({"query": base_query.strip(), "source": query_name})
                continue
            
            # Call LLM to refine the query
            logger.info(f"   🤖 Refining query for [{query_name}] with LLM ({len(kept)} kept, {len(discarded)} discarded)")
            refined_text = await self._call_llm_for_refinement(base_query, kept, discarded)
            
            if refined_text:
                # Store refined query for potential iteration 3
                if "refined_queries" not in state:
                    state["refined_queries"] = {}
                state["refined_queries"][query_name] = refined_text
                followup_queries.append({"query": refined_text.strip(), "source": query_name})
                logger.info(f"   ✅ Refined query for [{query_name}]: {refined_text[:100]}...")
            else:
                # LLM failed, use base query as fallback
                logger.warning(f"   ⚠️  LLM refinement failed for [{query_name}], using base query")
                followup_queries.append({"query": base_query.strip(), "source": query_name})
        
        logger.info(f"   ✅ Generated {len(followup_queries)} refined queries")
        for i, q in enumerate(followup_queries, 1):
            logger.info(f"      {i}. [{q['source']}]: {q['query'][:80]}...")
        logger.info("=" * 80)
        
        return {
            "next_queries": followup_queries,
            "iteration": iteration + 1,
            "refined_queries": state.get("refined_queries", {}),
        }
    
    async def _call_llm_for_refinement(self, original_query: str, kept: List[Dict], discarded: List[Dict]) -> str:
        """
        Use gpt-4.1-mini to surgically refine query by removing problematic terms.
        """
        # Build context strings (limit for token budget)
        kept_context = "\n".join([
            f"- {a['title']} | {a.get('source', 'N/A')} | Score: {a.get('overall_score', 'N/A')}\n  Summary: {a.get('summary', 'N/A')[:200]}"
            for a in kept[:5]  # Limit to 5 for token budget
        ])
        
        discarded_context = "\n".join([
            f"- {a['title']} | {a.get('source', 'N/A')} | Scores: {a.get('scores', {})}\n  Summary: {a.get('summary', 'N/A')[:200]}\n  Reason: {a.get('reasoning', 'N/A')}"
            for a in discarded[:10]  # Limit to 10
        ])
        
        prompt = f"""You are refining a search query that returned some low-quality results.

ORIGINAL QUERY:
{original_query}

KEPT ARTICLES (good results, for context only):
{kept_context or "None"}

DISCARDED ARTICLES (bad results to avoid):
{discarded_context}

TASK:
Surgically remove specific problematic terms from the original query that likely led to the discarded results.

RULES:
1. Remove specific entities/products (e.g., "Vapi", "Retell") that led to bad results
2. Remove narrow phrases (e.g., "conversational AI platforms") if they led to low-quality content
3. KEEP high-level categories (e.g., "conversational AI", "foundation models")
4. Do NOT discard broader concepts that were not directly relevant to bad results
5. Do NOT emphasize kept articles (we already have them)
6. Focus on what to AVOID

Return ONLY the refined query text (no JSON, no explanation)."""

        try:
            response = await self.llm.ainvoke(prompt, config={"temperature": 0.3})
            refined = response.content.strip()
            
            # Remove any markdown formatting if present
            if refined.startswith("```") and refined.endswith("```"):
                refined = refined.split("```")[1].strip()
            
            return refined
        except Exception as e:
            logger.error(f"LLM refinement failed: {e}")
            return ""  # Fail gracefully
    
    async def search_comprehensive(
        self,
        max_iterations: int = 2,
        use_cache: bool = True,
    ) -> List[SearchResult]:
        """
        Run the comprehensive search agent workflow.
        
        Args:
            max_iterations: Maximum rounds of follow-up searches (default: 2)
            use_cache: Use cached results if available for today (default: True)
        
        Returns:
            List of high-quality SearchResult objects (kept articles only)
        """
        # Try to load from cache first
        if use_cache:
            cached_articles = self._load_from_cache()
            if cached_articles is not None:
                logger.info(f"📦 Using {len(cached_articles)} cached articles (no Exa API calls)")
                return cached_articles
        
        logger.info("🚀 Starting comprehensive search agent...")
        
        initial_state: SearchState = {
            "iteration": 0,
            "max_iterations": max_iterations,
            "initial_queries": [],
            "completed_queries": [],
            "next_queries": [],
            "all_raw_results": [],
            "evaluated_results": [],
            "kept_articles": [],
            "discarded_urls": set(),
            "feedback_summary": "",
        }
        
        # Run the LangGraph workflow
        # LangGraph Concept: Invoke compiled graph with initial state
        final_state = await self.graph.ainvoke(initial_state)
        
        kept_articles = final_state["kept_articles"]
        logger.info(f"✅ Agent complete: {len(kept_articles)} high-quality articles from {len(final_state['completed_queries'])} searches")
        logger.info(f"📊 Total evaluated: {len(final_state['evaluated_results'])}, Iterations: {final_state['iteration']}")
        
        # Save to cache for today
        if use_cache:
            self._save_to_cache(kept_articles)
        
        return kept_articles


# Helper function for simple usage
async def search_with_agent(max_iterations: int = 2) -> List[SearchResult]:
    """Convenience function to run the search agent."""
    agent = SearchAgent()
    return await agent.search_comprehensive(max_iterations=max_iterations)


# Factory function for LangGraph Studio
def create_graph(config: Any = None):
    """
    Factory function for LangGraph Studio.
    Takes a RunnableConfig and returns the compiled graph.
    """
    agent = SearchAgent(enable_tracing=False)  # Disable duplicate tracing in Studio
    return agent.graph
