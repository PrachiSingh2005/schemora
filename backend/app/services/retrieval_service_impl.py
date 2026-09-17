"""Retrieval Service Implementation — Schemora RAG Pipeline."""

import re
import time
import logging
from typing import Any, Dict, List, Optional, Union, Tuple

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
from app.services.query_understanding_service_impl import (
    analyze_query_understanding,
    normalize_text,
    FuzzyMatcher,
    QueryUnderstandingResult,
    extract_profile_attributes,
)

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 8
MIN_SIMILARITY_THRESHOLD = 0.03


INTENT_PATTERNS = {
    "GREETING": [
        r"^(?:hi|hello|hey|greetings|namaste|namaskar|good\s*(?:morning|afternoon|evening))\b",
        r"\bwho\s+are\s+you\b", r"\bwhat\s+can\s+you\s+do\b", r"\bhelp\b",
    ],
    "THANKS": [
        r"^(?:thanks|thank\s*you|shukriya|dhanyawad|thx)\s*$", r"\bthank\s*you\b",
    ],
    "GOODBYE": [
        r"^(?:bye|goodbye|cya|see\s*you|take\s*care|alvida|tata)\s*$", r"\bgoodbye\b",
    ],
    "REQUIRED_DOCUMENTS": [
        r"\bdocuments?\b", r"\bpaper\b", r"\bcertificate\b", r"\bchecklist\b", r"\bproof\b", r"\bkyc\b",
    ],
    "APPLICATION_PROCESS": [
        r"\bhow.*(?:do|can|should|to).*apply\b", r"\bprocess\b", r"\bprocedure\b", r"\bhow.*fill\b",
    ],
    "APPLICATION_CHANNEL": [
        r"\bwhere.*(?:apply|submit|register)\b", r"\boffline.*apply\b", r"\bcsc\b",
    ],
    "ELIGIBILITY": [
        r"\bam i (?:eligible|qualified|fit)\b", r"\bwho (?:can|is|are) eligible\b", r"\beligib\w*",
    ],
    "BENEFITS": [
        r"\bbenefits?\b", r"\bamount\b", r"\bstipend\b", r"\bgrant\b", r"\bhow much\b",
    ],
    "FINANCIAL_DETAILS": [
        r"\bhow\s+much\s+(?:money|amount|rupees?|inr)\b", r"\bexact\s+amount\b",
    ],
    "DEADLINE": [
        r"\bdeadline\b", r"\blast date\b", r"\bwindow\b",
    ],
    "STATUS": [
        r"\bstatus\b", r"\btrack\b",
    ],
    "RENEWAL": [
        r"\brenew\w*\b",
    ],
    "FAQ": [
        r"\bfaq\b", r"\bfrequently\s+asked\b",
    ],
    "CONTACT": [
        r"\bhelpline\b", r"\bphone\s+number\b", r"\bcontact\b",
    ],
    "COMPARISON": [
        r"\bcompare\b", r"\bvs\.?\b", r"\bversus\b",
    ],
}

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
    "SCHEME_DISCOVERY":      {"overview": 0.25, "eligibility": 0.15, "benefits": 0.15},
    "GENERAL":               {"overview": 0.10},
}

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

CONCEPT_KEYWORDS = [
    "scheme", "schemes", "government scheme", "government schemes", "yojana", "yojna",
    "central scheme", "central government scheme", "state scheme", "state government scheme",
    "eligibility", "eligibility criteria", "beneficiary", "beneficiaries", "benefit", "benefits",
    "document", "documents", "application process", "subsidy", "subsidies", "financial assistance",
    "scholarship", "scholarships",
]

KNOWN_SPECIFIC_SCHEME_TITLES = [
    "pm-kisan", "pm kisan", "kisan samman", "pm internship", "post matric", "post-matric",
    "pre matric", "pre-matric", "nsp", "sukanya samriddhi", "ayushman bharat", "pmegp",
    "mudra", "mysy", "ladki bahin", "pudhumai penn", "gruha lakshmi",
]


