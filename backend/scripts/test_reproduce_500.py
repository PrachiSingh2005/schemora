import asyncio
import httpx
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000/api/v1/ai/chat"

async def test_query(question: str):
    print(f"\n=======================================================")
    print(f"Testing Query: '{question}'")
    print(f"=======================================================")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(BASE_URL, json={
            "question": question,
            "language": "en"
        })
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            print("Response JSON:")
            print(resp.json())
        else:
            print("Error Response:")
            print(resp.text)

async def main():
    await test_query("stepsor guidelines to fill scholarship form")
    await test_query("How do I apply for a scholarship?")
    await test_query("How do I apply for PM-KISAN?")
    await test_query("What documents are required for PM-KISAN?")

if __name__ == "__main__":
    asyncio.run(main())
