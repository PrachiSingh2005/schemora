import pytest
from app.services import chroma_service


def test_chroma_add_query_delete():
    # Test data
    chunk_1 = {
        "id": "test-chunk-1",
        "embedding": [0.1] * 128,
        "content": "Scholarship for OBC students in Maharashtra.",
        "metadata": {
            "scheme_id": "sch-test-1",
            "scheme_name": "Test OBC Scholarship",
            "section": "eligibility",
            "state": "Maharashtra",
            "category": "Scholarship",
        }
    }
    chunk_2 = {
        "id": "test-chunk-2",
        "embedding": [0.9] * 128,
        "content": "Financial aid for farmers in Gujarat.",
        "metadata": {
            "scheme_id": "sch-test-2",
            "scheme_name": "Farmer Aid Scheme",
            "section": "benefits",
            "state": "Gujarat",
            "category": "Agriculture",
        }
    }

    # Upsert chunks into ChromaDB
    upserted_count = chroma_service.add_or_update_chunks([chunk_1, chunk_2])
    assert upserted_count == 2
    assert chroma_service.get_collection_count() >= 2

    # Query ChromaDB with vector similar to chunk_1
    query_vec = [0.12] * 128
    results = chroma_service.query_similar_chunks(query_vec, top_k=2)

    assert len(results) >= 1
    assert results[0]["id"] == "test-chunk-1"
    assert results[0]["similarity_score"] > 0.8
    assert results[0]["metadata"]["scheme_id"] == "sch-test-1"

    # Query with metadata filter
    results_filter = chroma_service.query_similar_chunks(
        query_vec, top_k=2, where_filter={"state": "Gujarat"}
    )
    assert len(results_filter) == 1
    assert results_filter[0]["id"] == "test-chunk-2"

    # Delete chunks for scheme 1
    deleted = chroma_service.delete_chunks_by_scheme_id("sch-test-1")
    assert deleted is True

    # Verify deletion
    results_after = chroma_service.query_similar_chunks(
        query_vec, top_k=2, where_filter={"scheme_id": "sch-test-1"}
    )
    assert len(results_after) == 0

    # Cleanup test chunk 2
    chroma_service.delete_chunks_by_scheme_id("sch-test-2")
