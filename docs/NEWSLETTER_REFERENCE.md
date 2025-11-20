# Newsletter Processing System Reference

Complete technical reference for newsletter fetching, filtering, and AI enrichment.

## System Overview

The newsletter system fetches emails via Gmail API, extracts article URLs, applies AI filtering for AI PM relevance, and enriches top stories with full article content and GPT-4 summaries.

**Processing Flow:** Gmail API → HTML Parsing → URL Extraction → AI Filtering → Article Fetching → GPT-4 Summarization → Email Display

## Newsletter Configuration

**Location:** `backend/ingestion/gmail_newsletters.py:37`

### Supported Newsletters

**TLDR AI (Primary)**
```python
{
    "name": "TLDR AI",
    "from_email": "dan@tldrnewsletter.com",
    "subject_contains": None,
    "priority": 1,
    "parser": "parse_tldr_ai"
}
```

**Morning Brew (Secondary - Parser Not Implemented)**
```python
{
    "name": "Morning Brew",
    "from_email": "crew@morningbrew.com",
    "subject_contains": "Morning Brew",
    "priority": 2,
    "parser": "parse_morning_brew"
}
```

### Configuration Fields
- `name`: Display name for the newsletter
- `from_email`: Sender email address for Gmail filtering
- `subject_contains`: Optional subject line keyword filter
- `priority`: Processing order (lower = higher priority)
- `parser`: Function name for HTML parsing logic

## Core Functions

### 1. Gmail Authentication (`get_gmail_service`)

**File:** `backend/ingestion/gmail_newsletters.py:56`

**Purpose:** Authenticate with Gmail API using OAuth 2.0.

**Flow:**
1. Check for existing token (`gmail_token.pickle`)
2. If token exists and valid: Use it
3. If token expired: Refresh using credentials
4. If no token: Launch OAuth flow (browser-based)
5. Save token for future use

**Required Files:**
- `gmail_credentials.json` - OAuth client credentials from Google Cloud Console
- `gmail_token.pickle` - Cached authentication token (created after first auth)

**Scopes:** `https://www.googleapis.com/auth/gmail.readonly`

**Returns:** Gmail API service object or None if authentication fails

### 2. Email Search (`search_emails`)

**File:** `backend/ingestion/gmail_newsletters.py:111`

**Purpose:** Search Gmail for newsletters within specified time window.

**Parameters:**
- `service`: Gmail API service object
- `from_email` (str): Sender email to filter by
- `subject_contains` (Optional[str]): Subject keyword filter
- `hours_ago` (int): Time window in hours (default: 24)

**Query Construction:**
```
from:{from_email} after:{timestamp} subject:{subject_contains}
```

**Returns:** List of message metadata (id, threadId) or empty list

### 3. Email Content Retrieval (`get_email_content`)

**File:** `backend/ingestion/gmail_newsletters.py:148`

**Purpose:** Fetch and decode email HTML content.

**Flow:**
1. Get message by ID from Gmail API
2. Extract payload from message
3. Decode body (handles base64 encoding)
4. Parse multipart messages (prefer text/html)
5. Extract metadata (date, subject, from)

**Returns:**
```python
{
    'body': str,      # HTML content
    'date': str,      # ISO timestamp
    'subject': str,   # Email subject
    'from': str       # Sender
}
```

### 4. TLDR AI Parser (`parse_tldr_ai`)

**File:** `backend/ingestion/gmail_newsletters.py:235`

**Purpose:** Extract article URLs and metadata from TLDR AI HTML.

**Flow:**
1. Parse HTML with BeautifulSoup
2. Find all `<a>` tags with href attributes
3. For each link:
   - Decode tracking URLs (`tracking.tldrnewsletter.com`)
   - Extract actual article URL
   - Clean URL (remove UTM parameters)
   - Extract link text as title
   - Remove "(X minute read)" suffixes
   - Find parent context for brief description
4. Filter out non-article links (unsubscribe, ads, etc.)
5. Deduplicate by URL

**Filtering:**
- Minimum title length: 20 characters
- Must start with `http`
- Excludes: `tldr.tech`, `unsubscribe`, `sparkloop`, `advertise`, `utm_campaign`, `preferences`

