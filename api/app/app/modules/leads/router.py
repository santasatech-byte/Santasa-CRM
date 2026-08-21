"""
Hospital CRM - Lead Management API Router
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions, check_resource_access
from app.core.errors import NotFoundError, ForbiddenError, ValidationError
from app.core.logging import logger
from app.adapters.telephony_base import MockTelephonyAdapter
from app.modules.administration.models import User, UserRole
from app.modules.leads.models import Lead, LeadStatusEnum, LeadPriorityEnum, LeadSourceEnum
from app.modules.leads.schemas import (
    LeadSummary,
    CreateLeadRequest,
    UpdateLeadRequest,
    LeadSearchRequest,
)

router = APIRouter(prefix="/leads", tags=["Lead Management"])
telephony_adapter = MockTelephonyAdapter()


@router.post("", response_model=LeadSummary, status_code=status.HTTP_201_CREATED)
async def create_lead(
    request: CreateLeadRequest,
    current_user: User = Depends(require_permission(Permissions.CREATE_LEAD)),
    db: Session = Depends(get_db)
):
    """Creates a new patient lead with automatic phone normalization."""
    normalized_phone = telephony_adapter.normalize_phone_number(request.primary_phone)
    if not normalized_phone or len(normalized_phone) < 8:
        raise ValidationError("Invalid primary phone number format.")

    # Default assigned executive to current user if executive role and not specified
    assigned_exec = request.assigned_executive_id
    if not assigned_exec and current_user.role == UserRole.CRM_EXECUTIVE.value:
        assigned_exec = current_user.id

    lead = Lead(
        patient_name=request.patient_name.strip(),
        primary_phone=request.primary_phone.strip(),
        normalized_phone=normalized_phone,
        secondary_phone=request.secondary_phone,
        email=request.email.lower() if request.email else None,
        gender=request.gender,
        age=request.age,
        location=request.location,
        city=request.city,
        lead_source=request.lead_source.value,
        campaign=request.campaign,
        department=request.department,
        service_interested=request.service_interested,
        branch_id=request.branch_id or current_user.branch_id,
        assigned_executive_id=assigned_exec,
        lead_status=LeadStatusEnum.NEW.value,
        priority=request.priority.value,
        next_followup_at=request.next_followup_at,
        notes=request.notes,
        created_by=current_user.id,
        updated_by=current_user.id,
        is_archived=False
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    logger.info(f"Lead created successfully id={lead.id} patient='{lead.patient_name}' phone={lead.normalized_phone} by user {current_user.email}.")
    return LeadSummary.model_validate(lead)


@router.get("", response_model=List[LeadSummary], status_code=status.HTTP_200_OK)
async def list_leads(
    lead_status: Optional[str] = None,
    lead_source: Optional[str] = None,
    priority: Optional[str] = None,
    branch_id: Optional[str] = None,
    assigned_executive_id: Optional[str] = None,
    include_archived: bool = False,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lists leads with role-based scoping:
    - Super Admin & Hospital Admin: All leads / filtered by branch
    - CRM Manager: Team / Branch leads
    - CRM Executive: Assigned leads only
    """
    stmt = select(Lead)
    
    if not include_archived:
        stmt = stmt.where(Lead.is_archived == False)

    # Scoping by role
    if current_user.role == UserRole.CRM_EXECUTIVE.value:
        stmt = stmt.where(
            or_(
                Lead.assigned_executive_id == current_user.id,
                Lead.assigned_executive_id.is_(None)
            )
        )
    elif current_user.role == UserRole.CRM_MANAGER.value and current_user.branch_id:
        stmt = stmt.where(Lead.branch_id == current_user.branch_id)

    # Dynamic filters
    if lead_status:
        stmt = stmt.where(Lead.lead_status == lead_status)
    if lead_source:
        stmt = stmt.where(Lead.lead_source == lead_source)
    if priority:
        stmt = stmt.where(Lead.priority == priority)
    if branch_id:
        stmt = stmt.where(Lead.branch_id == branch_id)
    if assigned_executive_id and current_user.role != UserRole.CRM_EXECUTIVE.value:
        stmt = stmt.where(Lead.assigned_executive_id == assigned_executive_id)

    stmt = stmt.order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    leads = db.scalars(stmt).all()
    return [LeadSummary.model_validate(l) for l in leads]


