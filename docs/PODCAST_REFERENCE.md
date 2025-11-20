# Podcast Processing System Reference

Complete technical reference for podcast transcription, caching, and summarization.

## System Overview

The podcast system processes 6 podcasts with two priority tiers, using AssemblyAI for transcription and GPT-4 for summarization. All content is cached in Supabase to minimize API costs.

**Processing Flow:** RSS Feed → MP3 Download → AssemblyAI Transcription → Supabase Cache → GPT-4 Summarization → Email Display

## Podcast Configuration

**Location:** `backend/ingestion/sources.py`

### Primary Podcasts (Detailed Summaries)
- **Lenny's Podcast** - Product management insights
- **MLOps.community** - ML operations and production systems  
- **TWiML AI** - Machine learning and AI news

### Secondary Podcasts (Links Only)
- **The AI Daily Brief** - Daily AI news (special gap-filling logic)
- **Data Skeptic** - Data science and statistics
- **DataFramed by DataCamp** - Data science trends

### Configuration Fields
```python
{
    "name": str,                    # Display name
    "rss_url": str,                 # RSS feed URL
    "method": "assemblyai_transcript",
    "category": str,                # Classification category
    "description": str,             # Brief description
    "priority": "primary|secondary", # Display tier
    "is_gap_filler": bool           # Special flag for AI Daily Brief
}
```

## Core Functions

### 1. Transcript Caching (`cache_all_podcast_transcripts`)

**File:** `backend/services/assemblyai_processor.py:305`

**Purpose:** Populate Supabase cache with new episode transcripts.

**Flow:**
1. Fetch RSS feeds for all 6 podcasts
2. Extract latest N episodes per podcast
3. For each episode:
   - Check Supabase for existing transcript (by episode URL)
   - If not cached: Download MP3 → Call AssemblyAI → Save to Supabase
   - If cached: Skip (log as "episodes_skipped")
4. Return stats: episodes_cached, episodes_skipped, episodes_failed, total_cost_estimate

**Parameters:**
- `episodes_per_podcast` (int): Episodes to cache per podcast (default: 3)
- `force_refresh` (bool): Re-transcribe even if cached (default: False)

**Returns:**
```python
{
    'success': bool,
    'stats': {
        'podcasts_processed': int,
        'episodes_cached': int,        # NEW transcriptions (costs apply)
        'episodes_skipped': int,        # Already in cache (no cost)
        'episodes_failed': int,
        'total_cost_estimate': float,
        'details': List[Dict]
    }
}
```

**Database Operations:**
- Queries: `ContentItem.source_type = 'assemblyai_transcript'`, `ContentItem.item_url = episode_url`
- Inserts: New `ContentItem` records with transcript text

### 2. Cached Podcast Processing (`process_podcasts_from_cache`)

**File:** `backend/api/routes.py:1325`

**Purpose:** Generate insights from cached transcripts for daily briefing.

