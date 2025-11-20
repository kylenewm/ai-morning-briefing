"""
Research/Opinion Search Agent

Specialist agent for finding articles about:
- AI market analysis and trends
- Strategic insights for AI Product Managers
- Startup launches and funding
- Technical breakthroughs with business impact
- Novel AI use cases and adoption patterns
"""
import logging
from typing import Any

from .base_search_agent import BaseSearchAgent
from ..search_queries import RESEARCH_OPINION_QUERY
from ...test_config import AGENT_TARGET_ARTICLES

logger = logging.getLogger(__name__)


class ResearchOpinionAgent(BaseSearchAgent):
    """
    Specialist agent for Research/Opinion articles.
    
    Target: 2 articles (or 1 in test mode).
    """
    
    @property
    def TARGET_ARTICLES(self) -> int:
        # Use test config if set, otherwise production default
        if AGENT_TARGET_ARTICLES:
            return AGENT_TARGET_ARTICLES["research_opinion"]
        return 2
    
    @property
    def INITIAL_QUERY(self) -> str:
        return RESEARCH_OPINION_QUERY
    
    @property
    def QUERY_TYPE(self) -> str:
        return "research_opinion"


# Factory function for LangGraph Studio
def create_graph(config: Any = None):
    """
    Factory function for LangGraph Studio.
    Takes a RunnableConfig and returns the compiled graph.
    """
    agent = ResearchOpinionAgent(enable_tracing=False)  # Disable duplicate tracing in Studio
    return agent.graph

