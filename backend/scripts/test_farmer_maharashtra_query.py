"""Test script for user query: "I am a farmer in maharashtra state , give me schemes related to this"
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.services.query_understanding_service import analyze_query_understanding
from app.services.retrieval_service import detect_intent, extract_query_entity_and_section, retrieve_relevant_chunks
from app.services.groq_service import generate_grounded_chat_response

async def test_farmer_query():
    query = "I am a farmer in maharashtra state , give me schemes related to this"

    qu_res = analyze_query_understanding(query)
    intent = detect_intent(query)
    entity, section = extract_query_entity_and_section(query)

    print(f"Query: '{query}'")
    print(f"Detected Intent: {intent}")
    print(f"Detected Entity: {qu_res.entity_match.entity.canonical_name if qu_res.entity_match else 'None'}")
    print(f"Detected Entity Type: {qu_res.entity_match.entity.entity_type if qu_res.entity_match else 'None'}")
    print(f"Detected State: {qu_res.detected_state}")

    async with AsyncSessionLocal() as db:
        chunks = await retrieve_relevant_chunks(db, query=query, top_k=6)
        print(f"\nRetrieved Chunks Count: {len(chunks)}")
        for idx, c in enumerate(chunks, 1):
            print(f" [{idx}] Scheme: {c.get('scheme_name')} | Section: {c.get('section')} | Score: {c.get('similarity_score')} | State: {c.get('state')}")

        answer, citations, is_grounded = await generate_grounded_chat_response(
            query=query,
            chunks=chunks,
            language="en"
        )
        print(f"\n================ Generated Response ================\n")
        print(answer)
        print(f"\n================ Citations ================\n")
        print(citations)

if __name__ == "__main__":
    asyncio.run(test_farmer_query())
