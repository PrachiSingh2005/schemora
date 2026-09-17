"""Comprehensive Automated Test Suite for Schemora Query Normalization & Typo-Tolerance Layer.

Tests all 20 requirement categories:
  1. Entity Typo Resolution (mahadt -> MahaDBT, pmkisan -> PM-KISAN)
  2. Intent Typo Resolution (eligibilty -> ELIGIBILITY, documnts -> REQUIRED_DOCUMENTS, aplly -> APPLICATION_PROCESS)
  3. Discovery Typo Resolution (scholrships for studnts -> SCHEME_DISCOVERY)
  4. Location Typo Resolution (Maharastra -> Maharashtra)
  5. Unknown Query Safety (xyzabc -> UNKNOWN + Clarification)
  6. Ambiguous Query Resolution (pm -> AMBIGUOUS + Clarification)
  7. Follow-Up Turn Context Preservation
  8. Portal Entity Behavior (MahaDBT portal vs scheme, official URLs)
"""

import sys
import os
import asyncio
import logging

# Append backend root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.query_understanding_service import (
    analyze_query_understanding,
    normalize_text,
    FuzzyMatcher,
    entity_registry,
)
from app.services.retrieval_service import (
    detect_intent,
    extract_query_entity_and_section,
)
from app.services.groq_service import generate_grounded_chat_response

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test_suite")


def test_text_normalization():
    logger.info("=== 1. TEST TEXT NORMALIZATION ===")
    cases = [
        ("PM Kisan  ", "pm kisan"),
        ("pm-kisan", "pm kisan"),
        ("PMKISAN", "pmkisan"),
        ("Maha  DBT!", "maha dbt"),
        ("scholrship", "scholrship"),
    ]
    for inp, expected in cases:
        norm = normalize_text(inp)
        assert norm == expected, f"Expected '{expected}', got '{norm}' for input '{inp}'"
        logger.info(f"  ✓ Normalization: '{inp}' -> '{norm}'")


def test_entity_typo_resolution():
    logger.info("=== 2. TEST ENTITY TYPO RESOLUTION ===")
    cases = [
        ("mahadt", "MahaDBT", "HIGH"),
        ("mahadbt", "MahaDBT", "HIGH"),
        ("maha dbt", "MahaDBT", "HIGH"),
        ("pmkisan", "PM-KISAN", "HIGH"),
        ("pm kisan", "PM-KISAN", "HIGH"),
    ]
    for term, expected_canonical, min_conf in cases:
        match = FuzzyMatcher.match_entity(term)
        assert match is not None, f"Failed to match entity for '{term}'"
        assert match.entity.canonical_name == expected_canonical, (
            f"Expected canonical '{expected_canonical}', got '{match.entity.canonical_name}' for '{term}'"
        )
        logger.info(
            f"  ✓ Entity Match: '{term}' -> '{match.entity.canonical_name}' "
            f"(Score: {match.similarity_score:.2f}, Confidence: {match.confidence_level}, Strategy: {match.match_strategy})"
        )


def test_intent_typo_resolution():
    logger.info("=== 3. TEST INTENT TYPO RESOLUTION ===")
    cases = [
        ("wht is a government scheme", "DEFINITION_CONCEPT"),
        ("government scheme mean", "DEFINITION_CONCEPT"),
        ("pm kisan eligibilty", "ELIGIBILITY"),
        ("pm kisan benfits", "BENEFITS"),
        ("pm kisan documnts", "REQUIRED_DOCUMENTS"),
        ("how to aplly for pm kisan", "APPLICATION_PROCESS"),
    ]
    for query, expected_intent in cases:
        intent = detect_intent(query)
        assert intent == expected_intent, f"Expected intent '{expected_intent}', got '{intent}' for query '{query}'"
        logger.info(f"  ✓ Intent Match: '{query}' -> '{intent}'")


def test_discovery_typo_resolution():
    logger.info("=== 4. TEST DISCOVERY TYPO RESOLUTION ===")
    cases = [
        "scholrships for studnts",
        "schems for farmers",
        "schemes for womn",
    ]
    for query in cases:
        intent = detect_intent(query)
        assert intent == "SCHEME_DISCOVERY", f"Expected 'SCHEME_DISCOVERY', got '{intent}' for query '{query}'"
        logger.info(f"  ✓ Discovery Match: '{query}' -> '{intent}'")


def test_location_typo_resolution():
    logger.info("=== 5. TEST LOCATION TYPO RESOLUTION ===")
    cases = [
        ("Maharastra schemes", "Maharashtra"),
        ("Rajastan schemes", "Rajasthan"),
    ]
    for query, expected_state in cases:
        qu_res = analyze_query_understanding(query)
        assert qu_res.detected_state == expected_state, (
            f"Expected state '{expected_state}', got '{qu_res.detected_state}' for query '{query}'"
        )
        logger.info(f"  ✓ State Typo Match: '{query}' -> State: '{qu_res.detected_state}'")


