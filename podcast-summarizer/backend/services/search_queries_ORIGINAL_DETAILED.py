"""
ORIGINAL DETAILED Search Query Library - ARCHIVED for Deep Search

These are the original, highly detailed queries before simplification.
Stored for potential future use with deep search / research modes.

Date Archived: November 9, 2025
Reason: Too verbose for initial searches, but may be useful for targeted deep search later
"""

# ORIGINAL Query 1: Conversational AI (Voice + Agents)
CONVERSATIONAL_AI_QUERY_DETAILED = """
Recent conversational AI, voice AI, and agent framework updates (past 24-96 hours) for AI Product Managers.

**Priority Topics:**
- Voice-to-voice models: OpenAI Realtime API, Google Gemini Live, Deepgram Aura
- Conversational AI platforms: LangGraph, LangChain, Vapi, Retell, ElevenLabs
- Voice infrastructure: Krisp, LiveKit, Vocode, turn-taking, interruption handling
- AI agent frameworks: LangGraph, LangChain, CrewAI, AutoGPT, Agent Protocol
- Agent orchestration: Multi-agent systems, tool calling, memory management
- Voice agent testing: Hamming, Roark, simulation tools

**What to prioritize:**
- Product announcements and official releases
- API updates and pricing changes
- Technical benchmarks and performance data
- Enterprise deployments and case studies
- Framework releases and breaking changes
- New capabilities and features

**What to avoid:**
- Generic tutorials and getting started guides
- Opinion pieces without new data or announcements
- Purely theoretical discussions
- Basic tutorials on building first agent
"""

# ORIGINAL Query 2: General AI (Models + Infrastructure + Enterprise)
GENERAL_AI_QUERY_DETAILED = """
Recent foundation model, AI infrastructure, and enterprise AI updates (past 24-96 hours) for AI Product Managers.

**Priority Topics - Foundation Models:**
- Model releases: GPT-4, GPT-4o, Claude 3.5, Gemini 2.0, Llama 3, Mistral
- API updates: New endpoints, parameters, capabilities
- Pricing changes: Cost reductions, new tiers, volume discounts
- Performance improvements: Latency, throughput, context windows
- Capability expansions: Multimodal, function calling, JSON mode

**Priority Topics - Infrastructure:**
- RAG systems: Retrieval improvements, hybrid search, reranking
- Vector databases: Milvus, Pinecone, Weaviate, Qdrant, Chroma
- Observability: LangSmith, LangFuse, Helicone, Weights & Biases
- Prompt management: Version control, A/B testing, optimization
- Cost optimization: Caching, inference acceleration, model distillation

**Priority Topics - Enterprise:**
- Enterprise deployments and customer wins
- Partnerships and integrations
- Vertical AI applications (healthcare, finance, legal, customer service)
- Compliance updates (HIPAA, SOC2, GDPR, AI regulations)

**What to prioritize:**
- Official announcements from OpenAI, Anthropic, Google, Meta
- Product launches and feature releases
- Technical documentation and API changelogs
- Benchmark results and performance comparisons
- Pricing updates and enterprise packaging
- Integration announcements

**What to avoid:**
- Speculative rumors without official confirmation
- Generic model comparison articles without new data
- Introductory explainers on how LLMs work
- Basic setup tutorials
"""

# ORIGINAL Query 3: Research/Opinion (Trends, Analysis, Insights)
RESEARCH_OPINION_QUERY_DETAILED = """
Recent AI trends, analysis, and strategic insights (past 24-96 hours) for AI Product Managers.

**Priority Topics - Market Analysis:**
- AI adoption trends and patterns
- Customer migration stories and market shifts
- Competitive dynamics and positioning
- Build vs buy decision frameworks
- Success stories and lessons learned

**Priority Topics - Strategic Insights:**
- Technical breakthroughs with business implications
- Novel use cases and unexpected applications
- Industry paradigm shifts
- Cross-domain innovations (AI + robotics, AI + biology, AI + hardware)
- Emerging AI modalities and interaction patterns

**Priority Topics - Competitive Intelligence:**
- Startup launches and funding announcements
- Product launches from new entrants
- Feature comparisons and differentiation
- Market analysis with quantitative data
- Customer wins and case studies

**Priority Topics - Technical Analysis:**
- Inference improvements with product impact
- Context window expansions and applications
- Cost reduction strategies
- Benchmark results and leaderboard updates
- Open source releases with practical applications

**What to prioritize:**
- Analysis pieces with new data or insights
- Case studies with quantitative results
- Market reports from reputable sources
- Technical deep-dives with actionable takeaways
- Strategic perspectives from industry leaders

**What to avoid:**
- Purely speculative opinion pieces
- Generic AI trend listicles
- Introductory explainers without new angles
- Hype pieces without substance
- Theoretical discussions without practical relevance
"""

# Export original queries
ORIGINAL_DETAILED_QUERIES = {
    "conversational_ai": CONVERSATIONAL_AI_QUERY_DETAILED,
    "general_ai": GENERAL_AI_QUERY_DETAILED,
    "research_opinion": RESEARCH_OPINION_QUERY_DETAILED,
}

ALL_ORIGINAL_DETAILED_QUERIES = [
    CONVERSATIONAL_AI_QUERY_DETAILED,
    GENERAL_AI_QUERY_DETAILED,
    RESEARCH_OPINION_QUERY_DETAILED,
]

