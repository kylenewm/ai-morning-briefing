# Setup Reference (Consolidated)

This document consolidates all setup guides for reference.

---

## Prerequisites

- Python 3.9+
- Git
- API keys (OpenAI, Exa, AssemblyAI)
- Gmail account (for email delivery and newsletter fetching)

---

## API Keys Required

| Service | Purpose | Sign Up | Cost |
|---------|---------|---------|------|
| OpenAI | LLM evaluation & summarization | https://platform.openai.com | ~$0.02/day |
| Exa | Semantic web search | https://exa.ai | ~$0.06/day |
| AssemblyAI | Podcast transcription | https://www.assemblyai.com | ~$0.15/episode (cached after first run) |
| Gmail | Email delivery + newsletter fetching | https://myaccount.google.com/apppasswords | Free |
| LangSmith (Optional) | Observability | https://smith.langchain.com | Free tier available |

---

## Installation

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd morning-automation
```

### 2. Python Environment
```bash
cd podcast-summarizer
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
pip install -r backend/requirements.txt
```

### 3. Environment Variables
Create `.env` file:
```bash
# Required
OPENAI_API_KEY=<your-key>
EXA_API_KEY=<your-key>
ASSEMBLYAI_API_KEY=<your-key>
SMTP_EMAIL=<your-gmail>
SMTP_PASSWORD=<gmail-app-password>
EMAIL_RECIPIENT=<where-to-send>

# Optional
LANGSMITH_API_KEY=<your-key>
PERPLEXITY_API_KEY=<your-key>
```

**Gmail App Password:**
1. Go to https://myaccount.google.com/apppasswords
2. Create app password for "Mail"
3. Use 16-character password (NOT your regular Gmail password)

---

## Supabase Setup

### 1. Create Project
1. Go to https://supabase.com
2. Create new project
3. Note your credentials:
   - Project URL
   - API Key (anon/public)
   - Database password

### 2. Configure Connection
Add to `.env`:
```bash
SUPABASE_URL=https://[project-id].supabase.co
SUPABASE_API_KEY=<anon-key>
DATABASE_URL=postgresql://postgres:[password]@db.[project-id].supabase.co:5432/postgres
```

### 3. Run Schema
1. Go to Supabase dashboard → SQL Editor
2. Run `supabase_schema.sql`
3. Verify tables created: `content_items`, `insights`, `briefings`

### 4. Test Connection
```bash
python tests/test_supabase_connection.py
```

---

## Gmail Newsletter Setup

### 1. Enable Gmail API
1. Go to https://console.cloud.google.com
2. Create project → Enable Gmail API
3. Create OAuth credentials (Desktop app)
4. Download `credentials.json`

### 2. Configure OAuth
1. Rename to `gmail_credentials.json`
2. Place in `podcast-summarizer/` directory
3. Run first authentication:
```bash
python tests/test_newsletter.py
```
4. Browser opens → Grant Gmail access
5. Token saved to `gmail_token.pickle`

### 3. Supported Newsletters
- **TLDR AI:** `dan@tldrnewsletter.com`
- **Morning Brew:** `crew@morningbrew.com`

---

## GitHub Actions Setup

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/[username]/morning-automation.git
git push -u origin main
```

### 2. Add Secrets
Go to repo → Settings → Secrets and variables → Actions

Add these secrets:
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_API_KEY`
- `OPENAI_API_KEY`
- `EXA_API_KEY`
- `ASSEMBLYAI_API_KEY`
- `SMTP_EMAIL`
- `SMTP_PASSWORD`
- `EMAIL_RECIPIENT`
- `LANGSMITH_API_KEY` (optional)
- `GMAIL_CREDENTIALS_BASE64` (for newsletters)
- `GMAIL_TOKEN_BASE64` (for newsletters)

**Encode Gmail files:**
```bash
base64 -i gmail_credentials.json
base64 -i gmail_token.pickle
```

### 3. Test Workflow
1. Go to Actions tab
2. Run workflow manually
3. Check email (~2-3 minutes)

### 4. Schedule
Runs automatically Monday-Friday at 9:30 AM ET.

Edit `.github/workflows/morning-briefing.yml` to change schedule:
```yaml
schedule:
  - cron: '30 14 * * 1-5'  # 9:30 AM EST = 14:30 UTC
```

---

## LangGraph Setup

### 1. Install LangGraph Studio (Optional)
Download from https://studio.langchain.com

### 2. Configure Project
`langgraph.json`:
```json
{
  "graphs": {
    "conversational_ai": "./podcast-summarizer/backend/services/agents/conversational_ai_agent.py:graph",
    "general_ai": "./podcast-summarizer/backend/services/agents/general_ai_agent.py:graph",
    "research_opinion": "./podcast-summarizer/backend/services/agents/research_opinion_agent.py:graph"
  },
  "env": ".env"
}
```

### 3. Run Agents
```bash
cd podcast-summarizer
python -m backend.services.agents.search_orchestrator
```

---

## Testing

### Local Testing
```bash
# Test agent search
python tests/test_agent_search.py

# Test newsletters
python tests/test_newsletter.py

# Test full pipeline
cd podcast-summarizer
python -m backend.scripts.morning_briefing
```

### Test Mode
Set `TEST_MODE=true` in `.env` to reduce API costs during development.

---

## Troubleshooting

### API Errors
- Verify keys in `.env` are correct
- Check API quotas in provider dashboards
- Review logs for specific error messages

### Email Not Sending
- Verify Gmail app password (NOT regular password)
- Check `EMAIL_RECIPIENT` is set
- Test SMTP credentials manually

### Supabase Connection Failed
- Verify `DATABASE_URL` format
- Check database password is correct
- Ensure tables exist (run schema)

### Newsletter OAuth Failed
- `gmail_credentials.json` must be in `podcast-summarizer/` directory
- Run locally first to generate `gmail_token.pickle`
- In GitHub Actions, both files must be base64 encoded secrets

### GitHub Actions Not Running
- Check Actions tab is enabled
- Verify cron syntax (use UTC time)
- Repos inactive >60 days auto-disable workflows

---

## Cost Estimates

**Daily Costs:**
- Agent Search: $0.03
- Newsletter Enrichment: $0.02
- Podcast Transcription (first time): $0.90
- Podcast Transcription (cached): $0.00

**Total:** ~$0.05/day after initial podcast cache (~$3/month)

---

## Documentation Sources

This consolidated guide combines information from:
- `SETUP.md` - Initial setup
- `GITHUB_ACTIONS_SETUP.md` - CI/CD deployment
- `SUPABASE_SETUP_INSTRUCTIONS.md` - Database config
- `docs/GMAIL_NEWSLETTER_SETUP.md` - Newsletter OAuth
- `docs/LANGGRAPH_SETUP.md` - Agent configuration
- `docs/EMAIL_SETUP.md` - SMTP setup

For current workflow details, see active documentation:
- `README.md` - Project overview
- `docs/ARCHITECTURE.md` - System design
- `docs/BRIEFING_REFERENCE.md` - Briefing logic
- `docs/PODCAST_REFERENCE.md` - Podcast processing


