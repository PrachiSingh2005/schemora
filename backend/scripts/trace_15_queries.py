"""Diagnostic Trace Script for Chatbot Intent Routing.

Traces 15 queries through every stage:
1. Normalized Query
2. Language Detection
3. Intent Detection
4. Entity Extraction
5. Retrieval Decision (RAG Triggered?)
6. Chunks Count
7. Groq Called?
8. Response Generated
"""

import asyncio
import json
from app.core.database import AsyncSessionLocal
from app.services.retrieval_service import detect_intent, extract_query_entity_and_section, retrieve_relevant_chunks
from app.services.query_understanding_service import analyze_query_understanding
from app.services.groq_service import generate_grounded_chat_response, detect_query_language

TEST_QUERIES = [
    "hello",
    "hi",
    "hey",
    "good morning",
    "good evening",
    "thanks",
    "thank you",
    "bye",
    "What is PM-KISAN?",
    "What documents are required for PM-KISAN?",
    "How do I apply for PM-KISAN?",
    "Give me schemes for farmers in Maharashtra.",
    "Tell me about MahaDBT.",
    "What scholarships are available on MahaDBT?",
    "Compare PM-KISAN and PM Internship Scheme.",
]

async def trace_all():
    print("=" * 100)
    print(f"{'QUERY':<42} | {'INTENT':<22} | {'ENTITY':<20} | {'RAG?':<5} | {'GROQ?':<5}")
    print("=" * 100)

    async with AsyncSessionLocal() as db:
        for q in TEST_QUERIES:
            qu_res = analyze_query_understanding(q)
            intent = detect_intent(q)
            entity, sec = extract_query_entity_and_section(q)
            
            rag_triggered = intent not in ["GREETING", "THANKS", "GOODBYE", "AMBIGUOUS", "UNKNOWN", "PORTAL_INFO", "PORTAL_APPLICATION"]
            
            chunks = []
            if rag_triggered:
                chunks = await retrieve_relevant_chunks(db, q, top_k=5)

            ans, citations, grounded = await generate_grounded_chat_response(q, chunks=chunks, language="en")

            print(f"{q:<42} | {intent:<22} | {str(entity):<20} | {str(rag_triggered):<5} | {str(len(chunks)>0):<5}")
            print(f"   -> Response Preview: {ans[:100]}...\n")

if __name__ == "__main__":
    asyncio.run(trace_all())
