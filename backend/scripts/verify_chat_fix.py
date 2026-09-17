import asyncio
import sys
import json
import httpx

sys.stdout.reconfigure(encoding='utf-8')

# Import FastAPI app directly for in-process testing
from app.main import app

TEST_QUERIES = [
    {
        "description": "Test 1: Generic application form filling query with typo",
        "question": "stepsor guidelines to fill scholarship form",
        "language": "en"
    },
    {
        "description": "Test 2: Generic scholarship application query",
        "question": "How do I apply for a scholarship?",
        "language": "en"
    },
    {
        "description": "Test 3: Specific scheme application query",
        "question": "How do I apply for PM-KISAN?",
        "language": "en"
    },
    {
        "description": "Test 4: Specific scheme required documents query",
        "question": "What documents are required for PM-KISAN?",
        "language": "en"
    }
]

async def run_tests():
    print("=" * 80)
    print("RUNNING BACKEND CHATBOT API VERIFICATION TEST SUITE")
    print("=" * 80)
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for t in TEST_QUERIES:
            print(f"\n----------------------------------------------------------------")
            print(f"{t['description']}")
            print(f"QUERY: '{t['question']}'")
            print(f"----------------------------------------------------------------")
            
            resp = await client.post("/api/v1/ai/chat", json={
                "question": t["question"],
                "language": t["language"],
            })
            
            print(f"HTTP STATUS CODE: {resp.status_code}")
            assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}: {resp.text}"
            
            data = resp.json()
            success = data.get("success")
            print(f"API SUCCESS: {success}")
            
            res_data = data.get("data", {})
            answer = res_data.get("answer", "")
            citations = res_data.get("citations", [])
            retrieved_schemes = res_data.get("retrieved_schemes", [])
            is_grounded = res_data.get("is_grounded", False)
            
            print(f"ANSWER SNIPPET:\n{answer[:300]}")
            print(f"CITATIONS COUNT: {len(citations)}")
            if citations:
                for c in citations:
                    print(f"  • {c.get('source_name')} -> {c.get('url')}")
            print(f"RETRIEVED SCHEMES COUNT: {len(retrieved_schemes)}")
            if retrieved_schemes:
                for r in retrieved_schemes:
                    print(f"  • {r.get('scheme_name')} ({r.get('section')})")
            
            print("STATUS: VERIFIED PASSED (200 OK)")

if __name__ == "__main__":
    asyncio.run(run_tests())
