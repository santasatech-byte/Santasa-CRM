"""
Hospital CRM - Hospital & Branch Administration API Router
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_active_user
from app.core.permissions import require_permission, Permissions
from app.core.errors import NotFoundError, DuplicateResourceError
from app.modules.administration.models import User
from app.modules.administration.hospital_models import Hospital, Branch
from app.modules.administration.hospital_schemas import (
    HospitalSummary,
    CreateHospitalRequest,
    UpdateHospitalRequest,
    BranchSummary,
    CreateBranchRequest,
    UpdateBranchRequest,
)

router = APIRouter(prefix="/administration", tags=["Hospital & Branch Management"])


# ==========================================
# Hospital Endpoints
# ==========================================

@router.post("/hospitals", response_model=HospitalSummary, status_code=status.HTTP_201_CREATED)
async def create_hospital(
    request: CreateHospitalRequest,
    current_user: User = Depends(require_permission(Permissions.MANAGE_HOSPITALS)),
    db: Session = Depends(get_db)
):
    """Creates a new hospital organization (Admin only)."""
    stmt = select(Hospital).where(Hospital.code == request.code.upper().strip())
    existing = db.scalars(stmt).first()
    if existing:
        raise DuplicateResourceError("Hospital", "code", request.code)

    hospital = Hospital(
        name=request.name.strip(),
        code=request.code.upper().strip(),
        address=request.address,
        city=request.city,
        state=request.state,
        country=request.country,
        phone=request.phone,
        email=request.email,
        website=request.website,
        is_active=request.is_active
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return HospitalSummary.model_validate(hospital)


@router.get("/hospitals", response_model=List[HospitalSummary], status_code=status.HTTP_200_OK)
async def list_hospitals(
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists hospitals."""
    stmt = select(Hospital)
    if active_only:
        stmt = stmt.where(Hospital.is_active == True)
    hospitals = db.scalars(stmt).all()
    return [HospitalSummary.model_validate(h) for h in hospitals]


@router.get("/hospitals/{hospital_id}", response_model=HospitalSummary, status_code=status.HTTP_200_OK)
async def get_hospital(
    hospital_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves hospital details by ID."""
    stmt = select(Hospital).where(Hospital.id == hospital_id)
    hospital = db.scalars(stmt).first()
    if not hospital:
        raise NotFoundError("Hospital", hospital_id)
    return HospitalSummary.model_validate(hospital)


@router.patch("/hospitals/{hospital_id}", response_model=HospitalSummary, status_code=status.HTTP_200_OK)
async def update_hospital(
    hospital_id: str,
    request: UpdateHospitalRequest,
    current_user: User = Depends(require_permission(Permissions.MANAGE_HOSPITALS)),
    db: Session = Depends(get_db)
):
    """Updates hospital attributes (Admin only)."""
    stmt = select(Hospital).where(Hospital.id == hospital_id)
    hospital = db.scalars(stmt).first()
    if not hospital:
        raise NotFoundError("Hospital", hospital_id)

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(hospital, key, value)

    db.commit()
    db.refresh(hospital)
    return HospitalSummary.model_validate(hospital)


# ==========================================
# Branch Endpoints
# ==========================================

@router.post("/branches", response_model=BranchSummary, status_code=status.HTTP_201_CREATED)
async def create_branch(
    request: CreateBranchRequest,
    current_user: User = Depends(require_permission(Permissions.MANAGE_BRANCHES)),
    db: Session = Depends(get_db)
):
    """Creates a new branch associated with a hospital (Admin only)."""
    # Verify parent hospital exists
    hosp_stmt = select(Hospital).where(Hospital.id == request.hospital_id)
    hospital = db.scalars(hosp_stmt).first()
    if not hospital:
        raise NotFoundError("Hospital", request.hospital_id)

    # Check duplicate branch code
    stmt = select(Branch).where(Branch.code == request.code.upper().strip())
    existing = db.scalars(stmt).first()
    if existing:
        raise DuplicateResourceError("Branch", "code", request.code)

    branch = Branch(
        hospital_id=request.hospital_id,
        name=request.name.strip(),
        code=request.code.upper().strip(),
        address=request.address,
        city=request.city,
        state=request.state,
        country=request.country,
        phone=request.phone,
        ivr_number=request.ivr_number,
        timezone=request.timezone,
        is_active=request.is_active
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return BranchSummary.model_validate(branch)


@router.get("/branches", response_model=List[BranchSummary], status_code=status.HTTP_200_OK)
async def list_branches(
    hospital_id: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Lists branches, optionally filtered by hospital."""
    stmt = select(Branch)
    if hospital_id:
        stmt = stmt.where(Branch.hospital_id == hospital_id)
    if active_only:
        stmt = stmt.where(Branch.is_active == True)
    branches = db.scalars(stmt).all()
    return [BranchSummary.model_validate(b) for b in branches]


@router.get("/branches/{branch_id}", response_model=BranchSummary, status_code=status.HTTP_200_OK)
async def get_branch(
    branch_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves branch details by ID."""
    stmt = select(Branch).where(Branch.id == branch_id)
    branch = db.scalars(stmt).first()
    if not branch:
        raise NotFoundError("Branch", branch_id)
    return BranchSummary.model_validate(branch)


@router.patch("/branches/{branch_id}", response_model=BranchSummary, status_code=status.HTTP_200_OK)
async def update_branch(
    branch_id: str,
    request: UpdateBranchRequest,
    current_user: User = Depends(require_permission(Permissions.MANAGE_BRANCHES)),
    db: Session = Depends(get_db)
):
    """Updates branch attributes (Admin only)."""
    stmt = select(Branch).where(Branch.id == branch_id)
    branch = db.scalars(stmt).first()
    if not branch:
        raise NotFoundError("Branch", branch_id)

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(branch, key, value)

    db.commit()
    db.refresh(branch)
    return BranchSummary.model_validate(branch)
