"""
Module 4: Hospital and Branch Management Test Suite
"""
import pytest
from app.core.security import hash_password, create_access_token
from app.modules.administration.models import User, UserRole
from app.modules.administration.hospital_models import Hospital, Branch


@pytest.fixture
def admin_headers(db_session):
    admin = User(
        email="admin.hospital@santasa.com",
        full_name="Hospital Admin",
        hashed_password=hash_password("AdminPass123!"),
        role=UserRole.HOSPITAL_ADMIN.value,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    token = create_access_token(data={"sub": admin.id, "email": admin.email, "role": admin.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def exec_headers(db_session):
    exec_user = User(
        email="exec.branch@santasa.com",
        full_name="Branch Executive",
        hashed_password=hash_password("ExecPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(exec_user)
    db_session.commit()
    db_session.refresh(exec_user)
    token = create_access_token(data={"sub": exec_user.id, "email": exec_user.email, "role": exec_user.role})
    return {"Authorization": f"Bearer {token}"}


def test_create_hospital_and_branches(client, admin_headers):
    """Test creating hospital organization and child branches."""
    # 1. Create Hospital
    hosp_resp = client.post("/api/v1/administration/hospitals", headers=admin_headers, json={
        "name": "Santasa IVF & Hospital",
        "code": "SANTASA",
        "city": "Hassan",
        "state": "Karnataka",
        "country": "India",
        "phone": "+918172266000",
        "email": "contact@santasaivf.com"
    })
    assert hosp_resp.status_code == 201
    hospital_data = hosp_resp.json()
    hospital_id = hospital_data["id"]
    assert hospital_data["code"] == "SANTASA"

    # 2. Create Hassan Main Branch
    b1_resp = client.post("/api/v1/administration/branches", headers=admin_headers, json={
        "hospital_id": hospital_id,
        "name": "Hassan Main Hospital",
        "code": "HASSAN",
        "city": "Hassan",
        "phone": "+918172266001",
        "ivr_number": "08047190001",
        "timezone": "Asia/Kolkata"
    })
    assert b1_resp.status_code == 201
    assert b1_resp.json()["code"] == "HASSAN"

    # 3. Create Mysore Center Branch
    b2_resp = client.post("/api/v1/administration/branches", headers=admin_headers, json={
        "hospital_id": hospital_id,
        "name": "Mysore Center",
        "code": "MYSORE",
        "city": "Mysore",
        "phone": "+918212456000",
        "ivr_number": "08047190002"
    })
    assert b2_resp.status_code == 201
    assert b2_resp.json()["code"] == "MYSORE"


def test_duplicate_branch_code_rejection(client, admin_headers):
    """Test system rejects duplicate branch codes with 409 Conflict."""
    # Setup Hospital
    hosp = client.post("/api/v1/administration/hospitals", headers=admin_headers, json={
        "name": "Santasa Hospital",
        "code": "SANTASA_DUP",
        "city": "Hassan"
    }).json()

    # Create Branch 1
    client.post("/api/v1/administration/branches", headers=admin_headers, json={
        "hospital_id": hosp["id"],
        "name": "Bangalore Center",
        "code": "BLR_MAIN",
        "city": "Bangalore"
    })

    # Duplicate Attempt
    dup_resp = client.post("/api/v1/administration/branches", headers=admin_headers, json={
        "hospital_id": hosp["id"],
        "name": "Bangalore Second",
        "code": "BLR_MAIN",
        "city": "Bangalore"
    })
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "DUPLICATE_RESOURCE"


def test_branch_update_and_deactivation(client, admin_headers):
    """Test updating branch attributes and deactivating branch."""
    hosp = client.post("/api/v1/administration/hospitals", headers=admin_headers, json={
        "name": "Santasa Test",
        "code": "SANTASA_UPD",
        "city": "Hassan"
    }).json()

    branch = client.post("/api/v1/administration/branches", headers=admin_headers, json={
        "hospital_id": hosp["id"],
        "name": "Old Branch Name",
        "code": "OLD_BR",
        "city": "Hassan"
    }).json()

    # Update
    update_resp = client.patch(f"/api/v1/administration/branches/{branch['id']}", headers=admin_headers, json={
        "name": "Updated Branch Name",
        "is_active": False
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Branch Name"
    assert update_resp.json()["is_active"] is False


def test_executive_cannot_create_or_edit_branches(client, exec_headers):
    """Test CRM Executive is blocked from branch management operations (403 Forbidden)."""
    resp = client.post("/api/v1/administration/branches", headers=exec_headers, json={
        "hospital_id": "any_id",
        "name": "Unauthorized Branch",
        "code": "UNAUTH_BR",
        "city": "Hassan"
    })
    assert resp.status_code == 403
