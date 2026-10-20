"""Hybrid policy retrieval with chunking, BM25, local embeddings, and exact citations."""

import hashlib
import math
import os
import re
import uuid
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from resolvedesk.config import ROOT, RUNTIME
from resolvedesk.tracing import traceable

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_QDRANT_URL = os.getenv("QDRANT_URL", "")
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
_QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "resolvedesk_policies")
_DISABLE_EMBEDDINGS = os.getenv("RAG_DISABLE_EMBEDDINGS", "").lower() in {"1", "true", "yes", "on"}
_RRF_K = 60
_CHUNK_MAX_CHARS = int(os.getenv("RAG_CHUNK_MAX_CHARS", "512"))
_CHUNK_OVERLAP_CHARS = int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "128"))


def _tokens(value):
    return _TOKEN_RE.findall(value.lower().replace("_", " "))


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _chunk_text(text, max_chars=_CHUNK_MAX_CHARS, overlap_chars=_CHUNK_OVERLAP_CHARS):
    """Split *text* into overlapping chunks at sentence boundaries.

    Short texts that fit within *max_chars* are returned as a single chunk.
    Overlap is built from trailing sentences of the previous chunk so that
    context is preserved across boundaries.
    """
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return [text]

    chunks = []
    current = []
    current_len = 0

    for sentence in sentences:
        added_len = len(sentence) + (1 if current else 0)

        if current_len + added_len > max_chars and current:
            chunks.append(" ".join(current))
            # Retain trailing sentences that fit within the overlap budget.
            overlap, overlap_len = [], 0
            for s in reversed(current):
                candidate = len(s) + (1 if overlap else 0)
                if overlap_len + candidate > overlap_chars:
                    break
                overlap.insert(0, s)
                overlap_len += candidate
            current = overlap
            current_len = sum(len(s) for s in current) + max(len(current) - 1, 0)
            added_len = len(sentence) + (1 if current else 0)

        current.append(sentence)
        current_len += added_len

    if current:
        tail = " ".join(current)
        if not chunks or tail != chunks[-1]:
            chunks.append(tail)

    return chunks or [text]


# ---------------------------------------------------------------------------
# Policy loading and chunking
# ---------------------------------------------------------------------------


def policies():
    """Load raw policy documents from ``data/policies/*.md``."""
    result = []
    for path in sorted((ROOT / "data/policies").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        heading, body = text.split("\n", 1)
        pid, title = heading.lstrip("# ").split(" | ")
        result.append(
            {
                "id": pid,
                "title": title,
                "text": body.strip(),
                "version": 1,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
            }
        )
    return result


def _chunk_policies(docs):
    """Split each policy document into overlapping chunks, preserving parent metadata.

    Each chunk carries the parent ``id`` and ``title`` so that downstream
    citation validation (which checks policy IDs) continues to work.
    """
    chunks = []
    for doc in docs:
        parts = _chunk_text(doc["text"])
        for i, part in enumerate(parts):
            chunks.append(
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "text": part,
                    "version": doc["version"],
                    "sha256": hashlib.sha256(part.encode()).hexdigest(),
                    "parent_sha256": doc["sha256"],
                    "chunk_index": i,
                    "total_chunks": len(parts),
                }
            )
    return chunks


# ---------------------------------------------------------------------------
# Ranking strategies
# ---------------------------------------------------------------------------


def _tfidf_rank(query, docs):
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    matrix = vectorizer.fit_transform([p["title"] + " " + p["text"] for p in docs])
    scores = cosine_similarity(vectorizer.transform([query.replace("_", " ")]), matrix)[0]
    return sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)


@lru_cache(maxsize=1)
def _embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_EMBEDDING_MODEL)


def _bm25_rank(query, docs):
    tokenized = [_tokens(p["title"] + " " + p["text"]) for p in docs]
    average_length = sum(map(len, tokenized)) / max(len(tokenized), 1)
    document_frequency = {}
    for document in tokenized:
        for token in set(document):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    query_tokens = _tokens(query)
    scores = []
    for document in tokenized:
        counts = {token: document.count(token) for token in set(document)}
        score = 0.0
        for token in query_tokens:
            if token not in counts:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
            length_norm = 1.5 * (1 - 0.75 + 0.75 * len(document) / max(average_length, 1))
            score += idf * counts[token] * 2.5 / (counts[token] + length_norm)
        scores.append(score)
    return sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)


