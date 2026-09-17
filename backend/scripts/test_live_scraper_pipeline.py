"""Live Scraper Pipeline Verification Script.

Tests the full pipeline on 5 real schemes across key categories:
1. Agriculture (e.g. PM-KISAN)
2. Education (e.g. PM-Vidyalaxmi / Post-Matric Scholarship)
3. Women (e.g. Mukhyamantri Majhi Ladki Bahin Yojana)
4. Health (e.g. PM-JAY / Health Scheme)
5. Employment (e.g. PM Internship Scheme)

Verifies:
Source URL -> Scraped Scheme -> Extracted Official Scheme URL -> Extracted Application URL -> Redirect Tracing -> DB Record -> Vector Index Status
"""

import asyncio
import logging
from typing import Dict, Any, List

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.scheme import Scheme
from app.models.knowledge import KnowledgeChunk
from app.services.scraper.portal_scraper import GovernmentPortalScraper
from app.services.knowledge_base_service import index_scheme

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper_test")

SAMPLE_TARGET_URLS = [
    "https://www.myscheme.gov.in/schemes/pm-kisan",
    "https://www.myscheme.gov.in/schemes/pm-vidyalaxmi",
    "https://www.myscheme.gov.in/schemes/mmlby",
    "https://www.myscheme.gov.in/schemes/pmjay",
    "https://www.myscheme.gov.in/schemes/pmis",
]

async def run_live_scraper_test():
    logger.info("=== STARTING REAL LIVE SCRAPER PIPELINE TEST ===")
    scraper = GovernmentPortalScraper()
    scraped_records = await scraper.scrape_schemes(SAMPLE_TARGET_URLS)
    logger.info(f"Scraper returned {len(scraped_records)} structured scheme records.")

    test_results = []

    async with AsyncSessionLocal() as db:
        for rec in scraped_records:
            raw = rec.get("raw_data", {})
            s_id = raw.get("scheme_id")
            s_name = raw.get("scheme_name") or raw.get("title")
            source_url = raw.get("source_url")
            off_scheme_url = raw.get("official_scheme_url")
            off_app_url = raw.get("official_application_url")

            logger.info(f"\n--- TESTING SCRAPED SCHEME: {s_name} ({s_id}) ---")
            logger.info(f"  Source URL: {source_url}")
            logger.info(f"  Extracted Official Scheme URL: {off_scheme_url}")
            logger.info(f"  Extracted Application URL: {off_app_url}")

            # Verify & index into PostgreSQL + pgvector
            indexed_chunks_count = await index_scheme(db, raw)
            
            # Re-query DB to verify saved record
            db_res = await db.execute(select(Scheme).where(Scheme.id == s_id))
            scheme_obj = db_res.scalar_one_or_none()

            chunk_res = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.scheme_id == s_id))
            chunks = chunk_res.scalars().all()

            res_entry = {
                "scheme_id": s_id,
                "scheme_name": s_name,
                "source_url": source_url,
                "official_scheme_url": scheme_obj.official_scheme_url if scheme_obj else off_scheme_url,
                "application_url": scheme_obj.application_url if scheme_obj else off_app_url,
                "db_status": "SAVED" if scheme_obj else "FAILED",
                "indexed_chunks_count": len(chunks),
                "vector_status": "INDEXED" if len(chunks) > 0 else "FAILED",
            }
            test_results.append(res_entry)

    logger.info("\n=== LIVE SCRAPER TEST RESULTS SUMMARY ===")
    for r in test_results:
        logger.info(f"[{r['scheme_name']}]")
        logger.info(f"   Source URL: {r['source_url']}")
        logger.info(f"   Official Scheme URL: {r['official_scheme_url']}")
        logger.info(f"   Application URL: {r['application_url']}")
        logger.info(f"   DB Record: {r['db_status']} | Vector Chunks: {r['indexed_chunks_count']} ({r['vector_status']})")

    return test_results

if __name__ == "__main__":
    asyncio.run(run_live_scraper_test())
