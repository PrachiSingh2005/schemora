import urllib.request
import json
import time

url = "http://127.0.0.1:8000/api/v1/ai/chat"
payload = {"question": "hii", "language": "en"}

print(f"Sending POST {url} with payload {payload}...")
start = time.time()
try:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        data = response.read().decode('utf-8')
        elapsed = time.time() - start
        print(f"STATUS {response.status} in {elapsed:.2f}s:")
        print(data[:500])
except Exception as e:
    elapsed = time.time() - start
    print(f"FAILED after {elapsed:.2f}s: {e}")
