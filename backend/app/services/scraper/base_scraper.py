"""Base Web Scraper Class — Schemora Data Pipeline.

Defines the abstract interface, domain trust validation, and resilient HTML cleaning utilities
for web scrapers targeting official government scheme portals.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("schemora.scraper")

try:
    import httpx
except ImportError:
    httpx = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

# Configured list of trusted official government domains & domain patterns
TRUSTED_GOV_DOMAINS = [
    ".gov.in",
    ".nic.in",
    ".ac.in",
    ".edu.in",
    "myscheme.gov.in",
    "scholarships.gov.in",
    "mahadbt.maharashtra.gov.in",
    "pmkisan.gov.in",
    "ayushmanbharat.gov.in",
    "digitalindia.gov.in",
    "data.gov.in",
]


def is_trusted_official_url(url: str) -> bool:
    """Validate whether a URL belongs to a trusted official government domain."""
    if not url or not isinstance(url, str):
        return False
    url_str = url.strip().lower()
    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        return False
    try:
        parsed = urlparse(url_str)
        hostname = parsed.hostname or ""
        if not hostname:
            return False

        # Allow localhost / 127.0.0.1 for dev testing
        if hostname in ("localhost", "127.0.0.1", "test-portal.gov.in"):
            return True

        for pattern in TRUSTED_GOV_DOMAINS:
            if pattern.startswith(".") and hostname.endswith(pattern):
                return True
            elif hostname == pattern or hostname.endswith("." + pattern):
                return True
        return False
    except Exception as e:
        logger.warning(f"Failed to parse domain for URL {url}: {e}")
        return False


class BaseSchemeScraper(ABC):
    """Abstract Base Class for government portal web scrapers."""

    def __init__(self, source_name: str, timeout: float = 30.0, enforce_domain_trust: bool = True):
        self.source_name = source_name
        self.timeout = timeout
        self.enforce_domain_trust = enforce_domain_trust

    @abstractmethod
    async def scrape_schemes(self, target_urls: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch and extract raw scheme records from target URLs."""
        pass

    async def fetch_html(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Fetch HTML content from a target URL asynchronously after verifying domain trust."""
        if self.enforce_domain_trust and not is_trusted_official_url(url):
            logger.warning(
                f"[{self.source_name}] Blocked scraping untrusted URL '{url}'. "
                "Schemora only scrapes configured/trusted official government portals."
            )
            return None

        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Referer": "https://www.myscheme.gov.in/",
            "Origin": "https://www.myscheme.gov.in",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        }
        if headers:
            default_headers.update(headers)

        if httpx is not None:
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers=default_headers)
                    if resp.status_code == 200:
                        return resp.text
                    else:
                        logger.warning(f"[{self.source_name}] Failed to fetch {url} (HTTP {resp.status_code})")
                        return None
            except Exception as e:
                logger.error(f"[{self.source_name}] HTTP error fetching {url}: {e}")
                return None
        else:
            import asyncio
            import urllib.request

            def _sync_fetch():
                try:
                    req = urllib.request.Request(url, headers=default_headers)
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        return resp.read().decode("utf-8", errors="ignore")
                except Exception as ex:
                    logger.error(f"[{self.source_name}] Fallback HTTP error fetching {url}: {ex}")
                    return None

            return await asyncio.to_thread(_sync_fetch)

    def parse_html_to_text(self, html_content: str) -> str:
        """Extract and clean main webpage content, removing nav, scripts, styles, footers, and ads."""
        if not html_content:
            return ""

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html_content, "html.parser")

            # 1. Decompose non-content boilerplate elements
            unwanted_selectors = [
                "script", "style", "nav", "footer", "header", "noscript", "aside", "iframe",
                ".navigation", ".navbar", ".footer", ".header", ".sidebar", ".cookie-banner",
                ".ads", ".ad-container", "#comments", ".social-share", ".popup", ".modal"
            ]
            for tag in soup.find_all(unwanted_selectors):
                tag.decompose()

            # 2. Prefer main content containers if present
            main_container = soup.find("main") or soup.find("article") or soup.find(id=re.compile(r"content|main", re.I)) or soup.find(class_=re.compile(r"scheme|content|details", re.I))
            target_element = main_container if main_container else soup.body or soup

            text = target_element.get_text(separator="\n", strip=True)
            # Remove excessive whitespace
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            return "\n".join(lines)
        else:
            # Regex fallback
            cleaned = re.sub(r"<(script|style|nav|footer|header|aside|noscript).*?>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r"<[^>]+>", " ", cleaned)
            lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
            return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
