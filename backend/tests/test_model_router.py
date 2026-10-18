"""Unit tests for ModelRouter, provider fallback abstraction, structured output, and token usage tracking."""

import uuid
import pytest
from app.core.config import get_settings
from app.models.model_usage import ModelUsageRecord
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.router import ModelRouter
from app.services.llm.schemas import (
    DateInterpretationResult,
    IntentClassificationResult,
    LLMMessage,
    ModelRole,
    PlanGenerationResult,
)


def test_model_role_resolution():
    """Verify mapping of logical model roles to configuration-driven model IDs (PRD 9.3)."""
    settings = get_settings()
    router = ModelRouter()

    assert router.resolve_model_for_role(ModelRole.FAST_CHAT) == settings.model_fast_chat
    assert router.resolve_model_for_role(ModelRole.REASONING) == settings.model_reasoning
    assert router.resolve_model_for_role(ModelRole.CODING) == settings.model_coding
    assert router.resolve_model_for_role(ModelRole.VISION) == settings.model_vision
    assert router.resolve_model_for_role(ModelRole.EMBEDDING) == settings.model_embedding


def test_heuristic_intent_classification():
    """Verify task-to-model role classification rules (PRD 9.4)."""
    router = ModelRouter()

    # Coding
    assert router.classify_intent_role("Can you write a python function to parse dates?") == ModelRole.CODING
    assert router.classify_intent_role("Fix the bug in this algorithm class") == ModelRole.CODING

    # Reasoning
    assert router.classify_intent_role("Analyze the architectural tradeoffs and plan the migration") == ModelRole.REASONING
    assert router.classify_intent_role("Evaluate the strategic options and explain why") == ModelRole.REASONING

    # Vision
    assert router.classify_intent_role("Inspect this screenshot diagram") == ModelRole.VISION
    assert router.classify_intent_role("What is in this camera photo?") == ModelRole.VISION

    # Fast Chat
    assert router.classify_intent_role("Good morning! How are you doing today?") == ModelRole.FAST_CHAT
    assert router.classify_intent_role("Thank you, that was helpful.") == ModelRole.FAST_CHAT


@pytest.mark.asyncio
async def test_mock_provider_chat_generation():
    """Verify deterministic mock provider text generation and token usage tracking."""
    provider = MockLLMProvider()
    messages = [LLMMessage(role="user", content="Hello, JARVIS")]

    resp = await provider.generate(model="meta/llama-3.1-8b-instruct", messages=messages)
    assert resp.content is not None
    assert "sir" in resp.content.lower() or "hello" in resp.content.lower()
    assert resp.provider == "mock"
    assert resp.usage.total_tokens > 0
    assert resp.latency_ms >= 0.0
    assert resp.request_id is not None


@pytest.mark.asyncio
async def test_mock_provider_structured_output():
    """Verify schema-enforced structured outputs (PRD 9.6)."""
    provider = MockLLMProvider()

    # 1. Intent classification
    res_intent = await provider.generate_structured(
        model="meta/llama-3.1-8b-instruct",
        messages=[LLMMessage(role="user", content="Did I complete my fasting routine today?")],
        schema=IntentClassificationResult,
    )
    assert isinstance(res_intent.parsed, IntentClassificationResult)
    assert res_intent.parsed.intent == "HABIT_INQUIRY"
    assert res_intent.parsed.requires_tools is True
    assert res_intent.parsed.confidence >= 0.9

    # 2. Plan generation
    res_plan = await provider.generate_structured(
        model="meta/llama-3.1-70b-instruct",
        messages=[LLMMessage(role="user", content="Plan migration to PostgreSQL")],
        schema=PlanGenerationResult,
    )
    assert isinstance(res_plan.parsed, PlanGenerationResult)
    assert len(res_plan.parsed.steps) >= 3
    assert res_plan.parsed.estimated_risk == "SAFE"

    # 3. Date interpretation
    res_date = await provider.generate_structured(
        model="meta/llama-3.1-8b-instruct",
        messages=[LLMMessage(role="user", content="Tomorrow at 2 PM")],
        schema=DateInterpretationResult,
    )
    assert isinstance(res_date.parsed, DateInterpretationResult)
    assert res_date.parsed.timezone == "Asia/Kolkata"
    assert res_date.parsed.is_ambiguous is False


@pytest.mark.asyncio
async def test_mock_provider_embeddings():
    """Verify deterministic unit vector embedding generation."""
    provider = MockLLMProvider()

    emb1 = await provider.get_embedding("Deep learning architecture")
    emb2 = await provider.get_embedding("Deep learning architecture")
    emb3 = await provider.get_embedding("Completely unrelated topic")

    assert len(emb1) == 384
    # Determinism
    assert emb1 == emb2
    # Sensitivity
    assert emb1 != emb3
    # Unit length (norm ≈ 1.0)
    norm = sum(x * x for x in emb1) ** 0.5
    assert abs(norm - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_router_generate_and_usage_tracking(db_session):
    """Verify ModelRouter generation, database token usage logging, and audit tracking."""
    router = ModelRouter()
    uid = uuid.uuid4()
    messages = [LLMMessage(role="user", content="Write a python function to compute fibonacci")]

    resp = await router.generate(
        db=db_session,
        user_id=uid,
        messages=messages,
        role=ModelRole.CODING,
    )
    assert resp.content is not None
    assert resp.usage.total_tokens > 0

    # Verify usage record in DB
    metrics = await ModelRouter.get_user_usage_metrics(db_session, uid)
    assert metrics["total_calls"] == 1
    assert metrics["total_tokens"] > 0
    assert metrics["prompt_tokens"] > 0
    assert metrics["completion_tokens"] > 0


@pytest.mark.asyncio
async def test_user_usage_metrics_isolation(db_session):
    """Verify cross-user isolation in model usage and token metrics."""
    router = ModelRouter()
    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()

    # User A makes 2 calls
    await router.generate(db_session, uid_a, [LLMMessage(role="user", content="Hi")])
    await router.generate(db_session, uid_a, [LLMMessage(role="user", content="Hello again")])

    # User B makes 1 call
    await router.generate(db_session, uid_b, [LLMMessage(role="user", content="Greetings")])

    metrics_a = await ModelRouter.get_user_usage_metrics(db_session, uid_a)
    metrics_b = await ModelRouter.get_user_usage_metrics(db_session, uid_b)

    assert metrics_a["total_calls"] == 2
    assert metrics_b["total_calls"] == 1
    assert metrics_a["total_tokens"] > metrics_b["total_tokens"]
