"""myScheme Discovery Engine — Schemora Data Pipeline.

Crawls myScheme official API endpoints, sitemaps, search listings, and category indices
to discover all available Central Government and State/UT scheme URLs and slugs.

Strategy (in order of preference):
  1. myScheme Paginated Search API (v4 & v3) — discovers all active scheme slugs dynamically
  2. Category & State filter probes — captures specialized listings
  3. Sitemap XML parsing (sitemap.xml, sitemap-0.xml, etc.)
  4. Seed slugs fallback for resilience
"""

import re
import json
import logging
from typing import List, Dict, Any, Set, Optional

import httpx

logger = logging.getLogger("schemora.scraper.discovery")

# myScheme internal search API endpoints — supports pagination
MYSCHEME_SEARCH_API_V4 = "https://api.myscheme.gov.in/search/v4/schemes"
MYSCHEME_SEARCH_API_V3 = "https://api.myscheme.gov.in/search/v3/schemes"

MYSCHEME_SITEMAP_URLS = [
    "https://www.myscheme.gov.in/sitemap-0.xml",
    "https://www.myscheme.gov.in/sitemap.xml",
    "https://www.myscheme.gov.in/sitemap-1.xml",
    "https://www.myscheme.gov.in/sitemap_index.xml",
]

# Baseline seed slugs across categories for extra safety
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
    "mukhyamantri-yuva-swavalamban-yojana",
    "gujarat-farmers-debt-relief-scheme",
    "maharashtra-shatrusanjivani-yojana",
    "ladki-bahin-yojana",
    "kanya-sumangala-yojana",
    "mukhyamantri-kanya-vivah-yojana",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 SchemoraBot/2.0"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Referer": "https://www.myscheme.gov.in/",
    "Origin": "https://www.myscheme.gov.in",
}


def _extract_slug_from_item(item: Any) -> Optional[str]:
    """Extract scheme slug from raw API item dict."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        slug = (
            item.get("slug")
            or item.get("schemeSlug")
            or item.get("id")
            or item.get("scheme_slug")
            or item.get("link")
        )
        if slug and isinstance(slug, str):
            clean_slug = slug.rstrip("/").split("/")[-1]
            return clean_slug.strip()
    return None


async def _discover_via_search_api(
    client: httpx.AsyncClient,
    discovered_urls: Set[str],
    max_pages: int = 100,
) -> int:
    """Probe myScheme search API with dynamic pagination to discover scheme slugs."""
    initial_count = len(discovered_urls)

    for api_base in [MYSCHEME_SEARCH_API_V4, MYSCHEME_SEARCH_API_V3]:
        for page in range(1, max_pages + 1):
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
                    items = (
                        data.get("data", {}).get("schemes")
                        or data.get("schemes")
                        or data.get("data")
                        or (data if isinstance(data, list) else [])
                    )
                    if not items:
                        break  # No more pages

                    page_added = 0
                    for item in items:
                        slug = _extract_slug_from_item(item)
                        if slug and slug not in ("schemes", "search"):
                            discovered_urls.add(f"https://www.myscheme.gov.in/schemes/{slug}")
                            page_added += 1

                    logger.info(
                        f"[Discovery] API GET {api_base} page={page} returned {len(items)} items ({page_added} new)."
                    )
                    if len(items) < 100:
                        break  # Reached final page
                else:
                    logger.debug(f"[Discovery] GET {api_base} page={page} status={resp.status_code}")
                    break
            except Exception as e:
                logger.debug(f"[Discovery] API probe GET failed {api_base} page={page}: {e}")
                break

    return len(discovered_urls) - initial_count


async def _discover_via_post_search_api(
    client: httpx.AsyncClient,
    discovered_urls: Set[str],
    max_pages: int = 100,
) -> int:
    """Probe POST search endpoints on myScheme if GET pagination is capped."""
    initial_count = len(discovered_urls)

    post_endpoints = [
        "https://api.myscheme.gov.in/search/v4/schemes",
        "https://api.myscheme.gov.in/search/v3/schemes",
    ]

    for ep in post_endpoints:
        for page in range(1, max_pages + 1):
            try:
                payload = {
                    "searchKeyword": "",
                    "pageNumber": page,
                    "pageSize": 100,
                    "lang": "en",
                    "sort": "",
                    "filters": {},
                }
                resp = await client.post(ep, json=payload, timeout=20.0)
                if resp.status_code == 200:
                    data = resp.json()
                    items = (
                        data.get("data", {}).get("schemes")
                        or data.get("schemes")
                        or data.get("data")
                        or (data if isinstance(data, list) else [])
                    )
                    if not items:
                        break

                    for item in items:
                        slug = _extract_slug_from_item(item)
                        if slug and slug not in ("schemes", "search"):
                            discovered_urls.add(f"https://www.myscheme.gov.in/schemes/{slug}")

                    if len(items) < 100:
                        break
                else:
                    break
            except Exception as e:
                logger.debug(f"[Discovery] API POST failed {ep} page={page}: {e}")
                break

    return len(discovered_urls) - initial_count


async def _discover_via_sitemap(
    client: httpx.AsyncClient,
    discovered_urls: Set[str],
) -> int:
    """Parse myScheme sitemap XML to extract scheme page URLs."""
    initial_count = len(discovered_urls)
    for sm in MYSCHEME_SITEMAP_URLS:
        try:
            resp = await client.get(sm, timeout=15.0)
            if resp.status_code == 200:
                found_locs = re.findall(
                    r"<loc>(https?://[^\s<]+)</loc>", resp.text, re.I
                )
                added = 0
                for loc in found_locs:
                    clean_loc = loc.strip()
                    if "/schemes/" in clean_loc and not clean_loc.rstrip("/").endswith("/schemes"):
                        slug = clean_loc.rstrip("/").split("/")[-1]
                        if slug and slug not in ("schemes", "search"):
                            discovered_urls.add(f"https://www.myscheme.gov.in/schemes/{slug}")
                            added += 1
                logger.info(f"[Discovery] Sitemap {sm} → {added} scheme URLs found.")
        except Exception as e:
            logger.debug(f"[Discovery] Sitemap probe failed for {sm}: {e}")

    return len(discovered_urls) - initial_count


async def discover_myscheme_urls(
    timeout: float = 20.0,
    max_urls: Optional[int] = None,
) -> List[str]:
    """Discover all scheme URLs available on myScheme.gov.in dynamically.

    Full dynamic discovery pipeline:
      1. Seed baseline KNOWN_MYSCHEME_SLUGS
      2. Paginated GET Search API (v4 & v3)
      3. Paginated POST Search API
      4. Sitemap XML parsing
    """
    discovered_urls: Set[str] = set()

    # 1. Seed baseline
    for slug in KNOWN_MYSCHEME_SLUGS:
        discovered_urls.add(f"https://www.myscheme.gov.in/schemes/{slug}")

    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS
    ) as client:
        # 2. GET Search API
        await _discover_via_search_api(client, discovered_urls, max_pages=100)

        # 3. POST Search API
        await _discover_via_post_search_api(client, discovered_urls, max_pages=100)

        # 4. Sitemap XML
        await _discover_via_sitemap(client, discovered_urls)

    final_list = sorted(discovered_urls)
    if max_urls and len(final_list) > max_urls:
        final_list = final_list[:max_urls]

    logger.info(f"[Discovery] Total myScheme scheme URLs discovered: {len(final_list)}")
    return final_list


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    urls = asyncio.run(discover_myscheme_urls())
    print(f"Discovered {len(urls)} scheme URLs.")
    for u in urls[:15]:
        print(" ", u)
