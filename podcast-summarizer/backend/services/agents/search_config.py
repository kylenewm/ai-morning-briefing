"""
Shared configuration for AI search agents.

Contains constants used across all specialist agents.
"""
from datetime import timedelta
from test_config import EXA_SEARCH_TYPE as TEST_EXA_TYPE, EXA_LIVECRAWL as TEST_EXA_LIVECRAWL, EXA_SEARCH_LIMIT as TEST_SEARCH_LIMIT

# Low-quality domains to exclude from search results
LOW_QUALITY_DOMAINS = {
    "medium.com",
    "dev.to",
    "hackernoon.com",
    "towardsdatascience.com",
    "levelup.gitconnected.com",
}

# Date range for article searches (past N days)
SEARCH_DAYS_LOOKBACK = 4

# Exa search parameters (with test mode overrides)
EXA_SEARCH_TYPE = TEST_EXA_TYPE if TEST_EXA_TYPE else "deep"
EXA_LIVECRAWL = TEST_EXA_LIVECRAWL if TEST_EXA_LIVECRAWL else "always"
EXA_MAX_CHARACTERS_DEFAULT = 1000  # Summary length for conversational_ai and general_ai
EXA_MAX_CHARACTERS_RESEARCH = 1500  # Longer summaries for research_opinion (needs more detail)
EXA_MAX_CHARACTERS = 1000  # Default for backward compatibility
EXA_USER_LOCATION = "US"  # Geo preference

# LLM evaluation thresholds
EVALUATION_THRESHOLD_ITERATION_1 = 4.0  # Keep articles with score >= 4.0 on first iteration
EVALUATION_THRESHOLD_ITERATION_2_PLUS = 3.8  # Slightly lower threshold for refinement iterations

# Article limits per search (with test mode overrides)
SEARCH_LIMIT_ITERATION_1 = TEST_SEARCH_LIMIT if TEST_SEARCH_LIMIT else 5
SEARCH_LIMIT_ITERATION_2_PLUS = TEST_SEARCH_LIMIT if TEST_SEARCH_LIMIT else 5

