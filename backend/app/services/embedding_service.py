"""Deterministic vector embedding provider and similarity calculation for semantic search."""

import abc
import hashlib
import math
import re
from typing import List


class EmbeddingProvider(abc.ABC):
    """Abstract interface for text embedding generation."""

    @abc.abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Convert input text into normalized floating point vector."""
        pass


class DeterministicLocalEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic, offline embedding generator using token feature hashing and L2 normalization.
    Ensures zero external network dependencies and identical outputs across executions.
    """

    def __init__(self, dimension: int = 64):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        """Generate a unit-normalized vector of specified dimensions."""
        vec = [0.0] * self.dimension
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            vec[0] = 1.0
            return vec

        for tok in tokens:
            # Deterministic SHA-256 token hash to feature index
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vec[idx] += 1.0

        # Compute Euclidean L2 norm
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            return [float(x / norm) for x in vec]
        vec[0] = 1.0
        return vec


_default_embedding_provider = DeterministicLocalEmbeddingProvider()


def get_embedding_provider() -> EmbeddingProvider:
    """Return default embedding provider instance."""
    return _default_embedding_provider


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two normalized float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    # Bound to [-1.0, 1.0] to protect against slight float rounding
    return float(max(-1.0, min(1.0, dot)))