@router.get("/{lead_id}", response_model=LeadSummary, status_code=status.HTTP_200_OK)
async def get_lead(
    lead_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves lead detail with ownership permission check."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to view this lead.")

    return LeadSummary.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadSummary, status_code=status.HTTP_200_OK)
async def update_lead(
    lead_id: str,
    request: UpdateLeadRequest,
    current_user: User = Depends(require_permission(Permissions.EDIT_LEAD)),
    db: Session = Depends(get_db)
):
    """Updates lead attributes and status with permission verification."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to update this lead.")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key in ["lead_source", "lead_status", "priority"] and value is not None:
            setattr(lead, key, value.value if hasattr(value, "value") else value)
        else:
            setattr(lead, key, value)

    lead.updated_by = current_user.id
    db.commit()
    db.refresh(lead)

    logger.info(f"Updated lead id={lead.id} by user {current_user.email}.")
    return LeadSummary.model_validate(lead)


@router.post("/search", response_model=List[LeadSummary], status_code=status.HTTP_200_OK)
async def search_leads(
    search_params: LeadSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Fast search across phone number, patient name, and lead ID."""
    raw_query = search_params.query.strip()
    normalized_query = telephony_adapter.normalize_phone_number(raw_query)

    filters = [
        Lead.patient_name.ilike(f"%{raw_query}%"),
        Lead.primary_phone.ilike(f"%{raw_query}%"),
        Lead.normalized_phone.ilike(f"%{normalized_query}%"),
        Lead.id == raw_query
    ]

    stmt = select(Lead).where(or_(*filters))

    # Executive scope
    if current_user.role == UserRole.CRM_EXECUTIVE.value:
        stmt = stmt.where(Lead.assigned_executive_id == current_user.id)
    elif search_params.branch_id:
        stmt = stmt.where(Lead.branch_id == search_params.branch_id)

    stmt = stmt.limit(search_params.limit)
    leads = db.scalars(stmt).all()
    return [LeadSummary.model_validate(l) for l in leads]


# ==========================================
# Lead Assignment Endpoints
# ==========================================
from app.modules.leads.assignment_service import LeadAssignmentService
from app.modules.leads.assignment_models import LeadAssignmentHistory
from app.modules.leads.schemas import ManualAssignRequest, AutoAssignRequest, LeadAssignmentHistorySummary

@router.post("/{lead_id}/assign", response_model=LeadSummary, status_code=status.HTTP_200_OK)
async def assign_lead_manually(
    lead_id: str,
    request: ManualAssignRequest,
    current_user: User = Depends(require_permission(Permissions.REASSIGN_LEAD)),
    db: Session = Depends(get_db)
):
    """Manually assigns/reassigns lead to a designated executive (Manager/Admin)."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    LeadAssignmentService.assign_manual(
        db=db,
        lead=lead,
        new_executive_id=request.new_executive_id,
        assigned_by_user_id=current_user.id,
        reason=request.reason
    )
    return LeadSummary.model_validate(lead)


@router.post("/{lead_id}/auto-assign", response_model=LeadSummary, status_code=status.HTTP_200_OK)
async def auto_assign_lead(
    lead_id: str,
    request: AutoAssignRequest,
    current_user: User = Depends(require_permission(Permissions.REASSIGN_LEAD)),
    db: Session = Depends(get_db)
):
    """Triggers round-robin automated distribution to the next available online executive."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    LeadAssignmentService.assign_round_robin(
        db=db,
        lead=lead,
        assigned_by_user_id=current_user.id,
        reason=request.reason
    )
    return LeadSummary.model_validate(lead)


