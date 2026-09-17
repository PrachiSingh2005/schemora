"""Schemora Web Scraper Package.

Provides web scraping capabilities for government scheme portals,
integrating directly into Schemora's Knowledge Base and RAG pipeline.
"""

from app.services.scraper.base_scraper import BaseSchemeScraper
from app.services.scraper.portal_scraper import GovernmentPortalScraper
from app.services.scraper.scraper_service import run_web_scraping_ingestion

__all__ = [
    "BaseSchemeScraper",
    "GovernmentPortalScraper",
    "run_web_scraping_ingestion",
]