**Flow:**
1. Query Supabase for all cached transcripts (source_type='assemblyai_transcript')
2. Sort by published_date (most recent first)
3. For each podcast:
   - URL pattern matching to assign episodes (e.g., 'lennysnewsletter.com' → Lenny's Podcast)
   - Take up to N episodes per podcast
   - For each episode:
     - Check for cached insights (Insights table via content_item_id)
     - If cached insights exist: Use them
     - If no cached insights: Generate from transcript using GPT-4 → Cache result
4. Return episodes grouped by podcast

**Parameters:**
- `episodes_per_podcast` (int): Episodes per podcast to return (default: 1)
- `force_refresh` (bool): Regenerate insights even if cached (default: False)

**Returns:**
```python
{
    'success': bool,
    'episodes_by_podcast': {
        'Lenny\'s Podcast': [
            {
                'title': str,
                'pub_date': str,
                'link': str,
                'insights': str,              # GPT-4 generated summary
                'practical_tips': List[str],  # Actionable takeaways
                'source': 'assemblyai_cache',
                'transcript_length': int
            },
            ...
        ],
        ...
    },
    'total_episodes': int,
    'podcasts_processed': int
}
```

**URL Pattern Matching:**
- Lenny's: `'lennysnewsletter.com' in url`
- MLOps: `'spotify.com/pod/show/mlops' in url`
- TWiML: `'twimlai.com' in url`
- AI Daily Brief: `'anchor.fm' in url and 'f7cac464' in url`
- Data Skeptic: `'dataskeptic' in url or 'libsyn.com' in url`
- DataFramed: `'datacamp' in url.lower()`

### 3. AI Daily Brief Gap Analysis (`get_ai_daily_brief_gap_analysis`)

**File:** `backend/api/routes.py:170`

**Purpose:** Extract unique insights from AI Daily Brief not covered by newsletters.

**Flow:**
1. Fetch latest AI Daily Brief episode from RSS
2. Transcribe using AssemblyAI (if not cached)
3. Compare transcript against TLDR AI stories and Perplexity news
4. Use GPT-4 to extract ONLY unique insights not covered elsewhere
5. Return filtered summary for "Additional Analysis" section

**Parameters:**
- `tldr_stories` (List): Today's TLDR AI articles
- `perplexity_stories` (List): Today's Perplexity articles  
- `yesterday_tldr_stories` (List): Optional yesterday's TLDR
- `yesterday_perplexity_stories` (List): Optional yesterday's Perplexity

**Returns:** `Optional[str]` - Unique insights text or None if no unique content

## Transcription System

### AssemblyAI Integration

**File:** `backend/ingestion/assemblyai_transcriber.py`

**Class:** `AssemblyAITranscriber`

#### Key Methods:

**`transcribe_episode(episode_data, test_mode=False)`**
- Accepts MP3 URL directly (no download required)
- Uses AssemblyAI Universal model
- Cache check before transcription (by episode URL)
- Test mode: Truncates to ~1000 words
- Returns full transcript text or None

**`get_transcript_summary(transcript, episode_title, episode_url)`**
- Generates AI summary from transcript using GPT-4.1-mini
- Max tokens: 2000 (~8000 characters output)
- Temperature: 0.3 (deterministic)
- Caches summary with episode URL
- Returns summary text

**`_get_cached_transcript(episode_url)`**
- Queries Supabase ContentItem table
- Filter: `source_type='assemblyai_transcript'` AND `item_url=episode_url`
- Returns cached transcript or None

**`_cache_transcript(episode_url, transcript, episode_data)`**
- Creates ContentItem record with transcript
- Fields: source_type, item_url, title, transcript, transcript_length, published_date
- Idempotent: Updates if episode_url already exists

**`_cache_summary(episode_url, summary, episode_title, practical_tips, enriched_content)`**
- Creates Insight record linked to ContentItem
- Fields: content_item_id, insight_text, practical_tips, model_name, token_count
- Multiple insights can exist per ContentItem (historical tracking)

### GPT-4 Summarization Prompt

**Location:** `backend/ingestion/assemblyai_transcriber.py:204`

**Instruction:**
```
Clean this podcast transcript for an AI Product Manager briefing.

REMOVE:
- Greetings, outros, sponsor reads
- "Today we're going to talk about..."
- "Thanks for listening..."
- Conversational filler ("you know", "like", "um")

KEEP & ORGANIZE:
- Core concepts and how they work
- Specific examples with context
- Tactical advice and workflows
- Technical details and implementation notes

Format with subheadings. Write in active voice. Present the information directly—don't narrate that "they discussed" something.
```

**Model:** gpt-4.1-mini  
**Max Tokens:** 2000  
**Temperature:** 0.3

## Database Schema

### ContentItem Table
```sql
CREATE TABLE content_items (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50),           -- 'assemblyai_transcript'
    source_name VARCHAR(100),          -- 'AssemblyAI Transcript'
    item_url TEXT UNIQUE,              -- Episode URL (unique cache key)
    title TEXT,
    transcript TEXT,                   -- Full transcript
    transcript_length INTEGER,
    published_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Insights Table
```sql
CREATE TABLE insights (
    id SERIAL PRIMARY KEY,
    content_item_id INTEGER REFERENCES content_items(id),
    insight_text TEXT,                -- GPT-4 generated summary
    practical_tips TEXT,              -- JSON array of tips
    enriched_content TEXT,            -- Additional processed content
    model_name VARCHAR(50),           -- 'gpt-4o-mini'
    token_count INTEGER,
    was_test_mode BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Daily Briefing Integration

**File:** `backend/scripts/morning_briefing.py`

### Two-Step Process

**Step 1: Cache New Episodes**
```python
cache_result = await cache_all_podcast_transcripts(
    episodes_per_podcast=3,
    force_refresh=False  # Only transcribe NEW episodes
)
```
- Checks for new episodes
- Only transcribes what's not in Supabase
- Logs: new episodes transcribed, already cached, cost estimate

**Step 2: Generate Insights**
```python
podcast_results = await process_podcasts_from_cache(
    episodes_per_podcast=3,
    force_refresh=False
)
```
- Reads from Supabase cache
- Generates GPT-4 summaries if not cached
- Returns formatted episode data

### Email Display Logic

**Current Implementation:**
- Shows up to 2 episodes per podcast
- All episodes get full summaries (no priority filtering implemented yet)
- No truncation on insights (full GPT output shown)

**Intended Implementation (Not Yet Active):**
- Primary podcasts (3): First episode gets full detailed summary (~2000 tokens)
- Primary podcasts (3): Subsequent episodes shown as links only
- Secondary podcasts (3): All episodes shown as links only
- AI Daily Brief: Special gap analysis section (shows unique insights)

### Episode Display Format

**Full Summary (Primary, First Episode):**
```markdown
### Podcast Name

**Episode Title**

[Full GPT-4 summary text - no truncation]

[Listen →](episode_url)

---
```

**Link Only (All Others):**
```markdown
### Podcast Name

**Episode Title** - [Listen →](episode_url)

---
```

## Caching Strategy

### Cache Keys
- **Transcript Cache:** Episode URL (`ContentItem.item_url`)
- **Summary Cache:** content_item_id (`Insight.content_item_id`)

### URL Normalization
**Function:** `_normalize_url(url)`
- Removes query parameters
- Removes trailing slashes
- Normalizes protocol (https)
- Ensures consistent cache lookups

### Cache Hit Rate
- First run: 0% (transcribe all episodes, ~$0.15-0.30 per episode)
- Daily runs: ~70-90% (most episodes already cached)
- Cost per run after initial population: $0.15-0.90 (only new episodes)

## Cost Analysis

### Transcription Costs (AssemblyAI)
- Rate: $0.15 per audio hour
- Average podcast: 30-60 minutes
- Cost per episode: $0.075-0.15
- Initial cache population (18 episodes): $1.35-2.70
- Daily incremental (1-3 new episodes): $0.075-0.45

### Summarization Costs (GPT-4.1-mini)
- Input: ~30,000-60,000 tokens (transcript)
- Output: ~2,000 tokens (summary)
- Cost per summary: ~$0.03-0.06
- Daily cost (3-6 new summaries): $0.09-0.36

### Total Daily Cost
- Transcription: $0.075-0.45
- Summarization: $0.09-0.36
- **Total: $0.17-0.81 per day**

## Error Handling

### Common Failure Modes

**1. MP3 URL Not Found**
- Cause: RSS feed doesn't include enclosure URL
- Handling: Log warning, skip episode
- Impact: Episode not transcribed

**2. AssemblyAI Transcription Failed**
- Cause: API error, invalid audio format, timeout
- Handling: Log error, return None, increment failed_count
- Impact: Episode skipped, no cost incurred

**3. Database Connection Error**
- Cause: Invalid DATABASE_URL, network issue
- Handling: Fall through to transcription (no cache benefit)
- Impact: Re-transcribe even if cached (cost inefficiency)

**4. GPT-4 Summarization Failed**
- Cause: API error, rate limit, token limit exceeded
- Handling: Return cached transcript without summary
- Impact: Email shows raw transcript or "Summary unavailable"

### Retry Logic
- AssemblyAI: Built-in retries (transcription service)
- Database: Single attempt per operation (fail fast)
- GPT-4: Single attempt (expensive to retry)

## Testing

### Local Testing
```bash
# Test with 1 episode per podcast, minimal cost
python -c "
import asyncio
from podcast-summarizer.backend.services.assemblyai_processor import cache_all_podcast_transcripts

result = asyncio.run(cache_all_podcast_transcripts(episodes_per_podcast=1, force_refresh=False))
print(f'Cached: {result[\"stats\"][\"episodes_cached\"]}')
print(f'Skipped: {result[\"stats\"][\"episodes_skipped\"]}')
print(f'Cost: ${result[\"stats\"][\"total_cost_estimate\"]:.2f}')
"
```

### Test Mode
**Not Implemented for Podcasts** - No test mode configuration exists.
Recommendation: Always use `episodes_per_podcast=1` for testing to minimize costs.

## Production Deployment

### GitHub Actions Integration

**Workflow:** `.github/workflows/morning-briefing.yml`

**Environment Variables:**
- `ASSEMBLYAI_API_KEY` - Required for transcription
- `OPENAI_API_KEY` - Required for summarization
- `DATABASE_URL` - Required for Supabase caching

**Execution Flow:**
1. Scheduled trigger (Mon-Fri 9:30 AM ET)
2. Install dependencies
3. Run `morning_briefing.py` as Python module
4. **Phase 3: Podcast Processing**
   - Step 1: Cache new episodes (1-3 minutes)
   - Step 2: Generate insights (30-60 seconds)
5. Include podcasts in email

**Monitoring:**
- Check GitHub Actions logs for transcription errors
- Monitor Supabase for cache growth
- Track `episodes_cached` vs `episodes_skipped` ratio

## Known Issues and Limitations

### 1. Priority Filtering Not Implemented
**Issue:** All 6 podcasts currently receive detailed summaries, ignoring the priority field.  
**Impact:** Longer emails, more GPT-4 costs than intended.  
**Fix:** Implement priority check in `morning_briefing.py` to show only primary podcasts with full summaries.

### 2. AI Daily Brief Gap Analysis Missing
**Issue:** `get_ai_daily_brief_gap_analysis` function exists but not called in `morning_briefing.py`.  
**Impact:** AI Daily Brief processed as regular podcast, not as gap-filler.  
**Fix:** Add gap analysis call after newsletter processing in `morning_briefing.py`.

### 3. No Episode Ordering by Priority
**Issue:** Episodes displayed in order returned from cache query, not by podcast priority.  
**Impact:** Secondary podcasts may appear before primary podcasts.  
**Fix:** Sort episodes by podcast priority before display.

### 4. URL Pattern Matching Fragility
**Issue:** Hard-coded URL patterns in `process_podcasts_from_cache` can break if RSS URLs change.  
**Impact:** Episodes not assigned to correct podcast, missing from briefing.  
**Fix:** Store podcast_id in ContentItem table during transcription instead of inferring from URL.

## Future Enhancements

### Short-term
- Implement priority-based filtering (primary vs secondary)
- Add AI Daily Brief gap analysis to daily briefing
- Improve URL pattern matching robustness

### Long-term
- Speaker diarization (track multiple speakers)
- Chapter detection and summaries
- Semantic search across all podcast transcripts
- Custom podcast generation via NotebookLM
