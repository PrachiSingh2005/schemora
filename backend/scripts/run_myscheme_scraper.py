"""Standalone myScheme Scraper Runner — Schemora.

Discovers ALL official government scheme URLs on myScheme, scrapes their full
structured content, normalizes records, and outputs:
  - data/myscheme_raw.json
  - data/myscheme_schemes.json
  - data/myscheme_scrape_report.json

Usage:
  python scripts/run_myscheme_scraper.py [--limit 100] [--concurrency 5]
"""

import sys
import os
import json
import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

# Ensure backend root is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.scraper.myscheme_discovery import discover_myscheme_urls
from app.services.scraper.portal_scraper import GovernmentPortalScraper
from app.services.scraper.scraper_service import clean_scraped_raw_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("schemora.myscheme_runner")


async def scrape_url_with_retry(
    scraper: GovernmentPortalScraper,
    url: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    delay: float = 0.2,
) -> tuple:
    """Scrape a single scheme URL with semaphore concurrency limit and retry logic."""
    async with semaphore:
        await asyncio.sleep(delay)
        for attempt in range(1, max_retries + 1):
            try:
                records = await scraper.scrape_schemes([url])
                if records:
                    return (url, records[0], None)
            except Exception as e:
                logger.debug(f"Attempt {attempt} failed for {url}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(1.0 * attempt)
                else:
                    return (url, None, str(e))
        return (url, None, "No data extracted after max retries")


async def main():
    parser = argparse.ArgumentParser(description="Run complete myScheme scraper pipeline")
    parser.add_argument("--limit", type=int, default=None, help="Limit total schemes to scrape")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent HTTP requests limit")
    args = parser.parse_args()

    start_time = datetime.now(timezone.utc)
    logger.info("=== STEP 1: Discovering ALL myScheme URLs ===")
    discovered_urls = await discover_myscheme_urls(max_urls=args.limit)
    total_discovered = len(discovered_urls)
    logger.info(f"Discovered {total_discovered} unique scheme URLs on myScheme.")

    logger.info(f"=== STEP 2: Scraping discovered scheme pages (Concurrency={args.concurrency}) ===")
    scraper = GovernmentPortalScraper(timeout=25.0)
    semaphore = asyncio.Semaphore(args.concurrency)

    tasks = [
        scrape_url_with_retry(scraper, url, semaphore)
        for url in discovered_urls
    ]

    results = await asyncio.gather(*tasks)

    raw_records = []
    cleaned_records = []
    failed_urls = []
    seen_scheme_ids = set()
    duplicates_count = 0
    http_errors = []

    for url, raw_rec, err in results:
        if raw_rec:
            raw_data = raw_rec.get("raw_data", {})
            scheme_id = raw_data.get("scheme_id") or url

            if scheme_id in seen_scheme_ids:
                duplicates_count += 1
                logger.info(f"Duplicate scheme ID '{scheme_id}' skipped for URL {url}")
                continue

            seen_scheme_ids.add(scheme_id)
            raw_records.append(raw_rec)

            cleaned = clean_scraped_raw_record(raw_rec)
            cleaned_records.append(cleaned)
        else:
            failed_urls.append(url)
            http_errors.append({"url": url, "error": err or "Scrape failed"})

    # Report calculations
    total_scraped = len(cleaned_records)
    total_failed = len(failed_urls)

    incomplete_schemes = []
    missing_fields_summary = {
        "objective": 0,
        "state": 0,
        "beneficiaries": 0,
        "benefits": 0,
        "documents": 0,
        "application_process": 0,
        "faqs": 0,
        "application_url": 0,
        "helpline": 0,
    }

    for s in cleaned_records:
        missing_in_this = []
        if not s.get("objective"):
            missing_fields_summary["objective"] += 1
            missing_in_this.append("objective")
        if not s.get("state") and s.get("jurisdiction") == "State":
            missing_fields_summary["state"] += 1
            missing_in_this.append("state")
        if not s.get("target_beneficiaries"):
            missing_fields_summary["beneficiaries"] += 1
            missing_in_this.append("target_beneficiaries")
        if not s.get("benefits"):
            missing_fields_summary["benefits"] += 1
            missing_in_this.append("benefits")
        if not s.get("required_documents"):
            missing_fields_summary["documents"] += 1
            missing_in_this.append("required_documents")
        if not s.get("application_process"):
            missing_fields_summary["application_process"] += 1
            missing_in_this.append("application_process")
        if not s.get("faqs"):
            missing_fields_summary["faqs"] += 1
            missing_in_this.append("faqs")
        if not s.get("official_application_url"):
            missing_fields_summary["application_url"] += 1
            missing_in_this.append("official_application_url")
        if not s.get("helpline"):
            missing_fields_summary["helpline"] += 1
            missing_in_this.append("helpline")

        if len(missing_in_this) >= 3:
            incomplete_schemes.append({
                "scheme_id": s.get("scheme_id"),
                "scheme_name": s.get("scheme_name"),
                "missing_fields": missing_in_this,
            })

    # Save outputs
    data_dir = BACKEND_DIR.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    raw_file = data_dir / "myscheme_raw.json"
    cleaned_file = data_dir / "myscheme_schemes.json"
    report_file = data_dir / "myscheme_scrape_report.json"

    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(raw_records, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved raw dataset: {raw_file} ({len(raw_records)} records)")

    with open(cleaned_file, "w", encoding="utf-8") as f:
        json.dump(cleaned_records, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved cleaned dataset: {cleaned_file} ({len(cleaned_records)} records)")

    scrape_report = {
        "scrape_timestamp": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_scheme_urls_discovered": total_discovered,
        "total_schemes_successfully_scraped": total_scraped,
        "total_failed_urls": total_failed,
        "duplicate_schemes_count": duplicates_count,
        "incomplete_schemes_count": len(incomplete_schemes),
        "missing_fields_summary": missing_fields_summary,
        "failed_urls": failed_urls,
        "http_request_errors": http_errors,
        "incomplete_schemes": incomplete_schemes[:10],  # Sample of incomplete schemes
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(scrape_report, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved scrape report: {report_file}")

    print("\n" + "=" * 60)
    print("MYSCHEME SCRAPER COMPLETED SUCCESSFULLY")
    print(f"Total Discovered URLs : {total_discovered}")
    print(f"Successfully Scraped   : {total_scraped}")
    print(f"Failed URLs           : {total_failed}")
    print(f"Duplicates Skipped    : {duplicates_count}")
    print(f"Incomplete Schemes    : {len(incomplete_schemes)}")
    print(f"Raw Output Path       : {raw_file}")
    print(f"Cleaned Output Path   : {cleaned_file}")
    print(f"Scrape Report Path    : {report_file}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