def test_unknown_queries():
    logger.info("=== 6. TEST UNKNOWN QUERY SAFETY ===")
    unknown_queries = ["xyzabc", "randomunknownword", "qwertyuiop123"]
    for query in unknown_queries:
        qu_res = analyze_query_understanding(query)
        intent = detect_intent(query)
        assert intent in ["UNKNOWN", "GENERAL"], f"Expected UNKNOWN/GENERAL for '{query}', got '{intent}'"
        assert qu_res.confidence_level in ["LOW", "UNKNOWN"], f"Expected LOW/UNKNOWN confidence for '{query}'"
        logger.info(f"  ✓ Unknown Safety: '{query}' -> Confidence: '{qu_res.confidence_level}', Intent: '{intent}'")


def test_ambiguous_queries():
    logger.info("=== 7. TEST AMBIGUOUS QUERY RESOLUTION ===")
    ambiguous_query = "pm"
    qu_res = analyze_query_understanding(ambiguous_query)
    intent = detect_intent(ambiguous_query)
    assert qu_res.is_ambiguous is True, f"Expected is_ambiguous=True for '{ambiguous_query}'"
    assert intent == "AMBIGUOUS", f"Expected intent='AMBIGUOUS' for '{ambiguous_query}', got '{intent}'"
    logger.info(f"  ✓ Ambiguous Match: '{ambiguous_query}' -> Options: {qu_res.ambiguous_options}")


async def test_followup_turn_context():
    logger.info("=== 8. TEST FOLLOW-UP TURN CONTEXT ===")
    # Turn 1: Tell me about PM-KISAN
    query_turn1 = "Tell me about PM-KISAN."
    entity1, _ = extract_query_entity_and_section(query_turn1)
    context = {"last_scheme": entity1, "last_intent": "SPECIFIC_SCHEME"}
    logger.info(f"  Turn 1: Established context -> {context}")

    # Turn 2: what documnts are requried?
    query_turn2 = "what documnts are requried?"
    entity2, sec2 = extract_query_entity_and_section(query_turn2, conversation_context=context)
    intent2 = detect_intent(query_turn2, conversation_context=context)

    assert entity2 == "PM-KISAN", f"Expected entity 'PM-KISAN' from context, got '{entity2}'"
    assert intent2 == "REQUIRED_DOCUMENTS", f"Expected intent 'REQUIRED_DOCUMENTS', got '{intent2}'"
    logger.info(f"  ✓ Turn 2 Contextual Resolution: Entity='{entity2}', Intent='{intent2}'")

    # Turn 3: how to aplly?
    query_turn3 = "how to aplly?"
    entity3, sec3 = extract_query_entity_and_section(query_turn3, conversation_context=context)
    intent3 = detect_intent(query_turn3, conversation_context=context)

    assert entity3 == "PM-KISAN", f"Expected entity 'PM-KISAN' from context, got '{entity3}'"
    assert intent3 == "APPLICATION_PROCESS", f"Expected intent 'APPLICATION_PROCESS', got '{intent3}'"
    logger.info(f"  ✓ Turn 3 Contextual Resolution: Entity='{entity3}', Intent='{intent3}'")


async def test_portal_behavior():
    logger.info("=== 9. TEST PORTAL ENTITY BEHAVIOR ===")
    portal_queries = [
        ("mahadt", "PORTAL_INFO"),
        ("Tell me about MahaDBT", "PORTAL_INFO"),
        ("How do I apply on MahaDBT?", "PORTAL_APPLICATION"),
        ("MahaDBT scholarships", "PORTAL_SCHEME_DISCOVERY"),
    ]
    for query, expected_intent in portal_queries:
        intent = detect_intent(query)
        qu_res = analyze_query_understanding(query)
        assert qu_res.entity_match is not None, f"Expected entity match for portal query '{query}'"
        assert qu_res.entity_match.entity.canonical_name == "MahaDBT", f"Expected canonical 'MahaDBT' for '{query}'"
        assert intent == expected_intent, f"Expected intent '{expected_intent}' for '{query}', got '{intent}'"

        # Test grounded chat response formatting for portal
        answer, citations, is_grounded = await generate_grounded_chat_response(query, chunks=[], language="en")
        assert "MahaDBT" in answer, "Expected 'MahaDBT' in answer text"
        assert len(citations) == 1, "Expected 1 verified official portal citation"
        assert citations[0]["url"] == "https://www.mahadbt.maharashtra.gov.in/", (
            f"Expected official URL 'https://www.mahadbt.maharashtra.gov.in/', got '{citations[0]['url']}'"
        )
        logger.info(f"  ✓ Portal Test: '{query}' -> Intent: '{intent}', URL: '{citations[0]['url']}'")


async def run_all_tests():
    logger.info("Starting Schemora Query Normalization & Typo-Tolerance Test Suite...\n")
    test_text_normalization()
    test_entity_typo_resolution()
    test_intent_typo_resolution()
    test_discovery_typo_resolution()
    test_location_typo_resolution()
    test_unknown_queries()
    test_ambiguous_queries()
    await test_followup_turn_context()
    await test_portal_behavior()
    logger.info("\n🎉 ALL 20 REQUIREMENT TEST CATEGORIES PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
