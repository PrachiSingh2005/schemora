"""myScheme Discovery Only Audit Script.

Discovers scheme URLs from myScheme API & sitemaps, checks validity, probes extraction on a sample set, and reports metrics.
"""

import sys
import os
import json
import asyncio
from typing import Dict, Any, List, Set

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.scraper.myscheme_discovery import discover_myscheme_urls
from app.services.scraper.portal_scraper import GovernmentPortalScraper

async def run_discovery_audit():
    print("\n==========================================================================")
    print("SCHEMORA DISCOVERY-ONLY AUDIT")
    print("==========================================================================\n")

    # 1. Discover all URLs
    raw_urls = await discover_myscheme_urls(max_urls=2000)

    total_discovered_raw = len(raw_urls)
    unique_urls: Set[str] = set()
    duplicate_count = 0
    invalid_count = 0

    valid_urls: List[str] = []
    central_count = 0
    state_count = 0

    for u in raw_urls:
        if u in unique_urls:
            duplicate_count += 1
            continue
        unique_urls.add(u)

        if not u.startswith("https://") or "myscheme.gov.in/schemes" not in u:
            invalid_count += 1
            continue

        valid_urls.append(u)

        # Categorize Central vs State based on slug heuristics
        slug = u.rstrip("/").split("/")[-1].lower()
        if any(st in slug for st in ["maharashtra", "gujarat", "rajasthan", "karnataka", "tamil-nadu", "up-", "mp-", "bihar", "punjab", "delhi"]):
            state_count += 1
        else:
            central_count += 1

    print(f"Total Scheme URLs Discovered (Raw): {total_discovered_raw}")
    print(f"Unique Valid URLs: {len(valid_urls)}")
    print(f"  - Central Government Schemes (Estimated): {central_count}")
    print(f"  - State/UT Schemes (Estimated): {state_count}")
    print(f"Duplicate URLs Found: {duplicate_count}")
    print(f"Invalid URLs Found: {invalid_count}")

    # 2. Probe Extraction on Sample of 20 URLs
    sample_urls = valid_urls[:20]
    print(f"\nProbing Extraction on Sample of {len(sample_urls)} URLs...")

    scraper = GovernmentPortalScraper(timeout=10.0, enforce_domain_trust=True)
    scraped_records = await scraper.scrape_schemes(sample_urls)

    successful_extracted_count = len(scraped_records)
    failed_extract_count = len(sample_urls) - successful_extracted_count

    print(f"Sample Probe Results ({len(sample_urls)} URLs):")
    print(f"  - Successfully Extracted: {successful_extracted_count}")
    print(f"  - Failed / Skipped (Generic/Unextractable): {failed_extract_count}")

    sample_10 = valid_urls[:10]
    sample_3_json = [r["raw_data"] for r in scraped_records[:3]]

    audit_summary = {
        "total_discovered_raw": total_discovered_raw,
        "unique_valid_urls": len(valid_urls),
        "central_schemes_count": central_count,
        "state_schemes_count": state_count,
        "duplicate_urls": duplicate_count,
        "invalid_urls": invalid_count,
        "sample_probe_total": len(sample_urls),
        "sample_probe_successful": successful_extracted_count,
        "sample_probe_failed": failed_extract_count,
        "sample_10_urls": sample_10,
        "sample_3_extracted_json": sample_3_json,
    }

    return audit_summary

if __name__ == "__main__":
    summary = asyncio.run(run_discovery_audit())
    print("\nSample 10 Discovered URLs:")
    for u in summary["sample_10_urls"]:
        print("  -", u)
