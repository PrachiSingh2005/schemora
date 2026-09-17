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
  7-Section Knowledge Base Chunker & Embedder (knowledge_base_service.py)
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
    parse_income_amount,
    parse_age_range,
    normalize_url,
    normalize_slug,
)
from app.services.knowledge_base_service import index_scheme

logger = logging.getLogger("schemora.scraper.service")

DEFAULT_TARGET_URLS = [
    "https://www.myscheme.gov.in/schemes/pm-vidyalaxmi",
    "https://mahadbt.maharashtra.gov.in/SchemeData/PostMatric",
    "https://scholarships.gov.in/nsp-guidelines",
]


def clean_scraped_raw_record(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """Clean a raw scraped scheme record using Schemora's standard normalization rules."""
    source = raw_record.get("source", "WebScraper")
    source_id = str(raw_record.get("source_id") or "").strip()
    raw = raw_record.get("raw_data", {})

    title = normalize_string(raw.get("scheme_name") or raw.get("title"))
    if not title:
        title = "Web Scraped Scheme"

    state = normalize_state(raw.get("state"))
    govt_level = normalize_government_level(raw.get("government_level") or raw.get("jurisdiction"), state)

    ministry = normalize_string(raw.get("ministry") or raw.get("provider") or "Ministry of Social Welfare")
    dept = normalize_string(raw.get("department") or "Department of Education")

    scheme_id = str(raw.get("scheme_id") or f"sch-scrape-{normalize_slug(title)[:20]}")
    unique_slug = f"{normalize_slug(title)[:40]}_{normalize_slug(scheme_id)[:20]}"

    description = normalize_string(raw.get("description") or raw.get("short_description"))

    categories = raw.get("category") or ["Education"]
    if isinstance(categories, str):
        categories = [categories]

    benefits = raw.get("benefits", [])
    eligibility_rules = raw.get("eligibility_rules", {})
    required_docs = raw.get("required_documents", [])
    app_process = raw.get("application_process", [])
    official_info_url = raw.get("official_information_url", "")
    official_app_url = raw.get("official_application_url", "")

    return {
        "scheme_id": scheme_id,
        "scheme_name": title,
        "slug": unique_slug,
        "government_level": govt_level,
        "jurisdiction": govt_level.title(),
        "state": state,
        "ministry": ministry,
        "department": dept,
        "category": categories,
        "scheme_category": ", ".join(categories) if isinstance(categories, list) else str(categories),
        "short_description": description,
        "description": description,
        "status": "Active",
        "benefits": benefits,
        "eligibility_rules": eligibility_rules,
        "gender_eligibility": raw.get("gender_eligibility", "All"),
        "social_categories": raw.get("social_categories", "All"),
        "required_documents": required_docs,
        "application_process": app_process,
        "faqs": raw.get("faqs", []),
        "official_information_url": official_info_url,
        "official_application_url": official_app_url,
        "verified_at": raw.get("verified_at", "2026-08-17"),
        "verified_by": "WebScraperEngine",
        "scheme_version": "v1-scraped",
        "official_source": {
            "name": source,
            "url": official_info_url,
            "source_id": source_id,
            "last_verified": raw.get("verified_at", "2026-08-17"),
            "verification_status": "verified",
        }
    }


async def run_web_scraping_ingestion(
    db: AsyncSession,
    target_urls: Optional[List[str]] = None,
    batch_size: int = 50,
    save_raw_to_disk: bool = True,
) -> Dict[str, Any]:
    """Execute web scraping ingestion pipeline and index directly into Schemora RAG system in configurable batches.

    Returns summary metrics.
    """
    from app.services.scraper.myscheme_discovery import discover_myscheme_urls

    if target_urls:
        urls = target_urls
    else:
        all_discovered = await discover_myscheme_urls(timeout=10.0)
        urls = all_discovered[:batch_size]

    logger.info(f"Starting Web Scraping Ingestion for {len(urls)} target URLs (batch_size={batch_size})...")

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
        raw_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        scraped_raw_file = raw_dir / "scraped_schemes_raw.json"
        try:
            with open(scraped_raw_file, "w", encoding="utf-8") as f:
                json.dump(raw_scraped_records, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(raw_scraped_records)} raw scraped records to {scraped_raw_file}")
        except Exception as e:
            logger.warning(f"Could not save raw scraped records to disk: {e}")

    # Process, Clean & Index into Knowledge Base
    indexed_count = 0
    total_chunks = 0
    total_semantic = 0

    errors = []
    for raw_rec in raw_scraped_records:
        try:
            cleaned_scheme = clean_scraped_raw_record(raw_rec)
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

    return {
        "scraped_urls_count": len(urls),
        "raw_records_count": len(raw_scraped_records),
        "indexed_schemes_count": indexed_count,
        "total_chunks_created": total_chunks,
        "semantic_chunks_created": total_semantic,
        "indexing_errors": errors[:5],
    }
