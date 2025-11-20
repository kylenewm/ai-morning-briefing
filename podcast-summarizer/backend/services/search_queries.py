"""
Search Query Library for AI Newsletter Agent

Simplified, focused queries for Exa semantic search.
Uses 3 specialized queries for targeted coverage:
1. Conversational AI (voice, agents, real-time systems)
2. General AI (models, infrastructure, enterprise)
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

# Query 2: General AI (Models + Infrastructure + Enterprise) - SIMPLIFIED
GENERAL_AI_QUERY = """
Recent foundation model and AI infrastructure updates for AI Product Managers (past 24-96 hours).

Areas of interest: Large language model releases from major AI labs or open source projects, RAG systems, vector databases, observability platforms, prompt engineering tools, fine-tuning platforms, inference optimization, model serving infrastructure, LLM orchestration frameworks, evaluation and testing frameworks, and any other relevant AI infrastructure.

Focus on: Model releases and other key improvements that could lead to someone wanting to leverage for their own use case or is just large enough news to be noteworthy. Technical blog posts from companies building in this space.

Avoid: Generic explainers, introductory tutorials, support guides, news aggregators (TechCrunch, VentureBeat, etc.), generic news coverage. Prefer original sources and official announcements.
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

