"""
Unit Tests for Project Foundation: Config, Logging Redaction, and Error Handling.
"""
import pytest
from app.core.config import settings
from app.core.logging import redact_sensitive_data
from app.core.errors import (
    CRMException,
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    DuplicateResourceError,
    ValidationError
)


def test_config_defaults():
    """Verify application configuration loads default settings accurately."""
    assert settings.APP_NAME is not None
    assert isinstance(settings.CORS_ORIGINS, list)
    assert settings.TELEPHONY_PROVIDER in ["mock", "exotel", "twilio", "asterisk"]
    assert settings.WHATSAPP_PROVIDER in ["mock", "meta", "gupshup", "twilio"]


def test_sensitive_data_redaction():
    """Verify sensitive tokens and keys are never printed in plain text."""
    payload = {
        "user_id": "usr_123",
        "api_key": "secret_live_key_9999",
        "nested": {
            "password": "Password123!",
            "token": "bearer xyz123",
            "phone": "+919876543210"
        }
    }
    cleaned = redact_sensitive_data(payload)
    
    assert cleaned["user_id"] == "usr_123"
    assert cleaned["api_key"] == "******"
    assert cleaned["nested"]["password"] == "******"
    assert cleaned["nested"]["token"] == "******"
    assert cleaned["nested"]["phone"] == "+919876543210"


def test_error_hierarchy():
    """Verify exception classes generate structured codes and HTTP status codes."""
    not_found = NotFoundError("Lead", "lead_404")
    assert not_found.status_code == 404
    assert not_found.code == "NOT_FOUND"
    assert not_found.details["id"] == "lead_404"

    unauthorized = UnauthorizedError()
    assert unauthorized.status_code == 401
    assert unauthorized.code == "UNAUTHORIZED"

    duplicate = DuplicateResourceError("Lead", "phone", "+919876543210")
    assert duplicate.status_code == 409
    assert duplicate.code == "DUPLICATE_RESOURCE"
    assert duplicate.details["value"] == "+919876543210"
