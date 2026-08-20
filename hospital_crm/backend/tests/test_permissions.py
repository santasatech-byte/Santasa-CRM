"""
Module 3: Roles and Permissions RBAC Test Suite
Validates authorization, privilege escalation rejection, and granular role permissions
for Super Admin, Hospital Admin, CRM Manager, CRM Executive, and Doctor.
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.core.permissions import check_resource_access, user_has_permission, Permissions
from app.modules.administration.models import User, UserRole


def create_user_with_role(db_session, email: str, role: str) -> str:
    """Helper to create user with specific role and return JWT auth header."""
    user = User(
        email=email,
        full_name=f"Test {role}",
        hashed_password=hash_password("ValidPass123!"),
        role=role,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    token = create_access_token(data={"sub": user.id, "email": user.email, "role": user.role})
    return token, user


def test_super_admin_permissions(client, db_session):
    """Super Admin must have unrestricted access across all system endpoints."""
    token, user = create_user_with_role(db_session, "superadmin@santasa.com", UserRole.SUPER_ADMIN.value)
    headers = {"Authorization": f"Bearer {token}"}
    
    assert client.get("/api/v1/auth/rbac/super-admin-only", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/rbac/hospital-admin", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/rbac/manager-leads", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/rbac/doctor-consultations", headers=headers).status_code == 200


def test_hospital_admin_permissions(client, db_session):
    """Hospital Admin has hospital management access but is blocked from super-admin operations."""
    token, user = create_user_with_role(db_session, "hospadmin@santasa.com", UserRole.HOSPITAL_ADMIN.value)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Allowed
    assert client.get("/api/v1/auth/rbac/hospital-admin", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/rbac/manager-leads", headers=headers).status_code == 200
    
    # Blocked (Super Admin only)
    resp = client.get("/api/v1/auth/rbac/super-admin-only", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_crm_manager_permissions(client, db_session):
    """CRM Manager has team and lead reassign access but is blocked from hospital/system admin."""
    token, user = create_user_with_role(db_session, "manager@santasa.com", UserRole.CRM_MANAGER.value)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Allowed
    assert client.get("/api/v1/auth/rbac/manager-leads", headers=headers).status_code == 200
    
    # Blocked
    assert client.get("/api/v1/auth/rbac/hospital-admin", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/rbac/super-admin-only", headers=headers).status_code == 403


def test_crm_executive_restrictions(client, db_session):
    """CRM Executive cannot access administrative, manager-level, or doctor consultation outcome routes."""
    token, user = create_user_with_role(db_session, "exec@santasa.com", UserRole.CRM_EXECUTIVE.value)
    headers = {"Authorization": f"Bearer {token}"}
    
    assert client.get("/api/v1/auth/rbac/super-admin-only", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/rbac/hospital-admin", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/rbac/manager-leads", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/rbac/doctor-consultations", headers=headers).status_code == 403


def test_doctor_permissions(client, db_session):
    """Doctor role can record consultation outcomes but cannot access lead reassignment or CRM admin."""
    token, user = create_user_with_role(db_session, "doctor@santasa.com", UserRole.DOCTOR.value)
    headers = {"Authorization": f"Bearer {token}"}
    
    # Allowed
    assert client.get("/api/v1/auth/rbac/doctor-consultations", headers=headers).status_code == 200
    
    # Blocked
    assert client.get("/api/v1/auth/rbac/manager-leads", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/rbac/hospital-admin", headers=headers).status_code == 403
    assert client.get("/api/v1/auth/rbac/super-admin-only", headers=headers).status_code == 403


def test_resource_level_access_checks(db_session):
    """Verify resource-level ownership isolation between executives."""
    _, exec_a = create_user_with_role(db_session, "exec.a@santasa.com", UserRole.CRM_EXECUTIVE.value)
    _, exec_b = create_user_with_role(db_session, "exec.b@santasa.com", UserRole.CRM_EXECUTIVE.value)
    _, mgr = create_user_with_role(db_session, "mgr@santasa.com", UserRole.CRM_MANAGER.value)
    
    # Executive A owns Lead 1
    assert check_resource_access(exec_a, owner_id=exec_a.id) is True
    # Executive B cannot access Lead 1
    assert check_resource_access(exec_b, owner_id=exec_a.id) is False
    # Manager can access Lead 1
    assert check_resource_access(mgr, owner_id=exec_a.id) is True
