"""Personalized AI Scheme Recommendation Service — Schemora.

Architecture:
  User Profile
        ↓
  Profile normalization
        ↓
  Structured eligibility filtering (PostgreSQL)
        ↓
  pgvector semantic retrieval & boost
        ↓
  Deterministic relevance scoring (0.0 to 1.0)
        ↓
  Match type classification (LIKELY_MATCH, POTENTIAL_MATCH, REQUIRES_VERIFICATION)
        ↓
  Groq grounded explanation (1-2 sentences per scheme)
        ↓
  Scheme-specific verified URLs & UI payload
"""

import logging
import re
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheme import Scheme
from app.models.knowledge import KnowledgeChunk
from app.models.student_profile import StudentProfile
from app.schemas.ai import (
    AIRecommendationItem,
    AIRecommendationResponse,
    AIRecommendationProfileInput,
)
from app.services.groq_service import _call_groq, _get_api_key, _get_generation_model

logger = logging.getLogger(__name__)

PORTAL_SCHEME_IDS = {
    "portal-myscheme", "portal-mahadbt", "portal-nsp", "portal-jansamarth",
    "myscheme", "mahadbt", "nsp", "jansamarth"
}

PORTAL_TITLE_KEYWORDS = [
    "myscheme", "mahadbt portal", "national scholarship portal",
    "jan samarth portal", "aaple sarkar dbt portal"
]


