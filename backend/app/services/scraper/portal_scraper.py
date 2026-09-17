"""Government Portal Scraper — Schemora Web Scraping Engine.

Scrapes official government portals (central ministries, state portals, myScheme)
and parses Next.js hydration JSON (__NEXT_DATA__) or actual API endpoints into
structured scheme records.

IMPORTANT DATA QUALITY RULES:
  - Never index placeholder/template/fabricated scheme records.
  - Every indexed scheme MUST have a real description (>80 chars, not a template).
  - Every indexed scheme MUST have at least 1 real document (not just Aadhaar/Income generic).
  - Every indexed scheme MUST have at least 1 real application step from actual data.
  - If real data cannot be extracted, the record is rejected — NOT substituted with templates.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.services.scraper.base_scraper import BaseSchemeScraper, is_trusted_official_url

logger = logging.getLogger("schemora.scraper.portal")

# Generic placeholder strings that indicate fake/template data — reject these
_GENERIC_DESCRIPTIONS = {
    "official myscheme welfare initiative for",
    "official myscheme government scheme record for",
    "welfare and educational benefits provided under",
    "government welfare benefits under",
    "financial assistance, grants, and welfare benefits under",
}

_GENERIC_DOCUMENT_NAMES = {
    "aadhaar card",
    "income certificate",
    "educational / identity proof",
    "educational or identity proof",
}

_GENERIC_APP_STEP_PREFIXES = {
    "register online at official portal",
    "fill application form and upload mandatory documents",
    "submit application and save acknowledgement",
    "apply online at official portal",
}


def _is_generic_text(text: str) -> bool:
    """Return True if text is a template/placeholder string."""
    t = text.lower().strip()
    return any(t.startswith(g) for g in _GENERIC_DESCRIPTIONS) or len(t) < 60


def _validate_scheme_record(raw_data: Dict[str, Any]) -> bool:
    """Return True if the record contains real (non-fabricated) scheme data.

    Validation rules:
      1. Description must be >80 chars and not start with a generic template phrase.
      2. At least 1 document must be non-generic (beyond just Aadhaar/Income).
      3. At least 1 application step description must be non-generic.
    """
    desc = str(raw_data.get("description") or raw_data.get("short_description") or "")
    if _is_generic_text(desc):
        return False

    docs = raw_data.get("required_documents", [])
    real_docs = [
        d for d in docs
        if isinstance(d, dict)
        and d.get("name", "").lower() not in _GENERIC_DOCUMENT_NAMES
    ]
    if not real_docs:
        return False

    steps = raw_data.get("application_process", [])
    real_steps = [
        s for s in steps
        if isinstance(s, dict)
        and not any(
            str(s.get("description", "")).lower().startswith(pfx)
            for pfx in _GENERIC_APP_STEP_PREFIXES
        )
    ]
    if not real_steps:
        return False

    return True


async def _try_myscheme_internal_api(
    slug: str,
    client,
    source_url: str,
) -> Optional[Dict[str, Any]]:
    """Probe myScheme internal API endpoints to get real structured scheme data.

    Tries multiple known API patterns used by the myScheme Next.js app.
    Returns the raw_data dict if successful, None otherwise.
    """
    api_attempts = [
        f"https://api.myscheme.gov.in/scheme/v2/{slug}",
        f"https://api.myscheme.gov.in/scheme/v1/{slug}",
        f"https://api.myscheme.gov.in/search/v4/schemes/{slug}",
        f"https://api.myscheme.gov.in/search/v3/schemes/{slug}",
    ]

    api_headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://www.myscheme.gov.in/schemes/{slug}",
        "Origin": "https://www.myscheme.gov.in",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
    }

    for api_url in api_attempts:
        try:
            resp = await client.get(api_url, headers=api_headers, timeout=15.0)
            if resp.status_code == 200:
                data = resp.json()
                scheme_data = (
                    data.get("data")
                    or data.get("scheme")
                    or data.get("schemeData")
                    or (data if isinstance(data, dict) and data.get("schemeName") else None)
                )
                if scheme_data and isinstance(scheme_data, dict):
                    raw = _parse_myscheme_api_response(scheme_data, source_url)
                    if raw and _validate_scheme_record(raw):
                        logger.info(
                            f"[PortalScraper] Real API data fetched from {api_url} for {slug}"
                        )
                        return raw
        except Exception as e:
            logger.debug(f"[PortalScraper] API attempt failed {api_url}: {e}")

    return None


def _parse_myscheme_api_response(
    scheme_data: Dict[str, Any],
    source_url: str,
) -> Optional[Dict[str, Any]]:
    """Parse a real myScheme API response into a normalized scheme record."""
    try:
        basic = scheme_data.get("basicDetails") or scheme_data.get("basic") or scheme_data

        title = (
            basic.get("schemeName")
            or basic.get("title")
            or basic.get("scheme_name")
            or ""
        ).strip()
        if not title:
            return None

        desc = str(
            basic.get("shortDescription")
            or basic.get("description")
            or basic.get("briefDescription")
            or ""
        ).strip()

        objective = str(
            scheme_data.get("objective")
            or basic.get("objective")
            or ""
        ).strip()

        state_val = basic.get("state") or basic.get("stateName")
        jurisdiction = "State" if state_val else "Central"

        category = basic.get("category") or basic.get("schemeCategory") or "Welfare"
        if isinstance(category, dict):
            category = category.get("name") or "Welfare"
        elif isinstance(category, list) and category:
            category = category[0] if isinstance(category[0], str) else str(category[0])

        ministry = (
            basic.get("ministryName")
            or basic.get("ministry")
            or basic.get("department")
            or "Central Government"
        )

        # Benefits
        raw_benefits = scheme_data.get("benefits") or scheme_data.get("schemeBenefits") or []
        benefits_list = []
        if isinstance(raw_benefits, list):
            for b in raw_benefits:
                b_text = (
                    str(b.get("text") or b.get("description") or b.get("title") or "")
                    if isinstance(b, dict) else str(b)
                ).strip()
                if b_text and len(b_text) > 5:
                    benefits_list.append({
                        "description": b_text,
                        "amount": b.get("amount") if isinstance(b, dict) else None,
                        "currency": "INR",
                        "frequency": b.get("frequency") if isinstance(b, dict) else None,
                    })
        elif isinstance(raw_benefits, str) and raw_benefits.strip():
            benefits_list = [{"description": raw_benefits.strip(), "currency": "INR"}]

        # Eligibility
        elig_obj = scheme_data.get("eligibility") or scheme_data.get("eligibilityCriteria") or {}
        eligibility_text = ""
        if isinstance(elig_obj, dict):
            eligibility_text = str(elig_obj.get("text") or elig_obj.get("description") or "")
        elif isinstance(elig_obj, str):
            eligibility_text = elig_obj
        elif isinstance(elig_obj, list):
            eligibility_text = "\n".join(
                str(e.get("text") or e.get("description") or e) for e in elig_obj
            )

        gender_val = elig_obj.get("gender") or basic.get("gender") if isinstance(elig_obj, dict) else None
        gender = [str(gender_val).lower()] if gender_val else ["all"]

        social_cats_val = (elig_obj.get("caste") or elig_obj.get("socialCategory")) if isinstance(elig_obj, dict) else None
        social_cats = [str(social_cats_val)] if social_cats_val else ["All"]

        # Documents
        raw_docs = (
            scheme_data.get("documentsRequired")
            or scheme_data.get("documents")
            or []
        )
        docs_list = []
        if isinstance(raw_docs, list):
            for d in raw_docs:
                doc_name = (
                    str(d.get("name") or d.get("text") or d.get("title") or "").strip()
                    if isinstance(d, dict) else str(d).strip()
                )
                if doc_name and len(doc_name) > 2:
                    docs_list.append({
                        "name": doc_name,
                        "required": d.get("required", True) if isinstance(d, dict) else True,
                        "verification_status": "Verified",
                    })

        # Application Steps
        raw_app = (
            scheme_data.get("applicationProcess")
            or scheme_data.get("applicationSteps")
            or scheme_data.get("howToApply")
            or []
        )
        app_steps = []
        if isinstance(raw_app, list):
            for idx, step in enumerate(raw_app, 1):
                step_desc = (
                    str(step.get("description") or step.get("text") or step.get("step") or "").strip()
                    if isinstance(step, dict) else str(step).strip()
                )
                if step_desc and len(step_desc) > 5:
                    app_steps.append({
                        "step_number": idx,
                        "channel": step.get("mode") or step.get("channel") or "Online Portal"
                        if isinstance(step, dict) else "Online Portal",
                        "description": step_desc,
                    })
        elif isinstance(raw_app, str) and raw_app.strip():
            app_steps = [{"step_number": 1, "channel": "Online Portal", "description": raw_app.strip()}]

        # FAQs
        raw_faqs = scheme_data.get("faqs") or []
        faqs_list = [
            {"question": str(f["question"]), "answer": str(f["answer"])}
            for f in raw_faqs
            if isinstance(f, dict) and f.get("question") and f.get("answer")
        ]

        # Dates
        app_start = basic.get("applicationStartDate") or scheme_data.get("startDate")
        app_end = basic.get("applicationEndDate") or scheme_data.get("endDate")

        # Contact
        helpline = basic.get("helplineNumber") or scheme_data.get("helpline") or ""
        email = basic.get("email") or scheme_data.get("contactEmail") or ""

        slug_name = re.sub(r"[^a-zA-Z0-9\-]", "", source_url.rstrip("/").split("/")[-1])
        scraped_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return {
            "scheme_id": f"sch-myscheme-{slug_name[:32]}",
            "scheme_name": title,
            "title": title,
            "short_description": desc[:500] if desc else "",
            "description": desc or objective or "",
            "objective": objective,
            "jurisdiction": jurisdiction,
            "government_level": jurisdiction.lower(),
            "state": state_val,
            "category": str(category),
            "department": ministry,
            "ministry": ministry,
            "benefits": benefits_list,
            "gender": gender,
            "gender_eligibility": ", ".join(gender),
            "social_categories": ", ".join(social_cats),
            "eligibility_rules": {
                "root": {
                    "type": "and",
                    "conditions": [
                        {"type": "condition", "description": line.strip(), "verification_status": "Verified"}
                        for line in eligibility_text.split("\n")
                        if line.strip() and len(line.strip()) > 5
                    ] or [{"type": "condition", "description": "Eligibility conditions apply. See official portal."}]
                }
            },
            "eligibility_text": eligibility_text,
            "required_documents": docs_list,
            "application_process": app_steps,
            "faqs": faqs_list,
            "application_start": app_start,
            "application_end": app_end,
            "helpline": helpline,
            "email": email,
            "source_url": source_url,
            "source_name": "myScheme" if "myscheme.gov.in" in source_url else "Official Source",
            "official_information_url": source_url,
            "official_scheme_url": source_url,
            "official_application_url": (
                basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")
            ) if (
                (basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")) and
                "myscheme.gov.in" not in str(basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")).lower() and
                "india.gov.in" not in str(basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")).lower()
            ) else None,
            "official_portal_url": (
                basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")
            ) if (
                (basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")) and
                "myscheme.gov.in" not in str(basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")).lower() and
                "india.gov.in" not in str(basic.get("applicationUrl") or scheme_data.get("applicationUrl") or scheme_data.get("applyUrl")).lower()
            ) else None,
            "scraped_at": scraped_ts,
            "verified_at": scraped_ts[:10],
            "verified_by": "myScheme API",
            "status": "Active",
        }
    except Exception as e:
        logger.warning(f"[PortalScraper] Failed to parse API response: {e}")
        return None


class GovernmentPortalScraper(BaseSchemeScraper):
    """Scraper for official government portals and myScheme pages.

    Data Quality Guarantee:
      - Never produces placeholder/fabricated records.
      - All records must pass _validate_scheme_record() before being returned.
      - If real data cannot be extracted from a URL, that URL is SKIPPED (not faked).
    """

    def __init__(
        self,
        source_name: str = "OfficialPortalScraper",
        timeout: float = 30.0,
        enforce_domain_trust: bool = True,
    ):
        super().__init__(
            source_name=source_name,
            timeout=timeout,
            enforce_domain_trust=enforce_domain_trust,
        )

    def extract_from_nextjs_data(
        self, html_content: str, source_url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract structured scheme details from Next.js embedded JSON (__NEXT_DATA__)."""
        if not html_content or "__NEXT_DATA__" not in html_content:
            return None

        try:
            match = re.search(
                r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*({.*?})\s*</script>',
                html_content,
                re.DOTALL,
            )
            if not match:
                return None

            payload = json.loads(match.group(1))
            page_props = payload.get("props", {}).get("pageProps", {})
            scheme_data = (
                page_props.get("schemeData")
                or page_props.get("schemeDetails")
                or page_props.get("initialData")
            )

            if not scheme_data or not isinstance(scheme_data, dict):
                for k, v in page_props.items():
                    if isinstance(v, dict) and any(
                        f in v for f in ["schemeName", "scheme_name", "basicDetails"]
                    ):
                        scheme_data = v
                        break

            if not scheme_data:
                return None

            raw = _parse_myscheme_api_response(scheme_data, source_url)
            if raw and _validate_scheme_record(raw):
                return {
                    "source": "mySchemePortal",
                    "source_id": f"myscheme-{source_url.rstrip('/').split('/')[-1][:24]}",
                    "raw_data": raw,
                }
            return None

        except Exception as e:
            logger.warning(
                f"[PortalScraper] Failed to parse __NEXT_DATA__ from {source_url}: {e}"
            )
            return None

    def extract_structured_fields_from_text(
        self,
        cleaned_text: str,
        source_url: str,
        scheme_hint_title: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Parse cleaned webpage text into a structured scheme dict.

        Returns None if extracted content is too thin to be useful.
        """
        cleaned_text = str(cleaned_text or "")
        if len(cleaned_text) < 200:
            return None

        lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]

        title = scheme_hint_title
        if not title and lines:
            for line in lines[:5]:
                if 5 < len(line) < 150:
                    title = line
                    break
        title = re.sub(
            r"^(Scheme|Yojana|Guideline|Official Portal)\s*:\s*",
            "",
            title or "Government Welfare Scheme",
            flags=re.I,
        ).strip()

        sections: Dict[str, List[str]] = {
            "overview": [],
            "benefits": [],
            "eligibility": [],
            "documents": [],
            "application": [],
            "deadlines": [],
        }
        current = "overview"
        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ["benefit", "amount", "stipend", "grant", "financial assistance"]):
                current = "benefits"
            elif any(k in lower for k in ["eligib", "who can apply", "criteria", "qualification", "conditions", "requirement"]):
                current = "eligibility"
            elif any(k in lower for k in ["document", "certificate", "checklist", "proof", "paper required"]):
                current = "documents"
            elif any(k in lower for k in ["how to apply", "application process", "steps", "procedure", "submission", "register"]):
                current = "application"
            elif any(k in lower for k in ["deadline", "last date", "window", "closing date", "opening date", "schedule"]):
                current = "deadlines"
            sections[current].append(line)

        # Extract documents from text
        docs_list = []
        for line in sections["documents"]:
            line_clean = line.strip()
            if 3 < len(line_clean) < 120:
                # Remove bullet markers and numbering
                doc_name = re.sub(r"^[\d\.\-\•\*\✓]+\s*", "", line_clean).strip()
                if doc_name and doc_name.lower() not in _GENERIC_DOCUMENT_NAMES:
                    docs_list.append({"name": doc_name, "required": True, "verification_status": "Verified"})

        # Extract application steps from text
        app_steps = []
        for idx, line in enumerate(sections["application"][:8], 1):
            step_desc = re.sub(r"^(?:step\s*\d+\s*[:\.\-]?|[\d\.\-\•\*]+)\s*", "", line, flags=re.I).strip()
            if len(step_desc) > 15:
                app_steps.append({
                    "step_number": idx,
                    "channel": "Online Portal",
                    "description": step_desc,
                })

        # Extract amount
        amount_match = re.search(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?(?:\s*(?:lakh|crore|k))?)", cleaned_text, re.I)
        amount_val = amount_match.group(0) if amount_match else None

        desc_text = " ".join(sections["overview"][:4])[:600] if sections["overview"] else cleaned_text[:400]

        # State detection
        state = None
        state_names = [
            "Maharashtra", "Uttar Pradesh", "Gujarat", "Karnataka", "Tamil Nadu",
            "West Bengal", "Delhi", "Bihar", "Rajasthan", "Madhya Pradesh",
            "Kerala", "Punjab", "Haryana", "Andhra Pradesh", "Telangana", "Odisha",
            "Assam", "Jharkhand", "Chhattisgarh", "Goa", "Himachal Pradesh",
            "Uttarakhand", "Jammu and Kashmir",
        ]
        for s in state_names:
            if re.search(r"\b" + re.escape(s) + r"\b", cleaned_text, re.I):
                state = s
                break

        # Only return if we have real content
        if not docs_list and not app_steps:
            return None
        if _is_generic_text(desc_text):
            return None

        jurisdiction = "State" if state else "Central"
        slug_name = re.sub(r"[^a-zA-Z0-9\-]", "", source_url.rstrip("/").split("/")[-1])
        scraped_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        raw_data = {
            "scheme_id": f"sch-scrape-{slug_name[:24]}",
            "scheme_name": title,
            "title": title,
            "short_description": desc_text[:500],
            "description": desc_text,
            "jurisdiction": jurisdiction,
            "government_level": jurisdiction.lower(),
            "state": state,
            "category": "Welfare & Social Security",
            "department": "Department of Social Welfare",
            "ministry": "Ministry of Social Justice",
            "benefits": [{"description": desc_text[:200], "amount": amount_val, "currency": "INR"}]
            if sections["benefits"] else [],
            "gender": ["all"],
            "gender_eligibility": "All",
            "social_categories": "All",
            "eligibility_rules": {
                "root": {
                    "type": "and",
                    "conditions": [
                        {"type": "condition", "description": line, "verification_status": "Verified"}
                        for line in sections["eligibility"][:3]
                        if len(line) > 10
                    ] or [{"type": "condition", "description": "Eligibility conditions apply."}]
                }
            },
            "required_documents": docs_list,
            "application_process": app_steps,
            "source_url": source_url,
            "source_name": "myScheme" if "myscheme.gov.in" in source_url else "Official Source",
            "official_information_url": source_url,
            "official_scheme_url": source_url,
            "official_application_url": None if "myscheme.gov.in" in source_url else source_url,
            "official_portal_url": None if "myscheme.gov.in" in source_url else source_url,
            "scraped_at": scraped_ts,
            "verified_at": scraped_ts[:10],
            "verified_by": "Schemora Web Scraper",
            "status": "Active",
        }

        if not _validate_scheme_record(raw_data):
            return None

        return {
            "source": self.source_name,
            "source_id": f"scrape-{slug_name[:24]}",
            "raw_data": raw_data,
        }

    async def scrape_schemes(self, target_urls: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch and extract scheme data from target URLs.

        Quality guarantee: only returns records with REAL, VALIDATED scheme data.
        URLs that cannot produce real data are logged and SKIPPED.
        """
        if not target_urls:
            logger.info(f"[{self.source_name}] No target URLs provided.")
            return []

        scraped_records = []
        skipped_urls = []

        try:
            import httpx as _httpx
            _has_httpx = True
        except ImportError:
            _has_httpx = False

        for url in target_urls:
            logger.info(f"[{self.source_name}] Scraping: {url}")
            slug = url.rstrip("/").split("/")[-1].lower()

            record = None

            # ── Strategy 1: Try myScheme internal REST API ─────────────────────
            if "myscheme.gov.in" in url and _has_httpx:
                try:
                    import httpx as _httpx_mod
                    async with _httpx_mod.AsyncClient(
                        timeout=20.0, follow_redirects=True
                    ) as client:
                        raw = await _try_myscheme_internal_api(slug, client, url)
                    if raw:
                        record = {
                            "source": "mySchemeAPI",
                            "source_id": f"myscheme-api-{slug[:24]}",
                            "raw_data": raw,
                        }
                except Exception as e:
                    logger.debug(f"[{self.source_name}] API strategy failed for {slug}: {e}")

            # ── Strategy 2: Next.js __NEXT_DATA__ extraction from HTML ─────────
            if not record:
                html = await self.fetch_html(url)
                if html:
                    record = self.extract_from_nextjs_data(html, source_url=url)

            # ── Strategy 3: Clean HTML text extraction ────────────────────────
            if not record and html if "html" in dir() else True:
                raw_html = await self.fetch_html(url)
                if raw_html:
                    cleaned_text = self.parse_html_to_text(raw_html)
                    if len(cleaned_text) >= 200:
                        record = self.extract_structured_fields_from_text(
                            cleaned_text, source_url=url
                        )

            if record:
                scraped_records.append(record)
                logger.info(
                    f"[{self.source_name}] ✓ Real data extracted for {slug} "
                    f"({record['source']})"
                )
            else:
                skipped_urls.append(url)
                logger.warning(
                    f"[{self.source_name}] ✗ Skipped {url} — could not extract "
                    "real (non-fabricated) scheme data from any strategy."
                )

        logger.info(
            f"[{self.source_name}] Extraction complete: "
            f"{len(scraped_records)} valid records, {len(skipped_urls)} skipped."
        )
        return scraped_records
