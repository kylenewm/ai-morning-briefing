#!/usr/bin/env python3
"""
Test script for podcast processing (1 episode).
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add podcast-summarizer to path (go up one level from tests/ to root)
project_root = Path(__file__).parent.parent / "podcast-summarizer"
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from backend.services.podcast_processor import process_all_podcasts_parallel
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_podcast():
    """Test podcast processing with 1 episode per podcast."""
    print("=" * 80)
    print("🎙️  TESTING PODCAST PROCESSING (1 episode)")
    print("=" * 80)
    print()
    
    try:
        logger.info("Starting podcast processing...")
        start_time = datetime.now()
        
        # Process podcasts with 1 episode each
        result = await process_all_podcasts_parallel(
            episodes_per_podcast=1,
            use_transcripts=True,
            test_mode=False,
            include_transcripts=False,
            force_refresh=False
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print()
        print("=" * 80)
        print("✅ TEST RESULTS")
        print("=" * 80)
        print(f"📊 Total episodes processed: {result.get('total_episodes', 0)}")
        print(f"📻 Podcasts processed: {len(result.get('episodes_by_podcast', {}))}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print()
        
        episodes_by_podcast = result.get('episodes_by_podcast', {})
        if episodes_by_podcast:
            print("📰 Processed episodes:")
            for podcast_name, episodes in episodes_by_podcast.items():
                print(f"\n🎙️  {podcast_name}:")
                for episode in episodes:
                    title = episode.get('title', 'Unknown')
                    has_summary = 'summary' in episode and episode['summary']
                    has_insights = 'insights' in episode and episode['insights']
                    print(f"   • {title}")
                    print(f"     Summary: {'✅' if has_summary else '❌'}")
                    print(f"     Insights: {'✅' if has_insights else '❌'}")
        else:
            print("⚠️  No episodes processed")
        
        failed_transcripts = result.get('failed_transcripts', [])
        if failed_transcripts:
            print(f"\n⚠️  Failed transcripts: {len(failed_transcripts)}")
            for failed in failed_transcripts[:3]:
                print(f"   • {failed.get('title', 'Unknown')}: {failed.get('reason', 'Unknown error')}")
        
        print()
        print("=" * 80)
        print("✅ TEST COMPLETE")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        print()
        print("=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        return {}


if __name__ == "__main__":
    asyncio.run(test_podcast())

