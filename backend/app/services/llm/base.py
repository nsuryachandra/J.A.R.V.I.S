"""Abstract Base Class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Type, TypeVar
from pydantic import BaseModel
from app.services.llm.schemas import LLMMessage, LLMResponse, StructuredLLMResponse

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """Abstract provider interface for LLM inference, structured output, and embeddings."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. nvidia, mock)."""
        pass

    @abstractmethod
    async def generate(
        self,
        model: str,
        messages: List[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate text completion from model."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        model: str,
        messages: List[LLMMessage],
        schema: Type[T],
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> StructuredLLMResponse[T]:
        """Generate structured completion adhering to Pydantic schema."""
        pass

    @abstractmethod
    async def get_embedding(
        self,
        text: str,
        model: str = "nvidia/nv-embed-v1",
    ) -> List[float]:
        """Generate vector embedding for text."""
        pass
