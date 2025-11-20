#!/usr/bin/env python3
"""
Test script for search orchestrator with 1 iteration per agent.
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

from backend.services.agents.search_orchestrator import search_all_categories, flatten_results
from backend.test_config import IS_TEST_MODE, AGENT_MAX_ITERATIONS
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_agent_search():
    """Test search orchestrator."""
    # Use test config if set, otherwise default
    max_iters = AGENT_MAX_ITERATIONS if AGENT_MAX_ITERATIONS else 3
    mode = "🧪 TEST MODE (fast & cheap)" if IS_TEST_MODE else "🚀 PRODUCTION MODE"
    
    print("=" * 80)
    print(f"🤖 TESTING SEARCH ORCHESTRATOR - {mode}")
    print(f"   Iterations: {max_iters} per agent")
    print("=" * 80)
    print()
    
    try:
        logger.info(f"Running orchestrator with max_iterations={max_iters}...")
        start_time = datetime.now()
        
        # Run orchestrator - test config automatically applied if TEST_MODE set
        orchestrator_results = await search_all_categories(
            max_iterations=max_iters,
            use_cache=False  # Force fresh search for testing
        )
        
        # Flatten results for display
        articles = flatten_results(orchestrator_results)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print()
        print("=" * 80)
        print("✅ TEST RESULTS")
        print("=" * 80)
        print(f"📊 Total articles found: {len(articles)}")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print()
        print("📈 By Category:")
        print(f"   • Conversational AI: {orchestrator_results['by_category_count']['conversational_ai']} articles")
        print(f"   • General AI: {orchestrator_results['by_category_count']['general_ai']} articles")
        print(f"   • Research/Opinion: {orchestrator_results['by_category_count']['research_opinion']} articles")
        print()
        
        if articles:
            print("📰 Sample articles by category:")
            
            # Show Conversational AI articles
            if orchestrator_results['conversational_ai']:
                print("\n🗣️  Conversational AI:")
                for i, article in enumerate(orchestrator_results['conversational_ai'][:2], 1):
                    print(f"   {i}. {article.title}")
                    print(f"      URL: {article.url}")
                    if article.summary:
                        summary_preview = article.summary[:100] + "..." if len(article.summary) > 100 else article.summary
                        print(f"      Summary: {summary_preview}")
            
            # Show General AI articles
            if orchestrator_results['general_ai']:
                print("\n🤖 General AI:")
                for i, article in enumerate(orchestrator_results['general_ai'][:2], 1):
                    print(f"   {i}. {article.title}")
                    print(f"      URL: {article.url}")
                    if article.summary:
                        summary_preview = article.summary[:100] + "..." if len(article.summary) > 100 else article.summary
                        print(f"      Summary: {summary_preview}")
            
            # Show Research/Opinion articles
            if orchestrator_results['research_opinion']:
                print("\n📊 Research/Opinion:")
                for i, article in enumerate(orchestrator_results['research_opinion'][:1], 1):
                    print(f"   {i}. {article.title}")
                    print(f"      URL: {article.url}")
                    if article.summary:
                        summary_preview = article.summary[:100] + "..." if len(article.summary) > 100 else article.summary
                        print(f"      Summary: {summary_preview}")
        else:
            print("⚠️  No articles found")
        
        print()
        print("=" * 80)
        print("✅ TEST COMPLETE")
        print("=" * 80)
        
        return articles
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        print()
        print("=" * 80)
        print("❌ TEST FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        return []


if __name__ == "__main__":
    asyncio.run(test_agent_search())

