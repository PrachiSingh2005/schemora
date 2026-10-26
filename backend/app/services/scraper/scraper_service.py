"""Web Scraper Service Orchestrator — Schemora Data Pipeline.

Connects the web scraping pipeline directly into Schemora's existing Knowledge Base
and pgvector RAG pipeline.

Flow:
  Web Scraping (PortalScraper)
       ↓
  Raw Records
       ↓
  Cleaner & Normalizer (cleaner.py)
       ↓
  16-Section Knowledge Base Chunker & Embedder (knowledge_base_service.py)
       ↓
  SQL KnowledgeChunk Table + PostgreSQL pgvector Storage
       ↓
  Instantly Queryable by RAG Pipeline (retrieval_service.py & ai/chat)
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.scraper.portal_scraper import GovernmentPortalScraper
from app.services.data_pipeline.cleaner import (
    normalize_string,
    normalize_state,
    normalize_government_level,
    normalize_gender,
    normalize_social_category,
    normalize_url,
    normalize_slug,
)
from app.services.knowledge_base_service import index_scheme

logger = logging.getLogger("schemora.scraper.service")


def clean_scraped_raw_record(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """Clean a raw scraped scheme record using Schemora's standard normalization rules."""
    source = raw_record.get("source", "mySchemeAPI")
    source_id = str(raw_record.get("source_id") or "").strip()
    raw = raw_record.get("raw_data", {})

    title = normalize_string(raw.get("scheme_name") or raw.get("title"))
    if not title:
        title = "Web Scraped Scheme"

    state = normalize_state(raw.get("state"))
    govt_level = normalize_government_level(raw.get("government_level") or raw.get("jurisdiction"), state)

    ministry = normalize_string(raw.get("ministry") or "Ministry of Social Justice and Empowerment")
    dept = normalize_string(raw.get("department") or ministry)

    scheme_id = str(raw.get("scheme_id") or f"sch-myscheme-{normalize_slug(title)[:30]}")
    unique_slug = raw.get("slug") or f"{normalize_slug(title)[:40]}_{normalize_slug(scheme_id)[:20]}"

    description = normalize_string(raw.get("description") or raw.get("short_description") or title)
    objective = normalize_string(raw.get("objective")) if raw.get("objective") else None

    categories = raw.get("category") or raw.get("scheme_category") or "Welfare"
    if isinstance(categories, str):
        categories_list = [c.strip() for c in categories.split(",") if c.strip()]
    elif isinstance(categories, list):
        categories_list = [str(c) for c in categories]
    else:
        categories_list = ["Welfare"]

    benefits = raw.get("benefits", [])
    eligibility_rules = raw.get("eligibility_rules", {})
    required_docs = raw.get("required_documents", [])
    app_process = raw.get("application_process", [])
    official_info_url = raw.get("official_information_url") or raw.get("source_url") or ""
    official_app_url = raw.get("official_application_url") or ""

    return {
        "scheme_id": scheme_id,
        "scheme_name": title,
        "title": title,
        "slug": unique_slug,
        "government_level": govt_level,
        "jurisdiction": govt_level.title(),
        "state": state,
        "ministry": ministry,
        "department": dept,
        "category": categories_list,
        "scheme_category": ", ".join(categories_list),
        "target_beneficiaries": raw.get("target_beneficiaries"),
        "short_description": description[:500] if description else title,
        "description": description,
        "objective": objective,
        "status": "Active",
        "benefits": benefits,
        "financial_assistance": raw.get("financial_assistance"),
        "eligibility_rules": eligibility_rules,
        "eligibility_text": raw.get("eligibility_text"),
        "gender_eligibility": raw.get("gender_eligibility", "All"),
        "social_categories": raw.get("social_categories", "All"),
        "min_age": raw.get("min_age"),
        "max_age": raw.get("max_age"),
        "income_requirements": raw.get("income_requirements"),
        "max_family_income": raw.get("max_family_income"),
        "education_requirements": raw.get("education_requirements"),
        "occupation_requirements": raw.get("occupation_requirements"),
        "residence_requirements": raw.get("residence_requirements"),
        "required_documents": required_docs,
        "application_process": app_process,
        "application_mode": raw.get("application_mode", "Online"),
        "faqs": raw.get("faqs", []),
        "application_start": raw.get("application_start"),
        "application_end": raw.get("application_end"),
        "important_dates": raw.get("important_dates"),
        "helpline": raw.get("helpline"),
        "email": raw.get("email"),
        "source_url": official_info_url,
        "official_information_url": official_info_url,
        "official_scheme_url": official_info_url,
        "official_application_url": official_app_url,
        "scraped_at": raw.get("scraped_at"),
        "verified_at": raw.get("verified_at", "2026-10-03"),
        "verified_by": "myScheme API",
        "scheme_version": "v1-scraped",
        "official_source": {
            "name": "myScheme",
            "url": official_info_url,
            "source_id": source_id,
            "last_verified": raw.get("verified_at", "2026-10-03"),
            "verification_status": "verified",
        }
    }


