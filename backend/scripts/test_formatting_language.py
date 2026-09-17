import asyncio
import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000/api/v1/ai/chat"

TEST_QUERIES = [
    {
        "question": "What is a government scheme?",
        "language": "en",
        "description": "Definition in English"
    },
    {
        "question": "What schemes are available for students?",
        "language": "en",
        "description": "Scheme listing in English"
    },
    {
        "question": "योजना क्या है?",
        "language": "hi",
        "description": "Definition in Hindi"
    },
    {
        "question": "સરકારી યોજના શું છે?",
        "language": "gu",
        "description": "Definition in Gujarati"
    }
]

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        for t in TEST_QUERIES:
            print(f"\n=======================================================")
            print(f"TEST: {t['description']} | Query: '{t['question']}'")
            print(f"=======================================================")
            resp = await client.post(BASE_URL, json={
                "question": t["question"],
                "language": t["language"],
            })
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("data", {}).get("answer", "")
                print("RESPONSE:")
                print(answer)
            else:
                print(f"ERROR {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    asyncio.run(main())
