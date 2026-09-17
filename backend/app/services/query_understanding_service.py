"""Query Understanding Service — Schemora NLP & Typo-Tolerance Engine.

Provides unified query normalization, canonical entity & portal resolution, multi-strategy
fuzzy matching with confidence scoring, and typo-tolerant intent/location extraction.

Key Capabilities:
  1. Text Normalization: NFKC Unicode, lowercase, whitespace collapse, punctuation & hyphen handling.
  2. Canonical Entity Registry: Maintains SCHEME, PORTAL, STATE, CATEGORY, BENEFICIARY_GROUP,
     CONCEPT, and DOCUMENT_TYPE entities without duplicating KB database rows for typos.
  3. Multi-Strategy Fuzzy Matcher: Exact, alias, token-set, and Levenshtein similarity.
  4. Confidence Scoring & Safety Thresholds:
     - HIGH (>= 0.80): Auto-resolve
     - MEDIUM (0.60 - 0.79): Resolve with confirmation/clarification ask
     - LOW / UNKNOWN (< 0.60): Skip unrestricted retrieval, ask for user clarification
  5. Sentence-Level Typo Tolerance: Handles misspelled keywords inside full sentences
     (e.g., "what documnts are requried for pm kisan", "scholrships for studnts", "Maharastra schemes").
"""

import re
import logging
import unicodedata
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Set

logger = logging.getLogger("schemora.query_understanding")

# ── Confidence Threshold Definitions ──────────────────────────────────────────
HIGH_CONFIDENCE_THRESHOLD = 0.80
MEDIUM_CONFIDENCE_THRESHOLD = 0.60
LOW_CONFIDENCE_THRESHOLD = 0.40


@dataclass
class CanonicalEntity:
    id: str
    canonical_name: str
    official_name: str
    entity_type: str  # SCHEME | PORTAL | STATE | CATEGORY | BENEFICIARY_GROUP | CONCEPT | DOCUMENT_TYPE
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
    confidence_level: str  # HIGH | MEDIUM | LOW | UNKNOWN
    match_strategy: str    # EXACT | ALIAS | VARIANT | FUZZY_TOKEN | LEVENSHTEIN


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
    corrected_keywords: List[Tuple[str, str]]  # List of (original_word, corrected_word)
    is_ambiguous: bool = False
    ambiguous_options: List[str] = field(default_factory=list)


# ── Text Normalization ────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Normalize input text: NFKC Unicode, lowercase, punctuation, whitespace, hyphens.
    Preserves Indic scripts (Devanagari, Gujarati, etc.) and vowel matras intact.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Unicode Normalization (NFKC)
    norm = unicodedata.normalize("NFKC", text)

    # 2. Lowercase
    norm = norm.lower()

    # 3. Replace hyphens and underscores with spaces
    norm = re.sub(r"[-_]", " ", norm)

    # 4. Remove punctuation except alphanumeric, spaces, and Indic Unicode ranges (\u0900-\u0D7F)
    norm = re.sub(r"[^\w\s\u0900-\u0D7F]", " ", norm)

    # 5. Collapse repeated whitespaces and strip
    norm = re.sub(r"\s+", " ", norm).strip()

    return norm


# ── Canonical Entity Registry ──────────────────────────────────────────────────

