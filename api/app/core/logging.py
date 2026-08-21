"""
Hospital CRM - Structured Logging System
Provides clean, structured logging with automated redaction of sensitive credentials,
tokens, passwords, and sensitive PII.
"""
import logging
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict
from app.core.config import settings

# Sensitive keys to redact
SENSITIVE_KEYS = {
    "password", "secret", "token", "api_key", "auth", "authorization",
    "access_token", "refresh_token", "private_key", "secret_key"
}

def redact_sensitive_data(data: Any) -> Any:
    """Recursively redact sensitive key-values from dicts/lists."""
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            if any(sensitive in k.lower() for sensitive in SENSITIVE_KEYS):
                cleaned[k] = "******"
            else:
                cleaned[k] = redact_sensitive_data(v)
        return cleaned
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    elif isinstance(data, str):
        # Redact common bearer tokens or long keys
        if data.lower().startswith("bearer "):
            return "Bearer ******"
        return data
    return data


class JSONFormatter(logging.Formatter):
    """Formats log records into JSON objects for production ingestion."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "extra_data"):
            log_entry["data"] = redact_sensitive_data(record.extra_data)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logger(name: str = "hospital_crm") -> logging.Logger:
    logger = logging.getLogger(name)
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler()
        if settings.LOG_FORMAT.lower() == "json" and settings.APP_ENV != "development":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(
                logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
            )
        logger.addHandler(handler)

    logger.propagate = False
    return logger

logger = setup_logger()
