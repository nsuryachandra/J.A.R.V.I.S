"""Application exceptions and standardized error response handlers."""

from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class JarvisError(Exception):
    """Base class for all internal JARVIS exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ConfigurationError(JarvisError):
    """Raised when application configuration or environment variables are invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ValidationError(JarvisError):
    """Raised when input validation or temporal parameter constraints fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class DatabaseConnectionError(JarvisError):
    """Raised when the database cannot be connected or health check fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class EntityNotFoundError(JarvisError):
    """Raised when a requested resource does not exist."""

    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' was not found.",
            code="ENTITY_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"entity": entity_name, "identifier": str(identifier)},
        )


class AuthenticationError(JarvisError):
    """Raised when authentication credentials are missing, invalid, or expired."""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class TokenExpiredError(AuthenticationError):
    """Raised specifically when a JWT access token has expired."""

    def __init__(self, message: str = "Access token has expired"):
        super().__init__(message=message, details={"reason": "token_expired"})


class SessionRevokedError(AuthenticationError):
    """Raised when a session or refresh token has been revoked or reused."""

    def __init__(self, message: str = "Session has been revoked"):
        super().__init__(message=message, details={"reason": "session_revoked"})


class PermissionDeniedError(JarvisError):
    """Raised when an authenticated actor lacks capability or resource scope."""

    def __init__(self, message: str = "Permission denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ApprovalRequiredError(JarvisError):
    """Raised when an action requires explicit human approval before execution."""

    def __init__(self, message: str, approval_id: Any, details: Optional[Dict[str, Any]] = None):
        det = details or {}
        det["approval_id"] = str(approval_id)
        super().__init__(
            message=message,
            code="APPROVAL_REQUIRED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=det,
        )


class ApprovalExpiredError(JarvisError):
    """Raised when an approval token has passed its expiration window."""

    def __init__(self, message: str = "Approval has expired"):
        super().__init__(
            message=message,
            code="APPROVAL_EXPIRED",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class ReplayDetectedError(JarvisError):
    """Raised when an approval token is attempted to be reused after consumption."""

    def __init__(self, message: str = "Replay detected: approval has already been consumed"):
        super().__init__(
            message=message,
            code="REPLAY_DETECTED",
            status_code=status.HTTP_409_CONFLICT,
        )


class InvalidApprovalError(JarvisError):
    """Raised when approval parameters or arguments do not match the proposed action."""

    def __init__(self, message: str = "Approval validation failed"):
        super().__init__(
            message=message,
            code="INVALID_APPROVAL",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class RateLimitExceededError(JarvisError):
    """Raised when an actor exceeds permitted request frequency."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform JSON exception handlers on the FastAPI instance."""

    @app.exception_handler(JarvisError)
    async def jarvis_error_handler(_: Request, exc: JarvisError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "details": {"type": exc.__class__.__name__},
                }
            },
        )
