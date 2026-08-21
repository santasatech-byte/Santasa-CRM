"""
Hospital CRM - Security & Authentication Engine
Handles password hashing via bcrypt, JWT token generation/validation,
session revocation, and password strength policies.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set
import re
import bcrypt
import jwt
from app.core.config import settings
from app.core.errors import UnauthorizedError, ValidationError

# In-memory Token Blacklist for active session invalidation / logout
# Can be backed by Redis in multi-instance production deployment
REVOKED_TOKENS: Set[str] = set()


def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with standard salt rounds."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def validate_password_strength(password: str) -> bool:
    """
    Hospital Security Password Policy:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    """
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one digit.")
    return True


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed HS256 JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates JWT token, checking expiration and blacklist."""
    if token in REVOKED_TOKENS:
        raise UnauthorizedError("Session has been logged out or invalidated.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Session has expired. Please log in again.")
    except (jwt.InvalidTokenError, Exception):
        raise UnauthorizedError("Invalid authentication token.")


def revoke_token(token: str):
    """Adds token to the revoked session blacklist."""
    REVOKED_TOKENS.add(token)


def is_token_revoked(token: str) -> bool:
    return token in REVOKED_TOKENS
