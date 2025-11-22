# AI-Powered Morning Briefing System

An automated daily briefing system that curates AI articles, summarizes podcasts, and processes newsletters to deliver a personalized morning update every weekday at 9:30 AM ET.

## 📋 What It Does

This system automatically:
1. **Curates** - 3 parallel AI agents search for 8 high-quality AI articles daily
2. **Processes** - Transcribes podcasts and parses newsletters using AI
3. **Delivers** - Sends a clean HTML email briefing with deduplication

### Content Sources

**AI Search Agents (Exa + LangGraph):**
- Conversational AI articles (3/day)
- General AI developments (3/day)
- Research papers & opinion pieces (2/day)

**Podcasts (5 total, AssemblyAI transcription):**
- Lenny's Podcast
- MLOps.community Podcast
- TWiML AI Podcast
- Data Skeptic
- DataFramed by DataCamp

**Newsletter (Gmail API with AI filtering):**
- TLDR AI (top 8 stories selected via AI from 15-20)

## 🎯 Why I Built This

As an AI Product Manager, staying current on AI developments is critical. However:
- Manually reading newsletters and articles is time-consuming
- Listening to full podcasts (30-60 min each) isn't always practical
- Important insights are buried in noise and filler content
- Quality curation requires time and attention

**This system automates the entire workflow:**
- AI agents find and evaluate high-quality articles using semantic search
- Podcasts are transcribed and summarized with key takeaways
- Cross-content deduplication prevents redundant information
- Everything arrives in one email at a consistent time

## 🏗️ Technical Architecture

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
                  │   • GPT-4o-mini       │
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

## ✨ Key Features

### 1. **Multi-Agent AI Search (LangGraph)**
- 3 parallel specialist agents with distinct search strategies
- Semantic search using Exa AI (finds articles by meaning, not keywords)
- LLM-based evaluation with 4-criteria scoring (Relevance, Actionability, Source Quality, Recency)
- Iterative refinement when targets not met

### 2. **Cross-Content Deduplication**
- Checks all content from past 5 days before adding to briefing
- Prevents duplicate articles across newsletters, podcasts, and agent searches
- Detailed logging of duplicate detection
- Tracks run source (manual vs automated) for analytics

### 3. **Podcast Transcription & Caching**
- AssemblyAI transcription for all 6 podcasts (high-quality speech-to-text)
- All transcripts cached permanently in Supabase to avoid re-transcription costs
- Cache-first strategy: checks Supabase before calling AssemblyAI API
- Priority system: primary podcasts get detailed summaries, secondary get brief links

### 4. **Test Mode for Development**
- Reduces article targets (3 total instead of 8)
- Uses cheaper Exa search options
- Limits iterations to minimize costs
- Configured via `TEST_MODE` environment variable

### 5. **GitHub Actions Automation**
- Serverless deployment (no server maintenance)
- Scheduled runs Monday-Friday at 9:30 AM ET
- Manual trigger available for testing
- Automatic log uploads on failure

---

## 📖 Detailed Component Breakdown

### 🤖 AI Search Agents

**Three Parallel Specialist Agents:**
- **Conversational AI Agent** - Finds 3 articles on chatbots, voice AI, and conversational interfaces
- **General AI Agent** - Finds 3 articles on AI models, tools, and general developments
- **Research/Opinion Agent** - Finds 2 articles on research papers and thought leadership

**Agent Capabilities:**
- **LangGraph Multi-Agent Architecture** - Each agent runs independently and in parallel
- **Exa Semantic Search** - Finds articles by meaning, not just keywords
- **LLM-Based Evaluation** - GPT-4.1-mini scores each article on 4 criteria (1-5 scale)
- **Iterative Refinement** - Agents can run multiple search iterations if targets not met
- **Query Refinement** - Failed searches trigger query adjustments using LLM

**Smart Filtering:**
- **Cross-Content Deduplication** - Checks against all content from past 5 days (podcasts, newsletters, previous agent searches)
- **Low-Quality Domain Filter** - Excludes news aggregators and low-signal sources
- **Recency Filter** - Only articles from past 7 days
- **Dynamic Summary Length** - 1000 characters for regular articles, 1500 for research papers
- **News Aggregator Avoidance** - Prefers original sources over TechCrunch, VentureBeat, etc.

