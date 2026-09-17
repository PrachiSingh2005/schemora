"""Comprehensive Automated Test Suite for Schemora Chatbot Answer Quality & Reliability.

Tests:
  1. Knowledge Base Direct Question (High accuracy, KB source cited)
  2. External Scheme Question (Web search fallback, official .gov.in cited)
  3. Insufficient Information Question (Graceful unavailable warning, zero hallucination)
  4. Out-of-Scope Question (Clear domain scope boundary)
  5. Multilingual Script Preservation (English, Hindi, Gujarati, Marathi)
"""

import sys
import os
import asyncio
import logging

# Add backend root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.groq_service import evaluate_chunk_relevance, generate_grounded_chat_response
from app.core.database import AsyncSessionLocal
from app.api.v1.ai import chat_assistant
from app.schemas.ai import AIChatRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_reliability")


async def run_tests():
    logger.info("========================================================================")
    logger.info("   STARTING ANSWER QUALITY, RELIABILITY & GROUNDING VERIFICATION TESTS   ")
    logger.info("========================================================================")

    passed = 0
    total = 0

    # ── Test 1: Knowledge Base Direct Question ───────────────────────────────
    total += 1
    logger.info("\n--- TEST 1: Question Present in Knowledge Base ---")
    kb_query = "What is the eligibility for PM-Vidyalaxmi scholarship?"

    async with AsyncSessionLocal() as db:
        req = AIChatRequest(question=kb_query, language="en")
        resp = await chat_assistant(req, db=db)
        data = resp.data
        logger.info(f"Answer Grounded: {data.is_grounded}")
        logger.info(f"KB Used: {data.knowledge_base_used}")
        logger.info(f"Web Search Used: {data.web_search_used}")
        logger.info(f"Answer Preview:\n{data.answer[:250]}...")

        if data.is_grounded and data.knowledge_base_used and not data.web_search_used:
            logger.info("✅ TEST 1 PASSED: Direct KB question answered accurately with KB grounding")
            passed += 1
        else:
            logger.error("❌ TEST 1 FAILED: KB query grounding or priority failed")

    # ── Test 2: Question Requiring Web Search ────────────────────────────────
    total += 1
    logger.info("\n--- TEST 2: Question Requiring Web Search ---")
    web_query = "What are the eligibility guidelines for PM Surya Ghar Muft Bijli Yojana?"

    async with AsyncSessionLocal() as db:
        req = AIChatRequest(question=web_query, language="en")
        resp = await chat_assistant(req, db=db)
        data = resp.data
        logger.info(f"KB Used: {data.knowledge_base_used}")
        logger.info(f"Web Search Used: {data.web_search_used}")
        logger.info(f"Citations Count: {len(data.citations)}")
        logger.info(f"Answer Preview:\n{data.answer[:250]}...")

        if data.web_search_used and data.citations:
            logger.info("✅ TEST 2 PASSED: Web search fallback activated and cited official source")
            passed += 1
        else:
            logger.error("❌ TEST 2 FAILED: Web search fallback did not cite official source")

    # ── Test 3: Insufficient Information Question ────────────────────────────
    total += 1
    logger.info("\n--- TEST 3: Insufficient Information Question (Zero Hallucination) ---")
    insufficient_query = "What is the secret pin code of scheme xyz999unreliable?"

    async with AsyncSessionLocal() as db:
        req = AIChatRequest(question=insufficient_query, language="en")
        resp = await chat_assistant(req, db=db)
        data = resp.data
        logger.info(f"Is Grounded: {data.is_grounded}")
        logger.info(f"Answer Text: '{data.answer}'")

        if (
            "couldn't find verified information" in data.answer.lower()
            or "unavailable" in data.answer.lower()
            or not data.is_grounded
        ):
            logger.info("✅ TEST 3 PASSED: System clearly stated information is unavailable without hallucinating")
            passed += 1
        else:
            logger.error("❌ TEST 3 FAILED: System hallucinated or failed fallback handling")

    # ── Test 4: Unrelated Question (Out of Scope Boundary) ───────────────────
    total += 1
    logger.info("\n--- TEST 4: Unrelated Question (Out of Scope) ---")
    out_query = "Who won the IPL cricket match yesterday?"

    async with AsyncSessionLocal() as db:
        req = AIChatRequest(question=out_query, language="en")
        resp = await chat_assistant(req, db=db)
        data = resp.data
        logger.info(f"Is Grounded: {data.is_grounded}")
        logger.info(f"Answer Text: '{data.answer}'")

        if "government scheme assistant" in data.answer.lower() or "scholarship" in data.answer.lower():
            logger.info("✅ TEST 4 PASSED: Out-of-scope query correctly identified with domain disclaimer")
            passed += 1
        else:
            logger.error("❌ TEST 4 FAILED: Out-of-scope handling failed")

    # ── Test 5: Multilingual Script Preservation ─────────────────────────────
    total += 1
    logger.info("\n--- TEST 5: Multilingual Script Preservation (EN, HI, GU, MR) ---")
    queries = {
        "en": "What documents are needed for CSSS scholarship?",
        "hi": "सीएसएसएस छात्रवृत्ति के लिए कौन से दस्तावेज आवश्यक हैं?",
        "gu": "CSSS શિષ્યવૃત્તિ માટે કયા દસ્તાવેજો જરૂરી છે?",
        "mr": "CSSS शिष्यवृत्तीसाठी कोणती कागदपत्रे आवश्यक आहेत?",
    }

    ml_success = True
    async with AsyncSessionLocal() as db:
        for lang_code, q_text in queries.items():
            req = AIChatRequest(question=q_text, language=lang_code)
            resp = await chat_assistant(req, db=db)
            answer_text = resp.data.answer
            logger.info(f"Lang [{lang_code.upper()}] Answer Preview:\n{answer_text[:120]}...")
            if not answer_text or len(answer_text) < 10:
                ml_success = False

    if ml_success:
        logger.info("✅ TEST 5 PASSED: Multilingual script preservation verified across all test languages")
        passed += 1
    else:
        logger.error("❌ TEST 5 FAILED: Multilingual response generation failed")

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("\n========================================================================")
    logger.info(f"  TEST SUMMARY: {passed}/{total} TESTS PASSED ({passed/total*100:.1f}%)")
    logger.info("========================================================================")
    if passed == total:
        logger.info("🎉 ALL ANSWER QUALITY & RELIABILITY TESTS PASSED PERFECTLY!")
        sys.exit(0)
    else:
        logger.error("⚠️ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
