"""Deterministic Policy and Permission Broker enforcing access control outside the model."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Set
from uuid import UUID
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    ApprovalExpiredError,
    EntityNotFoundError,
    InvalidApprovalError,
    PermissionDeniedError,
    ReplayDetectedError,
)
from app.models.approval import ApprovalRequest
from app.models.user import User
from app.services.approval_service import ApprovalService, canonicalize_arguments
from app.services.audit_service import AuditService
from app.services.tool_registry import RiskClass, ToolRegistry, get_tool_registry


class BrokerDecision(str, Enum):
    """Possible outcomes from policy broker action evaluation."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    INVALID_REQUEST = "INVALID_REQUEST"
    EXPIRED_APPROVAL = "EXPIRED_APPROVAL"
    REPLAY_DETECTED = "REPLAY_DETECTED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    TOOL_DISABLED = "TOOL_DISABLED"


@dataclass
class BrokerEvaluation:
    """Result payload from policy broker evaluation."""
    decision: BrokerDecision
    reason: str
    tool_name: str
    risk_class: Optional[str] = None
    arguments_hash: Optional[str] = None
    approval_request: Optional[ApprovalRequest] = None
    audit_log_id: Optional[UUID] = None


class PolicyBroker:
    """Deterministic security gate evaluating all proposed tool invocations."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_tool_registry()

    async def evaluate_action(
        self,
        session: AsyncSession,
        actor: User,
        tool_name: str,
        arguments: Dict[str, Any],
        target_resource: str = "user_workspace",
        approval_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        agent_run_id: Optional[str] = None,
        actor_capabilities: Optional[Set[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> BrokerEvaluation:
        """Evaluate a proposed action against tool definitions, capabilities, and approval state."""
        capabilities = actor_capabilities or set()

        # 1. Tool Registry Verification
        tool = self.registry.get(tool_name)
        if tool is None:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.DENY.value,
                user_id=actor.id,
                session_id=session_id,
                tool_name=tool_name,
                result_status="FAILED",
                error_code="UNREGISTERED_TOOL",
                details={"message": f"Tool '{tool_name}' is not registered"},
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.DENY,
                reason=f"Tool '{tool_name}' is not registered.",
                tool_name=tool_name,
                audit_log_id=audit.id,
            )

        if not tool.is_enabled:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.TOOL_DISABLED.value,
                user_id=actor.id,
                session_id=session_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                result_status="FAILED",
                error_code="TOOL_DISABLED",
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.TOOL_DISABLED,
                reason=f"Tool '{tool_name}' is currently disabled.",
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                audit_log_id=audit.id,
            )

        # 2. Input Schema Validation
        try:
            validated_input = tool.input_schema(**arguments)
            canonical_args, args_hash = canonicalize_arguments(validated_input.model_dump())
        except ValidationError as val_err:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.INVALID_REQUEST.value,
                user_id=actor.id,
                session_id=session_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                result_status="FAILED",
                error_code="VALIDATION_ERROR",
                details={"errors": val_err.errors()},
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.INVALID_REQUEST,
                reason=f"Input validation failed: {val_err.errors()}",
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                audit_log_id=audit.id,
            )

        # 3. Capability Verification
        if tool.required_capabilities:
            missing = tool.required_capabilities - capabilities
            if missing:
                audit = await AuditService.record_event(
                    session=session,
                    action_type="TOOL_EVALUATION",
                    decision=BrokerDecision.DENY.value,
                    user_id=actor.id,
                    session_id=session_id,
                    tool_name=tool_name,
                    tool_version=tool.version,
                    risk_class=tool.risk_class.value,
                    arguments_hash=args_hash,
                    result_status="FAILED",
                    error_code="MISSING_CAPABILITY",
                    details={"missing_capabilities": list(missing)},
                    correlation_id=correlation_id,
                )
                return BrokerEvaluation(
                    decision=BrokerDecision.DENY,
                    reason=f"Missing required capabilities: {missing}",
                    tool_name=tool_name,
                    risk_class=tool.risk_class.value,
                    arguments_hash=args_hash,
                    audit_log_id=audit.id,
                )

        # 4. Risk Classification and Approval Logic
        if tool.risk_class == RiskClass.SAFE:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.ALLOW.value,
                user_id=actor.id,
                session_id=session_id,
                agent_run_id=agent_run_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                resource_scope=target_resource,
                result_status="SUCCESS",
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.ALLOW,
                reason="Safe read operation authorized.",
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                audit_log_id=audit.id,
            )

        elif tool.risk_class == RiskClass.MODERATE:
            policy = tool.moderate_policy
            if policy and policy.requires_approval_by_default:
                # Treated with same approval mandate as Consequential
                pass
            else:
                # Check sensitive data access capability requirement
                if policy and policy.sensitive_data_access:
                    required_cap = policy.requires_user_capability
                    if required_cap and required_cap not in capabilities:
                        audit = await AuditService.record_event(
                            session=session,
                            action_type="TOOL_EVALUATION",
                            decision=BrokerDecision.DENY.value,
                            user_id=actor.id,
                            session_id=session_id,
                            tool_name=tool_name,
                            tool_version=tool.version,
                            risk_class=tool.risk_class.value,
                            arguments_hash=args_hash,
                            result_status="FAILED",
                            error_code="SENSITIVE_DATA_ACCESS_DENIED",
                            details={"required_capability": required_cap},
                            correlation_id=correlation_id,
                        )
                        return BrokerEvaluation(
                            decision=BrokerDecision.DENY,
                            reason=f"Access to sensitive data requires capability '{required_cap}'.",
                            tool_name=tool_name,
                            risk_class=tool.risk_class.value,
                            arguments_hash=args_hash,
                            audit_log_id=audit.id,
                        )

                audit = await AuditService.record_event(
                    session=session,
                    action_type="TOOL_EVALUATION",
                    decision=BrokerDecision.ALLOW.value,
                    user_id=actor.id,
                    session_id=session_id,
                    agent_run_id=agent_run_id,
                    tool_name=tool_name,
                    tool_version=tool.version,
                    risk_class=tool.risk_class.value,
                    arguments_hash=args_hash,
                    resource_scope=target_resource,
                    result_status="SUCCESS",
                    details={"write_operation": policy.write_operation if policy else False},
                    correlation_id=correlation_id,
                )
                return BrokerEvaluation(
                    decision=BrokerDecision.ALLOW,
                    reason="Moderate operation authorized according to policy.",
                    tool_name=tool_name,
                    risk_class=tool.risk_class.value,
                    arguments_hash=args_hash,
                    audit_log_id=audit.id,
                )

        # 5. Consequential / Approval-Mandated Operations
        if approval_id is None:
            # Generate new pending approval request
            approval_req = await ApprovalService.create_request(
                session=session,
                user_id=actor.id,
                tool_name=tool_name,
                tool_version=tool.version,
                arguments=canonical_args,
                target_resource=target_resource,
                risk_class=tool.risk_class.value,
                session_id=session_id,
                created_by_agent_run=agent_run_id,
            )
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.REQUIRE_APPROVAL.value,
                user_id=actor.id,
                session_id=session_id,
                agent_run_id=agent_run_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                approval_id=approval_req.id,
                result_status="PENDING",
                details={"approval_id": str(approval_req.id)},
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.REQUIRE_APPROVAL,
                reason="Consequential operation requires explicit human approval.",
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                approval_request=approval_req,
                audit_log_id=audit.id,
            )

        # 6. Verify and Atomically Consume Approval
        try:
            consumed = await ApprovalService.consume_atomically(
                session=session,
                approval_id=approval_id,
                user_id=actor.id,
                expected_tool_name=tool_name,
                expected_arguments_hash=args_hash,
            )
            if consumed:
                audit = await AuditService.record_event(
                    session=session,
                    action_type="TOOL_EVALUATION",
                    decision=BrokerDecision.ALLOW.value,
                    user_id=actor.id,
                    session_id=session_id,
                    agent_run_id=agent_run_id,
                    tool_name=tool_name,
                    tool_version=tool.version,
                    risk_class=tool.risk_class.value,
                    arguments_hash=args_hash,
                    approval_id=approval_id,
                    result_status="SUCCESS",
                    details={"consumed_approval_id": str(approval_id)},
                    correlation_id=correlation_id,
                )
                return BrokerEvaluation(
                    decision=BrokerDecision.ALLOW,
                    reason="Consequential operation approved and consumed.",
                    tool_name=tool_name,
                    risk_class=tool.risk_class.value,
                    arguments_hash=args_hash,
                    audit_log_id=audit.id,
                )
        except ReplayDetectedError as replay_err:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.REPLAY_DETECTED.value,
                user_id=actor.id,
                session_id=session_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                approval_id=approval_id,
                result_status="FAILED",
                error_code="REPLAY_DETECTED",
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.REPLAY_DETECTED,
                reason=str(replay_err),
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                audit_log_id=audit.id,
            )
        except ApprovalExpiredError as exp_err:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.EXPIRED_APPROVAL.value,
                user_id=actor.id,
                session_id=session_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                approval_id=approval_id,
                result_status="FAILED",
                error_code="EXPIRED_APPROVAL",
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.EXPIRED_APPROVAL,
                reason=str(exp_err),
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                audit_log_id=audit.id,
            )
        except (InvalidApprovalError, EntityNotFoundError) as inv_err:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.INVALID_REQUEST.value,
                user_id=actor.id,
                session_id=session_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                approval_id=approval_id,
                result_status="FAILED",
                error_code="INVALID_APPROVAL",
                details={"error": str(inv_err)},
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.INVALID_REQUEST,
                reason=str(inv_err),
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                audit_log_id=audit.id,
            )
        except PermissionDeniedError as perm_err:
            audit = await AuditService.record_event(
                session=session,
                action_type="TOOL_EVALUATION",
                decision=BrokerDecision.DENY.value,
                user_id=actor.id,
                session_id=session_id,
                tool_name=tool_name,
                tool_version=tool.version,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                approval_id=approval_id,
                result_status="FAILED",
                error_code="CROSS_USER_APPROVAL_ATTEMPT",
                correlation_id=correlation_id,
            )
            return BrokerEvaluation(
                decision=BrokerDecision.DENY,
                reason=str(perm_err),
                tool_name=tool_name,
                risk_class=tool.risk_class.value,
                arguments_hash=args_hash,
                audit_log_id=audit.id,
            )

        return BrokerEvaluation(
            decision=BrokerDecision.DENY,
            reason="Action could not be authorized.",
            tool_name=tool_name,
        )