def _embedding_rank(query, docs):
    """Return semantic ranking, or a deterministic lexical fallback offline."""
    if _DISABLE_EMBEDDINGS:
        return _tfidf_rank(query, docs)
    if _QDRANT_URL:
        try:
            return _qdrant_rank(query, docs)
        except Exception:
            pass
    try:
        cache_dir = RUNTIME / "rag-index"
        cache_dir.mkdir(parents=True, exist_ok=True)
        fingerprint = hashlib.sha256(
            (_EMBEDDING_MODEL + "\n" + "\n".join(p["sha256"] for p in docs)).encode()
        ).hexdigest()
        vectors_path = cache_dir / f"{fingerprint}.npy"
        if vectors_path.exists():
            matrix = np.load(vectors_path)
        else:
            model = _embedding_model()
            matrix = model.encode(
                [p["title"] + " " + p["text"] for p in docs],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            np.save(vectors_path, matrix)
        model = _embedding_model()
        query_vector = model.encode(
            [query.replace("_", " ")], normalize_embeddings=True, show_progress_bar=False
        )[0]
        scores = matrix @ query_vector
        return sorted(range(len(docs)), key=lambda i: float(scores[i]), reverse=True)
    except (ImportError, OSError, RuntimeError, ValueError):
        return _tfidf_rank(query, docs)


def _qdrant_rank(query, docs):
    """Use Qdrant for semantic ranking when QDRANT_URL is configured."""
    from qdrant_client import QdrantClient
    from qdrant_client.http import models

    cache_dir = RUNTIME / "rag-index"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(
        (_EMBEDDING_MODEL + "\n" + "\n".join(p["sha256"] for p in docs)).encode()
    ).hexdigest()
    marker = cache_dir / f"qdrant-{fingerprint}.ready"
    model = _embedding_model()
    client = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY, timeout=30)

    if not marker.exists():
        texts = [p["title"] + " " + p["text"] for p in docs]
        matrix = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        vector_size = len(matrix[0])
        try:
            client.get_collection(_QDRANT_COLLECTION)
        except Exception:
            client.create_collection(
                collection_name=_QDRANT_COLLECTION,
                vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
            )
        points = [
            models.PointStruct(
                id=str(uuid.UUID(hashlib.md5((fingerprint + ":" + str(i)).encode()).hexdigest())),
                vector=matrix[i].tolist(),
                payload={"fingerprint": fingerprint, "index": i},
            )
            for i in range(len(docs))
        ]
        client.upsert(collection_name=_QDRANT_COLLECTION, points=points)
        marker.write_text("ready", encoding="utf-8")

    query_vector = model.encode([query.replace("_", " ")], normalize_embeddings=True, show_progress_bar=False)[
        0
    ].tolist()
    result = client.query_points(
        collection_name=_QDRANT_COLLECTION,
        query=query_vector,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="fingerprint", match=models.MatchValue(value=fingerprint))]
        ),
        limit=len(docs),
        with_payload=True,
    )
    ranked = [point.payload["index"] for point in result.points]
    seen = set(ranked)
    return ranked + [i for i in range(len(docs)) if i not in seen]


# ---------------------------------------------------------------------------
# De-duplication and retrieval entry point
# ---------------------------------------------------------------------------


def _deduplicate_by_parent(chunks, fused_scores, k):
    """Keep the highest-scoring chunk per parent policy, return top *k*."""
    best = {}
    for idx, chunk in enumerate(chunks):
        pid = chunk["id"]
        score = fused_scores[idx]
        if pid not in best or score > best[pid]["_score"]:
            best[pid] = {**chunk, "_score": score}
    ranked = sorted(best.values(), key=lambda d: (-d["_score"], d["id"]))[:k]
    # Replace internal key with the public field name.
    for entry in ranked:
        entry["score"] = round(entry.pop("_score"), 4)
    return ranked


@traceable(name="retrieve_policy_context", run_type="retriever", tags=["rag", "policies"])
def retrieve(query, k=3):
    """Retrieve policies with chunking, BM25 + embeddings, and reciprocal rank fusion.

    Documents are split into overlapping sentence-boundary chunks before
    ranking.  After RRF scoring the chunks are de-duplicated back to the
    parent policy level so that citation IDs stay valid.  Configure chunk
    size with ``RAG_CHUNK_MAX_CHARS`` / ``RAG_CHUNK_OVERLAP_CHARS``.

    The embedding model is downloaded lazily by sentence-transformers. Set
    ``RAG_DISABLE_EMBEDDINGS=true`` for small demo hosts, or set
    ``RAG_EMBEDDING_MODEL`` to a local model path for air-gapped deployments.
    """
    docs = policies()
    chunks = _chunk_policies(docs)
    rankings = (_bm25_rank(query, chunks), _embedding_rank(query, chunks))
    fused = {
        index: sum(
            1 / (_RRF_K + rank + 1)
            for ranking in rankings
            for rank, item in enumerate(ranking)
            if item == index
        )
        for index in range(len(chunks))
    }
    results = _deduplicate_by_parent(chunks, fused, k)
    for r in results:
        r["retrieval"] = (
            "hybrid_bm25_tfidf"
            if _DISABLE_EMBEDDINGS
            else "hybrid_bm25_qdrant"
            if _QDRANT_URL
            else "hybrid_bm25_embedding"
        )
    return results
