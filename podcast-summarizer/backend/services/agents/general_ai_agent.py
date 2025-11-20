"""
General AI Search Agent

Specialist agent for finding articles about:
- Foundation models (GPT, Claude, Gemini, Llama, Mistral)
- AI infrastructure and tooling
- RAG systems and vector databases
- Observability and prompt management
- Model releases and API updates
"""
import logging
from typing import Any

from .base_search_agent import BaseSearchAgent
from ..search_queries import GENERAL_AI_QUERY
from ...test_config import AGENT_TARGET_ARTICLES

logger = logging.getLogger(__name__)


class GeneralAIAgent(BaseSearchAgent):
    """
    Specialist agent for General AI articles.
    
    Target: 3 articles (or 1 in test mode).
    """
    
    @property
    def TARGET_ARTICLES(self) -> int:
        # Use test config if set, otherwise production default
        if AGENT_TARGET_ARTICLES:
            return AGENT_TARGET_ARTICLES["general_ai"]
        return 3
    
    @property
    def INITIAL_QUERY(self) -> str:
        return GENERAL_AI_QUERY
    
    @property
    def QUERY_TYPE(self) -> str:
        return "general_ai"


# Factory function for LangGraph Studio
def create_graph(config: Any = None):
    """
    Factory function for LangGraph Studio.
    Takes a RunnableConfig and returns the compiled graph.
    """
    agent = GeneralAIAgent(enable_tracing=False)  # Disable duplicate tracing in Studio
    return agent.graph

