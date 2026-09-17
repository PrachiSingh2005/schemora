"""Embedding service for Schemora RAG pipeline.

Provides vector embeddings and TF-IDF representations for text search and retrieval.
"""

import json
import math
import re
import logging
from typing import List, Dict, Optional, Union

logger = logging.getLogger(__name__)


def _tfidf_vector(text: str) -> Dict[str, float]:
    """Lightweight TF-IDF word frequency vector."""
    words = re.findall(r"\w+", text.lower())
    total = max(1, len(words))
    freqs: Dict[str, int] = {}
    for w in words:
        freqs[w] = freqs.get(w, 0) + 1
    return {w: c / total for w, c in freqs.items()}


def cosine_similarity_tfidf(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Cosine similarity between two TF-IDF dicts."""
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    dot = sum(v1[w] * v2[w] for w in common)
    n1 = math.sqrt(sum(x ** 2 for x in v1.values()))
    n2 = math.sqrt(sum(x ** 2 for x in v2.values()))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def cosine_similarity_dense(v1: List[float], v2: List[float]) -> float:
    """Cosine similarity between two dense float vectors."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a ** 2 for a in v1))
    n2 = math.sqrt(sum(b ** 2 for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def is_dense_embedding(data: Union[Dict, List, None]) -> bool:
    """Returns True if the stored embedding is a dense float list."""
    return isinstance(data, list) and len(data) > 10


async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generates dense embedding vectors if external dense model configured.

    Returns None to fallback to TF-IDF representation.
    """
    return None


def embedding_to_json(embedding: Union[List[float], Dict[str, float], None]) -> str:
    """Serialize an embedding (dense list or TF-IDF dict) to JSON string."""
    if embedding is None:
        return json.dumps({})
    return json.dumps(embedding)


def json_to_embedding(json_str: Optional[str]) -> Union[List[float], Dict[str, float], None]:
    """Deserialize an embedding from its stored JSON string."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except Exception:
        return None


async def embed_text(text: str) -> tuple[Union[List[float], Dict[str, float]], bool]:
    """Embed text. Returns (embedding, is_semantic).

    is_semantic=True means a dense embedding was returned.
    is_semantic=False means TF-IDF fallback was used.
    """
    dense = await generate_embedding(text)
    if dense:
        return dense, True
    return _tfidf_vector(text), False
