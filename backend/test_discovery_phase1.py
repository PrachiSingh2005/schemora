"""Phase 1 Standalone Test Script — myScheme Discovery & Extraction.

Runs URL discovery and scheme field extraction without modifying the database.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("schemora.test_discovery")

from app.services.scraper.myscheme_discovery import discover_myscheme_urls, MYSCHEME_SITEMAP_URLS
from app.services.scraper.portal_scraper import GovernmentPortalScraper


async def run_phase1_test():
    print("\n" + "="*80)
    print("PHASE 1: MYSCHEME DISCOVERY & EXTRACTION DIAGNOSTIC TEST")
    print("="*80)

    # 1. Discovery
    print("\n--- 1. Endpoints & Sitemaps Targeted ---")
    for sm in MYSCHEME_SITEMAP_URLS:
        print(f" - {sm}")
    print(" - https://www.myscheme.gov.in/search")

    urls = await discover_myscheme_urls(timeout=20.0)

    print("\n--- 2. Discovery Metrics ---")
    print(f"Total Scheme URLs Discovered: {len(urls)}")

    if not urls:
        print("ERROR: No URLs discovered.")
        return

    # 2. Extract Sample Records (First 3 discovered schemes)
    sample_urls = urls[:3]
    print(f"\n--- 3. Testing Field Extraction on 3 Real Schemes ---")

    scraper = GovernmentPortalScraper(enforce_domain_trust=True)
    records = await scraper.scrape_schemes(sample_urls)

    print(f"\nTotal Records Extracted Successfully: {len(records)}")

    for idx, rec in enumerate(records, 1):
        raw = rec["raw_data"]
        print("\n" + "-"*70)
        print(f"SCHEME RECORD #{idx}")
        print("-"*70)
        print(f"Name                    : {raw.get('scheme_name')}")
        print(f"Official Source URL     : {raw.get('official_information_url')}")
        print(f"Jurisdiction & Level    : {raw.get('jurisdiction')} ({raw.get('government_level')})")
        print(f"State                   : {raw.get('state') or 'Central / All States'}")
        print(f"Category                : {raw.get('category')}")
        print(f"Ministry / Department   : {raw.get('ministry')}")
        print(f"Description (Short)     : {raw.get('short_description')[:150]}...")
        print(f"Benefits Count          : {len(raw.get('benefits', []))}")
        print(f"Sample Benefit          : {raw.get('benefits')[0] if raw.get('benefits') else 'N/A'}")
        print(f"Required Documents      : {[d['name'] for d in raw.get('required_documents', [])[:3]]}")
        print(f"Application Steps Count : {len(raw.get('application_process', []))}")
        print(f"FAQs Count              : {len(raw.get('faqs', []))}")

    print("\n" + "="*80)
    print("PHASE 1 DIAGNOSTIC TEST COMPLETED SUCCESSFULLY")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_phase1_test())
