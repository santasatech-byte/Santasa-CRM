"""
Hospital CRM - Role-Based Access Control (RBAC) & Permission Engine
Defines role hierarchies, permission matrices, and dependency decorators.
"""
from typing import List, Optional, Set
from fastapi import Depends
from app.core.dependencies import get_current_active_user
from app.core.errors import ForbiddenError
from app.modules.administration.models import User, UserRole


# Permission Keys
class Permissions:
    # System & Settings
    MANAGE_SYSTEM = "manage:system"
    MANAGE_INTEGRATIONS = "manage:integrations"
    VIEW_AUDIT_LOGS = "view:audit_logs"

    # Hospital & Branches
    MANAGE_HOSPITALS = "manage:hospitals"
    MANAGE_BRANCHES = "manage:branches"

    # Users & Executives
    MANAGE_USERS = "manage:users"
    VIEW_EXECUTIVE_PERFORMANCE = "view:executive_performance"

    # Leads
    VIEW_ALL_LEADS = "view:all_leads"
    VIEW_TEAM_LEADS = "view:team_leads"
    VIEW_ASSIGNED_LEADS = "view:assigned_leads"
    CREATE_LEAD = "create:lead"
    EDIT_LEAD = "edit:lead"
    REASSIGN_LEAD = "reassign:lead"
    CLOSE_LEAD = "close:lead"

    # Calls & Recordings
    MAKE_CALL = "make:call"
    VIEW_ALL_CALLS = "view:all_calls"
    VIEW_OWN_CALLS = "view:own_calls"
    LISTEN_ALL_RECORDINGS = "listen:all_recordings"
    LISTEN_OWN_RECORDINGS = "listen:own_recordings"

    # Follow-ups & Reminders
    SCHEDULE_FOLLOWUP = "schedule:followup"
    COMPLETE_FOLLOWUP = "complete:followup"
    VIEW_ALL_FOLLOWUPS = "view:all_followups"

    # Appointments & Consultations
    BOOK_APPOINTMENT = "book:appointment"
    VIEW_ASSIGNED_APPOINTMENTS = "view:assigned_appointments"
    RECORD_CONSULTATION_OUTCOME = "record:consultation_outcome"
    RECORD_CONVERSION = "record:conversion"

    # Reports & Exports
    VIEW_REPORTS = "view:reports"
    EXPORT_DATA = "export:data"


