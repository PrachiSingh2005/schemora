"""myScheme Discovery Engine — Schemora Data Pipeline.

Crawls myScheme official API endpoints, sitemaps, and category indices
to discover all available Central Government and State/UT scheme URLs and slugs.

Strategy (in order of preference):
  1. myScheme Search API (paginated) — returns real slug catalogue
  2. Sitemap XML parsing
  3. Hardcoded seed slugs as final fallback
"""

import re
import json
import logging
from typing import List, Dict, Any, Set, Optional

import httpx

logger = logging.getLogger("schemora.scraper.discovery")

# myScheme internal search API — supports pagination
MYSCHEME_SEARCH_API = "https://api.myscheme.gov.in/search/v4/schemes"
MYSCHEME_SEARCH_API_V3 = "https://api.myscheme.gov.in/search/v3/schemes"

MYSCHEME_API_ENDPOINTS = [
    "https://api.myscheme.gov.in/search/v4/schemes?lang=en&q=&pageSize=100&pageNumber=1",
    "https://api.myscheme.gov.in/search/v3/schemes?lang=en&q=&pageSize=100&pageNumber=1",
    "https://api.myscheme.gov.in/search/v1/schemes",
    "https://www.myscheme.gov.in/api/v1/schemes",
    "https://cdn.myscheme.in/json/schemes.json",
]

MYSCHEME_SITEMAP_URLS = [
    "https://www.myscheme.gov.in/sitemap-0.xml",
    "https://www.myscheme.gov.in/sitemap.xml",
]

# Comprehensive seed list of 60+ major myScheme slugs across Central & State categories
KNOWN_MYSCHEME_SLUGS = [
    # ── Education & Scholarships ───────────────────────────────────────────────
    "pm-vidyalaxmi",
    "central-sector-scheme-of-scholarship-for-college-and-university-students",
    "post-matric-scholarship-for-obc-students",
    "post-matric-scholarship-for-sc-students",
    "pre-matric-scholarship-for-sc-students",
    "pm-yasasvi-scholarship-scheme",
    "pm-poshan-shakti-nirman",
    "national-means-cum-merit-scholarship",
    "national-scholarship-portal",
    "begum-hazrat-mahal-national-scholarship",
    "maulana-azad-national-fellowship",
    "rajiv-gandhi-national-fellowship",
    "pm-scholarship-scheme-for-central-armed-police-forces",
    "scholarship-for-top-class-education-for-students-with-disabilities",
    "national-overseas-scholarship",
    "ishan-uday-special-scholarship",

    # ── Agriculture & Farmers ─────────────────────────────────────────────────
    "pm-kisan-samman-nidhi",
    "pm-kisan-maandhan-yojana",
    "pradhan-mantri-fasal-bima-yojana",
    "pradhan-mantri-krishi-sinchayee-yojana",
    "pm-kusum",
    "kisan-credit-card",
    "national-agriculture-market",
    "paramparagat-krishi-vikas-yojana",
    "soil-health-card-scheme",
    "rastriya-krishi-vikas-yojana",
    "pradhan-mantri-annadata-aay-sanrakshan-abhiyan",

    # ── Women & Child ─────────────────────────────────────────────────────────
    "pradhan-mantri-matru-vandana-yojana",
    "lakhpati-didi",
    "sukanya-samriddhi-yojana",
    "beti-bachao-beti-padhao",
    "mission-shakti",
    "ujjwala-yojana",

    # ── Health & Insurance ────────────────────────────────────────────────────
    "ayushman-bharat-pradhan-mantri-jan-arogya-yojana",
    "pm-jan-arogya-yojana",
    "pradhan-mantri-jeevan-jyoti-bima-yojana",
    "pradhan-mantri-suraksha-bima-yojana",
    "pm-national-dialysis-programme",

    # ── Housing ───────────────────────────────────────────────────────────────
    "pm-awas-yojana-urban",
    "pm-awas-yojana-gramin",

    # ── Employment, Skills & Entrepreneurship ─────────────────────────────────
    "pm-internship-scheme",
    "pm-mudra-yojana",
    "pm-vishwakarma-yojana",
    "stand-up-india",
    "startup-india-seed-fund-scheme",
    "national-apprenticeship-promotion-scheme",
    "deen-dayal-upadhyaya-grameen-kaushalya-yojana",
    "skill-india-mission",
    "pm-svamitva-yojana",

    # ── Social Security & Pension ─────────────────────────────────────────────
    "atal-pension-yojana",
    "national-pension-system-for-traders-and-self-employed-persons",
    "pradhan-mantri-vaya-vandana-yojana",
    "national-social-assistance-programme",
    "indira-gandhi-national-old-age-pension-scheme",
    "indira-gandhi-national-widow-pension-scheme",
    "indira-gandhi-national-disability-pension-scheme",

    # ── Financial Inclusion ───────────────────────────────────────────────────
    "pradhan-mantri-jan-dhan-yojana",
    "pm-garib-kalyan-anna-yojana",

    # ── State Schemes ─────────────────────────────────────────────────────────
    "mukhyamantri-yuva-swavalamban-yojana",   # Gujarat
    "gujarat-farmers-debt-relief-scheme",      # Gujarat
    "maharashtra-shatrusanjivani-yojana",      # Maharashtra
    "ladki-bahin-yojana",                      # Maharashtra
    "kanya-sumangala-yojana",                  # UP
    "mukhyamantri-kanya-vivah-yojana",         # MP
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 SchemoraBot/1.0"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Referer": "https://www.myscheme.gov.in/",
    "Origin": "https://www.myscheme.gov.in",
}


