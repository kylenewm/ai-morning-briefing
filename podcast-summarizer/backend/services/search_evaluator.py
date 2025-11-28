import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from ..config import settings
from ..ingestion.search_providers.base import SearchResult
from ..ingestion.search_providers.exa_provider import ExaProvider
from ..ingestion.search_providers.perplexity_provider import PerplexityProvider

logger = logging.getLogger(__name__)


# Default prompts
EXA_SEARCH_QUERY_DEFAULT = (
    "AI product updates conversational AI voice-to-voice models foundation model releases "
    "enterprise deployments technical breakthroughs agent frameworks last 24-48 hours"
)

EXA_RESEARCH_INSTRUCTIONS_DEFAULT = (
    "Find recent conversational AI and major AI product updates from the last 24-48 hours relevant to AI Product Managers.\n\n"
    "**Priority Voice AI Topics:**\n\n"
    "- Voice-to-voice models (OpenAI Realtime, Google Gemini audio, Deepgram Aura)\n\n"
    "- Conversational AI platforms (LangGraph, LangChain, Vapi, Retell, ElevenLabs)\n\n"
    "- Voice infrastructure (Krisp, LiveKit, Vocode, turn-taking improvements)\n\n"
    "- Multimodal RAG systems and vector databases (Milvus, Pinecone, Weaviate)\n\n"
    "- Voice agent testing and evaluation (Hamming, Roark, simulation tools)\n\n"
    "**AI Product & Infrastructure:**\n\n"
    "- Foundation model releases (GPT, Claude, Gemini, Llama, Mistral)\n\n"
    "- AI agent frameworks and autonomous systems\n\n"
    "- Model pricing, API updates, and capability improvements\n\n"
    "- Open source AI alternatives and community tools\n\n"
    "- RAG and retrieval system improvements\n\n"
    "**AI Product Management Tools:**\n\n"
    "- Observability platforms (LangSmith, LangFuse, Helicone)\n\n"
    "- A/B testing and evaluation frameworks\n\n"
    "- Cost optimization (prompt caching, inference optimization, distillation)\n\n"
    "- Prompt management and versioning tools\n\n"
    "- AI product analytics\n\n"
    "**Enterprise & Strategic:**\n\n"
    "- Enterprise AI deployments and customer wins\n\n"
    "- AI partnerships and acquisitions\n\n"
    "- Vertical-specific AI applications (healthcare, finance, legal, customer service)\n\n"
    "- Compliance updates (HIPAA, SOC2, AI regulations)\n\n"
    "- Build vs buy case studies\n\n"
    "**Technical Breakthroughs:**\n\n"
    "- Real-time inference and streaming improvements\n\n"
    "- Context window expansions\n\n"
    "- Latency and cost reductions\n\n"
    "- Novel architectures with immediate product applications\n\n"
    "- Benchmarks and leaderboard updates\n\n"
    "**Broader AI Breakthroughs & Emerging Trends:**\n\n"
    "- Novel AI capabilities or applications not yet mainstream\n\n"
    "- Cross-domain innovations (AI + robotics, AI + biology, AI + hardware)\n\n"
    "- Unexpected use cases or market applications\n\n"
    "- Major industry paradigm shifts\n\n"
    "- New AI modalities or interaction patterns\n\n"
    "- Breakthrough benchmarks or capability demonstrations\n\n"
    "- Consumer AI products with novel approaches\n\n"
    "- Hardware innovations enabling new AI applications\n\n"
    "- Data innovations (new datasets, synthetic data breakthroughs)\n\n"
    "**Competitive Intelligence:**\n\n"
    "- Product launches from competitors in voice AI and conversational AI space\n\n"
    "- Customer migration stories and market shifts\n\n"
    "- Startup funding in relevant categories\n\n"
    "**Prioritize:**\n\n"
    "- Original announcements and primary sources (company blogs, official releases)\n\n"
    "- Technical analysis with actionable insights\n\n"
    "- Enterprise case studies and deployment stories\n\n"
    "- Quantitative benchmarks and performance data\n\n"
    "- In-depth technical documentation and changelogs\n\n"
    "**De-prioritize (but don't exclude):**\n\n"
    "- Purely theoretical research without near-term product applications\n\n"
    "- Introductory tutorials and \"getting started\" guides\n\n"
    "- Hot takes and opinion pieces without new data or announcements\n\n"
    "- Speculative AI safety discussions without regulatory or product implications"
)

PPLX_QUERY_DEFAULT = (
    "Recent AI product updates (24-48h) for AI Product Managers:\n"
    "Voice AI: OpenAI Realtime, Gemini audio, Deepgram, LangGraph, conversational platforms\n"
    "Foundation models: GPT, Claude, Gemini, Llama releases and pricing updates\n"
    "AI infrastructure: Agent frameworks, RAG systems, vector databases, observability tools\n"
    "Enterprise: Deployments, partnerships, vertical AI applications, compliance updates\n"
    "Breakthroughs: New capabilities, benchmarks, hardware innovations, unexpected use cases\n"
    "Focus on announcements, case studies, technical improvements, and primary sources."
)


