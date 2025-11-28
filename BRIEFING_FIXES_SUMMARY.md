# Morning Briefing Fixes - Summary

## Changes Made (November 28, 2025)

### 1. Fixed Duplicate Workflow Runs ✅

**Problem:** The workflow was running twice daily because both cron schedules were active:
- `30 14 * * 1-5` (9:30 AM EST)
- `30 13 * * 1-5` (9:30 AM EDT)

**Solution:** Removed the duplicate schedule. Now only runs once at 14:30 UTC.

**File:** `.github/workflows/morning-briefing.yml`
- Lines 40-44: Updated to single cron schedule
- Note: Will run at 9:30 AM EST (winter) and 10:30 AM EDT (summer)

### 2. Filter TLDR Newsletter to AI Edition Only ✅

**Problem:** Multiple TLDR newsletters from same sender (AI, Tech, Web Dev, etc.) with same sender email but no distinguishing subject line.

**Solution:** Added body content filter to only get emails containing "TLDR AI" in the body.

**File:** `podcast-summarizer/backend/ingestion/gmail_newsletters.py`
- Line 41: Added `body_must_contain: "TLDR AI"` to config
- Lines 474-510: Updated `get_newsletter_stories()` to check multiple emails and filter by body content
- Now loops through emails from dan@tldrnewsletter.com and only processes ones with "TLDR AI" in body

### 3. Added Retry Workflow ✅

**Problem:** If newsletter arrives late, the briefing would miss it.

**Solution:** Created a retry workflow that runs 30 minutes after main briefing.

**File:** `.github/workflows/morning-briefing-retry.yml` (NEW)
- Runs at 15:00 UTC (10:00 AM EST) - 30 minutes after main
- Checks if main briefing succeeded today
- Only runs if main failed OR manually triggered
- Focuses on newsletter processing (agent search and podcasts disabled by default)

## Testing

### Manual Test Run
To test the changes, trigger a manual workflow run:

1. Go to: https://github.com/kylenewman/morning-automation-clean/actions/workflows/morning-briefing.yml
2. Click "Run workflow" button
3. Select branch: `main`
4. Configure options as needed
5. Click "Run workflow"

### Expected Behavior
1. Workflow should run ONCE (not twice)
2. Newsletter processing should only fetch "TLDR AI" emails
3. If newsletter not found, briefing should still send with other content
4. Retry workflow available as backup

## Schedule Summary

| Workflow | Time (UTC) | Time (EST) | Purpose |
|----------|-----------|-----------|----------|
| morning-briefing.yml | 14:30 | 9:30 AM | Main briefing |
| morning-briefing-retry.yml | 15:00 | 10:00 AM | Retry if main failed |

## Next Steps

1. ✅ Changes committed
2. ⏳ Test manual run
3. ⏳ Monitor tomorrow's scheduled run
4. ⏳ Verify only TLDR AI newsletter is fetched
5. ⏳ Confirm single daily run (not double)

