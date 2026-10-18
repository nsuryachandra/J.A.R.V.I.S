"""Domain orchestration service for Research and Writing Agents with database persistence and audit trails."""

import uuid
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.research import (
    DocumentArtifact,
    ResearchFact,
    ResearchSession,
    ResearchSource,
)
from app.services.audit_service import AuditService
from app.services.research.research_agent import ResearchAgent
from app.services.research.schemas import (
    DocumentExportResponse,
    DocumentResponse,
    DraftDocumentRequest,
    ExtractedFact,
    ResearchBriefResult,
    ResearchSessionSummary,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
)
from app.services.research.search_provider import BaseSearchProvider, MockSearchProvider
from app.services.research.writing_agent import WritingAgent


class ResearchService:
    """High-level service coordinating multi-source research investigations and document generation."""

    def __init__(self, search_provider: Optional[BaseSearchProvider] = None):
        self._search = search_provider or MockSearchProvider()
        self._research_agent = ResearchAgent(search_provider=self._search)
        self._writing_agent = WritingAgent()

    async def search_sources(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: WebSearchRequest,
        session_id: Optional[uuid.UUID] = None,
    ) -> WebSearchResponse:
        """Search approved sources with quality ranking and audit logging."""
        results = await self._search.search(request.query, max_results=request.max_results)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id,
            action_type="research.search",
            resource_scope="research:web",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "query": request.query[:80],
                "results_count": len(results),
            },
        )
        await db.commit()

        return WebSearchResponse(
            query=request.query,
            total_results=len(results),
            results=results,
        )

    async def execute_research(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        topic: str,
        query: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> ResearchBriefResult:
        """Execute full research pipeline, store session/sources/facts, and log audit."""
        brief = await self._research_agent.execute_research(
            topic=topic,
            query=query,
            session_id=session_id,
        )

        # Persist session
        session_rec = ResearchSession(
            id=brief.session_id,
            user_id=user_id,
            topic=topic,
            query=query,
            status="COMPLETED",
            findings_count=brief.findings_count,
            summary=brief.summary,
        )
        db.add(session_rec)
        await db.flush()

        # Persist sources
        src_map = {}
        for src in brief.sources:
            s_rec = ResearchSource(
                session_id=session_rec.id,
                title=src.title,
                url=src.url,
                domain=src.domain,
                snippet=src.snippet,
                credibility_score=src.credibility_score,
                author_or_publisher=src.author_or_publisher,
            )
            db.add(s_rec)
            await db.flush()
            src_map[src.url] = s_rec.id

        # Persist facts
        for fact in brief.facts:
            f_rec = ResearchFact(
                session_id=session_rec.id,
                source_id=src_map.get(fact.source_url),
                claim=fact.claim,
                citation_tag=fact.citation_tag,
                confidence=fact.confidence,
                has_conflict=fact.has_conflict,
                conflict_notes=fact.conflict_notes,
            )
            db.add(f_rec)

        await db.commit()

        # Emit audit trail
        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id,
            action_type="research.execute",
            resource_scope=f"research_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "topic": topic,
                "sources_count": len(brief.sources),
                "facts_count": len(brief.facts),
                "has_conflicts": brief.has_unresolved_conflicts,
            },
        )
        await db.commit()

        return brief

    async def list_user_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[ResearchSessionSummary]:
        """List user's historical research sessions enforcing tenant isolation."""
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.user_id == user_id)
            .order_by(desc(ResearchSession.created_at))
        )
        result = await db.execute(stmt)
        return [
            ResearchSessionSummary(
                id=s.id,
                user_id=s.user_id,
                topic=s.topic,
                query=s.query,
                status=s.status,
                findings_count=s.findings_count,
                summary=s.summary,
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in result.scalars().all()
        ]

    async def get_session_details(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> Optional[ResearchBriefResult]:
        """Fetch complete research session with linked sources and facts."""
        stmt = (
            select(ResearchSession)
            .where(ResearchSession.id == session_id, ResearchSession.user_id == user_id)
            .options(
                selectinload(ResearchSession.sources),
                selectinload(ResearchSession.facts).selectinload(ResearchFact.source),
            )
        )
        result = await db.execute(stmt)
        session_rec = result.scalar_one_or_none()

        if not session_rec:
            return None

        sources = [
            SearchResult(
                title=s.title,
                url=s.url,
                domain=s.domain,
                snippet=s.snippet,
                credibility_score=s.credibility_score,
                author_or_publisher=s.author_or_publisher,
            )
            for s in session_rec.sources
        ]

        facts = [
            ExtractedFact(
                claim=f.claim,
                citation_tag=f.citation_tag,
                source_url=f.source.url if f.source else "",
                source_title=f.source.title if f.source else "Internal Knowledge",
                confidence=f.confidence,
                has_conflict=f.has_conflict,
                conflict_notes=f.conflict_notes,
            )
            for f in session_rec.facts
        ]

        has_conflicts = any(f.has_conflict for f in facts)

        return ResearchBriefResult(
            session_id=session_rec.id,
            topic=session_rec.topic,
            query=session_rec.query,
            summary=session_rec.summary or "",
            findings_count=session_rec.findings_count,
            facts=facts,
            sources=sources,
            has_unresolved_conflicts=has_conflicts,
        )

    async def draft_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: DraftDocumentRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> DocumentResponse:
        """Draft a structured document grounded in research findings and persist artifact."""
        facts: List[ExtractedFact] = []
        sources: List[SearchResult] = []

        if request.session_id:
            brief = await self.get_session_details(db, user_id, request.session_id)
            if brief:
                facts = brief.facts
                sources = brief.sources

        markdown_content = self._writing_agent.draft_document(
            title=request.title,
            doc_type=request.doc_type,
            instructions=request.instructions,
            facts=facts,
            sources=sources,
        )

        word_count = len(markdown_content.split())
        citations_count = len(sources)

        doc = DocumentArtifact(
            user_id=user_id,
            session_id=request.session_id,
            title=request.title,
            doc_type=request.doc_type.upper(),
            format=request.format.upper(),
            content_markdown=markdown_content,
            word_count=word_count,
            citations_count=citations_count,
            metadata_json={"audience": request.instructions},
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Audit
        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="document.draft",
            resource_scope=f"document:{doc.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "title": doc.title,
                "doc_type": doc.doc_type,
                "word_count": doc.word_count,
                "citations_count": doc.citations_count,
            },
        )
        await db.commit()

        return DocumentResponse(
            id=doc.id,
            user_id=doc.user_id,
            session_id=doc.session_id,
            title=doc.title,
            doc_type=doc.doc_type,
            format=doc.format,
            content_markdown=doc.content_markdown,
            word_count=doc.word_count,
            citations_count=doc.citations_count,
            created_at=doc.created_at.isoformat(),
        )

    async def list_user_documents(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[DocumentResponse]:
        """List all generated documents for the user."""
        stmt = (
            select(DocumentArtifact)
            .where(DocumentArtifact.user_id == user_id)
            .order_by(desc(DocumentArtifact.created_at))
        )
        result = await db.execute(stmt)
        docs = result.scalars().all()
        return [
            DocumentResponse(
                id=d.id,
                user_id=d.user_id,
                session_id=d.session_id,
                title=d.title,
                doc_type=d.doc_type,
                format=d.format,
                content_markdown=d.content_markdown,
                word_count=d.word_count,
                citations_count=d.citations_count,
                created_at=d.created_at.isoformat(),
            )
            for d in docs
        ]

    async def get_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Optional[DocumentResponse]:
        """Retrieve specific document artifact ensuring user isolation."""
        stmt = select(DocumentArtifact).where(
            DocumentArtifact.id == document_id,
            DocumentArtifact.user_id == user_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            return None

        return DocumentResponse(
            id=doc.id,
            user_id=doc.user_id,
            session_id=doc.session_id,
            title=doc.title,
            doc_type=doc.doc_type,
            format=doc.format,
            content_markdown=doc.content_markdown,
            word_count=doc.word_count,
            citations_count=doc.citations_count,
            created_at=doc.created_at.isoformat(),
        )

    async def export_document(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        export_format: str = "html",
    ) -> Optional[DocumentExportResponse]:
        """Export document into HTML or plain text."""
        doc = await self.get_document(db, user_id, document_id)
        if not doc:
            return None

        fmt = export_format.lower()
        if fmt == "html":
            exported = self._writing_agent.export_as_html(doc.title, doc.content_markdown)
            content_type = "text/html"
        else:
            exported = doc.content_markdown
            content_type = "text/markdown"

        return DocumentExportResponse(
            document_id=doc.id,
            title=doc.title,
            format=fmt.upper(),
            content_type=content_type,
            exported_content=exported,
        )