def is_definition_query(query: str) -> bool:
    """Semantic detector for definition and conceptual questions about government schemes."""
    q = query.lower().strip()

    for title in KNOWN_SPECIFIC_SCHEME_TITLES:
        if title in q:
            return False

    profile_attrs = extract_profile_attributes(query)
    is_list_request = any(lr in q for lr in [
        "available", "list of", "list all", "show me", "find schemes", "which schemes",
        "schemes for", "give me schemes", "what schemes", "programs for", "scholarships for",
        "schemes in", "scholarships in", "schemes available"
    ])

    has_profile_target = bool(
        profile_attrs.get("occupation")
        or profile_attrs.get("gender")
        or profile_attrs.get("education")
        or profile_attrs.get("beneficiary")
        or profile_attrs.get("caste_category")
        or profile_attrs.get("state")
        or profile_attrs.get("extracted_terms")
    )

    if has_profile_target or is_list_request:
        return False

    def_triggers = [
        r"\bwhat\s+is\b", r"\bwhat\s+are\b", r"\bwhat\s+does\b", r"\bwhat\s+do\b",
        r"\bwhat\s+is\s+meant\b", r"\bmeaning\s+of\b", r"\bdefine\b", r"\bdefinition\b",
        r"\bmeaning\b", r"\bexplain\b",
    ]

    has_def_trigger = any(re.search(pat, q) for pat in def_triggers)
    if any(w in q for w in ["meaning", "mean", "means", "define", "definition", "explain"]):
        has_def_trigger = True

    has_concept_keyword = any(ck in q for ck in CONCEPT_KEYWORDS)

    if has_def_trigger and has_concept_keyword:
        return True

    if re.search(r"^\s*(?:what\s+(?:is|are)\s+(?:a\s+|an\s+|the\s+)?)?(?:government\s+)?(?:scheme|schemes|yojana|subsidy|beneficiary|eligibility)\s*(?:means?|meaning|definition)?[\?\!\.\s]*$", q):
        return True

    return False


def extract_query_entity_and_section(
    query: str, conversation_context: Optional[Dict[str, Any]] = None
) -> Tuple[Optional[str], Optional[str]]:
    qu_res = analyze_query_understanding(query, conversation_context=conversation_context)
    q_norm = qu_res.normalized_query

    section = None
    if any(w in q_norm for w in ["document", "documents", "paper", "papers", "certificate", "proof", "kyc"]):
        section = "documents"
    elif any(w in q_norm for w in ["apply", "application", "step", "steps", "procedure", "process", "fill", "register"]):
        section = "application"
    elif any(w in q_norm for w in ["eligible", "eligibility", "criteria", "qualify"]):
        section = "eligibility"
    elif any(w in q_norm for w in ["benefit", "benefits", "amount", "stipend", "grant", "money"]):
        section = "benefits"

    if qu_res.entity_match and qu_res.entity_match.confidence_level in ["HIGH", "MEDIUM"]:
        ent = qu_res.entity_match.entity
        if ent.entity_type in ["SCHEME", "PORTAL"]:
            return ent.canonical_name, section

    scheme_entity_patterns = [
        ("PM-KISAN", r"(?:pm[-_\s]*kisan|kisan\s+samman|pm\s+kisan)"),
        ("PM Internship Scheme", r"(?:pm[-_\s]*internship|prime\s+minister\s+internship)"),
        ("Post-Matric Scholarship for Scheduled Caste Students", r"(?:post[-_\s]*matric|postmatric)"),
        ("Mukhyamantri Majhi Ladki Bahin Yojana", r"(?:ladki\s+bahin|majhi\s+ladki)"),
    ]

    for canonical_name, pattern in scheme_entity_patterns:
        if re.search(pattern, q_norm, re.IGNORECASE):
            return canonical_name, section

    return None, section


def detect_intent(query: str, conversation_context: Optional[Dict[str, Any]] = None) -> str:
    """Detect the primary intent of the user's query."""
    qu_res = analyze_query_understanding(query, conversation_context=conversation_context)

    if qu_res.is_ambiguous:
        return "AMBIGUOUS"

    norm_q = qu_res.normalized_query

    for pat in INTENT_PATTERNS["GREETING"]:
        if re.search(pat, norm_q):
            return "GREETING"
    for pat in INTENT_PATTERNS["THANKS"]:
        if re.search(pat, norm_q):
            return "THANKS"
    for pat in INTENT_PATTERNS.get("GOODBYE", []):
        if re.search(pat, norm_q):
            return "GOODBYE"

    profile_attrs = extract_profile_attributes(query)
    has_profile_target = bool(
        profile_attrs.get("occupation")
        or profile_attrs.get("gender")
        or profile_attrs.get("beneficiary")
        or profile_attrs.get("caste_category")
        or profile_attrs.get("state")
        or profile_attrs.get("extracted_terms")
    )

    broad_patterns = [
        r"\bwhat\s+schemes?\b",
        r"\bschemes?\s+available\b",
        r"\b(?:list|show|find|tell|all|give\s+me)\b.*(?:schemes?|scholarships?|yojana)\b",
        r"\bschemes?\s+for\b",
        r"\bfor\s+.*\s+schemes?\b",
        r"\bschemes?\s+in\b",
        r"\b(?:give|show|find|get)\s+me\s+schemes\b",
    ]
    is_broad_discovery = any(re.search(bp, norm_q) for bp in broad_patterns)

    if is_broad_discovery or has_profile_target:
        return "SCHEME_DISCOVERY"

    if is_definition_query(norm_q):
        return "DEFINITION_CONCEPT"

    for pat in INTENT_PATTERNS["COMPARISON"]:
        if re.search(pat, norm_q):
            return "COMPARISON"

    for intent in [
        "REQUIRED_DOCUMENTS", "APPLICATION_CHANNEL", "APPLICATION_PROCESS",
        "FINANCIAL_DETAILS", "ELIGIBILITY", "BENEFITS",
        "RENEWAL", "CONTACT", "FAQ", "DEADLINE", "STATUS",
    ]:
        patterns = INTENT_PATTERNS.get(intent, [])
        for pat in patterns:
            if re.search(pat, norm_q):
                return intent

    if re.search(r"\bwhich\b", norm_q) and re.search(r"\b(?:scholarships?|schemes?|programs?|yojana)\b", norm_q):
        return "SCHEME_DISCOVERY"

    if qu_res.detected_state:
        return "SCHEME_DISCOVERY"

    if qu_res.entity_match and qu_res.entity_match.entity.entity_type == "SCHEME":
        return "SPECIFIC_SCHEME"

    if qu_res.confidence_level in ["LOW", "UNKNOWN"] and not is_definition_query(norm_q):
        return "UNKNOWN"

    return "GENERAL"


