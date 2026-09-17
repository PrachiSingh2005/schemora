import asyncio
import logging
import sys
from pathlib import Path

# Setup path and logging
sys.path.insert(0, str(Path(__file__).resolve().parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("schemora.reindex_test")

from app.core.database import async_session_maker
from app.services.knowledge_base_service import index_all_schemes, get_knowledge_base_status
from app.services.retrieval_service import retrieve_relevant_chunks
from app.services.groq_service import evaluate_chunk_relevance

TEST_QUERIES = [
    ("Broad Scheme Query", "What schemes are available?"),
    ("Scholarship Query", "student scholarships"),
    ("Farmer Query", "schemes for farmers"),
    ("Women-Focused Query", "women government schemes"),
    ("Hindi Query", "गरीब लोगों के लिए योजनाएं"),
    ("Gujarati Query", "વિદ્યાર્થીઓ માટે સરકારી યોજનાઓ"),
    ("Specific Scheme Query", "What is PM Internship Scheme?"),
    ("Eligibility Query", "Am I eligible if my family income is below 2.5 lakh?"),
    ("Document Query", "What documents are required for PM scholarship?"),
    ("Application Process Query", "How to apply for OBC post matric scholarship?"),
]

async def main():
    logger.info("=== STEP 1: Re-indexing Full dataset into PostgreSQL / pgvector ===")
    async with async_session_maker() as db:
        result = await index_all_schemes(db)
        kb_status = await get_knowledge_base_status(db)

        print("\n" + "="*70)
        print("SCHEMORA KNOWLEDGE BASE INGESTION SUMMARY REPORT")
        print("="*70)
        print(f"Total Schemes Discovered  : {result['total_schemes']}")
        print(f"Total Schemes Indexed     : {result['indexed_schemes']}")
        print(f"Failed / Duplicate Schemes: {len(result['failed_schemes'])}")
        print(f"Total Chunks Created      : {result['total_chunks']}")
        print(f"Semantic Embeddings Count : {result['semantic_chunks']}")
        print(f"Embedding Model Used      : SentenceTransformers / TF-IDF Vector Hybrid")
        print(f"Database / Vector Tables  : PostgreSQL / SQLite (knowledge_documents, knowledge_chunks)")
        print("="*70 + "\n")

        logger.info("=== STEP 2: Diagnostic Retrieval Testing across 10 Query Categories ===")
        all_passed = True
        test_results = []

        for category, query in TEST_QUERIES:
            print(f"\n--- Testing Category: [{category}] ---")
            print(f"Query: \"{query}\"")
            chunks = await retrieve_relevant_chunks(db, query=query, top_k=6)
            distinct_schemes = list({c['scheme_name'] for c in chunks})
            is_relevant, confidence = evaluate_chunk_relevance(query, chunks)

            print(f"Chunks Retrieved : {len(chunks)}")
            print(f"Distinct Schemes : {len(distinct_schemes)} -> {distinct_schemes[:4]}")
            print(f"Top Score        : {chunks[0]['similarity_score'] if chunks else 0.0}")
            print(f"Evaluated Status : {'PASS' if is_relevant and len(chunks) > 0 else 'FAIL'} (confidence={confidence})")

            if not chunks:
                all_passed = False

            test_results.append({
                "category": category,
                "query": query,
                "chunks_count": len(chunks),
                "distinct_schemes_count": len(distinct_schemes),
                "top_scheme": distinct_schemes[0] if distinct_schemes else "None",
                "top_score": chunks[0]['similarity_score'] if chunks else 0.0,
                "passed": len(chunks) > 0 and (len(distinct_schemes) >= 3 if "Broad" in category or "Scholarship" in category or "Farmer" in category or "Women" in category or "Hindi" in category or "Gujarati" in category else len(chunks) >= 1)
            })

        print("\n" + "="*70)
        print("RETRIEVAL DIAGNOSTIC RESULTS MATRIX")
        print("="*70)
        for tr in test_results:
            status_str = "SUCCESS" if tr["passed"] else "FAIL"
            print(f"[{status_str:7s}] {tr['category']:26s} | Chunks: {tr['chunks_count']} | Schemes: {tr['distinct_schemes_count']} | Top: {tr['top_scheme'][:30]}")
        print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
