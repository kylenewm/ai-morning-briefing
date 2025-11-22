"""Quick test to check podcast formatting"""
import asyncio
from podcast-summarizer.backend.ingestion.assemblyai_transcriber import AssemblyAITranscriber
from dotenv import load_dotenv

load_dotenv()

async def test():
    transcriber = AssemblyAITranscriber()
    
    # Test with a short fake transcript
    test_transcript = """
    So today we're talking about context windows in AI models. One of the biggest challenges 
    we're seeing is what we call context rot. Essentially, as you make the context window 
    longer and longer, the model starts to lose track of what's important. It gets distracted
    by seemingly relevant but actually irrelevant information.
    
    We tested this across 17 different models, and what we found was really interesting.
    The needle in a haystack benchmark doesn't really capture the problem, because it's 
    mostly testing lexical matching, not actual reasoning.
    
    From a product perspective, developers just don't trust outputs beyond certain limits.
    We're hearing from customers that they won't use more than 40,000 tokens because the 
    quality degrades too much.
    """
    
    summary = await transcriber.get_transcript_summary(
        test_transcript,
        "Context Rot Test Episode",
        "https://test.com"
    )
    
    print("\n" + "="*80)
    print("GENERATED SUMMARY:")
    print("="*80)
    print(summary)
    print("="*80)
    
    # Check format
    has_bullets = "-" in summary and "\n-" in summary
    has_headings = "###" in summary
    
    print(f"\n✅ Has headings: {has_headings}")
    print(f"❌ Has bullets: {has_bullets}")
    print(f"{'✅ PARAGRAPHS!' if not has_bullets else '❌ STILL BULLETS'}")

asyncio.run(test())
