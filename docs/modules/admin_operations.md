# Admin & Operations Module (Module 14)

## Purpose & Exclusions
The Admin & Operations module provides the backend foundation and REST API for internal staff tools, administration, monitoring, and recovery across the Camp Match modular monolith.
- **Exclusions:** No public-facing endpoints; no customer ticket intake (support tickets are not handled in MVP); no payment, booking, or listing mutation/recovery tools (delegated entirely to their respective domain owners); no automated background jobs for admin actions (all actions are synchronous API requests); no staff frontend UI (backend data and action contracts only).

## Responsibilities
1. **Overview Dashboard Aggregation:** Live aggregation of system-wide metrics across Verification, Payments, Trust & Safety, Notifications, Messaging, Operational Issues, and Admin Actions with per-section status (`OK`, `UNAVAILABLE`, `NOT_AUTHORIZED`).
2. **Operational Support Issues:** Internal support issue tracking, priority/status management, assignment, and resolution logging with append-only history.
3. **Account Administration:** Audited account disable and reactivate operations with mandatory minimum-length reasons and protection for administrator accounts.
4. **Staff Role Management:** Granting and revoking the `OPERATIONS` staff role (`ADMIN` management is script-only).
5. **Recovery Actions:** Requeuing dead notification inbox events and failed safety enforcement actions.
6. **Immutable Audit Trail:** Append-only recording of all administrative and staff actions (`ACTION_REQUESTED`, `ACTION_SUCCEEDED`, `ACTION_FAILED`) with uncertain action detection.

## Authorization & Permissions
- **OPERATIONS Role:** Access to Overview and Operational Support Issues.
- **ADMIN Role:** Access to Overview, Operational Support Issues, Audit Trail, Account Actions, Staff Management, and Recovery Actions.
- **Permission Table:**
  - `admin.overview.view` (`OPERATIONS`, `ADMIN`)
  - `admin.issues.manage` (`OPERATIONS`, `ADMIN`)
  - `admin.audit.view` (`ADMIN`)
  - `admin.users.manage` (`ADMIN`)
  - `admin.staff.manage` (`ADMIN`)
  - `admin.recovery.run` (`ADMIN`)

## Issue Lifecycle (C6)
- Status flow: `OPEN` → `IN_PROGRESS` (requires assignee) ⇄ `AWAITING_INFORMATION` (requires reason) → `RESOLVED` (requires resolution summary) → `CLOSED`.
- Resolved issues can be reopened to `IN_PROGRESS` with a reason. `CLOSED` is final.
- Every state transition is recorded in an immutable event history.

## Audit Design & Uncertain Actions (C7)
- Every administrative action records an `ACTION_REQUESTED` event first in its own transaction.
- Upon completion or failure, an `ACTION_SUCCEEDED` or `ACTION_FAILED` event is recorded.
- **Uncertain-Action Procedure:** If a request remains without an outcome after a configured threshold (default 5 minutes), it is flagged as uncertain (`uncertain_actions` in overview). Operators must inspect the owner's actual state (e.g., `GET /admin/accounts/{id}`) before deciding to repeat the action through the normal route.
- Immutability database triggers prevent `UPDATE` or `DELETE` on both audit and issue event tables.

## Overview Data-Source Table
| Section | Interface / Source | Authorization | Freshness | Failure Behavior |
|---|---|---|---|---|
| Verification | Verification module port | `verification.review` / `admin.overview.view` | Live | `UNAVAILABLE` (`source_error` / `timeout`) |
| Payments | Payment module port | `payment.review` / `admin.overview.view` | Live | `UNAVAILABLE` |
| Safety | Trust & Safety module port | `safety.review` / `admin.overview.view` | Live | `UNAVAILABLE` |
| Notifications | Notification module port | `notification.review` / `admin.overview.view` | Live | `UNAVAILABLE` |
| Messaging | Messaging module port | `messaging.review` / `admin.overview.view` | Live | `UNAVAILABLE` |
| Issues | Admin Operations Issue Repo | `admin.overview.view` | Live | `OK` / internal |
| Admin Actions | Admin Operations Audit Repo | `admin.audit.view` / `admin.overview.view` | Live | `OK` / internal |

## Persistence, Transactions & Append-Only Guarantees
- SqlAlchemy models for `admin_issues`, `admin_issue_events`, and `admin_audit_events`.
- Strict PostgreSQL triggers (`prevent_admin_audit_events_mutation`, `prevent_admin_issue_events_mutation`) raising exceptions on any direct `UPDATE` or `DELETE`.

## Known Limitations
- No customer-facing support ticket intake.
- Staff cannot open Trust & Safety reports directly.
- No booking or payment exception views.
- No lookup by email (lookup is strictly by ID).
- `ADMIN` role management is script-only and unaudited by design.
- Uncertain audit actions are surfaced but never auto-reconciled.
- Overview is computed live per request with no historical caching.
- No retention or automated purge policy for audit/issue records (nothing is deleted).