async def _discover_via_search_api(
    client: httpx.AsyncClient,
    discovered_urls: Set[str],
    max_pages: int = 10,
) -> None:
    """Probe myScheme search API with pagination to discover scheme slugs."""
    for page in range(1, max_pages + 1):
        for api_base in [MYSCHEME_SEARCH_API, MYSCHEME_SEARCH_API_V3]:
            try:
                resp = await client.get(
                    api_base,
                    params={
                        "lang": "en",
                        "q": "",
                        "keyword": "",
                        "sortBy": "",
                        "sortOrder": "",
                        "pageSize": 100,
                        "pageNumber": page,
                    },
                    timeout=20.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Try to extract scheme list from various response shapes
                    items = (
                        data.get("data", {}).get("schemes")
                        or data.get("schemes")
                        or data.get("data")
                        or (data if isinstance(data, list) else [])
                    )
                    if not items:
                        break  # No more pages
                    for item in items:
                        slug = (
                            item.get("slug")
                            or item.get("schemeSlug")
                            or item.get("id")
                            or item.get("scheme_slug")
                        )
                        if slug and isinstance(slug, str):
                            discovered_urls.add(
                                f"https://www.myscheme.gov.in/schemes/{slug.strip('/')}"
                            )
                    logger.info(
                        f"[Discovery] API {api_base} page={page} returned {len(items)} items."
                    )
                    if len(items) < 100:
                        break  # Last page
                    break  # Success with this API — move to next page
                else:
                    logger.debug(
                        f"[Discovery] API {api_base} page={page} status={resp.status_code}"
                    )
            except Exception as e:
                logger.debug(f"[Discovery] API probe failed {api_base} page={page}: {e}")


async def _discover_via_sitemap(
    client: httpx.AsyncClient,
    discovered_urls: Set[str],
) -> None:
    """Parse myScheme sitemap XML to extract scheme page URLs."""
    for sm in MYSCHEME_SITEMAP_URLS:
        try:
            resp = await client.get(sm, timeout=15.0)
            if resp.status_code == 200:
                found_locs = re.findall(
                    r"<loc>(https?://[^\s<]+)</loc>", resp.text, re.I
                )
                added = 0
                for loc in found_locs:
                    if "/schemes/" in loc and not loc.rstrip("/").endswith("/schemes"):
                        discovered_urls.add(loc.strip())
                        added += 1
                logger.info(
                    f"[Discovery] Sitemap {sm} → {added} scheme URLs found."
                )
        except Exception as e:
            logger.debug(f"[Discovery] Sitemap probe failed for {sm}: {e}")


async def discover_myscheme_urls(
    timeout: float = 20.0,
    max_urls: Optional[int] = None,
) -> List[str]:
    """Discover all scheme URLs available on myScheme.gov.in.

    Strategy (in order):
      1. Probe myScheme Search API (paginated)
      2. Parse sitemap XML
      3. Seed from KNOWN_MYSCHEME_SLUGS
    """
    discovered_urls: Set[str] = set()

    # Always seed from known slugs as a baseline
    for slug in KNOWN_MYSCHEME_SLUGS:
        discovered_urls.add(f"https://www.myscheme.gov.in/schemes/{slug}")

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS
    ) as client:
        # 1. Paginated search API
        await _discover_via_search_api(client, discovered_urls, max_pages=10)

        # 2. Sitemap XML
        await _discover_via_sitemap(client, discovered_urls)

    final_list = sorted(discovered_urls)
    if max_urls and len(final_list) > max_urls:
        final_list = final_list[:max_urls]

    logger.info(
        f"[Discovery] Total myScheme scheme URLs discovered: {len(final_list)}"
    )
    return final_list


if __name__ == "__main__":
    import asyncio
    urls = asyncio.run(discover_myscheme_urls())
    print(f"Discovered {len(urls)} scheme URLs.")
    for u in urls[:10]:
        print(" ", u)
