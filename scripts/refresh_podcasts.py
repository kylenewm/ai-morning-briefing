#!/usr/bin/env python3
"""
Podcast Refresh Script

Fetches and transcribes new podcast episodes from RSS feeds.
Run this weekly to keep podcast cache fresh.

Usage:
  ./refresh_podcasts.py [--episodes-per-podcast 3]

Costs: ~$0.15-0.30 per episode transcribed
Recommended schedule: Weekly (Sundays at 8 PM)
"""

import requests
import sys
import argparse
from datetime import datetime

def refresh_podcasts(episodes_per_podcast: int = 3, force_refresh: bool = False):
    """
    Fetch and transcribe new podcast episodes.
    
    Args:
        episodes_per_podcast: Number of recent episodes to cache per podcast
        force_refresh: Force re-transcription even if cached
    """
    print(f"🎙️  Refreshing podcast cache...")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Episodes per podcast: {episodes_per_podcast}")
    print(f"🔄 Force refresh: {force_refresh}")
    print()
    
    try:
        url = f"http://localhost:8002/api/podcasts/cache-transcripts"
        params = {
            "episodes_per_podcast": episodes_per_podcast,
            "force_refresh": force_refresh
        }
        
        print("⏳ Calling transcription API...")
        print("   (This may take 30-60 seconds per episode)")
        print()
        
        response = requests.post(url, params=params, timeout=600)
        response.raise_for_status()
        
        data = response.json()
        
        print("✅ Transcription complete!")
        print()
        print("📊 Summary:")
        print(f"   Podcasts processed: {data['stats']['podcasts_processed']}")
        print(f"   Episodes cached: {data['stats']['episodes_cached']} (new)")
        print(f"   Episodes skipped: {data['stats']['episodes_skipped']} (already cached)")
        print(f"   Episodes failed: {data['stats']['episodes_failed']}")
        print(f"   Cost estimate: ${data['stats']['total_cost_estimate']:.2f}")
        print()
        
        if data['stats']['episodes_cached'] > 0:
            print("📝 Details:")
            for detail in data['stats']['details']:
                if detail['episodes_cached'] > 0:
                    print(f"   • {detail['podcast_name']}: {detail['episodes_cached']} new episodes")
        else:
            print("ℹ️  No new episodes found - cache is up to date!")
        
        print()
        print("✅ Podcast refresh complete!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server on port 8002")
        print("   Make sure the FastAPI server is running:")
        print("   cd podcast-summarizer && python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8002")
        return False
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out (took longer than 10 minutes)")
        print("   Some episodes may have been cached successfully.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Refresh podcast cache with new episodes")
    parser.add_argument(
        "--episodes-per-podcast",
        type=int,
        default=3,
        help="Number of episodes to cache per podcast (default: 3)"
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force re-transcription even if already cached"
    )
    
    args = parser.parse_args()
    
    success = refresh_podcasts(
        episodes_per_podcast=args.episodes_per_podcast,
        force_refresh=args.force_refresh
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

