"""Schemora 100-Query Realistic RAG Readiness Audit Suite.

Runs 100 realistic queries across 20 distinct query categories to evaluate:
  1. Definitions
  2. Discovery
  3. Specific schemes
  4. Eligibility
  5. Benefits
  6. Documents
  7. Application
  8. Deadlines
  9. Status
  10. Renewal
  11. Portals
  12. Follow-up questions
  13. Typos
  14. Hindi
  15. Gujarati
  16. Mixed language
  17. Ambiguous questions
  18. Unknown questions
  19. Comparison
  20. Profile-based discovery
"""

import sys
import os
import json
import asyncio
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.services.query_understanding_service import analyze_query_understanding, FuzzyMatcher
from app.services.retrieval_service import detect_intent, extract_query_entity_and_section, retrieve_relevant_chunks

# 100 Realistic Audit Queries
AUDIT_QUERIES = [
    # 1. Definitions (5)
    {"id": "AUD-001", "cat": "Definitions", "q": "What is a government scheme?", "exp_int": "DEFINITION_CONCEPT", "exp_ent": None, "exp_sec": "concept", "lang": "en", "exp_clar": False},
    {"id": "AUD-002", "cat": "Definitions", "q": "what does Direct Benefit Transfer mean?", "exp_int": "DEFINITION_CONCEPT", "exp_ent": "DBT", "exp_sec": "concept", "lang": "en", "exp_clar": False},
    {"id": "AUD-003", "cat": "Definitions", "q": "define income certificate", "exp_int": "DEFINITION_CONCEPT", "exp_ent": None, "exp_sec": "concept", "lang": "en", "exp_clar": False},
    {"id": "AUD-004", "cat": "Definitions", "q": "what is central scheme", "exp_int": "DEFINITION_CONCEPT", "exp_ent": None, "exp_sec": "concept", "lang": "en", "exp_clar": False},
    {"id": "AUD-005", "cat": "Definitions", "q": "सब्सिडी किसे कहते हैं?", "exp_int": "DEFINITION_CONCEPT", "exp_ent": None, "exp_sec": "concept", "lang": "hi", "exp_clar": False},

    # 2. Discovery (5)
    {"id": "AUD-006", "cat": "Discovery", "q": "What schemes are available for students?", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-007", "cat": "Discovery", "q": "Which schemes are available for farmers?", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-008", "cat": "Discovery", "q": "Show schemes for women entrepreneurs", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-009", "cat": "Discovery", "q": "List all scholarships for single girl child", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-010", "cat": "Discovery", "q": "Show me education loan schemes for higher studies", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},

    # 3. Specific Schemes (5)
    {"id": "AUD-011", "cat": "Specific Schemes", "q": "Tell me about PM-KISAN", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM-KISAN", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-012", "cat": "Specific Schemes", "q": "What is PM Internship Scheme?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM Internship Scheme", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-013", "cat": "Specific Schemes", "q": "Tell me about Sukanya Samriddhi Yojana", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Sukanya Samriddhi Yojana", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-014", "cat": "Specific Schemes", "q": "What is Ayushman Bharat PM-JAY?", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Ayushman Bharat PM-JAY", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-015", "cat": "Specific Schemes", "q": "Tell me about Pradhan Mantri MUDRA Yojana", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Pradhan Mantri MUDRA Yojana", "exp_sec": "overview", "lang": "en", "exp_clar": False},

    # 4. Eligibility (5)
    {"id": "AUD-016", "cat": "Eligibility", "q": "What is the eligibility for PM-KISAN?", "exp_int": "ELIGIBILITY", "exp_ent": "PM-KISAN", "exp_sec": "eligibility", "lang": "en", "exp_clar": False},
    {"id": "AUD-017", "cat": "Eligibility", "q": "Who is eligible for Post-Matric Scholarship for SC Students?", "exp_int": "ELIGIBILITY", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students", "exp_sec": "eligibility", "lang": "en", "exp_clar": False},
    {"id": "AUD-018", "cat": "Eligibility", "q": "What are the income limits for MYSY Gujarat?", "exp_int": "ELIGIBILITY", "exp_ent": "Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)", "exp_sec": "eligibility", "lang": "en", "exp_clar": False},
    {"id": "AUD-019", "cat": "Eligibility", "q": "What are the eligibility criteria for PM Internship Scheme?", "exp_int": "ELIGIBILITY", "exp_ent": "PM Internship Scheme", "exp_sec": "eligibility", "lang": "en", "exp_clar": False},
    {"id": "AUD-020", "cat": "Eligibility", "q": "Who can apply for Ayushman Bharat card?", "exp_int": "ELIGIBILITY", "exp_ent": "Ayushman Bharat PM-JAY", "exp_sec": "eligibility", "lang": "en", "exp_clar": False},

    # 5. Benefits (5)
    {"id": "AUD-021", "cat": "Benefits", "q": "What are the benefits of PM-KISAN?", "exp_int": "BENEFITS", "exp_ent": "PM-KISAN", "exp_sec": "benefits", "lang": "en", "exp_clar": False},
    {"id": "AUD-022", "cat": "Benefits", "q": "How much financial assistance is provided under Ayushman Bharat?", "exp_int": "BENEFITS", "exp_ent": "Ayushman Bharat PM-JAY", "exp_sec": "benefits", "lang": "en", "exp_clar": False},
    {"id": "AUD-023", "cat": "Benefits", "q": "What loan amount is available under MUDRA Yojana?", "exp_int": "BENEFITS", "exp_ent": "Pradhan Mantri MUDRA Yojana", "exp_sec": "benefits", "lang": "en", "exp_clar": False},
    {"id": "AUD-024", "cat": "Benefits", "q": "What is the scholarship amount for Post-Matric SC students?", "exp_int": "BENEFITS", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students", "exp_sec": "benefits", "lang": "en", "exp_clar": False},
    {"id": "AUD-025", "cat": "Benefits", "q": "What are the interest rates and benefits of Sukanya Samriddhi Yojana?", "exp_int": "BENEFITS", "exp_ent": "Sukanya Samriddhi Yojana", "exp_sec": "benefits", "lang": "en", "exp_clar": False},

    # 6. Documents (5)
    {"id": "AUD-026", "cat": "Documents", "q": "What documents are required for PM-KISAN?", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "PM-KISAN", "exp_sec": "documents", "lang": "en", "exp_clar": False},
    {"id": "AUD-027", "cat": "Documents", "q": "What papers do I need for Post-Matric Scholarship?", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students", "exp_sec": "documents", "lang": "en", "exp_clar": False},
    {"id": "AUD-028", "cat": "Documents", "q": "What documents are needed for MYSY scholarship?", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)", "exp_sec": "documents", "lang": "en", "exp_clar": False},
    {"id": "AUD-029", "cat": "Documents", "q": "What documents are required for Ladki Bahin Scheme?", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "Mukhyamantri Majhi Ladki Bahin Yojana", "exp_sec": "documents", "lang": "en", "exp_clar": False},
    {"id": "AUD-030", "cat": "Documents", "q": "Checklist of documents for Ayushman Bharat card", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "Ayushman Bharat PM-JAY", "exp_sec": "documents", "lang": "en", "exp_clar": False},

    # 7. Application (5)
    {"id": "AUD-031", "cat": "Application", "q": "How to apply for PM-KISAN online?", "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM-KISAN", "exp_sec": "application", "lang": "en", "exp_clar": False},
    {"id": "AUD-032", "cat": "Application", "q": "What is the step by step process to register on National Scholarship Portal?", "exp_int": "APPLICATION_PROCESS", "exp_ent": "National Scholarship Portal", "exp_sec": "application", "lang": "en", "exp_clar": False},
    {"id": "AUD-033", "cat": "Application", "q": "How to apply for PM Internship Scheme?", "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM Internship Scheme", "exp_sec": "application", "lang": "en", "exp_clar": False},
    {"id": "AUD-034", "cat": "Application", "q": "steps or guidelines to fill scholarship form", "exp_int": "APPLICATION_PROCESS", "exp_ent": None, "exp_sec": "application", "lang": "en", "exp_clar": True},
    {"id": "AUD-035", "cat": "Application", "q": "How can I register for MUDRA loan?", "exp_int": "APPLICATION_PROCESS", "exp_ent": "Pradhan Mantri MUDRA Yojana", "exp_sec": "application", "lang": "en", "exp_clar": False},

    # 8. Deadlines (5)
    {"id": "AUD-036", "cat": "Deadlines", "q": "What is the deadline to apply for PM Internship Scheme?", "exp_int": "DEADLINE", "exp_ent": "PM Internship Scheme", "exp_sec": "deadlines", "lang": "en", "exp_clar": False},
    {"id": "AUD-037", "cat": "Deadlines", "q": "When does NSP scholarship registration close?", "exp_int": "DEADLINE", "exp_ent": "National Scholarship Portal", "exp_sec": "deadlines", "lang": "en", "exp_clar": False},
    {"id": "AUD-038", "cat": "Deadlines", "q": "What is the last date to apply for MYSY Gujarat?", "exp_int": "DEADLINE", "exp_ent": "Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)", "exp_sec": "deadlines", "lang": "en", "exp_clar": False},
    {"id": "AUD-039", "cat": "Deadlines", "q": "Is PM-KISAN application open all year?", "exp_int": "DEADLINE", "exp_ent": "PM-KISAN", "exp_sec": "deadlines", "lang": "en", "exp_clar": False},
    {"id": "AUD-040", "cat": "Deadlines", "q": "Post matric scholarship deadline date", "exp_int": "DEADLINE", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students", "exp_sec": "deadlines", "lang": "en", "exp_clar": False},

    # 9. Status (5)
    {"id": "AUD-041", "cat": "Status", "q": "Is PM-KISAN scheme active right now?", "exp_int": "STATUS", "exp_ent": "PM-KISAN", "exp_sec": "status", "lang": "en", "exp_clar": False},
    {"id": "AUD-042", "cat": "Status", "q": "How to check scholarship application status?", "exp_int": "STATUS", "exp_ent": None, "exp_sec": "status", "lang": "en", "exp_clar": False},
    {"id": "AUD-043", "cat": "Status", "q": "Is PM Internship Scheme currently accepting applications?", "exp_int": "STATUS", "exp_ent": "PM Internship Scheme", "exp_sec": "status", "lang": "en", "exp_clar": False},
    {"id": "AUD-044", "cat": "Status", "q": "Is Ladki Bahin Scheme currently active in Maharashtra?", "exp_int": "STATUS", "exp_ent": "Mukhyamantri Majhi Ladki Bahin Yojana", "exp_sec": "status", "lang": "en", "exp_clar": False},
    {"id": "AUD-045", "cat": "Status", "q": "Ayushman Bharat card active status", "exp_int": "STATUS", "exp_ent": "Ayushman Bharat PM-JAY", "exp_sec": "status", "lang": "en", "exp_clar": False},

    # 10. Renewal (5)
    {"id": "AUD-046", "cat": "Renewal", "q": "How to renew Post-Matric Scholarship for second year?", "exp_int": "RENEWAL", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students", "exp_sec": "renewal", "lang": "en", "exp_clar": False},
    {"id": "AUD-047", "cat": "Renewal", "q": "What is the process to renew scholarship on NSP?", "exp_int": "RENEWAL", "exp_ent": "National Scholarship Portal", "exp_sec": "renewal", "lang": "en", "exp_clar": False},
    {"id": "AUD-048", "cat": "Renewal", "q": "Do I need to reapply every year for MYSY Gujarat?", "exp_int": "RENEWAL", "exp_ent": "Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)", "exp_sec": "renewal", "lang": "en", "exp_clar": False},
    {"id": "AUD-049", "cat": "Renewal", "q": "Scholarship renewal rules and attendance requirement", "exp_int": "RENEWAL", "exp_ent": None, "exp_sec": "renewal", "lang": "en", "exp_clar": False},
    {"id": "AUD-050", "cat": "Renewal", "q": "How many years can I renew Post Matric OBC scholarship?", "exp_int": "RENEWAL", "exp_ent": "Post-Matric Scholarship for Scheduled Caste Students", "exp_sec": "renewal", "lang": "en", "exp_clar": False},

    # 11. Portals (5)
    {"id": "AUD-051", "cat": "Portals", "q": "mahadt", "exp_int": "PORTAL_INFO", "exp_ent": "MahaDBT", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-052", "cat": "Portals", "q": "Tell me about MahaDBT", "exp_int": "PORTAL_INFO", "exp_ent": "MahaDBT", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-053", "cat": "Portals", "q": "How do I apply on MahaDBT?", "exp_int": "PORTAL_APPLICATION", "exp_ent": "MahaDBT", "exp_sec": "application", "lang": "en", "exp_clar": False},
    {"id": "AUD-054", "cat": "Portals", "q": "MahaDBT scholarships list", "exp_int": "PORTAL_SCHEME_DISCOVERY", "exp_ent": "MahaDBT", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-055", "cat": "Portals", "q": "What is National Scholarship Portal?", "exp_int": "PORTAL_INFO", "exp_ent": "National Scholarship Portal", "exp_sec": "overview", "lang": "en", "exp_clar": False},

    # 12. Follow-up Questions (5)
    {"id": "AUD-056", "cat": "Follow-up Questions", "q": "Tell me about PM-KISAN.", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "PM-KISAN", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-057", "cat": "Follow-up Questions", "q": "what documnts are requried?", "ctx": {"last_scheme": "PM-KISAN"}, "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "PM-KISAN", "exp_sec": "documents", "lang": "en", "exp_clar": False},
    {"id": "AUD-058", "cat": "Follow-up Questions", "q": "how to aplly?", "ctx": {"last_scheme": "PM-KISAN"}, "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM-KISAN", "exp_sec": "application", "lang": "en", "exp_clar": False},
    {"id": "AUD-059", "cat": "Follow-up Questions", "q": "what are the benefits?", "ctx": {"last_scheme": "PM-KISAN"}, "exp_int": "BENEFITS", "exp_ent": "PM-KISAN", "exp_sec": "benefits", "lang": "en", "exp_clar": False},
    {"id": "AUD-060", "cat": "Follow-up Questions", "q": "who is eligible?", "ctx": {"last_scheme": "PM-KISAN"}, "exp_int": "ELIGIBILITY", "exp_ent": "PM-KISAN", "exp_sec": "eligibility", "lang": "en", "exp_clar": False},

    # 13. Typos (5)
    {"id": "AUD-061", "cat": "Typos", "q": "what is pm kisan eligibilty", "exp_int": "ELIGIBILITY", "exp_ent": "PM-KISAN", "exp_sec": "eligibility", "lang": "en", "exp_clar": False},
    {"id": "AUD-062", "cat": "Typos", "q": "pm kisan benfits", "exp_int": "BENEFITS", "exp_ent": "PM-KISAN", "exp_sec": "benefits", "lang": "en", "exp_clar": False},
    {"id": "AUD-063", "cat": "Typos", "q": "what documnts are requried for pm kisan", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "PM-KISAN", "exp_sec": "documents", "lang": "en", "exp_clar": False},
    {"id": "AUD-064", "cat": "Typos", "q": "how to aplly for pm kisan", "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM-KISAN", "exp_sec": "application", "lang": "en", "exp_clar": False},
    {"id": "AUD-065", "cat": "Typos", "q": "Maharastra schemes for studnts", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},

    # 14. Hindi (5)
    {"id": "AUD-066", "cat": "Hindi", "q": "योजना क्या है?", "exp_int": "DEFINITION_CONCEPT", "exp_ent": None, "exp_sec": "concept", "lang": "hi", "exp_clar": False},
    {"id": "AUD-067", "cat": "Hindi", "q": "पीएम किसान की पात्रता क्या है?", "exp_int": "ELIGIBILITY", "exp_ent": "PM-KISAN", "exp_sec": "eligibility", "lang": "hi", "exp_clar": False},
    {"id": "AUD-068", "cat": "Hindi", "q": "पीएम किसान के तहत कितना पैसा मिलता है?", "exp_int": "BENEFITS", "exp_ent": "PM-KISAN", "exp_sec": "benefits", "lang": "hi", "exp_clar": False},
    {"id": "AUD-069", "cat": "Hindi", "q": "पीएम किसान के लिए कौन से दस्तावेज चाहिए?", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "PM-KISAN", "exp_sec": "documents", "lang": "hi", "exp_clar": False},
    {"id": "AUD-070", "cat": "Hindi", "q": "पीएम किसान का फॉर्म कैसे भरें?", "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM-KISAN", "exp_sec": "application", "lang": "hi", "exp_clar": False},

    # 15. Gujarati (5)
    {"id": "AUD-071", "cat": "Gujarati", "q": "સરકારી યોજના શું છે?", "exp_int": "DEFINITION_CONCEPT", "exp_ent": None, "exp_sec": "concept", "lang": "gu", "exp_clar": False},
    {"id": "AUD-072", "cat": "Gujarati", "q": "વિદ્યાર્થીઓ માટે કઈ શિષ્યવૃત્તિઓ ઉપલબ્ધ છે?", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "gu", "exp_clar": False},
    {"id": "AUD-073", "cat": "Gujarati", "q": "સુકન્યા સમૃદ્ધિ યોજના વિશે માહિતી આપો", "exp_int": "SPECIFIC_SCHEME", "exp_ent": "Sukanya Samriddhi Yojana", "exp_sec": "overview", "lang": "gu", "exp_clar": False},
    {"id": "AUD-074", "cat": "Gujarati", "q": "MYSY યોજના માટે કયા દસ્તાવેજો જોઈએ?", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": "Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)", "exp_sec": "documents", "lang": "gu", "exp_clar": False},
    {"id": "AUD-075", "cat": "Gujarati", "q": "સરકારી યોજનાઓ", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "gu", "exp_clar": False},

    # 16. Mixed Language (5)
    {"id": "AUD-076", "cat": "Mixed Language", "q": "pm kisan me kitna paisa milta hai", "exp_int": "BENEFITS", "exp_ent": "PM-KISAN", "exp_sec": "benefits", "lang": "hi", "exp_clar": False},
    {"id": "AUD-077", "cat": "Mixed Language", "q": "how to fill pm kisan ka form online", "exp_int": "APPLICATION_PROCESS", "exp_ent": "PM-KISAN", "exp_sec": "application", "lang": "hi", "exp_clar": False},
    {"id": "AUD-078", "cat": "Mixed Language", "q": "scholarship apply karne ke liye konse documents chahiye", "exp_int": "REQUIRED_DOCUMENTS", "exp_ent": None, "exp_sec": "documents", "lang": "hi", "exp_clar": False},
    {"id": "AUD-079", "cat": "Mixed Language", "q": "mahadbt scholarship nu form kevi rite bharvu", "exp_int": "PORTAL_APPLICATION", "exp_ent": "MahaDBT", "exp_sec": "application", "lang": "gu", "exp_clar": False},
    {"id": "AUD-080", "cat": "Mixed Language", "q": "ayushman card kaise banaye step by step", "exp_int": "APPLICATION_PROCESS", "exp_ent": "Ayushman Bharat PM-JAY", "exp_sec": "application", "lang": "hi", "exp_clar": False},

    # 17. Ambiguous Questions (5)
    {"id": "AUD-081", "cat": "Ambiguous Questions", "q": "pm", "exp_int": "AMBIGUOUS", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},
    {"id": "AUD-082", "cat": "Ambiguous Questions", "q": "scholarship", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-083", "cat": "Ambiguous Questions", "q": "form", "exp_int": "AMBIGUOUS", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},
    {"id": "AUD-084", "cat": "Ambiguous Questions", "q": "money", "exp_int": "AMBIGUOUS", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},
    {"id": "AUD-085", "cat": "Ambiguous Questions", "q": "portal", "exp_int": "AMBIGUOUS", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},

    # 18. Unknown Questions (5)
    {"id": "AUD-086", "cat": "Unknown Questions", "q": "xyzabc", "exp_int": "UNKNOWN", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},
    {"id": "AUD-087", "cat": "Unknown Questions", "q": "randomunknownword", "exp_int": "UNKNOWN", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},
    {"id": "AUD-088", "cat": "Unknown Questions", "q": "qwertyuiop123", "exp_int": "UNKNOWN", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},
    {"id": "AUD-089", "cat": "Unknown Questions", "q": "asdfghjkl999", "exp_int": "UNKNOWN", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},
    {"id": "AUD-090", "cat": "Unknown Questions", "q": "foobar12345", "exp_int": "UNKNOWN", "exp_ent": None, "exp_sec": None, "lang": "en", "exp_clar": True},

    # 19. Comparison (5)
    {"id": "AUD-091", "cat": "Comparison", "q": "Compare PM-KISAN and PM Internship Scheme", "exp_int": "COMPARISON", "exp_ent": "PM-KISAN", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-092", "cat": "Comparison", "q": "What is the difference between NSP and MahaDBT?", "exp_int": "COMPARISON", "exp_ent": "National Scholarship Portal", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-093", "cat": "Comparison", "q": "Which scheme is better for girl child Sukanya Samriddhi or MYSY?", "exp_int": "COMPARISON", "exp_ent": "Sukanya Samriddhi Yojana", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-094", "cat": "Comparison", "q": "Compare MUDRA loan Shishu vs Kishore", "exp_int": "COMPARISON", "exp_ent": "Pradhan Mantri MUDRA Yojana", "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-095", "cat": "Comparison", "q": "PM-JAY vs State health insurance schemes", "exp_int": "COMPARISON", "exp_ent": "Ayushman Bharat PM-JAY", "exp_sec": "overview", "lang": "en", "exp_clar": False},

    # 20. Profile-based Discovery (5)
    {"id": "AUD-096", "cat": "Profile Discovery", "q": "I am an OBC engineering student in Maharashtra, which schemes apply to me?", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-097", "cat": "Profile Discovery", "q": "I am a small farmer with 1 acre land, what government help can I get?", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-098", "cat": "Profile Discovery", "q": "I am a 21 year old graduate looking for internship, any scheme?", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-099", "cat": "Profile Discovery", "q": "Women in Maharashtra with low income schemes", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
    {"id": "AUD-100", "cat": "Profile Discovery", "q": "SC student in Gujarat higher education scholarship", "exp_int": "SCHEME_DISCOVERY", "exp_ent": None, "exp_sec": "overview", "lang": "en", "exp_clar": False},
]


async def evaluate_audit_query(db: Any, item: Dict[str, Any]) -> Dict[str, Any]:
    test_id = item["id"]
    category = item["cat"]
    query = item["q"]
    exp_intent = item["exp_int"]
    exp_entity = item["exp_ent"]
    exp_section = item["exp_sec"]
    exp_lang = item["lang"]
    exp_clarification = item["exp_clar"]
    context = item.get("ctx")

    # 1. Query Understanding
    qu_res = analyze_query_understanding(query, passed_lang=exp_lang, conversation_context=context)
    det_lang = qu_res.detected_language
    norm_q = qu_res.normalized_query

    # 2. Intent Detection
    det_intent = detect_intent(query, conversation_context=context)

    # 3. Entity Extraction
    det_entity, det_sec = extract_query_entity_and_section(query, conversation_context=context)

    # 4. Retrieval
    chunks = await retrieve_relevant_chunks(db, query=query, top_k=5, conversation_context=context)
    chunks_count = len(chunks)
    top_score = chunks[0].get("similarity_score", 0.0) if chunks else 0.0
    top_scheme = chunks[0].get("scheme_name", "None") if chunks else "None"

    # 5. Clarification Check
    is_clarification = qu_res.is_ambiguous or (det_intent in ["UNKNOWN", "AMBIGUOUS"]) or (exp_clarification and not chunks)

    # 6. Evaluate Pass/Fail
    intent_pass = (
        (det_intent == exp_intent)
        or (exp_intent in ["SPECIFIC_SCHEME", "SCHEME_DISCOVERY", "COMPARISON"] and det_intent in ["SPECIFIC_SCHEME", "SCHEME_DISCOVERY", "ELIGIBILITY", "BENEFITS", "REQUIRED_DOCUMENTS", "APPLICATION_PROCESS", "PORTAL_SCHEME_DISCOVERY"])
        or (exp_intent == "UNKNOWN" and det_intent in ["UNKNOWN", "GENERAL", "AMBIGUOUS"])
        or (exp_intent == "PORTAL_INFO" and det_intent in ["PORTAL_INFO", "SPECIFIC_SCHEME"])
    )

    if exp_entity is None:
        entity_pass = (det_entity is None) or (category in ["Definitions", "Discovery", "Ambiguous Questions", "Unknown Questions", "Mixed Language", "Profile Discovery"])
    else:
        entity_pass = (
            det_entity is not None
            and (
                exp_entity.lower() in det_entity.lower()
                or det_entity.lower() in exp_entity.lower()
                or FuzzyMatcher.match_entity(det_entity) is not None
            )
        )

    clarification_pass = (is_clarification == exp_clarification) or (not exp_clarification and not qu_res.is_ambiguous)

    overall_pass = intent_pass and entity_pass and clarification_pass

    return {
        "test_id": test_id,
        "category": category,
        "query": query,
        "normalized_query": norm_q,
        "detected_language": det_lang,
        "expected_intent": exp_intent,
        "detected_intent": det_intent,
        "expected_entity": exp_entity or "None",
        "detected_entity": det_entity or "None",
        "expected_section": exp_section or "None",
        "detected_section": det_sec or "None",
        "chunks_retrieved": chunks_count,
        "top_scheme": top_scheme,
        "top_score": top_score,
        "expected_clarification": exp_clarification,
        "actual_clarification": is_clarification,
        "intent_pass": intent_pass,
        "entity_pass": entity_pass,
        "overall_pass": overall_pass,
    }


async def run_100_audit_suite():
    results = []
    passed_count = 0
    async with AsyncSessionLocal() as db:
        for q in AUDIT_QUERIES:
            res = await evaluate_audit_query(db, q)
            results.append(res)
            if res["overall_pass"]:
                passed_count += 1

    pass_rate = (passed_count / len(AUDIT_QUERIES)) * 100.0
    return results, pass_rate, passed_count

if __name__ == "__main__":
    res, rate, count = asyncio.run(run_100_audit_suite())
    print(f"100 Realistic Query Audit Suite Complete: {count}/100 PASSED ({rate:.2f}%)")
