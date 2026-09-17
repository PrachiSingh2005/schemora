import json
import logging
import os
import httpx
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SCHEME_GENERATION_PROMPT = """You are an expert on Indian Central and State Government Schemes (MyScheme, NSP, MahaDBT, PM Initiatives, State Welfare).
Generate {count} comprehensive, highly accurate Indian government schemes for the category '{category}'.

Return ONLY a JSON array of scheme objects conforming strictly to the following schema:

[
  {{
    "scheme_id": "sch-central-pmkisan-004",
    "scheme_name": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
    "scheme_version": "2026-08-01-v1",
    "short_description": "Income support scheme providing Rs 6,000 per year to small and marginal farmer families.",
    "description": "PM-KISAN is a Central Sector Scheme providing financial support to landholding farmer families across India. The financial benefit of Rs 6,000 per year is transferred in three equal installments directly into bank accounts.",
    "benefits": [
      {{
        "benefit_id": "pmkisan-benefit-financial-001",
        "description": "Financial assistance of Rs 6,000 per year in 3 equal installments of Rs 2,000.",
        "amount": 6000,
        "currency": "INR",
        "frequency": "Annual",
        "verification_status": "Verified",
        "source_ids": ["src-pmkisan-001"]
      }}
    ],
    "jurisdiction": "Central",
    "state": null,
    "department": "Ministry of Agriculture & Farmers Welfare",
    "scheme_category": "{category}",
    "eligibility_rules": {{
      "rules_version": "v1",
      "root": {{
        "rule_id": "pmkisan-root",
        "type": "and",
        "description": "PM-KISAN eligibility criteria",
        "mandatory": true,
        "conditions": [
          {{
            "rule_id": "pmkisan-r001-farmer",
            "type": "condition",
            "description": "Applicant family holds cultivable land.",
            "field": "landholding_status",
            "operator": "eq",
            "value": true,
            "mandatory": true,
            "missing_behavior": "Unresolved",
            "verification_status": "Verified"
          }}
        ]
      }}
    }},
    "required_documents": [
      {{
        "document_id": "doc-land-record",
        "document_type": "LandRecord",
        "name": "Cultivable land ownership document / Khatauni",
        "required": true,
        "verification_status": "Verified"
      }},
      {{
        "document_id": "doc-aadhaar",
        "document_type": "AadhaarCard",
        "name": "Aadhaar Card linked with Bank Account",
        "required": true,
        "verification_status": "Verified"
      }}
    ],
    "application_process": [
      {{
        "step_number": 1,
        "description": "Apply online at pmkisan.gov.in or through local CSC center.",
        "channel": "Online",
        "verification_status": "Verified"
      }}
    ],
    "official_information_url": "https://pmkisan.gov.in/",
    "official_application_url": "https://pmkisan.gov.in/RegistrationForm.aspx",
    "status": "Active"
  }}
]

Make sure scheme_id is unique, descriptive, lowercase (e.g. sch-central-pmkisan-004, sch-maharashtra-ladkibahin-005). Include official guidelines, actual rules, required documents, and URLs.
Return valid JSON only. Do not include markdown codeblocks or non-JSON text.
"""


async def generate_schemes_with_groq(
    api_key: Optional[str] = None,
    category: str = "Agriculture",
    count: int = 2,
) -> List[Dict[str, Any]]:
    """Generates structured Indian government schemes using Groq API."""
    key = api_key or os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", "") or ""
    if not key:
        raise ValueError("Groq API Key is required")

    model = getattr(settings, "GROQ_GENERATION_MODEL", "openai/gpt-oss-20b")
    headers = {
        "Authorization": f"Bearer {key.strip()}",
        "Content-Type": "application/json",
    }
    prompt = SCHEME_GENERATION_PROMPT.format(category=category, count=count)

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(GROQ_API_URL, json=payload, headers=headers)
        if response.status_code != 200:
            logger.error(f"Groq API error ({response.status_code}): {response.text}")
            raise RuntimeError(f"Groq API request failed: {response.status_code} - {response.text}")

        data = response.json()
        try:
            raw_text = data["choices"][0]["message"]["content"].strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            schemes = json.loads(raw_text)
            if isinstance(schemes, dict) and "schemes" in schemes:
                schemes = schemes["schemes"]
            return schemes if isinstance(schemes, list) else [schemes]
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse Groq response: {e}")
            raise ValueError(f"Invalid JSON returned from Groq: {e}")
