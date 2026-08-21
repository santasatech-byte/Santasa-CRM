"""
Hospital CRM - User & Executive Management API Router
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions
from app.core.security import hash_password, validate_password_strength
from app.core.errors import NotFoundError, DuplicateResourceError, ForbiddenError
from app.core.logging import logger
from app.modules.administration.models import User, UserRole
from app.modules.administration.executive_models import ExecutiveProfile, ExecutiveStatus
from app.modules.administration.executive_schemas import (
    UserDetailResponse,
    CreateExecutiveUserRequest,
    UpdateExecutiveStatusRequest,
    UpdateUserRequest,
    ExecutiveProfileSummary
)

router = APIRouter(prefix="/administration", tags=["User & Executive Management"])


@router.post("/users", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_user_and_executive(
    request: CreateExecutiveUserRequest,
    current_user: User = Depends(require_permission(Permissions.MANAGE_USERS)),
    db: Session = Depends(get_db)
):
    """Creates a new CRM user and associated ExecutiveProfile (Admin only)."""
    # Check duplicate email
    stmt = select(User).where(User.email == request.email.lower().strip())
    if db.scalars(stmt).first():
        raise DuplicateResourceError("User", "email", request.email)

    # Check duplicate employee_id
    emp_stmt = select(ExecutiveProfile).where(ExecutiveProfile.employee_id == request.employee_id.strip())
    if db.scalars(emp_stmt).first():
        raise DuplicateResourceError("ExecutiveProfile", "employee_id", request.employee_id)

    validate_password_strength(request.password)

    # 1. Create User
    user = User(
        email=request.email.lower().strip(),
        full_name=request.full_name.strip(),
        phone=request.phone,
        hashed_password=hash_password(request.password),
        role=request.role,
        branch_id=request.branch_id,
        is_active=True
    )
    db.add(user)
    db.flush()

    # 2. Create Executive Profile
    profile = ExecutiveProfile(
        user_id=user.id,
        employee_id=request.employee_id.strip(),
        manager_id=request.manager_id,
        telephony_agent_id=request.telephony_agent_id,
        telephony_extension=request.telephony_extension,
        status=ExecutiveStatus.ONLINE.value,
        max_active_leads_capacity=request.max_active_leads_capacity,
        is_available_for_lead_assignment=True
    )
    db.add(profile)
    db.commit()
    db.refresh(user)

    logger.info(f"Created new user {user.email} with Employee ID {profile.employee_id}.")
    
    # Return mapped response
    return UserDetailResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        branch_id=user.branch_id,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        executive_profile=ExecutiveProfileSummary.model_validate(profile)
    )


@router.get("/users", response_model=List[UserDetailResponse], status_code=status.HTTP_200_OK)
async def list_users(
    role: Optional[str] = None,
    branch_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists CRM users with filters."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if branch_id:
        stmt = stmt.where(User.branch_id == branch_id)
    if active_only:
        stmt = stmt.where(User.is_active == True)

    users = db.scalars(stmt).all()
    results = []
    
    for u in users:
        prof_stmt = select(ExecutiveProfile).where(ExecutiveProfile.user_id == u.id)
        prof = db.scalars(prof_stmt).first()
        
        if manager_id and prof and prof.manager_id != manager_id:
            continue
            
        results.append(UserDetailResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            phone=u.phone,
            role=u.role,
            branch_id=u.branch_id,
            is_active=u.is_active,
            last_login_at=u.last_login_at,
            executive_profile=ExecutiveProfileSummary.model_validate(prof) if prof else None
        ))
        
    return results


@router.patch("/executives/{user_id}/status", response_model=ExecutiveProfileSummary, status_code=status.HTTP_200_OK)
async def update_executive_status(
    user_id: str,
    request: UpdateExecutiveStatusRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Updates executive real-time availability status (Online/Away/Busy/Offline).
    Executives can update their own status; Managers/Admins can update team status.
    """
    # Permission check: Own status or Manager/Admin
    if current_user.id != user_id and current_user.role not in [
        UserRole.SUPER_ADMIN.value,
        UserRole.HOSPITAL_ADMIN.value,
        UserRole.CRM_MANAGER.value
    ]:
        raise ForbiddenError("You cannot modify another executive's status.")

    stmt = select(ExecutiveProfile).where(ExecutiveProfile.user_id == user_id)
    profile = db.scalars(stmt).first()
    if not profile:
        raise NotFoundError("ExecutiveProfile", user_id)

    profile.status = request.status.value
    profile.last_status_change_at = datetime.now(timezone.utc)
    
    # Auto-adjust assignment availability: only Online executives receive auto round-robin leads
    profile.is_available_for_lead_assignment = (request.status == ExecutiveStatus.ONLINE)

    db.commit()
    db.refresh(profile)
    logger.info(f"Updated status for executive user_id={user_id} to [{profile.status}].")
    return ExecutiveProfileSummary.model_validate(profile)
