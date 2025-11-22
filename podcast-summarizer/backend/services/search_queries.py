"""
Search Query Library for AI Newsletter Agent

Simplified, focused queries for Exa semantic search.
Uses 3 specialized queries for targeted coverage:
1. Conversational AI (voice, agents, real-time systems)
2. AI Startups & Emerging Companies (innovation from smaller players)
3. Research/Opinion (trends, analysis, insights)

Note: Original detailed queries archived in search_queries_ORIGINAL_DETAILED.py
"""

# Query 1: Conversational AI (Voice + Agents) - SIMPLIFIED
CONVERSATIONAL_AI_QUERY = """
Recent voice AI and conversational agent updates for AI Product Managers (past 24-96 hours).

Areas of interest: Real-time voice platforms, streaming speech APIs, agent frameworks, multi-agent orchestration, speech-to-text advancements, text-to-speech improvements, voice cloning technology, conversational UX patterns, agentic workflows, function calling, tool use, and any other relevant voice or agent technologies.

Focus on: Product announcements, API updates, new capabilities, enterprise deployments, technical blog posts from companies building in this space.

Avoid: Basic tutorials, getting started guides, support guides, news aggregators (TechCrunch, VentureBeat, etc.), generic news coverage. Prefer original sources and official announcements.
"""

# Query 2: AI Startups & Emerging Companies - FOCUSED ON INNOVATION
GENERAL_AI_QUERY = """
Recent product launches and updates from AI startups and emerging companies for AI Product Managers (past 24-96 hours).

Areas of interest: New AI tools and platforms from startups, product launches, funding announcements, innovative AI applications, developer tools, infrastructure startups, vertical AI solutions, open-source projects from smaller teams, emerging companies disrupting traditional AI workflows.

Focus on: Company announcements from startups and smaller AI companies, new product launches, technical innovations, seed/Series A-C funding with product details, open-source releases from emerging teams, novel AI applications and use cases.

Avoid: Major tech companies (OpenAI, Google, Anthropic, Microsoft, Meta), generic explainers, tutorials, support guides, news aggregators (TechCrunch, VentureBeat, etc.). Prefer company blogs, official announcements, and technical posts from startup engineering teams.
"""

# Query 3: Research/Opinion (Trends, Analysis, Insights) - SIMPLIFIED
RESEARCH_OPINION_QUERY = """
Recent AI research and strategic insights for AI Product Managers (past 24-96 hours).

Areas of interest: Adoption trends, AI startup launches, funding announcements, competitive landscape analysis, technical breakthroughs with business impact, novel use cases, AI safety developments, regulatory changes, benchmark results, and any other strategic insights relevant to AI product development.

Focus on: ML research papers, data-driven analysis, case studies with results, market reports, strategic perspectives, technical deep-dives, industry analysis.

Avoid: Purely speculative opinion pieces, generic trend listicles, hype without substance, support guides, news aggregators (TechCrunch, VentureBeat, etc.), generic news coverage. Prefer original research, official announcements, and thoughtful analysis.
"""

# Export 3 specialized queries
THREE_AGENT_QUERIES = {
    "conversational_ai": CONVERSATIONAL_AI_QUERY,
    "general_ai": GENERAL_AI_QUERY,
    "research_opinion": RESEARCH_OPINION_QUERY,
}

# Legacy exports for backward compatibility (if needed)
ALL_INITIAL_QUERIES = [
    CONVERSATIONAL_AI_QUERY,
    GENERAL_AI_QUERY,
    RESEARCH_OPINION_QUERY,
]

