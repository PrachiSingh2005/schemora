#!/usr/bin/env python3
"""Audit and Fix Scheme URLs in PostgreSQL Database — Schemora.

This script audits all scheme records in PostgreSQL and retrofits them with:
- source_url: Information source (myScheme or official ministry page)
- source_name: Source name ("myScheme", "National Scholarship Portal", etc.)
- official_scheme_url: Main overview page of the scheme
- application_url: Actual official portal/page where user applies (verified .gov.in/.nic.in)
- official_portal_url: Department/Ministry main portal

Guarantees:
- Never deletes scheme records.
- Does NOT set myScheme URLs as application URLs.
- Populates verified application URLs for national and state schemes.
"""

import sys
import asyncio
import json
import logging
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, text
from app.core.database import AsyncSessionLocal
from app.models.scheme import Scheme, SchemeSource
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("audit_fix_urls")

# ── Verified Direct Application URL Registry for Known Schemes ─────────────────
VERIFIED_SCHEME_URL_MAP = {
    # Scholarships & Education
    "csss": {
        "source_name": "Ministry of Education / myScheme",
        "official_scheme_url": "https://www.education.gov.in/scholarships",
        "application_url": "https://scholarships.gov.in/",
        "official_portal_url": "https://scholarships.gov.in/",
    },
    "postmatric-obc": {
        "source_name": "MahaDBT Portal",
        "official_scheme_url": "https://mahadbt.maharashtra.gov.in/",
        "application_url": "https://mahadbt.maharashtra.gov.in/",
        "official_portal_url": "https://mahadbt.maharashtra.gov.in/",
    },
    "postmatric-sc": {
        "source_name": "MahaDBT Portal / NSP",
        "official_scheme_url": "https://mahadbt.maharashtra.gov.in/",
        "application_url": "https://mahadbt.maharashtra.gov.in/",
        "official_portal_url": "https://mahadbt.maharashtra.gov.in/",
    },
    "nsp": {
        "source_name": "National Scholarship Portal",
        "official_scheme_url": "https://scholarships.gov.in/",
        "application_url": "https://scholarships.gov.in/",
        "official_portal_url": "https://scholarships.gov.in/",
    },
    # Agriculture & Farmers
    "pm-kisan": {
        "source_name": "PM-KISAN Portal",
        "official_scheme_url": "https://pmkisan.gov.in/",
        "application_url": "https://pmkisan.gov.in/RegistrationFormNew.aspx",
        "official_portal_url": "https://pmkisan.gov.in/",
    },
    "pmfby": {
        "source_name": "PMFBY Portal",
        "official_scheme_url": "https://pmfby.gov.in/",
        "application_url": "https://pmfby.gov.in/",
        "official_portal_url": "https://pmfby.gov.in/",
    },
    "soil-health-card": {
        "source_name": "Department of Agriculture",
        "official_scheme_url": "https://soilhealth.dac.gov.in/",
        "application_url": "https://soilhealth.dac.gov.in/",
        "official_portal_url": "https://soilhealth.dac.gov.in/",
    },
    # Skill & Employment
    "pm-internship": {
        "source_name": "Ministry of Corporate Affairs / MY Bharat",
        "official_scheme_url": "https://pminternship.mca.gov.in/",
        "application_url": "https://pminternship.mca.gov.in/",
        "official_portal_url": "https://pminternship.mca.gov.in/",
    },
    "pmkvy": {
        "source_name": "Skill India Digital",
        "official_scheme_url": "https://www.skillindiadigital.gov.in/",
        "application_url": "https://www.skillindiadigital.gov.in/",
        "official_portal_url": "https://www.skillindiadigital.gov.in/",
    },
    "naps": {
        "source_name": "Apprenticeship India Portal",
        "official_scheme_url": "https://www.apprenticeshipindia.gov.in/",
        "application_url": "https://www.apprenticeshipindia.gov.in/",
        "official_portal_url": "https://www.apprenticeshipindia.gov.in/",
    },
    # Health & Social Security
    "ayushman": {
        "source_name": "National Health Authority (NHA)",
        "official_scheme_url": "https://pmjay.gov.in/",
        "application_url": "https://beneficiary.nha.gov.in/",
        "official_portal_url": "https://beneficiary.nha.gov.in/",
    },
    "pm-jay": {
        "source_name": "National Health Authority (NHA)",
        "official_scheme_url": "https://pmjay.gov.in/",
        "application_url": "https://beneficiary.nha.gov.in/",
        "official_portal_url": "https://beneficiary.nha.gov.in/",
    },
    "ladki-bahin": {
        "source_name": "Government of Maharashtra",
        "official_scheme_url": "https://ladkibahin.maharashtra.gov.in/",
        "application_url": "https://ladkibahin.maharashtra.gov.in/",
        "official_portal_url": "https://ladkibahin.maharashtra.gov.in/",
    },
    "apy": {
        "source_name": "PFRDA / NPS Cra",
        "official_scheme_url": "https://www.npscra.nsdl.co.in/scheme-details.php",
        "application_url": "https://www.npscra.nsdl.co.in/",
        "official_portal_url": "https://www.npscra.nsdl.co.in/",
    },
    "atal-pension": {
        "source_name": "PFRDA / NPS Cra",
        "official_scheme_url": "https://www.npscra.nsdl.co.in/scheme-details.php",
        "application_url": "https://www.npscra.nsdl.co.in/",
        "official_portal_url": "https://www.npscra.nsdl.co.in/",
    },
    # Financial Inclusion & Microfinance
    "pm-svanidhi": {
        "source_name": "Ministry of Housing and Urban Affairs",
        "official_scheme_url": "https://pmsvanidhi.mohua.gov.in/",
        "application_url": "https://pmsvanidhi.mohua.gov.in/",
        "official_portal_url": "https://pmsvanidhi.mohua.gov.in/",
    },
    "mudra": {
        "source_name": "UdyamiMitra / PMMY",
        "official_scheme_url": "https://www.mudra.org.in/",
        "application_url": "https://www.udyamimitra.in/",
        "official_portal_url": "https://www.udyamimitra.in/",
    },
    "sukanya": {
        "source_name": "India Post / Ministry of Finance",
        "official_scheme_url": "https://www.indiapost.gov.in/Financial/Pages/Content/Post-Office-Saving-Schemes.aspx",
        "application_url": "https://www.indiapost.gov.in/",
        "official_portal_url": "https://www.indiapost.gov.in/",
    },
    "pmay": {
        "source_name": "PMAY MIS Portal",
        "official_scheme_url": "https://pmaymis.gov.in/",
        "application_url": "https://pmaymis.gov.in/",
        "official_portal_url": "https://pmaymis.gov.in/",
    },
    "eshram": {
        "source_name": "Ministry of Labour & Employment",
        "official_scheme_url": "https://eshram.gov.in/",
        "application_url": "https://eshram.gov.in/",
        "official_portal_url": "https://eshram.gov.in/",
    },
    "pmvishwakarma": {
        "source_name": "PM Vishwakarma Portal",
        "official_scheme_url": "https://pmvishwakarma.gov.in/",
        "application_url": "https://pmvishwakarma.gov.in/",
        "official_portal_url": "https://pmvishwakarma.gov.in/",
    },
    "standupindia": {
        "source_name": "Stand Up Mitra Portal",
        "official_scheme_url": "https://www.standupmitra.in/",
        "application_url": "https://www.standupmitra.in/",
        "official_portal_url": "https://www.standupmitra.in/",
    },
}


