#!/usr/bin/env python3
"""
Schemora Full Audit Test — Tests all 15 required queries end-to-end via HTTP.
"""
import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000/api/v1/ai"

TEST_QUERIES = [
    # Greetings
    {"q": "hello", "lang": "en", "expected_intent": "GREETING", "expect_no": ["scholarship", "scheme are you asking"]},
    {"q": "hi", "lang": "en", "expected_intent": "GREETING", "expect_no": ["scholarship", "scheme are you asking"]},
    # Concept
    {"q": "What is a government scheme?", "lang": "en", "expected_intent": "DEFINITION_CONCEPT"},
    # Specific scheme
    {"q": "What is PM-KISAN?", "lang": "en", "expected_intent": "SPECIFIC_SCHEME", "expect_in": ["pm-kisan", "kisan", "farmer", "6000", "samman"]},
    # Documents
    {"q": "What documents are required for PM-KISAN?", "lang": "en", "expected_intent": "REQUIRED_DOCUMENTS", "expect_in": ["document", "aadhaar", "land", "bank"]},
    # Application
    {"q": "How do I apply for PM-KISAN?", "lang": "en", "expected_intent": "APPLICATION_PROCESS", "expect_in": ["apply", "pmkisan", "portal", "step", "online"]},
    # Discovery
    {"q": "Give me schemes for farmers in Maharashtra.", "lang": "en", "expected_intent": "SCHEME_DISCOVERY", "expect_no": ["myscheme portal", "visit myscheme.gov.in to find"]},
    # Scholarship
    {"q": "Give me scholarships for students in Maharashtra.", "lang": "en", "expected_intent": "SCHEME_DISCOVERY"},
    # Specific scheme with state
    {"q": "Tell me about Ladki Bahin scheme.", "lang": "en", "expect_in": ["ladki bahin", "women", "maharashtra", "1500"]},
    # Application
    {"q": "How do I apply for Ladki Bahin?", "lang": "en", "expect_in": ["apply", "nari shakti", "portal", "step"]},
    # Portal
    {"q": "Tell me about MahaDBT.", "lang": "en", "expect_in": ["mahadbt", "maharashtra", "scholarship", "portal"]},
    # Portal + scheme discovery
    {"q": "What scholarships are available on MahaDBT?", "lang": "en", "expect_in": ["mahadbt", "scholarship"]},
    # Comparison
    {"q": "Compare PM-KISAN and PM Internship Scheme.", "lang": "en", "expect_in": ["pm-kisan", "internship", "farmer", "comparison"]},
    # Typo handling
    {"q": "What are the eligibilty criteria for PM-KISAN?", "lang": "en", "expect_in": ["eligib", "pm-kisan"]},
    # Unknown
    {"q": "xyzabc", "lang": "en", "expect_no": ["I'm sorry", "found a scheme", "pm-kisan"], "safe_unknown": True},
]

MULTILINGUAL_QUERIES = [
    {"q": "पीएम किसान योजना क्या है?", "lang": "hi", "expect_lang_in": ["किसान", "योजना", "₹", "6000"]},
    {"q": "PM Kisan ke liye kaunse documents chahiye?", "lang": "en", "expect_in": ["document", "aadhaar"]},
    {"q": "પીએમ કિસાન યોજના શું છે?", "lang": "gu", "expect_in": ["kisan", "gu_text"]},
]


