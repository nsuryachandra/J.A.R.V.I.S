"""Intelligent Model Router: task-to-model mapping, provider fallbacks, and token observability."""

import uuid
from typing import Any, Dict, List, Optional, Type, TypeVar
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.model_usage import ModelUsageRecord
from app.services.audit_service import AuditService
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.nvidia_provider import NvidiaNIMProvider
from app.services.llm.schemas import (
    LLMMessage,
    LLMResponse,
    ModelRole,
    StructuredLLMResponse,
)

T = TypeVar("T")


class ModelRouter:
    """Routes inference requests across model roles, handles graceful fallbacks, and tracks usage."""

    def __init__(
        self,
        primary_provider: Optional[BaseLLMProvider] = None,
        fallback_provider: Optional[BaseLLMProvider] = None,
    ):
        settings = get_settings()
        self._nvidia = primary_provider or NvidiaNIMProvider()
        self._mock = fallback_provider or MockLLMProvider()

    def resolve_model_for_role(self, role: ModelRole | str) -> str:
        """Resolve logical model role to configured provider model string."""
        settings = get_settings()
        role_str = role.value if isinstance(role, ModelRole) else str(role).lower()

        if role_str == ModelRole.FAST_CHAT.value:
            return settings.model_fast_chat
        elif role_str == ModelRole.REASONING.value:
            return settings.model_reasoning
        elif role_str == ModelRole.CODING.value:
            return settings.model_coding
        elif role_str == ModelRole.VISION.value:
            return settings.model_vision
        elif role_str == ModelRole.EMBEDDING.value:
            return settings.model_embedding
        elif role_str in (ModelRole.CLASSIFICATION.value, ModelRole.SUMMARIZATION.value):
            return settings.model_fast_chat
        return settings.model_fast_chat

    def resolve_fallback_model(self, model: str) -> Optional[str]:
        """Resolve secondary model fallback if primary model is unavailable."""
        settings = get_settings()
        if model == settings.model_reasoning:
            return settings.model_fast_chat
        if model == settings.model_coding:
            return settings.model_fast_chat
        return None

    def classify_intent_role(self, query: str) -> ModelRole:
        """Heuristic task classification routing queries to appropriate model roles (PRD 9.4)."""
        lower = query.lower()

        # Coding indicators
        if any(term in lower for term in ["def ", "class ", "function", "import ", "sql", "bug", "code", "refactor", "algorithm"]):
            return ModelRole.CODING

        # Deep reasoning / multi-step planning indicators
        if any(term in lower for term in ["plan", "strategy", "architecture", "tradeoff", "why", "analyze", "evaluate", "compare"]):
            return ModelRole.REASONING

        # Vision indicators
        if any(term in lower for term in ["image", "screenshot", "photo", "picture", "diagram", "camera"]):
            return ModelRole.VISION

        # Default conversational interaction
        return ModelRole.FAST_CHAT

    def get_active_provider(self) -> BaseLLMProvider:
        """Select primary live provider or offline mock provider."""
        settings = get_settings()
        if self._nvidia.is_configured and not settings.is_testing:
            return self._nvidia
        return self._mock

    async def generate(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        messages: List[LLMMessage],
        role: Optional[ModelRole | str] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Execute completion with automatic role routing, provider fallbacks, and usage recording.
        """
        # Determine logical role
        last_text = messages[-1].content if messages else ""
        resolved_role = role or self.classify_intent_role(last_text)
        model_id = self.resolve_model_for_role(resolved_role)

        provider = self.get_active_provider()
        status = "SUCCESS"
        error_msg = None

        try:
            resp = await provider.generate(model=model_id, messages=messages, **kwargs)
        except Exception as exc:
            # Try fallback model if available
            fallback_model = self.resolve_fallback_model(model_id)
            if fallback_model and provider is not self._mock:
                try:
                    resp = await provider.generate(model=fallback_model, messages=messages, **kwargs)
                    status = "FALLBACK"
                except Exception:
                    # Fallback to mock provider
                    resp = await self._mock.generate(model=model_id, messages=messages, **kwargs)
                    status = "FALLBACK"
            else:
                resp = await self._mock.generate(model=model_id, messages=messages, **kwargs)
                status = "FALLBACK"
            error_msg = str(exc)

        # Record usage in database
        usage_record = ModelUsageRecord(
            user_id=user_id,
            session_id=session_id,
            provider=resp.provider,
            model_role=resolved_role.value if isinstance(resolved_role, ModelRole) else str(resolved_role),
            model_id=resp.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            latency_ms=resp.latency_ms,
            request_id=resp.request_id,
            status=status,
            error_message=error_msg,
        )
        db.add(usage_record)
        await db.commit()

        # Record audit log entry
        await AuditService.record_event(
            session=db,
            action_type="model.inference",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"model:{resp.model}",
            details={
                "provider": resp.provider,
                "role": resolved_role.value if isinstance(resolved_role, ModelRole) else str(resolved_role),
                "total_tokens": resp.usage.total_tokens,
                "latency_ms": resp.latency_ms,
                "status": status,
            },
        )
        await db.commit()
        return resp

    async def generate_structured(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        messages: List[LLMMessage],
        schema: Type[T],
        role: Optional[ModelRole | str] = None,
        session_id: Optional[uuid.UUID] = None,
        correlation_id: Optional[uuid.UUID] = None,
        **kwargs: Any,
    ) -> StructuredLLMResponse[T]:
        """
        Execute structured JSON completion adhering strictly to target Pydantic schema.
        """
        last_text = messages[-1].content if messages else ""
        resolved_role = role or self.classify_intent_role(last_text)
        model_id = self.resolve_model_for_role(resolved_role)

        provider = self.get_active_provider()
        status = "SUCCESS"
        error_msg = None

        try:
            resp = await provider.generate_structured(model=model_id, messages=messages, schema=schema, **kwargs)
        except Exception as exc:
            resp = await self._mock.generate_structured(model=model_id, messages=messages, schema=schema, **kwargs)
            status = "FALLBACK"
            error_msg = str(exc)

        # Record usage
        usage_record = ModelUsageRecord(
            user_id=user_id,
            session_id=session_id,
            provider=resp.provider,
            model_role=resolved_role.value if isinstance(resolved_role, ModelRole) else str(resolved_role),
            model_id=resp.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            latency_ms=resp.latency_ms,
            status=status,
            error_message=error_msg,
        )
        db.add(usage_record)
        await db.commit()

        await AuditService.record_event(
            session=db,
            action_type="model.inference_structured",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
            resource_scope=f"model:{resp.model}",
            details={
                "provider": resp.provider,
                "schema": schema.__name__,
                "total_tokens": resp.usage.total_tokens,
                "latency_ms": resp.latency_ms,
            },
        )
        await db.commit()
        return resp

    @classmethod
    async def get_user_usage_metrics(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Aggregate total token usage and latency metrics for authenticated user."""
        stmt = (
            select(
                func.sum(ModelUsageRecord.prompt_tokens).label("prompt_tokens"),
                func.sum(ModelUsageRecord.completion_tokens).label("completion_tokens"),
                func.sum(ModelUsageRecord.total_tokens).label("total_tokens"),
                func.avg(ModelUsageRecord.latency_ms).label("avg_latency_ms"),
                func.count(ModelUsageRecord.id).label("total_calls"),
            )
            .where(ModelUsageRecord.user_id == user_id)
        )
        res = await db.execute(stmt)
        row = res.one()

        return {
            "total_calls": row.total_calls or 0,
            "prompt_tokens": row.prompt_tokens or 0,
            "completion_tokens": row.completion_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "avg_latency_ms": round(row.avg_latency_ms or 0.0, 2),
        }
