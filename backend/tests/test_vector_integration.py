import pytest
import pytest_asyncio
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.services import vector_service


@pytest.mark.asyncio
async def test_vector_service_upsert_query_delete(db_session):
    # Create parent document
    doc = KnowledgeDocument(
        id="test-doc-001",
        title="Test Scheme Document",
        doc_type="Test",
    )
    db_session.add(doc)

    # Create chunks
    chunk_1 = KnowledgeChunk(
        id="test-chunk-1",
        document_id=doc.id,
        scheme_id="sch-test-1",
        chunk_index=0,
        content="Scholarship for OBC students in Maharashtra.",
        section="eligibility",
        scheme_name="Test OBC Scholarship",
        state="Maharashtra",
        category="Scholarship",
        is_indexed=False,
    )
    chunk_2 = KnowledgeChunk(
        id="test-chunk-2",
        document_id=doc.id,
        scheme_id="sch-test-2",
        chunk_index=1,
        content="Financial aid for farmers in Gujarat.",
        section="benefits",
        scheme_name="Farmer Aid Scheme",
        state="Gujarat",
        category="Agriculture",
        is_indexed=False,
    )
    db_session.add(chunk_1)
    db_session.add(chunk_2)
    await db_session.flush()

    # Test upserting embeddings
    emb1 = [0.1] * 768
    emb2 = [0.9] * 768

    upsert_data = [
        {"id": "test-chunk-1", "embedding": emb1},
        {"id": "test-chunk-2", "embedding": emb2},
    ]

    upserted_count = await vector_service.upsert_vectors_async(db_session, upsert_data)
    assert upserted_count == 2

    count = await vector_service.get_vector_count_async(db_session)
    assert count >= 2

    # Query with vector similar to chunk 1
    query_vec = [0.12] * 768
    results = await vector_service.query_similar_chunks_async(
        db_session, query_embedding=query_vec, top_k=2
    )

    assert len(results) >= 1
    assert results[0]["id"] == "test-chunk-1"
    assert results[0]["similarity_score"] > 0.8
    assert results[0]["metadata"]["scheme_id"] == "sch-test-1"

    # Query with metadata filter
    results_filter = await vector_service.query_similar_chunks_async(
        db_session,
        query_embedding=query_vec,
        top_k=2,
        where_filter={"state": "Gujarat"},
    )
    assert len(results_filter) == 1
    assert results_filter[0]["id"] == "test-chunk-2"

    # Delete vectors for scheme 1
    deleted = await vector_service.delete_vectors_by_scheme_id_async(db_session, "sch-test-1")
    assert deleted is True

    # Verify vector deletion
    results_after = await vector_service.query_similar_chunks_async(
        db_session,
        query_embedding=query_vec,
        top_k=2,
        where_filter={"scheme_id": "sch-test-1"},
    )
    assert len(results_after) == 0
