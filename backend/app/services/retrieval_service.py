"""Retrieval Service — Schemora RAG Pipeline.

Retrieves the most semantically relevant knowledge chunks for a user query.

Strategy:
  1. Detect query intent (SCHEME_DISCOVERY, ELIGIBILITY, APPLICATION_PROCESS, etc.)
  2. Expand query with synonyms based on intent.
  3. Embed the user query (dense embedding OR TF-IDF fallback).
  4. Load all stored chunk embeddings from the DB.
  5. Compute cosine similarity between query and each chunk.
  6. Apply section-affinity boost based on detected intent.
  7. Apply keyword matching boost for scheme title, category, and state.
  8. Return top-K chunks with metadata for the Groq prompt.

Filtering:
  - scheme_id: restrict to a specific scheme's chunks
  - state: restrict to state-specific or central schemes
  - category: restrict to a scheme category (Scholarship, Agriculture, etc.)
  - section: restrict to specific section type

Intent detection ensures that:
  - "What documents do I need?" → boosts 'documents' section chunks
  - "How do I apply?" → boosts 'application' section chunks
  - "What benefits?" → boosts 'benefits' section chunks
  - "Am I eligible?" → boosts 'eligibility' section chunks
  - "Tell me OBC schemes" → boosts 'overview'+'eligibility' section chunks

This dramatically improves retrieval quality without requiring semantic embeddings.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.knowledge import KnowledgeChunk
from app.services import vector_service
from app.services.embedding_service import (
    embed_text,
    json_to_embedding,
    is_dense_embedding,
    cosine_similarity_dense,
    cosine_similarity_tfidf,
)
from app.services.query_understanding_service import (
    analyze_query_understanding,
    normalize_text,
    FuzzyMatcher,
    QueryUnderstandingResult,
)

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 8
MIN_SIMILARITY_THRESHOLD = 0.03  # Lowered: TF-IDF scores are naturally low


# ── Intent Detection ──────────────────────────────────────────────────────────

INTENT_PATTERNS = {
    "GREETING": [
        r"^(?:hi|hello|hey|greetings|namaste|namaskar|good\s*(?:morning|afternoon|evening)|hallo|hola|ssa|satsriakal|hi+|hello+)\b",
        r"\bwho\s+are\s+you\b",
        r"\bwhat\s+can\s+you\s+do\b",
        r"\bhow\s+are\s+you\b",
        r"\bhelp\b",
    ],
    "THANKS": [
        r"^(?:thanks|thank\s*you|shukriya|dhanyawad|thx|dhanbad)\s*$",
        r"\bthank\s*you\b",
    ],
    "GOODBYE": [
        r"^(?:bye|goodbye|cya|see\s*you|take\s*care|alvida|tata|tata\s*bye|bye\s*bye)\s*[\!\?\,\.]*$",
        r"\bbye\s*bye\b", r"\bgoodbye\b",
    ],
    # REQUIRED_DOCUMENTS checked FIRST — before APPLICATION_PROCESS
    # so "what documents are required" doesn't match 'required' → APPLICATION_PROCESS
    "REQUIRED_DOCUMENTS": [
        r"\bdocuments?\b", r"\bpaper\b", r"\bcertificate\b",
        r"\bchecklist\b", r"\bupload\b", r"\bproof\b", r"\bkyc\b",
        r"\bpapers?\b",
        r"\bwhat.*need\b",   # "what do I need"
        r"\bwhat.*require\b",  # "what are the requirements / required docs"
        r"\brequired.*doc\b",  # "required documents"
        r"\bdoc.*needed?\b",  # "documents needed"
    ],
    "APPLICATION_PROCESS": [
        r"\bhow.*(?:do|can|should|to).*apply\b",
        r"\bprocess\b",
        r"\bprocedure\b",
        r"\bfill\b",
        r"\bfilling\b",
        r"\bhow.*fill\b",
        r"\bapplication.*process\b",
        r"\bstep.*(?:apply|fill|submit|register)\b",
        r"\bsubmit.*application\b",
        r"\bregister.*(?:on|at|in|for)?\b",
        r"\bsteps?.*scholarship\b",
        r"\bsteps?.*apply\b",
        r"\bapply.*online\b",
        r"\bapplication.*form\b",
        r"\bscholarship.*form\b",
        r"\bhow.*to.*(?:fill|apply|register|submit)\b",
    ],
    "APPLICATION_CHANNEL": [
        r"\bwhere.*(?:apply|submit|register)\b",
        r"\boffline.*apply\b",
        r"\bcsc\b",
        r"\bcommon\s+service\s+centre\b",
        r"\bjan\s+seva\s+kendra\b",
        r"\bonline.*portal\b",
        r"\bapplication.*centre\b",
        r"\bapply.*office\b",
    ],
    "ELIGIBILITY": [
        r"\bam i (?:eligible|qualified|fit)\b",
        r"\bcan i (?:get|apply|qualify|receive)\b",
        r"\bwho (?:can|is|are) eligible\b",
        r"\beligib\w*", r"\bqualif\w*", r"\bcriteria\b",
        r"\bfor whom\b",
    ],
    "BENEFITS": [
        r"\bbenefits?\b", r"\bamount\b", r"\bstipend\b",
        r"\bgrant\b", r"\bhow much\b", r"\brupees?\b", r"\binr\b",
        r"\bfinancial.*help\b", r"\bfinancial.*assist\b", r"\bfinancial.*support\b",
        r"\bprovide\b", r"\bgive.*money\b", r"\bget.*money\b",
        r"\bcan.*i get\b",
        r"\bsupport.*studying\b", r"\bhelp.*studying\b",
        r"\bscholarship.*amount\b", r"\bmoney.*stud\b",
    ],
    "FINANCIAL_DETAILS": [
        r"\bhow\s+much\s+(?:money|amount|rupees?|inr)\b",
        r"\bexact\s+amount\b",
        r"\bhow\s+much.*(?:give|get|receive|pay)\b",
        r"\bper\s+(?:month|year|annum|annual)\b",
        r"\bmonthly\s+(?:amount|stipend|grant|pension)\b",
        r"\bannual\s+(?:amount|stipend|grant|income)\b",
        r"\bfinancial\s+details\b",
        r"\bcoverage\s+amount\b",
        r"\b(?:subsidy|discount)\s+(?:amount|percentage|%)\b",
    ],
    "DEADLINE": [
        r"\bdeadline\b", r"\blast date\b",
        r"\bwindow\b", r"\bapply.*by\b", r"\bopen.*till\b",
        r"\bwhen.*apply\b", r"\bclose.*date\b",
    ],
    "STATUS": [
        r"\bstatus\b", r"\btrack\b", r"\breminder\b", r"\bbookmark\b",
        r"\bactive\b", r"\bcurrent\b", r"\bis.*(?:open|active|running|closed|available)\b",
        r"\bstill.*(?:active|available|open)\b",
    ],
    "RENEWAL": [
        r"\brenew\w*\b",
        r"\bcan.*renew\b",
        r"\bhow.*renew\b",
        r"\brenew.*scholarship\b",
        r"\bscholarship.*renew\b",
        r"\bnext\s+year.*scholarship\b",
        r"\bagain.*apply\b",
        r"\bre.?apply\b",
        r"\bnवीनीकरण\b", r"\brenewwal\b",
    ],
    "FAQ": [
        r"\bfaq\b",
        r"\bfrequently\s+asked\b",
        r"\bcommon\s+questions?\b",
        r"\bquestions?.*about\b",
        r"\bpeople\s+also\s+ask\b",
    ],
    "CONTACT": [
        r"\bhelpline\b",
        r"\bphone\s+number\b",
        r"\bcontact.*number\b",
        r"\bemail\b",
        r"\bgrievance\b",
        r"\bcontact\b",
        r"\bwhom.*contact\b",
        r"\bwho.*contact\b",
        r"\bcall.*(?:number|helpline)\b",
    ],
    "COMPARISON": [
        r"\bcompare\b",
        r"\bvs\.?\b", r"\bversus\b",
        r"\bdifference\s+between\b",
        r"\bbetter.*(?:scheme|scholarship|yojana)\b",
        r"\bwhich.*better\b",
    ],
    "SPECIFIC_SCHEME": [
        # Covered by entity extraction; this is a fallback pattern
    ],
}

# Map intent to preferred sections for scoring boost
INTENT_SECTION_BOOST = {
    "DEFINITION_CONCEPT":    {"concept": 0.45, "glossary": 0.45, "overview": 0.15},
    "REQUIRED_DOCUMENTS":    {"documents": 0.35, "application": 0.15, "overview": 0.05},
    "APPLICATION_PROCESS":   {"application": 0.35, "documents": 0.15, "overview": 0.10},
    "APPLICATION_CHANNEL":   {"application_channels": 0.40, "application": 0.20, "contact": 0.10},
    "ELIGIBILITY":           {"eligibility": 0.25, "beneficiaries": 0.15, "overview": 0.10},
    "BENEFITS":              {"benefits": 0.30, "financial_details": 0.15, "overview": 0.10},
    "FINANCIAL_DETAILS":     {"financial_details": 0.40, "benefits": 0.20, "overview": 0.05},
    "DEADLINE":              {"deadlines": 0.30, "status": 0.15, "application": 0.10},
    "STATUS":                {"status": 0.35, "deadlines": 0.15, "notes": 0.10},
    "RENEWAL":               {"renewal": 0.40, "deadlines": 0.15, "application": 0.10},
    "FAQ":                   {"faqs": 0.40, "overview": 0.10},
    "CONTACT":               {"contact": 0.50, "notes": 0.10, "overview": 0.05},
    "COMPARISON":            {"overview": 0.20, "benefits": 0.15, "eligibility": 0.10},
    "SPECIFIC_SCHEME":       {"overview": 0.35, "benefits": 0.10, "objective": 0.10},
    "SCHEME_DISCOVERY":      {"overview": 0.20, "eligibility": 0.10, "benefits": 0.10},
    "GENERAL":               {"overview": 0.10},
}

# Map intent to query expansion terms (improves TF-IDF recall)
INTENT_QUERY_EXPANSIONS = {
    "DEFINITION_CONCEPT":    " definition concept meaning glossary explanation government scheme beneficiary eligibility subsidy financial assistance",
    "REQUIRED_DOCUMENTS":    " required documents certificate aadhaar marksheet income caste domicile disability proof checklist",
    "APPLICATION_PROCESS":   " apply application process portal steps online register procedure fill form guidelines nsp scholarships",
    "APPLICATION_CHANNEL":   " where apply online offline csc common service centre jan seva kendra portal website tehsil",
    "ELIGIBILITY":           " eligible eligibility criteria who can apply conditions requirements income age caste gender",
    "BENEFITS":              " benefits financial assistance amount scholarship grant stipend coverage",
    "FINANCIAL_DETAILS":     " amount rupees inr monthly annual stipend grant subsidy coverage financial details",
    "DEADLINE":              " deadline date window opens closes application cycle last date",
    "STATUS":                " status active closed open running available current",
    "RENEWAL":               " renew renewal annual reapply next year continuation re-apply nsp",
    "FAQ":                   " faq questions answers common frequently asked",
    "CONTACT":               " helpline phone number email contact grievance portal",
    "COMPARISON":            " compare vs versus difference between benefits eligibility overview",
    "SPECIFIC_SCHEME":       " overview description objective purpose benefits eligibility",
    "SCHEME_DISCOVERY":      " scheme scholarship overview category description list available",
}

# Social category synonyms for better OBC/SC/ST retrieval
SOCIAL_CATEGORY_SYNONYMS = {
    "obc": "OBC other backward class caste backward",
    "sc": "SC scheduled caste dalit",
    "st": "ST scheduled tribe tribal adivasi",
    "general": "general open category",
    "ews": "EWS economically weaker section",
    "minority": "minority religion muslim christian sikh",
}


CONCEPT_KEYWORDS = [
    "scheme", "schemes", "government scheme", "government schemes", "yojana", "yojna",
    "central scheme", "central government scheme", "state scheme", "state government scheme",
    "eligibility", "eligibility criteria", "beneficiary", "beneficiaries", "benefit", "benefits",
    "document", "documents", "documents required", "application process", "subsidy", "subsidies",
    "financial assistance", "financial aid", "welfare program", "welfare scheme",
    "scholarship", "scholarships", "dbt", "direct benefit transfer",
    "income certificate", "caste certificate", "domicile certificate", "residence certificate",
    "disability certificate", "udid", "renewal", "csc", "common service centre",
    "योजना", "सरकारी योजना", "केंद्र सरकार की योजना", "राज्य सरकार की योजना", "पात्रता", "लाभार्थी", "लाभ", "आवश्यक दस्तावेज", "आवेदन प्रक्रिया", "सब्सिडी", "वित्तीय सहायता",
    "छात्रवृत्ति", "प्रत्यक्ष लाभ अंतरण", "आय प्रमाण पत्र", "जाति प्रमाण पत्र", "निवास प्रमाण पत्र", "नवीनीकरण",
    "યોજના", "સરકારી યોજના", "કેન્દ્ર સરકારની યોજના", "રાજ્ય સરકારની યોજના", "પાત્રતા", "લાભાર્થી", "લાભો", "જરૂરી દસ્તાવેજો", "અરજી પ્રક્રિયા", "સબસીડી", "નાણાકીય સહાય",
    "શિષ્યવૃત્તિ", "ડાયરેક્ટ બેનિફિટ ટ્રાન્સફર", "આવક પ્રમાણ પત્ર", "જ્ઞાતિ પ્રમાણ પત્ર", "ડોમિસાઇલ", "નવીકરણ",
]

KNOWN_SPECIFIC_SCHEME_TITLES = [
    "pm-kisan", "pm kisan", "kisan samman", "pm internship", "post matric", "post-matric",
    "pre matric", "pre-matric", "nsp", "sukanya samriddhi", "ayushman bharat", "pmegp",
    "mudra", "mysy", "ladki bahin", "pudhumai penn", "gruha lakshmi", "samarth",
]


def is_definition_query(query: str) -> bool:
    """Semantic detector for definition and conceptual questions about government schemes."""
    q = query.lower().strip()

    # 1. Exclusion Check: If query mentions a specific known scheme instance, it's a specific scheme query
    for title in KNOWN_SPECIFIC_SCHEME_TITLES:
        if title in q:
            return False

    # 2. Exclusion Check: If query has demographic target filters ("for students", "for farmers") or list requests
    demographic_patterns = [
        r"\bfor\s+(?:students?|farmers?|women|female|girls?|obc|sc|st|ews|minorities?|seniors?|entrepreneurs?|single\s+girl)\b",
        r"\b(?:students?|farmers?|women|female|girls?|obc|sc|st|ews|minorities?|seniors?|entrepreneurs?)\s+schemes?\b",
        r"\bfor\s+(?:विद्यार्थी|किसान|महिला|छात्र|વિદ્યાર્થીઓ|ખેડૂતો|મહિલાઓ)\b",
    ]
    has_demographic = any(re.search(pat, q) for pat in demographic_patterns)
    is_list_request = any(lr in q for lr in ["available", "list of", "list all", "show me", "find schemes", "which schemes", "schemes for"])
    if has_demographic or is_list_request:
        return False

    # 3. Generalized Definitional Intent Triggers (English, Hindi, Gujarati, Marathi, etc.)
    def_triggers = [
        r"\bwhat\s+is\b", r"\bwhat\s+are\b", r"\bwhat\s+does\b", r"\bwhat\s+do\b",
        r"\bwhat\s+is\s+meant\b", r"\bmeant\s+by\b", r"\bmeaning\s+of\b", r"\bterm\b",
        r"\bdefine\b", r"\bdefinition\b", r"\bmeaning\b", r"\bmeanings\b",
        r"\bmean\b", r"\bmeans\b", r"\brefer\s+to\b", r"\brefers\s+to\b",
        r"\bexplain\b", r"\bunderstand\b", r"\bclarify\b", r"\bdescribe\b",
        r"क्या\s+है", r"क्या\s+होती\s+है", r"क्या\s+होता\s+है", r"का\s+अर्थ", r"का\s+मतलब",
        r"क्या\s+मतलब", r"मतलब", r"परिभाषा", r"किसे\s+कहते", r"अभिप्राय", r"समझाएं", r"किसे\s+बोलते",
        r"શું\s+છે", r"એટલે\s+શું", r"અર્થ", r"વ્યાખ્યા", r"સમજાવો",
        r"म्हणजे\s+काय", r"अर्थ\s+काय", r"स्पष्ट\s+करा",
    ]

    has_def_trigger = any(re.search(pat, q) for pat in def_triggers)
    if any(w in q for w in ["meaning", "mean", "means", "define", "definition", "explain", "describe", "परिभाषा", "વ્યાખ્યા", "अर्थ", "अभिप्राय", "मतलब"]):
        has_def_trigger = True

    # 4. Check if subject is a concept keyword
    has_concept_keyword = any(ck in q for ck in CONCEPT_KEYWORDS)

    if has_def_trigger and has_concept_keyword:
        return True

    # Standalone phrase like "government schemes means?", "what is a scheme?", "what is subsidy?", "what is eligibility?"
    if re.search(r"^\s*(?:what\s+(?:is|are)\s+(?:a\s+|an\s+|the\s+)?)?(?:government\s+)?(?:scheme|schemes|yojana|subsidy|beneficiary|eligibility|financial assistance)\s*(?:means?|meaning|definition)?[\?\!\.\s]*$", q):
        return True

    return False


def extract_query_entity_and_section(
    query: str, conversation_context: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Extract specific scheme entity title (if present) and requested section type from query using Query Understanding layer.

    Returns:
        (entity_name, section_type)
    """
    qu_res = analyze_query_understanding(query, conversation_context=conversation_context)
    q_norm = qu_res.normalized_query

    # 1. Identify Target Section
    section = None
    if any(w in q_norm for w in ["document", "documents", "paper", "papers", "certificate", "proof", "kyc"]):
        section = "documents"
    elif any(w in q_norm for w in ["apply", "application", "step", "steps", "procedure", "process", "fill", "filling", "register", "how to"]):
        section = "application"
    elif any(w in q_norm for w in ["eligible", "eligibility", "criteria", "qualify", "requirement", "requirements", "patrata"]):
        section = "eligibility"
    elif any(w in q_norm for w in ["benefit", "benefits", "amount", "stipend", "grant", "money", "financial", "rupees"]):
        section = "benefits"
    elif any(w in q_norm for w in ["deadline", "last date", "close date", "window"]):
        section = "deadlines"

    # 2. Identify Entity via Entity Matcher
    if qu_res.entity_match and qu_res.entity_match.confidence_level in ["HIGH", "MEDIUM"]:
        ent = qu_res.entity_match.entity
        if ent.entity_type in ["SCHEME", "PORTAL"]:
            return ent.canonical_name, section

    # Fallback to existing entity patterns for any legacy scheme titles
    scheme_entity_patterns = [
        ("PM-KISAN", r"(?:pm[-_\s]*kisan|kisan\s+samman|pm\s+kisan)"),
        ("PM Internship Scheme", r"(?:pm[-_\s]*internship|prime\s+minister\s+internship)"),
        ("Post-Matric Scholarship for Scheduled Caste Students", r"(?:post[-_\s]*matric|postmatric)"),
        ("Pre-Matric Scholarship for Scheduled Caste Students", r"(?:pre[-_\s]*matric|prematric)"),
        ("PM YASASVI Scholarship Scheme", r"(?:pm[-_\s]*yasasvi|yasasvi)"),
        ("Central Sector Scheme of Scholarship", r"(?:central\s+sector\s+schol|csss)"),
        ("Atal Pension Yojana", r"(?:atal\s+pension|apy)"),
        ("Ayushman Bharat PM-JAY", r"(?:ayushman|pm[-_\s]*jay|pmjay|jan\s+arogya)"),
        ("Gujarat Farmers Debt Relief Scheme", r"(?:gujarat\s+farmers?|debt\s+relief)"),
        ("Ladki Bahin Scheme", r"(?:ladki\s+bahin|mukhyamantri\s+ladki)"),
        ("Lakhpati Didi Scheme", r"(?:lakhpati\s+didi)"),
        ("Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)", r"(?:mysy|yuva\s+swavalamban)"),
        ("Sukanya Samriddhi Yojana", r"(?:sukanya\s+samriddhi|ssy)"),
        ("Pradhan Mantri Matru Vandana Yojana (PMMVY)", r"(?:pmmvy|matru\s+vandana|pradhan\s+mantri\s+matru)"),
        ("Pradhan Mantri Awas Yojana (Urban)", r"(?:pmay[-_\s]*urban|pm\s+awas.*urban|awas\s+yojana.*urban)"),
        ("Pradhan Mantri Awas Yojana (Gramin)", r"(?:pmay[-_\s]*gramin|pm\s+awas.*gramin|pradhan\s+mantri\s+awas.*gramin)"),
        ("Pradhan Mantri MUDRA Yojana", r"(?:mudra|pmmy|pradhan\s+mantri\s+mudra)"),
        ("PM Vishwakarma Scheme", r"(?:vishwakarma|pm\s+vishwakarma)"),
        ("Pradhan Mantri Fasal Bima Yojana (PMFBY)", r"(?:fasal\s+bima|pmfby|crop\s+insurance)"),
        ("PM Vidyalaxmi Scheme", r"(?:vidyalaxmi|pm\s+vidyalaxmi)"),
        ("Pradhan Mantri Jan Dhan Yojana", r"(?:jan\s+dhan|pmjdy)"),
        ("Stand Up India Scheme", r"(?:stand\s*up\s*india)"),
        ("Kisan Credit Card", r"(?:kisan\s+credit\s+card|kcc)"),
        ("National Pension System for Traders", r"(?:nps\s+traders|pension.*traders|traders.*pension)"),
        ("PM POSHAN Shakti Nirman Scheme", r"(?:pm\s+poshan|mid\s+day\s+meal|mdm)"),
    ]

    for canonical_name, pattern in scheme_entity_patterns:
        if re.search(pattern, q_norm, re.IGNORECASE):
            return canonical_name, section

    return None, section