# Role-Permission Mapping Matrix
ROLE_PERMISSIONS: dict[str, Set[str]] = {
    UserRole.SUPER_ADMIN.value: {
        Permissions.MANAGE_SYSTEM,
        Permissions.MANAGE_INTEGRATIONS,
        Permissions.VIEW_AUDIT_LOGS,
        Permissions.MANAGE_HOSPITALS,
        Permissions.MANAGE_BRANCHES,
        Permissions.MANAGE_USERS,
        Permissions.VIEW_EXECUTIVE_PERFORMANCE,
        Permissions.VIEW_ALL_LEADS,
        Permissions.VIEW_TEAM_LEADS,
        Permissions.VIEW_ASSIGNED_LEADS,
        Permissions.CREATE_LEAD,
        Permissions.EDIT_LEAD,
        Permissions.REASSIGN_LEAD,
        Permissions.CLOSE_LEAD,
        Permissions.MAKE_CALL,
        Permissions.VIEW_ALL_CALLS,
        Permissions.VIEW_OWN_CALLS,
        Permissions.LISTEN_ALL_RECORDINGS,
        Permissions.LISTEN_OWN_RECORDINGS,
        Permissions.SCHEDULE_FOLLOWUP,
        Permissions.COMPLETE_FOLLOWUP,
        Permissions.VIEW_ALL_FOLLOWUPS,
        Permissions.BOOK_APPOINTMENT,
        Permissions.VIEW_ASSIGNED_APPOINTMENTS,
        Permissions.RECORD_CONSULTATION_OUTCOME,
        Permissions.RECORD_CONVERSION,
        Permissions.VIEW_REPORTS,
        Permissions.EXPORT_DATA,
    },
    UserRole.HOSPITAL_ADMIN.value: {
        Permissions.MANAGE_HOSPITALS,
        Permissions.MANAGE_BRANCHES,
        Permissions.MANAGE_USERS,
        Permissions.VIEW_EXECUTIVE_PERFORMANCE,
        Permissions.VIEW_ALL_LEADS,
        Permissions.VIEW_TEAM_LEADS,
        Permissions.VIEW_ASSIGNED_LEADS,
        Permissions.CREATE_LEAD,
        Permissions.EDIT_LEAD,
        Permissions.REASSIGN_LEAD,
        Permissions.CLOSE_LEAD,
        Permissions.MAKE_CALL,
        Permissions.VIEW_ALL_CALLS,
        Permissions.VIEW_OWN_CALLS,
        Permissions.LISTEN_ALL_RECORDINGS,
        Permissions.LISTEN_OWN_RECORDINGS,
        Permissions.SCHEDULE_FOLLOWUP,
        Permissions.COMPLETE_FOLLOWUP,
        Permissions.VIEW_ALL_FOLLOWUPS,
        Permissions.BOOK_APPOINTMENT,
        Permissions.VIEW_ASSIGNED_APPOINTMENTS,
        Permissions.RECORD_CONSULTATION_OUTCOME,
        Permissions.RECORD_CONVERSION,
        Permissions.VIEW_REPORTS,
        Permissions.EXPORT_DATA,
    },
    UserRole.CRM_MANAGER.value: {
        Permissions.VIEW_EXECUTIVE_PERFORMANCE,
        Permissions.VIEW_TEAM_LEADS,
        Permissions.VIEW_ASSIGNED_LEADS,
        Permissions.CREATE_LEAD,
        Permissions.EDIT_LEAD,
        Permissions.REASSIGN_LEAD,
        Permissions.CLOSE_LEAD,
        Permissions.MAKE_CALL,
        Permissions.VIEW_ALL_CALLS,
        Permissions.VIEW_OWN_CALLS,
        Permissions.LISTEN_ALL_RECORDINGS,
        Permissions.LISTEN_OWN_RECORDINGS,
        Permissions.SCHEDULE_FOLLOWUP,
        Permissions.COMPLETE_FOLLOWUP,
        Permissions.VIEW_ALL_FOLLOWUPS,
        Permissions.BOOK_APPOINTMENT,
        Permissions.VIEW_ASSIGNED_APPOINTMENTS,
        Permissions.RECORD_CONVERSION,
        Permissions.VIEW_REPORTS,
    },
    UserRole.CRM_EXECUTIVE.value: {
        Permissions.VIEW_ASSIGNED_LEADS,
        Permissions.CREATE_LEAD,
        Permissions.EDIT_LEAD,
        Permissions.CLOSE_LEAD,
        Permissions.MAKE_CALL,
        Permissions.VIEW_OWN_CALLS,
        Permissions.LISTEN_OWN_RECORDINGS,
        Permissions.SCHEDULE_FOLLOWUP,
        Permissions.COMPLETE_FOLLOWUP,
        Permissions.BOOK_APPOINTMENT,
        Permissions.RECORD_CONVERSION,
        Permissions.VIEW_REPORTS,
    },
    UserRole.DOCTOR.value: {
        Permissions.VIEW_ASSIGNED_APPOINTMENTS,
        Permissions.RECORD_CONSULTATION_OUTCOME,
    },
}


def user_has_permission(user: User, permission: str) -> bool:
    """Checks if the user's role grants a specific permission."""
    role_perms = ROLE_PERMISSIONS.get(user.role, set())
    return permission in role_perms


def require_roles(*allowed_roles: str):
    """Dependency factory restricting route access to specific roles."""
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{current_user.role}' is not authorized to access this resource."
            )
        return current_user
    return role_checker


def require_permission(permission: str):
    """Dependency factory checking if active user has the required granular permission."""
    def permission_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if not user_has_permission(current_user, permission):
            raise ForbiddenError(
                f"User does not have required permission: '{permission}'."
            )
        return current_user
    return permission_checker


def check_resource_access(user: User, owner_id: Optional[str], branch_id: Optional[str] = None) -> bool:
    """
    Checks if a user has access to a specific record based on ownership and role.
    Super Admins and Hospital Admins have broad access.
    Managers have branch/team access.
    Executives can only access records they own.
    """
    if user.role in [UserRole.SUPER_ADMIN.value, UserRole.HOSPITAL_ADMIN.value]:
        return True
    
    if user.role == UserRole.CRM_MANAGER.value:
        if branch_id and user.branch_id and branch_id != user.branch_id:
            return False
        return True

    if user.role == UserRole.CRM_EXECUTIVE.value:
        return owner_id == user.id or owner_id is None

    return False
