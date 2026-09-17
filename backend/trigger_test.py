import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000/api/v1/ai"

def make_post(url, data_dict, timeout=60):
    json_bytes = json.dumps(data_dict).encode("utf-8")
    req = urllib.request.Request(url, data=json_bytes, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def make_get(url, timeout=10):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def test_pipeline():
    print("=== STEP 1: Re-indexing Full Knowledge Base via FastAPI Endpoint ===")
    try:
        res = make_post(f"{BASE_URL}/knowledge-base/index", {}, timeout=60)
        print("Index Response:", json.dumps(res, indent=2))
    except Exception as e:
        print("Re-index failed:", e)

    print("\n=== STEP 2: Knowledge Base Status Check ===")
    try:
        res = make_get(f"{BASE_URL}/knowledge-base/status", timeout=10)
        print("Status Response:", json.dumps(res, indent=2))
    except Exception as e:
        print("Status check failed:", e)

    print("\n=== STEP 3: Testing 10 Retrieval & Chat Query Categories ===")
    test_cases = [
        ("Broad Scheme Query", "What schemes are available?", "en"),
        ("Scholarship Query", "student scholarships", "en"),
        ("Farmer Query", "schemes for farmers", "en"),
        ("Women Query", "women government schemes", "en"),
        ("Hindi Query", "गरीब लोगों के लिए योजनाएं", "hi"),
        ("Gujarati Query", "વિદ્યાર્થીઓ માટે સરકારી યોજનાઓ", "gu"),
        ("Specific Scheme Query", "What is PM Internship Scheme?", "en"),
        ("Eligibility Query", "Am I eligible if my family income is below 2.5 lakh?", "en"),
        ("Document Query", "What documents are required for PM scholarship?", "en"),
        ("Application Process Query", "How to apply for OBC post matric scholarship?", "en"),
    ]

    for title, query, lang in test_cases:
        print(f"\n------------------------------------------------------------")
        print(f"[{title}] Question: \"{query}\" (Lang: {lang})")
        payload = {"question": query, "language": lang}
        try:
            res = make_post(f"{BASE_URL}/chat", payload, timeout=35)
            if res.get("success"):
                resp_data = res.get("data", {})
                answer = resp_data.get("answer", "")
                retrieved = resp_data.get("retrieved_schemes", [])
                citations = resp_data.get("citations", [])

                schemes_found = list({s.get("scheme_name") for s in retrieved if s.get("scheme_name")})
                print(f"HTTP Status      : 200 OK")
                print(f"Retrieved Chunks : {len(retrieved)}")
                print(f"Distinct Schemes : {len(schemes_found)} -> {schemes_found[:4]}")
                print(f"Citations Count  : {len(citations)}")
                print(f"Answer Preview   :\n{answer[:350]}...\n")
            else:
                print(f"HTTP Status Error: {res}")
        except Exception as e:
            print(f"Chat request failed: {e}")

if __name__ == "__main__":
    test_pipeline()