@router.get("/{lead_id}/assignment-history", response_model=List[LeadAssignmentHistorySummary], status_code=status.HTTP_200_OK)
async def get_lead_assignment_history(
    lead_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves immutable chronological assignment audit logs for a lead."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to view this lead's assignment history.")

    hist_stmt = (
        select(LeadAssignmentHistory)
        .where(LeadAssignmentHistory.lead_id == lead_id)
        .order_by(LeadAssignmentHistory.assigned_at.desc())
    )
    histories = db.scalars(hist_stmt).all()
    return [LeadAssignmentHistorySummary.model_validate(h) for h in histories]


# ==========================================
# Lead Status Workflow Endpoints
# ==========================================
from app.modules.leads.status_service import LeadStatusService
from app.modules.leads.status_models import LeadStatusHistory
from app.modules.leads.schemas import ChangeLeadStatusRequest, LeadStatusHistorySummary

@router.post("/{lead_id}/status", response_model=LeadSummary, status_code=status.HTTP_200_OK)
async def update_lead_status_endpoint(
    lead_id: str,
    request: ChangeLeadStatusRequest,
    current_user: User = Depends(require_permission(Permissions.EDIT_LEAD)),
    db: Session = Depends(get_db)
):
    """Transitions lead status with state validation and immutable status audit logging."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to update this lead's status.")

    LeadStatusService.change_lead_status(
        db=db,
        lead=lead,
        new_status=request.new_status,
        changed_by_user_id=current_user.id,
        reason=request.reason,
        competitor_name=request.competitor_name,
        next_followup_at=request.next_followup_at
    )
    return LeadSummary.model_validate(lead)


@router.get("/{lead_id}/status-history", response_model=List[LeadStatusHistorySummary], status_code=status.HTTP_200_OK)
async def get_lead_status_history(
    lead_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves immutable chronological status audit history for a lead."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to view this lead's status history.")

    hist_stmt = (
        select(LeadStatusHistory)
        .where(LeadStatusHistory.lead_id == lead_id)
        .order_by(LeadStatusHistory.changed_at.desc())
    )
    histories = db.scalars(hist_stmt).all()
    return [LeadStatusHistorySummary.model_validate(h) for h in histories]


# ==========================================
# Activity Timeline Endpoints
# ==========================================
from app.modules.leads.activity_service import LeadActivityService
from app.modules.leads.activity_models import LeadActivity, ActivityTypeEnum
from app.modules.leads.schemas import AddLeadNoteRequest, LeadActivitySummary

@router.post("/{lead_id}/notes", response_model=LeadActivitySummary, status_code=status.HTTP_201_CREATED)
async def add_lead_note(
    lead_id: str,
    request: AddLeadNoteRequest,
    current_user: User = Depends(require_permission(Permissions.EDIT_LEAD)),
    db: Session = Depends(get_db)
):
    """Appends an executive note to the lead's chronological timeline."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to add notes to this lead.")

    activity = LeadActivityService.log_activity(
        db=db,
        lead_id=lead_id,
        activity_type=ActivityTypeEnum.NOTE_ADDED,
        title="Executive Note Added",
        description=request.note.strip(),
        performed_by_user_id=current_user.id
    )
    return LeadActivitySummary.model_validate(activity)


@router.get("/{lead_id}/timeline", response_model=List[LeadActivitySummary], status_code=status.HTTP_200_OK)
async def get_lead_timeline(
    lead_id: str,
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves unified chronological timeline for a lead."""
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = db.scalars(stmt).first()
    if not lead:
        raise NotFoundError("Lead", lead_id)

    if not check_resource_access(current_user, owner_id=lead.assigned_executive_id, branch_id=lead.branch_id):
        raise ForbiddenError("You are not authorized to view this lead's timeline.")

    activities = LeadActivityService.get_timeline(db=db, lead_id=lead_id, limit=limit, offset=offset)
    return [LeadActivitySummary.model_validate(a) for a in activities]



