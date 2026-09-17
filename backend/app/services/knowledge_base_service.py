"""Knowledge Base Service — Schemora RAG Phase 1.

Converts structured Phase 0 scheme JSON records into meaningful semantic
chunks that are then embedded and stored for retrieval.

Chunking strategy: NOT random character splits. Each scheme produces up to 16
section-level chunks with full metadata preserved per chunk:

  1. overview             — name, description, department, category
  2. benefits             — what you receive, amounts, frequency
  3. eligibility          — who can apply, rules in plain language
  4. documents            — required documents list
  5. application          — step-by-step how to apply, channels
  6. deadlines            — windows, cycles, opens/closes dates
  7. notes                — verification status, important caveats
  8. faqs                 — frequently asked questions
  9. objective            — scheme objective / purpose
  10. financial_details   — specific amounts, coverage, frequency
  11. beneficiaries       — target groups, demographic filters
  12. application_channels — online portal URL, offline CSC location
  13. status              — active/closed/upcoming, validity
  14. renewal             — renewal criteria, renewal process
  15. restrictions        — exclusions, who cannot apply
  16. contact             — helpline, email, grievance portal

Every chunk carries:
  scheme_id, scheme_name, section, jurisdiction, state, category, ministry,
  language, content_hash, source_authority,
  official_info_url, official_app_url, last_verified_at, scheme_version
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.config import settings
from app.models.scheme import Scheme
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.services.embedding_service import embed_text, embedding_to_json
from app.services import vector_service

import hashlib

logger = logging.getLogger(__name__)

# Primary dataset path with fallback
DATASET_PATH_PRIMARY = Path(__file__).resolve().parent.parent.parent.parent / "data" / "schemes" / "schemes.v1.json"
DATASET_PATH_FALLBACK = Path(__file__).resolve().parent.parent.parent / "data" / "final" / "schemes.json"

DATASET_PATH = DATASET_PATH_PRIMARY if DATASET_PATH_PRIMARY.exists() else DATASET_PATH_FALLBACK

# Section labels — core
SECTION_OVERVIEW = "overview"
SECTION_BENEFITS = "benefits"
SECTION_ELIGIBILITY = "eligibility"
SECTION_DOCUMENTS = "documents"
SECTION_APPLICATION = "application"
SECTION_DEADLINES = "deadlines"
SECTION_NOTES = "notes"
SECTION_FAQS = "faqs"

# Section labels — extended
SECTION_OBJECTIVE = "objective"
SECTION_FINANCIAL_DETAILS = "financial_details"
SECTION_BENEFICIARIES = "beneficiaries"
SECTION_APPLICATION_CHANNELS = "application_channels"
SECTION_STATUS = "status"
SECTION_RENEWAL = "renewal"
SECTION_RESTRICTIONS = "restrictions"
SECTION_CONTACT = "contact"



# ── Chunk builders ────────────────────────────────────────────────────────────

def _build_overview_chunk(s: Dict[str, Any]) -> str:
    lines = [
        f"Scheme: {s.get('scheme_name', '')}",
        f"Category: {s.get('scheme_category', '')}",
        f"Jurisdiction: {s.get('jurisdiction', '')}",
    ]
    if s.get("state"):
        lines.append(f"State: {s['state']}")
    lines.append(f"Department: {s.get('department', '')}")
    desc = s.get("description") or s.get("short_description") or ""
    if desc:
        lines.append(f"Description: {desc[:800]}")
    lines.append(f"Status: {s.get('status', 'Active')}")
    return "\n".join(lines)


def _build_benefits_chunk(s: Dict[str, Any]) -> str:
    benefits = s.get("benefits", [])
    if not benefits:
        return f"Benefits for {s.get('scheme_name', '')}: Not yet fully verified. Check official portal."
    lines = [f"Benefits provided by {s.get('scheme_name', '')}:"]
    for b in benefits:
        desc = b.get("description", "")
        amount = b.get("amount")
        currency = b.get("currency", "INR")
        frequency = b.get("frequency", "")
        vstatus = b.get("verification_status", "")
        if amount:
            lines.append(f"  • {desc} — Amount: {currency} {amount} ({frequency})")
        else:
            lines.append(f"  • {desc} ({frequency})")
        if vstatus == "VerificationRequired":
            lines.append(f"    Note: Exact amount requires verification from official source.")
    return "\n".join(lines)


def _flatten_eligibility_conditions(conditions: List[Dict], depth: int = 0) -> List[str]:
    """Recursively flatten nested rule conditions into plain text lines."""
    lines = []
    indent = "  " * depth
    for cond in conditions:
        ctype = cond.get("type", "condition")
        if ctype == "condition":
            desc = cond.get("description", "")
            vstatus = cond.get("verification_status", "Verified")
            marker = "✓" if vstatus == "Verified" else "?"
            lines.append(f"{indent}{marker} {desc}")
        elif ctype in ("and", "or"):
            op_label = "All of the following" if ctype == "and" else "Any one of the following"
            lines.append(f"{indent}[{op_label}]:")
            sub = cond.get("conditions", [])
            lines.extend(_flatten_eligibility_conditions(sub, depth + 1))
    return lines


def _build_eligibility_chunk(s: Dict[str, Any]) -> str:
    lines = [f"Eligibility criteria for {s.get('scheme_name', '')}:"]

    rules = s.get("eligibility_rules", {})
    root = rules.get("root", {})
    conditions = root.get("conditions", [])

    if conditions:
        flat = _flatten_eligibility_conditions(conditions)
        lines.extend(flat)
    else:
        lines.append("Detailed eligibility criteria require verification from official portal.")

    # Append high-level filters if present
    for field, label in [
        ("gender_eligibility", "Gender"), ("social_categories", "Social Category"),
    ]:
        val = s.get(field)
        if val and val != "All":
            lines.append(f"  • {label}: {val}")

    return "\n".join(lines)


def _build_documents_chunk(s: Dict[str, Any]) -> str:
    docs = s.get("required_documents", [])
    lines = [f"Required documents for {s.get('scheme_name', '')}:"]
    if not docs:
        lines.append("Document checklist requires verification. Check official portal.")
        return "\n".join(lines)
    for d in docs:
        name = d.get("name", "")
        required = d.get("required", True)
        vstatus = d.get("verification_status", "Verified")
        marker = "✓" if vstatus == "Verified" else "?"
        req_label = "(Required)" if required else "(Optional)"
        lines.append(f"  {marker} {name} {req_label}")
    return "\n".join(lines)


def _build_application_chunk(s: Dict[str, Any]) -> str:
    steps = s.get("application_process", [])
    lines = [f"How to apply for {s.get('scheme_name', '')}:"]
    if s.get("official_application_url"):
        lines.append(f"Apply at: {s['official_application_url']}")
    if not steps:
        lines.append("Application process requires verification from official portal.")
        return "\n".join(lines)
    for step in sorted(steps, key=lambda x: x.get("step_number", 0)):
        n = step.get("step_number", "")
        desc = step.get("description", "")
        channel = step.get("channel", "")
        lines.append(f"  Step {n} ({channel}): {desc}")
    return "\n".join(lines)


def _build_deadlines_chunk(s: Dict[str, Any]) -> str:
    windows = s.get("application_windows", [])
    lines = [f"Application deadlines for {s.get('scheme_name', '')}:"]
    if s.get("application_cycle"):
        lines.append(f"Cycle: {s['application_cycle']}")
    if not windows:
        lines.append("Application window not announced. Check official portal for updates.")
        return "\n".join(lines)
    for w in windows:
        dtype = w.get("deadline_type", "")
        opens = w.get("opens_on") or "Not announced"
        closes = w.get("closes_on") or "Not announced"
        cycle = w.get("application_cycle", "")
        lines.append(f"  • Opens: {opens} | Closes: {closes} | Type: {dtype}")
        if cycle:
            lines.append(f"    Cycle: {cycle}")
    if s.get("application_deadline"):
        lines.append(f"Deadline: {s['application_deadline']}")
    return "\n".join(lines)


def _build_notes_chunk(s: Dict[str, Any]) -> str:
    verification = s.get("verification", {})
    overall = verification.get("overall_status", "Unknown")
    notes_text = verification.get("notes", "")
    required_fields = verification.get("verification_required_fields", [])
    verified_fields = verification.get("verified_fields", [])
    verified_at = s.get("verified_at", "")
    verified_by = s.get("verified_by", "")

    lines = [
        f"Important notes for {s.get('scheme_name', '')}:",
        f"Verification status: {overall}",
        f"Verified at: {verified_at}",
        f"Verified by: {verified_by}",
    ]
    if notes_text:
        lines.append(f"Note: {notes_text}")
    if verified_fields:
        lines.append(f"Verified fields: {', '.join(verified_fields[:5])}")
    if required_fields:
        lines.append(f"Fields requiring verification: {', '.join(required_fields[:5])}")
    lines.append(
        f"Official information: {s.get('official_information_url', 'Not available')}"
    )
    return "\n".join(lines)


def _build_faqs_chunk(s: Dict[str, Any]) -> str:
    faqs = s.get("faqs", [])
    if not faqs:
        return ""
    lines = [f"Frequently Asked Questions (FAQs) for {s.get('scheme_name', '')}:"]
    for faq in faqs:
        q = faq.get("question", "")
        a = faq.get("answer", "")
        if q and a:
            lines.append(f"Q: {q}\nA: {a}\n")
    return "\n".join(lines).strip()


# ── Extended chunk builders ───────────────────────────────────────────────────

def _build_objective_chunk(s: Dict[str, Any]) -> str:
    """Build an objective/purpose chunk. Skip if no objective field."""
    objective = s.get("objective") or s.get("scheme_objective") or ""
    if not objective:
        return ""
    lines = [
        f"Objective and Purpose of {s.get('scheme_name', '')}:",
        objective[:600],
    ]
    ministry = s.get("ministry") or s.get("department") or ""
    if ministry:
        lines.append(f"Implementing Ministry: {ministry}")
    return "\n".join(lines)


def _build_financial_details_chunk(s: Dict[str, Any]) -> str:
    """Build a financial details chunk with amounts, frequency, coverage."""
    benefits = s.get("benefits", [])
    if not benefits:
        return ""

    has_amount = any(b.get("amount") for b in benefits if isinstance(b, dict))
    if not has_amount:
        return ""  # Skip if no structured financial data

    lines = [f"Financial Details for {s.get('scheme_name', '')}:"]
    for b in benefits:
        if not isinstance(b, dict):
            continue
        amount = b.get("amount")
        if not amount:
            continue
        currency = b.get("currency", "INR")
        frequency = b.get("frequency", "")
        desc = b.get("description", "")
        coverage = b.get("coverage") or ""
        line = f"  • {currency} {amount}"
        if frequency:
            line += f" per {frequency}"
        if desc:
            line += f" — {desc[:120]}"
        if coverage:
            line += f" (Coverage: {coverage})"
        lines.append(line)
    return "\n".join(lines)


def _build_beneficiaries_chunk(s: Dict[str, Any]) -> str:
    """Build a beneficiaries/target group chunk."""
    parts = []
    name = s.get("scheme_name", "")

    target_groups = s.get("target_groups") or s.get("beneficiaries") or []
    if isinstance(target_groups, list) and target_groups:
        parts.append("Target Groups: " + ", ".join(str(g) for g in target_groups))

    gender = s.get("gender_eligibility") or ""
    if gender and gender != "All":
        parts.append(f"Gender: {gender}")

    social_cats = s.get("social_categories") or ""
    if social_cats and social_cats != "All":
        parts.append(f"Social Categories: {social_cats}")

    age_min = s.get("min_age")
    age_max = s.get("max_age")
    if age_min or age_max:
        age_str = f"Age: {age_min or 'Any'} to {age_max or 'Any'} years"
        parts.append(age_str)

    income_limit = s.get("max_family_income") or s.get("income_limit")
    if income_limit:
        parts.append(f"Maximum Annual Family Income: ₹{income_limit}")

    occupation = s.get("occupation") or s.get("beneficiary_occupation") or ""
    if occupation:
        parts.append(f"Occupation: {occupation}")

    if not parts:
        return ""

    return f"Who can benefit from {name}:\n" + "\n".join(f"  • {p}" for p in parts)


def _build_application_channels_chunk(s: Dict[str, Any]) -> str:
    """Build a chunk describing WHERE to apply (online portal, offline CSC)."""
    lines = [f"How and Where to Apply for {s.get('scheme_name', '')}:"]

    app_url = s.get("official_application_url") or ""
    info_url = s.get("official_information_url") or ""

    if app_url:
        lines.append(f"  • Online Application Portal: {app_url}")
    if info_url and info_url != app_url:
        lines.append(f"  • Official Information: {info_url}")

    steps = s.get("application_process", [])
    online_steps = [st for st in steps if isinstance(st, dict) and "online" in str(st.get("channel", "")).lower()]
    offline_steps = [st for st in steps if isinstance(st, dict) and "offline" in str(st.get("channel", "")).lower()]
    csc_steps = [st for st in steps if isinstance(st, dict) and "csc" in str(st.get("channel", "")).lower()]

    if online_steps:
        lines.append("  • Online Mode: Application via official web portal.")
    if offline_steps or csc_steps:
        lines.append("  • Offline Mode: Application at Common Service Centre (CSC) / Jan Seva Kendra / Tehsil Office.")

    if not app_url and not info_url:
        return ""

    return "\n".join(lines)


def _build_status_chunk(s: Dict[str, Any]) -> str:
    """Build a scheme status chunk."""
    status = s.get("status") or s.get("implementation_status") or "Active"
    name = s.get("scheme_name", "")
    lines = [f"Current Status of {name}:", f"  Status: {status}"]

    validity = s.get("validity_period") or ""
    if validity:
        lines.append(f"  Validity: {validity}")

    start = s.get("scheme_start_date") or s.get("application_start") or ""
    end = s.get("scheme_end_date") or s.get("application_end") or ""
    if start:
        lines.append(f"  Application Start: {start}")
    if end:
        lines.append(f"  Application End / Deadline: {end}")

    return "\n".join(lines)


def _build_renewal_chunk(s: Dict[str, Any]) -> str:
    """Build a renewal information chunk."""
    renewal_info = s.get("renewal") or s.get("renewal_process") or s.get("renewal_details") or {}
    name = s.get("scheme_name", "")

    if not renewal_info:
        # Infer from scheme type
        cat = str(s.get("scheme_category") or s.get("category") or "").lower()
        if "scholarship" in cat or "education" in cat:
            return (
                f"Renewal for {name}:\n"
                "  • This scholarship typically requires annual renewal on the National Scholarship Portal (scholarships.gov.in) or State portal.\n"
                "  • Minimum academic performance must be maintained each year to qualify for renewal.\n"
                "  • Submit updated income certificate and current year enrollment proof."
            )
        return ""

    lines = [f"Renewal Process for {name}:"]
    if isinstance(renewal_info, dict):
        process = renewal_info.get("process") or renewal_info.get("description") or ""
        if process:
            lines.append(f"  {process[:400]}")
        period = renewal_info.get("period") or renewal_info.get("frequency") or ""
        if period:
            lines.append(f"  Renewal Period: {period}")
    elif isinstance(renewal_info, str) and renewal_info:
        lines.append(f"  {renewal_info[:400]}")

    return "\n".join(lines)


def _build_restrictions_chunk(s: Dict[str, Any]) -> str:
    """Build a restrictions/exclusions chunk (who CANNOT apply)."""
    restrictions = s.get("restrictions") or s.get("exclusions") or []
    if not restrictions:
        return ""

    name = s.get("scheme_name", "")
    lines = [f"Restrictions and Exclusions for {name} (Who cannot apply):"]
    if isinstance(restrictions, list):
        for r in restrictions:
            r_text = str(r.get("description") or r) if isinstance(r, dict) else str(r)
            if r_text.strip():
                lines.append(f"  • {r_text.strip()}")
    elif isinstance(restrictions, str):
        lines.append(f"  {restrictions[:400]}")

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def _build_contact_chunk(s: Dict[str, Any]) -> str:
    """Build a contact/helpline/grievance chunk."""
    helpline = s.get("helpline") or s.get("helpline_number") or ""
    email = s.get("email") or s.get("contact_email") or ""
    grievance = s.get("grievance_portal") or s.get("grievance_url") or ""
    info_url = s.get("official_information_url") or ""

    if not any([helpline, email, grievance, info_url]):
        return ""

    name = s.get("scheme_name", "")
    lines = [f"Contact Information for {name}:"]
    if helpline:
        lines.append(f"  • Helpline Number: {helpline}")
    if email:
        lines.append(f"  • Email: {email}")
    if grievance:
        lines.append(f"  • Grievance Portal: {grievance}")
    if info_url:
        lines.append(f"  • Official Portal: {info_url}")

    return "\n".join(lines)


# ── Main chunker ──────────────────────────────────────────────────────────────

SECTION_BUILDERS = [
    # Core sections
    (SECTION_OVERVIEW, _build_overview_chunk),
    (SECTION_BENEFITS, _build_benefits_chunk),
    (SECTION_ELIGIBILITY, _build_eligibility_chunk),
    (SECTION_DOCUMENTS, _build_documents_chunk),
    (SECTION_APPLICATION, _build_application_chunk),
    (SECTION_DEADLINES, _build_deadlines_chunk),
    (SECTION_NOTES, _build_notes_chunk),
    (SECTION_FAQS, _build_faqs_chunk),
    # Extended sections
    (SECTION_OBJECTIVE, _build_objective_chunk),
    (SECTION_FINANCIAL_DETAILS, _build_financial_details_chunk),
    (SECTION_BENEFICIARIES, _build_beneficiaries_chunk),
    (SECTION_APPLICATION_CHANNELS, _build_application_channels_chunk),
    (SECTION_STATUS, _build_status_chunk),
    (SECTION_RENEWAL, _build_renewal_chunk),
    (SECTION_RESTRICTIONS, _build_restrictions_chunk),
    (SECTION_CONTACT, _build_contact_chunk),
]



def build_chunks_for_scheme(s: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build all semantic chunks for a single scheme dict.

    Returns a list of chunk dicts with content + metadata.
    Each chunk now includes: ministry, language, content_hash, source_authority.
    """
    scheme_id = s.get("scheme_id", "")
    scheme_name = s.get("scheme_name") or s.get("title") or ""
    jurisdiction = s.get("jurisdiction") or s.get("government_level") or "Central"
    state = s.get("state")
    ministry = s.get("ministry") or s.get("department") or ""
    language = s.get("language", "en")
    source_authority = (
        "State" if state
        else ("GOI" if "central" in jurisdiction.lower() else "Unknown")
    )

    category_val = s.get("scheme_category") or s.get("category") or ""
    if isinstance(category_val, list):
        category = ", ".join(category_val)
    else:
        category = str(category_val)

    source_url_raw = s.get("source_url") or s.get("official_information_url") or (s.get("official_source") or {}).get("url") or ""
    source_name = s.get("source_name") or (s.get("official_source") or {}).get("name") or ("myScheme" if "myscheme.gov.in" in source_url_raw.lower() else "Official Source")
    
    official_scheme_url = s.get("official_scheme_url") or source_url_raw
    official_info_url = official_scheme_url or source_url_raw

    raw_app_url = s.get("application_url") or s.get("official_application_url") or (s.get("application") or {}).get("url") or ""
    if raw_app_url and "myscheme.gov.in" not in raw_app_url.lower():
        official_app_url = raw_app_url
    else:
        official_app_url = ""

    official_portal_url = s.get("official_portal_url") or (official_app_url if official_app_url else official_scheme_url)

    last_verified_at = s.get("verified_at") or s.get("last_verified") or "2026-08-07"
    scheme_version = s.get("scheme_version", "v1")

    # Collect source IDs
    source_ids = s.get("source_documents", [])
    source_id = source_ids[0] if source_ids else ""

    chunks = []
    for idx, (section, builder) in enumerate(SECTION_BUILDERS):
        try:
            content = builder(s).strip()
            if not content:
                continue
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
            chunks.append({
                "chunk_index": idx,
                "section": section,
                "content": content,
                "scheme_id": scheme_id,
                "scheme_name": scheme_name,
                "jurisdiction": jurisdiction,
                "state": state,
                "category": category,
                "ministry": ministry,
                "language": language,
                "content_hash": content_hash,
                "source_authority": source_authority,
                "source_id": source_id,
                "source_name": source_name,
                "official_info_url": official_info_url,
                "official_app_url": official_app_url,
                "official_scheme_url": official_scheme_url,
                "official_portal_url": official_portal_url,
                "last_verified_at": last_verified_at,
                "scheme_version": scheme_version,
                "metadata_json": json.dumps({
                    "source_url": source_url_raw,
                    "source_name": source_name,
                    "official_scheme_url": official_scheme_url,
                    "official_info_url": official_info_url,
                    "official_app_url": official_app_url,
                    "official_portal_url": official_portal_url,
                    "title": f"{scheme_name} — {section.title()}",
                    "scheme_id": scheme_id,
                    "ministry": ministry,
                    "language": language,
                    "source_authority": source_authority,
                }),
            })
        except Exception as e:
            logger.warning(f"Failed to build {section} chunk for {scheme_id}: {e}")

    return chunks


