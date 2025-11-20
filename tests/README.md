# Test Scripts Reference

This directory contains test scripts for validating individual components of the morning automation system.

## Component Test Scripts

Located in `tests/` directory:

**`test_agent_search.py`**
- Tests the 3-agent search orchestration system
- Validates LangGraph execution, Exa integration, and article filtering
- Supports TEST_MODE for reduced API costs during development
- Usage: `TEST_MODE=true python tests/test_agent_search.py`

**`test_podcast.py`**
- Tests podcast RSS parsing and transcription
- Validates AssemblyAI integration and caching
- Checks episode metadata extraction
- Usage: `python tests/test_podcast.py`

**`test_newsletter.py`**
- Tests Gmail OAuth authentication
- Validates newsletter parsing (TLDR AI, Morning Brew)
- Checks article extraction and AI filtering
- Usage: `python tests/test_newsletter.py`
- Note: First run requires browser authentication to generate `gmail_token.pickle`

**`test_supabase_connection.py`**
- Tests database connectivity
- Validates Supabase connection string
- Checks table existence
- Usage: `python tests/test_supabase_connection.py`

**`test_imports.py`**
- Validates all required dependencies are installed
- Useful for debugging environment setup issues
- Checks both external libraries and internal modules
- Usage: `python tests/test_imports.py`

## Test Strategies

### Local Development
1. Use `TEST_MODE=true` for agent search testing (97% cost savings)
2. Test components individually before full pipeline
3. Check logs for detailed debugging information
4. Use component tests to iterate quickly

### Integration Testing
1. Test full pipeline locally: `cd podcast-summarizer && python -m backend.scripts.morning_briefing`
2. Use workflow inputs in GitHub Actions for selective phase testing
3. Verify in production environment before enabling schedule

## Running Tests

### Quick Component Test
```bash
# Fastest way to test search agents
TEST_MODE=true python tests/test_agent_search.py
```

### Full Local Pipeline
```bash
# Run all phases (agent search, newsletters, podcasts)
cd podcast-summarizer
python -m backend.scripts.morning_briefing
```

### Selective Testing
```bash
# Skip specific phases
RUN_PODCASTS=false python -m backend.scripts.morning_briefing
```

## Test Mode Configuration

Set `TEST_MODE=true` to reduce costs during development:
- Articles: 3 total (1 per agent) vs 8 in production
- Exa search: neural vs deep
- Livecrawl: never vs always
- Iterations: 1 vs 3
- Cost: ~$0.05 vs ~$1.50 per run

## Troubleshooting Tests

### Import Errors
Run `python tests/test_imports.py` to identify missing dependencies.

### API Errors
- Verify API keys in `.env` (no quotes, no spaces)
- Check API quotas in provider dashboards
- Review logs for specific error messages

### Database Errors
Run `python tests/test_supabase_connection.py` to verify connectivity.

### Newsletter OAuth Errors
- Must run `python tests/test_newsletter.py` locally first to generate token
- Requires `gmail_credentials.json` in `podcast-summarizer/` directory
- Browser will open for OAuth consent on first run

## Archived Tests

**`tests/archive/test_openai_key.py`**
- Temporary test file for debugging OpenAI API key issues
- Archived after successful key validation

## Documentation

For detailed testing strategies, see:
- `docs/archive/TESTING_CONSOLIDATED.md` - Complete testing reference
- `README.md` - Quick start and troubleshooting
- `FEATURES.md` - Feature-specific testing notes

