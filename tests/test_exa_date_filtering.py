"""
Test Exa search with enhanced date filtering.
Run locally to verify old articles are properly rejected.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent / "podcast-summarizer"
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from backend.services.agents.general_ai_agent import GeneralAIAgent
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_exa_date_filtering():
    """Test that old articles are filtered out by enhanced evaluation."""
    logger.info("\n🧪 TESTING EXA DATE FILTERING")
    logger.info(f"   Current date: {datetime.now().strftime('%B %d, %Y')}")
    logger.info("   Target: Only articles from past 4 days")
    logger.info("=" * 80)
    
    # Test General AI agent (where we saw the May 2024 article)
    agent = GeneralAIAgent(run_source="manual")
    
    logger.info("\n🔍 Running General AI search (1 iteration for speed)...")
    result = await agent.search(max_iterations=1, use_cache=False)
    
    # Result is a list of SearchResult objects
    articles = result if isinstance(result, list) else result.get('articles', [])
    
    logger.info("\n" + "=" * 80)
    logger.info(f"✅ Search Complete!")
    logger.info(f"   Articles returned: {len(articles)}")
    logger.info("=" * 80)
    
    if not articles:
        logger.warning("⚠️  No articles found!")
        return
    
    # Check for old articles
    logger.info("\n📋 ARTICLES FOUND:")
    logger.info("=" * 80)
    
    old_articles_found = []
    
    for i, article in enumerate(articles, 1):
        logger.info(f"\n{i}. {article.title}")
        logger.info(f"   URL: {article.url}")
        if hasattr(article, 'score'):
            logger.info(f"   Score: {article.score}")
        
        # Check summary for date mentions
        summary = article.summary or ""
        
        # Look for old dates in summary
        old_date_patterns = [
            "May 2024", "May 13, 2024", "2023", "January 2024", 
            "February 2024", "March 2024", "April 2024", "May 2024",
            "June 2024", "July 2024", "August 2024", "September 2024"
        ]
        
        found_old_dates = [pattern for pattern in old_date_patterns if pattern in summary]
        
        if found_old_dates:
            logger.warning(f"   ⚠️  OLD DATES FOUND: {', '.join(found_old_dates)}")
            old_articles_found.append({
                'title': article.title,
                'url': article.url,
                'dates': found_old_dates,
                'score': getattr(article, 'score', 'N/A')
            })
        else:
            logger.info(f"   ✅ No old dates detected")
        
        # Show snippet of summary
        if summary:
            snippet = summary[:200] + "..." if len(summary) > 200 else summary
            logger.info(f"   Summary: {snippet}")
    
    logger.info("\n" + "=" * 80)
    logger.info("📊 RESULTS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"   Total articles: {len(articles)}")
    logger.info(f"   Old articles detected: {len(old_articles_found)}")
    
    if old_articles_found:
        logger.warning("\n⚠️  OLD ARTICLES STILL GETTING THROUGH:")
        for article in old_articles_found:
            logger.warning(f"   - {article['title']}")
            logger.warning(f"     URL: {article['url']}")
            logger.warning(f"     Score: {article['score']}")
            logger.warning(f"     Old dates: {', '.join(article['dates'])}")
    else:
        logger.info("\n✅ SUCCESS! No old articles detected.")
        logger.info("   Date filtering is working correctly!")
    
    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_exa_date_filtering())

