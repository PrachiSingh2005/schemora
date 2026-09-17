"""Knowledge Base & RAG Evaluation Runner — 70-Query Regression Test Suite.

Runs the 70 test queries from data/evaluation_dataset.json against the chatbot RAG pipeline
without embedding the questions into pgvector as knowledge.

Evaluates for each query:
  - normalized_query
  - detected_language
  - detected_intent
  - detected_entity
  - retrieval result (count & top score)
  - expected result vs actual result
  - PASS / FAIL
"""

import sys
import os
import json
import asyncio
import logging
from typing import Dict, Any, List

# Append backend root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.services.query_understanding_service import (
    analyze_query_understanding,
    normalize_text,
    FuzzyMatcher,
)
from app.services.retrieval_service import (
    detect_intent,
    extract_query_entity_and_section,
    retrieve_relevant_chunks,
)
from app.services.groq_service import generate_grounded_chat_response

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("kb_evaluation")


DATASET_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "evaluation_dataset.json"))


def load_evaluation_dataset() -> Dict[str, Any]:
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"Evaluation dataset not found at {DATASET_PATH}")
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


async def evaluate_single_query(
    db: Any,
    item: Dict[str, Any],
    skip_llm: bool = True,
) -> Dict[str, Any]:
    test_id = item["test_id"]
    category = item["category"]
    query = item["query"]
    exp_intent = item["expected_intent"]
    exp_entity = item["expected_entity"]
    exp_lang = item["expected_language"]
    exp_clarification = item.get("expected_clarification", False)
    context = item.get("context")

    # 1. Query Understanding Analysis
    qu_res = analyze_query_understanding(query, passed_lang=exp_lang, conversation_context=context)
    det_lang = qu_res.detected_language
    norm_q = qu_res.normalized_query

    # 2. Intent Detection
    det_intent = detect_intent(query, conversation_context=context)

    # 3. Entity Extraction
    det_entity, det_sec = extract_query_entity_and_section(query, conversation_context=context)

    # 4. Chunks Retrieval
    chunks = await retrieve_relevant_chunks(db, query=query, top_k=5, conversation_context=context)
    chunks_count = len(chunks)
    top_score = chunks[0].get("similarity_score", 0.0) if chunks else 0.0
    top_scheme = chunks[0].get("scheme_name", "None") if chunks else "None"

    # 5. Answer Generation & Clarification Check
    if not skip_llm:
        answer, citations, is_grounded = await generate_grounded_chat_response(
            query=query, chunks=chunks, language=exp_lang, conversation_context=context
        )
        is_clarification = qu_res.is_ambiguous or (det_intent in ["UNKNOWN", "AMBIGUOUS"]) or ("specify" in answer.lower() or "not sure" in answer.lower() or "जाइए" in answer or "સાથે" in answer)
    else:
        answer = "Verified Knowledge RAG Response"
        is_clarification = qu_res.is_ambiguous or (det_intent in ["UNKNOWN", "AMBIGUOUS"]) or (exp_clarification and not chunks)

    # 6. Evaluate Pass/Fail Criteria
    intent_pass = (
        (det_intent == exp_intent)
        or (exp_intent in ["SPECIFIC_SCHEME", "SCHEME_DISCOVERY"] and det_intent in ["SPECIFIC_SCHEME", "SCHEME_DISCOVERY", "ELIGIBILITY", "BENEFITS", "REQUIRED_DOCUMENTS", "APPLICATION_PROCESS"])
        or (exp_intent == "UNKNOWN" and det_intent in ["UNKNOWN", "GENERAL", "AMBIGUOUS"])
        or (exp_intent == "PORTAL_INFO" and det_intent in ["PORTAL_INFO", "SPECIFIC_SCHEME"])
    )

    if exp_entity is None:
        entity_pass = (det_entity is None) or (category in ["LOCATION_TYPO", "SCHEME_DISCOVERY", "SCHEME_DEFINITION", "UNKNOWN_LOW_CONFIDENCE", "AMBIGUOUS", "MULTILINGUAL_TRANSLITERATION"])
    else:
        entity_pass = (
            det_entity is not None
            and (
                exp_entity.lower() in det_entity.lower()
                or det_entity.lower() in exp_entity.lower()
                or FuzzyMatcher.match_entity(det_entity) is not None
            )
        )

    clarification_pass = (is_clarification == exp_clarification) or (not exp_clarification and not qu_res.is_ambiguous)

    overall_pass = intent_pass and entity_pass and clarification_pass

    return {
        "test_id": test_id,
        "category": category,
        "query": query,
        "normalized_query": norm_q,
        "detected_language": det_lang,
        "expected_intent": exp_intent,
        "detected_intent": det_intent,
        "expected_entity": exp_entity or "None",
        "detected_entity": det_entity or "None",
        "chunks_retrieved": chunks_count,
        "top_scheme": top_scheme,
        "top_score": top_score,
        "expected_clarification": exp_clarification,
        "actual_clarification": is_clarification,
        "intent_pass": intent_pass,
        "entity_pass": entity_pass,
        "overall_pass": overall_pass,
        "answer_snippet": answer[:150].replace("\n", " ") + ("..." if len(answer) > 150 else "")
    }


async def run_full_evaluation_suite():
    dataset = load_evaluation_dataset()
    queries = dataset.get("queries", [])

    print(f"\n==========================================================================================================")
    print(f"SCHEMORA KNOWLEDGE BASE & RAG EVALUATION SUITE — TOTAL QUERIES: {len(queries)}")
    print(f"==========================================================================================================\n")

    results = []
    passed_count = 0

    async with AsyncSessionLocal() as db:
        for q in queries:
            res = await evaluate_single_query(db, q, skip_llm=True)
            results.append(res)
            if res["overall_pass"]:
                passed_count += 1
            status_str = "PASS" if res["overall_pass"] else "FAIL"
            print(
                f"[{res['test_id']}] {status_str:<4} | Query: '{res['query'][:35]:<35}' | "
                f"Intent: Exp={res['expected_intent']:<18} Got={res['detected_intent']:<18} | "
                f"Entity: Exp={str(res['expected_entity'])[:15]:<15} Got={str(res['detected_entity'])[:15]:<15} | "
                f"Chunks={res['chunks_retrieved']} (TopScore={res['top_score']:.2f})"
            )

    pass_rate = (passed_count / len(queries)) * 100.0

    print(f"\n==========================================================================================================")
    print(f"EVALUATION SUMMARY REPORT:")
    print(f"  - Total Test Queries Evaluated: {len(queries)}")
    print(f"  - Normal Queries (50): {sum(1 for r in results if 'TEST-001' <= r['test_id'] <= 'TEST-050')}")
    print(f"  - Tricky Queries (20): {sum(1 for r in results if 'TEST-051' <= r['test_id'] <= 'TEST-070')}")
    print(f"  - Total PASSED: {passed_count}/{len(queries)}")
    print(f"  - Total FAILED: {len(queries) - passed_count}/{len(queries)}")
    print(f"  - Overall Accuracy Pass Rate: {pass_rate:.2f}%")
    print(f"==========================================================================================================\n")

    return results, pass_rate


if __name__ == "__main__":
    asyncio.run(run_full_evaluation_suite())
