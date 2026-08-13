import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

JWT_SECRET = os.getenv("JWT_SECRET", "demo-secret")
EXPECTED_ISSUER = os.getenv("EXPECTED_ISSUER", "workload-identity-poc")
EXPECTED_CALLER_WORKLOAD_ID = os.getenv("EXPECTED_CALLER_WORKLOAD_ID", "workload-caller-01")
RECEIVER_AUDIENCE = os.getenv("RECEIVER_AUDIENCE", "receiver-service")

logger = logging.getLogger("receiver.audit")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

app = FastAPI(title="Receiver Service")


class AccessDecision(BaseModel):
    decision: str
    reason: str
    caller_identity: Optional[str]
    timestamp: str
    request_path: str
    token_issuer: Optional[str] = None
    token_subject: Optional[str] = None


def emit_audit_decision(decision: str, reason: str, caller_identity: Optional[str], request_path: str, *, token_issuer: Optional[str] = None, token_subject: Optional[str] = None) -> None:
    record = {
        "event": "authorization_decision",
        "decision": decision,
        "reason": reason,
        "caller_identity": caller_identity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_path": request_path,
        "token_issuer": token_issuer,
        "token_subject": token_subject,
    }
    logger.info(json.dumps(record, separators=(",", ":")))


def parse_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access denied: missing bearer token",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access denied: invalid authorization header",
        )
    return token


@app.post("/protected")
def protected_endpoint(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    request_path = "/protected"
    try:
        token = parse_bearer_token(authorization)
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["iss", "sub", "exp", "aud"]},
            audience=RECEIVER_AUDIENCE,
            issuer=EXPECTED_ISSUER,
        )
    except jwt.ExpiredSignatureError:
        emit_audit_decision("deny", "token expired", None, request_path)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access denied: token expired")
    except Exception as exc:
        emit_audit_decision("deny", f"invalid token: {type(exc).__name__}", None, request_path)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access denied: invalid token")

    caller_identity = payload.get("caller_workload_id") or payload.get("sub")
    token_issuer = payload.get("iss")
    token_subject = payload.get("sub")

    if payload.get("iss") != EXPECTED_ISSUER:
        emit_audit_decision("deny", "issuer mismatch", caller_identity, request_path, token_issuer=token_issuer, token_subject=token_subject)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access denied: issuer mismatch")

    if payload.get("aud") != RECEIVER_AUDIENCE:
        emit_audit_decision("deny", "audience mismatch", caller_identity, request_path, token_issuer=token_issuer, token_subject=token_subject)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access denied: audience mismatch")

    if caller_identity != EXPECTED_CALLER_WORKLOAD_ID:
        emit_audit_decision("deny", "unexpected caller workload identity", caller_identity, request_path, token_issuer=token_issuer, token_subject=token_subject)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access denied: unexpected caller workload identity")

    emit_audit_decision("allow", "valid workload identity token", caller_identity, request_path, token_issuer=token_issuer, token_subject=token_subject)
    return {
        "message": "Protected resource accessed",
        "caller_identity": caller_identity,
        "issuer": token_issuer,
        "expires_at": datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat(),
    }


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
