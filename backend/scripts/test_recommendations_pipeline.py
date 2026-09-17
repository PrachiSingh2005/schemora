"""Recommendation Engine Test Suite for the 4 Debug Profiles.

Runs end-to-end testing against PostgreSQL + pgvector and outputs detailed step-by-step debug information:
Profile -> Normalized Profile -> Structured Filters -> Candidate Scheme IDs -> Vector Retrieval -> Final Recommendations -> Match Reasons -> Selected URLs
"""

import sys
import os
import asyncio
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.schemas.ai import AIRecommendationProfileInput
from app.services.recommendation_service import generate_recommendations


async def run_recommendation_tests():
    test_cases = [
        {
            "id": "PROFILE 1",
            "description": "Farmer in Maharashtra (Age 35, Income ₹2L)",
            "input": AIRecommendationProfileInput(
                age=35,
                state="Maharashtra",
                occupation="Farmer",
                annual_income=200000.0,
                language="en",
            ),
        },
        {
            "id": "PROFILE 2",
            "description": "B.Tech Student in Maharashtra (Age 21, Income ₹2.5L)",
            "input": AIRecommendationProfileInput(
                age=21,
                state="Maharashtra",
                occupation="Student",
                education="B.Tech",
                annual_income=250000.0,
                language="en",
            ),
        },
        {
            "id": "PROFILE 3",
            "description": "Senior Citizen in Maharashtra (Age 65)",
            "input": AIRecommendationProfileInput(
                age=65,
                state="Maharashtra",
                occupation="Senior Citizen",
                language="en",
            ),
        },
        {
            "id": "PROFILE 4",
            "description": "Female Student in Maharashtra",
            "input": AIRecommendationProfileInput(
                state="Maharashtra",
                gender="Female",
                occupation="Student",
                student_status=True,
                language="en",
            ),
        },
    ]

    async with AsyncSessionLocal() as db:
        print("\n" + "=" * 80)
        print("     SCHEMORA AI RECOMMENDATIONS PIPELINE DIAGNOSTIC SUITE")
        print("=" * 80 + "\n")

        all_passed = True

        for tc in test_cases:
            print(f"▶ {tc['id']}: {tc['description']}")
            print("-" * 60)

            rec_resp = await generate_recommendations(
                db=db,
                profile=None,
                input_data=tc["input"],
            )

            debug = rec_resp.debug_info
            print(f"  • User Input Profile: {json.dumps(debug.get('input_profile'), indent=2)}")
            print(f"  • Normalized Profile: {json.dumps(debug.get('normalized_profile'), indent=2)}")
            print(f"  • Structured DB Filters: {json.dumps(debug.get('structured_filters'), indent=2)}")
            print(f"  • Candidate Scheme Count: {debug.get('total_candidate_schemes')}")
            print(f"  • Candidate Scheme IDs: {debug.get('candidate_scheme_ids')}")
            print(f"  • Vector Semantic Query: '{debug.get('vector_query')}'")
            print(f"  • Final Recommended Count: {len(rec_resp.recommendations)}")
            print("\n  ★ FINAL RECOMMENDED SCHEMES:")

            for i, rec in enumerate(rec_resp.recommendations, 1):
                print(f"    [{i}] {rec.scheme_name} ({rec.jurisdiction} - {rec.state or 'All-India'})")
                print(f"        Match Type: {rec.match_type} (Score: {rec.score})")
                print(f"        Match Reasons: {rec.match_reasons}")
                print(f"        Why Relevant: {rec.relevance_explanation}")
                print(f"        Official Scheme URL: {rec.official_scheme_url or 'N/A'}")
                print(f"        Application URL:     {rec.application_url or 'N/A'}")
                print(f"        Best Action URL:     {rec.best_action_url or 'N/A'}")
                print()

            # Sanity Checks:
            # 1. No portals returned as schemes
            portal_names = ["myscheme", "mahadbt", "nsp", "jan samarth"]
            for rec in rec_resp.recommendations:
                for p in portal_names:
                    if p in rec.scheme_name.lower() and "portal" in rec.scheme_name.lower():
                        print(f"  ❌ ERROR: Portal '{rec.scheme_name}' recommended as a scheme!")
                        all_passed = False

            # 2. Profile 1 (Farmer) check
            if tc["id"] == "PROFILE 1":
                has_farmer_scheme = any("farmer" in r.scheme_name.lower() or "kisan" in r.scheme_name.lower() or "agri" in r.scheme_name.lower() or any("Farmer" in m for m in r.match_reasons) for r in rec_resp.recommendations)
                if not has_farmer_scheme:
                    print("  ⚠️ WARNING: Profile 1 did not retrieve explicit farmer scheme!")

            print("=" * 80 + "\n")

    return all_passed


if __name__ == "__main__":
    asyncio.run(run_recommendation_tests())