def detect_intent(query: str, conversation_context: Optional[Dict[str, Any]] = None) -> str:
    """Detect the primary intent of the user's query using Query Understanding layer."""
    qu_res = analyze_query_understanding(query, conversation_context=conversation_context)

    if qu_res.is_ambiguous:
        return "AMBIGUOUS"

    norm_q = qu_res.normalized_query

    # Priority 1: Greetings, Goodbye & Thanks
    for pat in INTENT_PATTERNS["GREETING"]:
        if re.search(pat, norm_q):
            return "GREETING"
    for pat in INTENT_PATTERNS["THANKS"]:
        if re.search(pat, norm_q):
            return "THANKS"
    for pat in INTENT_PATTERNS.get("GOODBYE", []):
        if re.search(pat, norm_q):
            return "GOODBYE"

    # Priority 1.5: Portal Entities
    if qu_res.entity_match and qu_res.entity_match.entity.entity_type == "PORTAL":
        if any(w in norm_q for w in ["apply", "application", "register", "fill", "how to"]):
            return "PORTAL_APPLICATION"
        elif any(w in norm_q for w in ["scheme", "schemes", "scholarship", "scholarships", "list", "available"]):
            return "PORTAL_SCHEME_DISCOVERY"
        else:
            return "PORTAL_INFO"

    # Priority 2: DEFINITION_CONCEPT check before broad scheme discovery
    if is_definition_query(norm_q):
        return "DEFINITION_CONCEPT"

    # Priority 3: Comparison
    for pat in INTENT_PATTERNS["COMPARISON"]:
        if re.search(pat, norm_q):
            return "COMPARISON"

    # Priority 4: Specific Action Intents (ordered by specificity)
    for intent in [
        "REQUIRED_DOCUMENTS", "APPLICATION_CHANNEL", "APPLICATION_PROCESS",
        "FINANCIAL_DETAILS", "ELIGIBILITY", "BENEFITS",
        "RENEWAL", "CONTACT", "FAQ", "DEADLINE", "STATUS",
    ]:
        patterns = INTENT_PATTERNS.get(intent, [])
        for pat in patterns:
            if re.search(pat, norm_q):
                return intent

    # Priority 5: SCHEME_DISCOVERY broad query detection & demographic discovery
    broad_patterns = [
        r"\bwhat\s+schemes?\b",
        r"\bschemes?\s+available\b",
        r"\b(?:list|show|find|tell|all)\b.*(?:schemes?|scholarships?|yojana)\b",
        r"योजनाएं", r"छात्रवृत्ति", r"યોજનાઓ", r"સરકારી\s+યોજનાઓ"
    ]
    for bp in broad_patterns:
        if re.search(bp, norm_q):
            return "SCHEME_DISCOVERY"

    # "which scholarships/schemes can I apply for?" or "schemes for students/farmers"
    if re.search(r"\bwhich\b", norm_q) and re.search(r"\b(?:scholarships?|schemes?|programs?|yojana)\b", norm_q):
        return "SCHEME_DISCOVERY"
    if any(dk in norm_q for dk in ["for students", "for farmers", "for women", "for obc", "for sc", "for st", "scholarship", "scholarships"]):
        return "SCHEME_DISCOVERY"
    if qu_res.detected_state:
        return "SCHEME_DISCOVERY"

    # Priority 6: SPECIFIC_SCHEME — if there's a named entity and no other intent matched
    if qu_res.entity_match and qu_res.entity_match.entity.entity_type == "SCHEME":
        return "SPECIFIC_SCHEME"

    # Priority 7: Unknown / Low confidence with no intent keywords matched
    if qu_res.confidence_level in ["LOW", "UNKNOWN"] and not is_definition_query(norm_q):
        return "UNKNOWN"

    return "GENERAL"



