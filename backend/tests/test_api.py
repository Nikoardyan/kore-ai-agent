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


def test_public_registration_is_disabled_by_default():
    response = client.post(
        "/auth/register",
        json={"employee_id": "EMP-001", "password": "password-yang-panjang"},
    )
    assert response.status_code == 403
    assert "dinonaktifkan" in response.json()["detail"]


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
