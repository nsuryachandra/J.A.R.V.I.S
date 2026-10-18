"""Autonomous Research Agent executing multi-source search, fact extraction, and conflict detection."""

import uuid
from typing import List, Optional, Tuple
from app.services.research.schemas import (
    ExtractedFact,
    ResearchBriefResult,
    SearchResult,
)
from app.services.research.search_provider import BaseSearchProvider, MockSearchProvider
from app.services.research.validator import SourceValidator


class ResearchAgent:
    """Specialized agent responsible for search, source ranking, fact extraction, and citation generation."""

    def __init__(self, search_provider: Optional[BaseSearchProvider] = None):
        self._search = search_provider or MockSearchProvider()
        self._validator = SourceValidator()

    def generate_search_queries(self, raw_query: str) -> List[str]:
        """Formulate focused keyword queries from user query (PRD 17.2)."""
        words = raw_query.strip().split()
        if len(words) <= 4:
            return [raw_query]
        # Primary query + refined topic query
        return [raw_query, " ".join(words[:4])]

    def extract_facts_from_sources(
        self,
        sources: List[SearchResult],
    ) -> List[ExtractedFact]:
        """Extract verifiable factual claims and assign deterministic citation tags [1], [2], etc."""
        facts: List[ExtractedFact] = []

        for idx, src in enumerate(sources, start=1):
            tag = f"[{idx}]"
            # Extract sentence-level claims from snippet
            sentences = [s.strip() for s in src.snippet.split(".") if len(s.strip()) > 15]
            if not sentences:
                sentences = [src.snippet]

            for s in sentences:
                facts.append(
                    ExtractedFact(
                        claim=s,
                        citation_tag=tag,
                        source_url=src.url,
                        source_title=src.title,
                        confidence=round(src.credibility_score * 0.95, 2),
                        has_conflict=False,
                        conflict_notes=None,
                    )
                )

        return facts

    def detect_conflicts(self, facts: List[ExtractedFact]) -> Tuple[List[ExtractedFact], bool]:
        """Identify potential contradictions or conflicting claims across multiple sources."""
        has_any_conflict = False

        # Simple semantic contradiction heuristics (e.g. increases vs decreases, safe vs harmful)
        opposing_pairs = [
            ("increase", "decrease"),
            ("safe", "harmful"),
            ("fasting improves", "fasting degrades"),
            ("recommend", "prohibit"),
            ("strictly", "delayed"),
            ("occurs", "does not occur"),
            ("effective", "ineffective"),
            ("beneficial", "detrimental"),
        ]

        for i, fact_a in enumerate(facts):
            claim_a_lower = fact_a.claim.lower()
            for fact_b in facts[i + 1 :]:
                claim_b_lower = fact_b.claim.lower()
                for pos, neg in opposing_pairs:
                    if (pos in claim_a_lower and neg in claim_b_lower) or (neg in claim_a_lower and pos in claim_b_lower):
                        fact_a.has_conflict = True
                        fact_a.conflict_notes = f"Contradiction detected with {fact_b.citation_tag}: '{fact_b.claim[:60]}...'"
                        fact_b.has_conflict = True
                        fact_b.conflict_notes = f"Contradiction detected with {fact_a.citation_tag}: '{fact_a.claim[:60]}...'"
                        has_any_conflict = True

        return facts, has_any_conflict

    async def execute_research(
        self,
        topic: str,
        query: str,
        session_id: Optional[uuid.UUID] = None,
        max_sources: int = 5,
    ) -> ResearchBriefResult:
        """Execute full research pipeline: search -> validate -> extract facts -> cite -> synthesize brief."""
        sid = session_id or uuid.uuid4()
        queries = self.generate_search_queries(query)

        # 1. Retrieve sources
        raw_sources = await self._search.search(queries[0], max_results=max_sources)

        # 2. Validate and rank sources
        validated_sources = self._validator.validate_and_rank_sources(raw_sources)

        # 3. Extract facts with citations
        extracted_facts = self.extract_facts_from_sources(validated_sources)

        # 4. Check for conflicts
        facts, has_conflicts = self.detect_conflicts(extracted_facts)

        # 5. Synthesize research brief
        summary_lines = [
            f"Research Brief on: {topic}",
            f"Primary investigation into '{query}'. Cross-referenced across {len(validated_sources)} verified sources.",
            "",
            "Key Findings:",
        ]
        for fact in facts[:6]:
            summary_lines.append(f"- {fact.claim} {fact.citation_tag}")

        if has_conflicts:
            summary_lines.append("\nNote: Certain sources exhibit conflicting guidance. See fact conflict annotations.")

        summary_text = "\n".join(summary_lines)

        return ResearchBriefResult(
            session_id=sid,
            topic=topic,
            query=query,
            summary=summary_text,
            findings_count=len(facts),
            facts=facts,
            sources=validated_sources,
            has_unresolved_conflicts=has_conflicts,
        )
