# Testing Reference (Consolidated)

This document consolidates all testing guides for reference.

---

## Component Testing (Recommended)

Test individual components locally for fast iteration:

```bash
# Test agent search (with test mode)
TEST_MODE=true python tests/test_agent_search.py

# Test podcasts
python tests/test_podcast.py

# Test newsletters
python tests/test_newsletter.py

# Test Supabase connection
python tests/test_supabase_connection.py
```

**Benefits:**
- Fast iteration (~15 seconds vs 2-3 minutes)
- Cheap ($0.05 vs $1.50 per run)
- Easier debugging
- More focused testing

---

## Test Mode

### Enable Test Mode
```bash
TEST_MODE=true python tests/test_agent_search.py
```

### What Changes in Test Mode

| Feature | Production | Test Mode |
|---------|-----------|-----------|
| Duration | 120s | 15s |
| Exa Search Type | Deep | Neural |
| Livecrawl | Always | Never |
| Articles | 8 (3+3+2) | 3 (1+1+1) |
| Iterations | 3 | 1 |
| Search Limit | 5 | 2 |
| Cost | ~$1.50 | ~$0.05 |

### How It Works

**Configuration file:** `podcast-summarizer/backend/test_config.py`

```python
IS_TEST_MODE = os.getenv("TEST_MODE", "").lower() == "true"

if IS_TEST_MODE:
    AGENT_MAX_ITERATIONS = 1
    AGENT_TARGET_ARTICLES = {"conversational_ai": 1, "general_ai": 1, "research_opinion": 1}
    EXA_SEARCH_TYPE = "neural"
    EXA_SEARCH_LIMIT = 2
    EXA_LIVECRAWL = "never"
else:
    AGENT_MAX_ITERATIONS = None
    AGENT_TARGET_ARTICLES = None
    EXA_SEARCH_TYPE = None
    EXA_SEARCH_LIMIT = None
    EXA_LIVECRAWL = None
```

**Components check config:**
```python
from test_config import AGENT_TARGET_ARTICLES

@property
def TARGET_ARTICLES(self) -> int:
    if AGENT_TARGET_ARTICLES:
        return AGENT_TARGET_ARTICLES["conversational_ai"]
    return 3  # Production default
```

### Verify Test Mode Active
Look for this output:
```
🧪 TEST MODE: Costs reduced, using cached data where possible
🤖 TESTING SEARCH ORCHESTRATOR - 🧪 TEST MODE (fast & cheap)
```

And in logs:
```
type=neural, livecrawl=never
target: 1 articles
```

---

## Full Pipeline Testing

### Option 1: GitHub Actions (Recommended)

Test the complete pipeline in production environment:

1. Push changes to GitHub
2. Go to Actions tab
3. Click "Morning Briefing"
4. Click "Run workflow"
5. Watch end-to-end execution

**Benefits:**
- Tests in real production environment
- No import issues
- Validates actual deployment
- Can test with selective phases (run_agent_search, run_newsletters, run_podcasts)

### Option 2: Local Full Pipeline

Run as Python module (required for relative imports):

```bash
cd podcast-summarizer
python -m backend.scripts.morning_briefing
```

**Note:** Environment variables control phases:
```bash
# Skip podcasts (cache not populated)
RUN_PODCASTS=false python -m backend.scripts.morning_briefing

# Test mode for cost savings
TEST_MODE=true python -m backend.scripts.morning_briefing

# Skip all phases except agent search
RUN_NEWSLETTERS=false RUN_PODCASTS=false python -m backend.scripts.morning_briefing
```

---

## Testing Checklist

### Before Pushing to Production
- [ ] Component tests pass locally
- [ ] Test mode works (reduced costs)
- [ ] Deduplication works (check logs for filtered duplicates)
- [ ] Articles saved to Supabase
- [ ] No linter errors
- [ ] Environment variables set correctly

### After Pushing to GitHub
- [ ] Manual workflow trigger successful
- [ ] Email received
- [ ] Check logs for errors
- [ ] Verify correct number of articles/newsletters/podcasts
- [ ] Confirm costs are as expected

---

## Deduplication Testing

### First Run
```
📊 Loaded 0 URLs from past 5 days for deduplication
💾 Saved 3 articles to Supabase (source: conversational_ai|automated)
```

