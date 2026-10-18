"""Tests for PrivacyPolicyEnforcer, scope compatibility, sensitivity clearance, and redaction."""

from app.contracts.common import PrivacyScope, SensitivityLevel
from app.contracts.privacy import PrivacyPolicyEnforcer, RedactionPolicy


def test_sensitivity_permission_check():
    """Verify threshold check against maximum permitted sensitivity."""
    # PRIVATE (30) <= PRIVATE (30) -> Allowed
    assert PrivacyPolicyEnforcer.is_sensitivity_permitted(
        SensitivityLevel.PRIVATE, SensitivityLevel.PRIVATE
    ) is True

    # PUBLIC (10) <= PRIVATE (30) -> Allowed
    assert PrivacyPolicyEnforcer.is_sensitivity_permitted(
        SensitivityLevel.PUBLIC, SensitivityLevel.PRIVATE
    ) is True

    # HIGHLY_SENSITIVE (50) <= PRIVATE (30) -> Denied
    assert PrivacyPolicyEnforcer.is_sensitivity_permitted(
        SensitivityLevel.HIGHLY_SENSITIVE, SensitivityLevel.PRIVATE
    ) is False


def test_scope_compatibility_firewall():
    """Verify strict privacy barriers between personal, business, and user-only scopes."""
    # Self-compatibility
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.PERSONAL, PrivacyScope.PERSONAL) is True
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.BUSINESS, PrivacyScope.BUSINESS) is True

    # Strict firewall between PERSONAL and BUSINESS
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.BUSINESS, PrivacyScope.PERSONAL) is False
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.PERSONAL, PrivacyScope.BUSINESS) is False

    # USER_ONLY data never leaves USER_ONLY context
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.USER_ONLY, PrivacyScope.PERSONAL) is False
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.USER_ONLY, PrivacyScope.AGENT) is False
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.USER_ONLY, PrivacyScope.CONVERSATION) is False

    # AGENT can receive PERSONAL or BUSINESS, but NOT USER_ONLY
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.PERSONAL, PrivacyScope.AGENT) is True
    assert PrivacyPolicyEnforcer.is_scope_compatible(PrivacyScope.BUSINESS, PrivacyScope.AGENT) is True


def test_sanitize_string_masks_sensitive_tokens():
    """Verify that sanitize_string masks explicit secrets and bearer tokens."""
    raw = "User said: My password is 'password': 'SecretPassword123' and token is Bearer eyJhbGciOiJIUzI1NiJ9.abc"
    sanitized = PrivacyPolicyEnforcer.sanitize_string(
        raw, extra_secrets=["SecretPassword123"]
    )
    assert "SecretPassword123" not in sanitized
    assert "eyJhbGciOiJIUzI1NiJ9" not in sanitized
    assert "[REDACTED]" in sanitized
