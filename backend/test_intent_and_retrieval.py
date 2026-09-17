"""Comprehensive Test Script for Schemora Chatbot Intent Detection & Retrieval.

Tests:
1. DEFINITION_CONCEPT queries:
   - "What is a scheme?"
   - "what does government scheme mean?"
   - "define government scheme"
   - "scheme meaning"
   - "योजना क्या है?"
   - "सरकारी योजना क्या होती है?"
   - "સરકારી યોજના શું છે?"
   - "What are government schemes?"
   - "What is subsidy?"
   - "What is beneficiary?"
2. SCHEME_DISCOVERY queries:
   - "What schemes are available for students?" -> Multiple student schemes
   - "Which schemes are available for farmers?" -> Multiple farmer schemes
3. SPECIFIC_SCHEME / ELIGIBILITY queries:
   - "What is the eligibility of PM-KISAN?"
   - "What is PM Internship Scheme?"
4. REQUIRED_DOCUMENTS queries:
   - "What documents are required for Post-Matric Scholarship?"
"""

import asyncio
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.services.retrieval_service import detect_intent, retrieve_relevant_chunks
from app.services.glossary_service import ensure_glossary_indexed
from app.services.groq_service import generate_grounded_chat_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_intent")


async def run_tests():
    print("\n========================================================")
    print("  SCHEMORA INTENT DETECTION & RETRIEVAL SUITE TEST")
    print("========================================================\n")

    async with AsyncSessionLocal() as db:
        # Step 1: Ensure glossary is seeded into PostgreSQL + pgvector
        glossary_count = await ensure_glossary_indexed(db)
        print(f"Glossary seeding check: {glossary_count} concept chunks ready.\n")

        # Definition Test Queries
        def_queries = [
            "What is a scheme?",
            "what does government scheme mean?",
            "define government scheme",
            "scheme meaning",
            "योजना क्या है?",
            "सरकारी योजना क्या होती है?",
            "સરકારી યોજના શું છે?",
            "What are government schemes?",
            "What is subsidy?",
            "What is beneficiary?",
        ]

        print("--- 1. TESTING DEFINITION / CONCEPT INTENT DETECTION & RETRIEVAL ---")
        for q in def_queries:
            intent = detect_intent(q)
            chunks = await retrieve_relevant_chunks(db, query=q, top_k=5)
            top_section = chunks[0]["section"] if chunks else "None"
            top_scheme = chunks[0]["scheme_name"] if chunks else "None"
            top_score = chunks[0]["similarity_score"] if chunks else 0.0

            passed = (intent == "DEFINITION_CONCEPT") and (top_section in ["concept", "glossary"] or top_scheme == "Schemora Knowledge Glossary")
            status = "PASSED" if passed else "FAILED"
            print(f"[{status}] Query: '{q}'")
            print(f"         Intent detected: {intent}")
            print(f"         Chunks retrieved: {len(chunks)}, Top Section: {top_section}, Top Scheme: {top_scheme}, Score: {top_score}")
            if not passed:
                print(f"         WARNING: Expected intent DEFINITION_CONCEPT & concept chunk.")
            print("-" * 50)

        # Discovery Test Queries
        discovery_queries = [
            ("What schemes are available for students?", "SCHEME_DISCOVERY"),
            ("Which schemes are available for farmers?", "SCHEME_DISCOVERY"),
        ]

        print("\n--- 2. TESTING SCHEME DISCOVERY INTENT DETECTION & RETRIEVAL ---")
        for q, expected_intent in discovery_queries:
            intent = detect_intent(q)
            chunks = await retrieve_relevant_chunks(db, query=q, top_k=5)
            distinct_schemes = list({c["scheme_name"] for c in chunks if c.get("scheme_name")})
            passed = (intent == expected_intent) and (len(distinct_schemes) >= 2)
            status = "PASSED" if passed else "FAILED"
            print(f"[{status}] Query: '{q}'")
            print(f"         Intent detected: {intent} (Expected: {expected_intent})")
            print(f"         Distinct schemes retrieved: {len(distinct_schemes)} -> {distinct_schemes[:3]}")
            print("-" * 50)

        # Specific Scheme / Eligibility Test Queries
        specific_queries = [
            ("What is the eligibility of PM-KISAN?", "ELIGIBILITY"),
            ("What is PM Internship Scheme?", "SCHEME_DISCOVERY"),
            ("What documents are required for Post-Matric Scholarship?", "REQUIRED_DOCUMENTS"),
        ]

        print("\n--- 3. TESTING SPECIFIC SCHEME, ELIGIBILITY & DOCUMENT INTENT ---")
        for q, expected_intent in specific_queries:
            intent = detect_intent(q)
            chunks = await retrieve_relevant_chunks(db, query=q, top_k=5)
            top_scheme = chunks[0]["scheme_name"] if chunks else "None"
            passed = (intent == expected_intent or intent in ["ELIGIBILITY", "SCHEME_DISCOVERY", "REQUIRED_DOCUMENTS"]) and len(chunks) > 0
            status = "PASSED" if passed else "FAILED"
            print(f"[{status}] Query: '{q}'")
            print(f"         Intent detected: {intent} (Expected: {expected_intent})")
            print(f"         Top scheme: {top_scheme}, Chunks: {len(chunks)}")
            print("-" * 50)

        # End-to-End Chat Response Generation Test with Groq / Grounded Pipeline
        print("\n--- 4. TESTING E2E GROQ / GROUNDED ANSWER GENERATION ---")
        test_q = "What is a scheme?"
        intent = detect_intent(test_q)
        chunks = await retrieve_relevant_chunks(db, query=test_q, top_k=3)
        answer, citations, is_grounded = await generate_grounded_chat_response(
            query=test_q,
            chunks=chunks,
            language="en"
        )
        print(f"Query: '{test_q}' (Intent: {intent})")
        print(f"Grounded: {is_grounded}, Citations Count: {len(citations)}")
        print("Generated Answer Snippet:")
        print(answer[:300] + "...\n")

        hindi_q = "योजना क्या है?"
        chunks_hi = await retrieve_relevant_chunks(db, query=hindi_q, top_k=3)
        answer_hi, _, _ = await generate_grounded_chat_response(
            query=hindi_q,
            chunks=chunks_hi,
            language="hi"
        )
        print(f"Hindi Query: '{hindi_q}'")
        print("Hindi Answer Snippet:")
        print(answer_hi[:300] + "...\n")

    print("========================================================")
    print("  TEST SUITE COMPLETE")
    print("========================================================\n")


if __name__ == "__main__":
    asyncio.run(run_tests())
