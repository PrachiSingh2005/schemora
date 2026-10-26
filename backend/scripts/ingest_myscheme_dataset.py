"""Safe PostgreSQL + pgvector Ingestion Script — Schemora.

Safely ingests or updates the cleaned myScheme dataset (data/myscheme_schemes.json)
into Schemora's PostgreSQL database and pgvector storage.

Ingestion Guarantees:
  1. Does NOT destroy existing data for unchanged schemes.
  2. Detects existing vs new schemes via scheme_id and SHA-256 content hashing.
  3. Updates changed schemes and removes/replaces only stale chunks for modified schemes.
  4. Preserves scheme IDs and metadata (scheme_id, source_url, state, category, section).
  5. Regenerates 768-dimension vector embeddings for changed/new chunks.

Usage:
  python scripts/ingest_myscheme_dataset.py
"""

import sys
import json
import asyncio
import logging
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.base import AsyncSessionLocal
from app.services.knowledge_base_service import index_scheme
from app.services import vector_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("schemora.ingestion")


async def main():
    data_file = BACKEND_DIR.parent / "data" / "myscheme_schemes.json"
    if not data_file.exists():
        logger.error(f"Dataset file not found: {data_file}")
        sys.exit(1)

    with open(data_file, "r", encoding="utf-8") as f:
        schemes = json.load(f)

    logger.info(f"Starting safe ingestion for {len(schemes)} myScheme records into PostgreSQL + pgvector...")

    inserted_count = 0
    updated_count = 0
    unchanged_count = 0
    failed_count = 0
    total_chunks = 0
    total_semantic_embeddings = 0

    async with AsyncSessionLocal() as db:
        for idx, scheme_dict in enumerate(schemes, 1):
            scheme_id = scheme_dict.get("scheme_id", f"scheme-{idx}")
            scheme_name = scheme_dict.get("scheme_name", "Unknown")

            try:
                # index_scheme detects SHA-256 hash match: returns (0, 0) if unchanged
                chunks, semantic = await index_scheme(
                    db,
                    scheme_dict,
                    replace=True,
                    force_reindex=False,  # Respect SHA-256 duplicate/update check
                )

                if chunks == 0 and semantic == 0:
                    unchanged_count += 1
                    logger.info(f"[{idx}/{len(schemes)}] UNCHANGED — {scheme_id} ({scheme_name[:35]})")
                else:
                    inserted_count += 1
                    total_chunks += chunks
                    total_semantic_embeddings += semantic
                    logger.info(
                        f"[{idx}/{len(schemes)}] INGESTED/UPDATED — {scheme_id}: "
                        f"{chunks} chunks ({semantic} pgvector embeddings)"
                    )
            except Exception as e:
                failed_count += 1
                logger.error(f"[{idx}/{len(schemes)}] FAILED to ingest {scheme_id}: {e}")

        # Vector count in PostgreSQL
        try:
            pgvector_total = await vector_service.get_vector_count_async(db)
        except Exception:
            pgvector_total = total_semantic_embeddings

    # Also sync into data/schemes/schemes.v1.json master dataset
    master_file = BACKEND_DIR.parent / "data" / "schemes" / "schemes.v1.json"
    try:
        master_file.parent.mkdir(parents=True, exist_ok=True)
        master_data = {
            "dataset_version": "2026-10-03-v2",
            "total_schemes": len(schemes),
            "source": "myScheme Official Complete Catalog",
            "schemes": schemes,
        }
        with open(master_file, "w", encoding="utf-8") as f:
            json.dump(master_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Synchronized master catalog at {master_file}")
    except Exception as e:
        logger.warning(f"Could not write master schemes.v1.json: {e}")

    print("\n" + "=" * 70)
    print("POSTGRESQL + PGVECTOR INGESTION COMPLETE")
    print("=" * 70)
    print(f"Total Schemes in Dataset : {len(schemes)}")
    print(f"New / Updated Schemes    : {inserted_count}")
    print(f"Unchanged (SHA-256 match): {unchanged_count}")
    print(f"Failed Ingestions        : {failed_count}")
    print(f"Knowledge Chunks Created : {total_chunks}")
    print(f"pgvector Vector Count    : {pgvector_total}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
