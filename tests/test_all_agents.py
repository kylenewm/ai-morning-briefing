"""
Test all 3 agents with enhanced date filtering.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent / "podcast-summarizer"
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from backend.services.agents.search_orchestrator import search_all_categories, flatten_results
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_all_agents():
    """Test all agents with weekend-aware date filtering."""
    current_date = datetime.now()
    day_name = current_date.strftime('%A')
    is_monday = current_date.weekday() == 0
    cutoff = "72 hours" if is_monday else "48 hours"
    
    logger.info("\n🧪 TESTING ALL AGENTS WITH DATE FILTERING")
    logger.info(f"   Today: {day_name}, {current_date.strftime('%B %d, %Y')}")
    logger.info(f"   Cutoff: {cutoff} (strict)")
    logger.info("=" * 80)
    
    logger.info("\n🔍 Running all agents (1 iteration for speed)...")
    result = await search_all_categories(
        max_iterations=1,
        use_cache=False,
        run_source="manual"
    )
    
    articles = flatten_results(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Search Complete!")
    logger.info("=" * 80)
    logger.info(f"   Total Articles: {len(articles)}")
    logger.info(f"   - Conversational AI: {result['by_category_count']['conversational_ai']}")
    logger.info(f"   - General AI (Startups): {result['by_category_count']['general_ai']}")
    logger.info(f"   - Research/Opinion: {result['by_category_count']['research_opinion']}")
    logger.info("=" * 80)
    
    if not articles:
        logger.warning("\n⚠️  No articles found! Date filtering may be too strict for current content availability.")
        return
    
    # Check for old dates
    logger.info("\n📋 ARTICLES FOUND:")
    logger.info("=" * 80)
    
    old_articles = []
    old_date_patterns = [
        "May 2024", "May 13, 2024", "2023", "January 2024", 
        "February 2024", "March 2024", "April 2024", "May 2024",
        "June 2024", "July 2024", "August 2024", "September 2024", "October 2024"
    ]
    
    for i, article in enumerate(articles, 1):
        query_type = getattr(article, 'query_type', 'unknown')
        logger.info(f"\n{i}. [{query_type.replace('_', ' ').title()}] {article.title}")
        logger.info(f"   URL: {article.url}")
        
        summary = article.summary or ""
        found_old = [p for p in old_date_patterns if p in summary]
        
        if found_old:
            logger.warning(f"   ⚠️  OLD DATES: {', '.join(found_old)}")
            old_articles.append(article.title)
        else:
            logger.info(f"   ✅ No old dates detected")
        
        snippet = summary[:200] + "..." if len(summary) > 200 else summary
        logger.info(f"   Preview: {snippet}")
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 FINAL RESULTS")
    logger.info("=" * 80)
    logger.info(f"   Total articles: {len(articles)}")
    logger.info(f"   Old articles detected: {len(old_articles)}")
    
    if old_articles:
        logger.warning("\n⚠️  OLD ARTICLES STILL GETTING THROUGH:")
        for title in old_articles:
            logger.warning(f"   - {title}")
        logger.warning("\n❌ Date filtering needs adjustment!")
    else:
        logger.info("\n✅ SUCCESS! All articles are recent.")
        logger.info("   Date filtering is working correctly!")
    
    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_all_agents())
