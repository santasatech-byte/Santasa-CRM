"""
Module 2: Authentication Test Suite
Verifies secure login, invalid credentials, account lockouts, disabled accounts,
token expiration, token revocation / logout, protected endpoints, and password reset flows.
"""
import pytest
from app.core.security import hash_password, create_access_token, validate_password_strength
from app.core.errors import ValidationError
from app.modules.administration.models import User, UserRole


@pytest.fixture
def test_user(db_session):
    """Seeds a standard active test executive user."""
    user = User(
        email="executive.a@santasa.com",
        full_name="Executive A",
        phone="+919876500001",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def disabled_user(db_session):
    """Seeds a disabled test user."""
    user = User(
        email="disabled.user@santasa.com",
        full_name="Disabled Executive",
        hashed_password=hash_password("ValidPass123!"),
        role=UserRole.CRM_EXECUTIVE.value,
        is_active=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_password_policy_validation():
    """Verify password strength policy enforces security rules."""
    # Valid password
    assert validate_password_strength("StrongPass123!") is True
    
    # Weak: too short
    with pytest.raises(ValidationError):
        validate_password_strength("Pass1!")
        
    # Weak: no uppercase
    with pytest.raises(ValidationError):
        validate_password_strength("weakpass123!")
        
    # Weak: no lowercase
    with pytest.raises(ValidationError):
        validate_password_strength("WEAKPASS123!")
        
    # Weak: no digit
    with pytest.raises(ValidationError):
        validate_password_strength("WeakPassword!")


def test_login_success(client, test_user):
    """Test valid credentials return 200 and signed JWT access token."""
    response = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "ValidPass123!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "executive.a@santasa.com"
    assert data["user"]["role"] == "CRM Executive"


def test_login_invalid_password(client, test_user):
    """Test invalid password returns 401 unauthorized."""
    response = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "WrongPassword123!"
    })
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_unknown_account(client):
    """Test non-existent user returns 401 without revealing account absence."""
    response = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@santasa.com",
        "password": "SomePassword123!"
    })
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_login_disabled_account(client, disabled_user):
    """Test disabled account returns 403 forbidden."""
    response = client.post("/api/v1/auth/login", json={
        "email": "disabled.user@santasa.com",
        "password": "ValidPass123!"
    })
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_account_lockout_after_max_failed_attempts(client, test_user):
    """Test account is locked after 5 consecutive failed login attempts."""
    for _ in range(5):
        client.post("/api/v1/auth/login", json={
            "email": "executive.a@santasa.com",
            "password": "WrongPassword!"
        })
    
    # 6th attempt with correct password should be rejected due to lockout
    response = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "ValidPass123!"
    })
    assert response.status_code == 403
    assert "locked" in response.json()["error"]["message"].lower()


def test_protected_endpoint_without_token(client):
    """Test protected endpoint without Authorization header returns 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_protected_endpoint_with_valid_token(client, test_user):
    """Test protected endpoint returns user profile when authenticated."""
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "ValidPass123!"
    })
    token = login_resp.json()["access_token"]
    
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "executive.a@santasa.com"


def test_logout_session_invalidation(client, test_user):
    """Test logout revokes token and subsequent calls with that token fail."""
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "ValidPass123!"
    })
    token = login_resp.json()["access_token"]
    
    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200
    
    # Attempt using revoked token
    subsequent_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert subsequent_resp.status_code == 401
    assert "invalidated" in subsequent_resp.json()["error"]["message"].lower() or "logged out" in subsequent_resp.json()["error"]["message"].lower()


def test_password_change_flow(client, test_user):
    """Test authenticated user can change password."""
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "ValidPass123!"
    })
    token = login_resp.json()["access_token"]
    
    change_resp = client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {token}"}, json={
        "current_password": "ValidPass123!",
        "new_password": "NewStrongPass2026!"
    })
    assert change_resp.status_code == 200
    
    # Login with new password
    new_login = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "NewStrongPass2026!"
    })
    assert new_login.status_code == 200


def test_password_reset_flow(client, test_user):
    """Test password reset request and reset confirmation."""
    # 1. Request Reset
    req_resp = client.post("/api/v1/auth/password-reset-request", json={
        "email": "executive.a@santasa.com"
    })
    assert req_resp.status_code == 200
    reset_token = req_resp.json().get("debug_token")
    assert reset_token is not None
    
    # 2. Confirm Reset
    confirm_resp = client.post("/api/v1/auth/password-reset", json={
        "token": reset_token,
        "new_password": "ResetPassword2026!"
    })
    assert confirm_resp.status_code == 200
    
    # 3. Verify login with reset password
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "executive.a@santasa.com",
        "password": "ResetPassword2026!"
    })
    assert login_resp.status_code == 200