**Article Quality Criteria:**

Each article is evaluated on 4 dimensions (1-5 scale):
1. **Relevance** - How relevant to the specific search query
2. **Actionability** - Contains practical takeaways, tools, or workflows
3. **Source Quality** - Prioritizes newsworthy launches/updates and original sources
4. **Recency/Impact** - Recent and significant developments

Articles scoring 4+ are accepted. Threshold may adjust based on iteration.

### 🎧 Podcast Processing

**Supported Podcasts (6 total):**

*Primary (detailed summaries):*
- Lenny's Podcast - Product management insights
- MLOps.community Podcast - ML operations and production systems
- TWiML AI Podcast - This Week in Machine Learning & AI

*Secondary (brief links):*
- Data Skeptic - Data science and statistics
- DataFramed by DataCamp - Data science trends and tools

**Transcription Method:**

**AssemblyAI (all 6 podcasts):**
- Downloads MP3 files from RSS feeds
- Transcribes using AssemblyAI API (high-quality speech-to-text)
- First transcription costs apply, then permanently cached in Supabase
- No YouTube IP blocking issues

**Features:**
- **RSS Feed Parsing** - Fetches latest episodes automatically
- **AssemblyAI Transcription** - High-quality speech-to-text for all podcasts
- **Supabase Caching** - Transcripts cached permanently to avoid re-transcription costs
- **AI Summarization** - GPT-4o-mini generates insights and practical tips
- **Parallel Processing** - Multiple podcasts processed simultaneously
- **Priority System** - Primary podcasts get detailed summaries, secondary get brief links
- **Cache-First Strategy** - Always checks Supabase before transcribing (70%+ cache hit rate)

### 📧 Newsletter Processing

**Supported Newsletter:**
- TLDR AI (via Gmail API)

**AI-Powered Article Selection:**

*The Challenge:*
- TLDR AI newsletters contain 15-20 articles per issue
- Many are sponsored content or generic tech news
- Not all articles are relevant to AI Product Management

*The Solution:*

GPT-4.1-mini evaluates and ranks all articles, selecting only the top 8 most relevant:

**Filtering Criteria:**
- ✅ Relevance to AI Product Management
- ✅ Technical depth and actionability
- ✅ AI tools, model releases, product updates
- ❌ Sponsored/marketing content
- ❌ Generic tech news
- ❌ HR/recruiting posts

**Process:**
1. Fetch newsletter via Gmail API (OAuth 2.0)
2. Parse HTML and extract all article links
3. Filter out ads, unsubscribe links, UTM campaigns
4. **AI Evaluation** - LLM ranks articles by AI PM relevance
5. Select top 8 articles
6. Generate concise AI summaries
7. Add to briefing

**Result:** ~50% noise reduction (from 15-20 down to 8 high-quality articles)

### 💾 Database & Caching

**Supabase PostgreSQL:**
- **content_items table** - Stores podcasts, articles, newsletters
- **insights table** - Stores AI-generated summaries and tips
- **briefings table** - Archives sent briefings

**Caching Strategy:**
- Podcast transcripts cached permanently
- Agent search results saved with metadata
- Deduplication checks against all cached content
- Run source tracking (manual vs automated)

### 🧪 Test Mode Details

**Purpose:** Reduces API costs during local development and testing.

**What It Does:**
- Reduces article targets to 1 per agent (3 total instead of 8)
- Limits iterations to 1 instead of 2-3
- Uses cheaper Exa search type (`neural` vs `deep`)
- Disables live crawling
- Reduces search limits per query

**Usage:**
```bash
TEST_MODE=true python tests/test_agent_search.py
```

Configured in `test_config.py` with minimal code complexity.

### 🚀 Deployment & Automation Details

**GitHub Actions Workflow:**
- **Schedule** - Runs Monday-Friday at 9:30 AM ET
- **Manual Trigger** - Can be run manually via workflow_dispatch
- **Dependency Caching** - Caches pip packages for faster runs
- **Error Handling** - Uploads logs on failure for debugging