# ── DB operations ─────────────────────────────────────────────────────────────

async def delete_scheme_knowledge(db: AsyncSession, scheme_id: str) -> int:
    """Delete all knowledge chunks and documents for a scheme from SQL and pgvector. Returns chunk count removed."""
    try:
        chunks_result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.scheme_id == scheme_id)
        )
        chunks = chunks_result.scalars().all()
        count = len(chunks)
        for c in chunks:
            await db.delete(c)
    except Exception as e:
        logger.warning(f"Could not query KnowledgeChunk for deletion of {scheme_id}: {e}")
        count = 0

    try:
        docs_result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.scheme_id == scheme_id)
        )
        for doc in docs_result.scalars().all():
            await db.delete(doc)
    except Exception as e:
        logger.warning(f"Could not query KnowledgeDocument for deletion of {scheme_id}: {e}")

    await db.flush()
    # Synchronize vector deletion with vector service
    await vector_service.delete_vectors_by_scheme_id_async(db, scheme_id)

    return count


async def index_scheme(
    db: AsyncSession,
    scheme_data: Dict[str, Any],
    replace: bool = True,
    force_reindex: bool = False,
) -> Tuple[int, int]:
    """Index a single scheme into SQL DB and pgvector storage with duplicate SHA-256 update detection.

    Args:
        db: Async DB session.
        scheme_data: Scheme dict from Phase 0 or Scraper.
        replace: If True, delete existing chunks first (idempotent re-index).
        force_reindex: If True, bypass SHA-256 hash check and force re-indexing.

    Returns:
        (chunks_created, semantic_embeddings_count)
    """
    scheme_id = scheme_data.get("scheme_id", "")
    scheme_name = scheme_data.get("scheme_name", "Unknown")

    # Compute content SHA-256 hash for duplicate / update detection
    serialized = json.dumps(scheme_data, sort_keys=True, ensure_ascii=False)
    content_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    # Duplicate / Update Detection Check
    if not force_reindex and scheme_id:
        existing_doc_res = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.scheme_id == scheme_id)
        )
        existing_doc = existing_doc_res.scalar_one_or_none()
        if existing_doc and existing_doc.file_hash == content_hash:
            logger.info(
                f"Scheme '{scheme_id}' ({scheme_name}) content is unchanged "
                f"(SHA-256 hash {content_hash[:10]}... matched). Skipping re-indexing."
            )
            return 0, 0

    if replace:
        await delete_scheme_knowledge(db, scheme_id)

    # Ensure parent Scheme entry exists in schemes table to satisfy Foreign Key constraint
    if scheme_id:
        existing_scheme_res = await db.execute(select(Scheme).where(Scheme.id == scheme_id))
        existing_scheme = existing_scheme_res.scalar_one_or_none()
        if not existing_scheme:
            new_scheme = Scheme(
                id=scheme_id,
                slug=scheme_data.get("slug") or f"slug_{scheme_id.replace('-', '_')}",
                title=scheme_name,
                short_description=str(scheme_data.get("short_description") or scheme_data.get("description") or scheme_name)[:500],
                detailed_description=str(scheme_data.get("description") or scheme_name),
                provider=scheme_data.get("ministry") or scheme_data.get("department") or "Ministry of Social Justice",
                jurisdiction=scheme_data.get("jurisdiction") or "Central",
                state=scheme_data.get("state"),
                gender_eligibility=str(scheme_data.get("gender_eligibility") or "All"),
                social_categories=str(scheme_data.get("social_categories") or "All"),
                benefit_type=str(scheme_data.get("category") or "Financial"),
                benefit_summary=str(scheme_data.get("description") or scheme_name)[:500],
                implementation_status="Implemented",
                is_published=True,
            )
            db.add(new_scheme)
            await db.flush()

    # Create the parent document
    doc = KnowledgeDocument(
        scheme_id=scheme_id if scheme_id else None,
        title=f"{scheme_name} — Knowledge Base",
        source_url=scheme_data.get("official_information_url", ""),
        doc_type=scheme_data.get("doc_type", "OfficialGuideline"),
        file_hash=content_hash,
    )
    db.add(doc)
    await db.flush()

    # Build semantic chunks
    raw_chunks = build_chunks_for_scheme(scheme_data)
    semantic_count = 0

    for chunk_dict in raw_chunks:
        content = chunk_dict["content"]
        embedding, is_semantic = await embed_text(content)
        if is_semantic:
            semantic_count += 1

        chunk_obj = KnowledgeChunk(
            document_id=doc.id,
            scheme_id=chunk_dict["scheme_id"],
            chunk_index=chunk_dict["chunk_index"],
            content=content,
            section=chunk_dict["section"],
            scheme_name=chunk_dict["scheme_name"],
            jurisdiction=chunk_dict["jurisdiction"],
            state=chunk_dict.get("state"),
            category=chunk_dict["category"],
            source_id=chunk_dict["source_id"],
            official_info_url=chunk_dict["official_info_url"],
            official_app_url=chunk_dict["official_app_url"],
            last_verified_at=chunk_dict["last_verified_at"],
            scheme_version=chunk_dict["scheme_version"],
            embedding_json=embedding_to_json(embedding),
            embedding_vec=embedding if (is_semantic and isinstance(embedding, list)) else None,
            metadata_json=chunk_dict["metadata_json"],
            is_indexed=is_semantic,
            page_number=1,
        )
        db.add(chunk_obj)

    await db.commit()

    logger.info(
        f"Indexed scheme {scheme_id}: {len(raw_chunks)} chunks "
        f"({semantic_count} semantic into pgvector, {len(raw_chunks) - semantic_count} TF-IDF fallback)"
    )
    return len(raw_chunks), semantic_count


