from __future__ import annotations

import hashlib
import math
from typing import List

from core.contracts import EmbeddingProvider

# Adapted from RAG-Engineering-Lab/src/embeddings/mock_embedding_provider.py
# (see BANKING_PLATFORM_INTEGRATION_PLAN.md §3: "Reuse as-is"). Deterministic,
# offline, no API key and no model download required — this is the platform's
# default embedding provider (core.config.Settings.embedding_provider="local"
# resolves to this class until a real local model provider is added in
# Phase 2). Same input text always produces the same vector.

_DIMENSION = 128

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, dependency-free embedding provider for local/offline use."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [_text_to_vector(t) for t in texts]

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def dimension(self) -> int:
        return _DIMENSION


def _text_to_vector(text: str) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:4], byteorder="big")
    if _HAS_NUMPY:
        return _numpy_vector(seed)
    return _stdlib_vector(digest)


def _numpy_vector(seed: int) -> List[float]:
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(_DIMENSION)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def _stdlib_vector(digest: bytes) -> List[float]:
    raw = hashlib.shake_128(digest).digest(4 * _DIMENSION)
    values: List[float] = []
    for i in range(0, 4 * _DIMENSION, 4):
        n = int.from_bytes(raw[i : i + 4], byteorder="big", signed=True)
        values.append(n / 2_147_483_648.0)
    norm = math.sqrt(sum(x * x for x in values))
    return [x / norm for x in values] if norm > 0 else values