**Returns:**
```python
[
    {
        'title': str,
        'url': str,
        'brief_description': str,  # TLDR's own description
        'source': 'TLDR AI',
        'needs_ai_summary': True
    },
    ...
]
```

### 5. AI Filtering (`filter_and_rank_stories_for_ai_pm`)

**File:** `backend/ingestion/gmail_newsletters.py:312`

**Purpose:** Use GPT-4 to filter out sponsor content and rank by AI PM relevance.

**Parameters:**
- `stories` (List): Stories with title, url, brief_description
- `max_stories` (int): Maximum stories to return (default: 8)

**Flow:**
1. Prepare stories as numbered list for AI
2. Send to GPT-4.1-mini with filtering criteria
3. Parse JSON response with story selections
4. Return filtered and ranked stories

**GPT-4 Prompt:**
```
You are filtering newsletter stories for an AI Product Manager.

KEEP stories about:
- New AI model releases (GPT, Claude, Gemini, Llama, etc.)
- AI tool launches and major updates
- AI API announcements
- Production AI systems and case studies
- AI product strategy and roadmaps
- Technical deep-dives on AI implementation

DISCARD:
- Sponsored content / ads
- Generic tech news unrelated to AI
- HR/recruiting posts
- Social media announcements with no substance
- "Sign up for X" promotional content
- Vague "AI trends" without specifics

Return JSON array of story numbers (1-indexed) ranked by relevance.
Maximum {max_stories} stories.
```

**Model:** gpt-4.1-mini  
**Temperature:** 0.3  
**Response Format:** JSON array of story indices

**Returns:** Filtered list of stories (up to max_stories)

### 6. Article Enrichment (`enrich_stories_with_ai`)

**File:** `backend/ingestion/gmail_newsletters.py:558`

**Purpose:** Fetch full article content and generate AI PM-focused summaries.

**Parameters:**
- `stories` (List): Filtered stories with URLs
- `max_stories` (int): Maximum to process (default: 10)

**Flow (Per Story):**
1. Fetch article HTML via httpx GET request
2. Parse HTML with BeautifulSoup
3. Extract main content:
   - Remove `<script>`, `<style>`, `<nav>`, `<footer>`, `<aside>`
   - Find main content block (`<article>`, `<main>`, or `<div class="content">`)
   - Extract text content
4. Clean extracted text:
   - Remove extra whitespace
   - Remove duplicate lines
   - Truncate to reasonable length
5. Generate GPT-4 summary (3-5 paragraphs, AI PM focus)
6. Extract 3-5 key takeaways
7. Return enriched story

**GPT-4 Summarization Prompt:**
```
Summarize this article for an AI Product Manager in 3-5 paragraphs.

Focus on:
- What was announced/released
- Technical details and capabilities
- Product implications and use cases
- How this affects AI product strategy

Write in active voice. Be specific and technical.

Then extract 3-5 key takeaways as bullet points.
```

**Model:** gpt-4.1-mini  
**Max Tokens:** 1500  
**Temperature:** 0.4

**Returns:**
```python
[
    {
        'title': str,
        'url': str,
        'summary': str,           # 3-5 paragraph AI PM summary
        'key_points': List[str],  # 3-5 bullet points
        'source': 'TLDR AI',
        'enriched': True
    },
    ...
]
```

### 7. Newsletter Fetching (`get_newsletter_stories`)

**File:** `backend/ingestion/gmail_newsletters.py:433`

**Purpose:** Fetch stories from a specific newsletter.

**Parameters:**
- `newsletter_key` (str): Key from NEWSLETTER_CONFIGS
- `hours_ago` (int): Time window (default: 24)
- `max_stories` (int): Max stories after filtering (default: 15)

**Flow:**
1. Validate newsletter_key exists in config
2. Authenticate Gmail API
3. Search for emails from newsletter
4. Get most recent email content
5. Parse email with appropriate parser
6. Apply AI filtering (TLDR AI only)
7. Return stories with metadata

