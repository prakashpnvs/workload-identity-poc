import time

import jwt
from fastapi.testclient import TestClient

from receiver.app.main import app, EXPECTED_CALLER_WORKLOAD_ID, EXPECTED_ISSUER, JWT_SECRET

client = TestClient(app)


def build_token(*, expired: bool = False):
    now = int(time.time())
    payload = {
        "iss": EXPECTED_ISSUER,
        "sub": EXPECTED_CALLER_WORKLOAD_ID,
        "caller_workload_id": EXPECTED_CALLER_WORKLOAD_ID,
        "aud": "receiver-service",
        "iat": now,
        "exp": now - 30 if expired else now + 120,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def test_valid_token_is_allowed(monkeypatch):
    monkeypatch.setattr("receiver.app.main.fetch_runtime_posture", lambda: {"runtime_posture": "healthy"})
    token = build_token()
    response = client.post("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["caller_identity"] == EXPECTED_CALLER_WORKLOAD_ID


def test_expired_token_is_denied(monkeypatch):
    monkeypatch.setattr("receiver.app.main.fetch_runtime_posture", lambda: {"runtime_posture": "healthy"})
    token = build_token(expired=True)
    response = client.post("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Access denied: token expired"


def test_valid_identity_with_compromised_posture_is_denied(monkeypatch):
    monkeypatch.setattr("receiver.app.main.fetch_runtime_posture", lambda: {"runtime_posture": "compromised"})
    token = build_token()
    response = client.post("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied: runtime integrity compromised"


def test_recovery_restores_access(monkeypatch):
    monkeypatch.setattr("receiver.app.main.fetch_runtime_posture", lambda: {"runtime_posture": "healthy"})
    token = build_token()
    response = client.post("/protected", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
