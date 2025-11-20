# Multi-Agent Search System Reference

Complete technical reference for the LangGraph-based multi-agent article discovery system.

## System Overview

The search system uses three specialist AI agents running in parallel to curate AI news articles. Each agent focuses on a specific category, searches with Exa AI, evaluates results with GPT-4, and refines queries iteratively until target article counts are met.

**Architecture:** 3 Parallel Agents → Exa Semantic Search → GPT-4 Evaluation → Iterative Refinement → Deduplication → Supabase Storage

## Agent Configuration

**Location:** `backend/services/agents/`

### Agent Types

**1. Conversational AI Agent** (`conversational_ai_agent.py`)
- **Focus:** Voice AI, chatbots, conversational interfaces, real-time speech
- **Target:** 3 articles per briefing
- **Query:** Real-time voice platforms, agent frameworks, speech-to-text, text-to-speech, agentic workflows

**2. General AI Agent** (`general_ai_agent.py`)
- **Focus:** Model releases, tool launches, API updates, AI infrastructure
- **Target:** 3 articles per briefing
- **Query:** AI model releases, developer tools, AI APIs, production systems, infrastructure

**3. Research/Opinion Agent** (`research_opinion_agent.py`)
- **Focus:** Research papers, thought leadership, industry analysis
- **Target:** 2 articles per briefing
- **Query:** Research papers, industry analysis, strategic insights, technical deep-dives

### Configuration Constants

**File:** `backend/services/agents/search_config.py`

```python
# Search parameters
SEARCH_DAYS_LOOKBACK = 4                    # Articles from past 4 days
EXA_SEARCH_TYPE = "deep"                    # Exa search type (deep/neural)
EXA_LIVECRAWL = "always"                    # Always fetch fresh content
EXA_MAX_CHARACTERS_DEFAULT = 1000           # Summary length for conversational/general
EXA_MAX_CHARACTERS_RESEARCH = 1500          # Longer summaries for research
EXA_USER_LOCATION = "US"                    # Geographic preference

# Evaluation thresholds
EVALUATION_THRESHOLD_ITERATION_1 = 4.0      # First iteration: keep scores >= 4.0
EVALUATION_THRESHOLD_ITERATION_2_PLUS = 3.8 # Later iterations: lower threshold

# Search limits
SEARCH_LIMIT_ITERATION_1 = 5                # Fetch 5 results per iteration
SEARCH_LIMIT_ITERATION_2_PLUS = 5           # Consistent across iterations

# Domain filtering
LOW_QUALITY_DOMAINS = {
    "medium.com",
    "dev.to",
    "hackernoon.com",
    "towardsdatascience.com",
    "levelup.gitconnected.com"
}
```

## Core Components

### 1. Search Orchestrator (`search_orchestrator.py`)

**Purpose:** Coordinate all 3 specialist agents in parallel.

**Function:** `search_all_categories(max_iterations, use_cache, run_source)`

**Parameters:**
- `max_iterations` (int): Max refinement iterations per agent (default: 2)
- `use_cache` (bool): Use cached results if available (default: True)
- `run_source` (str): "manual" or "automated" for tracking

