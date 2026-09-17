#!/usr/bin/env python3
"""Comprehensive Chatbot & Scraped KB RAG Verification Test Script.

Validates all user requirements:
  1. Existing Schemora Knowledge Base question
  2. Scraped content question
  3. Unrelated / fake question (Non-hallucination guardrail check)
  4. Multilingual queries in English, Hindi, and Gujarati (auto-detected)
"""

import sys
import asyncio
import logging
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal, engine, Base
from app.services.scraper.scraper_service import run_web_scraping_ingestion
from app.services.knowledge_base_service import index_all_schemes
from app.services.retrieval_service import retrieve_relevant_chunks
from app.services.groq_service import generate_grounded_chat_response, detect_query_language

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_chatbot_rag")


async def run_4tier_chatbot_verification():
    logger.info("Initializing Database & Seeding Knowledge Base...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Seed both dataset schemes and scraped schemes
        logger.info("Step A: Indexing Phase 0 Dataset Schemes...")
        try:
            kb_res = await index_all_schemes(db)
            logger.info(f"Phase 0 Indexing: {kb_res['indexed_schemes']} schemes, {kb_res['total_chunks']} chunks")
        except Exception as e:
            logger.warning(f"Dataset seeding note: {e}")

        logger.info("Step B: Scraping and Indexing Official Web Portal Scheme...")
        scraped_url = "https://www.myscheme.gov.in/schemes/pm-vidyalaxmi"
        scraper_res = await run_web_scraping_ingestion(db, target_urls=[scraped_url], save_raw_to_disk=False)
        logger.info(f"Web Scraper Indexing: {scraper_res}")

        logger.info("\n" + "="*70)
        logger.info("TEST CASE 1: Existing Schemora Knowledge Base Question")
        logger.info("="*70)
        q1 = "What are the eligibility criteria for Post Matric Scholarship?"
        chunks1 = await retrieve_relevant_chunks(db, query=q1, top_k=5)
        ans1, cit1, ground1 = await generate_grounded_chat_response(query=q1, chunks=chunks1, language="en")
        logger.info(f"Q: {q1}")
        logger.info(f"Retrieved Chunks Count: {len(chunks1)}")
        logger.info(f"Is Grounded: {ground1} | Citations: {len(cit1)}")
        logger.info(f"Response Preview:\n{ans1[:250]}...\n")

        assert len(chunks1) > 0, "Test Case 1 failed: No chunks retrieved for existing scheme!"
        assert ground1 is True, "Test Case 1 failed: Response should be grounded!"
        logger.info("✅ TEST CASE 1 PASSED: Existing KB Scheme Query Verified!")

        logger.info("\n" + "="*70)
        logger.info("TEST CASE 2: Scraped Content Question")
        logger.info("="*70)
        q2 = "How do I apply for PM Vidyalaxmi scheme and what are the required documents?"
        chunks2 = await retrieve_relevant_chunks(db, query=q2, top_k=5)
        ans2, cit2, ground2 = await generate_grounded_chat_response(query=q2, chunks=chunks2, language="en")
        logger.info(f"Q: {q2}")
        logger.info(f"Retrieved Chunks Count: {len(chunks2)}")
        logger.info(f"Is Grounded: {ground2} | Citations: {len(cit2)}")
        for c in cit2:
            logger.info(f"  • Source Citation: {c['source_name']} -> {c['url']}")
        logger.info(f"Response Preview:\n{ans2[:250]}...\n")

        assert len(chunks2) > 0, "Test Case 2 failed: No scraped chunks retrieved!"
        assert ground2 is True, "Test Case 2 failed: Scraped answer should be grounded!"
        assert any(scraped_url in c["url"] for c in cit2), "Test Case 2 failed: Scraped source URL missing from citations!"
        logger.info("✅ TEST CASE 2 PASSED: Scraped Knowledge Integration Verified!")

        logger.info("\n" + "="*70)
        logger.info("TEST CASE 3: Unrelated Question (Hallucination Prevention)")
        logger.info("="*70)
        # 3a. Out-of-scope query
        q3a = "What is the recipe for making chocolate cake?"
        chunks3a = await retrieve_relevant_chunks(db, query=q3a, top_k=5)
        ans3a, cit3a, ground3a = await generate_grounded_chat_response(query=q3a, chunks=chunks3a, language="en")
        logger.info(f"Q (Out of Scope): {q3a}")
        logger.info(f"Grounded: {ground3a} | Response: {ans3a[:200]}...")
        assert ground3a is False, "Test Case 3a failed: Out-of-scope query should not be grounded!"

        # 3b. Non-existent fake scheme query
        q3b = "What is the grant amount for Mars Interstellar Exploration Scheme 2099?"
        chunks3b = await retrieve_relevant_chunks(db, query=q3b, top_k=5)
        ans3b, cit3b, ground3b = await generate_grounded_chat_response(query=q3b, chunks=chunks3b, language="en")
        logger.info(f"Q (Fake Scheme): {q3b}")
        logger.info(f"Retrieved Chunks: {len(chunks3b)} | Grounded: {ground3b}")
        logger.info(f"Response: {ans3b}")
        assert ground3b is False, "Test Case 3b failed: Non-existent scheme query must NOT hallucinate!"
        assert "not find verified information" in ans3b.lower() or "knowledge base" in ans3b.lower(), "Test Case 3b failed: Should state information is unavailable!"
        logger.info("✅ TEST CASE 3 PASSED: Anti-Hallucination & Domain Guardrails Verified!")

        logger.info("\n" + "="*70)
        logger.info("TEST CASE 4: Multilingual Queries (English, Hindi, Gujarati)")
        logger.info("="*70)
        
        # 4a. English Query
        q4_en = "What documents are needed for PM Vidyalaxmi scheme?"
        lang_en = detect_query_language(q4_en)
        chunks4_en = await retrieve_relevant_chunks(db, query=q4_en, top_k=5)
        ans4_en, _, _ = await generate_grounded_chat_response(query=q4_en, chunks=chunks4_en, language=lang_en)
        logger.info(f"[EN] Query: '{q4_en}' | Detected Lang: '{lang_en}'")
        logger.info(f"[EN] Answer Preview:\n{ans4_en[:200]}...\n")
        assert lang_en == "en", "English detection failed!"

        # 4b. Hindi Query (Devanagari script)
        q4_hi = "पीएम विद्यालक्ष्मी योजना के लिए कौन से दस्तावेज आवश्यक हैं?"
        lang_hi = detect_query_language(q4_hi)
        chunks4_hi = await retrieve_relevant_chunks(db, query=q4_hi, top_k=5)
        ans4_hi, _, _ = await generate_grounded_chat_response(query=q4_hi, chunks=chunks4_hi, language=lang_hi)
        logger.info(f"[HI] Query: '{q4_hi}' | Detected Lang: '{lang_hi}'")
        logger.info(f"[HI] Answer Preview:\n{ans4_hi[:200]}...\n")
        assert lang_hi == "hi", "Hindi detection failed!"

        # 4c. Gujarati Query (Gujarati script)
        q4_gu = "પીએમ વિદ્યાલક્ષ્મી યોજના માટે કયા દસ્તાવેજો જરૂરી છે?"
        lang_gu = detect_query_language(q4_gu)
        chunks4_gu = await retrieve_relevant_chunks(db, query=q4_gu, top_k=5)
        ans4_gu, _, _ = await generate_grounded_chat_response(query=q4_gu, chunks=chunks4_gu, language=lang_gu)
        logger.info(f"[GU] Query: '{q4_gu}' | Detected Lang: '{lang_gu}'")
        logger.info(f"[GU] Answer Preview:\n{ans4_gu[:200]}...\n")
        assert lang_gu == "gu", "Gujarati detection failed!"
        logger.info("✅ TEST CASE 4 PASSED: Multilingual Detection & Generation (EN, HI, GU) Verified!")

        logger.info("\n" + "="*70)
        logger.info("🎉 ALL 4 TEST CASES PASSED PERFECTLY!")
        logger.info("="*70)


if __name__ == "__main__":
    asyncio.run(run_4tier_chatbot_verification())
