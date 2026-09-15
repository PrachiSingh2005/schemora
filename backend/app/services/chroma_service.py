"""ChromaDB Service — Schemora Vector Database Manager.

Manages persistent vector collection storage, chunk upserts, scheme vector deletion,
and fast vector similarity queries using ChromaDB.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_chroma_client = None
_chroma_collection = None


def get_chroma_client():
    """Lazy initialize persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        persist_dir = Path(settings.CHROMA_PERSIST_DIRECTORY).resolve()
        persist_dir.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(persist_dir))
        logger.info(f"Initialized ChromaDB persistent client at: {persist_dir}")
    return _chroma_client


def get_chroma_collection():
    """Get or create ChromaDB collection for knowledge chunks."""
    global _chroma_collection
    if _chroma_collection is None:
        client = get_chroma_client()
        _chroma_collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"Loaded ChromaDB collection: {settings.CHROMA_COLLECTION_NAME}")
    return _chroma_collection


def _clean_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all metadata values are primitive types supported by ChromaDB (str, int, float, bool)."""
    cleaned = {}
    for k, v in meta.items():
        if v is None:
            cleaned[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            cleaned[k] = v
        else:
            cleaned[k] = str(v)
    return cleaned


def add_or_update_chunks(chunks_data: List[Dict[str, Any]]) -> int:
    """Upsert a list of chunk dicts into ChromaDB.

    Each dict in `chunks_data` should contain:
      - id: str
      - embedding: List[float]
      - content: str
      - metadata: Dict[str, Any]

    Returns the count of upserted vectors.
    """
    if not chunks_data:
        return 0

    collection = get_chroma_collection()

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for item in chunks_data:
        chunk_id = str(item.get("id", ""))
        embedding = item.get("embedding")
        content = item.get("content", "")
        raw_meta = item.get("metadata", {})

        if not chunk_id or not embedding or not isinstance(embedding, list):
            continue

        ids.append(chunk_id)
        embeddings.append(embedding)
        documents.append(content)
        metadatas.append(_clean_metadata(raw_meta))

    if not ids:
        return 0

    try:
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        logger.info(f"Upserted {len(ids)} vectors into ChromaDB collection '{settings.CHROMA_COLLECTION_NAME}'")
        return len(ids)
    except Exception as e:
        logger.error(f"Failed to upsert chunks into ChromaDB: {e}")
        return 0


def delete_chunks_by_scheme_id(scheme_id: str) -> bool:
    """Delete all vectors matching `scheme_id` from ChromaDB."""
    if not scheme_id:
        return False
    try:
        collection = get_chroma_collection()
        collection.delete(where={"scheme_id": scheme_id})
        logger.info(f"Deleted ChromaDB vectors for scheme_id: {scheme_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to delete ChromaDB vectors for scheme_id {scheme_id}: {e}")
        return False


def query_similar_chunks(
    query_embedding: List[float],
    top_k: int = 10,
    where_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Query ChromaDB collection for top_k most similar vectors.

    Args:
        query_embedding: Dense float array vector of user query.
        top_k: Number of results to retrieve.
        where_filter: Metadata query filter (e.g. {"scheme_id": "sch-1"}, {"state": "MH"}).

    Returns:
        List of result dicts containing: id, document, metadata, distance, similarity_score.
    """
    if not query_embedding or not isinstance(query_embedding, list):
        return []

    try:
        collection = get_chroma_collection()
        if collection.count() == 0:
            return []

        kw_args = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, max(1, collection.count())),
        }
        if where_filter:
            # Clean where_filter to remove empty/None values
            cleaned_where = {k: v for k, v in where_filter.items() if v is not None and v != ""}
            if cleaned_where:
                kw_args["where"] = cleaned_where

        res = collection.query(**kw_args)

        results = []
        if res and res.get("ids") and res["ids"][0]:
            ids = res["ids"][0]
            documents = res["documents"][0] if res.get("documents") else [""] * len(ids)
            metadatas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(ids)
            distances = res["distances"][0] if res.get("distances") else [1.0] * len(ids)

            for c_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
                # Cosine distance to cosine similarity conversion
                # ChromaDB cosine distance ranges from 0.0 (identical) to 2.0 (opposite)
                similarity = max(0.0, 1.0 - dist)
                results.append({
                    "id": c_id,
                    "document": doc,
                    "metadata": meta or {},
                    "distance": dist,
                    "similarity_score": round(similarity, 4),
                })

        return results
    except Exception as e:
        logger.error(f"ChromaDB query error: {e}")
        return []


def get_collection_count() -> int:
    """Return total count of vectors stored in ChromaDB collection."""
    try:
        collection = get_chroma_collection()
        return collection.count()
    except Exception as e:
        logger.warning(f"Could not fetch ChromaDB collection count: {e}")
        return 0
