#!/usr/bin/env python3
"""Universal Multilingual RAG Layer Verification Script.

Tests all required user scenarios:
  1. English query ('en')
  2. Hindi query ('hi')
  3. Gujarati query ('gu')
  4. Additional supported language 1: Marathi ('mr')
  5. Additional supported language 2: Bengali ('bn')
  6. Scraped scheme content query in non-English script (e.g., Gujarati query for PM Vidyalaxmi)
  7. Unrelated / Non-existent scheme query (Anti-hallucination handling in user's script)
"""

import sys
import asyncio
import logging
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal, engine, Base
from app.services.language_service import language_registry
from app.services.scraper.scraper_service import run_web_scraping_ingestion
from app.services.knowledge_base_service import index_all_schemes
from app.services.retrieval_service import retrieve_relevant_chunks
from app.services.groq_service import generate_grounded_chat_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_multilingual_rag")


async def run_multilingual_verification():
    logger.info("Initializing Database & Seeding Knowledge Base...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Seed dataset & scraped content
        try:
            await index_all_schemes(db)
        except Exception as e:
            logger.warning(f"Dataset index note: {e}")

        scraped_url = "https://www.myscheme.gov.in/schemes/pm-vidyalaxmi"
        await run_web_scraping_ingestion(db, target_urls=[scraped_url], save_raw_to_disk=False)

        test_scenarios = [
            {
                "id": "1. English Query",
                "lang_code": "en",
                "query": "What are the required documents for Post Matric Scholarship?",
                "expect_grounded": True,
            },
            {
                "id": "2. Hindi Query",
                "lang_code": "hi",
                "query": "पोस्ट मैट्रिक छात्रवृत्ति के लिए कौन से दस्तावेज आवश्यक हैं?",
                "expect_grounded": True,
            },
            {
                "id": "3. Gujarati Query",
                "lang_code": "gu",
                "query": "પોસ્ટ મેટ્રિક શિષ્યવૃત્તિ માટે કયા દસ્તાવેજો જરૂરી છે?",
                "expect_grounded": True,
            },
            {
                "id": "4. Additional Language 1 — Marathi",
                "lang_code": "mr",
                "query": "पोस्ट मॅट्रिक शिष्यवृत्तीसाठी कोणती कागदपत्रे आवश्यक आहेत?",
                "expect_grounded": True,
            },
            {
                "id": "5. Additional Language 2 — Bengali",
                "lang_code": "bn",
                "query": "পোস্ট মেট্রিক স্কলারশিপের জন্য কী কী নথি প্রয়োজন?",
                "expect_grounded": True,
            },
            {
                "id": "6. Scraped Content Query (Gujarati)",
                "lang_code": "gu",
                "query": "પીએમ વિદ્યાલક્ષ્મી યોજના માટે કયા દસ્તાવેજો જરૂરી છે અને કેવી રીતે અરજી કરવી?",
                "expect_grounded": True,
                "check_citation_url": scraped_url,
            },
            {
                "id": "7. Unrelated Non-Existent Scheme Query (Hindi anti-hallucination)",
                "lang_code": "hi",
                "query": "मंगल ग्रह 2099 योजना के लिए कितना फंड मिलेगा?",
                "expect_grounded": False,
            },
        ]

        logger.info("\n" + "="*80)
        logger.info("EXECUTING UNIVERSAL MULTILINGUAL RAG VERIFICATION (7 SCENARIOS)")
        logger.info("="*80 + "\n")

        all_passed = True
        for idx, scenario in enumerate(test_scenarios, 1):
            query = scenario["query"]
            detected_spec = language_registry.detect_language(query, scenario["lang_code"])

            logger.info(f"--- Scenario {scenario['id']} ---")
            logger.info(f"Query: '{query}'")
            logger.info(f"Detected Spec: Code='{detected_spec.code}' ({detected_spec.name} / {detected_spec.native_name})")

            chunks = await retrieve_relevant_chunks(db, query=query, top_k=5)
            ans, citations, grounded = await generate_grounded_chat_response(
                query=query,
                chunks=chunks,
                language=detected_spec.code,
            )

            logger.info(f"Retrieved Chunks Count: {len(chunks)}")
            logger.info(f"Is Grounded: {grounded} | Citations Count: {len(citations)}")
            logger.info(f"Generated Response Snippet:\n{ans[:250]}...\n")

            # Assertions
            if scenario["expect_grounded"]:
                if not grounded:
                    logger.error(f"❌ Scenario {scenario['id']} failed: Expected grounded answer!")
                    all_passed = False
                if scenario.get("check_citation_url"):
                    if not any(scenario["check_citation_url"] in c["url"] for c in citations):
                        logger.error(f"❌ Scenario {scenario['id']} failed: Scraped URL missing from citations!")
                        all_passed = False
            else:
                if grounded:
                    logger.error(f"❌ Scenario {scenario['id']} failed: Unrelated query should NOT be grounded!")
                    all_passed = False

        if all_passed:
            logger.info("\n==========================================================")
            logger.info("🎉 SUCCESS: ALL 7 UNIVERSAL MULTILINGUAL RAG SCENARIOS VERIFIED PERFECTLY!")
            logger.info("==========================================================")


if __name__ == "__main__":
    asyncio.run(run_multilingual_verification())