**Returns:**
```python
{
    'newsletter': str,
    'newsletter_key': str,
    'email_date': str,
    'stories': List[Dict],
    'total_stories': int,
    'raw_stories': int,  # Before filtering
    'error': Optional[str]
}
```

### 8. Fetch All Newsletters (`get_all_newsletters`)

**File:** `backend/ingestion/gmail_newsletters.py:520`

**Purpose:** Fetch from all configured newsletters in parallel.

**Parameters:**
- `hours_ago` (int): Time window (default: 24)
- `max_stories` (int): Max per newsletter (default: 15)

**Flow:**
1. Get all newsletter configurations
2. Create async tasks for each newsletter
3. Execute all fetches in parallel (asyncio.gather)
4. Aggregate results
5. Return combined data

**Returns:**
```python
{
    'newsletters': {
        'tldr_ai': {
            'newsletter': 'TLDR AI',
            'stories': List[Dict],
            'email_date': str,
            ...
        },
        ...
    },
    'total_stories': int,
    'errors': List[str]
}
```

## Daily Briefing Integration

**File:** `backend/scripts/morning_briefing.py`

### Processing Flow

**Step 1: Fetch Newsletters**
```python
newsletters_result = await get_all_newsletters(hours_ago=24, max_stories=15)
```
- Fetches from Gmail (past 24 hours)
- Parses TLDR AI format
- Returns 15-20 raw stories

**Step 2: Filter Stories**
```python
filtered_stories = await filter_and_rank_stories_for_ai_pm(
    all_newsletter_stories, 
    max_stories=8
)
```
- GPT-4 filters out sponsored content
- Ranks by AI PM relevance
- Returns top 8 stories

**Step 3: Enrich Top 5**
```python
enriched_newsletter_stories = await enrich_stories_with_ai(
    filtered_stories[:5],
    max_stories=5
)
```
- Fetches full article content
- Generates 3-5 paragraph summaries
- Extracts 3-5 key takeaways
- Returns enriched stories

**Step 4: Keep Remaining as Links**
```python
link_newsletter_stories = filtered_stories[5:]
```
- Stories 6-8 shown as links only
- Include brief description from TLDR
- No AI enrichment

### Email Display Format

**Enriched Stories (Top 5):**
```markdown
## Newsletter Stories

### Article Title

[3-5 paragraph GPT-4 summary focused on AI PM concerns]

**Key Points:**
- Key takeaway 1
- Key takeaway 2
- Key takeaway 3

[Read more](article_url)

---
```

**Link Stories (Remaining):**
```markdown
### Additional Newsletter Stories

• [Article Title](article_url)
  *Brief description from TLDR*

• [Article Title](article_url)
  *Brief description from TLDR*

---
```

## Error Handling

### Common Failure Modes

**1. Gmail Authentication Failed**
- Cause: Missing credentials, expired token, invalid OAuth scope
- Handling: Return empty results with error message
- Impact: No newsletter stories in briefing
- Fix: Re-authenticate by running `test_newsletter.py` locally

**2. No Emails Found**
- Cause: Newsletter not sent yet, wrong time window, email not in inbox
- Handling: Log warning, return empty stories
- Impact: No newsletter section in briefing
- Fix: Increase `hours_ago` parameter or check Gmail directly

**3. HTML Parsing Failed**
- Cause: Newsletter changed format, unexpected HTML structure
- Handling: Return empty stories, log error
- Impact: Newsletter section missing
- Fix: Update parser function to handle new format

**4. Article Fetch Failed (Enrichment)**
- Cause: Paywall, 403 error, slow response, site down
- Handling: Skip article, continue with others
- Impact: Some enriched stories missing, fall back to links
- Fix: Retry with different user agent or skip problematic domains

**5. GPT-4 Filtering Failed**
- Cause: API error, rate limit, malformed JSON response
- Handling: Return all raw stories (no filtering)
- Impact: Sponsored content may appear in briefing
- Fix: Retry or fall back to raw stories

### Retry Logic
- Gmail API: No retries (fail fast for authentication issues)
- Article fetching: Single attempt per URL (parallel processing)
- GPT-4: Single attempt per call (expensive to retry)

