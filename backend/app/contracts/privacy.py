"""Privacy scope policies, sensitivity ordering, and redaction contracts."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.contracts.common import PrivacyScope, SensitivityLevel
from app.core.logging import SENSITIVE_KEY_PATTERN, mask_sensitive_data


class RedactionPolicy(BaseModel):
    """Specification of sensitivity and scope constraints for content disclosure."""

    model_config = ConfigDict(frozen=True)

    max_permitted_sensitivity: SensitivityLevel = Field(
        default=SensitivityLevel.PRIVATE,
        description="Upper ceiling of sensitivity allowed without explicit escalation",
    )
    allowed_scopes: List[PrivacyScope] = Field(
        default_factory=lambda: [PrivacyScope.PERSONAL, PrivacyScope.CONVERSATION],
        description="Permitted target privacy boundaries",
    )
    mask_secrets: bool = Field(
        default=True,
        description="Whether regex/secret filters must redact patterns",
    )


class PrivacyPolicyEnforcer:
    """Deterministic validation rules governing data disclosure across sensitivity and scope boundaries."""

    @classmethod
    def is_sensitivity_permitted(
        cls,
        item_sensitivity: SensitivityLevel,
        max_permitted: SensitivityLevel,
    ) -> bool:
        """Verify that an item's sensitivity does not exceed the allowed threshold."""
        return item_sensitivity.value <= max_permitted.value

    @classmethod
    def is_scope_compatible(
        cls,
        source_scope: PrivacyScope,
        target_scope: PrivacyScope,
    ) -> bool:
        """
        Determine whether information from source_scope may flow into target_scope.
        Enforces strict segregation between personal, business, user-only, and agent contexts.
        """
        # Identical scopes are always compatible
        if source_scope == target_scope:
            return True

        # USER_ONLY data never leaves the user-only boundary
        if source_scope == PrivacyScope.USER_ONLY:
            return False

        # Strict firewall: BUSINESS data cannot leak into PERSONAL context without bridge
        if source_scope == PrivacyScope.BUSINESS and target_scope == PrivacyScope.PERSONAL:
            return False

        # Strict firewall: PERSONAL data cannot leak into BUSINESS context
        if source_scope == PrivacyScope.PERSONAL and target_scope == PrivacyScope.BUSINESS:
            return False

        # CONVERSATION or PROJECT scope can accept PERSONAL or BUSINESS if target is within same scope
        if target_scope == PrivacyScope.CONVERSATION:
            return source_scope in (PrivacyScope.PERSONAL, PrivacyScope.CONVERSATION, PrivacyScope.DEVICE)

        if target_scope == PrivacyScope.AGENT:
            # Agents cannot receive USER_ONLY or highly private raw credentials
            return source_scope != PrivacyScope.USER_ONLY

        return False

    @classmethod
    def sanitize_string(cls, text: str, extra_secrets: Optional[List[str]] = None) -> str:
        """Mask common secrets, bearer tokens, and explicit secret tokens in strings."""
        sanitized = text
        # Mask explicit secret tokens
        if extra_secrets:
            for s in extra_secrets:
                if s and len(s) >= 4:
                    sanitized = sanitized.replace(s, "[REDACTED]")

        # Mask regex bearer tokens and passwords
        import re
        sanitized = re.sub(r"(Bearer\s+)[A-Za-z0-9\-_.]+", r"\1[REDACTED_TOKEN]", sanitized, flags=re.I)
        sanitized = re.sub(r'("password"\s*:\s*")[^"]+(")', r"\1[REDACTED_SECRET]\2", sanitized, flags=re.I)
        return sanitized
