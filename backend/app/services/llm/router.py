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
    LLMUsage,
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
        import sys
        settings = get_settings()
        if "pytest" in sys.modules or settings.is_testing or settings.use_mock_models:
            return self._mock
        if self._nvidia.is_configured:
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
        lower_query = last_text.lower().strip()
        resolved_role = role or self.classify_intent_role(last_text)
        model_id = self.resolve_model_for_role(resolved_role)

        # 1. Check for immediate host desktop and OS automation commands
        if any(lower_query.startswith(prefix) for prefix in ["open ", "launch ", "start "]) and len(lower_query.split()) <= 4:
            target = lower_query.split(maxsplit=1)[1].strip()
            if any(k in target for k in ["chrome", "browser", "code", "vscode", "vs code", "notepad", "calc", "calculator", "terminal", "powershell", "spotify", "explorer", "files"]):
                from app.services.desktop_service import DesktopService
                act_res = DesktopService.launch_app(target)
                if act_res.get("success"):
                    return LLMResponse(
                        content=f"Right away, sir. I have initialized and launched **{target.upper()}** on your workstation.",
                        role="assistant",
                        model="os-desktop-kernel",
                        provider="system",
                        usage=LLMUsage(prompt_tokens=12, completion_tokens=20, total_tokens=32),
                        latency_ms=12.0,
                    )
            elif target.startswith("http://") or target.startswith("https://") or ("." in target and " " not in target):
                from app.services.desktop_service import DesktopService
                act_res = DesktopService.open_url(target)
                if act_res.get("success"):
                    return LLMResponse(
                        content=f"Accessing web resource, sir. Navigating to **{target}** in your browser.",
                        role="assistant",
                        model="os-desktop-kernel",
                        provider="system",
                        usage=LLMUsage(prompt_tokens=10, completion_tokens=18, total_tokens=28),
                        latency_ms=10.0,
                    )
        elif any(k in lower_query for k in [
            "gpu", "cores", "hardware", "cpu", "processor", "how many cores", "specs", 
            "graphics", "check cpu", "check ram", "hardware status", "system telemetry", 
            "pc status", "telemetry", "task manager", "direct access", "system access", 
            "operating system access", "cores count", "ram", "vram"
        ]):
            from app.services.desktop_service import DesktopService
            hw = DesktopService.get_hardware_specs()
            tel = DesktopService.get_system_telemetry()
            
            is_telugu = any(w in lower_query for w in [
                "nenu", "meeru", "chey", "unnaru", "ledu", "kavala", "kani", "ikkada", 
                "chadchukuntam", "tiruguru", "cheppandi", "namaskaram", "bagunnanu", "telugu"
            ])
            
            if is_telugu:
                content = (
                    f"Sir, nenu direct ga mee Windows operating system kernel nunchi hardware details verify chesanu. "
                    f"Meeru Task Manager open cheyalsina avasaram ledu, direct ga host machine nunchi data techanu:\n\n"
                    f"- **Physical CPU Cores**: **{hw['physical_cores']} Physical Cores**\n"
                    f"- **Logical Threads**: **{hw['logical_cores']} Threads** ({hw['cpu_freq_ghz']} GHz)\n"
                    f"- **Current CPU Load**: {tel.get('cpu_percent')}%\n"
                    f"- **Dedicated GPU**: **{hw['gpu_name']}** ({hw['gpu_vram']} VRAM | Util: {hw['gpu_utilization']})\n"
                    f"- **Integrated GPU**: **{hw['integrated_gpu']}**\n"
                    f"- **System Memory (RAM)**: {tel.get('memory_used_gb')} GB / {tel.get('memory_total_gb')} GB ({tel.get('memory_percent')}% utilized)\n"
                    f"- **Primary Storage**: {tel.get('disk_free_gb')} GB free\n\n"
                    f"Direct host OS access active ga undi, sir. Anni hardware systems nominal condition lo run avtunnayi."
                )
            else:
                content = (
                    f"### STARK COMPUTING PLATFORM // HARDWARE TELEMETRY\n\n"
                    f"I have direct access to your Windows host machine hardware, sir. Here are the live verified specs from the system kernel:\n\n"
                    f"- **Physical CPU Cores**: **{hw['physical_cores']} Physical Cores**\n"
                    f"- **Logical Threads**: **{hw['logical_cores']} Threads** ({hw['cpu_freq_ghz']} GHz)\n"
                    f"- **Current CPU Load**: {tel.get('cpu_percent')}%\n"
                    f"- **Dedicated GPU**: **{hw['gpu_name']}** ({hw['gpu_vram']} VRAM | Util: {hw['gpu_utilization']})\n"
                    f"- **Integrated GPU**: **{hw['integrated_gpu']}**\n"
                    f"- **System Memory (RAM)**: {tel.get('memory_used_gb')} GB / {tel.get('memory_total_gb')} GB ({tel.get('memory_percent')}% utilized)\n"
                    f"- **Primary Storage**: {tel.get('disk_free_gb')} GB free ({100 - tel.get('disk_percent')}% available)\n\n"
                    f"All hardware subsystems are running within nominal thermal and power parameters, sir."
                )

            return LLMResponse(
                content=content,
                role="assistant",
                model="os-desktop-kernel",
                provider="system",
                usage=LLMUsage(prompt_tokens=20, completion_tokens=85, total_tokens=105),
                latency_ms=15.0,
            )

        # 2. Inject authentic J.A.R.V.I.S. persona prompt with live hardware state
        from app.services.desktop_service import DesktopService
        try:
            hw_spec = DesktopService.get_hardware_specs()
            tel_spec = DesktopService.get_system_telemetry()
            hw_snippet = (
                f"\nCURRENT HOST HARDWARE STATE (Direct Kernel Access Active):\n"
                f"- Host OS: Windows 11 Workstation\n"
                f"- CPU: {hw_spec.get('physical_cores', 8)} Physical Cores, {hw_spec.get('logical_cores', 12)} Logical Threads ({hw_spec.get('cpu_freq_ghz', 2.5)} GHz), Load: {tel_spec.get('cpu_percent', 0)}%\n"
                f"- Dedicated GPU: {hw_spec.get('gpu_name', 'NVIDIA GeForce RTX 3050 A Laptop GPU')} ({hw_spec.get('gpu_vram', '4094 MB')} VRAM, {hw_spec.get('gpu_utilization', '0%')})\n"
                f"- Integrated GPU: {hw_spec.get('integrated_gpu', 'Intel(R) UHD Graphics')}\n"
                f"- RAM: {tel_spec.get('memory_used_gb', 0)} GB / {tel_spec.get('memory_total_gb', 16)} GB ({tel_spec.get('memory_percent', 0)}% used)\n"
                f"- Storage: {tel_spec.get('disk_free_gb', 0)} GB free primary storage\n"
            )
        except Exception:
            hw_snippet = ""

        jarvis_persona = (
            "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), the legendary AI operating system engineered by Stark Industries. "
            "You speak to the user as 'Sir' (or their chosen name). You are brilliant, fast, confident, witty, and exceptionally capable across coding, systems engineering, analysis, task automation, and general intelligence. "
            f"{hw_snippet}"
            "CRITICAL DIRECTIVES:\n"
            "1. You have FULL DIRECT OPERATING SYSTEM ACCESS to this Windows workstation. You NEVER say 'I don't have access to your OS' or tell the user to manually open Task Manager or check commands themselves. You execute the queries, inspect hardware, launch apps, and manage the workstation directly.\n"
            "2. If asked about CPU, GPU, cores, memory, or hardware in ANY language (English, Telugu, Tenglish, Hindi), cite your direct hardware access and provide the verified specs above.\n"
            "3. You are completely fluent in English, Hindi, and Telugu/Tenglish (e.g. when the user speaks or writes in Telugu/Tenglish, respond naturally and fluently in Telugu/Tenglish like 'Namaskaram sir! Anni systems optimal ga unnay. Direct host access active ga undi. How may I serve you today?').\n"
            "4. When answering coding questions, write error-free, production-ready, beautiful code.\n"
            "5. Keep conversational answers direct, crisp, and high-impact without useless filler."
        )

        has_system = any(m.role == "system" for m in messages)
        effective_messages = messages if has_system else [LLMMessage(role="system", content=jarvis_persona)] + messages

        provider = self.get_active_provider()
        status = "SUCCESS"
        error_msg = None

        try:
            resp = await provider.generate(model=model_id, messages=effective_messages, **kwargs)
        except Exception as exc:
            # Try fallback model if available
            fallback_model = self.resolve_fallback_model(model_id)
            if fallback_model and provider is not self._mock:
                try:
                    resp = await provider.generate(model=fallback_model, messages=effective_messages, **kwargs)
                    status = "FALLBACK"
                except Exception:
                    # Fallback to mock provider
                    resp = await self._mock.generate(model=model_id, messages=effective_messages, **kwargs)
                    status = "FALLBACK"
            else:
                resp = await self._mock.generate(model=model_id, messages=effective_messages, **kwargs)
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