def _compute_recency_score(published_date: Optional[str]) -> Optional[float]:
    if not published_date:
        return None
    try:
        # Expect YYYY-MM-DD
        dt = datetime.strptime(published_date[:10], "%Y-%m-%d")
        hours = (datetime.utcnow() - dt).total_seconds() / 3600.0
        if hours <= 24:
            return 1.0
        if hours <= 48:
            return 0.8
        if hours <= 24 * 7:
            return 0.6
        return 0.3
    except Exception:
        return None


def condense_snippet(text: str, max_chars: int = 1000, min_chars: int = 500) -> str:
    if not text:
        return ""
    # Normalize whitespace
    s = " ".join(text.split())
    # Split into naive sentences
    import re
    sentences = re.split(r'(?<=[.!?])\s+', s)
    selected: List[str] = []
    total = 0
    # Pick sentences in order until within bounds
    for sent in sentences:
        if not sent or len(sent) < 20:
            continue
        if total + len(sent) + 1 > max_chars:
            if total >= min_chars:
                break
            # take partial tail if still short
            remaining = max_chars - total - 1
            if remaining > 60:
                selected.append(sent[:remaining])
                total += len(selected[-1]) + 1
            break
        selected.append(sent)
        total += len(sent) + 1
    condensed = " ".join(selected).strip()
    # If we didn't get enough, fall back to leading slice
    if len(condensed) < min_chars:
        return s[:max_chars]
    return condensed[:max_chars]


async def fetch_main_text(url: str, timeout: float = 8.0) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}) as client:
            r = await client.get(url, follow_redirects=True)
            r.raise_for_status()
            html = r.text
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        texts = [t.get_text(separator=" ", strip=True) for t in soup.find_all(["article", "main", "section", "p", "h1", "h2", "h3"])]
        text = " ".join([t for t in texts if len(t) > 40])
        return " ".join(text.split())
    except Exception:
        return ""


async def summarize_to_brief(client: AsyncOpenAI, title: str, text: str, target_words: int = 150) -> str:
    if not text:
        return ""
    prompt = (
        f"Summarize the article for an AI Product Manager in {target_words} words.\n"
        f"Focus on concrete product changes, capabilities, model details, benchmarks, and enterprise implications.\n"
        f"Title: {title}\n\nArticle:\n{text[:8000]}"
    )
    try:
        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return ""