def calculate_age_from_dob(dob: Optional[date]) -> Optional[float]:
    """Calculate age in years from date of birth."""
    if not dob:
        return None
    if isinstance(dob, str):
        try:
            dob = datetime.strptime(dob, "%Y-%m-%d").date()
        except ValueError:
            return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def normalize_profile_input(profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw profile dict into standard parameters for recommendation matching."""
    age = profile_data.get("age")
    dob = profile_data.get("date_of_birth") or profile_data.get("dob")
    if age is None and dob:
        age = calculate_age_from_dob(dob)

    state = str(profile_data.get("state") or "").strip()
    gender = str(profile_data.get("gender") or "All").strip().title()

    raw_occ = str(profile_data.get("occupation") or profile_data.get("employment_status") or "").strip()
    student_status = bool(profile_data.get("student_status", False))
    farmer_status = bool(profile_data.get("farmer_status", False))

    if farmer_status:
        occupation = "Farmer"
    elif student_status:
        occupation = "Student"
    elif not raw_occ or raw_occ.lower() == "unemployed":
        edu = str(profile_data.get("education_level") or profile_data.get("education") or "").strip()
        if edu:
            occupation = "Student"
        else:
            occupation = "General Citizen"
    else:
        occupation = raw_occ.title()

    # Explicit keyword overrides
    if any(k in raw_occ.lower() for k in ["farm", "agri", "kisan", "crop"]):
        occupation = "Farmer"
    elif any(k in raw_occ.lower() for k in ["stud", "scholar", "school", "college"]):
        occupation = "Student"
    elif age and age >= 60:
        occupation = "Senior Citizen"

    income = profile_data.get("annual_family_income") or profile_data.get("annual_income")
    try:
        income_val = float(income) if income is not None else None
    except (ValueError, TypeError):
        income_val = None

    education = str(profile_data.get("education_level") or profile_data.get("education") or "").strip()
    category = str(profile_data.get("social_category") or profile_data.get("category") or "General").strip().upper()
    lang = str(profile_data.get("language") or "en").strip().lower()

    return {
        "age": age,
        "gender": gender,
        "state": state,
        "occupation": occupation,
        "education": education,
        "income": income_val,
        "category": category,
        "language": lang,
    }


def compute_deterministic_score(
    scheme: Scheme,
    norm_profile: Dict[str, Any]
) -> Tuple[float, str, List[str], List[str]]:
    """Calculate a deterministic relevance score (0.0 to 1.0) and match classification."""
    score = 0.50
    reasons = []
    missing = []

    user_state = norm_profile["state"]
    user_occ = norm_profile["occupation"]
    user_gender = norm_profile["gender"]
    user_age = norm_profile["age"]
    user_income = norm_profile["income"]
    user_category = norm_profile["category"]

    s_title = (scheme.title or "").lower()
    s_desc = (scheme.short_description or "").lower()
    s_ben = (scheme.benefit_summary or "").lower()
    s_text = f"{s_title} {s_desc} {s_ben} {scheme.beneficiaries or ''} {scheme.occupation or ''}".lower()

    # 1. State Alignment (+0.20)
    if scheme.state and user_state and scheme.state.lower() == user_state.lower():
        score += 0.20
        reasons.append(user_state)
    elif scheme.jurisdiction and scheme.jurisdiction.lower() == "central":
        score += 0.10
        reasons.append("Central Government Initiative")
    elif scheme.state and user_state and scheme.state.lower() != user_state.lower():
        score -= 0.35
        missing.append(f"Requires {scheme.state} domicile")

    # 2. Occupation & Beneficiary Alignment (+0.25)
    if user_occ.lower() == "farmer":
        if any(k in s_text for k in ["farm", "kisan", "agri", "crop", "land", "soil", "cultivat"]):
            score += 0.25
            reasons.append("Farmer / Agricultural Beneficiary")
        elif "student" in s_text or "scholarship" in s_text:
            score -= 0.30

    elif user_occ.lower() == "student":
        if any(k in s_text for k in ["student", "scholarship", "college", "school", "education", "matric", "tuition"]):
            score += 0.25
            reasons.append("Student & Education Aid")

    elif user_occ.lower() == "senior citizen" or (user_age and user_age >= 60):
        if any(k in s_text for k in ["senior", "pension", "old age", "elderly", "vaya"]):
            score += 0.25
            reasons.append("Senior Citizen Support")

    # 3. Gender Eligibility (+0.10)
    s_gender = (scheme.gender_eligibility or "All").lower()
    if s_gender in ["all", "any"]:
        score += 0.05
    elif user_gender and user_gender.lower() in s_gender:
        score += 0.15
        reasons.append(f"Targeted for {user_gender}")
        if any(k in s_text for k in ["women", "female", "girl", "ladki", "kanya", "bahin"]):
            reasons.append("Women Empowerment Initiative")
    else:
        score -= 0.40
        missing.append(f"Restricted to {scheme.gender_eligibility}")

    # 4. Age Eligibility (+0.10)
    if user_age is not None:
        if scheme.min_age is not None and user_age < scheme.min_age:
            score -= 0.35
            missing.append(f"Minimum age {int(scheme.min_age)} years required")
        elif scheme.max_age is not None and user_age > scheme.max_age:
            score -= 0.35
            missing.append(f"Maximum age {int(scheme.max_age)} years exceeded")
        elif scheme.min_age is not None or scheme.max_age is not None:
            score += 0.10
            reasons.append(f"Age {int(user_age)} qualifies")

    # 5. Annual Income Eligibility (+0.10)
    if user_income is not None and scheme.max_family_income is not None:
        if user_income <= scheme.max_family_income:
            score += 0.10
            reasons.append(f"Income within threshold (<= ₹{int(scheme.max_family_income):,})")
        else:
            score -= 0.30
            missing.append(f"Income exceeds ₹{int(scheme.max_family_income):,} limit")

    # 6. Social Category Alignment (+0.05)
    s_cats = (scheme.social_categories or "All").upper()
    if user_category and user_category in s_cats and "ALL" not in s_cats:
        score += 0.10
        reasons.append(f"Category {user_category}")

    score = max(0.05, min(0.99, score))

    if score >= 0.75 and not missing:
        match_type = "LIKELY_MATCH"
    elif score >= 0.45:
        match_type = "POTENTIAL_MATCH"
    else:
        match_type = "REQUIRES_VERIFICATION"

    return (round(score, 2), match_type, list(dict.fromkeys(reasons)), list(dict.fromkeys(missing)))


async def generate_grounded_relevance_explanation(
    scheme: Scheme,
    norm_profile: Dict[str, Any],
    reasons: List[str]
) -> str:
    """Generate a concise, 1-2 sentence grounded explanation using Groq (or clean fallback)."""
    api_key = _get_api_key()
    model = _get_generation_model()

    profile_desc = f"State: {norm_profile['state']}, Occupation: {norm_profile['occupation']}, Gender: {norm_profile['gender']}, Age: {norm_profile['age'] or 'N/A'}"
    reasons_text = ", ".join(reasons) if reasons else "General eligibility match"

    prompt = f"""You are Schemora AI Assistant.
Write a 1-2 sentence personalized explanation for why this government scheme is relevant to the user.

USER PROFILE:
{profile_desc}

SCHEME DETAILS:
Name: {scheme.title}
Provider: {scheme.provider} ({scheme.jurisdiction})
Benefit: {scheme.benefit_summary}
Short Description: {scheme.short_description}
Matched Criteria: {reasons_text}

RULES:
1. Write ONLY 1-2 sentences.
2. Ground your explanation STRICTLY in the scheme details above.
3. Language: {norm_profile['language']} (If 'en', write ONLY in English. If 'hi', in Hindi. If 'gu', in Gujarati).
4. Do NOT invent eligibility facts, dates, or URLs.
"""
    if api_key and len(api_key) > 5:
        ans = await _call_groq(prompt, api_key, model)
        if ans:
            return ans.strip()

    if norm_profile["language"] == "hi":
        return f"यह योजना आपके प्रोफ़ाइल ({norm_profile['state']} - {norm_profile['occupation']}) के अनुसार उपयुक्त है। इसके तहत {scheme.benefit_summary or 'वित्तीय सहायता'} प्रदान की जाती है।"
    elif norm_profile["language"] == "gu":
        return f"આ યોજના તમારા પ્રોફાઇલ ({norm_profile['state']} - {norm_profile['occupation']}) મુજબ ઉપયોગી છે. તેના હેઠળ {scheme.benefit_summary or 'નાણાકીય સહાય'} મળે છે."
    else:
        return f"Recommended based on your profile as a {norm_profile['occupation']} in {norm_profile['state']}. {scheme.benefit_summary or scheme.short_description}"


async def generate_recommendations(
    db: AsyncSession,
    profile: Optional[StudentProfile] = None,
    input_data: Optional[AIRecommendationProfileInput] = None,
    limit: int = 5,
) -> AIRecommendationResponse:
    """Main recommendation pipeline matching profile -> PostgreSQL filters -> pgvector -> deterministic scoring -> Groq explanation."""
    raw_data = {}
    if profile:
        raw_data = {
            "age": calculate_age_from_dob(profile.date_of_birth),
            "gender": profile.gender,
            "state": profile.state,
            "occupation": profile.occupation or profile.employment_status,
            "education_level": profile.education_level,
            "annual_family_income": profile.annual_family_income,
            "social_category": profile.social_category,
        }

    if input_data:
        inp_dict = input_data.model_dump(exclude_unset=True, exclude_none=True)
        raw_data.update({k: v for k, v in inp_dict.items() if v is not None and v != ""})

    norm_profile = normalize_profile_input(raw_data)

    missing_fields = []
    if not norm_profile["state"]:
        missing_fields.append("state")
    if not norm_profile["occupation"] or norm_profile["occupation"] == "General Citizen":
        missing_fields.append("occupation")

    profile_incomplete = len(missing_fields) > 0 and not profile and not input_data

    # 1. Structured PostgreSQL Query
    stmt = select(Scheme).where(Scheme.is_published == True)
    res = await db.execute(stmt)
    all_schemes = res.scalars().all()

    # 2. Exclude portal aggregators
    candidate_schemes = []
    candidate_ids = []
    for s in all_schemes:
        s_id = (s.id or "").lower()
        s_title = (s.title or "").lower()
        if s_id in PORTAL_SCHEME_IDS or any(k in s_title for k in PORTAL_TITLE_KEYWORDS):
            continue
        candidate_schemes.append(s)
        candidate_ids.append(s.id)

    # 3. Vector semantic retrieval boost
    vec_query = f"{norm_profile['occupation']} schemes in {norm_profile['state']} for {norm_profile['gender']} {norm_profile['category']}"
    vec_matches = []
    try:
        from app.services.retrieval_service_impl import retrieve_relevant_chunks
        vec_chunks = await retrieve_relevant_chunks(db, query=vec_query, state=norm_profile["state"], top_k=10)
        vec_matches = [c.get("scheme_id") for c in vec_chunks if c.get("scheme_id")]
    except Exception as err:
        logger.warning(f"Vector retrieval boost skipped: {err}")

    # 4. Deterministic Scoring
    scored_items = []
    for s in candidate_schemes:
        score, match_type, reasons, missing = compute_deterministic_score(s, norm_profile)
        if s.id in vec_matches:
            score = round(min(0.99, score + 0.10), 2)
            reasons.append("Semantic Vector Match")

        scored_items.append({
            "scheme": s,
            "score": score,
            "match_type": match_type,
            "reasons": reasons,
            "missing": missing,
        })

    scored_items.sort(key=lambda x: (x["match_type"] == "LIKELY_MATCH", x["score"]), reverse=True)
    top_candidates = scored_items[:limit]

    # 5. Explanations & URL Selection
    rec_items = []
    for item in top_candidates:
        s: Scheme = item["scheme"]
        explanation = await generate_grounded_relevance_explanation(s, norm_profile, item["reasons"])

        info_url = s.official_scheme_url if (s.official_scheme_url and "india.gov.in" not in s.official_scheme_url.lower()) else s.source_url
        app_url = s.application_url if (s.application_url and "india.gov.in" not in s.application_url.lower()) else None

        if info_url and "india.gov.in" in info_url.lower():
            info_url = None

        best_url = app_url or info_url or s.official_portal_url or None

        rec_items.append(AIRecommendationItem(
            scheme_id=s.id,
            scheme_name=s.title,
            match_type=item["match_type"],
            score=item["score"],
            match_reasons=item["reasons"],
            relevance_explanation=explanation,
            benefits=s.benefit_summary or s.short_description,
            eligibility=f"Gender: {s.gender_eligibility} | Category: {s.social_categories} | State: {s.state or 'Central'}",
            provider=s.provider,
            jurisdiction=s.jurisdiction,
            state=s.state,
            official_scheme_url=info_url,
            application_url=app_url,
            best_action_url=best_url,
        ))

    debug_info = {
        "input_profile": raw_data,
        "normalized_profile": norm_profile,
        "structured_filters": {
            "state": norm_profile["state"],
            "occupation": norm_profile["occupation"],
            "gender": norm_profile["gender"],
            "age": norm_profile["age"],
        },
        "total_candidate_schemes": len(candidate_schemes),
        "candidate_scheme_ids": candidate_ids[:10],
        "vector_query": vec_query,
        "vector_matches": vec_matches,
        "recommended_scheme_ids": [r.scheme_id for r in rec_items],
    }

    return AIRecommendationResponse(
        recommendations=rec_items,
        profile_incomplete=profile_incomplete,
        missing_fields=missing_fields,
        debug_info=debug_info,
    )
