# Morning Briefing Reference

**Purpose:** Expected behavior for each component in the daily briefing pipeline.

---

## AI Agent Search

**What it does:**
- Runs 3 specialist agents in parallel (Conversational AI, General AI, Research/Opinion)
- Each agent targets 3, 3, 2 articles respectively (8 total)
- Uses Exa semantic search (`type=deep`, `livecrawl=always`)
- LLM evaluates articles on relevance, actionability, quality, recency
- Deduplicates against past 5 days from all content sources
- Saves to Supabase with `run_source` tracking

**Returns:** SearchResult objects with `title`, `url`, `summary`, `source`

---

## Newsletter Processing

**Step 1: Fetch**
- Calls `get_all_newsletters(hours_ago=24, max_stories=15)`
- Fetches from Gmail (TLDR AI, Morning Brew)
- Parses HTML to extract article metadata: `title`, `url`, `brief_description`

**Step 2: Filter** 
- Calls `filter_and_rank_stories_for_ai_pm(all_stories, max_stories=8)`
- GPT-4 filters out sponsor content and ranks by AI PM relevance
- Returns top 8 stories

**Step 3: Enrich**
- Takes top 5 filtered stories
- Calls `enrich_stories_with_ai(stories[:5], max_stories=5)`
- For each story:
  - Fetches full article from URL (httpx + BeautifulSoup)
  - GPT-4 generates 3-5 paragraph summary for AI PMs
  - Extracts 3-5 key takeaways as bullet points
- Returns: `title`, `url`, `summary`, `key_points`

**Step 4: Links**
- Remaining stories (6-8) shown as links only with brief descriptions
- No AI enrichment for these

---

## Podcast Processing

**What it does:**
- Calls `process_podcasts_from_cache(episodes_per_podcast=3)`
- Queries Supabase for cached transcripts (source_type='assemblyai_transcript')
- URL pattern matching assigns episodes to podcasts
- Checks for cached insights first, generates from transcript if needed
- Returns: `title`, `link`, `pub_date`, `insights`, `podcast_name`, `source`

**Note:** Requires cache to be populated. Run `cache_all_podcast_transcripts()` once to initialize.

---

## Email Format

**Newsletters:** Top 5 get full summaries + key points, remaining 3 shown as links with brief descriptions

**Agent Articles:** Exa's summary (1000 chars) grouped by category

**Podcasts:** GPT-4 insights truncated to 500 chars per episode

**HTML Generation:** Markdown text → `format_briefing_as_html()` → styled email with stats bar

