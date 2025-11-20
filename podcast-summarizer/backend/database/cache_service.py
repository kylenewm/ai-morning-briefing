"""
Cache service for content items and insights.
Handles lookup, storage, and retrieval from database.
"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from .models import ContentItem, Insight
from .db import SessionLocal

logger = logging.getLogger(__name__)


class CacheService:
    """Handles caching of content and insights"""
    
    @staticmethod
    def get_cached_content(
        source_name: str,
        item_url: str,
        force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Check if content item exists in cache.
        
        Args:
            source_name: Name of the source (e.g., "Lenny's Podcast")
            item_url: URL of the content item (for deduplication)
            force_refresh: If True, ignore cache and return None
            
        Returns:
            Dict with content data if cached, None otherwise
        """
        if force_refresh:
            logger.info(f"🔄 Force refresh enabled, skipping cache for {item_url}")
            return None
        
        db = SessionLocal()
        try:
            item = db.query(ContentItem).filter(
                ContentItem.source_name == source_name,
                ContentItem.item_url == item_url
            ).first()
            
            if not item:
                return None
            
            logger.info(f"✅ Cache hit for: {item.title}")
            
            # Get latest insight for this content
            latest_insight = db.query(Insight).filter(
                Insight.content_item_id == item.id
            ).order_by(Insight.created_at.desc()).first()
            
            return {
                "id": item.id,
                "title": item.title,
                "url": item.item_url,
                "youtube_url": item.youtube_url,
                "published_date": item.published_date,
                "description": item.description,
                "transcript": item.transcript,
                "transcript_length": item.transcript_length,
                "insight": latest_insight.insight_text if latest_insight else None,
                "cached_at": item.created_at,
                "from_cache": True
            }
        finally:
            db.close()
    
    @staticmethod
    def get_cached_content_by_id(content_id: int) -> Optional[Dict[str, Any]]:
        """
        Get cached content by ID.
        
        Args:
            content_id: Database ID of the content item
            
        Returns:
            Dict with content data if found, None otherwise
        """
        db = SessionLocal()
        try:
            item = db.query(ContentItem).filter(
                ContentItem.id == content_id
            ).first()
            
            if not item:
                return None
            
            logger.info(f"✅ Cache hit by ID for: {item.title}")
            
            # Get latest insight for this content
            latest_insight = db.query(Insight).filter(
                Insight.content_item_id == item.id
            ).order_by(Insight.created_at.desc()).first()
            
            return {
                "id": item.id,
                "title": item.title,
                "url": item.item_url,
                "youtube_url": item.youtube_url,
                "published_date": item.published_date,
                "description": item.description,
                "transcript": item.transcript,
                "transcript_length": item.transcript_length,
                "insight": latest_insight.insight_text if latest_insight else None,
                "cached_at": item.created_at,
                "from_cache": True
            }
        finally:
            db.close()
    
    @staticmethod
    def save_content_and_insight(
        source_type: str,
        source_name: str,
        item_url: str,
        title: str,
        transcript: Optional[str],
        insight: Optional[str],
        youtube_url: Optional[str] = None,
        published_date: Optional[str] = None,  # Can be string or datetime
        description: Optional[str] = None,
        model_name: str = "gpt-5-mini",
        test_mode: bool = False,
        token_count: Optional[int] = None,
        cost_cents: Optional[int] = None
    ) -> int:
        """
        Save content item and insight to database.
        
        Returns:
            content_item_id
        """
        db = SessionLocal()
        try:
            # Parse published_date if it's a string
            parsed_date = None
            if published_date:
                if isinstance(published_date, str):
                    from dateutil import parser as date_parser
                    try:
                        parsed_date = date_parser.parse(published_date)
                    except:
                        parsed_date = None
                else:
                    parsed_date = published_date
            
            # Check if content exists
            existing = db.query(ContentItem).filter(
                ContentItem.item_url == item_url
            ).first()
            
            if existing:
                # Update existing
                existing.transcript = transcript
                existing.transcript_length = len(transcript) if transcript else 0
                existing.transcript_fetched = bool(transcript)
                existing.updated_at = datetime.utcnow()
                db.commit()
                content_id = existing.id
                logger.info(f"📝 Updated cached content: {title}")
            else:
                # Create new
                content = ContentItem(
                    source_type=source_type,
                    source_name=source_name,
                    item_url=item_url,
                    title=title,
                    youtube_url=youtube_url,
                    published_date=parsed_date,
                    description=description,
                    transcript=transcript,
                    transcript_length=len(transcript) if transcript else 0,
                    transcript_fetched=bool(transcript)
                )
                db.add(content)
                db.commit()
                db.refresh(content)
                content_id = content.id
                logger.info(f"💾 Saved new content: {title}")
            
            # Save insight if provided
            if insight:
                insight_obj = Insight(
                    content_item_id=content_id,
                    insight_text=insight,
                    model_name=model_name,
                    was_test_mode=test_mode,
                    token_count=token_count,
                    cost_cents=cost_cents
                )
                db.add(insight_obj)
                db.commit()
                logger.info(f"💡 Saved insight for: {title}")
            
            return content_id
        except Exception as e:
            logger.error(f"❌ Error saving to cache: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_recent_episodes(source_name: str, limit: int = 10) -> list[Dict[str, Any]]:
        """
        Get recent episodes from a source for historical archive browsing.
        
        Args:
            source_name: Name of the podcast/source
            limit: Max number of episodes to return
            
        Returns:
            List of episode dictionaries
        """
        db = SessionLocal()
        try:
            items = db.query(ContentItem).filter(
                ContentItem.source_name == source_name
            ).order_by(ContentItem.published_date.desc()).limit(limit).all()
            
            results = []
            for item in items:
                latest_insight = db.query(Insight).filter(
                    Insight.content_item_id == item.id
                ).order_by(Insight.created_at.desc()).first()
                
                results.append({
                    "id": item.id,
                    "title": item.title,
                    "url": item.item_url,
                    "youtube_url": item.youtube_url,
                    "published_date": item.published_date,
                    "has_transcript": item.transcript_fetched,
                    "has_insight": bool(latest_insight),
                    "cached_at": item.created_at
                })
            
            return results
        finally:
            db.close()
    
    @staticmethod
    def get_recent_content_urls(days: int = 5) -> Dict[str, Dict[str, Any]]:
        """
        Get ALL content URLs from past N days (agents, newsletters, news, etc.).
        Used for deduplication across all content types.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dict mapping URL -> metadata for logging:
            {
                "https://example.com/article": {
                    "source_type": "agent_search",
                    "source_name": "conversational_ai|manual",
                    "created_at": "2025-11-15",
                    "title": "Article Title"
                }
            }
        """
        from datetime import timedelta
        
        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Query ALL content items from past N days (all source_types)
            items = db.query(ContentItem).filter(
                ContentItem.created_at >= cutoff_date
            ).all()
            
            # Build dict of URLs with metadata for detailed logging
            url_map = {}
            for item in items:
                url_map[item.item_url] = {
                    "source_type": item.source_type,
                    "source_name": item.source_name,
                    "created_at": item.created_at.strftime("%Y-%m-%d"),
                    "title": item.title
                }
            
            logger.info(f"📊 Loaded {len(url_map)} URLs from past {days} days for deduplication")
            return url_map
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to load recent content URLs: {e}")
            return {}  # Return empty dict on error, don't crash
        finally:
            db.close()
    
    @staticmethod
    def save_agent_articles(
        articles: list[Dict[str, Any]],
        query_type: str,
        run_source: str = "manual"
    ) -> int:
        """
        Save agent-found articles to Supabase for deduplication.
        
        Args:
            articles: List of article dicts with url, title, summary, domain, score
            query_type: conversational_ai, general_ai, research_opinion
            run_source: "manual" (test run) or "automated" (daily briefing)
            
        Returns:
            Number of articles saved
        """
        db = SessionLocal()
        saved_count = 0
        
        try:
            for article in articles:
                # Check if already exists (shouldn't happen, but safe)
                existing = db.query(ContentItem).filter(
                    ContentItem.item_url == article['url']
                ).first()
                
                if existing:
                    logger.debug(f"   Article already in DB: {article['title'][:50]}")
                    continue
                
                # Create new content item
                content_item = ContentItem(
                    source_type="agent_search",
                    source_name=f"{query_type}|{run_source}",  # Track agent + run type
                    item_url=article['url'],
                    title=article['title'],
                    description=article.get('summary', ''),  # Store Exa summary
                    published_date=datetime.utcnow(),  # We don't have exact publish date
                    transcript_fetched=False,  # Not applicable for articles
                    youtube_url=None
                )
                
                db.add(content_item)
                saved_count += 1
            
            db.commit()
            logger.info(f"💾 Saved {saved_count} articles to Supabase (source: {query_type}|{run_source})")
            return saved_count
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to save articles to Supabase: {e}")
            db.rollback()
            return 0  # Return 0 on error, don't crash the whole process
        finally:
            db.close()