DEMOGRAPHIC_EXPANSIONS = {
    "women": " women female girl mahila kanya lady daughter empowerment maternity matru ladki bahin tread ",
    "female": " women female girl mahila kanya lady daughter empowerment maternity matru ladki bahin tread ",
    "girl": " women female girl mahila kanya lady daughter empowerment sukanya ",
    "mahila": " women female girl mahila kanya lady daughter empowerment maternity matru ladki bahin ",
    "farmer": " farmer kisan agriculture crop farming landholding agriculture livestock sinchayee ",
    "kisan": " farmer kisan agriculture crop farming landholding agriculture livestock sinchayee ",
    "health": " health medical hospital ayushman doctor clinic treatment janaushadhi ",
    "business": " business entrepreneur mudra loan credit msme startup vendor tread vishwakarma pmegp ",
    "senior": " senior citizen pension elderly aging old age vayoshri atal ",
}


def expand_query(query: str, intent: str) -> str:
    """Expand query with relevant terms based on intent, script translation, and social/demographic category mentions."""
    from app.services.language_service import language_registry
    spec = language_registry.detect_language(query)
    base_query = language_registry.translate_query_for_retrieval(query, spec)

    q_lower = query.lower()

    # Demographic category expansion (e.g. women, farmer, health, etc.)
    demo_expansion = ""
    for kw, exp in DEMOGRAPHIC_EXPANSIONS.items():
        if kw in q_lower:
            demo_expansion += exp

    # Social category expansion (OBC, SC, ST, EWS)
    social_expansion = ""
    for category, synonyms in SOCIAL_CATEGORY_SYNONYMS.items():
        if category in q_lower:
            social_expansion += f" {synonyms}"
            break

    # Intent-based expansion (avoid appending 'scholarship' if user didn't ask for scholarship)
    intent_expansion = INTENT_QUERY_EXPANSIONS.get(intent, "")
    if "scholarship" in intent_expansion and "scholarship" not in q_lower:
        intent_expansion = intent_expansion.replace("scholarship", "")

    return f"{base_query} {demo_expansion} {social_expansion} {intent_expansion}".strip()


