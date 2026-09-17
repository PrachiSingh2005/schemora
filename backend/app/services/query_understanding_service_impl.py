"""Query Understanding Service Implementation — Schemora NLP Engine."""

import re
import logging
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Set

logger = logging.getLogger("schemora.query_understanding")

HIGH_CONFIDENCE_THRESHOLD = 0.80
MEDIUM_CONFIDENCE_THRESHOLD = 0.60
LOW_CONFIDENCE_THRESHOLD = 0.40


@dataclass
class CanonicalEntity:
    id: str
    canonical_name: str
    official_name: str
    entity_type: str
    aliases: List[str] = field(default_factory=list)
    known_variants: List[str] = field(default_factory=list)
    state: Optional[str] = None
    official_url: Optional[str] = None
    description: Optional[str] = None


@dataclass
class EntityMatch:
    entity: CanonicalEntity
    matched_term: str
    similarity_score: float
    confidence_level: str
    match_strategy: str


@dataclass
class QueryUnderstandingResult:
    original_query: str
    normalized_query: str
    detected_language: str
    entity_match: Optional[EntityMatch]
    entity_confidence: float
    confidence_level: str
    detected_intent: str
    intent_confidence: float
    detected_state: Optional[str]
    detected_category: Optional[str]
    detected_beneficiary: Optional[str]
    corrected_keywords: List[Tuple[str, str]]
    extracted_profile: Dict[str, Any] = field(default_factory=dict)
    is_ambiguous: bool = False
    ambiguous_options: List[str] = field(default_factory=list)


