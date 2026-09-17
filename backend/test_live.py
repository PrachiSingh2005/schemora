import urllib.request
import json

def test_chat(query, lang="en"):
    url = "http://127.0.0.1:8000/api/v1/ai/chat"
    payload = {"question": query, "language": lang}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            print(f"=== QUERY: {query} ({lang}) ===")
            print("STATUS:", response.status)
            print("INTENT:", res_data.get("detected_intent"))
            print("ANSWER:", res_data.get("answer"))
            print("CITATIONS:", len(res_data.get("citations", [])))
            print()
    except Exception as e:
        print(f"ERROR for {query}:", e)

if __name__ == "__main__":
    test_chat("hello", "en")
    test_chat("Tell me about PM-KISAN", "en")
    test_chat("पीएम किसान क्या है?", "hi")
