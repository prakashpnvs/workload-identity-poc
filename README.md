# Workload Identity Proof of Concept

## Objective

Develop and demonstrate a runtime-aware workload identity system that continuously evaluates trust across multiple pillars beyond initial authentication. This proof of concept validates that identity and access decisions can be dynamically adjusted when a service's runtime integrity is compromised, closing the gap between initial authentication trust and ongoing operational trust.

## Scope

This prototype consists of two services:

1. **Service A (Consumer)** — Requires authenticated access to protected resources
2. **Service B (Provider)** — Grants or denies access based on continuous trust evaluation

The scope includes:

- Establishing baseline authentication and trust between services
- Simulating a runtime compromise in Service A
- Detecting the compromise through observable signals
- Dynamically revoking or restricting Service A's access
- Recording auditable decisions for compliance and forensics

**Out of Scope:**

- Production-grade implementations or performance optimization
- Kubernetes, container orchestration, or infrastructure-as-code
- Complete application logic, business workflows, or feature development
- Configuration management systems or dynamic policy engines
- Comprehensive monitoring, logging, or alerting infrastructure
- Multi-environment deployment strategies

## Problem Statement

Existing workload-identity solutions (mTLS, OIDC, bearer tokens, cloud-native IAM) successfully establish the identity and execution context of a workload at startup. However, they provide no mechanism to detect when that workload's *runtime integrity* has been compromised after authentication succeeds.

A service may begin execution in a trusted state but later:
- Experience memory corruption or code injection
- Load malicious libraries or dependencies
- Have its environment variables or secrets exfiltrated
- Execute unauthorized operations under the guise of legitimate identity

Today's identity systems grant access based on *who* is calling, not *what state* the caller is in. Once authenticated, a compromised workload retains full access until its credentials expire or are explicitly revoked—a typically manual process.

This proof of concept evaluates whether runtime integrity signals can inform dynamic trust decisions, reducing the exposure window and improving the security posture of service-to-service communication.

## Trust Model

Trust is evaluated across five independent pillars:

### 1. Software Integrity
- Verification that binaries, libraries, and dependencies match expected cryptographic signatures
- Detection of unauthorized code modifications or injected libraries
- **Signal:** Attestation from software bill of materials (SBOM) or code signing verification

### 2. Execution Integrity
- Confirmation that the process is running with the expected permissions, parent process, and runtime environment
- Detection of privilege escalation, unexpected process spawning, or container escape attempts
- **Signal:** Process metadata (UID, GID, parent PID, seccomp status, capabilities)

### 3. Runtime Integrity
- Continuous observation of memory, CPU, I/O, and network behavior at runtime
- Detection of anomalous operations, unauthorized system calls, or unexpected resource access
- **Signal:** Behavioral anomalies, policy violations, or security event triggers

### 4. Identity and Access
- Verification of the caller's cryptographic identity (certificate, token, or key)
- Confirmation that the caller is authorized to perform the requested operation
- **Signal:** Valid credentials and matching access control list (ACL)

### 5. Operational Trust
- Audit trail of trust decisions, access grants, and denials
- Compliance with organizational policy and regulatory requirements
- **Signal:** Tamper-evident logs and decision rationale

A trust decision is affirmative only if *all five pillars remain satisfactory*. Degradation in any pillar triggers a re-evaluation and may result in access denial or revocation.

## Proposed Demonstration

### Phase 1: Baseline Trust
1. Service A authenticates to Service B using standard workload identity (e.g., mTLS or signed JWT)
2. Service B verifies all five trust pillars and grants access
3. Service A makes repeated, authorized requests; Service B honors them

### Phase 2: Simulated Runtime Compromise
1. A controlled fault or injection occurs in Service A's runtime (e.g., unauthorized system call, memory corruption, unexpected process spawn)
2. Runtime integrity monitoring detects the anomaly
3. The compromise is recorded as a runtime integrity violation

### Phase 3: Dynamic Trust Response
1. Service B is notified of or observes the runtime integrity violation
2. Service B re-evaluates the five pillars and downgrades trust
3. Subsequent requests from Service A are denied or restricted
4. An auditable decision record is logged, including:
   - Timestamp of compromise detection
   - Identity of the compromised service
   - Pillar(s) that failed
   - Trust decision (grant, restrict, revoke)
   - Justification and evidence

### Phase 4: Recovery and Audit
1. Service A is restarted or remediated
2. Trust is re-established through the five-pillar evaluation
3. Audit logs demonstrate the complete lifecycle: trust → compromise → revocation → recovery

## Success Criteria

The proof of concept is successful if it demonstrates:

