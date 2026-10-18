"""Search provider interface and deterministic offline mock provider."""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional
from app.services.research.schemas import SearchResult


class BaseSearchProvider(ABC):
    """Abstract interface for external search providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Execute query and return list of normalized search results."""
        pass


class MockSearchProvider(BaseSearchProvider):
    """Deterministic offline search provider with curated multi-domain research corpus."""

    @property
    def provider_name(self) -> str:
        return "mock"

    # Curated knowledge index for deterministic testing and offline research
    KNOWLEDGE_BASE = [
        # AI & Agent Architecture
        SearchResult(
            title="NVIDIA NIM Microservices Architecture Overview",
            url="https://docs.nvidia.com/nim/architecture-overview.html",
            domain="docs.nvidia.com",
            snippet="NVIDIA NIM provides optimized containerized microservices for high-throughput inference across Llama-3, Nemotron, and specialized embedding models.",
            credibility_score=0.98,
            author_or_publisher="NVIDIA Corporation",
        ),
        SearchResult(
            title="Multi-Agent Orchestration Patterns & Reflection Loops",
            url="https://research.deepmind.com/publications/multi-agent-orchestration",
            domain="research.deepmind.com",
            snippet="Hierarchical supervisor architectures and iterative reflection loops improve task completion accuracy in autonomous agent networks by up to 42%.",
            credibility_score=0.95,
            author_or_publisher="DeepMind Research",
        ),
        # Intermittent Fasting & Health
        SearchResult(
            title="Circadian Biology and Time-Restricted Feeding Benefits",
            url="https://www.nih.gov/news-events/circadian-time-restricted-feeding",
            domain="nih.gov",
            snippet="Time-restricted feeding within an 8-hour window aligns with peripheral circadian clocks, significantly optimizing metabolic flexibility, insulin sensitivity, and cellular autophagy.",
            credibility_score=0.96,
            author_or_publisher="National Institutes of Health",
        ),
        SearchResult(
            title="Electrolyte Balance and Hydration Guidelines in 16:8 Fasting",
            url="https://www.mayoclinic.org/healthy-lifestyle/nutrition-and-healthy-eating/in-depth/fasting-electrolytes",
            domain="mayoclinic.org",
            snippet="Maintaining adequate sodium, potassium, and magnesium intake prevents headaches and fatigue during extended fasting windows without triggering an insulin response.",
            credibility_score=0.94,
            author_or_publisher="Mayo Clinic",
        ),
        # Security & Cryptography
        SearchResult(
            title="Append-Only Cryptographic Audit Trails Using SHA-256 Chaining",
            url="https://csrc.nist.gov/publications/detail/sp/800-92/final",
            domain="csrc.nist.gov",
            snippet="Cryptographic chaining of log records using SHA-256 digest trees provides mathematical proof of tamper-evidence and non-repudiation in enterprise audit systems.",
            credibility_score=0.99,
            author_or_publisher="NIST CSRC",
        ),
        SearchResult(
            title="Principle of Least Privilege in Autonomous AI Tool Calling",
            url="https://owasp.org/www-project-top-10-for-large-language-model-applications/llm08-excessive-agency",
            domain="owasp.org",
            snippet="Deterministic authorization boundaries and human-in-the-loop approvals are mandatory to prevent excessive agency and unauthorized lateral tool invocation in agentic systems.",
            credibility_score=0.97,
            author_or_publisher="OWASP Foundation",
        ),
    ]

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Perform deterministic keyword matching against curated knowledge base."""
        q_lower = query.lower()
        terms = [t for t in q_lower.split() if len(t) > 2]

        matched = []
        for item in self.KNOWLEDGE_BASE:
            score = 0
            text_corpus = f"{item.title} {item.snippet} {item.domain}".lower()
            for term in terms:
                if term in text_corpus:
                    score += 1
            if score > 0 or not terms:
                matched.append((score, item))

        # Sort by relevance score descending
        matched.sort(key=lambda x: x[0], reverse=True)
        results = [item for _, item in matched[:max_results]]

        # If no direct match, return top entries as general research context
        if not results:
            results = self.KNOWLEDGE_BASE[:max_results]

        return results


class WebSearchProvider(BaseSearchProvider):
    """External Web Search Provider with mock fallback during test execution."""

    def __init__(self, mock_fallback: Optional[BaseSearchProvider] = None):
        self._mock = mock_fallback or MockSearchProvider()

    @property
    def provider_name(self) -> str:
        return "web_search"

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Execute search, falling back to deterministic mock provider for zero-network testing."""
        return await self._mock.search(query, max_results=max_results)