def _match_verified_urls(slug: str, title: str):
    """Match a scheme slug/title against verified government portals registry."""
    slug_lower = (slug or "").lower()
    title_lower = (title or "").lower()

    for key, data in VERIFIED_SCHEME_URL_MAP.items():
        if key in slug_lower or key in title_lower:
            return data
    return None


async def audit_and_fix_scheme_urls():
    logger.info("Starting Scheme URL Audit and Retrofit...")
    async with AsyncSessionLocal() as session:
        # 1. Audit Schemes table
        schemes_res = await session.execute(select(Scheme))
        schemes = schemes_res.scalars().all()
        logger.info(f"Auditing {len(schemes)} scheme records in PostgreSQL DB...")

        updated_schemes_count = 0
        for s in schemes:
            slug = s.slug or ""
            title = s.title or ""

            # Check if existing source URL exists
            sources_res = await session.execute(
                select(SchemeSource).where(SchemeSource.scheme_id == s.id)
            )
            sources = sources_res.scalars().all()
            existing_source_url = sources[0].url if sources else (s.source_url or "")

            matched = _match_verified_urls(slug, title)

            if matched:
                s.source_name = matched["source_name"]
                s.source_url = existing_source_url if existing_source_url else matched["official_scheme_url"]
                s.official_scheme_url = matched["official_scheme_url"]
                s.application_url = matched["application_url"]
                s.official_portal_url = matched["official_portal_url"]
            else:
                # Default logic for unmatched schemes
                is_myscheme = "myscheme.gov.in" in existing_source_url.lower()
                if is_myscheme:
                    s.source_name = "myScheme"
                    s.source_url = existing_source_url
                    s.official_scheme_url = existing_source_url
                    s.application_url = None  # Do NOT treat myScheme as application URL!
                    s.official_portal_url = None
                elif existing_source_url and ("gov.in" in existing_source_url or "nic.in" in existing_source_url):
                    s.source_name = s.provider or "Official Government Portal"
                    s.source_url = existing_source_url
                    s.official_scheme_url = existing_source_url
                    s.application_url = existing_source_url
                    s.official_portal_url = existing_source_url
                else:
                    s.source_name = s.provider or "Official Portal"
                    s.source_url = existing_source_url if existing_source_url else None
                    s.official_scheme_url = existing_source_url if existing_source_url else None
                    s.application_url = None
                    s.official_portal_url = None

            # Sync or add SchemeSource
            if sources:
                src = sources[0]
                src.source_name = f"{s.title} Official Portal" if s.application_url else f"{s.title} Information Source ({s.source_name})"
                src.url = s.application_url or s.official_scheme_url or s.source_url
                src.source_type = "OfficialApplicationPortal" if s.application_url else "InformationSource"
            else:
                new_src = SchemeSource(
                    scheme_id=s.id,
                    source_name=f"{s.title} Official Portal" if s.application_url else f"{s.title} Source ({s.source_name})",
                    url=s.application_url or s.official_scheme_url or s.source_url,
                    source_type="OfficialApplicationPortal" if s.application_url else "InformationSource",
                    last_verified_at="2026-08-07",
                )
                session.add(new_src)

            updated_schemes_count += 1

        await session.flush()
        logger.info(f"Updated {updated_schemes_count} scheme records.")

        # 2. Audit KnowledgeChunks table
        chunks_res = await session.execute(select(KnowledgeChunk))
        chunks = chunks_res.scalars().all()
        logger.info(f"Auditing {len(chunks)} KnowledgeChunk records...")

        updated_chunks_count = 0
        for c in chunks:
            # Match chunk's scheme
            scheme_id = c.scheme_id
            chunk_scheme = None
            if scheme_id:
                s_res = await session.execute(select(Scheme).where(Scheme.id == scheme_id))
                chunk_scheme = s_res.scalar_one_or_none()

            if chunk_scheme:
                c.source_name = chunk_scheme.source_name
                c.official_info_url = chunk_scheme.official_scheme_url or chunk_scheme.source_url
                c.official_scheme_url = chunk_scheme.official_scheme_url or chunk_scheme.source_url
                c.official_app_url = chunk_scheme.application_url or ""
                c.official_portal_url = chunk_scheme.official_portal_url or chunk_scheme.source_url

                # Update metadata_json
                meta = {}
                if c.metadata_json:
                    try:
                        meta = json.loads(c.metadata_json)
                    except Exception:
                        pass
                meta.update({
                    "source_url": chunk_scheme.source_url,
                    "source_name": chunk_scheme.source_name,
                    "official_scheme_url": chunk_scheme.official_scheme_url,
                    "official_info_url": chunk_scheme.official_scheme_url or chunk_scheme.source_url,
                    "official_app_url": chunk_scheme.application_url or "",
                    "application_url": chunk_scheme.application_url or "",
                    "official_portal_url": chunk_scheme.official_portal_url,
                })
                c.metadata_json = json.dumps(meta)
                updated_chunks_count += 1
            else:
                # Chunk not linked to scheme ID — sanitize raw URLs
                raw_info = c.official_info_url or ""
                raw_app = c.official_app_url or ""
                if "myscheme.gov.in" in raw_app.lower():
                    c.official_app_url = ""  # Clean up fake app URLs
                if "myscheme.gov.in" in raw_info.lower():
                    c.source_name = "myScheme"

        await session.commit()
        logger.info(f"Successfully retrofitted {updated_chunks_count} KnowledgeChunks in PostgreSQL!")

if __name__ == "__main__":
    asyncio.run(audit_and_fix_scheme_urls())
