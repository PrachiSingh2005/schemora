import urllib.request
import json
import time

url = "http://127.0.0.1:8000/api/v1/ai/chat"
payload = {"question": "hi", "language": "en"}

print(f"Testing {url} with payload {payload}...")
start = time.time()
try:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        elapsed = time.time() - start
        print(f"STATUS {response.status} in {elapsed:.2f}s:")
        print(json.dumps(res_data, indent=2))
except Exception as e:
    elapsed = time.time() - start
    print(f"FAILED after {elapsed:.2f}s: {e}")