## Cost Analysis

### API Costs

**Gmail API:**
- Free tier: 1 billion quota units per day
- Typical usage: ~10-50 quota units per briefing
- Cost: $0

**GPT-4.1-mini Costs:**

**Filtering (Step 2):**
- Input: ~1,000 tokens (15-20 story titles + descriptions)
- Output: ~50 tokens (JSON array)
- Cost per run: ~$0.001-0.002

**Enrichment (Step 3, per story):**
- Input: ~3,000-5,000 tokens (full article content)
- Output: ~500-800 tokens (summary + key points)
- Cost per story: ~$0.01-0.02
- Total for 5 stories: ~$0.05-0.10

**Total Daily Cost:**
- Filtering: $0.001-0.002
- Enrichment: $0.05-0.10
- **Total: $0.051-0.102 per day**

## Gmail OAuth Setup

### Initial Configuration

**1. Google Cloud Console**
- Go to https://console.cloud.google.com/apis/credentials
- Create new OAuth 2.0 Client ID
- Application type: Desktop app
- Download credentials as `gmail_credentials.json`
- Place in project root (`/Users/kylenewman/morning-automation/`)

**2. First-Time Authentication**
```bash
cd /Users/kylenewman/morning-automation
python tests/test_newsletter.py
```
- Opens browser for OAuth flow
- User grants Gmail read-only access
- Token saved as `gmail_token.pickle`
- Future runs use cached token

**3. GitHub Actions Setup**
```bash
# Encode credentials for GitHub Secrets
base64 -i gmail_credentials.json

# Encode token for GitHub Secrets
base64 -i gmail_token.pickle
```
- Add `GMAIL_CREDENTIALS_BASE64` secret
- Add `GMAIL_TOKEN_BASE64` secret
- Workflow decodes both files at runtime

### Token Refresh
- Tokens expire after 7 days of inactivity
- Auto-refresh handled by Google Auth library
- If refresh fails: Re-authenticate locally and update `GMAIL_TOKEN_BASE64` secret

## Testing

### Local Testing
```bash
# Test newsletter fetching
python tests/test_newsletter.py
```

**Output:**
- Total stories found
- Filtered stories count
- Enriched stories count
- Sample article titles and summaries

### Test Specific Newsletter
```python
import asyncio
from podcast-summarizer.backend.ingestion.gmail_newsletters import get_newsletter_stories

result = asyncio.run(get_newsletter_stories('tldr_ai', hours_ago=24))
print(f"Stories: {len(result['stories'])}")
```

## Known Issues and Limitations

### 1. Morning Brew Parser Not Implemented
**Issue:** Parser function exists but returns empty list.  
**Impact:** Morning Brew newsletters not processed.  
**Fix:** Implement HTML parsing logic specific to Morning Brew format.

### 2. Single Newsletter Per Config
**Issue:** Only fetches most recent email per newsletter.  
**Impact:** If newsletter sent multiple times per day, only latest is processed.  
**Fix:** Process all emails within time window, deduplicate stories.

### 3. Paywall Handling
**Issue:** Article enrichment fails for paywalled content.  
**Impact:** Some enriched stories missing, falls back to links.  
**Fix:** Detect paywall, skip enrichment, keep as link-only story.

### 4. HTML Parsing Fragility
**Issue:** Parser breaks if TLDR changes email format.  
**Impact:** No stories extracted, empty newsletter section.  
**Fix:** Add fallback parser, more robust selectors, format detection.

### 5. No Fallback for Failed Enrichment
**Issue:** If all enrichment fails, only links shown.  
**Impact:** Lower quality briefing, missing detailed summaries.  
**Fix:** Use TLDR's brief descriptions as backup summaries.

## Future Enhancements

### Short-term
- Implement Morning Brew parser
- Add fallback summaries for failed enrichment
- Improve paywall detection and handling
- Add rate limiting for article fetching

### Long-term
- Support more newsletters (Hacker News Digest, AI Alignment Forum)
- Smart scheduling (fetch when newsletter typically arrives)
- Historical newsletter search and summarization
- Semantic deduplication across newsletters and agent search

