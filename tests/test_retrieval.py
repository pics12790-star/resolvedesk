"""Comprehensive tests for the retrieval pipeline: chunking, BM25, TF-IDF,
embeddings, RRF fusion, de-duplication, and end-to-end retrieval correctness."""

import hashlib
import os

import pytest
from resolvedesk.retrieval import (
    _bm25_rank,
    _chunk_policies,
    _chunk_text,
    _deduplicate_by_parent,
    _embedding_rank,
    _tfidf_rank,
    _tokens,
    policies,
    retrieve,
)


# ===================================================================
# Tokenisation
# ===================================================================


class TestTokens:
    def test_basic_lowercase(self):
        assert _tokens("Hello World") == ["hello", "world"]

    def test_strips_punctuation(self):
        assert _tokens("order_id: ORD-1001!") == ["order", "id", "ord", "1001"]

    def test_underscore_becomes_space(self):
        assert _tokens("damaged_item") == ["damaged", "item"]

    def test_empty_string(self):
        assert _tokens("") == []

    def test_numeric_tokens(self):
        assert _tokens("3 items at $12") == ["3", "items", "at", "12"]


# ===================================================================
# Chunking — _chunk_text
# ===================================================================


class TestChunkText:
    def test_short_text_stays_single(self):
        text = "This is a short text. It should stay as one chunk."
        chunks = _chunk_text(text, max_chars=512, overlap_chars=128)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_long_text(self):
        text = ". ".join(
            [f"Sentence number {i} has some extra padding words" for i in range(30)]
        ) + "."
        chunks = _chunk_text(text, max_chars=200, overlap_chars=50)
        assert len(chunks) > 1
        # Every chunk should be within budget (may slightly exceed due to
        # sentence boundary — but should not be wildly over).
        for chunk in chunks:
            assert len(chunk) < 400, f"Chunk too large: {len(chunk)} chars"

    def test_overlap_content_shared(self):
        """Consecutive chunks should share overlapping sentence content."""
        text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five."
        chunks = _chunk_text(text, max_chars=40, overlap_chars=20)
        assert len(chunks) >= 2
        # At least one sentence should appear in both chunk[0] and chunk[1].
        words_0 = set(chunks[0].split())
        words_1 = set(chunks[1].split())
        assert words_0 & words_1, "Expected overlapping words between consecutive chunks"

    def test_empty_string(self):
        chunks = _chunk_text("", max_chars=512, overlap_chars=128)
        assert chunks == [""]

    def test_whitespace_only(self):
        chunks = _chunk_text("   ", max_chars=512, overlap_chars=128)
        assert chunks == ["   "]

    def test_single_sentence(self):
        text = "Only one sentence here."
        chunks = _chunk_text(text, max_chars=512, overlap_chars=128)
        assert chunks == [text]

    def test_exact_boundary(self):
        """Text exactly at max_chars should not split."""
        text = "A" * 512
        chunks = _chunk_text(text, max_chars=512, overlap_chars=128)
        assert len(chunks) == 1

    def test_no_sentence_breaks(self):
        """A long text without periods stays as one chunk (no sentence boundaries)."""
        text = "word " * 200  # ~1000 chars, no period
        chunks = _chunk_text(text.strip(), max_chars=100, overlap_chars=20)
        # Without sentence endings the splitter cannot break it, so it stays whole.
        assert len(chunks) == 1

    def test_deterministic(self):
        text = "Alpha. Bravo. Charlie. Delta. Echo. Foxtrot."
        a = _chunk_text(text, max_chars=30, overlap_chars=10)
        b = _chunk_text(text, max_chars=30, overlap_chars=10)
        assert a == b

    def test_all_original_content_covered(self):
        """The union of all chunks should contain every sentence from the original."""
        text = ". ".join(f"Sentence {i}" for i in range(20)) + "."
        chunks = _chunk_text(text, max_chars=100, overlap_chars=30)
        joined = " ".join(chunks)
        for i in range(20):
            assert f"Sentence {i}" in joined


# ===================================================================
# Policy loading
# ===================================================================


EXPECTED_POLICY_IDS = {
    "APP-01",
    "DAM-01",
    "FRA-01",
    "INT-01",
    "INV-01",
    "PAY-01",
    "REF-01",
    "RET-01",
    "SEC-01",
    "SHIP-01",
    "SUB-01",
    "WAR-01",
}


