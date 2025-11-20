"""
Search Orchestrator

Coordinates all 3 specialist search agents (Conversational AI, General AI, Research/Opinion)
to run in parallel and merge their results.

This provides:
- True parallelism (all agents run simultaneously)
- Clear separation of concerns (each agent focuses on one query type)
- Easy debugging (separate traces per agent in LangGraph Studio)
"""
import asyncio
import logging
from typing import Any, Dict, List

from ...ingestion.search_providers.base import SearchResult
from .conversational_ai_agent import ConversationalAIAgent
from .general_ai_agent import GeneralAIAgent
from .research_opinion_agent import ResearchOpinionAgent

logger = logging.getLogger(__name__)


async def search_all_categories(
    max_iterations: int = 2,
    use_cache: bool = True,
    run_source: str = "manual"
) -> Dict[str, Any]:
    """
    Run all 3 specialist agents in parallel and merge results.
    
    Args:
        max_iterations: Maximum refinement iterations per agent
        use_cache: Use cached results if available for today
        run_source: "manual" for test runs, "automated" for daily briefing
    
    Returns:
        Dictionary with results grouped by category:
        {
            "conversational_ai": [SearchResult, ...],  # 3 articles (target)
            "general_ai": [SearchResult, ...],          # 3 articles (target)
            "research_opinion": [SearchResult, ...],    # 2 articles (target)
            "total": 8,
            "by_category_count": {"conversational_ai": 3, ...}
        }
    """
    logger.info("=" * 80)
    logger.info("🚀 SEARCH ORCHESTRATOR: Launching all 3 specialist agents in parallel")
    logger.info("=" * 80)
    logger.info(f"   Max iterations per agent: {max_iterations}")
    logger.info(f"   Targets: Conversational AI=3, General AI=3, Research/Opinion=2 (Total: 8)")
    logger.info(f"   Use cache: {use_cache}")
    logger.info(f"   Run source: {run_source}")
    logger.info("=" * 80)
    
    # Initialize all agents with run_source tracking
    conv_agent = ConversationalAIAgent(run_source=run_source)
    general_agent = GeneralAIAgent(run_source=run_source)
    research_agent = ResearchOpinionAgent(run_source=run_source)
    
    # Launch all 3 agents in parallel
    results = await asyncio.gather(
        conv_agent.search(max_iterations=max_iterations, use_cache=use_cache),
        general_agent.search(max_iterations=max_iterations, use_cache=use_cache),
        research_agent.search(max_iterations=max_iterations, use_cache=use_cache),
        return_exceptions=True,  # Don't fail entire orchestrator if one agent fails
    )
    
    # Handle exceptions gracefully
    conv_results = results[0] if not isinstance(results[0], Exception) else []
    general_results = results[1] if not isinstance(results[1], Exception) else []
    research_results = results[2] if not isinstance(results[2], Exception) else []
    
    if isinstance(results[0], Exception):
        logger.error(f"❌ Conversational AI agent failed: {results[0]}")
    if isinstance(results[1], Exception):
        logger.error(f"❌ General AI agent failed: {results[1]}")
    if isinstance(results[2], Exception):
        logger.error(f"❌ Research/Opinion agent failed: {results[2]}")
    
    total = len(conv_results) + len(general_results) + len(research_results)
    
    logger.info("=" * 80)
    logger.info("✅ ORCHESTRATOR COMPLETE")
    logger.info("=" * 80)
    logger.info(f"   Conversational AI: {len(conv_results)} articles")
    logger.info(f"   General AI: {len(general_results)} articles")
    logger.info(f"   Research/Opinion: {len(research_results)} articles")
    logger.info(f"   Total: {total} articles")
    logger.info("=" * 80)
    
    return {
        "conversational_ai": conv_results,
        "general_ai": general_results,
        "research_opinion": research_results,
        "total": total,
        "by_category_count": {
            "conversational_ai": len(conv_results),
            "general_ai": len(general_results),
            "research_opinion": len(research_results),
        }
    }


def flatten_results(orchestrator_results: Dict[str, Any]) -> List[SearchResult]:
    """
    Flatten orchestrator results into a single list of SearchResult objects.
    
    This is useful for backward compatibility with code that expects a flat list.
    
    Args:
        orchestrator_results: Output from search_all_categories()
    
    Returns:
        Flat list of all SearchResult objects from all categories
    """
    all_results = []
    all_results.extend(orchestrator_results.get("conversational_ai", []))
    all_results.extend(orchestrator_results.get("general_ai", []))
    all_results.extend(orchestrator_results.get("research_opinion", []))
    return all_results


# For LangGraph Studio: Simple orchestrator graph
from langgraph.graph import StateGraph, END
from typing import TypedDict


class OrchestratorState(TypedDict):
    """State for orchestrator graph."""
    max_iterations: int
    use_cache: bool
    results: Dict[str, Any]


async def _run_agents(state: OrchestratorState) -> Dict[str, Any]:
    """Node: Run all agents and collect results."""
    max_iterations = state.get("max_iterations", 2)
    use_cache = state.get("use_cache", True)
    
    results = await search_all_categories(
        max_iterations=max_iterations,
        use_cache=use_cache
    )
    
    return {"results": results}


def create_graph(config: Any = None):
    """
    Factory function for LangGraph Studio.
    
    Creates a simple orchestrator graph that runs all 3 agents.
    """
    workflow = StateGraph(OrchestratorState)
    
    workflow.add_node("run_agents", _run_agents)
    workflow.set_entry_point("run_agents")
    workflow.add_edge("run_agents", END)
    
    return workflow.compile()