**Workflow Phases:**
1. Fetch latest code from GitHub
2. Set up Python 3.11
3. Install dependencies
4. Run morning_briefing.py script
   - Phase 1: AI agent search (8 articles)
   - Phase 2: Newsletter processing (8 stories from TLDR AI)
   - Phase 3: Podcast processing (6 podcasts)
   - Phase 4: Generate and send email via SMTP

### 🔍 Observability & Debugging

**LangGraph Studio:**
- Visual debugging of agent workflows
- Step-by-step execution inspection
- State visualization
- Local development server

**LangSmith:**
- End-to-end tracing of LLM calls
- Token usage tracking
- Error logging
- Performance monitoring

### 🔐 Security

**API Key Management:**
- All keys stored in `.env` (local) or GitHub Secrets (production)
- No credentials committed to git
- `.gitignore` configured to protect sensitive files

**Database:**
- Supabase provides SSL/TLS encryption
- Connection pooling with health checks
- Row-level security available (not currently configured)

---

## 🛠️ Tech Stack

### Core Framework
- **Python 3.11** - Main language
- **LangGraph 1.0+** - Multi-agent orchestration
- **FastAPI** - Web framework for local API
- **SQLAlchemy** - Database ORM

### AI Services
- **Exa AI** - Semantic web search
- **OpenAI GPT-4o-mini** - Article evaluation and summarization
- **AssemblyAI** - Podcast transcription
- **LangSmith** - LLM observability and tracing

### Infrastructure
- **Supabase** - PostgreSQL database hosting
- **GitHub Actions** - CI/CD and daily scheduling
- **Gmail API** - Newsletter fetching
- **SMTP** - Email delivery

## 🔑 Key Design Decisions

### 1. Multi-Agent Architecture (LangGraph)
**Decision**: 3 separate specialist agents instead of one monolithic agent  
**Rationale**: 
- Better debuggability (can inspect each agent independently)
- Parallel execution (faster overall runtime)
- Specialist queries produce better results than generic search
- Easier to adjust targets per category

### 2. AssemblyAI for All Podcasts
**Decision**: Use AssemblyAI for transcription instead of YouTube transcripts  
**Rationale**:
- YouTube transcript API had IP blocking issues
- AssemblyAI provides consistent, high-quality transcription
- Works for all podcasts regardless of platform
- Cache-first strategy minimizes API costs (only transcribe once)

### 3. Supabase vs. SQLite
**Decision**: Use Supabase (hosted PostgreSQL) instead of local SQLite  
**Rationale**:
- GitHub Actions needs persistent storage
- Enables cross-content deduplication
- No database file management in git
- Free tier sufficient for this use case

### 4. Cross-Content Deduplication
**Decision**: Check all content from past 5 days before adding articles  
**Rationale**:
- Prevents sending same article multiple times
- Improves briefing quality
- Uses database as source of truth
- 5 days balances freshness with coverage

### 5. Test Mode Configuration
**Decision**: Centralized test mode via environment variable  
**Rationale**:
- Reduces API costs during development
- Minimal code complexity (single config file)
- Easy to enable/disable
- Speeds up local iteration

### 6. LLM-Based Evaluation vs. Rule-Based
**Decision**: Use GPT-4o-mini for article scoring instead of keyword matching  
**Rationale**:
- Better understanding of relevance and quality
- Can adapt to nuanced criteria
- Handles edge cases better than rules
- Trade-off: Adds API cost but improves quality

## 📁 Project Structure