1. **Baseline Authentication Works** — Service A successfully authenticates and accesses Service B without runtime compromise
2. **Compromise Detection** — A simulated runtime integrity violation is detected and surfaced to the access control layer
3. **Dynamic Denial** — Service B denies subsequent requests from Service A after detecting the compromise
4. **Audit Trail** — Access decisions are recorded with sufficient detail to reconstruct what happened, why, and when
5. **Pillar Isolation** — Degradation in one pillar (runtime integrity) does not trigger false positives in others; other pillars remain verifiable and independent
6. **Recovery Path** — After remediation, Service A can re-establish trust and regain access through normal authentication flow

## Architecture Overview

- Service A initiates requests to Service B
- Service B enforces trust evaluation on each request
- A runtime integrity monitor (or injected fault) signals when Service A enters a compromised state
- Trust decisions and audit records are logged centrally
- The system continues operating during and after the compromise scenario

## Phase 1 Implementation (clarified)

This repository contains a Phase 1 baseline implementation of the workload-identity proof of concept. The implementation is intentionally small and portable: two FastAPI services (caller and receiver), short-lived signed JWTs for identity, and a simple runtime posture toggle used to demonstrate how runtime integrity affects access decisions.

Key points:
- Authorization requires both a valid workload identity (signed JWT) and a healthy runtime posture.
- Runtime posture is simulated for demonstration with explicit endpoints; no real attacks or detection systems are included.
- All authorization decisions emit structured JSON audit records with decision reasoning.

### Runtime posture endpoints (demo-only)
- GET  /runtime-posture — show current posture (`healthy` or `compromised`)
- POST /runtime-posture/compromise — mark posture as `compromised`
- POST /runtime-posture/recover — mark posture as `healthy`

When posture is `compromised`, requests with otherwise valid identity receive 403 Forbidden and a runtime-integrity denial in the audit log.

### Running locally (recommended)
1. Create and activate a virtual environment (macOS/Linux):
   ```bash
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

   Notes:
   - On Apple Silicon (arm64) macs, some binary wheels (e.g., pydantic_core) require matching interpreter architecture. If you see an ImportError referencing incompatible architecture, start servers using the same architecture as the wheel, e.g. `arch -arm64 .venv/bin/python -m uvicorn ...`.

2. Start services for local testing (each command runs in its own terminal):
   ```bash
   .venv/bin/python -m uvicorn receiver.app.main:app --host 0.0.0.0 --port 8000
   .venv/bin/python -m uvicorn caller.app.main:app   --host 0.0.0.0 --port 8001
   ```

3. Run the demos:
   - Valid request: `curl http://localhost:8001/demo-valid`
   - Expired/invalid token: `curl http://localhost:8001/demo-invalid`
   - Check posture: `curl http://localhost:8001/runtime-posture`
   - Simulate compromise: `curl -X POST http://localhost:8001/runtime-posture/compromise`
   - Recover: `curl -X POST http://localhost:8001/runtime-posture/recover`

### Running with Docker Compose
1. Install Docker Desktop (macOS/Windows) or Docker Engine (Linux).
2. From the repo root:
   ```bash
   docker compose up --build
   ```
3. The same demo endpoints are exposed on the caller service port (8001). Use `docker compose logs -f` to follow audit output.

### Tests
- Unit/integration tests are provided under `tests/` and can be executed with the virtualenv active:
  ```bash
  python -m pytest -q
  ```
- CI should run the same command and ensure architecture/wheel compatibility in runner images.

### Troubleshooting
- ImportError for `pydantic_core` complaining about incompatible architecture: recreate the venv on the target machine or run the Python binary under the same architecture as the wheel (macOS `arch` helper), or rebuild native wheels from source on that host.
- If ports 8000/8001 are in use, stop the conflicting processes or change ports in the `uvicorn` commands and `docker-compose.yml`.

### Expected audit evidence
Healthy request example:
```json
{"event":"authorization_decision","decision":"allow","reason":"valid workload identity and healthy runtime posture","caller_identity":"workload-caller-01","runtime_posture":"healthy"}
```
Compromised request example:
```json
{"event":"authorization_decision","decision":"deny","reason":"runtime integrity compromised","caller_identity":"workload-caller-01","runtime_posture":"compromised"}
```

### Next steps (suggested)
- Replace the posture toggle with signed remote attestations or a policy engine
- Add time- and signal-based revocation windows and recovery proofs
- Centralize audit logs and add tamper-evidence for compliance

---

**Document Status:** Architecture Proposal + Phase 1 Implementation
**Version:** 1.3
**Date:** 2026
