"""NVIDIA NIM API client adapter with exponential backoff retries and structured output."""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.services.llm.base import BaseLLMProvider
from app.services.llm.schemas import (
    LLMMessage,
    LLMResponse,
    LLMUsage,
    StructuredLLMResponse,
)

T = TypeVar("T", bound=BaseModel)


class NvidiaNIMProvider(BaseLLMProvider):
    """Client adapter for NVIDIA NIM API with model discovery, retries, and schema enforcement."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        settings = get_settings()
        self._api_key = api_key or settings.nvidia_api_key
        self._base_url = (base_url or settings.nvidia_base_url).rstrip("/")
        self._timeout = timeout or settings.model_timeout_seconds
        self._max_retries = max_retries if max_retries is not None else settings.model_max_retries

    @property
    def provider_name(self) -> str:
        return "nvidia"

    @property
    def is_configured(self) -> bool:
        """Check whether valid API key is available."""
        return bool(self._api_key and self._api_key.strip())

    def _get_headers(self) -> Dict[str, str]:
        if not self._api_key:
            raise ValidationError("NVIDIA NIM API key is not configured.")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def generate(
        self,
        model: str,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call NVIDIA NIM chat completions endpoint with retry policy."""
        url = f"{self._base_url}/chat/completions"
        headers = self._get_headers()
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                    resp = await client.post(url, json=payload, headers=headers)

                latency_ms = (time.perf_counter() - start_time) * 1000.0

                if resp.status_code in (429, 500, 502, 503, 504) and attempt < self._max_retries:
                    await asyncio.sleep(2**attempt * 0.5)
                    continue

                resp.raise_for_status()
                data = resp.json()

                choice = data["choices"][0]
                content = choice["message"]["content"]
                role = choice["message"].get("role", "assistant")

                usage_data = data.get("usage", {})
                usage = LLMUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                )

                return LLMResponse(
                    content=content,
                    role=role,
                    model=model,
                    provider="nvidia",
                    usage=usage,
                    latency_ms=round(latency_ms, 2),
                    request_id=data.get("id"),
                )
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(2**attempt * 0.5)
                else:
                    break

        raise RuntimeError(f"NVIDIA NIM API error after {self._max_retries} retries: {last_error}")

    async def generate_structured(
        self,
        model: str,
        messages: List[LLMMessage],
        schema: Type[T],
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> StructuredLLMResponse[T]:
        """Call NVIDIA NIM and validate structured JSON response against target schema."""
        # Inject schema system instructions
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        system_instruction = (
            f"You MUST respond ONLY with valid JSON conforming strictly to this JSON Schema:\n{schema_json}\n"
            f"Do not include any other markdown formatting or conversational text."
        )

        enhanced_messages = [LLMMessage(role="system", content=system_instruction)] + messages

        raw_resp = await self.generate(
            model=model,
            messages=enhanced_messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            **kwargs,
        )

        content = raw_resp.content.strip()
        # Clean potential markdown fences e.g. ```json ... ```
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        try:
            parsed_json = json.loads(content)
            parsed_obj = schema(**parsed_json)
        except Exception as exc:
            raise ValidationError(f"Failed to validate model output against schema {schema.__name__}: {exc}")

        return StructuredLLMResponse(
            parsed=parsed_obj,
            raw_content=raw_resp.content,
            model=raw_resp.model,
            provider="nvidia",
            usage=raw_resp.usage,
            latency_ms=raw_resp.latency_ms,
        )

    async def get_embedding(
        self,
        text: str,
        model: str = "nvidia/nv-embed-v1",
    ) -> List[float]:
        """Fetch vector embeddings from NVIDIA NIM embeddings endpoint."""
        url = f"{self._base_url}/embeddings"
        headers = self._get_headers()
        payload = {
            "model": model,
            "input": [text],
            "input_type": "query",
        }

        async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