# ── Keyword Boost ─────────────────────────────────────────────────────────────

def _compute_keyword_boost(query: str, chunk: KnowledgeChunk) -> float:
    """Calculate a keyword matching boost to enhance retrieval quality.

    Works for both TF-IDF and dense embedding modes.
    Intent-aware section boosts are applied separately.
    """
    q_lower = query.lower()
    q_words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    if not q_words:
        return 0.0

    stop_words = {
        "the", "and", "for", "are", "that", "with", "from", "this",
        "can", "have", "about", "what", "how", "tell", "show", "give",
        "please", "need", "want", "like", "does", "should", "which",
        "scheme", "schemes", "program", "programs", "yojana", "related",
    }
    q_words = [w for w in q_words if w not in stop_words]

    boost = 0.0
    scheme_name = (chunk.scheme_name or "").lower()
    category = (chunk.category or "").lower()
    section = (chunk.section or "").lower()
    content = (chunk.content or "").lower()
    state = (chunk.state or "").lower()

    full_chunk_text = f"{scheme_name} {category} {content}"

    # High-precision demographic domain boosts
    if any(w in q_lower for w in ["women", "female", "girl", "mahila", "kanya", "lady", "daughter"]):
        women_keywords = ["women", "female", "mahila", "ladki", "girl", "kanya", "matru", "maternity", "pudhumai", "gruha", "sukanya", "tread", "womenempowerment"]
        if any(kw in full_chunk_text for kw in women_keywords):
            boost += 0.45

    if any(w in q_lower for w in ["farmer", "kisan", "agri", "crop", "farm", "krishi"]):
        farmer_keywords = ["kisan", "farmer", "agri", "crop", "irrigation", "livestock", "matsya", "raitha", "sinchayee", "mechanization", "agriculture", "fasal", "bima", "kusum", "samman"]
        if any(kw in full_chunk_text for kw in farmer_keywords):
            boost += 0.45

    if any(w in q_lower for w in ["health", "medical", "hospital", "doctor"]):
        health_keywords = ["health", "ayushman", "medical", "doctor", "janani", "clinic", "janaushadhi", "pmssy", "nhm"]
        if any(kw in full_chunk_text for kw in health_keywords):
            boost += 0.45

    if any(w in q_lower for w in ["business", "mudra", "loan", "entrepreneur", "startup", "msme"]):
        biz_keywords = ["mudra", "business", "msme", "entrepreneur", "startup", "vendor", "tread", "vishwakarma", "pmegp", "credit", "microfinance"]
        if any(kw in full_chunk_text for kw in biz_keywords):
            boost += 0.45

    if any(w in q_lower for w in ["senior", "pension", "elderly"]):
        senior_keywords = ["pension", "senior", "elderly", "vayoshri", "atal", "apy", "scss"]
        if any(kw in full_chunk_text for kw in senior_keywords):
            boost += 0.45

    # Penalty for generic glossary definition chunks during scheme discovery queries
    if category in ["glossary"] or scheme_name == "schemora knowledge glossary":
        if any(w in q_lower for w in ["farmer", "student", "women", "give me", "list", "available", "schemes related", "schemes for"]):
            boost -= 0.35

    # Standard word matches
    for w in q_words:
        if w in scheme_name:
            boost += 0.15
        if w in category:
            boost += 0.12
        if w in section:
            boost += 0.05
        if state and w in state:
            boost += 0.10
        if w in content:
            boost += 0.03

    return min(0.60, boost)


