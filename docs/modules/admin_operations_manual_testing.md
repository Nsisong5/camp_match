# Admin & Operations Manual Testing Guide

## Preconditions
- App running and database migrated.
- Roles: **Rita** (`OPERATIONS`), **Ade** (`ADMIN`), **Dual** (both roles), **Ada** (Student), **Chidi** (Student), **Bola** (Scout).

## Test Scenarios

### A1 — Overview as an operations account
- **Steps:** Rita `GET /api/v1/admin/overview` with `Authorization: Bearer <Rita_token>`.
- **Expect:** `verification`, `safety`, `notifications`, `messaging`, `issues`, `payments` sections return status `OK` or appropriate authorization status; `admin_actions` is `NOT_AUTHORIZED`.

### A2 — Overview as an admin account
- **Steps:** Ade `GET /api/v1/admin/overview`.
- **Expect:** `admin_actions` is `OK`; verification permissions are restricted according to admin grant policy.

### A3 — Ordinary users refused
- **Steps:** Ada (`STUDENT`) or unauthenticated requests on `/admin/overview`, `/admin/operations/issues`, `/admin/audit-events`.
- **Expect:** `401` unauthorized or `403` forbidden.

### A4 — Truthful partial results under outage
- **Steps:** Force a section failure or mock outage.
- **Expect:** Affected section returns `UNAVAILABLE` with `reason_code` and `data: null`, while other sections load successfully.

### A5 — Staff permission boundaries
- **Steps:** Rita attempts to access `/admin/audit-events` or `/admin/staff`.
- **Expect:** `403 Forbidden` (least privilege enforcement).

### A6 — Issue lifecycle
- **Steps:** Create an issue, test idempotent retry (`200` with same issue), assign, transition status (`OPEN` → `IN_PROGRESS` → `RESOLVED` → `CLOSED`), test invalid transitions (`409`).
- **Expect:** Strict state machine enforcement and append-only history recording.

### A7 — Audited account disable & retired routes
- **Steps:** Ade disables Chidi via `POST /api/v1/admin/accounts/{id}/disable` with a reason. Try old Identity route `POST /api/v1/auth/{id}/disable`.
- **Expect:** Success with audit logging; old route returns `404`/`405`.

### A8 — Downstream failure handling
- **Steps:** Simulate downstream failure mode.
- **Expect:** Request fails, account remains unchanged, audit records `ACTION_FAILED`.

### A9 — Uncertain outcome detection
- **Steps:** Simulate crash after request commit.
- **Expect:** Overview `admin_actions` surfaces uncertain action count and age.

### A10 — Staff management
- **Steps:** Ade grants/revokes `OPERATIONS` role on Chidi. Chidi tests permission immediately without re-login.
- **Expect:** Instant role effect; self-grant and admin escalation blocked.

### A11 — Recovery actions
- **Steps:** Ade requeues dead notification events or failed safety enforcements via `/admin/recovery/...`.
- **Expect:** `{"requeued": N}` response and successful processing.

### A12 — Audit immutability
- **Steps:** Attempt direct SQL `UPDATE` or `DELETE` on `admin_audit_events` or `admin_issue_events`.
- **Expect:** Database trigger raises exception (append-only guarantee).
