import urllib.request
import json
import time

def test_get(url):
    print(f"Testing GET {url}...")
    start = time.time()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            elapsed = (time.time() - start) * 1000
            print(f"✅ PASS: Status {resp.status} in {elapsed:.1f}ms")
            print("   Body:", json.dumps(data, indent=2))
            return True, data
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        print(f"❌ FAIL in {elapsed:.1f}ms: {e}")
        return False, str(e)

def test_post_chat(url, question="hi"):
    print(f"Testing POST {url} with question='{question}'...")
    start = time.time()
    try:
        payload = json.dumps({"question": question, "language": "en"}).encode('utf-8')
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            elapsed = (time.time() - start) * 1000
            print(f"✅ PASS: Status {resp.status} in {elapsed:.1f}ms")
            print("   Intent:", data.get("data", {}).get("detected_intent"))
            print("   Answer:", data.get("data", {}).get("answer")[:120] if data.get("data", {}).get("answer") else None)
            return True, data
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        print(f"❌ FAIL in {elapsed:.1f}ms: {e}")
        return False, str(e)

if __name__ == "__main__":
    print("=== STEP 3: LAPTOP BACKEND VERIFICATION ===")
    test_get("http://127.0.0.1:8000/")
    test_get("http://127.0.0.1:8000/api/v1/health")
    test_post_chat("http://127.0.0.1:8000/api/v1/ai/chat", "hi")
    test_post_chat("http://127.0.0.1:8000/api/v1/ai/chat", "What is PM-KISAN?")
