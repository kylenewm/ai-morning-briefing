"""
Simple test mode configuration to reduce costs during development.

Usage:
    TEST_MODE=true python test_agent_search.py
    
Default: Production mode (TEST_MODE not set)
"""
import os

# Simple flag - defaults to production
IS_TEST_MODE = os.getenv("TEST_MODE", "").lower() == "true"

# Only override if in test mode
if IS_TEST_MODE:
    # Agent Search - Reduce iterations and targets
    AGENT_MAX_ITERATIONS = 1
    AGENT_TARGET_ARTICLES = {"conversational_ai": 1, "general_ai": 1, "research_opinion": 1}
    
    # Exa - Use cheaper/faster settings
    EXA_SEARCH_TYPE = "neural"  # vs "deep" (cheaper)
    EXA_SEARCH_LIMIT = 2  # vs 5
    EXA_LIVECRAWL = "never"  # vs "always"
    
    print("🧪 TEST MODE: Costs reduced, using cached data where possible")
else:
    # Production defaults (None = use existing values)
    AGENT_MAX_ITERATIONS = None
    AGENT_TARGET_ARTICLES = None
    EXA_SEARCH_TYPE = None
    EXA_SEARCH_LIMIT = None
    EXA_LIVECRAWL = None

