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

## Phase 2 Runtime Posture Trust Rule

This repository now implements the Phase 2 trust rule for the existing proof of concept.

Trust is granted only when both conditions are true:
- the caller workload identity is valid, and
- the caller runtime posture is `healthy`

Access is denied when the workload identity remains valid but the runtime posture is `compromised`.

### Runtime posture model
- Default caller posture: `healthy`
- Explicit safe simulation: `POST /runtime-posture/compromise` changes the posture to `compromised`
- Explicit safe recovery: `POST /runtime-posture/recover` changes the posture back to `healthy`
- No real exploit or evasion behavior is used; this is a local, minimal demonstration only

### Audit semantics
- Identity failure events are tagged as identity verification failures
- Runtime-integrity failures are tagged separately as runtime integrity compromised
- Recovery is explicit and recorded in logs as a change back to healthy posture

## Repeatable Demonstration

1. Valid identity + healthy posture: allowed
2. Same valid identity after compromise: denied for runtime integrity
3. Recovery to healthy posture: access restored only through explicit recovery

## Run Instructions

1. Create a virtual environment and install dependencies:
   ```bash
   cd workload-identity-poc
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
2. Run the receiver and caller services locally:
   ```bash
   uvicorn receiver.app.main:app --host 0.0.0.0 --port 8000
   uvicorn caller.app.main:app --host 0.0.0.0 --port 8001
   ```
3. Confirm the valid and expired-token Phase 1 demos still work:
   ```bash
   curl http://localhost:8001/demo-valid
   curl http://localhost:8001/demo-invalid
   ```
4. Demonstrate Phase 2 runtime compromise behavior:
   ```bash
   curl http://localhost:8001/runtime-posture
   curl -X POST http://localhost:8001/runtime-posture/compromise
   curl http://localhost:8001/demo-valid
   ```
   Expected result: the valid identity is denied with a 403 and reason `runtime integrity compromised`.
5. Recover the workload posture explicitly and confirm access is restored:
   ```bash
   curl -X POST http://localhost:8001/runtime-posture/recover
   curl http://localhost:8001/demo-valid
   ```
   Expected result: access is allowed again only after the explicit recovery action.
6. Or run everything with Docker Compose:
   ```bash
   docker compose up --build
   curl http://localhost:8001/demo-valid
   curl http://localhost:8001/demo-invalid
   curl -X POST http://localhost:8001/runtime-posture/compromise
   curl http://localhost:8001/demo-valid
   curl -X POST http://localhost:8001/runtime-posture/recover
   curl http://localhost:8001/demo-valid
   ```
7. Inspect the receiver terminal logs for JSON audit records showing `allow` and `deny` decisions with either identity-failure or runtime-integrity-failure reasons.

## Expected Evidence

A healthy request should produce a log entry resembling:
```json
{"event":"authorization_decision","decision":"allow","reason":"valid workload identity and healthy runtime posture","caller_identity":"workload-caller-01","runtime_posture":"healthy"}
```

A compromised request should produce a deny event resembling:
```json
{"event":"authorization_decision","decision":"deny","reason":"runtime integrity compromised","caller_identity":"workload-caller-01","runtime_posture":"compromised"}
```

## Next Steps

1. Add a separate policy store or signed posture attestation signal
2. Introduce explicit trust state transitions and time-based evaluation windows
3. Extend audit logging to centralize decisions for review and compliance
4. Evaluate how this minimal model maps to real workload identity and attestation systems

---

**Document Status:** Architecture Proposal + Phase 2 Runtime Posture Control  
**Version:** 1.2  
**Date:** 2026
