# Scripts Directory

This directory contains utility scripts for manual operations.

## Utility Scripts

### `refresh_podcasts.py`
**Purpose:** Manually refresh podcast cache by transcribing new episodes  
**Usage:** `python scripts/refresh_podcasts.py [--episodes-per-podcast 3]`  
**Cost:** ~$0.15-0.30 per episode transcribed  
**When to use:** Weekly or when you want to update podcast cache with latest episodes

**Example:**
```bash
# Refresh with default 3 episodes per podcast
python scripts/refresh_podcasts.py

# Refresh with 5 episodes per podcast
python scripts/refresh_podcasts.py --episodes-per-podcast 5
```

**Note:** The automated GitHub Actions workflow handles daily briefings. This script is only for manual cache refresh.

---

## Archived Scripts

See `scripts/archive/` for deprecated scripts that have been replaced by GitHub Actions automation.