class EntityRegistry:
    """Registry of canonical government schemes, portals, states, categories, and concepts."""

    def __init__(self):
        self.entities: Dict[str, CanonicalEntity] = {}
        self.alias_lookup: Dict[str, str] = {}  # normalized_alias -> entity_id
        self._initialize_default_registry()

    def register_entity(self, entity: CanonicalEntity) -> None:
        self.entities[entity.id] = entity

        # Register normalized canonical name
        norm_canonical = normalize_text(entity.canonical_name)
        self.alias_lookup[norm_canonical] = entity.id

        # Register normalized official name
        norm_official = normalize_text(entity.official_name)
        self.alias_lookup[norm_official] = entity.id

        # Register normalized aliases
        for alias in entity.aliases:
            norm_alias = normalize_text(alias)
            if norm_alias:
                self.alias_lookup[norm_alias] = entity.id

        # Register normalized known variants (common typos / concatenated forms)
        for variant in entity.known_variants:
            norm_var = normalize_text(variant)
            if norm_var:
                self.alias_lookup[norm_var] = entity.id
            # Also register compact unspaced variant
            compact_var = norm_var.replace(" ", "")
            if compact_var:
                self.alias_lookup[compact_var] = entity.id

    def _initialize_default_registry(self) -> None:
        # ── PORTALS ────────────────────────────────────────────────────────────
        self.register_entity(CanonicalEntity(
            id="portal-mahadbt",
            canonical_name="MahaDBT",
            official_name="Aaple Sarkar DBT Portal",
            entity_type="PORTAL",
            state="Maharashtra",
            aliases=[
                "Maha DBT", "MahaDBT Portal", "Aaple Sarkar DBT",
                "Aaple Sarkar DBT Portal", "MahaDBT Maharashtra",
            ],
            known_variants=[
                "mahadbt", "mahadt", "maha dbt", "mahadbtt", "mahadb",
                "mahdbt", "mahadbtportal", "maharashtra dbt"
            ],
            official_url="https://www.mahadbt.maharashtra.gov.in/",
            description="Official Direct Benefit Transfer portal of the Government of Maharashtra for scholarships and welfare schemes."
        ))

        self.register_entity(CanonicalEntity(
            id="portal-nsp",
            canonical_name="National Scholarship Portal",
            official_name="National Scholarship Portal (NSP)",
            entity_type="PORTAL",
            state=None,
            aliases=["NSP", "NSP Portal", "National Scholarship Portal India"],
            known_variants=["nsp", "nspportal", "national scholarship"],
            official_url="https://scholarships.gov.in/",
            description="Central portal for National Scholarships under the Government of India."
        ))

        self.register_entity(CanonicalEntity(
            id="portal-myscheme",
            canonical_name="myScheme",
            official_name="myScheme Government Portal",
            entity_type="PORTAL",
            state=None,
            aliases=["myScheme", "myScheme Portal", "my scheme"],
            known_variants=["myscheme", "myschem", "my scheme portal"],
            official_url="https://www.myscheme.gov.in/",
            description="National e-Governance Division portal listing government schemes across India."
        ))

        self.register_entity(CanonicalEntity(
            id="portal-jansamarth",
            canonical_name="Jan Samarth Portal",
            official_name="National Portal for Credit Linked Government Schemes",
            entity_type="PORTAL",
            state=None,
            aliases=["Jan Samarth", "JanSamarth", "Jan Samarth Portal"],
            known_variants=["jansamarth", "jan samart", "jan samarth"],
            official_url="https://www.jansamarth.in/",
            description="Digital portal linking credit-linked government schemes for loans and subsidies."
        ))

        # ── SCHEMES ────────────────────────────────────────────────────────────
        self.register_entity(CanonicalEntity(
            id="sch-pm-kisan",
            canonical_name="PM-KISAN",
            official_name="Pradhan Mantri Kisan Samman Nidhi",
            entity_type="SCHEME",
            aliases=[
                "PM Kisan", "PM Kisan Samman Nidhi", "Pradhan Mantri Kisan Samman Nidhi",
                "Kisan Samman Nidhi", "PM-KISAN Yojana"
            ],
            known_variants=["pmkisan", "pm-kisan", "pm kisan", "pmkisan yojana", "pm kisan nidhi"],
            official_url="https://pmkisan.gov.in/",
            description="Central scheme providing ₹6,000 annually to eligible landholding farmer families across India."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-pm-internship",
            canonical_name="PM Internship Scheme",
            official_name="Prime Minister Internship Scheme in Top Companies",
            entity_type="SCHEME",
            aliases=["PM Internship", "Prime Minister Internship Scheme", "PM Internship Program"],
            known_variants=["pminternship", "pm internship", "pm internship scheme"],
            official_url="https://pminternship.mca.gov.in/",
            description="Government internship initiative providing skill training in top 500 companies."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-post-matric",
            canonical_name="Post-Matric Scholarship for Scheduled Caste Students",
            official_name="Post-Matric Scholarship for SC Students",
            entity_type="SCHEME",
            aliases=["Post-Matric Scholarship", "Post Matric Scholarship", "PostMatric SC Scholarship"],
            known_variants=["postmatric", "post-matric", "post matric", "post matric sc"],
            official_url="https://scholarships.gov.in/",
            description="Financial assistance for SC students pursuing post-secondary education."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-pre-matric",
            canonical_name="Pre-Matric Scholarship for Scheduled Caste Students",
            official_name="Pre-Matric Scholarship for SC Students",
            entity_type="SCHEME",
            aliases=["Pre-Matric Scholarship", "Pre Matric Scholarship", "PreMatric SC Scholarship"],
            known_variants=["prematric", "pre-matric", "pre matric", "pre matric sc"],
            official_url="https://scholarships.gov.in/",
            description="Financial support for SC students studying in classes 9 and 10."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-mysy",
            canonical_name="Mukhyamantri Yuva Swavalamban Yojana (MYSY Gujarat)",
            official_name="Mukhyamantri Yuva Swavalamban Yojana",
            entity_type="SCHEME",
            state="Gujarat",
            aliases=["MYSY", "MYSY Gujarat", "Yuva Swavalamban Yojana"],
            known_variants=["mysy", "mysy gujarat", "mysy scholarship"],
            official_url="https://mysy.guj.nic.in/",
            description="Higher education financial assistance scheme for meritorious students in Gujarat."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-sukanya",
            canonical_name="Sukanya Samriddhi Yojana",
            official_name="Sukanya Samriddhi Yojana (SSY)",
            entity_type="SCHEME",
            aliases=["SSY", "Sukanya Samriddhi", "Sukanya Samriddhi Scheme"],
            known_variants=["ssy", "sukanya samriddhi", "sukanya yojana"],
            official_url="https://www.indiapost.gov.in/",
            description="Small deposit savings scheme for the girl child backed by the Government of India."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-ayushman",
            canonical_name="Ayushman Bharat PM-JAY",
            official_name="Pradhan Mantri Jan Arogya Yojana",
            entity_type="SCHEME",
            aliases=["Ayushman Bharat", "PM-JAY", "PMJAY", "Jan Arogya Yojana"],
            known_variants=["ayushman", "pmjay", "pm-jay", "ayushman bharat card"],
            official_url="https://beneficiary.nha.gov.in/",
            description="National health protection scheme providing ₹5 lakh health insurance cover per family per year."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-mudra",
            canonical_name="Pradhan Mantri MUDRA Yojana",
            official_name="Pradhan Mantri MUDRA Yojana (PMMY)",
            entity_type="SCHEME",
            aliases=["MUDRA", "MUDRA Loan", "PMMY", "PM MUDRA Scheme"],
            known_variants=["mudra", "pmmy", "mudra loan", "pm mudra"],
            official_url="https://www.mudra.org.in/",
            description="Micro-finance loan scheme for non-corporate, non-farm small and micro enterprises."
        ))

        self.register_entity(CanonicalEntity(
            id="sch-ladki-bahin",
            canonical_name="Mukhyamantri Majhi Ladki Bahin Yojana",
            official_name="Mukhyamantri Majhi Ladki Bahin Yojana",
            entity_type="SCHEME",
            state="Maharashtra",
            aliases=[
                "Ladki Bahin Scheme", "Ladki Bahin Yojana", "Majhi Ladki Bahin",
                "Mukhyamantri Ladki Bahin", "Ladki Bahin Maharashtra",
            ],
            known_variants=[
                "ladki bahin", "ladkibahin", "ladki bahin yojana", "majhi ladki bahin",
                "mukhyamantri ladki bahin", "ladkibahinyojana",
            ],
            official_url="https://ladakibahin.maharashtra.gov.in/",
            description="Maharashtra government scheme providing monthly financial assistance to eligible women."
        ))

        # ── STATES ─────────────────────────────────────────────────────────────
        state_data = [
            ("Maharashtra", ["MH", "Maharashtra State"], ["maharashtra", "maharastra", "mahatrashtra", "mh"]),
            ("Gujarat", ["GJ", "Gujarat State"], ["gujarat", "gujrat", "gujarat state", "gj"]),
            ("Rajasthan", ["RJ", "Rajasthan State"], ["rajasthan", "rajastan", "rajsthan", "rj"]),
            ("Uttar Pradesh", ["UP", "Uttar Pradesh State"], ["uttar pradesh", "uttarpradesh", "uttar prades", "up"]),
            ("Madhya Pradesh", ["MP", "Madhya Pradesh State"], ["madhya pradesh", "madhyapradesh", "mp"]),
            ("Bihar", ["Bihar State"], ["bihar", "behar"]),
            ("Punjab", ["PB", "Punjab State"], ["punjab", "punjab state"]),
            ("Karnataka", ["KA", "Karnataka State"], ["karnataka", "karnatak"]),
            ("Tamil Nadu", ["TN", "Tamil Nadu State"], ["tamil nadu", "tamilnadu", "tn"]),
            ("West Bengal", ["WB", "West Bengal State"], ["west bengal", "westbengal", "wb"]),
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


# Global Entity Registry Instance
entity_registry = EntityRegistry()


# ── Multi-Strategy Fuzzy Matcher ──────────────────────────────────────────────

class FuzzyMatcher:
    """Multi-strategy fuzzy matching engine combining exact, alias, token-set, and Levenshtein distance."""

    @staticmethod
    def calculate_levenshtein_ratio(str1: str, str2: str) -> float:
        """Compute string similarity ratio [0.0, 1.0]."""
        if not str1 or not str2:
            return 0.0
        return SequenceMatcher(None, str1, str2).ratio()

    @staticmethod
    def calculate_token_similarity(query_norm: str, target_norm: str) -> float:
        """Compute token-set Jaccard overlap ratio."""
        q_tokens = set(query_norm.split())
        t_tokens = set(target_norm.split())
        if not q_tokens or not t_tokens:
            return 0.0
        intersection = len(q_tokens.intersection(t_tokens))
        union = len(q_tokens.union(t_tokens))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def match_entity(cls, term: str) -> Optional[EntityMatch]:
        """Match a given string term against canonical entities in the registry.
        
        Returns:
            EntityMatch object with confidence score and strategy, or None if match < LOW_THRESHOLD.
        """
        term_norm = normalize_text(term)
        if not term_norm or len(term_norm) < 2:
            return None

        # Exclude purely generic scheme/concept words from being matched as specific entities (e.g. "scheme" -> myScheme)
        GENERIC_STOP_WORDS = {
            "scheme", "schemes", "yojana", "yojna", "scholarship", "scholarships",
            "govt", "government", "government scheme", "government schemes",
            "central scheme", "state scheme", "subsidy", "subsidies",
            "financial assistance", "financial aid", "welfare program", "welfare scheme",
            "public scheme", "public schemes"
        }
        if term_norm in GENERIC_STOP_WORDS:
            return None

        # Compact unspaced version (e.g., "pmkisan", "mahadbt")
        term_compact = term_norm.replace(" ", "")

        best_entity: Optional[CanonicalEntity] = None
        best_score: float = 0.0
        best_strategy: str = "NONE"
        best_matched_term: str = ""

        # 1. Check Exact / Alias / Variant direct dictionary lookup
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

        # 2. Iterate through all entities for fuzzy token & Levenshtein matching
        for entity in entity_registry.entities.values():
            candidates = [entity.canonical_name, entity.official_name] + entity.aliases + entity.known_variants
            for candidate in candidates:
                cand_norm = normalize_text(candidate)
                cand_compact = cand_norm.replace(" ", "")

                # Strategy A: Levenshtein distance on full normalized text
                lev_ratio = cls.calculate_levenshtein_ratio(term_norm, cand_norm)

                # Strategy B: Levenshtein distance on compact unspaced strings, weighted by string length ratio to prevent false matches on generic sub-words
                raw_compact_ratio = cls.calculate_levenshtein_ratio(term_compact, cand_compact)
                len_ratio = min(len(term_compact), len(cand_compact)) / max(len(term_compact), len(cand_compact))
                lev_compact_ratio = raw_compact_ratio * len_ratio

                # Strategy C: Token similarity
                tok_sim = cls.calculate_token_similarity(term_norm, cand_norm)

                # Combine best score for this candidate
                current_score = max(lev_ratio, lev_compact_ratio * 0.95, tok_sim * 0.90)

                if current_score > best_score:
                    best_score = current_score
                    best_entity = entity
                    best_matched_term = candidate
                    if lev_ratio > 0.85 or lev_compact_ratio > 0.85:
                        best_strategy = "LEVENSHTEIN"
                    else:
                        best_strategy = "FUZZY_TOKEN"

        if not best_entity or best_score < LOW_CONFIDENCE_THRESHOLD:
            return None

        # Portals must match with HIGH confidence or exact/alias/variant strategy to prevent generic query overlap
        if best_entity.entity_type == "PORTAL" and best_score < HIGH_CONFIDENCE_THRESHOLD and best_strategy not in ["EXACT", "ALIAS", "VARIANT"]:
            return None

        # Determine confidence level category
        if best_score >= HIGH_CONFIDENCE_THRESHOLD:
            conf_level = "HIGH"
        elif best_score >= MEDIUM_CONFIDENCE_THRESHOLD:
            conf_level = "MEDIUM"
        else:
            conf_level = "LOW"

        return EntityMatch(
            entity=best_entity,
            matched_term=best_matched_term,
            similarity_score=round(best_score, 4),
            confidence_level=conf_level,
            match_strategy=best_strategy,
        )

    @classmethod
    def extract_all_entities(cls, query: str) -> List[EntityMatch]:
        """Extract ALL distinct canonical entity matches mentioned in a query.

        Used primarily for COMPARISON queries (e.g. "Compare PM-KISAN and PM Internship Scheme").
        """
        q_norm = normalize_text(query)
        if not q_norm:
            return []

        matched_entities: Dict[str, EntityMatch] = {}

        # Split query on comparison connectors (and, vs, versus, compared to, between, comma)
        segments = re.split(r"\b(?:and|vs\.?|versus|compared?\s+to|between|,)\b", q_norm, flags=re.I)

        for seg in segments:
            seg_str = seg.strip()
            if not seg_str or len(seg_str) < 2:
                continue
            match = cls.match_entity(seg_str)
            if match and match.confidence_level in ["HIGH", "MEDIUM"]:
                matched_entities[match.entity.id] = match

        # Also probe multi-word window tokens against registry
        words = q_norm.split()
        for i in range(len(words)):
            for j in range(i + 1, min(i + 6, len(words) + 1)):
                phrase = " ".join(words[i:j])
                match = cls.match_entity(phrase)
                if match and match.confidence_level in ["HIGH", "MEDIUM"]:
                    if match.entity.id not in matched_entities:
                        matched_entities[match.entity.id] = match

        return list(matched_entities.values())


# ── Typo-Tolerant Intent & Keyword Normalizer ─────────────────────────────────

INTENT_KEYWORD_TYPOS = {
    # REQUIRED_DOCUMENTS
    "documents": "documents", "documnts": "documents", "documnt": "documents",
    "document": "documents", "paper": "documents", "papers": "documents",
    "certificate": "documents", "proof": "documents", "kyc": "documents",
    # APPLICATION_PROCESS
    "application": "application", "aplication": "application", "apllication": "application",
    "apply": "apply", "aplly": "apply", "aply": "apply",
    "procedure": "process", "process": "process", "fill": "fill", "filling": "fill",
    "register": "register", "register": "register",
    # ELIGIBILITY
    "eligibility": "eligibility", "eligibilty": "eligibility", "eligiblity": "eligibility",
    "eligible": "eligible", "elgible": "eligible", "criteria": "criteria", "patrata": "eligibility",
    # BENEFITS
    "benefits": "benefits", "benfits": "benefits", "benefit": "benefits",
    "amount": "amount", "stipend": "stipend", "grant": "grant", "rupees": "amount",
    # DEADLINE
    "deadline": "deadline", "deadlin": "deadline", "last date": "deadline",
    # SCHOLARSHIP
    "scholarship": "scholarship", "scholrship": "scholarship", "scholarhsip": "scholarship",
    "scholrships": "scholarships", "scholarships": "scholarships",
    # GENERAL DEFINITION
    "wht": "what", "wat": "what", "wats": "what is",
}


def normalize_intent_keywords(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Normalize common typos in intent keywords (e.g. 'documnts' -> 'documents')."""
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
            # Fuzzy match word against intent keywords if length > 4
            matched_correction = None
            if len(w_clean) >= 5:
                for target_kw, replacement in INTENT_KEYWORD_TYPOS.items():
                    if SequenceMatcher(None, w_clean, target_kw).ratio() >= 0.82:
                        matched_correction = replacement
                        corrections.append((word, replacement))
                        break
            corrected_words.append(matched_correction if matched_correction else word)

    return " ".join(corrected_words), corrections


# ── Full Query Pipeline ────────────────────────────────────────────────────────

def analyze_query_understanding(
    query: str,
    passed_lang: Optional[str] = None,
    conversation_context: Optional[Dict[str, Any]] = None,
) -> QueryUnderstandingResult:
    """Full NLP Query Understanding Pipeline:
    1. Normalization
    2. Intent Keyword Typo Correction
    3. Entity & Portal Extraction (N-gram scanning + Fuzzy Matching)
    4. State & Category Extraction
    5. Context Preservation
    6. Confidence Evaluation
    """
    from app.services.language_service import language_registry
    detected_spec = language_registry.detect_language(query, passed_lang)
    lang_code = detected_spec.code

    raw_norm = normalize_text(query)
    corrected_query, corrections = normalize_intent_keywords(query)
    corrected_norm = normalize_text(corrected_query)

    # 1. Ambiguity & Exclusion Check
    is_ambiguous = False
    ambiguous_options = []
    if raw_norm in ["pm", "scheme", "scholarship", "yojana", "govt"]:
        is_ambiguous = True
        if raw_norm == "pm":
            ambiguous_options = ["PM-KISAN", "PM Internship Scheme", "PM MUDRA Yojana", "PM Vishwakarma Scheme"]

    # 2. Extract Candidate Entity Tokens (N-grams)
    matched_entity: Optional[EntityMatch] = None
    words = corrected_norm.split()

    # Scan n-grams from 4-gram down to 1-gram
    candidate_phrases = []
    n = len(words)
    for length in range(min(4, n), 0, -1):
        for i in range(n - length + 1):
            phrase = " ".join(words[i:i + length])
            candidate_phrases.append(phrase)

    GENERIC_IGNORE_PHRASES = {
        "what is", "what is a", "what is an", "how to apply", "required documents",
        "eligibility criteria", "for students", "for farmers", "a government scheme",
        "government scheme", "government schemes", "government scheme mean",
        "government scheme means", "what does government", "what is government",
        "schemes for", "scholarships for"
    }
    has_portal_keyword = any(k in corrected_norm for k in ["portal", "dbt", "website", "site", "online", "login", "register", "mahadbt", "nsp", "myscheme", "jansamarth"])

    for phrase in candidate_phrases:
        # Ignore phrases that are purely generic intent words
        if phrase in GENERIC_IGNORE_PHRASES:
            continue
        match = FuzzyMatcher.match_entity(phrase)
        if match:
            # If candidate match is a PORTAL entity, require explicit portal keywords or high confidence
            if match.entity.entity_type == "PORTAL" and not has_portal_keyword and match.similarity_score < 0.90:
                continue

            if not matched_entity:
                matched_entity = match
            elif match.similarity_score > matched_entity.similarity_score + 0.05:
                matched_entity = match
            elif match.entity.entity_type == "SCHEME" and matched_entity.entity.entity_type == "STATE" and match.similarity_score >= 0.80:
                matched_entity = match

            if matched_entity and matched_entity.confidence_level == "HIGH" and matched_entity.entity.entity_type == "SCHEME":
                break

    # 3. Context-Aware Entity Resolution (Follow-up questions)
    if not matched_entity and conversation_context and conversation_context.get("last_scheme"):
        last_scheme_name = conversation_context["last_scheme"]
        ctx_match = FuzzyMatcher.match_entity(last_scheme_name)
        if ctx_match:
            matched_entity = ctx_match
            logger.info(f"Resolved entity '{last_scheme_name}' from conversation context.")

    # 4. Extract State
    detected_state = None
    if matched_entity and matched_entity.entity.state:
        detected_state = matched_entity.entity.state
    else:
        for phrase in candidate_phrases:
            state_match = FuzzyMatcher.match_entity(phrase)
            if state_match and state_match.entity.entity_type == "STATE":
                detected_state = state_match.entity.state
                break

    # 5. Determine Final Entity Confidence Level
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
        detected_category=None,
        detected_beneficiary=None,
        corrected_keywords=corrections,
        is_ambiguous=is_ambiguous,
        ambiguous_options=ambiguous_options,
    )
