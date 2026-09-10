"""Dense embeddings for the semantic half of retrieval.

Keyword search (FTS5/BM25) cannot answer a question whose words do not appear
in the text - "what is this document about?" shares no term with the prose it
asks about. This module supplies the second, meaning-based channel.

Everything here degrades to `None` rather than raising: without HF_TOKEN, or
when the API is down, retrieval silently falls back to BM25-only and uploads
still succeed. Nothing in the app may depend on an embedding being available.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import numpy as np
from dotenv import load_dotenv

from config import settings

load_dotenv()

logger = logging.getLogger(__name__)

# BGE is trained asymmetrically: passages are embedded raw, queries get this
# prefix. Skipping it costs recall in a way that looks like "embeddings did
# not help much", so it is not optional.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# The provider is called over the network, so texts go up in batches.
_BATCH_SIZE = 32
_TIMEOUT_SECONDS = 60


class _Unavailable(RuntimeError):
    """Raised internally when no embedding client can be built."""


def dimension() -> int:
    return settings.embedding_dim


@lru_cache(maxsize=1)
def _client():
    """The shared HF inference client. Imported lazily so a missing package or
    token degrades retrieval instead of breaking startup."""
    if not settings.embedding_enabled:
        raise _Unavailable("Embeddings are disabled (embedding_enabled=False).")

    token = os.getenv("HF_TOKEN")
    if not token:
        raise _Unavailable("HF_TOKEN is not set. Add it to text-extractor/.env.")

    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise _Unavailable(f"huggingface_hub is not installed: {exc}") from exc

    return InferenceClient(
        provider=settings.embedding_provider,
        api_key=token,
        timeout=_TIMEOUT_SECONDS,
    )


def is_available() -> bool:
    """True when embeddings can actually be produced."""
    try:
        _client()
    except _Unavailable as exc:
        logger.debug("Embeddings unavailable: %s", exc)
        return False
    return True


def _normalise(matrix: np.ndarray) -> np.ndarray | None:
    """Coerce a provider response to (N, dim) unit-length float32 rows.

    `normalize=True` is passed to the API as well, but providers are free to
    ignore it and L2-normalising twice is harmless - so it is enforced here.
    Unit rows make cosine similarity a plain dot product.
    """
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix[np.newaxis, :]
    elif matrix.ndim == 3:
        # Token-level output (no pooling applied server-side): mean-pool it.
        matrix = matrix.mean(axis=1)
    if matrix.ndim != 2:
        logger.warning("Unexpected embedding shape %s - ignoring.", matrix.shape)
        return None

    expected = dimension()
    if matrix.shape[1] != expected:
        logger.warning(
            "Embedding dimension mismatch: model returned %d, config expects %d. "
            "Update settings.embedding_dim and re-run the backfill.",
            matrix.shape[1],
            expected,
        )
        return None

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    np.maximum(norms, 1e-12, out=norms)  # never divide by zero
    return matrix / norms


def _embed(texts: list[str]) -> np.ndarray | None:
    """One batched call to the provider. Returns (N, dim) or None on failure."""
    try:
        raw = _client().feature_extraction(
            texts,
            model=settings.embedding_model,
            normalize=True,
        )
    except _Unavailable as exc:
        logger.debug("Skipping embeddings: %s", exc)
        return None
    except Exception:
        logger.warning(
            "Embedding request failed for %d text(s) - retrieval falls back to "
            "keyword search.",
            len(texts),
            exc_info=True,
        )
        return None

    return _normalise(raw)


def embed_documents(texts: list[str]) -> list[np.ndarray] | None:
    """Embed chunk texts. Returns one vector per input, or None if unavailable.

    A partial failure returns None for the whole call rather than a ragged
    result: the caller stores NULL embeddings and the backfill script repairs
    them later.
    """
    if not texts:
        return []

    vectors: list[np.ndarray] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        matrix = _embed(batch)
        if matrix is None or len(matrix) != len(batch):
            if matrix is not None:
                logger.warning(
                    "Provider returned %d vectors for %d texts - discarding batch.",
                    len(matrix),
                    len(batch),
                )
            return None
        vectors.extend(matrix)

    logger.info("Embedded %d chunk(s) with %s.", len(vectors), settings.embedding_model)
    return vectors


@lru_cache(maxsize=256)
def _embed_query_cached(text: str) -> np.ndarray | None:
    matrix = _embed([_QUERY_PREFIX + text])
    if matrix is None or len(matrix) != 1:
        return None
    vector = matrix[0]
    vector.setflags(write=False)  # shared across callers via the cache
    return vector


def embed_query(text: str) -> np.ndarray | None:
    """Embed a question. Cached, so repeating a question skips the round-trip."""
    text = (text or "").strip()
    if not text:
        return None
    return _embed_query_cached(text)
