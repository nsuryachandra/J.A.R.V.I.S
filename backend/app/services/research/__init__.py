"""Research and Writing Agents package for JARVIS."""

from app.services.research.research_agent import ResearchAgent
from app.services.research.schemas import (
    DocumentExportResponse,
    DocumentResponse,
    DraftDocumentRequest,
    ExtractedFact,
    ResearchBriefResult,
    ResearchExecutionRequest,
    ResearchSessionSummary,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
)
from app.services.research.search_provider import (
    BaseSearchProvider,
    MockSearchProvider,
    WebSearchProvider,
)
from app.services.research.service import ResearchService
from app.services.research.validator import SourceValidator
from app.services.research.writing_agent import WritingAgent

__all__ = [
    "BaseSearchProvider",
    "MockSearchProvider",
    "WebSearchProvider",
    "SourceValidator",
    "ResearchAgent",
    "WritingAgent",
    "ResearchService",
    "SearchResult",
    "WebSearchRequest",
    "WebSearchResponse",
    "ExtractedFact",
    "ResearchExecutionRequest",
    "ResearchSessionSummary",
    "ResearchBriefResult",
    "DraftDocumentRequest",
    "DocumentResponse",
    "DocumentExportResponse",
]
