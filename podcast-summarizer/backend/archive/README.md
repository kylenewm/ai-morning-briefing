# Archived Components

This directory contains code that has been removed from the main pipeline but preserved for future reference or potential reimplementation.

---

## youtube_search.py

**Purpose**: Fallback to search YouTube when RSS doesn't include video URLs

**Why Archived**: 
- 95% of podcast episodes have YouTube URLs in RSS already
- Complex web scraping with fragile HTML parsing
- Adds latency and failure points
- Not worth the maintenance overhead for edge cases

**When to Reimplement**:
- If you add podcasts that consistently don't include YouTube links in RSS
- Consider using YouTube Data API instead of web scraping
- Or use OpenAI search: "Find YouTube link for {episode_title} on {channel}"
- Or manually configure YouTube URLs in podcast source config

**Original location**: `backend/ingestion/youtube_search.py`  
**Archived date**: 2025-10-19  
**Last working version**: Commit before this change

---

## How to Use Archived Code

If you need to reimplement this functionality:

1. Copy the file back to its original location
2. Restore the import in `rss_parser.py`
3. Test thoroughly - web scraping may have broken due to YouTube changes
4. Consider modern alternatives (API, OpenAI search) before using scraping

---

## Description Summarization (Deprecated but not archived)

The description-based summarization functions in `summarizer.py` are marked as deprecated but kept in the codebase since they're simple and might be useful for reference or debugging.

Functions:
- `summarize_description()` - Summarize episode from RSS description
- `summarize_episode()` - Dispatcher for different summarization methods

These are no longer called in the main pipeline but remain available if needed.




