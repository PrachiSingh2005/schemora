import urllib.request
import json
import time

def test_endpoint(name, url, method="GET", payload=None):
    start = time.time()
    try:
        data_bytes = json.dumps(payload).encode('utf-8') if payload else None
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"} if payload else {},
            method=method
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            elapsed = time.time() - start
            print(f"✅ [{name}] STATUS: {response.status} in {elapsed:.2f}s")
            return res_data
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ [{name}] ERROR after {elapsed:.2f}s: {e}")
        return None

if __name__ == "__main__":
    print("Testing Backend Response Times...")
    test_endpoint("SCHEMES PAGE 200", "http://127.0.0.1:8000/api/v1/schemes?page_size=200")
    test_endpoint("CHAT", "http://127.0.0.1:8000/api/v1/ai/chat", method="POST", payload={"question": "hello", "language": "en"})
