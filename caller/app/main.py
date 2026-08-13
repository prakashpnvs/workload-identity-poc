import json
import os
import time

import jwt
import httpx
from fastapi import FastAPI

CALLER_WORKLOAD_ID = os.getenv("CALLER_WORKLOAD_ID", "workload-caller-01")
JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret")
EXPECTED_ISSUER = os.getenv("EXPECTED_ISSUER", "workload-identity-poc")
RECEIVER_URL = os.getenv("RECEIVER_URL", "http://localhost:8000/protected")

app = FastAPI(title="Caller Service")


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


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}
