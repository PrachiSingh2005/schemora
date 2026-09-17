import asyncio
import httpx

async def test_pipeline():
    print("==================================================")
    print("TESTING VOICE & CHAT PIPELINE END-TO-END")
    print("==================================================")

    base_url = "http://127.0.0.1:8000/api/v1/ai"
    
    # 1. Test Chat Pipeline for requested queries
    queries = [
        "hello",
        "What is a government scheme?",
        "What is PM-KISAN?",
        "What documents are required for PM-KISAN?",
        "Give me farmer schemes in Maharashtra.",
        "How do I apply for Ladki Bahin?"
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for q in queries:
            print(f"\n--- QUERY: '{q}' ---")
            resp = await client.post(f"{base_url}/chat", json={"question": q, "language": "en"})
            print(f"Status Code: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()["data"]
                answer = data.get("answer", "")
                intent = data.get("intent", "N/A")
                print(f"[CHAT] Intent: {intent}")
                print(f"[CHAT] Answer snippet: {answer[:120]}...")
            else:
                print(f"ERROR: {resp.text}")

        # 2. Test STT direct endpoint with mock audio WAV header bytes
        print("\n--- STT DIRECT ENDPOINT TEST ---")
        # Standard silent 44-byte WAV header + 1 second silence
        wav_header = bytes([
            0x52, 0x49, 0x46, 0x46, 0x24, 0x08, 0x00, 0x00, 0x57, 0x41, 0x56, 0x45,
            0x66, 0x6d, 0x74, 0x20, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
            0x44, 0xac, 0x00, 0x00, 0x88, 0x58, 0x01, 0x00, 0x02, 0x00, 0x10, 0x00,
            0x64, 0x61, 0x74, 0x61, 0x00, 0x08, 0x00, 0x00
        ]) + bytes(2000)
        
        files = {"file": ("test.wav", wav_header, "audio/wav")}
        resp = await client.post(f"{base_url}/speech-to-text", files=files)
        print(f"STT Direct Status Code: {resp.status_code}")
        print(f"STT Direct Response: {resp.text[:200]}")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