class TestPolicies:
    def test_loads_policy_corpus(self):
        docs = policies()
        assert len(docs) == 12
        ids = {d["id"] for d in docs}
        assert ids == EXPECTED_POLICY_IDS

    def test_fields_present(self):
        for doc in policies():
            assert set(doc.keys()) == {"id", "title", "text", "version", "sha256"}

    def test_sha256_is_hex(self):
        for doc in policies():
            assert len(doc["sha256"]) == 64
            int(doc["sha256"], 16)  # validates hex

    def test_version_is_one(self):
        for doc in policies():
            assert doc["version"] == 1

    def test_text_not_empty(self):
        for doc in policies():
            assert len(doc["text"].strip()) > 0

    def test_titles(self):
        titles = {d["id"]: d["title"] for d in policies()}
        assert titles["SEC-01"] == "Account access, identity scope, and approval boundaries"
        assert titles["DAM-01"] == "Damaged items, replacement eligibility, and inspection evidence"
        assert titles["REF-01"] == "Refund lifecycle, payment rails, and status communication"
        assert titles["SHIP-01"] == "Delivery delays, lost shipments, and tracking exceptions"


# ===================================================================
# Policy chunking
# ===================================================================


class TestChunkPolicies:
    def test_chunk_count(self):
        """The expanded policy corpus chunks every policy at least once."""
        docs = policies()
        chunks = _chunk_policies(docs)
        assert len(chunks) >= len(docs)
        ids = [c["id"] for c in chunks]
        for policy_id in EXPECTED_POLICY_IDS:
            assert ids.count(policy_id) >= 1

    def test_preserves_parent_metadata(self):
        docs = [
            {
                "id": "TEST-01",
                "title": "Test Policy",
                "version": 42,
                "sha256": "abcdef" * 10 + "abcd",
                "text": "Short sentence.",
            }
        ]
        chunks = _chunk_policies(docs)
        assert len(chunks) == 1
        c = chunks[0]
        assert c["id"] == "TEST-01"
        assert c["title"] == "Test Policy"
        assert c["version"] == 42
        assert c["parent_sha256"] == docs[0]["sha256"]
        assert c["chunk_index"] == 0
        assert c["total_chunks"] == 1

    def test_chunk_fields(self):
        for chunk in _chunk_policies(policies()):
            assert "chunk_index" in chunk
            assert "total_chunks" in chunk
            assert "parent_sha256" in chunk
            assert 0 <= chunk["chunk_index"] < chunk["total_chunks"]

    def test_chunk_sha256_differs_from_parent(self):
        """Chunk sha256 is computed from chunk text, not the parent doc."""
        docs = policies()
        chunks = _chunk_policies(docs)
        multi = [c for c in chunks if c["total_chunks"] > 1]
        assert len(multi) > 0
        for c in multi:
            assert c["sha256"] != c["parent_sha256"]

    def test_chunk_sha256_is_content_hash(self):
        for chunk in _chunk_policies(policies()):
            expected = hashlib.sha256(chunk["text"].encode()).hexdigest()
            assert chunk["sha256"] == expected


# ===================================================================
# Ranking — BM25
# ===================================================================


class TestBM25:
    @pytest.fixture()
    def sample_docs(self):
        return [
            {"title": "Fruit", "text": "apple banana cherry"},
            {"title": "Vegetable", "text": "carrot potato onion"},
            {"title": "Mixed", "text": "apple carrot mango"},
        ]

    def test_returns_valid_permutation(self, sample_docs):
        ordering = _bm25_rank("apple", sample_docs)
        assert set(ordering) == {0, 1, 2}

    def test_relevant_doc_ranks_first(self, sample_docs):
        ordering = _bm25_rank("apple", sample_docs)
        # Doc 0 and 2 both contain "apple"; doc 1 doesn't.
        assert ordering[-1] == 1, "Doc without query term should rank last"

    def test_empty_query(self, sample_docs):
        ordering = _bm25_rank("", sample_docs)
        assert set(ordering) == {0, 1, 2}

    def test_query_not_in_any_doc(self, sample_docs):
        ordering = _bm25_rank("zzzzzz", sample_docs)
        assert set(ordering) == {0, 1, 2}

    def test_single_doc(self):
        docs = [{"title": "Only", "text": "single document here"}]
        ordering = _bm25_rank("document", docs)
        assert ordering == [0]

    def test_real_policies(self):
        docs = policies()
        chunks = _chunk_policies(docs)
        ordering = _bm25_rank("damaged item replacement policy", chunks)
        assert set(ordering) == set(range(len(chunks)))