# ── Main Retrieval ────────────────────────────────────────────────────────────

async def retrieve_relevant_chunks(
    db: AsyncSession,
    query: str,
    scheme_id: Optional[str] = None,
    state: Optional[str] = None,
    category: Optional[str] = None,
    section: Optional[str] = None,
    top_k: int = DEFAULT_TOP_K,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve the most relevant knowledge chunks for a user query.

    Integrates Query Understanding, State extraction, Observability logging, and
    Strict Retrieval Safety (blocks unrestricted vector search for LOW/UNKNOWN confidence queries).
    """
    # 1. Run Query Understanding Analysis
    qu_res = analyze_query_understanding(query, conversation_context=conversation_context)

    # State filter override if query specifies state (e.g. "Maharastra schemes")
    if not state and qu_res.detected_state:
        state = qu_res.detected_state

    # 2. Observability Logging (Requirement 21)
    logger.info(
        f"[Query Understanding Observability] "
        f"original_query='{query}' | "
        f"normalized_query='{qu_res.normalized_query}' | "
        f"detected_language='{qu_res.detected_language}' | "
        f"corrected_keywords={qu_res.corrected_keywords} | "
        f"detected_entity={qu_res.entity_match.entity.canonical_name if qu_res.entity_match else None} | "
        f"entity_type={qu_res.entity_match.entity.entity_type if qu_res.entity_match else None} | "
        f"entity_confidence={qu_res.entity_confidence} ({qu_res.confidence_level}) | "
        f"is_ambiguous={qu_res.is_ambiguous} | "
        f"detected_state={qu_res.detected_state}"
    )

    # 3. Detect intent using Query Understanding
    intent = detect_intent(query, conversation_context=conversation_context)

    # Dual-Entity Comparison Handler (Part 3 requirement)
    if intent == "COMPARISON" and not scheme_id:
        from app.services.query_understanding_service import FuzzyMatcher
        matched_entities = FuzzyMatcher.extract_all_entities(query)
        if len(matched_entities) >= 2:
            logger.info(
                f"[Dual-Entity Retrieval] Comparison query detected: "
                f"{matched_entities[0].entity.canonical_name} vs {matched_entities[1].entity.canonical_name}"
            )
            comp_chunks = []
            for em in matched_entities[:2]:
                e_name = em.entity.canonical_name
                sub_chunks = await retrieve_relevant_chunks(
                    db=db,
                    query=f"{e_name} overview eligibility benefits financial assistance application",
                    top_k=4,
                    conversation_context=conversation_context,
                )
                # Filter sub_chunks to ensure they match entity
                filtered_sub = [
                    c for c in sub_chunks
                    if e_name.lower() in (c.get("scheme_name") or "").lower()
                    or (c.get("scheme_name") or "").lower() in e_name.lower()
                    or em.entity.id.lower() in (c.get("scheme_id") or "").lower()
                ]
                comp_chunks.extend(filtered_sub if filtered_sub else sub_chunks[:3])
            if comp_chunks:
                return comp_chunks

    # 4. Retrieval Safety Rule (Requirements 4, 18):
    # UNKNOWN / LOW CONFIDENCE -> NO unrestricted scheme retrieval -> Clarification
    if intent in ["UNKNOWN", "AMBIGUOUS"] or (
        qu_res.confidence_level in ["LOW", "UNKNOWN"]
        and not qu_res.entity_match
        and not qu_res.detected_state
        and intent == "GENERAL"
    ):
        logger.info(f"Retrieval Safety Triggered: Bypassing unrestricted vector retrieval for low-confidence query '{query}'")
        return []

    expanded_query = expand_query(query, intent)

    if intent == "DEFINITION_CONCEPT":
        from app.services.glossary_service import ensure_glossary_indexed
        await ensure_glossary_indexed(db)

    logger.info(f"Retrieval: intent={intent}, query='{query[:80]}'")

    # Embed the expanded query
    query_embedding, is_semantic = await embed_text(expanded_query)

    # Section boost map for this intent
    section_boosts = INTENT_SECTION_BOOST.get(intent, {})
    scored = []

    # ── Path A: Try PostgreSQL pgvector Vector Search ───────────────────────────
    if is_semantic and is_dense_embedding(query_embedding):
        where_filter = {}
        if scheme_id:
            where_filter["scheme_id"] = scheme_id
        if state:
            where_filter["state"] = state
        if category:
            where_filter["category"] = category
        if section:
            where_filter["section"] = section

        vector_results = await vector_service.query_similar_chunks_async(
            db=db,
            query_embedding=query_embedding,
            top_k=top_k * 3,
            where_filter=where_filter,
        )

        for res in vector_results:
            meta = res.get("metadata", {})
            c_section = meta.get("section", "general")
            c_scheme_id = meta.get("scheme_id", "")
            c_scheme_name = meta.get("scheme_name", "")
            c_content = res.get("document", "")

            # Create dummy chunk object for keyword boost helper
            class _TempChunk:
                pass

            tc = _TempChunk()
            tc.scheme_name = c_scheme_name
            tc.category = meta.get("category", "")
            tc.section = c_section
            tc.content = c_content
            tc.state = meta.get("state", "")

            base_score = res.get("similarity_score", 0.0)
            section_boost = section_boosts.get(c_section, 0.0)
            kw_boost = _compute_keyword_boost(expanded_query, tc)

            total_score = min(1.0, base_score + section_boost + kw_boost)
            if total_score < MIN_SIMILARITY_THRESHOLD:
                continue

            scored.append({
                "chunk_id": res.get("id"),
                "scheme_id": c_scheme_id,
                "scheme_name": c_scheme_name,
                "section": c_section,
                "content": c_content,
                "similarity_score": round(total_score, 4),
                "intent": intent,
                "source_url": meta.get("official_info_url", ""),
                "source_title": f"{c_scheme_name or 'Official'} — {c_section.title()}",
                "source_id": meta.get("source_id", ""),
                "official_app_url": meta.get("official_app_url", ""),
                "last_verified_at": meta.get("last_verified_at", "2026-08-07"),
                "scheme_version": meta.get("scheme_version", "v1"),
                "jurisdiction": meta.get("jurisdiction", ""),
                "state": meta.get("state", ""),
                "category": meta.get("category", ""),
                "is_semantic": True,
                "vector_store": "pgvector",
            })

    # ── Path B: Fallback to SQL DB Search ─────────────────────────────────────
    if not scored:
        try:
            stmt = select(KnowledgeChunk)
            if scheme_id:
                stmt = stmt.where(
                    (KnowledgeChunk.scheme_id == scheme_id)
                    | (KnowledgeChunk.scheme_id == None)
                )
            if state:
                stmt = stmt.where(
                    (KnowledgeChunk.state == state) | (KnowledgeChunk.state == None)
                )
            if category:
                stmt = stmt.where(KnowledgeChunk.category == category)
            if section:
                stmt = stmt.where(KnowledgeChunk.section == section)

            result = await db.execute(stmt)
            chunks = result.scalars().all()
        except Exception as e:
            logger.warning(f"SQL DB retrieval scan exception: {e}")
            chunks = []

        if not chunks:
            logger.info(f"No knowledge chunks found for filters: scheme_id={scheme_id}, state={state}")
            return []

        q_tokens = set(re.findall(r"\w+", expanded_query.lower()))
        for chunk in chunks:
            c_text_lower = f"{chunk.scheme_name or ''} {chunk.content or ''}".lower()
            # Fast token overlap check to skip expensive TF-IDF math for non-matching chunks
            if q_tokens and not any(t in c_text_lower for t in q_tokens if len(t) > 2):
                section_boost = section_boosts.get(chunk.section or "", 0.0)
                if section_boost <= 0:
                    continue

            stored = json_to_embedding(chunk.embedding_json)
            score = 0.0
            if stored is not None:
                chunk_is_dense = is_dense_embedding(stored)
                query_is_dense = is_dense_embedding(query_embedding)

                if query_is_dense and chunk_is_dense:
                    score = cosine_similarity_dense(query_embedding, stored)
                elif not query_is_dense and not chunk_is_dense:
                    score = cosine_similarity_tfidf(query_embedding, stored)
                else:
                    from app.services.embedding_service import _tfidf_vector
                    q_tfidf = _tfidf_vector(expanded_query) if query_is_dense else query_embedding
                    c_tfidf = _tfidf_vector(chunk.content)
                    score = cosine_similarity_tfidf(q_tfidf, c_tfidf)

            section_boost = section_boosts.get(chunk.section or "", 0.0)
            kw_boost = _compute_keyword_boost(expanded_query, chunk)
            total_score = min(1.0, score + section_boost + kw_boost)

            if total_score < MIN_SIMILARITY_THRESHOLD:
                continue

            scored.append({
                "chunk_id": chunk.id,
                "scheme_id": chunk.scheme_id,
                "scheme_name": chunk.scheme_name or "",
                "section": chunk.section or "general",
                "content": chunk.content,
                "similarity_score": round(total_score, 4),
                "intent": intent,
                "source_url": chunk.official_info_url or "",
                "source_title": f"{chunk.scheme_name or 'Official'} — {(chunk.section or 'Guideline').title()}",
                "source_id": chunk.source_id or "",
                "official_app_url": chunk.official_app_url or "",
                "last_verified_at": chunk.last_verified_at or "2026-08-07",
                "scheme_version": chunk.scheme_version or "v1",
                "jurisdiction": chunk.jurisdiction or "",
                "state": chunk.state or "",
                "category": chunk.category or "",
                "is_semantic": chunk.is_indexed,
                "vector_store": "sql_fallback",
            })

    # Sort by score descending
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)

    # For DEFINITION_CONCEPT intent, filter and return pure concept/glossary chunks
    if intent == "DEFINITION_CONCEPT":
        concept_chunks = [
            item for item in scored
            if item.get("section") in ["concept", "glossary"]
            or item.get("category") == "Glossary"
            or item.get("scheme_id") == "schemora-glossary"
        ]
        if concept_chunks:
            concept_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
            logger.info(f"Retrieved {len(concept_chunks)} authoritative glossary chunks for DEFINITION_CONCEPT query")
            return concept_chunks[:top_k]

    # Entity-Specific Retrieval Filtering Strategy
    entity, target_sec = extract_query_entity_and_section(query)
    if entity:
        ent_clean = re.sub(r"[^\w\s]", " ", entity.lower())
        raw_kws = [w for w in ent_clean.split() if len(w) > 1]
        specific_kws = [w for w in raw_kws if w not in {"pm", "scheme", "yojana", "pradhan", "mantri"}]
        entity_kw = specific_kws if specific_kws else raw_kws
        entity_matches = []
        for item in scored:
            full_text = f"{item.get('scheme_name') or ''} {item.get('scheme_id') or ''} {item.get('content') or ''}".lower()
            full_text_clean = re.sub(r"[^\w\s]", " ", full_text)
            if any(kw in full_text_clean for kw in entity_kw):
                entity_matches.append(item)

        if entity_matches:
            if target_sec:
                entity_matches.sort(
                    key=lambda x: (1 if x.get("section") == target_sec else 0, float(x.get("similarity_score") or 0.0)),
                    reverse=True
                )
            else:
                entity_matches.sort(key=lambda x: float(x.get("similarity_score") or 0.0), reverse=True)
            logger.info(f"Retrieved {len(entity_matches)} entity-filtered chunks for entity='{entity}', section='{target_sec}'")
            return entity_matches[:min(top_k, 5)]

    # Multi-Scheme Broad Query vs Specific Scheme Deduplication Strategy
    seen_schemes = set()
    seen_section_keys = set()
    deduped = []

    target_limit = max(top_k, 6) if intent == "SCHEME_DISCOVERY" else top_k

    for item in scored:
        s_id = item["scheme_id"]
        sec = item["section"]

        if intent == "SCHEME_DISCOVERY":
            # For broad discovery queries, return 1 primary overview/eligibility chunk per scheme to list multiple distinct schemes
            if s_id not in seen_schemes:
                seen_schemes.add(s_id)
                deduped.append(item)
        else:
            # For specific query types (documents, eligibility, application process), allow multiple sections per scheme
            key = (s_id, sec)
            if key not in seen_section_keys:
                seen_section_keys.add(key)
                deduped.append(item)

        if len(deduped) >= target_limit:
            break

    logger.info(
        f"Retrieved {len(deduped)} chunks for query "
        f"(intent={intent}, semantic={is_semantic}, "
        f"top_score={deduped[0]['similarity_score'] if deduped else 0})"
    )
    return deduped



async def retrieve_scheme_overview(
    db: AsyncSession,
    scheme_id: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve just the overview chunk for a specific scheme."""
    result = await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.scheme_id == scheme_id,
            KnowledgeChunk.section == "overview",
        )
    )
    chunk = result.scalar_one_or_none()
    if not chunk:
        return None
    return {
        "chunk_id": chunk.id,
        "scheme_id": chunk.scheme_id,
        "scheme_name": chunk.scheme_name,
        "content": chunk.content,
        "section": "overview",
        "source_url": chunk.official_info_url or "",
        "source_title": f"{chunk.scheme_name} — Overview",
        "last_verified_at": chunk.last_verified_at or "2026-08-07",
    }