**Flow:**
1. Initialize all 3 agents with run_source parameter
2. Launch agents in parallel using `asyncio.gather`
3. Handle exceptions gracefully (don't fail entire orchestrator if one agent fails)
4. Merge results by category
5. Calculate statistics
6. Return aggregated results

**Returns:**
```python
{
    'conversational_ai': [SearchResult, ...],  # 3 articles
    'general_ai': [SearchResult, ...],          # 3 articles
    'research_opinion': [SearchResult, ...],    # 2 articles
    'total': 8,
    'by_category_count': {
        'conversational_ai': 3,
        'general_ai': 3,
        'research_opinion': 2
    }
}
```

### 2. Base Search Agent (`base_search_agent.py`)

**Purpose:** Abstract base class with shared logic for all specialist agents.

**Key Responsibilities:**
- LangGraph workflow management
- Exa API integration
- GPT-4 evaluation
- Query refinement
- Deduplication
- Caching

#### LangGraph Workflow

**Nodes:**
1. **plan_search** - Load query and initialize state
2. **execute_search** - Call Exa API and deduplicate
3. **evaluate_results** - Score articles with GPT-4
4. **should_continue** - Decision: stop or refine?
5. **plan_followup_search** - Generate refined query with LLM

**State:**
```python
{
    'iteration': int,
    'current_query': str,
    'all_raw_results': List[SearchResult],
    'evaluated_results': List[Dict],
    'kept_articles': List[SearchResult],
    'discarded_urls': Set[str],
    'message': str
}
```

**Flow:**
```
START → plan_search → execute_search → evaluate_results → should_continue
                                                              ↓
                                      stop ← END ←──────── continue
                                                              ↓
                                    plan_followup_search ────┘
```

#### Core Methods

**`search(max_iterations, use_cache)`**
- Entry point for agent execution
- Compiles and executes LangGraph workflow
- Returns final kept_articles

**`_plan_search(state)`**
- Loads base query from specialist class
- Initializes state for iteration 1
- Returns updated state

**`_execute_search(state)`**
- Calls Exa API with current query
- Filters by domain quality and recency
- Removes URL duplicates
- Applies cross-content deduplication (checks Supabase)
- Returns raw results

**`_evaluate_results(state)`**
- Sends articles to GPT-4 for scoring
- Uses 4-criteria evaluation (Relevance, Actionability, Source Quality, Recency)
- Applies threshold (4.0 first iteration, 3.8 later)
- Keeps articles above threshold
- Returns evaluation results

**`_should_continue(state)`**
- Checks if target article count met
- Checks if max iterations reached
- Returns "stop" or "continue"

**`_plan_followup_search(state)`**
- Uses GPT-4 to refine query based on discarded results
- Generates more specific query to avoid low-quality matches
- Returns refined query

**`_filter_duplicates(articles)`**
- Queries Supabase for content from past 5 days
- Checks against: agent_search, newsletter, podcast sources
- Logs detailed duplicate info (source_type, source_name, created_at)
- Returns filtered articles

**`_finalize_results(state)`**
- Saves accepted articles to Supabase ContentItem table
- Includes source_name as `{query_type}|{run_source}` (e.g., "conversational_ai|automated")
- Returns kept_articles

### 3. Exa Integration

**File:** `backend/ingestion/search_providers/exa_provider.py`

**Class:** `ExaProvider`

**Method:** `search_with_contents(query, max_results, max_characters, ...)`

**Parameters:**
- `query` (str): Natural language search query
- `max_results` (int): Number of results to return
- `max_characters` (int): Summary length (1000 or 1500)
- `search_type` (str): "deep" (semantic) or "neural" (keyword)
- `live_crawl` (str): "always", "never", "fallback"
- `start_published_date` (str): ISO timestamp for recency filter
- `user_location` (str): Geographic preference

**Flow:**
1. Initialize Exa client with API key
2. Call `exa.search_and_contents()`
3. Parse results into SearchResult objects
4. Return list of results

**SearchResult:**
```python
{
    'url': str,
    'title': str,
    'summary': str,           # Exa-generated summary
    'published_date': str,    # ISO timestamp
    'author': str,
    'score': float,           # Exa relevance score
    'source': str,            # 'exa'
    'query_type': str,        # 'conversational_ai', 'general_ai', 'research_opinion'
}
```

### 4. GPT-4 Evaluation

**File:** `backend/services/agents/base_search_agent.py:_evaluate_articles`

**Purpose:** Score articles on 4 criteria to determine relevance.

**Model:** gpt-4.1-mini  
**Temperature:** 0.3

**Evaluation Criteria:**
1. **Relevance (1-5):** How relevant to the search query and target audience
2. **Actionability (1-5):** Contains practical takeaways, tools, or workflows
3. **Source Quality (1-5):** Prioritizes newsworthy launches/updates, original sources
4. **Recency/Impact (1-5):** Recent and significant developments

**Prompt Structure:**
```
Evaluate these articles for an AI Product Manager on a 4-criteria scale (1-5).

CRITERIA:
1. Relevance: How relevant to "{query_type}" and AI PM needs
2. Actionability: Practical takeaways, tools, workflows
3. Source Quality: Original sources, official announcements (not news aggregators)
4. Recency/Impact: Recent and significant

For each article:
1. Provide scores (1-5) for each criterion
2. Calculate overall_score (average of 4 scores)
3. Decision: "keep" if overall_score >= {threshold}, else "discard"
4. One-sentence reasoning

Return JSON array with evaluations.
```

**Response Format:**
```json
[
    {
        "url": "https://...",
        "relevance": 5,
        "actionability": 4,
        "source_quality": 5,
        "recency_impact": 4,
        "overall_score": 4.5,
        "decision": "keep",
        "reasoning": "Official Claude 3 announcement with technical details"
    },
    ...
]
```

**Threshold Logic:**
- Iteration 1: Keep if `overall_score >= 4.0`
- Iteration 2+: Keep if `overall_score >= 3.8`
- Lower threshold on refinement iterations to allow more results through

### 5. Query Refinement

**File:** `backend/services/agents/base_search_agent.py:_plan_followup_search`

**Purpose:** Generate improved search query based on discarded results.

**Model:** gpt-4.1-mini  
**Temperature:** 0.3

**Prompt:**
```
Refine this search query to find better articles.

ORIGINAL QUERY:
{original_query}

RECENT DISCARDED RESULTS (to avoid):
- {url} (Score: {score}) - {reasoning}
...

TASK:
Refine the query to avoid low-quality results. Keep the core focus but add specificity to get better articles.

RULES:
1. Remove terms that led to poor results
2. Add phrases to emphasize product announcements, APIs, launches
3. Explicitly avoid tutorials, getting started guides
4. Keep query concise (2-3 sentences max)

Return ONLY the refined query text (no JSON, no explanation).
```

**Output:** Refined query string used in next iteration

### 6. Cross-Content Deduplication

**File:** `backend/services/agents/base_search_agent.py:_filter_duplicates`

**Purpose:** Prevent duplicate articles from past 5 days across all sources.

**Flow:**
1. Call `CacheService.get_recent_content_urls(days=5)`
2. Query Supabase ContentItem table for all content from past 5 days
3. Build dictionary: `{url: {source_type, source_name, created_at, title}}`
4. For each search result:
   - Check if URL in seen_content dictionary
   - If duplicate: Log details and skip
   - If new: Keep
5. Return filtered list

**Duplicate Logging:**
```
DUPLICATE FOUND: {article_title}
    URL: {url}
    Source: {source_type} ({source_name})
    Original Date: {created_at}
    Skipping to avoid redundancy.
```

**Sources Checked:**
- `agent_search` - Previous agent searches
- `newsletter` - TLDR AI and other newsletters
- `assemblyai_transcript` - Podcast episodes
- All sources within 5-day window

### 7. Caching

**Database Table:** `content_items`

**Fields Saved:**
- `source_type`: 'agent_search'
- `source_name`: '{query_type}|{run_source}' (e.g., 'conversational_ai|automated')
- `item_url`: Article URL (unique key)
- `title`: Article title
- `summary`: Exa-generated summary
- `published_date`: Article publication date
- `created_at`: Timestamp when saved

**Cache Key:** Article URL

**Deduplication:** Prevents same URL from being shown twice within 5 days

## Daily Briefing Integration

**File:** `backend/scripts/morning_briefing.py`

### Processing Flow

**Step 1: Run Orchestrator**
```python
articles_result = await search_all_categories(
    max_iterations=2,
    use_cache=False,
    run_source="automated"
)
```

**Step 2: Flatten Results**
```python
articles = flatten_results(articles_result)
```
- Combines all 3 agent results into single list
- Preserves query_type metadata

**Step 3: Display in Email**
```markdown
## Top AI Articles

### Article Title
[Summary from Exa - 1000 or 1500 characters]

Source: {source} | Category: {query_type}

[Read more](article_url)

---
```

## Test Mode

**File:** `backend/test_config.py`

**Environment Variable:** `TEST_MODE=true`

**Test Mode Overrides:**
```python
AGENT_MAX_ITERATIONS = 1                # Reduce from 2 to 1
AGENT_TARGET_ARTICLES = {
    'conversational_ai': 1,             # Reduce from 3 to 1
    'general_ai': 1,                    # Reduce from 3 to 1
    'research_opinion': 1               # Reduce from 2 to 1
}
EXA_SEARCH_TYPE = "neural"              # Faster than "deep"
EXA_SEARCH_LIMIT = 2                    # Reduce from 5 to 2
EXA_LIVECRAWL = "never"                 # Skip live crawling
```

**Impact:**
- Total articles: 8 → 3
- Search calls: ~6-12 → ~3
- Exa cost: ~$0.20-0.40 → ~$0.05-0.10
- Runtime: ~30-60 seconds → ~10-20 seconds

## Cost Analysis

### Exa Search Costs
- **Search API:** $1 per 1,000 searches
- **Contents API:** $3 per 1,000 contents retrieved
- **Typical run:** 6-12 searches + 30-60 contents
- **Cost per run:** $0.03-0.06 (searches) + $0.09-0.18 (contents) = **$0.12-0.24**

### GPT-4 Evaluation Costs
- **Input:** ~2,000-4,000 tokens (article summaries + evaluation prompt)
- **Output:** ~500-1,000 tokens (JSON evaluation results)
- **Cost per evaluation batch:** ~$0.01-0.02
- **Total evaluations:** 2-4 batches per run
- **Cost per run:** **$0.02-0.08**

### GPT-4 Query Refinement Costs
- **Input:** ~500-1,000 tokens (discarded results + refinement prompt)
- **Output:** ~100-200 tokens (refined query)
- **Cost per refinement:** ~$0.001-0.002
- **Total refinements:** 0-3 per agent (3 agents)
- **Cost per run:** **$0.003-0.018**

### Total Daily Cost
- Exa: $0.12-0.24
- GPT-4 Evaluation: $0.02-0.08
- GPT-4 Refinement: $0.003-0.018
- **Total: $0.143-0.338 per day**

## Error Handling

### Common Failure Modes

**1. Exa API Error**
- Cause: Rate limit, API key invalid, network timeout
- Handling: Agent returns empty results, doesn't crash orchestrator
- Impact: One category missing from briefing
- Fix: Check Exa API key and quota

**2. GPT-4 Evaluation Failed**
- Cause: Malformed JSON response, API error, rate limit
- Handling: Fall back to keeping all articles (no filtering)
- Impact: Lower quality articles may appear
- Fix: Retry with exponential backoff

**3. Deduplication Query Failed**
- Cause: Database connection error, invalid DATABASE_URL
- Handling: Skip deduplication, proceed without filtering
- Impact: Potential duplicate articles in briefing
- Fix: Verify DATABASE_URL environment variable

**4. No Articles Found**
- Cause: Search query too specific, no recent content, all results filtered
- Handling: Agent triggers refinement (up to max_iterations)
- Impact: May return fewer than target articles
- Fix: Lower evaluation threshold or increase search days lookback

**5. Query Refinement Failed**
- Cause: GPT-4 error, malformed prompt
- Handling: Reuse original query for next iteration
- Impact: May not improve results on refinement
- Fix: Check query refinement prompt and response parsing

### Retry Logic
- Exa API: No retries (fail fast)
- GPT-4: No retries (expensive)
- Database: No retries (fail fast)
- **Recommendation:** Implement exponential backoff for GPT-4 calls

## Testing

### Local Testing
```bash
# Test with test mode enabled
TEST_MODE=true python tests/test_agent_search.py
```

**Output:**
- Iteration logs for each agent
- Article counts per category
- Sample article titles and summaries
- Total runtime

### Test Individual Agent
```python
import asyncio
from podcast-summarizer.backend.services.agents.conversational_ai_agent import ConversationalAIAgent

async def test():
    agent = ConversationalAIAgent(run_source="manual")
    results = await agent.search(max_iterations=2, use_cache=False)
    print(f"Found {len(results)} articles")
    
asyncio.run(test())
```

## LangGraph Studio Integration

### Graph Visualization
- Each agent is a separate LangGraph graph
- View in LangGraph Studio for debugging
- Step-by-step execution inspection
- State visualization at each node

### Configuration
**File:** `langgraph.json`

**Graphs:**
- `conversational_ai_agent`
- `general_ai_agent`
- `research_opinion_agent`
- `search_orchestrator`

### Usage
```bash
langgraph dev --watch --host 0.0.0.0 --port 8123
```

## Known Issues and Limitations

### 1. No Retry Logic
**Issue:** Failed API calls don't retry.  
**Impact:** Agent may return fewer articles than target.  
**Fix:** Implement exponential backoff for Exa and GPT-4 calls.

### 2. Deduplication Only Checks URLs
**Issue:** Same article at different URLs (AMP, canonical) not detected.  
**Impact:** Duplicate content may appear.  
**Fix:** Implement semantic similarity check using embeddings.

### 3. Static Evaluation Thresholds
**Issue:** Thresholds (4.0, 3.8) don't adapt to result quality.  
**Impact:** May filter too aggressively or not enough.  
**Fix:** Dynamic threshold adjustment based on available results.

### 4. No Caching for Today's Results
**Issue:** `use_cache=False` always in production, doesn't reuse today's search.  
**Impact:** Re-runs searches even if already done today.  
**Fix:** Implement date-based cache key, return cached results for same day.

### 5. Query Refinement Limited Context
**Issue:** Only uses last 10 discarded results for refinement.  
**Impact:** May not learn from all bad results.  
**Fix:** Include more context or aggregate learnings across iterations.

## Future Enhancements

### Short-term
- Add retry logic with exponential backoff
- Implement semantic deduplication using embeddings
- Dynamic threshold adjustment based on result quality
- Date-based caching for daily results

### Long-term
- Multi-day trend detection (track recurring topics)
- User feedback loop (learn from clicked vs ignored articles)
- Cross-agent learning (share successful queries/patterns)
- Custom embedding model for better semantic matching

