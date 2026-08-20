"""
Module 5: Executive Management Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.administration.executive_models import ExecutiveProfile, ExecutiveStatus


@pytest.fixture
def admin_headers(db_session):
    admin = User(
        email="admin.exec@santasa.com",
        full_name="Hospital Admin",
        hashed_password=hash_password("AdminPass123!"),
        role=UserRole.HOSPITAL_ADMIN.value,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    token = create_access_token(data={"sub": admin.id, "email": admin.email, "role": admin.role})
    return {"Authorization": f"Bearer {token}"}, admin


def test_create_executive_user(client, admin_headers):
    """Test admin creates a new executive user with employee ID & telephony settings."""
    headers, _ = admin_headers
    resp = client.post("/api/v1/administration/users", headers=headers, json={
        "email": "priya.sharma@santasa.com",
        "full_name": "Priya Sharma",
        "phone": "+919876500021",
        "password": "ValidPass123!",
        "role": "CRM Executive",
        "employee_id": "EMP-002",
        "telephony_agent_id": "EXO_PRIYA_102",
        "telephony_extension": "102"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "priya.sharma@santasa.com"
    assert data["executive_profile"]["employee_id"] == "EMP-002"
    assert data["executive_profile"]["status"] == "Online"


def test_duplicate_employee_id_rejection(client, admin_headers):
    """Test duplicate employee ID returns 409 Conflict."""
    headers, _ = admin_headers
    client.post("/api/v1/administration/users", headers=headers, json={
        "email": "user1@santasa.com",
        "full_name": "User One",
        "password": "ValidPass123!",
        "employee_id": "EMP-DUP-01"
    })

    dup_resp = client.post("/api/v1/administration/users", headers=headers, json={
        "email": "user2@santasa.com",
        "full_name": "User Two",
        "password": "ValidPass123!",
        "employee_id": "EMP-DUP-01"
    })
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "DUPLICATE_RESOURCE"


def test_executive_status_update_lifecycle(client, admin_headers):
    """Test executive toggles status (Online -> Busy -> Away) and updates availability."""
    headers, _ = admin_headers
    user_data = client.post("/api/v1/administration/users", headers=headers, json={
        "email": "rahul.n@santasa.com",
        "full_name": "Rahul N",
        "password": "ValidPass123!",
        "employee_id": "EMP-003"
    }).json()

    user_id = user_data["id"]
    user_token = create_access_token(data={"sub": user_id, "email": "rahul.n@santasa.com", "role": "CRM Executive"})
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Executive updates own status to Busy
    busy_resp = client.patch(f"/api/v1/administration/executives/{user_id}/status", headers=user_headers, json={
        "status": "Busy"
    })
    assert busy_resp.status_code == 200
    assert busy_resp.json()["status"] == "Busy"
    assert busy_resp.json()["is_available_for_lead_assignment"] is False

    # Executive updates back to Online
    online_resp = client.patch(f"/api/v1/administration/executives/{user_id}/status", headers=user_headers, json={
        "status": "Online"
    })
    assert online_resp.status_code == 200
    assert online_resp.json()["status"] == "Online"
    assert online_resp.json()["is_available_for_lead_assignment"] is True


def test_executive_cannot_modify_peer_status(client, admin_headers):
    """Test executive A cannot modify executive B's status (403 Forbidden)."""
    headers, _ = admin_headers
    u1 = client.post("/api/v1/administration/users", headers=headers, json={
        "email": "exec1@santasa.com", "full_name": "Exec 1", "password": "ValidPass123!", "employee_id": "EMP-P1"
    }).json()
    u2 = client.post("/api/v1/administration/users", headers=headers, json={
        "email": "exec2@santasa.com", "full_name": "Exec 2", "password": "ValidPass123!", "employee_id": "EMP-P2"
    }).json()

    token_u1 = create_access_token(data={"sub": u1["id"], "email": u1["email"], "role": "CRM Executive"})
    resp = client.patch(f"/api/v1/administration/executives/{u2['id']}/status", headers={"Authorization": f"Bearer {token_u1}"}, json={
        "status": "Away"
    })
    assert resp.status_code == 403