### Second Run (Same Day)
```
📊 Loaded 3 URLs from past 5 days for deduplication
⚠️ Filtered 2 duplicate(s) from past 5 days:
   • 'Article Title...' (previously in agent_search/conversational_ai|automated on 2025-11-19)
```

### Verify Deduplication
1. Run agent search twice
2. Check logs for "Filtered X duplicate(s)"
3. Query Supabase to see saved articles
4. Verify `run_source` field is set correctly (`manual` or `automated`)

---

## Cost Analysis

### Daily Production Run
- Agent Search: $0.03
- Newsletter Enrichment: $0.02
- Podcast from Cache: $0.01
- **Total:** ~$0.06/day

### Development Testing
**Without test mode:** $1.50 × 10 tests = $15/day  
**With test mode:** $0.05 × 10 tests = $0.50/day  
**Savings:** $14.50/day = ~$290/month

---

## Common Issues

### Test Mode Not Activating
Must be exactly `TEST_MODE=true` (case-sensitive):
```bash
# ✅ Correct
TEST_MODE=true python tests/test_agent_search.py

# ❌ Wrong
TEST_MODE=True python tests/test_agent_search.py
test_mode=true python tests/test_agent_search.py
```

### Import Errors
Run as module, not as script:
```bash
# ✅ Correct
cd podcast-summarizer
python -m backend.scripts.morning_briefing

# ❌ Wrong
python podcast-summarizer/backend/scripts/morning_briefing.py
```

### Empty Results
- Check API keys are set
- Verify Supabase connection
- Check logs for specific errors
- Ensure cache is populated (for podcasts)

### Deduplication Not Working
- Verify `DATABASE_URL` is set
- Check Supabase tables exist
- Ensure `content_items` table has records
- Check logs for "Loaded X URLs" message

---

## Test Scripts Reference

| Script | Purpose | Duration | Cost |
|--------|---------|----------|------|
| `test_agent_search.py` | Test 3-agent search system | 15s (test) / 120s (prod) | $0.05 / $1.50 |
| `test_podcast.py` | Test podcast transcription | Varies | $0.15/episode |
| `test_newsletter.py` | Test Gmail OAuth + parsing | 5-10s | Free |
| `test_supabase_connection.py` | Verify database connection | 1s | Free |
| `backend.scripts.morning_briefing` | Full pipeline | 2-3 min | $0.06 |

---

## Troubleshooting Tips

### Check Logs
```bash
# View recent logs
tail -f logs/morning_briefing.log

# Search for errors
grep "ERROR" logs/*.log
```

### Verify Environment
```bash
# Check Python version (need 3.9+)
python3 --version

# Check virtual environment
which python  # Should show venv path

# List environment variables
env | grep -E "(OPENAI|EXA|DATABASE)"
```

### Debug Deduplication
```bash
# Query Supabase directly
python -c "
from podcast_summarizer.backend.database.cache_service import CacheService
recent = CacheService.get_recent_content_urls(days=5)
print(f'Found {len(recent)} URLs in past 5 days')
for url, meta in list(recent.items())[:5]:
    print(f'  {meta[\"source_name\"]}: {url[:50]}...')
"
```

---

## Best Practices

### Local Development
1. Use test mode for fast iteration
2. Test components individually
3. Only test full pipeline when integrating
4. Check logs after each test

### CI/CD Testing
1. Test manually before enabling schedule
2. Use workflow inputs to test specific phases
3. Monitor costs in API dashboards
4. Review logs in GitHub Actions

### Debugging Strategy
1. Start with component tests
2. Check logs for specific errors
3. Verify environment variables
4. Test in production environment (GitHub Actions)
5. Compare logs with working runs

---

## Documentation Sources

This consolidated guide combines information from:
- `LOCAL_TESTING.md` - Local testing strategies
- `LOCAL_TESTING_COMPLETE.md` - Full pipeline testing
- `TEST_MODE_SUMMARY.md` - Test mode implementation

For current testing procedures, see:
- `README.md` - Quick start
- `docs/BRIEFING_REFERENCE.md` - Expected behavior
- `docs/PODCAST_REFERENCE.md` - Podcast testing


