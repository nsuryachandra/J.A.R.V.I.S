"""REST API endpoints for Model Routing, completions, structured inference, and token usage."""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.config import get_settings
from app.core.database import get_db_session
from app.models.user import User
from app.services.llm.router import ModelRouter
from app.services.llm.schemas import (
    IntentClassificationResult,
    LLMMessage,
    LLMResponse,
    ModelRole,
    PlanGenerationResult,
)

router = APIRouter(prefix="/models", tags=["Model Strategy & Inference"])
_model_router = ModelRouter()


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class ChatCompletionRequest(BaseModel):
    messages: List[LLMMessage]
    role: Optional[str] = Field(default=None, description="fast_chat, reasoning, coding, vision")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=4096)


class ChatCompletionResponse(BaseModel):
    content: str
    role: str
    model: str
    provider: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    request_id: Optional[str] = None


class StructuredIntentRequest(BaseModel):
    query: str = Field(min_length=1)


class StructuredPlanRequest(BaseModel):
    goal: str = Field(min_length=1)


class ModelRoutesResponse(BaseModel):
    active_provider: str
    is_live_configured: bool
    routes: Dict[str, str]


class ModelUsageResponse(BaseModel):
    user_id: uuid.UUID
    total_calls: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: float


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/routes", response_model=ModelRoutesResponse)
async def get_model_routes(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
) -> ModelRoutesResponse:
    """Return logical model role mappings and active provider status."""
    settings = get_settings()
    active_provider = _model_router.get_active_provider()
    routes = {
        role.value: _model_router.resolve_model_for_role(role)
        for role in ModelRole
    }
    return ModelRoutesResponse(
        active_provider=active_provider.provider_name,
        is_live_configured=_model_router._nvidia.is_configured,
        routes=routes,
    )


@router.post("/chat", response_model=ChatCompletionResponse)
async def create_chat_completion(
    payload: ChatCompletionRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ChatCompletionResponse:
    """Execute chat completion with automatic model routing and token usage logging."""
    current_user, session_id = auth
    resp: LLMResponse = await _model_router.generate(
        db=db,
        user_id=current_user.id,
        messages=payload.messages,
        role=payload.role,
        session_id=session_id,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    return ChatCompletionResponse(
        content=resp.content,
        role=resp.role,
        model=resp.model,
        provider=resp.provider,
        total_tokens=resp.usage.total_tokens,
        prompt_tokens=resp.usage.prompt_tokens,
        completion_tokens=resp.usage.completion_tokens,
        latency_ms=resp.latency_ms,
        request_id=resp.request_id,
    )


@router.post("/structured/intent", response_model=IntentClassificationResult)
async def classify_intent_structured(
    payload: StructuredIntentRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> IntentClassificationResult:
    """Classify user query intent into structured Pydantic schema."""
    current_user, session_id = auth
    messages = [LLMMessage(role="user", content=payload.query)]
    res = await _model_router.generate_structured(
        db=db,
        user_id=current_user.id,
        messages=messages,
        schema=IntentClassificationResult,
        role=ModelRole.CLASSIFICATION,
        session_id=session_id,
    )
    return res.parsed


@router.post("/structured/plan", response_model=PlanGenerationResult)
async def generate_plan_structured(
    payload: StructuredPlanRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> PlanGenerationResult:
    """Generate multi-step plan adhering to structured schema."""
    current_user, session_id = auth
    messages = [LLMMessage(role="user", content=f"Generate a clear plan for: {payload.goal}")]
    res = await _model_router.generate_structured(
        db=db,
        user_id=current_user.id,
        messages=messages,
        schema=PlanGenerationResult,
        role=ModelRole.REASONING,
        session_id=session_id,
    )
    return res.parsed


@router.get("/usage", response_model=ModelUsageResponse)
async def get_model_usage(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ModelUsageResponse:
    """Retrieve aggregated model token metrics and latency for current user."""
    current_user, _ = auth
    metrics = await ModelRouter.get_user_usage_metrics(db, current_user.id)
    return ModelUsageResponse(
        user_id=current_user.id,
        total_calls=metrics["total_calls"],
        total_tokens=metrics["total_tokens"],
        prompt_tokens=metrics["prompt_tokens"],
        completion_tokens=metrics["completion_tokens"],
        avg_latency_ms=metrics["avg_latency_ms"],
    )
