#!/usr/bin/env python3
"""
Morning briefing script for GitHub Actions.
Runs: Agent search + Podcast processing + Newsletter processing + Email generation
"""
import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Import using relative imports (works when run as module with python -m)
from ..services.agents.search_orchestrator import search_all_categories, flatten_results
from ..ingestion.gmail_newsletters import get_all_newsletters, filter_and_rank_stories_for_ai_pm, enrich_stories_with_ai
from ..email_service import send_briefing_email
from ..database.db import init_db
from ..config import settings

# Import working podcast processor from API routes
from ..api.routes import process_podcasts_from_cache
from ..services.assemblyai_processor import cache_all_podcast_transcripts
from ..ingestion.sources import get_all_podcast_sources
from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def clean_exa_summary_with_llm(summary: str, llm: ChatOpenAI) -> str:
    """
    Use LLM to extract only the actual article summary content,
    removing all meta-commentary, analysis notes, and Exa's internal formatting.
    
    Args:
        summary: Raw Exa summary text
        llm: ChatOpenAI instance
        
    Returns:
        Cleaned summary with only article content
    """
    if not summary or len(summary.strip()) < 50:
        return summary
    
    prompt = f"""You are reformatting an Exa AI search summary..

REMOVE:
- Meta-commentary like "Areas Not Covered", "Focus Areas Covered"
- Source attributions like "*Source: ecfan*", "*Source: by Paul Gillin*", "*Source: News Desk*" (anything with *Source:)
- Analysis notes about what the article does/doesn't cover
- Section headers that are Exa's internal analysis

KEEP & REFORMAT:
- The actual article content
- Key product updates, announcements, technical details
- Important facts, numbers, dates, names

CRITICAL FORMATTING:
- If the content has bullet points, convert them into flowing paragraphs with natural transitions
- Write 2-4 cohesive paragraphs (not bullet points or lists)
- Use connective language: "Additionally,", "The update also includes...", "Furthermore," etc.
- Don't add filler or elaborate—just present what's in the original in paragraph form

Input summary:
{summary}

Output the reformatted summary as flowing paragraphs:"""

    try:
        response = await llm.ainvoke(prompt)
        cleaned = response.content.strip()
        return cleaned if cleaned else summary  # Fallback to original if LLM fails
    except Exception as e:
        logger.warning(f"LLM summary cleaning failed: {e}, using original")
        return summary


