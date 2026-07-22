from __future__ import annotations

from core.contracts import Chunk
from rag.embeddings.mock_embedding_provider import MockEmbeddingProvider
from rag.vectorstores.chroma_store import ChromaVectorStore

# Real, local, network-free integration test: Chroma's PersistentClient
# requires no server, so this exercises actual add/search/delete behavior
# against a temporary on-disk collection rather than just plumbing/config.


def _make_chunk(embedder: MockEmbeddingProvider, chunk_id: str, doc_id: str, text: str) -> Chunk:
    [vector] = embedder.embed([text])
    return Chunk(chunk_id=chunk_id, doc_id=doc_id, text=text, embedding=vector, metadata={"doc_id": doc_id})


def test_add_and_search_roundtrip(tmp_path):
    embedder = MockEmbeddingProvider()
    store = ChromaVectorStore(
        persist_directory=str(tmp_path / "chroma"),
        collection_name="test_collection",
    )

    chunks = [
        _make_chunk(embedder, "c1", "doc1", "payments settlement window controls"),
        _make_chunk(embedder, "c2", "doc1", "credit risk scoring model documentation"),
        _make_chunk(embedder, "c3", "doc2", "fraud detection alerting thresholds"),
    ]
    store.add(chunks)

    [query_vector] = embedder.embed(["payments settlement window controls"])
    results = store.search(query_vector, top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "c1"  # identical text -> identical mock vector -> top match


def test_health_check_reports_healthy_after_add(tmp_path):
    embedder = MockEmbeddingProvider()
    store = ChromaVectorStore(persist_directory=str(tmp_path / "chroma"))
    store.add([_make_chunk(embedder, "c1", "doc1", "sample text")])
    status = store.health_check()
    assert status.healthy is True
    assert status.backend == "chroma"


def test_delete_by_document_removes_only_that_documents_chunks(tmp_path):
    embedder = MockEmbeddingProvider()
    store = ChromaVectorStore(persist_directory=str(tmp_path / "chroma"))
    store.add(
        [
            _make_chunk(embedder, "c1", "doc1", "alpha"),
            _make_chunk(embedder, "c2", "doc2", "beta"),
        ]
    )
    store.delete_by_document("doc1")

    [query_vector] = embedder.embed(["alpha"])
    results = store.search(query_vector, top_k=5)
    remaining_doc_ids = {c.doc_id for c in results}
    assert "doc1" not in remaining_doc_ids
    assert "doc2" in remaining_doc_ids


def test_clear_empties_the_collection(tmp_path):
    embedder = MockEmbeddingProvider()
    store = ChromaVectorStore(persist_directory=str(tmp_path / "chroma"))
    store.add([_make_chunk(embedder, "c1", "doc1", "alpha")])
    store.clear()

    [query_vector] = embedder.embed(["alpha"])
    results = store.search(query_vector, top_k=5)
    assert results == []


def test_search_respects_metadata_filters(tmp_path):
    embedder = MockEmbeddingProvider()
    store = ChromaVectorStore(persist_directory=str(tmp_path / "chroma"))
    store.add(
        [
            Chunk(
                chunk_id="c1",
                doc_id="doc1",
                text="alpha",
                embedding=embedder.embed(["alpha"])[0],
                metadata={"doc_id": "doc1", "category": "policy"},
            ),
            Chunk(
                chunk_id="c2",
                doc_id="doc2",
                text="alpha",
                embedding=embedder.embed(["alpha"])[0],
                metadata={"doc_id": "doc2", "category": "evidence"},
            ),
        ]
    )
    [query_vector] = embedder.embed(["alpha"])
    results = store.search(query_vector, top_k=5, filters={"category": "policy"})
    assert {c.chunk_id for c in results} == {"c1"}