async def index_all_schemes(db: AsyncSession) -> Dict[str, Any]:
    """Load dataset and index all schemes into SQL and pgvector storage.

    Returns a summary dict with counts.
    """
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATASET_PATH}")

    # Clear existing knowledge records for clean re-indexing
    await db.execute(delete(KnowledgeChunk))
    await db.execute(delete(KnowledgeDocument))
    await db.commit()

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        schemes = data
        dataset_version = "v1"
    else:
        schemes = data.get("schemes", [])
        dataset_version = data.get("dataset_version", "v1")
    total_chunks = 0
    total_semantic = 0
    indexed_schemes = []
    failed_schemes = []

    for s in schemes:
        scheme_id = s.get("scheme_id", "unknown")
        try:
            chunks, semantic = await index_scheme(db, s, replace=True, force_reindex=True)
            total_chunks += chunks
            total_semantic += semantic
            indexed_schemes.append(scheme_id)
        except Exception as e:
            logger.error(f"Failed to index scheme {scheme_id}: {e}")
            failed_schemes.append({"scheme_id": scheme_id, "error": str(e)})

    # Also index Schemora Glossary concepts
    try:
        from app.services.glossary_service import ensure_glossary_indexed
        glossary_chunks = await ensure_glossary_indexed(db)
        total_chunks += glossary_chunks
        logger.info(f"Schemora Glossary: {glossary_chunks} concept chunks indexed into Knowledge Base.")
    except Exception as e:
        logger.error(f"Failed to index glossary during full indexing: {e}")

    pgvector_count = await vector_service.get_vector_count_async(db)

    return {
        "total_schemes": len(schemes),
        "indexed_schemes": len(indexed_schemes),
        "failed_schemes": failed_schemes,
        "total_chunks": total_chunks,
        "semantic_chunks": total_semantic,
        "tfidf_chunks": total_chunks - total_semantic,
        "pgvector_vectors": pgvector_count,
        "dataset_version": dataset_version,
    }



