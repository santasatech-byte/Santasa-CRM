"""
Hospital CRM - Executive & User Management Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.modules.administration.executive_models import ExecutiveStatus


class ExecutiveProfileSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    employee_id: str
    manager_id: Optional[str] = None
    telephony_agent_id: Optional[str] = None
    telephony_extension: Optional[str] = None
    status: str
    last_status_change_at: datetime
    max_active_leads_capacity: int
    is_available_for_lead_assignment: bool


class UserDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    branch_id: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    executive_profile: Optional[ExecutiveProfileSummary] = None


class CreateExecutiveUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2)
    phone: Optional[str] = None
    password: str = Field(..., min_length=8)
    role: str = "CRM Executive"
    branch_id: Optional[str] = None
    
    # Executive profile fields
    employee_id: str = Field(..., min_length=2)
    manager_id: Optional[str] = None
    telephony_agent_id: Optional[str] = None
    telephony_extension: Optional[str] = None
    max_active_leads_capacity: int = 50


class UpdateExecutiveStatusRequest(BaseModel):
    status: ExecutiveStatus


class UpdateUserRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    branch_id: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    manager_id: Optional[str] = None
    telephony_agent_id: Optional[str] = None
    telephony_extension: Optional[str] = None
    is_available_for_lead_assignment: Optional[bool] = None
