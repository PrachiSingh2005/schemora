"""Ingest all 66+ schemes across all dataset files directly into PostgreSQL DB."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from app.services.knowledge_base_service import index_scheme
from app.services.scraper.scraper_service import clean_scraped_raw_record
from app.models.scheme import Scheme
from sqlalchemy import select, update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("schemora.ingest_66")


async def ingest_all_schemes():
    base_dir = Path(__file__).resolve().parent.parent

    file_paths = [
        base_dir / "data" / "raw" / "scraped_schemes_raw.json",
        base_dir / "data" / "raw" / "schemes_raw.json",
        base_dir / "data" / "final" / "schemes.json",
        base_dir.parent / "data" / "schemes" / "schemes.v1.json",
    ]

    all_raw_records = []

    # 1. Load from files
    for p in file_paths:
        if not p.exists():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = json.load(f)

            if isinstance(content, list):
                all_raw_records.extend(content)
            elif isinstance(content, dict):
                schemes_list = content.get("schemes") or content.get("data") or content.get("records") or []
                all_raw_records.extend(schemes_list)
        except Exception as e:
            logger.warning(f"Could not load {p.name}: {e}")

    # 2. Also import catalog from build_catalog.py
    try:
        from build_catalog import schemes_catalog
        all_raw_records.extend(schemes_catalog)
    except Exception as e:
        logger.warning(f"Could not import build_catalog: {e}")

    logger.info(f"Loaded {len(all_raw_records)} raw scheme objects across all sources.")

    # 3. Clean and deduplicate records
    cleaned_map = {}

    for raw_obj in all_raw_records:
        if not isinstance(raw_obj, dict):
            continue

        # If it's already a cleaned scheme dict from schemes.v1.json
        if "scheme_id" in raw_obj and "scheme_name" in raw_obj and "eligibility_rules" in raw_obj and "raw_data" not in raw_obj:
            s_id = raw_obj["scheme_id"]
            s_name = raw_obj["scheme_name"]
            key = (s_id, s_name.lower().strip())
            cleaned_map[key] = raw_obj
        # If it's a scraped raw record with raw_data
        elif "raw_data" in raw_obj or "source" in raw_obj:
            cleaned = clean_scraped_raw_record(raw_obj)
            s_id = cleaned["scheme_id"]
            s_name = cleaned["scheme_name"]
            key = (s_id, s_name.lower().strip())
            if key not in cleaned_map:
                cleaned_map[key] = cleaned
            else:
                # Prefer fuller record
                existing = cleaned_map[key]
                if len(cleaned.get("description", "")) > len(existing.get("description", "")):
                    cleaned_map[key] = cleaned
        elif "title" in raw_obj or "scheme_name" in raw_obj:
            s_name = raw_obj.get("scheme_name") or raw_obj.get("title")
            s_id = raw_obj.get("scheme_id") or f"sch-{s_name.lower().replace(' ', '-')[:25]}"
            key = (s_id, s_name.lower().strip())
            if key not in cleaned_map:
                cleaned_map[key] = raw_obj

    unique_schemes = list(cleaned_map.values())
    logger.info(f"Deduplicated to {len(unique_schemes)} unique schemes.")

    # 4. Ingest each scheme into PostgreSQL
    async with AsyncSessionLocal() as db:
        indexed_count = 0
        total_chunks_created = 0

        for s_data in unique_schemes:
            try:
                chunks_count, _ = await index_scheme(db, s_data, replace=True, force_reindex=True)
                total_chunks_created += chunks_count
                indexed_count += 1
            except Exception as err:
                logger.error(f"Error indexing scheme {s_data.get('scheme_id')}: {err}")

        # Ensure all Schemes in DB are marked is_published = True
        await db.execute(update(Scheme).values(is_published=True))
        await db.commit()

        # Check count in DB
        res = await db.execute(select(Scheme).where(Scheme.is_published == True))
        db_schemes = res.scalars().all()

        print("\n" + "=" * 80)
        print(f" SUCCESS: Ingested & Published {len(db_schemes)} schemes into PostgreSQL!")
        print(f" Total Knowledge Chunks Created: {total_chunks_created}")
        print("=" * 80 + "\n")

        for i, s in enumerate(db_schemes, 1):
            print(f"{i:2d}. [{s.id}] {s.title} ({s.jurisdiction} - {s.state or 'Central'})")

        try:
            from app.api.v1.schemes import invalidate_schemes_cache
            invalidate_schemes_cache()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(ingest_all_schemes())
