# How to Trigger Manual Workflow Run

## Via GitHub Web Interface

1. Go to your repository's Actions page:
   ```
   https://github.com/kylenewman/morning-automation-clean/actions
   ```

2. Click on "Morning Briefing" in the left sidebar

3. Click the "Run workflow" dropdown button (top right)

4. Configure the run:
   - **Branch:** main (should be selected by default)
   - **Run AI Agent Search:** true (recommended for full test)
   - **Run Newsletter Processing:** true (to test TLDR AI filtering)
   - **Run Podcast Processing:** true (for complete briefing)
   - **Use TEST_MODE:** false

5. Click the green "Run workflow" button

6. The workflow will appear in the list below. Click on it to see real-time logs

## Via Command Line (if GitHub CLI is installed)

```bash
# Install GitHub CLI first (if not installed)
# macOS: brew install gh
# Then authenticate: gh auth login

# Trigger workflow
gh workflow run morning-briefing.yml \
  --ref main \
  -f run_agent_search=true \
  -f run_newsletters=true \
  -f run_podcasts=true \
  -f test_mode=false

# View the run
gh run list --workflow=morning-briefing.yml --limit 1
gh run watch
```

## What to Look For in the Logs

### Newsletter Processing Section
Look for these log messages to verify TLDR AI filtering:

```
📧 PHASE 2: Processing Newsletters...
📧 Gmail query: after:XXXXXXX from:dan@tldrnewsletter.com
✅ Found X emails
✅ Found TLDR AI email matching body filter: 'TLDR AI'
```

### Expected Behavior
- Should find emails from dan@tldrnewsletter.com
- Should skip any that don't contain "TLDR AI" in body
- Should process the first email that contains "TLDR AI"
- Should extract and filter stories
- Should send briefing email

### If Issues Occur
- Check the "📧 Gmail query" line to see what filter was used
- Check if "✅ Found TLDR AI email matching body filter" appears
- If it says "⚠️ No emails found matching body filter", check:
  - That you received TLDR AI email in past 24 hours
  - That the email body actually contains "TLDR AI" text
  - Gmail authentication is working

## Quick Test (Just Newsletters)

For a faster test of just the newsletter filtering:

```bash
gh workflow run morning-briefing.yml \
  --ref main \
  -f run_agent_search=false \
  -f run_newsletters=true \
  -f run_podcasts=false
```

This will only test the newsletter processing and skip the time-consuming agent search and podcast processing.