DEMOGRAPHIC_EXPANSIONS = {
    "women": " women female girl mahila kanya lady daughter empowerment maternity matru ladki bahin ",
    "female": " women female girl mahila kanya lady daughter empowerment maternity matru ladki bahin ",
    "farmer": " farmer kisan agriculture crop farming landholding agriculture livestock sinchayee ",
    "farmers": " farmer kisan agriculture crop farming landholding agriculture livestock sinchayee ",
    "kisan": " farmer kisan agriculture crop farming landholding agriculture livestock sinchayee ",
    "student": " student students scholarship post matric pre matric education ",
    "students": " student students scholarship post matric pre matric education ",
}


def expand_query(query: str, intent: str) -> str:
    from app.services.language_service import language_registry
    spec = language_registry.detect_language(query)
    base_query = language_registry.translate_query_for_retrieval(query, spec)
    q_lower = query.lower()

    demo_terms = set()
    for kw, exp in DEMOGRAPHIC_EXPANSIONS.items():
        if kw in q_lower:
            demo_terms.add(exp.strip())

    demo_expansion = " ".join(demo_terms)
    intent_expansion = INTENT_QUERY_EXPANSIONS.get(intent, "")

    return f"{base_query} {demo_expansion} {intent_expansion}".strip()


def _compute_keyword_boost(query: str, chunk: KnowledgeChunk) -> float:
    q_lower = query.lower()
    profile_attrs = extract_profile_attributes(query)

    q_words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
    stop_words = {"the", "and", "for", "are", "that", "with", "from", "this", "can", "what", "how", "tell", "show", "give", "scheme", "schemes"}
    q_words = [w for w in q_words if w not in stop_words]

    boost = 0.0
    scheme_name = (chunk.scheme_name or "").lower()
    category = (chunk.category or "").lower()
    section = (chunk.section or "").lower()
    content = (chunk.content or "").lower()
    state = (chunk.state or "").lower()

    full_chunk_text = f"{scheme_name} {category} {content} {state}"

    is_glossary = (
        category in ["glossary", "Glossary"]
        or scheme_name == "schemora knowledge glossary"
        or section in ["concept", "glossary"]
        or getattr(chunk, "scheme_id", "") == "schemora-glossary"
    )

    has_profile = bool(
        profile_attrs.get("beneficiary")
        or profile_attrs.get("occupation")
        or profile_attrs.get("gender")
        or profile_attrs.get("state")
        or profile_attrs.get("extracted_terms")
    )

    if is_glossary and (has_profile or any(w in q_lower for w in ["give me", "list", "available", "schemes", "scholarships", "find", "show"])):
        return -1.0

    # Generic profile terms match
    for term in profile_attrs.get("extracted_terms", []):
        t_clean = term.lower()
        if t_clean and len(t_clean) > 2:
            if t_clean in full_chunk_text:
                boost += 0.35

    # Specific state match boost
    detected_state = profile_attrs.get("state")
    if detected_state:
        st_lower = detected_state.lower()
        if state == st_lower or st_lower in full_chunk_text:
            boost += 0.30

    for w in q_words:
        if w in scheme_name:
            boost += 0.15
        if w in category:
            boost += 0.12
        if state and w in state:
            boost += 0.10
        if w in content:
            boost += 0.03

    return min(0.60, max(-1.0, boost))


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
    qu_res = analyze_query_understanding(query, conversation_context=conversation_context)

    if not state and qu_res.detected_state:
        state = qu_res.detected_state

    intent = detect_intent(query, conversation_context=conversation_context)

    if intent in ["UNKNOWN", "AMBIGUOUS"] or (
        qu_res.confidence_level in ["LOW", "UNKNOWN"]
        and not qu_res.entity_match
        and not qu_res.detected_state
        and intent == "GENERAL"
    ):
        return []

    expanded_query = expand_query(query, intent)
    t_emb_start = time.time()
    query_embedding, is_semantic = await embed_text(expanded_query)
    t_emb = round((time.time() - t_emb_start) * 1000, 2)
    logger.info(f"[CHAT] embedding generation: {t_emb} ms (is_semantic={is_semantic})")

    section_boosts = INTENT_SECTION_BOOST.get(intent, {})
    scored = []

    if is_semantic and is_dense_embedding(query_embedding):
        where_filter = {}
        if scheme_id:
            where_filter["scheme_id"] = scheme_id
        if state:
            where_filter["state"] = state
        if category:
            where_filter["category"] = category

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
                "official_app_url": meta.get("official_app_url", ""),
                "last_verified_at": meta.get("last_verified_at", "2026-08-07"),
                "scheme_version": meta.get("scheme_version", "v1"),
                "jurisdiction": meta.get("jurisdiction", ""),
                "state": meta.get("state", ""),
                "category": meta.get("category", ""),
                "is_semantic": True,
                "vector_store": "pgvector",
            })

    if not scored:
        try:
            stmt = select(KnowledgeChunk)
            if scheme_id:
                stmt = stmt.where(KnowledgeChunk.scheme_id == scheme_id)
            if state:
                stmt = stmt.where((KnowledgeChunk.state == state) | (KnowledgeChunk.state == None))
            if category:
                stmt = stmt.where(KnowledgeChunk.category == category)

            result = await db.execute(stmt)
            chunks = result.scalars().all()
        except Exception as e:
            logger.warning(f"SQL DB retrieval scan exception: {e}")
            chunks = []

        q_tokens = set(re.findall(r"\w+", expanded_query.lower()))
        for chunk in chunks:
            c_text_lower = f"{chunk.scheme_name or ''} {chunk.content or ''}".lower()
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
                "official_app_url": chunk.official_app_url or "",
                "last_verified_at": chunk.last_verified_at or "2026-08-07",
                "scheme_version": chunk.scheme_version or "v1",
                "jurisdiction": chunk.jurisdiction or "",
                "state": chunk.state or "",
                "category": chunk.category or "",
                "is_semantic": chunk.is_indexed,
                "vector_store": "sql_fallback",
            })

    scored.sort(key=lambda x: x["similarity_score"], reverse=True)

    if intent == "DEFINITION_CONCEPT":
        concept_chunks = [
            item for item in scored
            if item.get("section") in ["concept", "glossary"]
            or item.get("category") == "Glossary"
            or item.get("scheme_id") == "schemora-glossary"
        ]
        if concept_chunks:
            return concept_chunks[:top_k]

    if intent == "SCHEME_DISCOVERY":
        scored = [
            item for item in scored
            if item.get("section") not in ["concept", "glossary"]
            and item.get("category") != "Glossary"
            and item.get("scheme_id") != "schemora-glossary"
        ]

    entity, target_sec = extract_query_entity_and_section(query)
    if entity:
        ent_clean = re.sub(r"[^\w\s]", " ", entity.lower())
        raw_kws = [w for w in ent_clean.split() if len(w) > 1]
        specific_kws = [w for w in raw_kws if w not in {"pm", "scheme", "yojana", "pradhan", "mantri"}]
        entity_kw = specific_kws if specific_kws else raw_kws
        entity_matches = [
            item for item in scored
            if any(kw in f"{item.get('scheme_name') or ''} {item.get('content') or ''}".lower() for kw in entity_kw)
        ]
        if entity_matches:
            return entity_matches[:min(top_k, 5)]

    seen_schemes = set()
    deduped = []
    target_limit = max(top_k, 6) if intent == "SCHEME_DISCOVERY" else top_k

    for item in scored:
        s_id = item["scheme_id"]
        if intent == "SCHEME_DISCOVERY":
            if s_id not in seen_schemes:
                seen_schemes.add(s_id)
                deduped.append(item)
        else:
            deduped.append(item)

        if len(deduped) >= target_limit:
            break

    return deduped


async def retrieve_scheme_overview(
    db: AsyncSession,
    scheme_id: str,
) -> Optional[Dict[str, Any]]:
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
