"""Deterministic, offline mock LLM provider for tests and zero-network local development."""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel
from app.services.llm.base import BaseLLMProvider
from app.services.llm.schemas import (
    DateInterpretationResult,
    IntentClassificationResult,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    PlanGenerationResult,
    StructuredLLMResponse,
)

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, offline mock LLM provider simulating chat, structured schemas, and embeddings."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(
        self,
        model: str,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate deterministic text completion based on prompt contents."""
        start_time = time.perf_counter()
        last_msg = messages[-1].content if messages else ""
        lower_prompt = last_msg.lower()

        if "hello" in lower_prompt or "hi" in lower_prompt or "hey" in lower_prompt:
            reply = "Hello, sir. How may I assist you today?"
        elif "fast" in lower_prompt or "habit" in lower_prompt:
            reply = "I have checked your schedule. Your fasting routine is active and up to date."
        elif "code" in lower_prompt or "python" in lower_prompt or "function" in lower_prompt:
            reply = "```python\ndef solution():\n    return 'Deterministic code generated.'\n```"
        elif "plan" in lower_prompt or "goal" in lower_prompt:
            reply = "Here is the recommended 3-step plan:\n1. Analyze requirements\n2. Execute core logic\n3. Verify results"
        else:
            reply = f"Acknowledged: {last_msg}"

        prompt_tokens = sum(len(m.content.split()) for m in messages) * 2
        completion_tokens = len(reply.split()) * 2
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return LLMResponse(
            content=reply,
            role="assistant",
            model=model,
            provider="mock",
            usage=LLMUsage(
                prompt_tokens=max(1, prompt_tokens),
                completion_tokens=max(1, completion_tokens),
                total_tokens=max(2, prompt_tokens + completion_tokens),
            ),
            latency_ms=round(latency_ms, 2),
            request_id=f"mock-req-{hashlib.md5(last_msg.encode()).hexdigest()[:8]}",
        )

    async def generate_structured(
        self,
        model: str,
        messages: List[LLMMessage],
        schema: Type[T],
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> StructuredLLMResponse[T]:
        """Generate structured response strictly adhering to target Pydantic schema."""
        start_time = time.perf_counter()
        last_msg = messages[-1].content if messages else ""
        lower = last_msg.lower()

        data: Dict[str, Any] = {}

        if schema is IntentClassificationResult:
            if any(k in lower for k in ["fast", "routine", "habit", "workout"]):
                data = {
                    "intent": "HABIT_INQUIRY",
                    "confidence": 0.96,
                    "entities": {"habit": "fasting" if "fast" in lower else "routine"},
                    "requires_tools": True,
                    "risk_level": "SAFE",
                }
            elif any(k in lower for k in ["task", "project", "deadline", "todo"]):
                data = {
                    "intent": "TASK_QUERY",
                    "confidence": 0.94,
                    "entities": {"topic": "tasks"},
                    "requires_tools": True,
                    "risk_level": "SAFE",
                }
            elif any(k in lower for k in ["hello", "hi", "hey", "morning", "evening"]):
                data = {
                    "intent": "GREETING",
                    "confidence": 0.99,
                    "entities": {},
                    "requires_tools": False,
                    "risk_level": "SAFE",
                }
            else:
                data = {
                    "intent": "GENERAL_INQUIRY",
                    "confidence": 0.88,
                    "entities": {},
                    "requires_tools": False,
                    "risk_level": "SAFE",
                }
        elif schema is PlanGenerationResult:
            data = {
                "goal": last_msg or "Execute user goal",
                "steps": [
                    "Step 1: Inspect environment and available context",
                    "Step 2: Execute designated domain tools",
                    "Step 3: Verify outputs and synthesize final response",
                ],
                "estimated_risk": "SAFE",
                "required_tools": ["tasks.read", "memory.search"],
            }
        elif schema is DateInterpretationResult:
            data = {
                "raw_expression": last_msg,
                "resolved_iso": "2026-10-19T14:00:00+05:30",
                "timezone": "Asia/Kolkata",
                "is_ambiguous": False,
                "clarification_needed": None,
            }
        else:
            # Fallback: construct instance from schema fields with appropriate defaults
            for field_name, field_info in schema.model_fields.items():
                annotation = field_info.annotation
                if annotation is str or annotation == str:
                    data[field_name] = f"mock_{field_name}"
                elif annotation is int or annotation == int:
                    data[field_name] = 1
                elif annotation is float or annotation == float:
                    data[field_name] = 1.0
                elif annotation is bool or annotation == bool:
                    data[field_name] = True
                elif hasattr(annotation, "__origin__") and annotation.__origin__ is list:
                    data[field_name] = ["mock_item"]
                elif hasattr(annotation, "__origin__") and annotation.__origin__ is dict:
                    data[field_name] = {"mock_key": "mock_val"}
                else:
                    data[field_name] = field_info.default if field_info.default is not None else "mock_data"

        parsed = schema(**data)
        raw_json = json.dumps(data)

        prompt_tokens = sum(len(m.content.split()) for m in messages) * 2
        completion_tokens = len(raw_json.split()) * 2
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return StructuredLLMResponse(
            parsed=parsed,
            raw_content=raw_json,
            model=model,
            provider="mock",
            usage=LLMUsage(
                prompt_tokens=max(1, prompt_tokens),
                completion_tokens=max(1, completion_tokens),
                total_tokens=max(2, prompt_tokens + completion_tokens),
            ),
            latency_ms=round(latency_ms, 2),
        )

    async def get_embedding(
        self,
        text: str,
        model: str = "nvidia/nv-embed-v1",
    ) -> List[float]:
        """Generate deterministic 384-dimensional unit vector embedding."""
        clean = text.strip()
        hasher = hashlib.sha256(clean.encode("utf-8"))
        seed_bytes = hasher.digest()

        # Generate 384 floats deterministically
        vec: List[float] = []
        for i in range(384):
            byte_val = seed_bytes[i % len(seed_bytes)]
            val = ((byte_val / 255.0) * 2.0) - 1.0  # normalize between -1.0 and 1.0
            vec.append(round(val, 6))

        # Normalize to unit length
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]

        return vec
