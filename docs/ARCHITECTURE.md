# System Architecture

**Last Updated:** November 16, 2025

---

## Overview

The Morning Automation system is an AI-powered briefing tool that curates AI articles, transcribes podcasts, and processes newsletters to deliver a personalized daily email every weekday at 9:30 AM ET.

**Key Innovation:** Multi-agent architecture with cross-content deduplication and cost-optimized caching.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       DATA SOURCES                           │
│  Exa Search  │  Gmail API (Newsletter)  │  RSS Feeds (Podcasts) │
└──────┬───────┴──────────┬───────────────┴─────────┬─────────┘
       │                  │                         │
       ▼                  ▼                         ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────────────┐
│ 3 Search Agents │  │  Newsletter   │  │  Podcast Processing  │
│  (LangGraph)    │  │  Processing   │  │  • Fetch RSS         │
│ • Conversational│  │  • Parse HTML │  │  • Download MP3      │
│ • General AI    │  │  • Extract    │  │  • Transcribe (AAI)  │
│ • Research      │  │    articles   │  │  • Cache transcripts │
└────────┬────────┘  └───────┬──────┘  └──────────┬───────────┘
         │                   │                     │
         └───────────────────┼─────────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │   AI Evaluation       │
                  │   • GPT-4.1-mini      │
                  │   • 4-criteria scoring│
                  │   • Deduplication     │
                  └──────────┬───────────┘
                             │
                  ┌──────────▼───────────┐
                  │  Supabase (Postgres) │
                  │  • Content cache      │
                  │  • Insights           │
                  │  • Dedup checking     │
                  └──────────┬───────────┘
                             │
                  ┌──────────▼───────────┐
                  │   Email Delivery      │
                  │   Mon-Fri @ 9:30 AM   │
                  │   (GitHub Actions)    │
                  └──────────────────────┘