async def _llm_score_batch(
    items: List[SearchResult],
    provider_name: str,
    query_rubric: str,
    client: AsyncOpenAI,
) -> List[Tuple[float, Optional[str]]]:
    # Return list of (relevance_score, recency_label_if_needed)
    compact: List[Dict[str, Any]] = []
    for idx, it in enumerate(items):
        compact.append({
            "index": idx,
            "title": it.title,
            "snippet": condense_snippet(it.snippet or "", max_chars=1000, min_chars=500),
            "published_date": it.published_date or ""
        })

    system = (
        "You are scoring news results for an AI Product Manager."
    )
    user = (
        f"Scoring rubric (importance):\n{query_rubric}\n\n"
        "For each item, produce a JSON object with: index, relevance (0.0-1.0).\n"
        "If published_date is missing, also provide recency_label as one of: recent, somewhat, stale.\n"
        "Return only JSON in the form: {\"scores\": [{\"index\":0,\"relevance\":0.85,\"recency_label\":\"recent\"}, ...]}\n\n"
        f"Items:\n{json.dumps(compact)}"
    )

    try:
        resp = await client.chat.completions.create(
            model="gpt-4.1-mini",  # USER PREFERENCE: Always use 4.1-mini
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = resp.choices[0].message.content
        data = json.loads(content) if content else {"scores": []}
        by_index: Dict[int, Dict[str, Any]] = {s.get("index"): s for s in data.get("scores", []) if isinstance(s, dict)}
        out: List[Tuple[float, Optional[str]]] = []
        for i in range(len(items)):
            s = by_index.get(i, {})
            rel = float(s.get("relevance", 0.0)) if isinstance(s.get("relevance", 0.0), (int, float)) else 0.0
            label = s.get("recency_label") if isinstance(s.get("recency_label"), str) else None
            out.append((max(0.0, min(1.0, rel)), label))
        return out
    except Exception as e:
        logger.warning(f"LLM scoring failed for {provider_name}: {e}")
        return [(0.0, None) for _ in items]


async def evaluate_search(
    query: Optional[str],
    providers: List[str],
    limit: int,
    exa_modes: List[str],
    seed_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    logger.info(f"📋 evaluate_search called: providers={providers}, exa_modes={exa_modes}, limit={limit}")
    
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    tasks = []
    results_by_provider: Dict[str, Any] = {}

    providers = [p.strip().lower() for p in providers if p.strip()]
    logger.info(f"📋 Cleaned providers: {providers}")
    
    if "exa" in providers:
        logger.info(f"🚀 Creating ExaProvider...")
        exa = ExaProvider()
        for m in exa_modes:
            mode = m.strip().lower()
            if not mode:
                continue
            mode_query = query
            if not mode_query:
                if mode == "search":
                    mode_query = EXA_SEARCH_QUERY_DEFAULT
                elif mode == "research":
                    mode_query = EXA_RESEARCH_INSTRUCTIONS_DEFAULT
                elif mode == "find_similar":
                    mode_query = EXA_SEARCH_QUERY_DEFAULT
            tasks.append(("exa", mode, exa.search(mode_query or "", limit=limit, mode=mode, seed_urls=seed_urls)))

    if "perplexity" in providers:
        pplx = PerplexityProvider()
        pplx_query = query or PPLX_QUERY_DEFAULT
        tasks.append(("perplexity", None, pplx.search(pplx_query, limit=limit)))

    # Run in parallel
    async def _run_all():
        coros = [t[2] for t in tasks]
        return await asyncio.gather(*coros, return_exceptions=True)

    gathered = await _run_all()

    # Attach results
    for (prov, mode, _), res in zip(tasks, gathered):
        if isinstance(res, Exception):
            logger.warning(f"Provider {prov} mode {mode} failed: {res}")
            continue
        if prov == "exa":
            results_by_provider.setdefault("exa", {})[mode or "search"] = res
        else:
            results_by_provider.setdefault("perplexity", res)

    # Enrich text per item (fetch+summarize only when needed)
    async def enrich_items(items: List[SearchResult]) -> None:
        if not items:
            return
        sem = asyncio.Semaphore(5)

        async def process_item(item: SearchResult) -> None:
            # Decide if we need fetching
            snippet = (item.snippet or "").strip()
            needs_fetch = (len(snippet) < 200) or any(x in snippet.lower() for x in ["read more", "learn more", "subscribe", "click here"]) 
            if needs_fetch and client:
                text = await fetch_main_text(item.url)
                if text and len(text) > 400:
                    brief = await summarize_to_brief(client, item.title, text, target_words=150)
                    if brief:
                        item.snippet = brief
                        return
                # fallback to whatever we got
                item.snippet = text[:1000] if text else snippet
            else:
                # Condense existing snippet lightly
                item.snippet = condense_snippet(snippet, max_chars=1000, min_chars=500) if snippet else snippet

        async def guarded(item: SearchResult) -> None:
            async with sem:
                await process_item(item)

        await asyncio.gather(*(guarded(it) for it in items))

    # Enrich Exa groups
    exa_group = results_by_provider.get("exa", {})
    for mode, items in exa_group.items():
        await enrich_items(items)

    # Enrich Perplexity items
    pplx_items: List[SearchResult] = results_by_provider.get("perplexity", [])
    await enrich_items(pplx_items)

    # Score per provider/mode
    combined_ranked: List[Dict[str, Any]] = []
    if client:
        # Exa modes
        for mode, items in exa_group.items():
            rubric = EXA_RESEARCH_INSTRUCTIONS_DEFAULT if mode == "research" else EXA_SEARCH_QUERY_DEFAULT
            scores = await _llm_score_batch(items, f"exa:{mode}", rubric, client)
            for item, (rel, label) in zip(items, scores):
                rec = _compute_recency_score(item.published_date)
                if rec is None:
                    rec = 1.0 if (label or "").lower() == "recent" else 0.6 if (label or "").lower() == "somewhat" else 0.3 if (label or "").lower() == "stale" else 0.6
                combined = 0.7 * rel + 0.3 * rec
                d = item.__dict__.copy()
                d.update({
                    "relevance_score": round(rel, 3),
                    "recency_score": round(rec, 3),
                    "combined_score": round(combined, 3),
                })
                exa_group[mode] = items
                combined_ranked.append(d)

        # Perplexity
        if pplx_items:
            scores = await _llm_score_batch(pplx_items, "perplexity", PPLX_QUERY_DEFAULT, client)
            for item, (rel, label) in zip(pplx_items, scores):
                rec = _compute_recency_score(item.published_date)
                if rec is None:
                    rec = 1.0 if (label or "").lower() == "recent" else 0.6 if (label or "").lower() == "somewhat" else 0.3 if (label or "").lower() == "stale" else 0.6
                combined = 0.7 * rel + 0.3 * rec
                d = item.__dict__.copy()
                d.update({
                    "relevance_score": round(rel, 3),
                    "recency_score": round(rec, 3),
                    "combined_score": round(combined, 3),
                })
                combined_ranked.append(d)

    # Sort combined
    combined_ranked.sort(key=lambda x: x.get("combined_score", 0), reverse=True)

    return {
        "providers": results_by_provider,
        "combined_ranked": combined_ranked,
    }


