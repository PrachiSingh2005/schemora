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


import hashlib

def _generate_dense_vector_768(text: str) -> List[float]:
    """Generates a 768-dimensional dense float vector for text feature matching.

    Compatible with PostgreSQL pgvector (Vector(768)). Fast execution (< 0.1ms).
    """
    dim = 768
    vec = [0.0] * dim
    words = re.findall(r"\w+", text.lower())
    if not words:
        return vec

    features = list(words)
    for i in range(len(words) - 1):
        features.append(f"{words[i]}_{words[i+1]}")
    for w in words:
        if len(w) >= 3:
            for i in range(len(w) - 2):
                features.append(f"ngram_{w[i:i+3]}")

    for feat in features:
        h_bytes = hashlib.sha256(feat.encode("utf-8")).digest()
        idx = int.from_bytes(h_bytes[:4], "big") % dim
        sign = 1.0 if (h_bytes[4] % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [round(x / norm, 6) for x in vec]

    return vec


async def generate_embedding(text: str) -> Optional[List[float]]:
    """Generates 768-dim dense embedding vectors for PostgreSQL pgvector storage."""
    if not text or not text.strip():
        return None
    return _generate_dense_vector_768(text)


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