async def main():
    """Run the complete morning briefing workflow."""
    start_time = datetime.now()
    
    # Check which phases to run (from workflow inputs or default to all)
    run_agent_search = os.getenv('RUN_AGENT_SEARCH', 'true').lower() == 'true'
    run_newsletters = os.getenv('RUN_NEWSLETTERS', 'true').lower() == 'true'
    run_podcasts = os.getenv('RUN_PODCASTS', 'true').lower() == 'true'
    
    logger.info("=" * 80)
    logger.info(f"🌅 MORNING BRIEFING: {start_time.strftime('%Y-%m-%d %I:%M %p ET')}")
    logger.info("=" * 80)
    logger.info(f"Phase Configuration:")
    logger.info(f"  • Agent Search: {'✅ Enabled' if run_agent_search else '⏭️  Skipped'}")
    logger.info(f"  • Newsletters: {'✅ Enabled' if run_newsletters else '⏭️  Skipped'}")
    logger.info(f"  • Podcasts: {'✅ Enabled' if run_podcasts else '⏭️  Skipped'}")
    logger.info("=" * 80)
    
    # Initialize database (creates tables if they don't exist)
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
    
    try:
        # Initialize containers for results
        articles = []
        
        # Phase 1: Run AI search agents (no cache, fresh daily articles)
        if run_agent_search:
            logger.info("\n" + "=" * 80)
            logger.info("🤖 PHASE 1: Running AI Search Agents...")
            logger.info("=" * 80)
            
            articles_result = await search_all_categories(
                max_iterations=3, 
                use_cache=False,
                run_source="automated"  # Track as automated daily run
            )
            
            logger.info(f"\n✅ Agent Search Complete!")
            logger.info(f"   Total Articles: {articles_result['total']}")
            logger.info(f"   - Conversational AI: {articles_result['by_category_count']['conversational_ai']}")
            logger.info(f"   - General AI: {articles_result['by_category_count']['general_ai']}")
            logger.info(f"   - Research/Opinion: {articles_result['by_category_count']['research_opinion']}")
        else:
            logger.info("\n⏭️  PHASE 1: Agent Search SKIPPED")
            articles_result = {'conversational_ai': [], 'general_ai': [], 'research_opinion': []}
        
        # Phase 2: Process newsletters (TLDR AI)
        enriched_newsletter_stories = []
        link_newsletter_stories = []
        if run_newsletters:
            logger.info("\n" + "=" * 80)
            logger.info("📧 PHASE 2: Processing Newsletters...")
            logger.info("=" * 80)
            
            try:
                newsletters_result = await get_all_newsletters(hours_ago=24, max_stories=15)
                
                if newsletters_result.get('total_stories', 0) > 0:
                    # Extract all stories from all newsletters
                    all_newsletter_stories = []
                    for newsletter_data in newsletters_result.get('newsletters', {}).values():
                        all_newsletter_stories.extend(newsletter_data.get('stories', []))
                    
                    # Step 1: Apply AI filtering to get top 12 relevant stories
                    if all_newsletter_stories:
                        filtered_stories = await filter_and_rank_stories_for_ai_pm(
                            all_newsletter_stories, 
                            max_stories=12
                        )
                        
                        # Step 2: Enrich top 5 with AI (fetch full article + GPT-4 summary)
                        top_k = min(5, len(filtered_stories))
                        logger.info(f"   🎯 Enriching top {top_k} stories with AI...")
                        enriched_newsletter_stories = await enrich_stories_with_ai(
                            filtered_stories[:top_k],
                            max_stories=top_k
                        )
                        
                        # Step 3: Keep remaining stories as links only
                        link_newsletter_stories = filtered_stories[top_k:]
                        
                    logger.info(f"\n✅ Newsletter Processing Complete!")
                    logger.info(f"   Total Stories Found: {len(all_newsletter_stories)}")
                    logger.info(f"   Enriched Stories: {len(enriched_newsletter_stories)}")
                    logger.info(f"   Link-Only Stories: {len(link_newsletter_stories)}")
                else:
                    logger.info(f"   ⚠️ No newsletters found in past 24 hours")
            except Exception as e:
                logger.warning(f"   ⚠️ Newsletter processing failed: {e}")
        else:
            logger.info("\n⏭️  PHASE 2: Newsletter Processing SKIPPED")
        
        # Phase 3: Process podcasts (cache new episodes, then read from cache)
        podcast_results = {'episodes_by_podcast': {}, 'total_episodes': 0}
        if run_podcasts:
            logger.info("\n" + "=" * 80)
            logger.info("🎙️ PHASE 3: Processing Podcasts...")
            logger.info("=" * 80)
            
            try:
                # Step 1: Cache any new episodes (only transcribes what's not cached)
                logger.info("📥 Step 1: Checking for new episodes to transcribe...")
                cache_result = await cache_all_podcast_transcripts(
                    episodes_per_podcast=3,
                    force_refresh=False  # Only transcribe new episodes
                )
                
                logger.info(f"   ✅ Cache check complete:")
                logger.info(f"      New episodes transcribed: {cache_result['stats']['episodes_cached']}")
                logger.info(f"      Already cached: {cache_result['stats']['episodes_skipped']}")
                logger.info(f"      Cost estimate: ${cache_result['stats']['total_cost_estimate']:.2f}")
                
                # Step 2: Get cached transcripts and generate insights
                logger.info("\n📖 Step 2: Generating insights from cached transcripts...")
                podcast_results = await process_podcasts_from_cache(
                    episodes_per_podcast=3,
                    force_refresh=False  # Use cached transcripts and insights
                )
                
                logger.info(f"\n✅ Podcast Processing Complete!")
                logger.info(f"   Total Episodes: {podcast_results.get('total_episodes', 0)}")
                logger.info(f"   Transcript Success: {podcast_results.get('transcript_success_rate', '0/0')}")
                for podcast_name, episodes in podcast_results.get('episodes_by_podcast', {}).items():
                    logger.info(f"   - {podcast_name}: {len(episodes)} episodes")
                    
            except Exception as e:
                logger.error(f"   ❌ Podcast processing failed: {e}")
                logger.warning(f"   Continuing without podcasts...")
        else:
            logger.info("\n⏭️  PHASE 3: Podcast Processing SKIPPED")
        
        # Phase 4: Generate email briefing
        logger.info("\n" + "=" * 80)
        logger.info("📧 PHASE 4: Generating and Sending Email Briefing...")
        logger.info("=" * 80)
        
        # Build email content (plain text with markdown - will be formatted to HTML later)
        email_subject = f"🌅 AI PM Briefing - {start_time.strftime('%A, %B %d, %Y')}"
        
        # Generate markdown briefing text (following proven format from /morning-briefing API)
        briefing_text = ""
        
        # Newsletter Stories Section - Enriched (Top 5 with full summaries)
        if enriched_newsletter_stories:
            briefing_text += "## Newsletter Stories\n\n"
            
            for story in enriched_newsletter_stories:
                briefing_text += f"### {story['title']}\n\n"
                
                # Add full AI-generated summary (3-5 paragraphs)
                summary = story.get('summary', '')
                if summary:
                    briefing_text += f"{summary}\n\n"
                
                # Add key takeaways if available
                key_points = story.get('key_points', [])
                if key_points:
                    briefing_text += "**Key Points:**\n"
                    for point in key_points:
                        briefing_text += f"- {point}\n"
                    briefing_text += "\n"
                
                # Add URL
                briefing_text += f"[Read more]({story.get('url', '#')})\n\n"
                briefing_text += "---\n\n"
        
        # Newsletter Stories Section - Links Only (Remaining stories)
        if link_newsletter_stories:
            briefing_text += "### Additional Newsletter Stories\n\n"
            
            for story in link_newsletter_stories:
                # Brief description with link
                description = story.get('brief_description', '')
                if description:
                    # Truncate if too long (keep first 100 chars)
                    if len(description) > 100:
                        description = description[:97] + "..."
                    briefing_text += f"• [{story['title']}]({story.get('url', '#')})\n  *{description}*\n"
                else:
                    briefing_text += f"• [{story['title']}]({story.get('url', '#')})\n"
            
            briefing_text += "\n---\n\n"
        
        # AI-Curated Articles Section (only if we have articles)
        categories = {
            'conversational_ai': '🗣️ Conversational AI',
            'general_ai': '🚀 AI Startups & Emerging Companies',
            'research_opinion': '🔬 Research & Opinion'
        }
        
        total_articles = sum(len(articles_result.get(cat, [])) for cat in categories.keys())
        if total_articles > 0:
            # Initialize LLM for summary cleaning
            llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
            
            briefing_text += "## AI-Curated Articles\n\n"
            briefing_text += "*🤖 Curated by AI Agent using Exa semantic search*\n\n"
            
            for category_key, category_name in categories.items():
                category_articles = articles_result.get(category_key, [])
                if category_articles:
                    briefing_text += f"### {category_name}\n\n"
                    for article in category_articles:
                        briefing_text += f"#### [{article.title}]({article.url})\n\n"
                        
                        # Add summary if available (cleaned with LLM)
                        if article.summary:
                            cleaned_summary = await clean_exa_summary_with_llm(article.summary, llm)
                            if cleaned_summary:
                                briefing_text += f"{cleaned_summary}\n\n"
                        
                        # Add source
                        if article.source:
                            briefing_text += f"*Source: {article.source}*\n\n"
                        
                        briefing_text += "---\n\n"
        
        # Podcast Section - 2-Tier System
        # Primary podcasts: First episode with detailed summary
        # Secondary + 2nd episodes: Links only
        
        podcast_sources = get_all_podcast_sources()
        primary_podcasts = {name: info for name, info in podcast_sources.items() if info.get('priority') == 'primary'}
        
        # Collect primary podcast episodes (first episode only, with full insights)
        detailed_episodes = []
        link_only_episodes = []
        
        for podcast_name, episodes in podcast_results.get('episodes_by_podcast', {}).items():
            if not episodes:
                continue
                
            # Check if this is a primary podcast
            is_primary = any(info['name'] == podcast_name and info.get('priority') == 'primary' 
                           for info in podcast_sources.values())
            
            if is_primary and episodes:
                # First episode: detailed summary
                first_episode = episodes[0]
                insights = first_episode.get('insights')
                
                if insights and isinstance(insights, str) and insights.strip() and insights.strip() != 'No insights available.':
                    detailed_episodes.append({
                        'podcast_name': podcast_name,
                        'episode': first_episode,
                        'insights': insights
                    })
                
                # Remaining episodes from primary podcasts: links only
                for episode in episodes[1:]:
                    link_only_episodes.append({
                        'podcast_name': podcast_name,
                        'episode': episode
                    })
            else:
                # Secondary podcasts: all episodes as links only
                for episode in episodes:
                    link_only_episodes.append({
                        'podcast_name': podcast_name,
                        'episode': episode
                    })
        
        # Display detailed episodes (primary podcasts, first episode)
        if detailed_episodes:
            briefing_text += "## Podcast Insights\n\n"
            
            for item in detailed_episodes:
                briefing_text += f"### {item['podcast_name']}\n\n"
                briefing_text += f"**{item['episode'].get('title', 'Untitled Episode')}**\n\n"
                briefing_text += f"{item['insights']}\n\n"
                
                if item['episode'].get('link'):
                    briefing_text += f"[Listen →]({item['episode']['link']})\n\n"
                
                briefing_text += "---\n\n"
        
        # Display link-only episodes (secondary podcasts + additional primary episodes)
        if link_only_episodes:
            briefing_text += "### Additional Podcast Episodes\n\n"
            
            for item in link_only_episodes:
                briefing_text += f"• **{item['podcast_name']}**: [{item['episode'].get('title', 'Untitled')}]({item['episode'].get('link', '#')})\n"
            
            briefing_text += "\n---\n\n"
        
        # Send email
        try:
            recipient = settings.EMAIL_RECIPIENT
            if not recipient:
                logger.error("EMAIL_RECIPIENT not configured")
                raise ValueError("EMAIL_RECIPIENT environment variable not set")
            
            total_articles = sum(len(articles_result.get(cat, [])) for cat in ['conversational_ai', 'general_ai', 'research_opinion'])
            stats = {
                'newsletter_stories': len(enriched_newsletter_stories),
                'agent_articles': total_articles,
                'podcast_episodes': podcast_results.get('total_episodes', 0)
            }
            
            success = send_briefing_email(
                briefing_text=briefing_text,  # Markdown text (will be formatted to HTML by format_briefing_as_html)
                stats=stats,
                recipient_email=recipient,
                subject=email_subject,
                use_html=True
            )
            
            if success:
                logger.info("✅ Email sent successfully!")
            else:
                logger.error("❌ Email sending returned False")
                raise Exception("Email sending failed")
                
        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}")
            raise
        
        # Summary
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ MORNING BRIEFING COMPLETE")
        logger.info(f"   Total Time: {duration:.1f}s")
        logger.info(f"   Agent Articles: {total_articles}")
        logger.info(f"   Newsletter Stories (Enriched): {len(enriched_newsletter_stories)}")
        logger.info(f"   Newsletter Stories (Links): {len(link_newsletter_stories)}")
        logger.info(f"   Podcast Episodes: {podcast_results.get('total_episodes', 0)}")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ ERROR: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

