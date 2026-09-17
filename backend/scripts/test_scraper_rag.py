#!/usr/bin/env python3
"""Comprehensive Scraper & RAG Pipeline Verification Script.

Tests the complete flow:
  1. Configured Official URL Domain Trust Check
  2. Webpage HTML Extraction & Cleaning (Navigation, Scripts, Ads removed)
  3. Scheme Details Field Extraction (Eligibility, Benefits, Documents, Steps, URLs)
  4. 7-Section Semantic Chunking & Embedding Generation
  5. PostgreSQL + pgvector Storage
  6. Duplicate SHA-256 Hash Detection (skips re-indexing unchanged content)
  7. RAG Q&A Semantic Retrieval & Citation Generation
"""

import sys
import asyncio
import logging
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal, engine, Base
from app.services.scraper.base_scraper import is_trusted_official_url
from app.services.scraper.portal_scraper import GovernmentPortalScraper
from app.services.scraper.scraper_service import run_web_scraping_ingestion
from app.services.retrieval_service import retrieve_relevant_chunks, detect_intent
from app.services.groq_service import generate_grounded_chat_response
from app.services.knowledge_base_service import get_knowledge_base_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_scraper_rag")


async def run_pipeline_verification():
    logger.info("Initializing DB tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        logger.info("\n--- Stage 1: Domain Trust & URL Security Verification ---")
        official_url = "https://www.myscheme.gov.in/schemes/pm-vidyalaxmi"
        untrusted_url = "https://www.random-scam-site.com/fake-scheme"

        assert is_trusted_official_url(official_url) is True, "Official domain should be trusted!"
        assert is_trusted_official_url(untrusted_url) is False, "Untrusted domain must be blocked!"
        logger.info("✅ Domain Trust Validation Passed!")

        logger.info("\n--- Stage 2: Web Scraping & Clean Content Extraction ---")
        scraper = GovernmentPortalScraper(enforce_domain_trust=True)
        html = await scraper.fetch_html(official_url)
        assert html is not None, f"Failed to fetch HTML for {official_url}"

        cleaned_text = scraper.parse_html_to_text(html)
        logger.info(f"Cleaned Text Sample (first 250 chars):\n{cleaned_text[:250]}...")
        assert "<script" not in cleaned_text.lower(), "Scripts must be stripped!"
        assert "<nav" not in cleaned_text.lower(), "Navigation tags must be stripped!"
        assert "<footer" not in cleaned_text.lower(), "Footers must be stripped!"
        logger.info("✅ HTML Cleaning & Boilerplate Removal Passed!")

        logger.info("\n--- Stage 3: Initial Web Scraper Ingestion & 7-Section Indexing ---")
        metrics_1 = await run_web_scraping_ingestion(db, target_urls=[official_url], save_raw_to_disk=False)
        logger.info(f"First Ingestion Metrics: {metrics_1}")

        assert metrics_1["indexed_schemes_count"] == 1, "Scraped scheme should be indexed!"
        assert metrics_1["total_chunks_created"] >= 7, "All 7 semantic section chunks should be created!"
        logger.info("✅ 7-Section Chunking & Vector Indexing Passed!")

        logger.info("\n--- Stage 4: Duplicate / Update Detection Check ---")
        # Running second ingestion on unchanged page content
        metrics_2 = await run_web_scraping_ingestion(db, target_urls=[official_url], save_raw_to_disk=False)
        logger.info(f"Second (Duplicate) Ingestion Metrics: {metrics_2}")

        assert metrics_2["total_chunks_created"] == 0, "Unchanged page content should NOT be re-indexed!"
        logger.info("✅ SHA-256 Duplicate Update Detection Passed (0 chunks created on re-run)!")

        logger.info("\n--- Stage 5: PostgreSQL + pgvector Semantic Retrieval ---")
        query = "What documents are required and what are the benefits of PM Vidyalaxmi scheme?"
        intent = detect_intent(query)
        logger.info(f"Query: '{query}' | Detected Intent: {intent}")

        chunks = await retrieve_relevant_chunks(db, query=query, top_k=6)
        logger.info(f"Retrieved {len(chunks)} Chunks:")
        for c in chunks:
            logger.info(
                f"  • [{c['section']}] {c['scheme_name']} (score: {c['similarity_score']}) | URL: {c['source_url']}"
            )

        assert len(chunks) > 0, "Retrieval returned 0 chunks!"
        assert any("myscheme.gov.in" in c.get("source_url", "") for c in chunks), "Scraped URL metadata preserved!"
        logger.info("✅ Vector Retrieval & Metadata Preservation Passed!")

        logger.info("\n--- Stage 6: Grounded RAG Chat Assistant Response ---")
        answer, citations, is_grounded = await generate_grounded_chat_response(
            query=query,
            chunks=chunks,
            language="en",
        )

        logger.info(f"RAG Response Grounded: {is_grounded}")
        logger.info(f"Citations Count: {len(citations)}")
        for cit in citations:
            logger.info(f"  • Citation: {cit['source_name']} -> {cit['url']}")
        logger.info(f"Answer Preview:\n{answer[:350]}...")

        assert is_grounded is True, "RAG answer must be grounded!"
        assert len(citations) > 0, "Verified source citations must be present!"
        assert any("myscheme.gov.in" in cit["url"] for cit in citations), "Official source URL present in citations!"
        logger.info("✅ Grounded RAG Generation Passed!")

        logger.info("\n==========================================================")
        logger.info("🎉 SUCCESS: Webpage → Scraper → Clean Content → Chunks → Embeddings → PostgreSQL/pgvector → Existing RAG VERIFIED PERFECTLY!")
        logger.info("==========================================================")


if __name__ == "__main__":
    asyncio.run(run_pipeline_verification())
