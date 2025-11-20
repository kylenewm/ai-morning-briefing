#!/usr/bin/env python3
"""
Test script for newsletter processing (1 run).
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

from backend.ingestion.gmail_newsletters import get_all_newsletters
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_newsletter():
    """Test newsletter processing."""
    print("=" * 80)
    print("📧 TESTING NEWSLETTER PROCESSING")
    print("=" * 80)
    print()
    
    try:
        logger.info("Fetching newsletters from Gmail...")
        start_time = datetime.now()
        
        # Get newsletters from past 24 hours
        result = await get_all_newsletters(hours_ago=24)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print()
        print("=" * 80)
        print("✅ TEST RESULTS")
        print("=" * 80)
        print(f"📊 Total stories: {result.get('total_stories', 0)}")
        print(f"📧 Newsletters found: {len(result.get('newsletters', {}))}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print()
        
        newsletters = result.get('newsletters', {})
        if newsletters:
            print("📰 Newsletter breakdown:")
            for newsletter_key, newsletter_data in newsletters.items():
                newsletter_name = newsletter_data.get('name', newsletter_key)
                count = newsletter_data.get('count', 0)
                stories = newsletter_data.get('stories', [])
                print(f"\n📧 {newsletter_name}:")
                print(f"   Stories: {count}")
                
                if stories:
                    print("   Sample stories:")
                    for i, story in enumerate(stories[:3], 1):
                        title = story.get('title', 'Unknown')
                        url = story.get('url', '')
                        print(f"   {i}. {title}")
                        if url:
                            print(f"      URL: {url[:80]}...")
        else:
            print("⚠️  No newsletters found")
        
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
        print()
        print("💡 Troubleshooting:")
        print("   - Check if gmail_credentials.json exists")
        print("   - Check if gmail_token.pickle exists (or run OAuth flow)")
        print("   - Verify GMAIL_ENABLED=true in .env")
        return {}


if __name__ == "__main__":
    asyncio.run(test_newsletter())