async def run_audit():
    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n" + "="*70)
        print("SCHEMORA CHATBOT FULL AUDIT — TEXT QUERIES")
        print("="*70)

        for test in TEST_QUERIES:
            q = test["q"]
            lang = test.get("lang", "en")
            payload = {"question": q, "language": lang}
            
            try:
                resp = await client.post(f"{BASE_URL}/chat", json=payload)
                status_code = resp.status_code
                
                if status_code == 200:
                    data = resp.json()
                    answer = data.get("data", {}).get("answer", "")
                    intent = data.get("data", {}).get("intent", "N/A")
                    citations = data.get("data", {}).get("citations", [])
                    
                    # Verify checks
                    issues = []
                    
                    # Check expected_in
                    if "expect_in" in test:
                        for keyword in test["expect_in"]:
                            if keyword.lower() not in answer.lower():
                                issues.append(f"MISSING: '{keyword}' not found in answer")
                    
                    # Check expect_no
                    if "expect_no" in test:
                        for keyword in test["expect_no"]:
                            if keyword.lower() in answer.lower():
                                issues.append(f"BAD: '{keyword}' should NOT be in answer")
                    
                    # Greetings check
                    if "GREETING" in test.get("expected_intent", "") or q.lower() in ["hi", "hello"]:
                        if any(bad in answer.lower() for bad in ["which scholarship", "scheme are you asking", "please mention the scheme"]):
                            issues.append("CRITICAL: Greeting returned scheme-clarification response!")
                    
                    status = "PASS" if not issues else "FAIL"
                    
                    print(f"\n{'✅' if status == 'PASS' else '❌'} Q: '{q}'")
                    print(f"   Intent: {intent} | Lang: {lang} | Answer length: {len(answer)} chars")
                    print(f"   Citations: {len(citations)}")
                    print(f"   Answer[:200]: {answer[:200]}")
                    if issues:
                        for issue in issues:
                            print(f"   ⚠️  {issue}")
                    
                    results.append({"query": q, "status": status, "intent": intent, "issues": issues, "answer_preview": answer[:200], "citations_count": len(citations)})
                else:
                    print(f"\n❌ Q: '{q}'")
                    print(f"   HTTP {status_code}: {resp.text[:200]}")
                    results.append({"query": q, "status": "FAIL", "error": f"HTTP {status_code}"})
            
            except Exception as e:
                print(f"\n❌ Q: '{q}' — EXCEPTION: {e}")
                results.append({"query": q, "status": "ERROR", "error": str(e)})
        
        print("\n" + "="*70)
        print("MULTILINGUAL QUERIES")
        print("="*70)
        
        for test in MULTILINGUAL_QUERIES:
            q = test["q"]
            lang = test.get("lang", "en")
            payload = {"question": q, "language": lang}
            
            try:
                resp = await client.post(f"{BASE_URL}/chat", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data.get("data", {}).get("answer", "")
                    # Check it's not purely English when Hindi/Gujarati expected
                    lang_flag = lang
                    if lang == "hi" and not any(c > "\u0900" for c in answer):
                        lang_flag = "FAIL:ENGLISH_RESPONSE_FOR_HINDI"
                    elif lang == "gu" and not any("\u0A80" <= c <= "\u0AFF" for c in answer):
                        lang_flag = "WARN:MAY_NOT_BE_GUJARATI"
                    
                    print(f"\n  Q ({lang}): '{q[:50]}'")
                    print(f"  Lang check: {lang_flag}")
                    print(f"  Answer[:200]: {answer[:200]}")
                    results.append({"query": q, "status": "SEE_ABOVE", "lang_check": lang_flag})
                else:
                    print(f"\n  ❌ Q: '{q}' — HTTP {resp.status_code}")
            except Exception as e:
                print(f"\n  ❌ Q: '{q}' — EXCEPTION: {e}")
        
        # Check KB status
        print("\n" + "="*70)
        print("KNOWLEDGE BASE STATUS")
        print("="*70)
        try:
            kb_resp = await client.get(f"{BASE_URL}/knowledge-base/status")
            if kb_resp.status_code == 200:
                kb_data = kb_resp.json()
                print(f"  KB Data: {json.dumps(kb_data, indent=2)[:500]}")
            else:
                print(f"  KB Status endpoint returned HTTP {kb_resp.status_code}")
        except Exception as e:
            print(f"  KB Status check FAILED: {e}")
        
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        error = sum(1 for r in results if r["status"] == "ERROR")
        print(f"  PASSED: {passed} / {len(results)}")
        print(f"  FAILED: {failed} / {len(results)}")
        print(f"  ERRORS: {error} / {len(results)}")
        
        return results


if __name__ == "__main__":
    asyncio.run(run_audit())
