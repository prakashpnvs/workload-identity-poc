import os
import time
from typing import Dict

import httpx
import jwt
from fastapi import FastAPI

CALLER_WORKLOAD_ID = os.getenv("CALLER_WORKLOAD_ID", "workload-caller-01")
JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret")
EXPECTED_ISSUER = os.getenv("EXPECTED_ISSUER", "workload-identity-poc")
RECEIVER_URL = os.getenv("RECEIVER_URL", "http://localhost:8000/protected")

app = FastAPI(title="Caller Service")

runtime_posture = "healthy"


def create_token(*, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "iss": EXPECTED_ISSUER,
        "sub": CALLER_WORKLOAD_ID,
        "caller_workload_id": CALLER_WORKLOAD_ID,
        "aud": "receiver-service",
        "iat": now,
        "exp": now - 30 if expired else now + 120,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def set_runtime_posture(posture: str) -> Dict[str, str]:
    global runtime_posture
    runtime_posture = posture
    return {"runtime_posture": runtime_posture, "status": "ok"}


@app.get("/runtime-posture")
def get_runtime_posture() -> Dict[str, str]:
    return {"runtime_posture": runtime_posture}


@app.post("/runtime-posture/compromise")
def simulate_compromise() -> Dict[str, str]:
    return set_runtime_posture("compromised")


@app.post("/runtime-posture/recover")
def recover_runtime() -> Dict[str, str]:
    return set_runtime_posture("healthy")


@app.get("/demo-valid")
def demo_valid() -> dict:
    token = create_token()
    response = httpx.post(RECEIVER_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return {
        "token_source": "valid",
        "status_code": response.status_code,
        "response": response.json(),
    }


@app.get("/demo-invalid")
def demo_invalid() -> dict:
    token = create_token(expired=True)
    response = httpx.post(RECEIVER_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return {
        "token_source": "expired",
        "status_code": response.status_code,
        "response": response.json(),
    }


@app.get("/demo-compromised")
def demo_compromised() -> dict:
    token = create_token()
    response = httpx.post(RECEIVER_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return {
        "token_source": "valid",
        "runtime_posture_seen_by_receiver": "compromised",
        "status_code": response.status_code,
        "response": response.json(),
    }


@app.get("/demo-recover")
def demo_recover() -> dict:
    response = httpx.post(f"{RECEIVER_URL.rsplit('/', 1)[0]}/runtime-posture/recover", timeout=10)
    token = create_token()
    final_response = httpx.post(RECEIVER_URL, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return {
        "recovery_status": response.status_code,
        "status_code": final_response.status_code,
        "response": final_response.json(),
    }


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "runtime_posture": runtime_posture}
