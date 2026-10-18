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

        # Tenglish / Telugu greetings
        if any(t in lower_prompt for t in ["ela unnaru", "ela unnav", "bagunnara", "namaskaram", "namaste", "meeru ela"]):
            reply = "Hello sir! Nenu chala bagunnanu, thank you! Meeru ela unnaru? All core telemetry is optimal and I am standing by for your instructions. How may I assist you today, sir?"
        # Hindi greetings
        elif any(h in lower_prompt for h in ["kaise ho", "kya haal", "namaste sir", "aap kaise"]):
            reply = "Namaste sir! Main bilkul theek hoon. Aap kaise hain? All systems are online and ready for your command."
        # English greetings
        elif any(g in lower_prompt for g in ["hello", "hi", "hey", "good morning", "good evening", "greetings"]):
            reply = "Hello, sir. How may I assist you today? All primary subsystems are active and standing by."
        # Quick affirmations
        elif lower_prompt.strip() in ["ya", "yeah", "yes", "ok", "okay", "sure", "fine", "cool", "alright"]:
            reply = "Understood, sir. Subsystems standing by. What task shall we execute next?"
        elif lower_prompt.strip() in ["what", "who", "who are you", "what can you do", "help", "what is jarvis"]:
            reply = (
                "I am J.A.R.V.I.S. (Just A Rather Very Intelligent System), your personal AI operating system.\n\n"
                "Here are my current core capabilities:\n"
                "1. **Dynamic Model Routing**: Intelligently dispatching tasks across fast chat, deep reasoning (70B), code generation, and vision models.\n"
                "2. **Hands-free Voice Input & Output**: Real-time microphone listening and natural speech synthesis.\n"
                "3. **Task & Schedule Governance**: Habit tracking, fasting schedules, and autonomous multi-step plans.\n"
                "4. **Policy & Consequential Guardrails**: Human-in-the-loop approval workflows for privileged operations.\n\n"
                "*Tip: To enable live unconstrained generative AI responses via NVIDIA NIM or Groq, configure your `NVIDIA_API_KEY` or `GROQ_API_KEY` in `backend/.env`.*"
            )
        elif any(k in lower_prompt for k in ["diagnostic", "status", "telemetry", "health", "system check"]):
            reply = (
                "Telemetry Diagnostics Report:\n"
                "- Core Processing: ONLINE\n"
                "- Neural Model Router: ACTIVE (Auto-routing enabled)\n"
                "- Voice Engine: READY\n"
                "- Policy Audit Broker: ACTIVE [SHA-256 Hash Chain]\n"
                "- SQLite Database: HEALTHY"
            )
        elif any(k in lower_prompt for k in ["fast", "habit", "routine", "fasting", "workout"]):
            reply = "Your schedule has been verified. Your intermittent fasting protocol and routine habits are currently tracked and active."
        elif any(k in lower_prompt for k in ["code", "python", "script", "function", "api test"]):
            reply = (
                "Here is an asynchronous Python script demonstrating interaction with the JARVIS API:\n\n"
                "```python\n"
                "import asyncio\n"
                "import httpx\n\n"
                "async def query_jarvis(prompt: str):\n"
                "    async with httpx.AsyncClient(base_url='http://localhost:8000') as client:\n"
                "        resp = await client.post('/api/v1/models/chat', json={\n"
                "            'messages': [{'role': 'user', 'content': prompt}],\n"
                "            'role': 'auto'\n"
                "        })\n"
                "        print('JARVIS Response:', resp.json().get('content'))\n\n"
                "if __name__ == '__main__':\n"
                "    asyncio.run(query_jarvis('Hello J.A.R.V.I.S.'))\n"
                "```"
            )
        elif any(k in lower_prompt for k in ["plan", "goal", "strategy", "architecture", "tradeoff"]):
            reply = (
                "Here is the strategic breakdown for your request:\n"
                "1. **Analysis & Requirement Decomposition**: Isolate constraints and verify dependencies.\n"
                "2. **Execution & Policy Verification**: Dispatch tasks via the model router while logging cryptographic audit events.\n"
                "3. **Synthesis & Validation**: Return verified outputs with full telemetry tracking."
            )
        else:
            clean_subject = last_msg.strip(" ?.!").capitalize()
            reply = (
                f"Regarding \"{clean_subject}\": I have processed your input through the holographic core.\n\n"
                "I am currently operating in localized offline mode. For real-time open-domain generative conversations, "
                "please insert your `NVIDIA_API_KEY` (from https://build.nvidia.com) or `GROQ_API_KEY` into your `backend/.env` file. "
                "How else may I assist you with your tasks or system controls?"
            )

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