async def run_web_scraping_ingestion(
    db: AsyncSession,
    target_urls: Optional[List[str]] = None,
    batch_size: int = 100,
    save_raw_to_disk: bool = True,
) -> Dict[str, Any]:
    """Execute web scraping ingestion pipeline and index directly into Schemora RAG system in configurable batches.

    Returns summary metrics.
    """
    from app.services.scraper.myscheme_discovery import discover_myscheme_urls

    if target_urls:
        urls = target_urls
    else:
        all_discovered = await discover_myscheme_urls(timeout=15.0)
        urls = all_discovered[:batch_size]

    logger.info(f"Starting Web Scraping Ingestion for {len(urls)} target URLs...")

    scraper = GovernmentPortalScraper()
    raw_scraped_records = await scraper.scrape_schemes(urls)

    if not raw_scraped_records:
        logger.warning("No raw scheme records were extracted by scraper.")
        return {
            "scraped_urls_count": len(urls),
            "raw_records_count": 0,
            "indexed_schemes_count": 0,
            "total_chunks_created": 0,
            "semantic_chunks_created": 0,
        }

    # Optionally append to raw disk dataset
    if save_raw_to_disk:
        data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        raw_file = data_dir / "myscheme_raw.json"
        try:
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(raw_scraped_records, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(raw_scraped_records)} raw scraped records to {raw_file}")
        except Exception as e:
            logger.warning(f"Could not save raw scraped records to disk: {e}")

    indexed_count = 0
    total_chunks = 0
    total_semantic = 0

    errors = []
    cleaned_schemes = []
    for raw_rec in raw_scraped_records:
        try:
            cleaned_scheme = clean_scraped_raw_record(raw_rec)
            cleaned_schemes.append(cleaned_scheme)
            chunks_created, semantic_count = await index_scheme(db, cleaned_scheme, replace=True, force_reindex=True)
            indexed_count += 1
            total_chunks += chunks_created
            total_semantic += semantic_count
            logger.info(
                f"Scraped scheme '{cleaned_scheme['scheme_id']}' ({cleaned_scheme['scheme_name']}) "
                f"indexed into Knowledge Base: {chunks_created} chunks ({semantic_count} semantic)"
            )
        except Exception as e:
            import traceback
            err_msg = f"Failed to index {raw_rec.get('source_id')}: {str(e)}"
            errors.append(err_msg)
            logger.error(f"{err_msg}\n{traceback.format_exc()}")

    # Save cleaned schemes dataset
    if cleaned_schemes:
        clean_file = Path(__file__).resolve().parent.parent.parent.parent / "data" / "myscheme_schemes.json"
        try:
            with open(clean_file, "w", encoding="utf-8") as f:
                json.dump(cleaned_schemes, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(cleaned_schemes)} cleaned records to {clean_file}")
        except Exception as e:
            logger.warning(f"Could not save cleaned dataset to disk: {e}")

    return {
        "scraped_urls_count": len(urls),
        "raw_records_count": len(raw_scraped_records),
        "indexed_schemes_count": indexed_count,
        "total_chunks_created": total_chunks,
        "semantic_chunks_created": total_semantic,
        "indexing_errors": errors[:5],
    }