async def get_knowledge_base_status(db: AsyncSession) -> Dict[str, Any]:
    """Return current knowledge base statistics including pgvector count."""
    from sqlalchemy import func, distinct

    # Total chunks
    result = await db.execute(select(func.count(KnowledgeChunk.id)))
    total_chunks = result.scalar() or 0

    # Semantic (embedded) chunks
    result = await db.execute(
        select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.is_indexed == True)
    )
    semantic_chunks = result.scalar() or 0

    # Distinct schemes indexed
    result = await db.execute(
        select(func.count(distinct(KnowledgeChunk.scheme_id)))
        .where(KnowledgeChunk.scheme_id != None)
    )
    indexed_schemes = result.scalar() or 0

    # Documents
    result = await db.execute(select(func.count(KnowledgeDocument.id)))
    total_docs = result.scalar() or 0

    pgvector_count = await vector_service.get_vector_count_async(db)

    return {
        "total_chunks": total_chunks,
        "semantic_chunks": semantic_chunks,
        "tfidf_chunks": total_chunks - semantic_chunks,
        "pgvector_vectors": pgvector_count,
        "indexed_schemes": indexed_schemes,
        "total_documents": total_docs,
        "embedding_model": "tfidf-vector",
        "is_ready": total_chunks > 0,
    }
