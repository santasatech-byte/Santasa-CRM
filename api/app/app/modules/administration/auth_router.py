"""
Hospital CRM - Authentication API Router
Handles Login, Logout, Session Refresh, and User Profile with Supabase Auth & JWT Sessions.
"""
from datetime import datetime, timedelta, timezone
import json
import urllib.request
import urllib.error
from typing import Dict, Optional
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.config import Settings
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    revoke_token,
)
from app.core.errors import (
    UnauthorizedError,
    NotFoundError,
    ValidationError,
    ForbiddenError,
    DuplicateResourceError
)
from app.core.dependencies import get_current_user, get_current_active_user, get_token_from_header
from app.core.permissions import require_roles
from app.core.logging import logger
from app.modules.administration.models import User, UserRole
from app.modules.administration.schemas import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    UserSummary,
    PasswordResetRequest,
    PasswordResetConfirm,
    ChangePasswordRequest,
    CreateUserRequest
)

settings = Settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates user with Supabase Auth (or local database fallback),
    returns Supabase JWT access token, refresh token, and user session profile.
    """
    email_clean = credentials.email.lower().strip()
    supabase_url = settings.SUPABASE_URL
    supabase_key = settings.SUPABASE_KEY

    # 1. Attempt Supabase Auth Authentication
    if supabase_url and supabase_key:
        try:
            auth_url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
            payload = json.dumps({
                "email": email_clean,
                "password": credentials.password
            }).encode("utf-8")

            req = urllib.request.Request(
                auth_url,
                data=payload,
                headers={
                    "apikey": supabase_key,
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                sb_data = json.loads(resp.read().decode("utf-8"))
                access_token = sb_data.get("access_token")
                refresh_token = sb_data.get("refresh_token")
                expires_in = sb_data.get("expires_in", 3600)

                # Sync user in local CRM DB
                stmt = select(User).where(User.email == email_clean)
                user = db.scalars(stmt).first()
                if not user:
                    role = UserRole.SUPER_ADMIN if "admin" in email_clean else UserRole.CRM_EXECUTIVE
                    full_name = "Super Admin" if role == UserRole.SUPER_ADMIN else "CRM Staff"
                    user = User(
                        email=email_clean,
                        full_name=full_name,
                        role=role.value,
                        hashed_password="SUPABASE_MANAGED_AUTH",
                        is_active=True,
                        last_login_at=datetime.now(timezone.utc)
                    )
                    db.add(user)
                else:
                    user.last_login_at = datetime.now(timezone.utc)
                    user.failed_login_attempts = 0
                db.commit()
                db.refresh(user)

                logger.info(f"Supabase Auth session established for user [{user.email}]")
                return TokenResponse(
                    access_token=access_token,
                    token_type="bearer",
                    refresh_token=refresh_token,
                    expires_in=expires_in,
                    user=UserSummary.model_validate(user)
                )
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.warning(f"Supabase Auth login rejected for {email_clean}: {err_body}")
        except Exception as ex:
            logger.warning(f"Supabase Auth network error, trying local fallback: {ex}")

    # 2. Local Database Verification Fallback
    stmt = select(User).where(User.email == email_clean)
    user = db.scalars(stmt).first()

    if not user:
        raise UnauthorizedError("Invalid email or password.")

    if not user.is_active:
        raise ForbiddenError("Account has been disabled. Please contact hospital administrator.")

    if user.is_locked():
        raise ForbiddenError(f"Account is temporarily locked. Please try again after {LOCKOUT_MINUTES} minutes.")

    if user.hashed_password != "SUPABASE_MANAGED_AUTH" and not verify_password(credentials.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            logger.warning(f"Account {user.email} locked due to {MAX_FAILED_ATTEMPTS} failed attempts.")
        db.commit()
        raise UnauthorizedError("Invalid email or password.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "branch_id": user.branch_id
    }
    access_token = create_access_token(data=token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserSummary.model_validate(user)
    )


@router.post("/refresh", response_model=Dict[str, str], status_code=status.HTTP_200_OK)
async def refresh_session(payload: RefreshTokenRequest):
    """
    Refreshes an active session using Supabase Auth refresh token.
    """
    supabase_url = settings.SUPABASE_URL
    supabase_key = settings.SUPABASE_KEY

    if supabase_url and supabase_key:
        try:
            refresh_url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
            body = json.dumps({"refresh_token": payload.refresh_token}).encode("utf-8")
            req = urllib.request.Request(
                refresh_url,
                data=body,
                headers={
                    "apikey": supabase_key,
                    "Content-Type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token"),
                    "token_type": "bearer"
                }
        except Exception as e:
            logger.error(f"Failed to refresh session with Supabase Auth: {e}")
            raise UnauthorizedError("Session has expired. Please login again.")

    raise UnauthorizedError("Session refresh not supported in current environment.")


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    token: str = Depends(get_token_from_header),
    current_user: User = Depends(get_current_active_user)
):
    """
    Logs out user and invalidates current session.
    """
    revoke_token(token)
    logger.info(f"User {current_user.email} logged out successfully.")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserSummary, status_code=status.HTTP_200_OK)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """
    Returns the authenticated user profile and permissions.
    """
    return UserSummary.model_validate(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Allows authenticated user to change their password."""
    if not verify_password(request.current_password, current_user.hashed_password):
        raise UnauthorizedError("Current password incorrect.")
    
    validate_password_strength(request.new_password)
    current_user.hashed_password = hash_password(request.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"User {current_user.email} changed password.")
    return {"message": "Password changed successfully."}


@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """Initiates a password reset token flow."""
    stmt = select(User).where(User.email == request.email.lower().strip())
    user = db.scalars(stmt).first()
    if user and user.is_active:
        logger.info(f"Password reset requested for {user.email}")
    return {"message": "If this email is registered, password reset instructions have been sent."}


# =============================================================
# RBAC Test Endpoints
# =============================================================
@router.get("/rbac/super-admin-only", status_code=status.HTTP_200_OK)
async def rbac_super_admin(current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN.value))):
    return {"message": "Access granted: Super Admin"}


@router.get("/rbac/hospital-admin", status_code=status.HTTP_200_OK)
async def rbac_hospital_admin(current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN.value, UserRole.HOSPITAL_ADMIN.value))):
    return {"message": "Access granted: Hospital Admin"}


@router.get("/rbac/manager-leads", status_code=status.HTTP_200_OK)
async def rbac_manager_leads(current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN.value, UserRole.HOSPITAL_ADMIN.value, UserRole.CRM_MANAGER.value))):
    return {"message": "Access granted: CRM Manager"}


@router.get("/rbac/doctor-consultations", status_code=status.HTTP_200_OK)
async def rbac_doctor_consultations(current_user: User = Depends(require_roles(UserRole.SUPER_ADMIN.value, UserRole.DOCTOR.value))):
    return {"message": "Access granted: Doctor"}
