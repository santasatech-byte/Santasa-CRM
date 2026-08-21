"""
Hospital CRM - Error Handling Hierarchy
Guarantees clean error responses without leaking internal stack traces or secrets.
"""
from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.logging import logger
from app.core.config import settings


class CRMException(Exception):
    """Base application exception for Hospital CRM."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: str = "BAD_REQUEST",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class NotFoundError(CRMException):
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} '{identifier}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            details={"resource": resource, "id": str(identifier)},
        )


class UnauthorizedError(CRMException):
    def __init__(self, message: str = "Authentication required."):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
        )


class ForbiddenError(CRMException):
    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
        )


class DuplicateResourceError(CRMException):
    def __init__(self, resource: str, field: str, value: Any):
        super().__init__(
            message=f"{resource} with {field} '{value}' already exists.",
            status_code=status.HTTP_409_CONFLICT,
            code="DUPLICATE_RESOURCE",
            details={"resource": resource, "field": field, "value": str(value)},
        )


class ValidationError(CRMException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=422,
            code="VALIDATION_ERROR",
            details=details,
        )


class TelephonyProviderError(CRMException):
    def __init__(self, provider: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Telephony provider ({provider}) error: {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="TELEPHONY_PROVIDER_ERROR",
            details={"provider": provider, **(details or {})},
        )


async def crm_exception_handler(request: Request, exc: CRMException) -> JSONResponse:
    """Handles all internal CRM domain exceptions."""
    logger.warning(
        f"Domain exception: {exc.code} - {exc.message}",
        extra={"extra_data": {"path": request.url.path, "details": exc.details}}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches unhandled exceptions and protects production systems from leaking internals."""
    logger.error(
        f"Unhandled server error on {request.method} {request.url.path}: {str(exc)}",
        exc_info=True
    )
    
    message = (
        f"Internal server error: {str(exc)}"
        if settings.DEBUG
        else "An unexpected error occurred. Please contact hospital administrator."
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": message,
            }
        },
    )