```
morning-automation/
├── .github/workflows/
│   └── morning-briefing.yml        # GitHub Actions workflow
├── podcast-summarizer/backend/
│   ├── api/                        # FastAPI routes
│   ├── database/
│   │   ├── db.py                   # Database connection (Supabase)
│   │   └── cache_service.py        # Caching & deduplication
│   ├── ingestion/
│   │   ├── sources.py              # Podcast sources
│   │   └── rss_parser.py           # RSS feed parsing
│   ├── services/
│   │   ├── agents/                 # LangGraph search agents
│   │   │   ├── base_search_agent.py         # Shared agent logic
│   │   │   ├── conversational_ai_agent.py   # Specialist agent
│   │   │   ├── general_ai_agent.py          # Specialist agent
│   │   │   ├── research_opinion_agent.py    # Specialist agent
│   │   │   ├── search_orchestrator.py       # Parallel execution
│   │   │   └── search_config.py             # Agent configuration
│   │   ├── podcast_processor.py    # Podcast processing
│   │   └── assemblyai_processor.py # Transcription
│   ├── scripts/
│   │   └── morning_briefing.py     # Main orchestration (GitHub Actions)
│   └── test_config.py              # Test mode configuration
├── supabase_schema.sql             # Database schema
├── test_agent_search.py            # Test search agents
├── test_podcast.py                 # Test podcast processing
├── test_newsletter.py              # Test newsletter processing
├── langgraph.json                  # LangGraph Studio config
├── FEATURES.md                     # Complete feature list
├── DEPLOYMENT_CHECKLIST.md         # Deployment guide
└── README.md                       # This file
```

## 🚀 Setup & Installation

### Prerequisites
- Python 3.11+ (required for LangGraph Studio)
- OpenAI API key
- Exa AI API key
- Supabase account (free tier)
- Gmail API credentials (optional, for newsletter fetching)
- AssemblyAI API key (optional, for podcast transcription)

### Quick Local Setup

1. **Clone and install dependencies**
```bash
git clone https://github.com/YOUR_USERNAME/morning-automation.git
cd morning-automation
python3.11 -m venv venv-3.11
source venv-3.11/bin/activate
pip install -r podcast-summarizer/backend/requirements.txt
```

2. **Configure environment variables**
Create a `.env` file:
```bash
# Required
OPENAI_API_KEY=sk-proj-...
EXA_API_KEY=...
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.PROJECT_ID.supabase.co:5432/postgres
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_RECIPIENT=your-email@gmail.com

# Optional
ASSEMBLYAI_API_KEY=...
LANGSMITH_API_KEY=...
```

3. **Test components locally**
```bash
# Test search agents (with test mode for lower cost)
TEST_MODE=true python tests/test_agent_search.py

# Test podcast processing
python tests/test_podcast.py

# Test newsletter fetching
python tests/test_newsletter.py
```

### GitHub Actions Deployment

1. Push code to GitHub
2. Add secrets to repository (Settings → Secrets and variables → Actions)
3. Manually trigger workflow to test
4. Automatic runs Monday-Friday at 9:30 AM ET

For complete deployment instructions, see `docs/archive/SETUP_CONSOLIDATED.md`.

## 🔧 Troubleshooting

### API Errors
- Verify API keys in `.env` are correct (no quotes, no spaces)
- Check API quotas in provider dashboards
- Review logs for specific error messages

### Email Not Sending
- Use Gmail app password (not regular password)
- Generate at https://myaccount.google.com/apppasswords
- Check `EMAIL_RECIPIENT` is set correctly

### Empty Results
- Verify Supabase `DATABASE_URL` format is correct
- Ensure database tables exist (run `supabase_schema.sql`)
- For podcasts: Cache must be populated first (expected behavior)

### GitHub Actions Not Running
- Check Actions tab is enabled in repository settings
- Verify cron schedule uses UTC time
- Repos inactive >60 days auto-disable workflows

For detailed troubleshooting, see `docs/archive/TESTING_CONSOLIDATED.md`.

## ⚠️ Known Limitations

### Exa AI Formatting
**Issue**: Exa's API does not consistently respect paragraph formatting instructions in `summary_query`.

**Impact**: Summaries may return with bullet points despite requesting "flowing paragraphs" or "NO bullet points".

**Workaround**: The system includes a post-processing step (`clean_exa_summary_with_llm`) that uses GPT-4o-mini to convert bullet-formatted summaries to flowing paragraphs before including them in the email. This ensures the final briefing maintains consistent paragraph formatting.

**Cost Impact**: Minimal (~$0.001 per article for summary reformatting).

### Exa API 500 Errors
**Issue**: Exa occasionally returns HTTP 500 errors depending on search parameters (query complexity, `livecrawl` setting, search type).