def normalize_text(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    norm = unicodedata.normalize("NFKC", text).lower()
    norm = re.sub(r"[-_]", " ", norm)
    norm = re.sub(r"[^\w\s\u0900-\u0D7F]", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


class EntityRegistry:

    def __init__(self):
        self.entities: Dict[str, CanonicalEntity] = {}
        self.alias_lookup: Dict[str, str] = {}
        self._initialize_default_registry()

    def register_entity(self, entity: CanonicalEntity) -> None:
        self.entities[entity.id] = entity
        self.alias_lookup[normalize_text(entity.canonical_name)] = entity.id
        self.alias_lookup[normalize_text(entity.official_name)] = entity.id

        for alias in entity.aliases:
            norm_alias = normalize_text(alias)
            if norm_alias:
                self.alias_lookup[norm_alias] = entity.id

        for variant in entity.known_variants:
            norm_var = normalize_text(variant)
            if norm_var:
                self.alias_lookup[norm_var] = entity.id
            compact_var = norm_var.replace(" ", "")
            if compact_var:
                self.alias_lookup[compact_var] = entity.id

    def _initialize_default_registry(self) -> None:
        self.register_entity(CanonicalEntity(
            id="portal-mahadbt",
            canonical_name="MahaDBT",
            official_name="Aaple Sarkar DBT Portal",
            entity_type="PORTAL",
            state="Maharashtra",
            aliases=["Maha DBT", "MahaDBT Portal", "Aaple Sarkar DBT"],
            known_variants=["mahadbt", "mahadt", "maha dbt", "mahadbtt"],
            official_url="https://www.mahadbt.maharashtra.gov.in/",
            description="Official Direct Benefit Transfer portal of Maharashtra."
        ))
        self.register_entity(CanonicalEntity(
            id="portal-nsp",
            canonical_name="National Scholarship Portal",
            official_name="National Scholarship Portal (NSP)",
            entity_type="PORTAL",
            aliases=["NSP", "NSP Portal"],
            known_variants=["nsp", "nspportal"],
            official_url="https://scholarships.gov.in/",
            description="Central portal for National Scholarships."
        ))
        self.register_entity(CanonicalEntity(
            id="sch-pm-kisan",
            canonical_name="PM-KISAN",
            official_name="Pradhan Mantri Kisan Samman Nidhi",
            entity_type="SCHEME",
            aliases=["PM Kisan", "PM Kisan Samman Nidhi", "Pradhan Mantri Kisan Samman Nidhi"],
            known_variants=["pmkisan", "pm-kisan", "pm kisan"],
            official_url="https://pmkisan.gov.in/",
            description="Central scheme providing Rs 6,000 annually to eligible farmers."
        ))
        self.register_entity(CanonicalEntity(
            id="sch-pm-internship",
            canonical_name="PM Internship Scheme",
            official_name="Prime Minister Internship Scheme in Top Companies",
            entity_type="SCHEME",
            aliases=["PM Internship", "Prime Minister Internship Scheme"],
            known_variants=["pminternship", "pm internship"],
            official_url="https://pminternship.mca.gov.in/",
            description="Government internship initiative providing skill training."
        ))
        self.register_entity(CanonicalEntity(
            id="sch-post-matric",
            canonical_name="Post-Matric Scholarship for Scheduled Caste Students",
            official_name="Post-Matric Scholarship for SC Students",
            entity_type="SCHEME",
            aliases=["Post-Matric Scholarship", "Post Matric Scholarship"],
            known_variants=["postmatric", "post-matric", "post matric"],
            official_url="https://scholarships.gov.in/",
            description="Financial assistance for SC students."
        ))
        self.register_entity(CanonicalEntity(
            id="sch-ladki-bahin",
            canonical_name="Mukhyamantri Majhi Ladki Bahin Yojana",
            official_name="Mukhyamantri Majhi Ladki Bahin Yojana",
            entity_type="SCHEME",
            state="Maharashtra",
            aliases=["Ladki Bahin Scheme", "Ladki Bahin Yojana", "Majhi Ladki Bahin"],
            known_variants=["ladki bahin", "ladkibahin", "ladki bahin yojana"],
            official_url="https://ladakibahin.maharashtra.gov.in/",
            description="Maharashtra scheme providing monthly financial assistance to eligible women."
        ))

        state_data = [
            ("Maharashtra", ["MH", "Maharashtra State"], ["maharashtra", "maharastra", "mh"]),
            ("Gujarat", ["GJ", "Gujarat State"], ["gujarat", "gujrat", "gj"]),
            ("Rajasthan", ["RJ", "Rajasthan State"], ["rajasthan", "rj"]),
            ("Uttar Pradesh", ["UP", "Uttar Pradesh State"], ["uttar pradesh", "up"]),
        ]
        for name, aliases, variants in state_data:
            self.register_entity(CanonicalEntity(
                id=f"state-{name.lower().replace(' ', '-')}",
                canonical_name=name,
                official_name=f"State of {name}",
                entity_type="STATE",
                state=name,
                aliases=aliases,
                known_variants=variants,
            ))


entity_registry = EntityRegistry()


class FuzzyMatcher:

    @staticmethod
    def calculate_levenshtein_ratio(str1: str, str2: str) -> float:
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1, str2).ratio()

    @staticmethod
    def calculate_token_similarity(query_norm: str, target_norm: str) -> float:
        q_tokens = set(query_norm.split())
        t_tokens = set(target_norm.split())
        if not q_tokens or not t_tokens:
            return 0.0
        intersection = len(q_tokens.intersection(t_tokens))
        union = len(q_tokens.union(t_tokens))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def match_entity(cls, term: str) -> Optional[EntityMatch]:
        term_norm = normalize_text(term)
        if not term_norm or len(term_norm) < 2:
            return None

        GENERIC_STOP_WORDS = {
            "scheme", "schemes", "yojana", "yojna", "scholarship", "scholarships",
            "govt", "government", "government scheme", "government schemes",
        }
        if term_norm in GENERIC_STOP_WORDS:
            return None

        term_compact = term_norm.replace(" ", "")

        if term_norm in entity_registry.alias_lookup:
            entity_id = entity_registry.alias_lookup[term_norm]
            entity = entity_registry.entities[entity_id]
            return EntityMatch(
                entity=entity,
                matched_term=term,
                similarity_score=1.0,
                confidence_level="HIGH",
                match_strategy="EXACT",
            )
        if term_compact in entity_registry.alias_lookup:
            entity_id = entity_registry.alias_lookup[term_compact]
            entity = entity_registry.entities[entity_id]
            return EntityMatch(
                entity=entity,
                matched_term=term,
                similarity_score=0.95,
                confidence_level="HIGH",
                match_strategy="VARIANT",
            )

        best_entity = None
        best_score = 0.0
        best_strategy = "NONE"
        best_matched_term = ""

        for entity in entity_registry.entities.values():
            candidates = [entity.canonical_name, entity.official_name] + entity.aliases + entity.known_variants
            for candidate in candidates:
                cand_norm = normalize_text(candidate)
                cand_compact = cand_norm.replace(" ", "")

                lev_ratio = cls.calculate_levenshtein_ratio(term_norm, cand_norm)
                raw_compact_ratio = cls.calculate_levenshtein_ratio(term_compact, cand_compact)
                len_ratio = min(len(term_compact), len(cand_compact)) / max(len(term_compact), len(cand_compact))
                lev_compact_ratio = raw_compact_ratio * len_ratio
                tok_sim = cls.calculate_token_similarity(term_norm, cand_norm)

                current_score = max(lev_ratio, lev_compact_ratio * 0.95, tok_sim * 0.90)
                if current_score > best_score:
                    best_score = current_score
                    best_entity = entity
                    best_matched_term = candidate
                    best_strategy = "LEVENSHTEIN" if (lev_ratio > 0.85 or lev_compact_ratio > 0.85) else "FUZZY_TOKEN"

        if not best_entity or best_score < LOW_CONFIDENCE_THRESHOLD:
            return None

        conf_level = "HIGH" if best_score >= HIGH_CONFIDENCE_THRESHOLD else ("MEDIUM" if best_score >= MEDIUM_CONFIDENCE_THRESHOLD else "LOW")
        return EntityMatch(
            entity=best_entity,
            matched_term=best_matched_term,
            similarity_score=round(best_score, 4),
            confidence_level=conf_level,
            match_strategy=best_strategy,
        )

    @classmethod
    def extract_all_entities(cls, query: str) -> List[EntityMatch]:
        q_norm = normalize_text(query)
        if not q_norm:
            return []
        matched_entities: Dict[str, EntityMatch] = {}
        segments = re.split(r"\b(?:and|vs\.?|versus|compared?\s+to|between|,)\b", q_norm, flags=re.I)
        for seg in segments:
            seg_str = seg.strip()
            if not seg_str or len(seg_str) < 2:
                continue
            match = cls.match_entity(seg_str)
            if match and match.confidence_level in ["HIGH", "MEDIUM"]:
                matched_entities[match.entity.id] = match
        return list(matched_entities.values())


INTENT_KEYWORD_TYPOS = {
    "documents": "documents", "documnts": "documents",
    "application": "application", "aplication": "application",
    "apply": "apply", "aplly": "apply",
    "eligibility": "eligibility", "eligibilty": "eligibility",
    "eligible": "eligible", "elgible": "eligible",
    "benefits": "benefits", "benfits": "benefits",
    "scholarship": "scholarship", "scholrship": "scholarship",
}


def normalize_intent_keywords(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    words = text.split()
    corrected_words = []
    corrections = []

    for word in words:
        w_clean = re.sub(r"[^\w]", "", word.lower())
        if w_clean in INTENT_KEYWORD_TYPOS:
            corrected = INTENT_KEYWORD_TYPOS[w_clean]
            corrected_words.append(corrected)
            if w_clean != corrected:
                corrections.append((word, corrected))
        else:
            corrected_words.append(word)

    return " ".join(corrected_words), corrections


def extract_profile_attributes(query: str) -> Dict[str, Any]:
    """Extract profile/beneficiary eligibility attributes generically from natural language queries."""
    if not query:
        return {}

    q_lower = query.lower().strip()

    extracted: Dict[str, Any] = {
        "occupation": None,
        "beneficiary": None,
        "gender": None,
        "education": None,
        "caste_category": None,
        "state": None,
        "extracted_terms": [],
    }

    # Gender
    if any(w in q_lower for w in ["women", "woman", "female", "girl", "girls", "mahila", "kanya", "lady", "ladies", "widow", "mother", "matru"]):
        extracted["gender"] = "Female"
        extracted["extracted_terms"].append("women")
        extracted["beneficiary"] = "women"
    elif any(w in q_lower for w in ["men", "man", "male", "boy", "boys"]):
        extracted["gender"] = "Male"
        extracted["extracted_terms"].append("men")
        extracted["beneficiary"] = "men"

    # Caste / Category
    caste_map = {
        "sc": "SC", "scheduled caste": "SC",
        "st": "ST", "scheduled tribe": "ST",
        "obc": "OBC", "other backward class": "OBC",
        "general": "General", "ebc": "EBC", "ews": "EWS",
        "minority": "Minority", "minorities": "Minority",
    }
    for c_k, c_v in caste_map.items():
        if re.search(r"\b" + re.escape(c_k) + r"\b", q_lower):
            extracted["caste_category"] = c_v
            extracted["extracted_terms"].append(c_k)
            break

    # Occupation / Role matching for common domains
    if any(w in q_lower for w in ["farmer", "farmers", "kisan", "agriculture", "cultivator", "crop"]):
        extracted["occupation"] = "farmer"
        extracted["extracted_terms"].append("farmer")
        extracted["beneficiary"] = extracted["beneficiary"] or "farmer"
    elif any(w in q_lower for w in ["student", "students", "scholarship", "scholarships", "btech", "undergraduate", "postgraduate", "school", "college"]):
        extracted["occupation"] = "student"
        extracted["extracted_terms"].append("student")
        extracted["beneficiary"] = extracted["beneficiary"] or "student"

    # State matching (generic list of states and UTs)
    state_map = {
        "maharashtra": "Maharashtra", "mh": "Maharashtra", "maharastra": "Maharashtra",
        "gujarat": "Gujarat", "gj": "Gujarat", "gujrat": "Gujarat",
        "rajasthan": "Rajasthan", "rj": "Rajasthan",
        "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
        "karnataka": "Karnataka", "tamil nadu": "Tamil Nadu", "tn": "Tamil Nadu",
        "kerala": "Kerala", "punjab": "Punjab", "haryana": "Haryana",
        "madhya pradesh": "Madhya Pradesh", "mp": "Madhya Pradesh",
        "west bengal": "West Bengal", "wb": "West Bengal", "bihar": "Bihar",
        "odisha": "Odisha", "telangana": "Telangana", "andhra pradesh": "Andhra Pradesh",
    }
    for st_k, st_v in state_map.items():
        if re.search(r"\b" + re.escape(st_k) + r"\b", q_lower):
            extracted["state"] = st_v
            extracted["extracted_terms"].append(st_k)
            break

    # Generic structural regex pattern matching for ANY beneficiary / target group
    patterns = [
        r"\b(?:schemes?|scholarships?|yojana|grants?|benefits?|programs?)\s+(?:for|to|of)\s+([a-z0-9\s\-]+?)(?:\s+in|\s+state|\?|\.|$)",
        r"\bfor\s+([a-z0-9\s\-]+?)\s+(?:schemes?|scholarships?|yojana|grants?|benefits?|programs?)",
        r"^\s*([a-z0-9\s\-]+?)\s+(?:schemes?|scholarships?|yojana)\s*$",
        r"^\s*(?:give|show|find|get|tell)\s+(?:me\s+)?(?:schemes?|scholarships?|yojana)\s+(?:for|to)\s+([a-z0-9\s\-]+?)(?:\s+in|\s+state|\?|\.|$)",
    ]

    for pat in patterns:
        m = re.search(pat, q_lower)
        if m:
            target = m.group(1).strip()
            clean_target = re.sub(r"\b(?:all|available|popular|new|government|govt|me|my|any|the|a|an)\b", "", target).strip()
            if clean_target and len(clean_target) > 2:
                if not extracted["beneficiary"]:
                    extracted["beneficiary"] = clean_target
                if not extracted["occupation"] and clean_target not in ["women", "men", "female", "male"]:
                    extracted["occupation"] = clean_target
                if clean_target not in extracted["extracted_terms"]:
                    extracted["extracted_terms"].append(clean_target)
            break

    return extracted


def analyze_query_understanding(
    query: str,
    passed_lang: Optional[str] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> QueryUnderstandingResult:
    from app.services.language_service import language_registry
    detected_spec = language_registry.detect_language(query, passed_lang)
    lang_code = detected_spec.code

    raw_norm = normalize_text(query)
    corrected_query, corrections = normalize_intent_keywords(query)
    corrected_norm = normalize_text(corrected_query)

    profile_attrs = extract_profile_attributes(query)

    is_ambiguous = False
    ambiguous_options = []
    if raw_norm in ["pm", "scheme", "scholarship", "yojana", "govt"]:
        is_ambiguous = True
        if raw_norm == "pm":
            ambiguous_options = ["PM-KISAN", "PM Internship Scheme", "PM MUDRA Yojana"]

    matched_entity: Optional[EntityMatch] = None
    words = corrected_norm.split()
    candidate_phrases = []
    n = len(words)
    for length in range(min(4, n), 0, -1):
        for i in range(n - length + 1):
            phrase = " ".join(words[i:i + length])
            candidate_phrases.append(phrase)

    GENERIC_IGNORE_PHRASES = {
        "what is", "what is a", "what is an", "how to apply", "required documents",
        "eligibility criteria", "a government scheme",
        "government scheme", "government schemes",
    }
    has_portal_keyword = any(k in corrected_norm for k in ["portal", "dbt", "website", "site", "mahadbt", "nsp", "myscheme"])

    for phrase in candidate_phrases:
        if phrase in GENERIC_IGNORE_PHRASES:
            continue
        match = FuzzyMatcher.match_entity(phrase)
        if match:
            if match.entity.entity_type == "PORTAL" and not has_portal_keyword and match.similarity_score < 0.90:
                continue
            if not matched_entity:
                matched_entity = match
            elif match.similarity_score > matched_entity.similarity_score + 0.05:
                matched_entity = match
            if matched_entity and matched_entity.confidence_level == "HIGH" and matched_entity.entity.entity_type == "SCHEME":
                break

    detected_state = profile_attrs.get("state")
    if not detected_state and matched_entity and matched_entity.entity.state:
        detected_state = matched_entity.entity.state
    elif not detected_state:
        for phrase in candidate_phrases:
            state_match = FuzzyMatcher.match_entity(phrase)
            if state_match and state_match.entity.entity_type == "STATE":
                detected_state = state_match.entity.state
                break
    profile_attrs["state"] = detected_state

    if is_ambiguous:
        final_conf_level = "LOW"
        final_score = 0.30
    elif matched_entity:
        final_conf_level = matched_entity.confidence_level
        final_score = matched_entity.similarity_score
    else:
        final_conf_level = "UNKNOWN"
        final_score = 0.0

    return QueryUnderstandingResult(
        original_query=query,
        normalized_query=corrected_norm,
        detected_language=lang_code,
        entity_match=matched_entity,
        entity_confidence=final_score,
        confidence_level=final_conf_level,
        detected_intent="UNKNOWN",
        intent_confidence=1.0 if corrections else 0.8,
        detected_state=detected_state,
        detected_category=profile_attrs.get("caste_category"),
        detected_beneficiary=profile_attrs.get("beneficiary") or profile_attrs.get("occupation"),
        corrected_keywords=corrections,
        extracted_profile=profile_attrs,
        is_ambiguous=is_ambiguous,
        ambiguous_options=ambiguous_options,
    )