```

---

## Component Details

### 1. Multi-Agent Search System (LangGraph)

**Three Parallel Specialist Agents:**

**Agent 1: Conversational AI**
- Searches for: chatbots, voice AI, conversational interfaces
- Target: 3 articles/day
- Query focus: Product launches, feature updates, commercial applications

**Agent 2: General AI**
- Searches for: AI models, tools, frameworks, industry developments
- Target: 3 articles/day
- Query focus: Newsworthy launches, technical updates, ecosystem changes

**Agent 3: Research/Opinion**
- Searches for: Research papers, thought leadership, analysis
- Target: 2 articles/day
- Query focus: Academic papers, expert opinions, trend analysis

**Orchestration:**
- All agents run in parallel (async execution)
- Each uses Exa semantic search with deep mode
- Results aggregated and deduplicated
- Total output: 8 high-quality articles

### 2. Article Evaluation

**4-Criteria Scoring System (1-5 scale):**

1. **Relevance** - How relevant to the specific search query
2. **Actionability** - Contains practical takeaways, tools, or workflows
3. **Source Quality** - Prioritizes newsworthy launches/updates, original sources
4. **Recency/Impact** - Recent and significant developments

**Acceptance Threshold:**
- Score 4+ accepted
- Score <4 rejected
- Threshold adjusts based on iteration (stricter first pass, more lenient if needed)

**Iterative Refinement:**
- If targets not met: refine query and search again
- Max 2-3 iterations per agent
- Query refinement uses LLM to adjust based on what was found/missing

### 3. Cross-Content Deduplication

**Purpose:** Prevent sending duplicate articles across all content sources

**How It Works:**
1. Before accepting any article, check Supabase for URL matches
2. Check against: podcasts, newsletters, previous agent searches
3. Lookback window: Past 5 days
4. Detailed logging of all duplicates found

**Benefits:**
- Higher briefing quality
- No redundant information
- Better user experience

### 4. Podcast Processing

**Supported Podcasts (6 total):**
- Lenny's Podcast (Product Management)
- MLOps.community Podcast (ML Operations)
- TWiML AI Podcast (Machine Learning & AI)
- The AI Daily Brief (AI News)
- Data Skeptic (Data Science)
- DataFramed by DataCamp (Data Science)

**Processing Pipeline:**
1. **Fetch** - Parse RSS feed for latest episodes
2. **Transcribe** - Download MP3 → AssemblyAI transcription
3. **Cache** - Save transcript to Supabase (permanent)
4. **Summarize** - GPT-4.1-mini generates insights and practical tips
5. **Categorize** - Primary podcasts get detailed summaries, secondary get brief links

**Cache-First Strategy:**
- Always check Supabase before transcribing
- Only transcribe once per episode (saves cost)

### 5. Newsletter Processing

**Supported Newsletter:**
- TLDR AI (via Gmail API)

**Processing Pipeline:**

1. **Fetch** - Gmail API fetches latest newsletter (OAuth 2.0)
2. **Parse HTML** - Extract all article links (typically 15-20 articles)
3. **Filter ads/spam** - Remove unsubscribe links, UTM campaigns, sponsor content
4. **AI Filtering & Ranking** - GPT-4.1-mini evaluates all articles:
   - Filters out sponsored/marketing content
   - Ranks by relevance to AI Product Managers
   - Selects top 8 most relevant articles
   - Returns ranked list
5. **Add to briefing** - Included in final email with article descriptions

**Why AI Filtering:**
- TLDR AI typically includes 15-20 articles per issue
- Many are sponsored content or general tech news (not AI-specific)
- AI filtering ensures only AI PM-relevant articles make it to briefing
- Reduces noise, improves signal-to-noise ratio

**Filtering Criteria:**
- Relevance to AI Product Management
- Technical depth and actionability
- Excludes: sponsored posts, generic tech news, HR/recruiting posts
- Includes: AI tools, model releases, product updates, industry analysis

**Result:** ~50% noise reduction (from 15-20 down to 8 high-quality articles)

---

## Data Storage (Supabase)

**PostgreSQL Database with 3 Tables:**

### content_items
- Stores: podcasts, articles, newsletters
- Indexed on: source_name, item_url, published_date
- Used for: caching transcripts, deduplication

### insights
- Stores: AI-generated summaries and tips
- Links to: content_items
- Tracks: model_name, token_count, cost

### briefings
- Stores: historical archive of sent briefings
- Includes: date, title, content, metadata

**Why Supabase:**
- GitHub Actions needs persistent storage (not local SQLite)
- Enables cross-content deduplication
- Free tier sufficient for this use case
- No database file management in git

---

## Deployment (GitHub Actions)

**Schedule:** Monday-Friday at 9:30 AM ET

**Workflow:**
1. Checkout code
2. Setup Python 3.11
3. Install dependencies (with caching)
4. Run morning_briefing.py
   - Phase 1: AI agent search (8 articles via Exa)
   - Phase 2: Newsletter processing (8 stories from TLDR AI)
   - Phase 3: Podcast processing (6 podcasts via AssemblyAI)
   - Phase 4: Generate and send email
5. Upload logs on failure

**Environment Variables:**
- API keys: OpenAI, Exa, AssemblyAI, LangSmith
- Database: DATABASE_URL (Supabase connection string)
- Email: SMTP credentials
- All stored as GitHub Secrets

**Cost:** $0/month (GitHub Actions free tier)

---

## Cost Optimization

### 1. Test Mode
**Purpose:** Reduce costs during local development

**Configuration:**
- Set `TEST_MODE=true` environment variable
- Reduces article targets (3 total instead of 8)
- Uses cheaper Exa search type (neural vs deep)
- Limits iterations to 1
- Disables livecrawl

**Savings:** ~97% cost reduction in test mode

### 2. Caching Strategy
**Podcast Transcripts:**
- Cached permanently in Supabase
- Only transcribe once per episode
- Saves AssemblyAI API costs

**Agent Search Results:**
- Saved to Supabase with metadata
- Enables deduplication
- Historical tracking

**Cache-First Approach:**
- Always check database before API calls
- Minimize redundant processing
- Track cache hit rates

---

## Key Design Decisions

### Multi-Agent vs. Monolithic
**Decision:** 3 separate specialist agents with orchestrator

**Rationale:**
- Better debuggability (inspect each agent independently)
- Parallel execution (faster overall runtime)
- Specialist queries produce better results
- Easier to adjust targets per category

### AssemblyAI for All Podcasts
**Decision:** Use AssemblyAI instead of YouTube transcripts

**Rationale:**
- YouTube transcript API had IP blocking issues
- AssemblyAI provides consistent, high-quality transcription
- Works for all podcasts regardless of platform
- Cache-first strategy minimizes costs

### Cross-Content Deduplication
**Decision:** Check all content from past 5 days

**Rationale:**
- Prevents sending same article multiple times
- Improves briefing quality
- 5 days balances freshness with coverage

### LLM-Based Evaluation
**Decision:** Use GPT-4.1-mini for scoring instead of rules

**Rationale:**
- Better understanding of relevance and quality
- Adapts to nuanced criteria
- Handles edge cases better than keyword matching

---

## Observability

### LangSmith
- End-to-end tracing of all LLM calls
- Token usage tracking
- Error logging
- Performance monitoring

### LangGraph Studio
- Visual debugging of agent workflows
- Step-by-step execution inspection
- State visualization
- Local development server

### Logging
- Detailed logs for all operations
- Deduplication logging (what was filtered and why)
- Run source tracking (manual vs automated)
- Cost tracking per component

---

## API Services

**AI Services:**
- Exa AI - Semantic web search
- OpenAI GPT-4.1-mini - Evaluation and summarization
- AssemblyAI - Podcast transcription
- LangSmith - LLM observability

**Infrastructure:**
- Supabase - PostgreSQL database
- GitHub Actions - CI/CD and scheduling
- Gmail API - Newsletter fetching
- SMTP - Email delivery

---

## Security

**API Key Management:**
- All keys in `.env` locally (gitignored)
- GitHub Secrets in production
- No credentials in code or git history

**Database:**
- Supabase provides SSL/TLS encryption
- Connection pooling with health checks
- Password-protected

**Email:**
- Gmail App Password (not regular password)
- SMTP over TLS

---

## Performance

**Typical Runtime:**
- Agent search: 30-60 seconds (3 agents in parallel)
- Podcast processing: 20-40 seconds (if cached)
- Newsletter processing: 5-10 seconds
- Total: ~1-2 minutes for full briefing

**Scalability:**
- Designed for single user (no multi-tenancy)
- Could scale to ~100 users with current architecture
- Database and API limits would need adjustment beyond that

---

## Future Considerations

**Not Currently Implemented (by design):**
- Web UI - adds complexity, no clear value for single user
- Multi-user support - scope creep, not needed
- Additional content sources - quality > quantity
- Mobile app - overkill for daily email

**Potential Improvements Based on Usage:**
- Adjust evaluation criteria based on feedback
- Fine-tune article targets per category
- Optimize search queries based on results
- Add analytics tracking

---

## Documentation

**Setup Guides:**
- `docs/GMAIL_NEWSLETTER_SETUP.md` - Gmail API setup
- `docs/EMAIL_SETUP.md` - SMTP configuration
- `docs/LANGGRAPH_SETUP.md` - LangGraph Studio setup
- `docs/PERPLEXITY_SETUP.md` - Perplexity API (legacy)

**Reference:**
- `FEATURES.md` - Complete feature list
- `DEPLOYMENT_CHECKLIST.md` - Deployment steps
- `LOCAL_TESTING.md` - Local testing guide
- `TEST_MODE_SUMMARY.md` - Test mode documentation
- `SUPABASE_SETUP_INSTRUCTIONS.md` - Database setup

**Historical:**
- `docs/archive/old-architecture/` - Previous architecture documentation

---

## Tech Stack Summary

**Language:** Python 3.11
**Framework:** FastAPI (local API), LangGraph 1.0+ (agents)
**Database:** Supabase (PostgreSQL)
**Deployment:** GitHub Actions
**AI Services:** Exa, OpenAI, AssemblyAI, LangSmith

