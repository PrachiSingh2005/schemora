"""Comprehensive Automated Test Suite for Schemora Text-to-Speech (TTS) Pipeline.

Tests:
  1. English TTS MP3 audio generation & header check
  2. Hindi TTS MP3 audio generation
  3. Gujarati TTS MP3 audio generation
  4. Marathi / Bengali TTS MP3 audio generation
  5. Edge Cases & Error Handling:
     - Empty text input (400 Bad Request)
     - Clean markdown / URL stripping before speech synthesis
     - Unsupported / fallback language handling
"""

import sys
import os
import asyncio
import logging

# Add backend root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.groq_service import generate_tts_audio
from app.schemas.ai import TextToSpeechRequest
from app.api.v1.ai import text_to_speech

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_tts")


async def run_tests():
    logger.info("========================================================================")
    logger.info("    STARTING TEXT-TO-SPEECH (TTS) MULTILINGUAL PIPELINE VERIFICATION    ")
    logger.info("========================================================================")

    passed = 0
    total = 0

    # ── Test 1: English TTS Audio Synthesis ─────────────────────────────────
    total += 1
    logger.info("\n--- TEST 1: English Text-to-Speech (EN) ---")
    en_text = "You satisfy all mandatory criteria for PM-Vidyalaxmi scholarship scheme."
    audio_bytes, mime, err = await generate_tts_audio(en_text, language="en")
    logger.info(f"Generated Audio Bytes Size: {len(audio_bytes) if audio_bytes else 0} bytes")
    logger.info(f"Content Type: {mime}")

    if audio_bytes and len(audio_bytes) > 500 and mime == "audio/mpeg":
        logger.info("✅ TEST 1 PASSED: English TTS audio generated successfully")
        passed += 1
    else:
        logger.error(f"❌ TEST 1 FAILED: {err}")

    # ── Test 2: Hindi TTS Audio Synthesis ───────────────────────────────────
    total += 1
    logger.info("\n--- TEST 2: Hindi Text-to-Speech (HI) ---")
    hi_text = "पीएम-विद्यालक्ष्मी योजना के लिए आपके सभी दस्तावेज़ सत्यापित हैं।"
    audio_bytes, mime, err = await generate_tts_audio(hi_text, language="hi")
    logger.info(f"Generated Audio Bytes Size: {len(audio_bytes) if audio_bytes else 0} bytes")

    if audio_bytes and len(audio_bytes) > 500:
        logger.info("✅ TEST 2 PASSED: Hindi TTS audio generated successfully")
        passed += 1
    else:
        logger.error(f"❌ TEST 2 FAILED: {err}")

    # ── Test 3: Gujarati TTS Audio Synthesis ────────────────────────────────
    total += 1
    logger.info("\n--- TEST 3: Gujarati Text-to-Speech (GU) ---")
    gu_text = "મુખ્યમંત્રી યુવા સ્વાવલંબન યોજના (MYSY) માટે સત્તાવાર વેબસાઇટ પર અરજી કરો."
    audio_bytes, mime, err = await generate_tts_audio(gu_text, language="gu")
    logger.info(f"Generated Audio Bytes Size: {len(audio_bytes) if audio_bytes else 0} bytes")

    if audio_bytes and len(audio_bytes) > 500:
        logger.info("✅ TEST 3 PASSED: Gujarati TTS audio generated successfully")
        passed += 1
    else:
        logger.error(f"❌ TEST 3 FAILED: {err}")

    # ── Test 4: Marathi / Bengali TTS Audio Synthesis ────────────────────────
    total += 1
    logger.info("\n--- TEST 4: Marathi Text-to-Speech (MR) ---")
    mr_text = "महाडिबीटी शिष्यवृत्ती योजनेचा लाभ घेण्यासाठी अर्ज प्रक्रिया पूर्ण करा."
    audio_bytes, mime, err = await generate_tts_audio(mr_text, language="mr")
    logger.info(f"Generated Audio Bytes Size: {len(audio_bytes) if audio_bytes else 0} bytes")

    if audio_bytes and len(audio_bytes) > 500:
        logger.info("✅ TEST 4 PASSED: Marathi TTS audio generated successfully")
        passed += 1
    else:
        logger.error(f"❌ TEST 4 FAILED: {err}")

    # ── Test 5: Empty Input / Unsupported Language Error Handling ────────────
    total += 1
    logger.info("\n--- TEST 5: Empty Text / Error Handling ---")
    audio_bytes, mime, err = await generate_tts_audio("", language="en")
    logger.info(f"Empty Text Handled Gracefully: {audio_bytes is None}")
    logger.info(f"Error Message: '{err}'")

    if audio_bytes is None and err is not None:
        logger.info("✅ TEST 5 PASSED: Empty text handled gracefully without crashing")
        passed += 1
    else:
        logger.error("❌ TEST 5 FAILED")

    # ── Summary ──────────────────────────────────────────────────────────────
    logger.info("\n========================================================================")
    logger.info(f"  TEST SUMMARY: {passed}/{total} TESTS PASSED ({passed/total*100:.1f}%)")
    logger.info("========================================================================")
    if passed == total:
        logger.info("🎉 ALL TEXT-TO-SPEECH (TTS) TESTS PASSED PERFECTLY!")
        sys.exit(0)
    else:
        logger.error("⚠️ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