# ===================================================================
# Ranking — TF-IDF
# ===================================================================


class TestTFIDF:
    @pytest.fixture()
    def sample_docs(self):
        return [
            {"title": "Fruit", "text": "apple banana cherry"},
            {"title": "Vegetable", "text": "carrot potato onion"},
            {"title": "Mixed", "text": "apple carrot mango"},
        ]

    def test_returns_valid_permutation(self, sample_docs):
        ordering = _tfidf_rank("apple", sample_docs)
        assert set(ordering) == {0, 1, 2}

    def test_relevant_doc_ranks_higher(self, sample_docs):
        ordering = _tfidf_rank("apple", sample_docs)
        # Docs 0 and 2 contain "apple", so they should rank above doc 1.
        apple_positions = {ordering.index(0), ordering.index(2)}
        assert ordering.index(1) > min(apple_positions)

    def test_single_doc(self):
        docs = [{"title": "Solo", "text": "only one document"}]
        ordering = _tfidf_rank("document", docs)
        assert ordering == [0]


# ===================================================================
# Ranking — Embeddings (with fallback)
# ===================================================================


class TestEmbeddingRank:
    def test_returns_valid_permutation(self):
        docs = [
            {"title": "Fruit", "text": "apple banana cherry", "sha256": "a" * 64},
            {"title": "Veg", "text": "carrot potato onion", "sha256": "b" * 64},
            {"title": "Mix", "text": "apple carrot mango", "sha256": "c" * 64},
        ]
        ordering = _embedding_rank("apple", docs)
        assert set(ordering) == {0, 1, 2}

    def test_real_policies(self):
        docs = policies()
        chunks = _chunk_policies(docs)
        ordering = _embedding_rank("refund status", chunks)
        assert set(ordering) == set(range(len(chunks)))


# ===================================================================
# De-duplication
# ===================================================================


class TestDeduplicate:
    def test_keeps_highest_scoring_chunk(self):
        chunks = [
            {"id": "A", "title": "A", "text": "low"},
            {"id": "A", "title": "A", "text": "high"},
            {"id": "B", "title": "B", "text": "mid"},
        ]
        fused = {0: 0.5, 1: 0.9, 2: 0.7}
        result = _deduplicate_by_parent(chunks, fused, k=3)
        assert len(result) == 2
        assert result[0]["id"] == "A"
        assert result[0]["score"] == 0.9
        assert result[0]["text"] == "high"
        assert result[1]["id"] == "B"

    def test_respects_k(self):
        chunks = [
            {"id": "A", "text": "a"},
            {"id": "B", "text": "b"},
            {"id": "C", "text": "c"},
        ]
        fused = {0: 0.9, 1: 0.8, 2: 0.7}
        result = _deduplicate_by_parent(chunks, fused, k=2)
        assert len(result) == 2

    def test_tiebreak_by_id(self):
        """When scores tie, sort alphabetically by parent ID."""
        chunks = [
            {"id": "B", "text": "b"},
            {"id": "A", "text": "a"},
        ]
        fused = {0: 0.5, 1: 0.5}
        result = _deduplicate_by_parent(chunks, fused, k=2)
        assert result[0]["id"] == "A"
        assert result[1]["id"] == "B"

    def test_single_chunk(self):
        chunks = [{"id": "ONLY", "text": "one"}]
        fused = {0: 1.0}
        result = _deduplicate_by_parent(chunks, fused, k=5)
        assert len(result) == 1
        assert result[0]["score"] == 1.0

    def test_many_chunks_same_parent(self):
        chunks = [{"id": "X", "text": f"chunk-{i}"} for i in range(10)]
        fused = {i: float(i) for i in range(10)}
        result = _deduplicate_by_parent(chunks, fused, k=5)
        assert len(result) == 1
        assert result[0]["score"] == 9.0
        assert result[0]["text"] == "chunk-9"


# ===================================================================
# RRF fusion (integration)
# ===================================================================


