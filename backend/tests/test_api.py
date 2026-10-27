import api
import pytest
from fastapi.testclient import TestClient


client = TestClient(api.app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    api._rate_limit_buckets.clear()


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from AI Agent API!"}


def test_registration_can_be_disabled_via_flag(monkeypatch):
    monkeypatch.setattr(api.settings, "allow_self_registration", False)
    response = client.post(
        "/auth/register",
        json={"employee_id": "EMP-TEST-FLAG", "password": "password-yang-panjang"},
    )
    assert response.status_code == 403
    assert "dinonaktifkan" in response.json()["detail"]


def test_registration_and_login_success():
    test_id = f"TEST-USER-{int(api.time.time())}"
    reg_response = client.post(
        "/auth/register",
        json={
            "employee_id": test_id,
            "display_name": "Test User",
            "password": "password12345",
        },
    )
    assert reg_response.status_code == 200
    token = reg_response.json()["token"]
    assert token

    # Cek session dengan token baru
    session_response = client.get(
        "/auth/session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert session_response.status_code == 200
    assert session_response.json()["user"]["employee_id"] == test_id

    # Cek login ulang dengan kredensial yang didaftarkan
    login_response = client.post(
        "/auth/login",
        json={"employee_id": test_id, "password": "password12345"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["token"]


def test_demo_account_login():
    response = client.post(
        "/auth/login",
        json={"employee_id": "EMP-001", "password": "password12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["employee_id"] == "EMP-001"
    assert data["token"]



def test_employee_list_requires_hr_role():
    result = api.get_database_reply(
        "employee_list", "", "tampilkan semua karyawan", repository=object(),
        requester_id="EMP-001", requester_role="employee",
    )
    assert result["source"].endswith("policy_guard")


def test_hr_can_access_employee_list():
    class Repository:
        def count_employees(self, filter_text):
            return 1

        def list_employees(self, limit, filter_text):
            return [{"employee_id": "EMP-001", "full_name": "Niko Demo", "department": "Engineering", "position": "AI Engineer"}]

    result = api.get_database_reply(
        "employee_list", "", "tampilkan semua karyawan", Repository(),
        requester_id="EMP-003", requester_role="hr",
    )
    assert "EMP-001" in result["reply"]


def test_token_for_deleted_or_unknown_user_is_rejected(monkeypatch):
    monkeypatch.setattr(api, "_get_auth_secret", lambda: b"a-test-secret-that-is-long-enough")
    monkeypatch.setattr(api, "_get_user_by_id", lambda employee_id: None)
    token = api._make_auth_token("EMP-001")

    response = client.get("/auth/session", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Sesi tidak lagi valid."


def test_chat_history_has_strict_size_limit():
    history = [{"role": "user", "content": "x"}] * 13
    response = client.post("/chat", json={"message": "halo", "recent_messages": history})
    assert response.status_code == 422


def test_login_is_rate_limited(monkeypatch):
    monkeypatch.setattr(api, "_get_user_by_id", lambda employee_id: None)
    payload = {"employee_id": "EMP-001", "password": "salah"}
    for _ in range(10):
        assert client.post("/auth/login", json=payload).status_code == 401
    assert client.post("/auth/login", json=payload).status_code == 429


def test_register_validation_and_duplicate():
    # Password too short (< 8 chars)
    res_short = client.post(
        "/auth/register",
        json={"employee_id": "EMP-SHORT", "password": "123"},
    )
    assert res_short.status_code == 422 or res_short.status_code == 400

    # Normal registration
    user_id = f"EMP-DUP-{int(api.time.time())}"
    res1 = client.post(
        "/auth/register",
        json={"employee_id": user_id, "display_name": "Dup Test", "password": "securepassword123"},
    )
    assert res1.status_code == 200

    # Duplicate registration should return 409
    res2 = client.post(
        "/auth/register",
        json={"employee_id": user_id, "display_name": "Dup Test", "password": "securepassword123"},
    )
    assert res2.status_code == 409
    assert "sudah terdaftar" in res2.json()["detail"]


def test_chat_authenticated_new_user(monkeypatch):
    monkeypatch.setattr(api, "run_agent_executor", lambda msg, req: {"reply": f"Halo {req.employee_id}!"})
    test_id = f"EMP-CHAT-{int(api.time.time())}"
    reg = client.post(
        "/auth/register",
        json={"employee_id": test_id, "display_name": "Chat User", "password": "password12345"},
    )
    token = reg.json()["token"]

    chat_res = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Halo AI", "recent_messages": []},
    )
    assert chat_res.status_code == 200
    assert test_id in chat_res.json()["reply"]