**Impact**: Intermittent search failures requiring retry logic.

**Workaround**: The search agents include automatic retry logic with exponential backoff. Failed searches are logged and don't crash the entire pipeline. Most failures resolve on retry.

**Mitigation Strategy**: 
- Use simpler query structures when possible
- Implement fallback search strategies in agent refinement
- Monitor LangSmith traces for patterns in failures

## 🧩 Component Testing

Individual components can be tested locally:

```bash
# Test search agents (with test mode for lower cost)
TEST_MODE=true python tests/test_agent_search.py

# Test podcast processing
python tests/test_podcast.py

# Test newsletter fetching
python tests/test_newsletter.py

# Test database connectivity
python tests/test_supabase_connection.py

# Validate dependencies
python tests/test_imports.py
```

All tests support `TEST_MODE` environment variable.

## 📚 Documentation

**Active Documentation:**
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture overview
- **[docs/AGENT_SEARCH_REFERENCE.md](docs/AGENT_SEARCH_REFERENCE.md)** - Multi-agent search system (Exa + LangGraph)
- **[docs/NEWSLETTER_REFERENCE.md](docs/NEWSLETTER_REFERENCE.md)** - Newsletter processing (Gmail API + AI filtering)
- **[docs/PODCAST_REFERENCE.md](docs/PODCAST_REFERENCE.md)** - Podcast transcription (AssemblyAI + GPT-4)
- **[docs/BRIEFING_REFERENCE.md](docs/BRIEFING_REFERENCE.md)** - Daily briefing pipeline

**Archived Documentation:** (setup guides, testing guides, historical references)
- **[docs/archive/SETUP_CONSOLIDATED.md](docs/archive/SETUP_CONSOLIDATED.md)** - Complete setup reference
- **[docs/archive/TESTING_CONSOLIDATED.md](docs/archive/TESTING_CONSOLIDATED.md)** - Testing strategies
- **[docs/archive/](docs/archive/)** - All historical documentation

## 📈 Future Enhancements

**Potential Improvements** (not currently prioritized):
- [ ] Web UI for browsing past briefings
- [ ] Custom podcast generation (via NotebookLM)
- [ ] Slack/Discord delivery options
- [ ] Multi-user support with personalized preferences
- [ ] Mobile app for on-the-go reading

## 🎯 What This Project Demonstrates

### Product Skills
- Identified real user need (staying current on AI developments efficiently)
- Iterative refinement based on usage patterns
- Cost-benefit trade-offs in feature decisions

### Engineering Skills
- Multi-agent AI system architecture (LangGraph)
- Async/parallel processing
- Database design and caching strategies
- Multiple API integrations (Exa, OpenAI, AssemblyAI, Gmail, Supabase)
- CI/CD pipeline with GitHub Actions

### AI/ML Skills
- Prompt engineering for article evaluation and summarization
- LLM-based quality scoring (4-criteria framework)
- Multi-agent orchestration
- Semantic search implementation
- Model selection and cost optimization

## 📝 License

MIT License - Feel free to use this for your own morning briefings!

## 🤝 Contact

Kyle Newman - AI Product Manager  
[GitHub](https://github.com/kylenewm) | [LinkedIn](https://www.linkedin.com/in/kylenewman2023/)

---

*Last Updated: November 16, 2025*

---

## 📖 Recent Updates (November 2025)

### Multi-Agent Architecture
- Refactored to 3 parallel specialist agents (Conversational AI, General AI, Research/Opinion)
- LangGraph-based orchestration with LangSmith tracing
- LLM-based article evaluation (4-criteria scoring)
- Finds 8 high-quality articles daily (3+3+2)

### Cross-Content Deduplication
- Checks all content from past 5 days before adding to briefing
- Prevents duplicate articles across all sources
- Supabase-backed for persistent storage

### Test Mode for Development
- Reduces API costs during local development
- Configurable via `TEST_MODE` environment variable
- Minimal code complexity

### GitHub Actions + Supabase
- Serverless deployment with scheduled runs (Mon-Fri at 9:30 AM ET)
- PostgreSQL database for persistent caching
- No local server required