class TestRRFFusion:
    def test_deterministic(self):
        r1 = retrieve("damaged headphones replacement")
        r2 = retrieve("damaged headphones replacement")
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a["id"] == b["id"]
            assert a["score"] == b["score"]

    def test_scores_are_positive(self):
        for r in retrieve("test query"):
            assert r["score"] > 0

    def test_scores_are_sorted_descending(self):
        results = retrieve("delivery tracking late")
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ===================================================================
# End-to-end retrieve()
# ===================================================================


class TestRetrieve:
    # --- Result count and schema ---

    def test_returns_at_most_k(self):
        assert len(retrieve("test", k=2)) <= 2

    def test_k_greater_than_corpus(self):
        results = retrieve("test", k=100)
        assert len(results) == len(EXPECTED_POLICY_IDS)

    def test_default_k(self):
        results = retrieve("anything")
        assert len(results) == 3

    def test_result_schema(self):
        expected = {
            "id", "title", "text", "version", "sha256", "score",
            "retrieval", "chunk_index", "total_chunks", "parent_sha256",
        }
        for r in retrieve("test", k=4):
            assert set(r.keys()) == expected

    def test_retrieval_method_field(self):
        expected = (
            "hybrid_bm25_tfidf"
            if os.getenv("RAG_DISABLE_EMBEDDINGS", "").lower() in {"1", "true", "yes", "on"}
            else "hybrid_bm25_qdrant"
            if os.getenv("QDRANT_URL")
            else "hybrid_bm25_embedding"
        )
        for r in retrieve("test"):
            assert r["retrieval"] == expected

    # --- All IDs are valid policies ---

    def test_ids_are_valid_policy_ids(self):
        for r in retrieve("anything at all", k=4):
            assert r["id"] in EXPECTED_POLICY_IDS

    # --- Intent-aligned ranking ---

    def test_damage_query_ranks_dam01_first(self):
        results = retrieve("damaged item replacement")
        assert results[0]["id"] == "DAM-01"

    def test_refund_query_ranks_ref01_first(self):
        results = retrieve("refund status pending")
        assert results[0]["id"] == "REF-01"

    def test_delivery_query_ranks_ship01_first(self):
        results = retrieve("delivery late tracking shipment")
        assert results[0]["id"] == "SHIP-01"

    def test_access_query_ranks_sec01_first(self):
        results = retrieve("account access ownership customer approval")
        assert results[0]["id"] == "SEC-01"

    # --- Query variations ---

    def test_combined_intent_query(self):
        """Query combining message + intent (as the agent does)."""
        results = retrieve("My headphones arrived damaged damaged_item")
        assert results[0]["id"] == "DAM-01"

    def test_single_word_query(self):
        results = retrieve("refund")
        assert len(results) > 0

    def test_long_query(self):
        long_q = "damaged item replacement refund " * 20
        results = retrieve(long_q)
        assert len(results) == 3

    # --- Chunk metadata in results ---

    def test_chunk_index_is_valid(self):
        for r in retrieve("test", k=4):
            assert 0 <= r["chunk_index"] < r["total_chunks"]

    def test_parent_sha256_is_hex(self):
        for r in retrieve("test", k=4):
            assert len(r["parent_sha256"]) == 64
            int(r["parent_sha256"], 16)

    # --- No duplicate parent IDs ---

    def test_no_duplicate_parents(self):
        results = retrieve("test", k=4)
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids)), "Each parent policy should appear at most once"

    # --- Eval-compatible: required_policy in results ---

    @pytest.mark.parametrize(
        "query,expected_policy",
        [
            ("The headphones arrived damaged. Could you send a replacement?", "DAM-01"),
            ("My headphones arrived with a cracked ear cup. Please help.", "DAM-01"),
            ("Could you check the tracking for my delivery?", "SHIP-01"),
            ("My delivery is late. Where is it?", "SHIP-01"),
            ("What is the status of my refund?", "REF-01"),
            ("Has my refund been processed?", "REF-01"),
        ],
    )
    def test_required_policy_in_top3(self, query, expected_policy):
        """The required policy for each eval case should appear in top-3 retrieval."""
        results = retrieve(query, k=3)
        ids = [r["id"] for r in results]
        assert expected_policy in ids, (
            f"Expected {expected_policy} in top 3 for query: {query!r}, got {ids}"
        )
