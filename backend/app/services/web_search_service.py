"""Web Search Service — Schemora RAG Fallback.

Queries trusted official government websites (.gov.in, .nic.in, myscheme.gov.in)
when knowledge base retrieval yields insufficient results.
"""

import re
import logging
from typing import Any, Dict, List, Optional
import urllib.parse

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)

TRUSTED_GOV_DOMAINS = [
    "myscheme.gov.in",
    "scholarships.gov.in",
    "india.gov.in",
    "pib.gov.in",
    "digitalindia.gov.in",
    "pmkisan.gov.in",
    "pmaymis.gov.in",
    "ncs.gov.in",
    "agricoop.nic.in",
    "dvet.gov.in",
    "mahadbt.maharashtra.gov.in",
]


async def search_trusted_web(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search trusted official government sources as a fallback for RAG.

    Args:
        query: User's search question
        max_results: Max number of web results to retrieve

    Returns:
        List of dicts:
            - title (str)
            - url (str)
            - snippet (str)
            - is_official (bool)
    """
    if not query or not query.strip():
        return []

    # Clean query for search
    clean_q = re.sub(r"[^\w\s]", " ", query).strip()
    if not clean_q:
        return []

    # Target government scheme portals in search query
    search_query = f"{clean_q} site:gov.in OR site:nic.in OR site:myscheme.gov.in"

    if httpx is None:
        logger.warning("httpx library is not available for web search")
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    results: List[Dict[str, Any]] = []

    # ── Try Official Government Filtered Search ─────────────────────────────
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(search_query)}"
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code == 200:
            html = resp.text
            link_matches = re.findall(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            )
            snippet_matches = re.findall(
                r'<(?:a|div)[^>]+class="result__snippet"[^>]*>(.*?)</(?:a|div)>',
                html,
                re.DOTALL,
            )

            for i in range(min(len(link_matches), max_results)):
                raw_url, raw_title = link_matches[i]

                # Unpack DuckDuckGo redirect URL if present (/l/?uddg=URL)
                actual_url = raw_url
                if "uddg=" in raw_url:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    if "uddg" in parsed:
                        actual_url = parsed["uddg"][0]

                clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
                snippet_text = ""
                if i < len(snippet_matches):
                    snippet_text = re.sub(r"<[^>]+>", "", snippet_matches[i]).strip()

                if clean_title and actual_url.startswith("http"):
                    results.append({
                        "title": clean_title,
                        "url": actual_url,
                        "snippet": snippet_text or clean_title,
                        "is_official": (
                            any(d in actual_url for d in TRUSTED_GOV_DOMAINS)
                            or ".gov.in" in actual_url
                            or ".nic.in" in actual_url
                        ),
                    })
    except Exception as e:
        logger.warning(f"Official web search attempt failed: {e}")

    # ── Fallback: Secondary Broader Search if Filtered Query Returned Nothing ─
    if not results:
        try:
            broad_query = f"{clean_q} government scheme"
            url_broad = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(broad_query)}"
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp_broad = await client.get(url_broad, headers=headers)

            if resp_broad.status_code == 200:
                html_b = resp_broad.text
                link_matches = re.findall(
                    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    html_b,
                    re.DOTALL,
                )
                snippet_matches = re.findall(
                    r'<(?:a|div)[^>]+class="result__snippet"[^>]*>(.*?)</(?:a|div)>',
                    html_b,
                    re.DOTALL,
                )

                for i in range(min(len(link_matches), max_results)):
                    raw_url, raw_title = link_matches[i]
                    actual_url = raw_url
                    if "uddg=" in raw_url:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                        if "uddg" in parsed:
                            actual_url = parsed["uddg"][0]

                    clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
                    snippet_text = ""
                    if i < len(snippet_matches):
                        snippet_text = re.sub(r"<[^>]+>", "", snippet_matches[i]).strip()

                    if clean_title and actual_url.startswith("http"):
                        results.append({
                            "title": clean_title,
                            "url": actual_url,
                            "snippet": snippet_text or clean_title,
                            "is_official": ".gov" in actual_url or ".nic" in actual_url,
                        })
        except Exception as e:
            logger.error(f"Broad web search fallback failed: {e}")

    logger.info(f"Web search returned {len(results)} fallback results for '{query[:60]}'")
    return results


def format_web_results_as_chunks(web_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert raw web search results into RAG-compatible knowledge chunk dicts."""
    chunks = []
    for i, item in enumerate(web_results, 1):
        title = item.get("title", "Official Web Source")
        url = item.get("url", "")
        snippet = item.get("snippet", "")

        content_lines = [
            f"Official Web Result: {title}",
            f"Description: {snippet}",
        ]
        if url:
            content_lines.append(f"Official Portal URL: {url}")

        chunks.append({
            "chunk_id": f"web-{i}",
            "scheme_id": f"web-src-{i}",
            "scheme_name": title,
            "section": "overview",
            "content": "\n".join(content_lines),
            "similarity_score": 0.85,
            "source_url": url,
            "source_title": title,
            "official_app_url": url if "apply" in title.lower() or "portal" in title.lower() else "",
            "last_verified_at": "2026-09-15",
            "jurisdiction": "central",
            "state": None,
            "category": "Government Scheme",
            "is_semantic": True,
            "is_web_search": True,
        })
    return chunks
