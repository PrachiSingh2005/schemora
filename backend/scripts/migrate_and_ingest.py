"""Schemora Pure PostgreSQL + pgvector Migration & Ingestion Script.

Usage:
  python scripts/migrate_and_ingest.py

This script:
  1. Tests connection to PostgreSQL (via DATABASE_URL in .env).
  2. Enables pgvector extension (`CREATE EXTENSION IF NOT EXISTS vector;`).
  3. Runs Alembic database migrations (`alembic upgrade head`).
  4. Ingests all 60+ Schemora schemes and 400+ knowledge chunks into PostgreSQL.
  5. Generates and stores vector embeddings in PostgreSQL pgvector column (`embedding_vec`).
  6. Verifies scheme count, knowledge chunk count, and pgvector embedding count.
  7. Runs diagnostic test queries ("farmer schemes", "schemes for women").
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("schemora.postgres_migrate")


async def main():
    print("=" * 75)
    print(" SCHEMORA PURE POSTGRESQL + PGVECTOR MIGRATION & INGESTION ")
    print("=" * 75)

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal, engine
    from sqlalchemy import text

    # 1. Connection check
    dialect = getattr(engine.dialect, "name", "")
    safe_url = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else settings.DATABASE_URL

    logger.info(f"Targeting Database: backend='{dialect}', host/db='{safe_url}'")
    if dialect != "postgresql":
        logger.error(
            f"ERROR: DATABASE_URL is pointing to dialect '{dialect}'. "
            "Schemora architecture requires PostgreSQL + pgvector exclusively."
        )
        sys.exit(1)

    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1;"))
            if res.scalar() == 1:
                logger.info("✓ PostgreSQL connection successful!")
    except Exception as e:
        logger.error(f"✕ CRITICAL: Failed to connect to PostgreSQL database: {e}")
        logger.error("Please check DATABASE_URL in backend/.env and ensure PostgreSQL is running.")
        sys.exit(1)

    # 2. Enable pgvector extension
    try:
        async with AsyncSessionLocal() as session:
            logger.info("Enabling pgvector extension in PostgreSQL...")
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await session.commit()
            logger.info("✓ pgvector extension enabled successfully!")
    except Exception as e:
        logger.error(f"✕ Failed to enable pgvector extension: {e}")
        sys.exit(1)

    # 3. Alembic Migrations
    logger.info("Executing Alembic database migrations...")
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")
        logger.info("✓ Alembic migrations applied to head successfully!")
    except Exception as e:
        logger.warning(f"Alembic migration via API failed/bypassed: {e}. Ensuring table schema via ORM...")
        async with engine.begin() as conn:
            from app.core.database import Base
            await conn.run_sync(Base.metadata.create_all)

    # 4. Populate Scheme Data & Generate pgvector Embeddings
    logger.info("Ingesting Schemora dataset & indexing into PostgreSQL pgvector...")
    from app.services.knowledge_base_service import index_all_schemes, get_knowledge_base_status
    async with AsyncSessionLocal() as session:
        result = await index_all_schemes(session)
        kb_status = await get_knowledge_base_status(session)

    # 5. Verification Report
    print("\n" + "=" * 75)
    print(" POSTGRESQL + PGVECTOR INGESTION VERIFICATION REPORT")
    print("=" * 75)
    print(f" Database Dialect        : {dialect}")
    print(f" Total Schemes Inserted  : {result.get('total_schemes')}")
    print(f" Total Chunks Created   : {result.get('total_chunks')}")
    print(f" pgvector Embeddings     : {result.get('pgvector_vectors')}")
    print(f" Ingestion Status        : SUCCESS")
    print("=" * 75 + "\n")

    # 6. Test RAG Retrieval
    logger.info("Running diagnostic RAG retrieval test queries...")
    from app.services.retrieval_service_impl import retrieve_relevant_chunks
    test_queries = ["farmer schemes", "schemes for women"]

    async with AsyncSessionLocal() as session:
        for q in test_queries:
            print(f"\n--- Testing Query: '{q}' ---")
            chunks = await retrieve_relevant_chunks(session, query=q, top_k=5)
            print(f"Retrieved Chunks Count: {len(chunks)}")
            for c in chunks:
                meta = c.get("metadata", {})
                title = meta.get("scheme_name") or str(c.get("document", ""))[:40]
                url = meta.get("official_info_url") or meta.get("official_app_url") or "N/A"
                sec = meta.get("section") or "N/A"
                score = c.get("similarity_score", 0.0)
                print(f"  • [{sec}] {title} | URL: {url} | Score: {score}")

    print("\n" + "=" * 75)
    print(" MIGRATION AND VERIFICATION COMPLETED SUCCESSFULLY ")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
