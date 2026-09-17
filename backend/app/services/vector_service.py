"""Vector Service — Schemora PostgreSQL pgvector Database Manager.

Manages vector embeddings, similarity search, and vector filtering
using PostgreSQL pgvector (`KnowledgeChunk.embedding_vec`).
Includes graceful fallback for SQLite / test environments.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.models.knowledge import KnowledgeChunk
from app.services.embedding_service import (
    json_to_embedding,
    is_dense_embedding,
    cosine_similarity_dense,
)

logger = logging.getLogger(__name__)


def _is_pgvector_supported(db: AsyncSession) -> bool:
    """Return True if the DB engine is PostgreSQL."""
    bind = db.get_bind()
    dialect = getattr(bind.dialect, "name", "")
    return dialect == "postgresql"


async def upsert_vectors_async(
    db: AsyncSession,
    chunks_data: List[Dict[str, Any]],
) -> int:
    """Upsert a list of chunk dicts with vector embeddings into PostgreSQL.

    Each item in `chunks_data` should contain:
      - id: str (KnowledgeChunk PK)
      - embedding: List[float]
      - content: str (optional)
      - metadata: Dict[str, Any] (optional)

    Returns the count of upserted vectors.
    """
    if not chunks_data:
        return 0

    updated_count = 0
    for item in chunks_data:
        chunk_id = str(item.get("id", ""))
        embedding = item.get("embedding")
        if not chunk_id or not embedding or not isinstance(embedding, list):
            continue

        result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id)
        )
        chunk_obj = result.scalar_one_or_none()
        if chunk_obj:
            chunk_obj.embedding_vec = embedding
            chunk_obj.embedding_json = json.dumps(embedding)
            chunk_obj.is_indexed = True
            updated_count += 1

    if updated_count > 0:
        await db.flush()
        logger.info(f"Upserted {updated_count} vectors into PostgreSQL pgvector storage")

    return updated_count


async def query_similar_chunks_async(
    db: AsyncSession,
    query_embedding: List[float],
    top_k: int = 10,
    where_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Query PostgreSQL pgvector for top_k most similar vectors.

    Args:
        db: Async database session.
        query_embedding: Dense float vector of user query.
        top_k: Number of results to retrieve.
        where_filter: Metadata filter dict (e.g. {"scheme_id": "sch-1", "state": "MH"}).

    Returns:
        List of result dicts containing: id, document, metadata, distance, similarity_score.
    """
    if not query_embedding or not isinstance(query_embedding, list):
        return []

    where_filter = where_filter or {}
    cleaned_filter = {k: v for k, v in where_filter.items() if v is not None and v != ""}

    # ── Path A: Native PostgreSQL pgvector search ────────────────────────────
    if _is_pgvector_supported(db):
        try:
            stmt = select(
                KnowledgeChunk,
                KnowledgeChunk.embedding_vec.cosine_distance(query_embedding).label("distance"),
            ).where(KnowledgeChunk.embedding_vec != None)

            # Apply filters
            if "scheme_id" in cleaned_filter:
                stmt = stmt.where(KnowledgeChunk.scheme_id == cleaned_filter["scheme_id"])
            if "state" in cleaned_filter:
                stmt = stmt.where(
                    or_(
                        KnowledgeChunk.state == cleaned_filter["state"],
                        KnowledgeChunk.state == None,
                        KnowledgeChunk.state == "",
                        KnowledgeChunk.jurisdiction.ilike("%Central%"),
                    )
                )
            if "category" in cleaned_filter:
                stmt = stmt.where(KnowledgeChunk.category == cleaned_filter["category"])
            if "section" in cleaned_filter:
                stmt = stmt.where(KnowledgeChunk.section == cleaned_filter["section"])

            stmt = stmt.order_by("distance").limit(top_k)

            result = await db.execute(stmt)
            rows = result.all()

            results = []
            for chunk, dist in rows:
                distance_val = float(dist) if dist is not None else 1.0
                similarity = max(0.0, 1.0 - distance_val)

                meta = {
                    "scheme_id": chunk.scheme_id or "",
                    "scheme_name": chunk.scheme_name or "",
                    "section": chunk.section or "",
                    "jurisdiction": chunk.jurisdiction or "",
                    "state": chunk.state or "",
                    "category": chunk.category or "",
                    "source_id": chunk.source_id or "",
                    "official_info_url": chunk.official_info_url or "",
                    "official_app_url": chunk.official_app_url or "",
                    "last_verified_at": chunk.last_verified_at or "2026-08-07",
                    "scheme_version": chunk.scheme_version or "v1",
                }

                results.append({
                    "id": chunk.id,
                    "document": chunk.content,
                    "metadata": meta,
                    "distance": distance_val,
                    "similarity_score": round(similarity, 4),
                })

            return results
        except Exception as e:
            logger.warning(f"PostgreSQL pgvector query error, falling back to in-memory scan: {e}")

    # ── Path B: Fallback scan (SQLite / unindexed DBs) ───────────────────────
    stmt = select(KnowledgeChunk).where(KnowledgeChunk.is_indexed == True)
    if "scheme_id" in cleaned_filter:
        stmt = stmt.where(KnowledgeChunk.scheme_id == cleaned_filter["scheme_id"])
    if "state" in cleaned_filter:
        stmt = stmt.where(
            or_(
                KnowledgeChunk.state == cleaned_filter["state"],
                KnowledgeChunk.state == None,
                KnowledgeChunk.state == "",
                KnowledgeChunk.jurisdiction.ilike("%Central%"),
            )
        )
    if "category" in cleaned_filter:
        stmt = stmt.where(KnowledgeChunk.category == cleaned_filter["category"])
    if "section" in cleaned_filter:
        stmt = stmt.where(KnowledgeChunk.section == cleaned_filter["section"])

    result = await db.execute(stmt)
    chunks = result.scalars().all()

    results = []
    for chunk in chunks:
        vec = chunk.embedding_vec
        if isinstance(vec, str):
            vec = json_to_embedding(vec)
        elif vec is None:
            vec = json_to_embedding(chunk.embedding_json)

        if is_dense_embedding(vec):
            score = cosine_similarity_dense(query_embedding, vec)
            dist = max(0.0, 1.0 - score)
            meta = {
                "scheme_id": chunk.scheme_id or "",
                "scheme_name": chunk.scheme_name or "",
                "section": chunk.section or "",
                "jurisdiction": chunk.jurisdiction or "",
                "state": chunk.state or "",
                "category": chunk.category or "",
                "source_id": chunk.source_id or "",
                "official_info_url": chunk.official_info_url or "",
                "official_app_url": chunk.official_app_url or "",
                "last_verified_at": chunk.last_verified_at or "2026-08-07",
                "scheme_version": chunk.scheme_version or "v1",
            }
            results.append({
                "id": chunk.id,
                "document": chunk.content,
                "metadata": meta,
                "distance": round(dist, 4),
                "similarity_score": round(score, 4),
            })

    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    return results[:top_k]


async def delete_vectors_by_scheme_id_async(db: AsyncSession, scheme_id: str) -> bool:
    """Clear vector embeddings for a given scheme ID."""
    if not scheme_id:
        return False
    try:
        result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.scheme_id == scheme_id)
        )
        chunks = result.scalars().all()
        for c in chunks:
            c.embedding_vec = None
            c.is_indexed = False
        await db.flush()
        logger.info(f"Cleared pgvector embeddings for scheme_id: {scheme_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to clear pgvector embeddings for scheme_id {scheme_id}: {e}")
        return False


async def get_vector_count_async(db: AsyncSession) -> int:
    """Return total count of indexed vectors stored in PostgreSQL."""
    try:
        result = await db.execute(
            select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.is_indexed == True)
        )
        return result.scalar() or 0
    except Exception as e:
        logger.warning(f"Could not fetch pgvector count: {e}")
        return 0
