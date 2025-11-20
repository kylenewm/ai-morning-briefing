"""
Database models for morning briefing system.
Simple, extensible design for caching and historical archive.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class ContentItem(Base):
    """
    Stores any content item (podcast episode, article, etc.)
    Serves as cache to avoid re-fetching transcripts.
    """
    __tablename__ = "content_items"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Identification (for cache lookup)
    source_type = Column(String(50), nullable=False)  # "podcast", "article", "newsletter"
    source_name = Column(String(255), nullable=False)  # "Lenny's Podcast"
    item_url = Column(String(1000), nullable=False, unique=True)  # Unique URL for deduplication
    
    # Content metadata
    title = Column(String(500), nullable=False)
    published_date = Column(DateTime)
    
    # Raw content (for archive)
    description = Column(Text)  # Episode description from RSS
    transcript = Column(Text)  # Full transcript text
    youtube_url = Column(String(500))
    
    # Processing metadata
    transcript_fetched = Column(Boolean, default=False)
    transcript_length = Column(Integer)  # Character count
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for fast lookup
    __table_args__ = (
        Index('idx_source_lookup', 'source_name', 'item_url'),
        Index('idx_published', 'published_date'),
    )


class Insight(Base):
    """
    AI-generated insights from content.
    Multiple insights can exist for same content (different models, re-runs).
    """
    __tablename__ = "insights"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Link to content (soft reference, no FK for simplicity)
    content_item_id = Column(Integer, nullable=False, index=True)
    
    # Insight content (multi-layer architecture)
    insight_text = Column(Text, nullable=False)  # Full 3000-char concept summary
    practical_tips = Column(Text)  # JSON array of 4-6 practical tip bullets
    enriched_content = Column(Text)  # Rich stories, workflows, gotchas for deep-dive
    
    # Generation metadata
    model_name = Column(String(50))  # "gpt-5-mini", "gpt-4o"
    was_test_mode = Column(Boolean, default=False)  # Was this from truncated transcript?
    
    # Quality metrics
    token_count = Column(Integer)
    cost_cents = Column(Integer)  # Cost in cents (e.g., 15 = $0.15)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_content_insights', 'content_item_id'),
    )


class Briefing(Base):
    """
    Generated morning briefings - for historical archive.
    """
    __tablename__ = "briefings"
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Briefing metadata
    date = Column(DateTime, nullable=False, unique=True)
    title = Column(String(255))
    
    # Content
    briefing_text = Column(Text, nullable=False)
    
    # Metadata
    total_episodes = Column(Integer)
    total_sources = Column(Integer)
    total_cost_cents = Column(Integer)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_date', 'date'),
    )

