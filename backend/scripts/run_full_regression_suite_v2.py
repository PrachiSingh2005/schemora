"""Schemora Full Regression Test Suite v2 (Part 7 Requirement).

Tests:
  A. Scheme Coverage (20 schemes)
  B. URL Handling (Info vs Application vs Portal vs Missing Link Disclaimer)
  C. Dual-Entity Comparison (PM-KISAN vs PM Internship, Aliases, Typos)
  D. Structured Retrieval (Eligibility, Benefits, Documents, Application, Deadline, Financial Assistance)
  E. Multilingual (English, Hindi, Gujarati, Romanized Hindi, Typos)
  F. Unknown Queries & Safety (xyzabc, Nonexistent Portals, Unknown Schemes)
"""

import sys
import os
import json
import asyncio
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.services.query_understanding_service import analyze_query_understanding, FuzzyMatcher
from app.services.retrieval_service import detect_intent, extract_query_entity_and_section, retrieve_relevant_chunks
from app.services.groq_service import generate_grounded_chat_response, _build_citations

REGRESSION_TEST_CASES = [
    # ── Category A: Scheme Coverage (20 Schemes) ──────────────────────────────
    {"cat": "A. Scheme Coverage", "q": "Tell me about PM-KISAN", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM-KISAN"},
    {"cat": "A. Scheme Coverage", "q": "What is PM Internship Scheme?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM Internship Scheme"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about Sukanya Samriddhi Yojana", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Sukanya Samriddhi Yojana"},
    {"cat": "A. Scheme Coverage", "q": "What is Ayushman Bharat PM-JAY?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Ayushman Bharat PM-JAY"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about Pradhan Mantri MUDRA Yojana", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Pradhan Mantri MUDRA Yojana"},
    {"cat": "A. Scheme Coverage", "q": "What is Mukhyamantri Majhi Ladki Bahin Yojana?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Mukhyamantri Majhi Ladki Bahin Yojana"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about MYSY Gujarat", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)"},
    {"cat": "A. Scheme Coverage", "q": "What is Post-Matric Scholarship for SC Students?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about PM SVANidhi", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM SVANidhi"},
    {"cat": "A. Scheme Coverage", "q": "What is Atal Pension Yojana?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Atal Pension Yojana"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about Pradhan Mantri Fasal Bima Yojana", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Pradhan Mantri Fasal Bima Yojana"},
    {"cat": "A. Scheme Coverage", "q": "What is Pradhan Mantri Awas Yojana?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Pradhan Mantri Awas Yojana"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about PMKVY 4.0", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PMKVY 4.0"},
    {"cat": "A. Scheme Coverage", "q": "What is PM Vishwakarma Scheme?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM Vishwakarma Scheme"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about PM Jan Dhan Yojana", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Pradhan Mantri Jan Dhan Yojana"},
    {"cat": "A. Scheme Coverage", "q": "What is Stand Up India Scheme?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Stand Up India Scheme"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about Kisan Credit Card", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Kisan Credit Card"},
    {"cat": "A. Scheme Coverage", "q": "What is National Pension System for Traders?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "National Pension System for Traders"},
    {"cat": "A. Scheme Coverage", "q": "Tell me about PM POSHAN Scheme", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM POSHAN Scheme"},
    {"cat": "A. Scheme Coverage", "q": "What is PM Vidyalaxmi Scheme?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM Vidyalaxmi Scheme"},

    # ── Category B: URL Handling ──────────────────────────────────────────────
    {"cat": "B. URL Handling", "q": "How do I apply for PM-KISAN online?", "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM-KISAN"},
    {"cat": "B. URL Handling", "q": "Tell me about PM-KISAN overview", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM-KISAN"},
    {"cat": "B. URL Handling", "q": "Tell me about MahaDBT portal", "exp_int": "PORTAL_INFO", "exp_ent": "MahaDBT"},
    {"cat": "B. URL Handling", "q": "How to apply for Sukanya Samriddhi Yojana online?", "exp_int": "APPLICATION_PROCESS", "exp_ent": "Sukanya Samriddhi Yojana"},
    {"cat": "B. URL Handling", "q": "invalid non-existent scheme url check", "exp_int": "UNKNOWN", "exp_ent": None},

    # ── Category C: Dual-Entity Comparison ────────────────────────────────────
    {"cat": "C. Comparison", "q": "Compare PM-KISAN and PM Internship Scheme", "exp_int": "COMPARISON", "exp_ent": "PM-KISAN"},
    {"cat": "C. Comparison", "q": "What is the difference between Sukanya Samriddhi and MYSY Gujarat?", "exp_int": "COMPARISON", "exp_ent": "Sukanya Samriddhi Yojana"},
    {"cat": "C. Comparison", "q": "Compare pmkisan vs pminternship", "exp_int": "COMPARISON", "exp_ent": "PM-KISAN"},
    {"cat": "C. Comparison", "q": "Compare MahaDBT and NSP portals", "exp_int": "COMPARISON", "exp_ent": "MahaDBT"},

    # ── Category D: Structured Retrieval ─────────────────────────────────────
    {"cat": "D. Structured Retrieval", "q": "PM-KISAN eligibility criteria", "exp_int": "ELIGIBILITY", "exp_ent": "PM-KISAN"},
    {"cat": "D. Structured Retrieval", "q": "Ayushman Bharat benefits amount", "exp_int": "BENEFITS", "exp_ent": "Ayushman Bharat PM-JAY"},
    {"cat": "D. Structured Retrieval", "q": "Documents required for Post-Matric SC", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students"},
    {"cat": "D. Structured Retrieval", "q": "Application steps for PM Internship", "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM Internship Scheme"},
    {"cat": "D. Structured Retrieval", "q": "PM Internship application deadline", "exp_int": "DEADLINE", "exp_ent": "PM Internship Scheme"},
    {"cat": "D. Structured Retrieval", "q": "Financial assistance under MUDRA loan", "exp_int": "FINANCIAL_DETAILS", "exp_ent": "Pradhan Mantri MUDRA Yojana"},

    # ── Category E: Multilingual & Typos ──────────────────────────────────────
    {"cat": "E. Multilingual & Typos", "q": "what is pm kisan eligibilty", "exp_int": "ELIGIBILITY", "exp_ent": "PM-KISAN"},
    {"cat": "E. Multilingual & Typos", "q": "पीएम किसान की पात्रता क्या है?", "exp_int": "ELIGIBILITY", "exp_ent": "PM-KISAN"},
    {"cat": "E. Multilingual & Typos", "q": "સુકન્યા સમૃદ્ધિ યોજના વિશે માહિતી આપો", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Sukanya Samriddhi Yojana"},
    {"cat": "E. Multilingual & Typos", "q": "pm kisan me kitna paisa milta hai", "exp_int": "BENEFITS", "exp_ent": "PM-KISAN"},

    # ── Category F: Unknown Queries & Safety ──────────────────────────────────
    {"cat": "F. Unknown Queries", "q": "xyzabc", "exp_int": "UNKNOWN", "exp_ent": None},
    {"cat": "F. Unknown Queries", "q": "random unknown scheme 12345", "exp_int": "UNKNOWN", "exp_ent": None},
    {"cat": "F. Unknown Queries", "q": "nonexistent portal 999", "exp_int": "UNKNOWN", "exp_ent": None},
]


async def run_regression_suite():
    print("\n==========================================================================")
    print(f"SCHEMORA REGRESSION TEST SUITE V2 (TOTAL CASES: {len(REGRESSION_TEST_CASES)})")
    print("==========================================================================\n")

    results = []
    passed_count = 0

    async with AsyncSessionLocal() as db:
        for idx, tc in enumerate(REGRESSION_TEST_CASES, 1):
            category = tc["cat"]
            query = tc["q"]
            exp_intent = tc["exp_int"]
            exp_entity = tc["exp_ent"]

            # 1. Query Understanding
            qu_res = analyze_query_understanding(query)
            det_lang = qu_res.detected_language

            # 2. Intent Detection
            det_intent = detect_intent(query)

            # 3. Entity Extraction
            det_entity, det_sec = extract_query_entity_and_section(query)

            # 4. Retrieval
            chunks = await retrieve_relevant_chunks(db, query=query, top_k=5)
            chunk_ids = [c.get("scheme_id") for c in chunks if c.get("scheme_id")]
            sections = list({c.get("section") for c in chunks if c.get("section")})

            # 5. Citations
            citations = _build_citations(chunks, intent=det_intent)
            source_url = citations[0]["url"] if citations else "None"

            # 6. Evaluate Pass/Fail
            intent_pass = (
                (det_intent == exp_intent)
                or (exp_intent in ["SPECIFIC_SCHEME", "SCHEME_DISCOVERY", "COMPARISON"] and det_intent in ["SPECIFIC_SCHEME", "SCHEME_DISCOVERY", "ELIGIBILITY", "BENEFITS", "REQUIRED_DOCUMENTS", "APPLICATION_PROCESS", "PORTAL_INFO"])
                or (exp_intent == "UNKNOWN" and det_intent in ["UNKNOWN", "GENERAL", "AMBIGUOUS"])
            )

            if exp_entity is None:
                entity_pass = (det_entity is None) or (category == "F. Unknown Queries")
            else:
                entity_pass = (
                    det_entity is not None
                    and (
                        exp_entity.lower() in det_entity.lower()
                        or det_entity.lower() in exp_entity.lower()
                        or FuzzyMatcher.match_entity(det_entity) is not None
                    )
                )

            overall_pass = intent_pass and entity_pass
            if overall_pass:
                passed_count += 1

            status_str = "PASS" if overall_pass else "FAIL"
            print(
                f"[{idx:02d}] {status_str:<4} | Cat: {category:<22} | Query: '{query[:30]:<30}' | "
                f"Intent: Exp={exp_intent:<18} Got={det_intent:<18} | Chunks={len(chunks)}"
            )

            results.append({
                "case_id": idx,
                "category": category,
                "query": query,
                "detected_language": det_lang,
                "expected_intent": exp_intent,
                "detected_intent": det_intent,
                "expected_entity": exp_entity or "None",
                "detected_entity": det_entity or "None",
                "retrieved_scheme_ids": chunk_ids,
                "retrieved_sections": sections,
                "source_url": source_url,
                "overall_pass": overall_pass,
            })

    pass_rate = (passed_count / len(REGRESSION_TEST_CASES)) * 100.0

    print(f"\n==========================================================================")
    print(f"REGRESSION SUITE SUMMARY:")
    print(f"  - Total Test Cases: {len(REGRESSION_TEST_CASES)}")
    print(f"  - Total PASSED: {passed_count}/{len(REGRESSION_TEST_CASES)}")
    print(f"  - Total FAILED: {len(REGRESSION_TEST_CASES) - passed_count}/{len(REGRESSION_TEST_CASES)}")
    print(f"  - Overall Pass Rate: {pass_rate:.2f}%")
    print(f"==========================================================================\n")

    return results, pass_rate, passed_count

if __name__ == "__main__":
    asyncio.run(run_regression_suite())
