# CAMP MATCH — MODULE 14: ADMIN & OPERATIONS
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Admin & Operations Module handoff (final MVP module)**

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** You do not copy chunks or parts. Gemini reads the complete document, then works through the chunks **in order, one at a time**. When a chunk is finished, Gemini stops and gives you a Completion Report; you check it and reply **"Proceed to Chunk N"** (or send corrections). Parts marked **[FOR NSISONG]** are for you — decisions, frontend documentation, the test-coverage matrix — and Gemini reads them only for context.

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

You are the implementation agent for this module. You have been given the **complete** specification in this one file.

1. **Read the entire file before doing anything.** Parts marked **[FOR NSISONG]** are for the human: read them for context and rationale, but they are not instructions to you. **The Design Specification (Part C) is the reference you must internalize fully** — every chunk points back to it ("Part C5", "ADR-133" and so on mean sections of this file). **Part D is your work**, in numbered chunks. **Part G (Manual Testing Guide)** at the end of this file is the source material for the manual-testing document you write in Chunk 17.
2. **Your first action is Chunk 1.** It is inspection and scaffolding and writes no behavior. Do not write any other code first.
3. **Work one chunk at a time, in order.** Do not start a chunk until Nsisong has replied "Proceed to Chunk N". Never combine, reorder, skip, or work ahead — not even small "preparatory" edits for a later chunk.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; every file created or changed; every command you ran with its **real** output; each acceptance criterion marked pass or fail; any deviation, surprise, or open question. Claim nothing you did not verify.
5. **If anything blocks you — a failing acceptance item, the repository contradicting this file, two parts of this file disagreeing, or a decision this file does not make — stop and report it.** Do not choose for yourself, skip a test, weaken a test, or work around it.
6. The Standing Instructions in `AI_instructions/` apply to everything. Change only the files a chunk names (plus anything that chunk's touch map allows). Do not modify other modules otherwise.

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

The handoff's default sequence has 15 chunks. This document has **18**. The module itself is small; the extra chunks are the owner-module amendments it needs (Security, Trust & Safety, Messaging) and the retirement of two Identity routes (see the corrections below). Because the handoff makes "scope and domain decisions" an implementation chunk, I have instead made those decisions up front in Parts A and B so Gemini isn't left to decide them. The mapping is in Part E.

---

## PART A — FINDINGS AND CORRECTIONS [FOR NSISONG]

Admin & Operations is the control surface through which staff run Camp Match. Its one rule — *authorized staff operate Camp Match through controlled workflows; the module that owns a resource stays responsible for changing it* — has a consequence that shapes everything: **most of what staff do already has a home in the module that owns it.** Verification already has a reviewer queue, Payment already has dispute and release/refund routes, Trust & Safety has its whole review namespace. This module must not become a second front door to any of them. I checked the 19 specifications behind your code; here is what I found.

### CORRECTIONS I MADE (you reserved the right to fix contradictions)

**Correction 1 — Identity's admin routes have no audit trail, which contradicts this module's rule that sensitive administrative actions are traceable.**
Module 3 (ADR-039, Chunk 10) added `POST /api/v1/auth/{identity_id}/disable` and `/reactivate` to Identity's router, guarded by `ADMIN_USERS_MANAGE`. They record no actor, no reason, no outcome, and don't stop an admin disabling themselves or another admin. That is exactly the "silent, unaudited administrative action" the handoff forbids. **Resolution (ADR-168):** this module provides audited replacements — `POST /api/v1/admin/accounts/{identity_id}/disable` and `/reactivate` — using the same permission and the same Identity use cases, now requiring a reason, writing an audit trail, refusing self-action, and refusing to disable an `ADMIN` account. **Identity's two routes and their tests are then removed** (Chunk 14), so there is exactly one way to do it and it is always audited. This is a breaking change for any frontend calling the old paths; Part F tells you what to update. Trust & Safety's `ACCOUNT_SUSPENSION` calls Identity's `DisableAccount` directly through its own approval workflow and is unaffected.

**Correction 2 — Module 3 deliberately left role management to a script, and the handoff now asks this module to expose it. The role code Security has is a repository method, not a use case.**
Security has `assign_role` / `revoke_role` on its repository port "because the domain needs them to be meaningful"; changing a role today means a Python one-liner with no authorization, no reason and no record. **Resolution (ADR-169):** Security gets four small public use cases (assign, revoke, list staff, read an identity's roles) and this module wraps them with permission checks and audit. The API manages **`OPERATIONS` only. Granting or revoking `ADMIN` stays script-only** — the person with shell access to the server is the root of trust, and an API that can mint administrators is a privilege-escalation path. The script stays, documented as the deliberate out-of-band route. Two guards close the most obvious escalation: **nobody can grant a role to themselves**, and the target must be an active account.

**Correction 3 — documentation wording in earlier modules.** Trust & Safety's and Notification's docs and specs say, in their limitation lists, that "Admin & Operations does not exist" and that staff have a "minimal API, no dashboard." After this module that sentence is wrong in its first half and still right in its second (this module is backend-only; it supplies the data a dashboard needs, not a dashboard). Chunk 17 corrects those sentences in the module docs.

### FINDING 1 — this module aggregates and delegates; it adds no proxy routes
Housing, Verification, Booking, Payment and Trust & Safety each already expose **staff-only routes with their own permissions**. If this module re-exposed them it would be building the "second version of their business rules" the handoff forbids. So it does **not**. A staff frontend calls the owners' routes directly; Part F includes a map of where each staff task lives (ADR-163). What this module genuinely owns is: the **operational overview**, a minimal **operational issue tracker**, the **administrative audit trail**, **staff-role management**, the **audited account actions**, and **two recovery actions**.

### FINDING 2 — the overview can be both truthful and least-privilege by calling owners *as the caller*
Each overview section calls an owner's public use case with the **requesting staff member's own identity**, so the owner decides what that person may see. A person without that owner's permission gets that section marked `NOT_AUTHORIZED` instead of the whole page failing, and an owner outage marks only that section `UNAVAILABLE`. No numbers are ever invented, cached, or read from another module's tables (ADR-164). The counts come from the owners' existing list use cases (`Page.total`) wherever those exist.

### FINDING 3 — the overview can only show what has a contract
- **Exists:** Verification's `ListPendingReviews`; Payment's pending-disputes list; Notification's `GetInboxStats`.
- **Missing, tiny, added by amendment:** a Trust & Safety overview (counts by status and pending/failed enforcement — Trust & Safety is new and has no counts use case), and a Messaging outbox backlog count.
- **Not available at all, deferred and named:** booking exceptions, Payment's and Booking's background-job health, Housing. Nothing here has a safe public read contract, and the handoff forbids inventing one (ADR-171, ADR-174).

### FINDING 4 — no shared audit facility exists; histories do
Verification and Trust & Safety each keep their own append-only history. That's the right pattern for *their* resources, and this module reuses it for *its* resources. It does **not** try to be a cross-module audit aggregator. Its own audit table records the sensitive actions it initiates, with a design that matches the handoff's reliability requirement: the **request row is committed before the action is attempted** and an **outcome row after**, linked by an action id. If the process dies in between, the request row has no outcome — which is *detectable and surfaced*, not silently lost (ADR-167).

### FINDING 5 — no operational-issue or support system exists
A minimal issue tracker is justified, and I keep it deliberately small: **created by staff only** (end-user ticket intake is a separate product feature and is deferred), no safety category, five states, append-only history (ADR-165). One real limitation is named, not papered over: if a staff member learns of fraud or harassment while handling an issue, **this module cannot open a Trust & Safety report**, because Trust & Safety only accepts reports from a user about a resource that user can see. Staff must ask the user to file the report. A staff-originated report path would be a later Trust & Safety amendment (ADR-173).

### FINDING 6 — no monitoring infrastructure exists, and none is built
"Health" means **backlog and failure counts that owners already know** (dead notification events, failed safety enforcement, stuck Messaging events, unresolved administrative actions). No metrics platform, no new worker, no scheduler. This module has **no background process of its own**.

### FINDING 7 — a real escalation risk, and the mitigation I chose
An `ADMIN` who can grant roles could grant `OPERATIONS` to a second account they control and thereby reach Trust & Safety investigative access that the T&S design deliberately withheld from `ADMIN`. The mitigations are: no self-grant; every grant and revoke audited with a reason; `ADMIN` itself never grantable through the API. **What remains is a risk I'm stating, not hiding:** two colluding administrators can still do it. A two-person approval for role grants is the proper fix; it is a decision for you below, not something I invented a broad authority model for.

**No other contradictions found.** Chunk 1 verifies all of this against the real repository, including that Modules 11–13 were built as specified.

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-162 … ADR-174)
Continuing the log from Trust & Safety (144–161).

| ADR | Decision | Why |
|---|---|---|
| 162 | Admin & Operations is Module 14. Routes are under `/api/v1/admin/…`. **Backend only — no UI.** It has **no background worker and publishes and consumes no events** | Handoff §5.5, §15. |
| 163 | **Delegate, don't duplicate.** No proxy routes for Housing, Verification, Booking, Payment or Trust & Safety — staff use those modules' own staff routes (mapped in Part F). Overview sections call the owners' public use cases **as the requesting staff member**, so each owner authorizes | Findings 1–2; handoff §8: "must not implement a second version of their business rules." |
| 164 | **Overview:** `GET /admin/overview` requires `ADMIN_OVERVIEW_VIEW` and returns independent sections, each `{status: OK \| UNAVAILABLE \| NOT_AUTHORIZED, as_of, data, reason_code}`. Counts come from owners' list use cases (`Page.total`, page size 1) or owners' stats use cases. **Computed per request — no cache, no read model, no fabricated or defaulted values.** Each section has a timeout (`admin_overview_section_timeout_seconds`); a failure marks only that section; `reason_code` is `timeout` or `source_error`, never a message | Handoff §5.2, §10. |
| 165 | **Operational issues:** minimal, **staff-created only**, categories `ACCOUNT`, `LISTING`, `BOOKING`, `PAYMENT`, `VERIFICATION`, `PLATFORM`, `OTHER` (**no safety category**), priorities `LOW`/`NORMAL`/`HIGH`, states `OPEN`, `IN_PROGRESS`, `AWAITING_INFORMATION`, `RESOLVED`, `CLOSED` with the table in C6; assignment is a field, not a state; every change is a **conditional update on `version`**; an append-only history protected by triggers; a resolution summary is required to resolve; `idempotency_key` required on create; related resources are **opaque typed pointers that this module never dereferences** | Handoff §5.3, §11. |
| 166 | **Permissions: five new role-scoped Security permissions** — `ADMIN_OVERVIEW_VIEW` → `OPERATIONS`, `ADMIN`; `ADMIN_ISSUES_MANAGE` → `OPERATIONS`, `ADMIN`; `ADMIN_AUDIT_VIEW`, `ADMIN_STAFF_MANAGE`, `ADMIN_RECOVERY_RUN` → `ADMIN` only. The existing `ADMIN_USERS_MANAGE` is reused for account actions. **Neither role is granted any Verification, Payment or Safety permission it doesn't already have**, and `OPERATIONS` gets nothing from the `ADMIN`-only set | Handoff §7: one operational permission must not imply unrelated ones. |
| 167 | **Audit.** Append-only `admin_audit_events`, one `ACTION_REQUESTED` row **committed before** the action is attempted and one `ACTION_SUCCEEDED` or `ACTION_FAILED` row after, linked by `action_id`. **Fail-closed:** if the request row can't be written, the action is not attempted. A request row with no outcome older than `admin_audit_uncertain_after_seconds` is **uncertain** and shown in the overview. A reason is mandatory. Covers account disable/reactivate, staff role grant/revoke, and recovery actions; **issue changes live in the issue's own history, not duplicated here** | Handoff §9. |
| 168 | **Correction 1:** audited `/admin/accounts/{id}/disable` and `/reactivate` (same `ADMIN_USERS_MANAGE`, same Identity use cases; reason required; self-action refused; **an account holding `ADMIN` can't be disabled**); **Identity's two unaudited routes are removed** | Part A, Correction 1. |
| 169 | **Correction 2:** Security gains `AssignStaffRole`, `RevokeStaffRole`, `ListStaff`, `GetAssignedRoles`. The API manages **`OPERATIONS` only**; **`ADMIN` stays script-only**; no self-grant; the target must be an `ACTIVE` account; every change audited with a reason. Roles are resolved at check time, so a change takes effect on the next request | Part A, Correction 2; Finding 7. |
| 170 | **Recovery actions — exactly two:** requeue dead Notification events (Notification's `RequeueDeadEvents`), and requeue failed Trust & Safety enforcement (T&S's `RequeueFailedEnforcement`, which additionally requires the caller to hold `SAFETY_ENFORCEMENT_APPROVE`). Both audited, both idempotent by design in their owners. **No payment, booking or listing recovery is exposed** | Handoff §15: never a "re-run" that could duplicate financial work. |
| 171 | **Owner amendments (small, bounded):** Security — the five permissions and the four staff use cases; Trust & Safety — `GetSafetyOverview`; Messaging — `GetOutboxStats`. No owner's existing behavior changes | Finding 3. |
| 172 | **Account lookup:** `GET /admin/accounts/{identity_id}` by id only, returning status and staff roles; **lookup by email is deferred** (it exposes personal data and has no stated need yet) | Handoff §14: least privilege and data minimization. |
| 173 | **A staff member cannot open a Trust & Safety report** — T&S accepts reports only from a user about a resource that user can see. Staff ask the user to file one. A staff-originated path is a named future amendment | Finding 5. |
| 174 | **Deferred, stated plainly:** end-user ticket intake; booking and payment exception views; background-job health beyond what owners expose; lookup by email; two-person approval for role grants; impersonation; any CRM/analytics/monitoring platform; retention policy for audit and issue records (nothing is deleted, no policy exists) | Handoff §5.5. |

### Decisions I need you to confirm before Chunk 1
1. **Correction 1 — retire Identity's two admin routes.** Anything calling `POST /api/v1/auth/{id}/disable|reactivate` must move to the new audited paths. Approve the removal? (Alternative: keep both, which leaves an unaudited path and fails the module's Definition of Done.)
2. **Correction 2 — `OPERATIONS` manageable by API, `ADMIN` script-only.** Is that the trust model you want? And do you want a **two-person approval** for role grants now (more work, closes Finding 7) or later?
3. **Role mapping.** `OPERATIONS` and `ADMIN` both run the overview and issues; only `ADMIN` sees audit, manages staff, runs recovery, and disables accounts. Does that match who does what on your team?
4. **Scope.** In: overview, issues, audit, staff roles, account actions, two recovery actions. Out (deferred): end-user ticket intake, booking/payment exception views, email lookup. Anything you need for the first release?

---

## PART C — DESIGN SPECIFICATION
**[FOR YOU — GEMINI CLI — the design: internalize it fully before starting Chunk 1.]**

Where a chunk and this part appear to disagree, **stop and report** instead of choosing.

### C1. Non-negotiable rules specific to this module
1. **This module never changes another module's data and never reads another module's tables.** It acts only through the public use cases named here. Owners validate and execute.
2. **No proxy routes.** If a route would merely forward to an owner's use case that already has its own staff route, do not write it (ADR-163).
3. **The actor is always the authenticated principal.** Never from a request body.
4. **Fail closed on audit.** For every audited action: write and commit the request row first; if that fails, **do not attempt the action** and raise. Never report success unless the owner returned success.
5. **Application and domain layers import nothing from any other module.** Only `adapters/` do, through other modules' `application/ports`. **No other module imports Admin & Operations.** Enforced by import-linter.
6. **Never log** issue titles/descriptions/summaries, audit reasons, or account details. Log ids, enums, counts, outcome codes, and short error class names.
7. **Overview honesty:** a value is either read from an owner this request or the section says it is unavailable. No default zeros, no cached numbers.
8. **Every state change and its history row are one transaction.** (Issues.)
9. **Unauthorized or nonexistent resources return the same `404`** wherever revealing existence would leak (issues are not sensitive, so a plain `404`/`403` split is fine there; account lookups use `404` for absent).

### C2. Module layout
```
src/camp_match/modules/admin_operations/
├── domain/        value_objects.py  entities.py  policies.py
├── application/
│   ├── errors.py
│   ├── ports/     inbound.py  outbound.py
│   ├── services/  audit_recorder.py                       # request-then-outcome, fail-closed
│   └── use_cases/ get_overview.py
│                  create_issue.py  list_issues.py  get_issue.py  assign_issue.py  change_issue_status.py
│                  get_account.py  disable_account.py  reactivate_account.py
│                  list_staff.py  grant_staff_role.py  revoke_staff_role.py
│                  requeue_dead_notification_events.py  requeue_failed_safety_enforcement.py
│                  list_audit_events.py
└── adapters/
    ├── persistence/   models.py  issue_repository.py  audit_repository.py
    ├── identity/      account_provider.py                  # Identity (read + disable/reactivate)
    ├── security/      staff_provider.py  authorizer.py     # Security staff use cases + AuthorizationService
    ├── overview/      verification_source.py  payment_source.py  safety_source.py
    │                  notification_source.py  messaging_source.py
    ├── recovery/      notification_recovery.py  safety_recovery.py
    └── api/           schemas.py  router.py  dependencies.py
```
There is **no `scripts/` entry** and no worker (ADR-162).

### C3. Domain model

**Enums.** `IssueCategory`, `IssuePriority`, `IssueStatus` per ADR-165. `ReferenceType`: `IDENTITY`, `LISTING`, `BOOKING`, `PAYMENT`, `VERIFICATION_CASE`. `SectionStatus`: `OK`, `UNAVAILABLE`, `NOT_AUTHORIZED`. `AuditEventType`: `ACTION_REQUESTED`, `ACTION_SUCCEEDED`, `ACTION_FAILED`. `AdminActionType`: `ACCOUNT_DISABLE`, `ACCOUNT_REACTIVATE`, `STAFF_ROLE_GRANT`, `STAFF_ROLE_REVOKE`, `RECOVERY_NOTIFICATION_EVENTS`, `RECOVERY_SAFETY_ENFORCEMENT`. `AuditTargetType`: `IDENTITY`, `NONE`.

**`OperationalIssue`** — `id`, `category`, `title` (1–120 chars), `description` (1–`admin_issue_description_max`), `priority` (default `NORMAL`), `status` (starts `OPEN`), `assignee_id | None`, `references` (0–5 `(ReferenceType, EntityId)` pairs; never dereferenced), `created_by`, `idempotency_key`, `version` (≥ 1), `created_at`, `updated_at`, `resolved_at | None`, `resolution_summary | None`. Transition methods enforce C6's table and raise `InvalidIssueTransition`; they know nothing about permissions.

**`IssueEvent`** (immutable) — `id`, `issue_id`, `event_type` (`CREATED`, `ASSIGNED`, `STATUS_CHANGED`), `actor_id`, `occurred_at`, `details` (a plain dict: `from`/`to` statuses, `assignee_id`, `reason`, and — for a resolution — `resolution_summary`; **staff-authored text is allowed here and nowhere else**).

**`AuditEvent`** (immutable) — `id`, `action_id`, `event_type`, `action_type`, `actor_id`, `target_type`, `target_id | None`, `reason | None` (**required on `ACTION_REQUESTED`**, min `admin_reason_min_length`), `outcome_code | None` (a short code or error class name, only on outcome rows), `occurred_at`, `request_id | None` (the project's correlation id if it has one), `details` (ids and enums only — e.g. the role name).

**`OverviewSection`** — `name`, `status`, `as_of`, `data | None`, `reason_code | None`. Invariants: `OK` requires `data`; `UNAVAILABLE` requires `reason_code` (`timeout` | `source_error`) and no data; `NOT_AUTHORIZED` has neither.

**Pure policy functions (`policies.py`):** `MANAGEABLE_STAFF_ROLES = {OPERATIONS}`; `is_manageable(role)`; `is_uncertain(request_event, outcome_exists, now, threshold_seconds)`; `can_reassign(status)`.

**Tests (Chunk 3):** every invariant individually — every issue transition in C6 allowed and **every other pair raises**; `OK` section without data raises, `UNAVAILABLE` without a reason code raises, `NOT_AUTHORIZED` with data raises; `ACTION_REQUESTED` without a reason raises; reference count cap; title/description bounds; `is_manageable` accepts only `OPERATIONS`; `is_uncertain` across the threshold boundary and when an outcome exists.

### C4. Database (all tables prefixed `admin_`; no foreign keys into any other module)

| Table | Columns (not null unless noted) and constraints |
|---|---|
| `admin_issues` | `id` PK; `category`; `title`; `description`; `priority`; `status`; `assignee_id` null; `references` jsonb; `created_by`; `idempotency_key`; `version` (`CHECK >= 1`); `created_at`; `updated_at`; `resolved_at` null; `resolution_summary` null. **Unique `(created_by, idempotency_key)`**; `CHECK`s on the three enums; `CHECK (status <> 'RESOLVED' OR resolution_summary IS NOT NULL)`; indexes `(status, priority, created_at)` and `(assignee_id) WHERE assignee_id IS NOT NULL`. |
| `admin_issue_events` | `id` PK; `issue_id` FK; `event_type`; `actor_id`; `occurred_at`; `details` jsonb. Index `(issue_id, occurred_at, id)`. **Immutable (trigger).** |
| `admin_audit_events` | `id` PK; `action_id`; `event_type`; `action_type`; `actor_id`; `target_type`; `target_id` null; `reason` null; `outcome_code` null; `occurred_at`; `request_id` null; `details` jsonb. **Unique `(action_id, event_type)`** (each phase at most once); `CHECK (event_type <> 'ACTION_REQUESTED' OR reason IS NOT NULL)`; indexes `(occurred_at DESC, id)`, `(actor_id, occurred_at)`, `(target_type, target_id)`, and partial `(occurred_at) WHERE event_type = 'ACTION_REQUESTED'`. **Immutable (trigger).** |

**Immutability triggers** on `admin_issue_events` and `admin_audit_events`: `BEFORE UPDATE OR DELETE` raising an exception, as raw SQL in the migration with a matching `downgrade` (the same technique as Trust & Safety's migration — Chunk 1 reports how it was written). **Read the migration before applying.**

**Uncertain-action query** (a repository method, one statement): request rows older than the cutoff for which **no** row with the same `action_id` and a type in (`ACTION_SUCCEEDED`, `ACTION_FAILED`) exists, returning count and the oldest `occurred_at`.

### C5. Ports

**Inbound** (`Protocol` + `execute`, `@dataclass` request/response, `actor_id: str` first): the 15 use cases in C2.

**Outbound:**
- `IssueRepository` (`add`, `get`, `list`, conditional `update_status`/`update_assignee` on `version`, `add_event`, `list_events`, `counts_by_status`, `count_unassigned_open`, `count_high_priority_open`); `AuditRepository` (`add`, `list` with filters, `count_uncertain(cutoff) -> (count, oldest_at)`).
- **`AccountProvider`** — `get(identity_id) -> AccountInfo | None` (`identity_id`, `status`, `created_at`); `disable(identity_id)`; `reactivate(identity_id)`. Identity's `GetIdentityById`, `DisableAccount`, `ReactivateAccount`. Owner `ApplicationError`s **propagate unchanged** (truthful); anything else propagates as an unexpected error.
- **`StaffRoleProvider`** — `assign(actor_id, identity_id, role)`, `revoke(actor_id, identity_id, role)`, `list(actor_id, role, page_request)`, `get_roles(identity_id) -> frozenset[str]`. Security's four new use cases (C12).
- **`Authorizer`** — `authorize(identity_id, permission)` (Security's `AuthorizationService`, raising Security's existing `Forbidden`); also used to check that an *assignee* holds `ADMIN_ISSUES_MANAGE` and that a recovering admin holds `SAFETY_ENFORCEMENT_APPROVE`.
- **Overview sources**, each `fetch(actor_id) -> dict` raising the owner's `Forbidden` (→ `NOT_AUTHORIZED`) or any other exception (→ `UNAVAILABLE`): `VerificationSource` (`ListPendingReviews(actor, page_size=1).total`), `PaymentSource` (the pending-disputes list use case, `.total`), `SafetySource` (T&S `GetSafetyOverview`), `NotificationSource` (`GetInboxStats`), `MessagingSource` (Messaging `GetOutboxStats`).
- **Recovery:** `NotificationRecovery.requeue_dead() -> int` (`RequeueDeadEvents`); `SafetyRecovery.requeue_failed() -> int` (`RequeueFailedEnforcement`).
- Reused: shared-kernel `Clock`, `EntityId`, `Page`/`PageRequest`, `UnitOfWork`.

### C6. Issue lifecycle (ADR-165)

| From | To | Requires |
|---|---|---|
| `OPEN` | `IN_PROGRESS` | an assignee |
| `IN_PROGRESS` | `AWAITING_INFORMATION` | reason |
| `AWAITING_INFORMATION` | `IN_PROGRESS` | — |
| `IN_PROGRESS` | `RESOLVED` | `resolution_summary` (min `admin_resolution_min_length`) |
| `RESOLVED` | `CLOSED` | — |
| `RESOLVED` | `IN_PROGRESS` | reason (reopen); history keeps the earlier summary |

`CLOSED` is terminal. Assignment is allowed in `OPEN`, `IN_PROGRESS`, `AWAITING_INFORMATION` only, and the assignee must hold `ADMIN_ISSUES_MANAGE` (checked through `Authorizer`). Any holder of `ADMIN_ISSUES_MANAGE` may perform any transition (a small team; documented, not restricted to the assignee). Every change: authorization → state check → **conditional update on `version`** (`IssueStateChanged` on a lost race) → one `admin_issue_events` row, **one transaction**. Same-state requests and pairs not in the table raise `InvalidIssueTransition`.

### C7. Audited actions (ADR-167) — the one algorithm every audited use case follows (`AuditRecorder`)

1. Authorize the permission; validate input and reason; run every cheap pre-check the use case defines (self-action, protection of `ADMIN`, target exists and is `ACTIVE` where required).
2. Generate `action_id`. **In its own unit of work, write the `ACTION_REQUESTED` row and commit.** If this fails → raise; **nothing was attempted.**
3. Call the owner through the port.
4. **Success:** in a new unit of work write `ACTION_SUCCEEDED` (`outcome_code = 'ok'`, details as relevant); return the owner's result.
5. **Owner `ApplicationError`:** write `ACTION_FAILED` (`outcome_code` = the error's `code`); **re-raise that same error** (the caller sees the owner's truthful answer).
6. **Any other exception:** write `ACTION_FAILED` (`outcome_code` = the exception class name); re-raise.
7. **If writing the outcome row itself fails**, log ERROR with `action_id` and re-raise the original result unchanged — the request row remains with no outcome, which is exactly the **uncertain** state the overview surfaces. Never invent an outcome.
8. Never retry an owner call automatically. A repeated request is a new `action_id`.

Account actions, role grants/revokes, and both recovery actions all go through `AuditRecorder` (the recovery actions record the count returned in `details`).

### C8. Account, staff and recovery rules

- **`DisableAccount(actor, target, reason)`:** authorize `ADMIN_USERS_MANAGE`; reason; **`actor != target`** (`SelfActionNotAllowed`, `403`); target exists (`AccountNotFound`, `404`); **target must not hold `ADMIN`** (`AdminAccountProtected`, `403`, via `StaffRoleProvider.get_roles`); then C7. `ReactivateAccount` mirrors it without the `ADMIN` protection. `GetAccount(actor, id)` — `ADMIN_USERS_MANAGE`; returns `identity_id`, `status`, `created_at`, `roles` (staff roles only).
- **`GrantStaffRole(actor, target, role, reason)`:** authorize `ADMIN_STAFF_MANAGE`; **role must be manageable** (`RoleNotManageable`, `422`, for anything but `OPERATIONS`); **`actor != target`** (`SelfActionNotAllowed`); target exists **and is `ACTIVE`** (`AccountNotFound` / `AccountNotActive`); then C7 around Security's idempotent assign. **`RevokeStaffRole`** mirrors it (no `ACTIVE` requirement; revoking an unassigned role succeeds as a no-op). `ListStaff(actor, role)` — `ADMIN_STAFF_MANAGE`, paginated, identity ids and roles only.
- **`RequeueDeadNotificationEvents(actor, reason)`:** authorize `ADMIN_RECOVERY_RUN`; C7 around `NotificationRecovery.requeue_dead()`. **`RequeueFailedSafetyEnforcement(actor, reason)`:** authorize `ADMIN_RECOVERY_RUN` **and** `SAFETY_ENFORCEMENT_APPROVE`; C7 around `SafetyRecovery.requeue_failed()`.
- `ListAuditEvents(actor, filters)` — `ADMIN_AUDIT_VIEW`; filters `actor_id`, `action_type`, `target_id`, `from`, `to`; paginated, newest first; never includes anything beyond the stored columns.

### C9. The overview (ADR-164)

`GetOverview(actor)`: authorize `ADMIN_OVERVIEW_VIEW`; then, **sequentially** (each section with its **own** short-lived session; a section's failure never aborts the rest), each section runs under `asyncio.wait_for(admin_overview_section_timeout_seconds)`:

| Section | Source | `data` |
|---|---|---|
| `verification` | `ListPendingReviews` as the caller | `{pending_reviews}` |
| `payments` | pending disputes list as the caller | `{pending_disputes}` |
| `safety` | T&S `GetSafetyOverview` as the caller | `{reviewer: {...}\|null, approver: {...}\|null}` per C13 |
| `notifications` | `GetInboxStats` | `{pending, dead}` |
| `messaging` | `GetOutboxStats` | `{outbox_pending, outbox_oldest_age_seconds}` |
| `issues` | own repository | `{open_by_status, unassigned_open, high_priority_open}` |
| `admin_actions` | own audit repository; **requires `ADMIN_AUDIT_VIEW`** | `{uncertain_actions, oldest_age_seconds}` |

`NOT_AUTHORIZED` ⇐ the owner (or the section's own permission) refused the caller; `UNAVAILABLE` ⇐ timeout or any other exception (logged at WARNING with the section name and error class, nothing else). `as_of` = the injected `Clock`'s time when that section finished. **Booking and Housing sections do not exist** (no contract; ADR-174). `admin_debug_fail_section` — see C10.

### C10. Settings (`config/settings.py`, `.env.example`)

| Setting | Default |
|---|---|
| `admin_overview_section_timeout_seconds` | 3 |
| `admin_reason_min_length` | 10 |
| `admin_resolution_min_length` | 10 |
| `admin_issue_description_max` | 2000 |
| `admin_audit_uncertain_after_seconds` | 300 |
| `admin_debug_fail_section` | `""` — a section name; honored **only** when `app_env` is `local` or `test`; forces that section to raise so `UNAVAILABLE` can be demonstrated |
| `admin_debug_account_action_mode` | `""` — `downstream_fails` or `crash_after_request`; honored **only** when `app_env` is `local` or `test` (Chunk 8) |

### C11. Touch map — the **only** files outside `modules/admin_operations/` this module changes

| Module / file | Change | Chunk |
|---|---|---|
| Security: policy and value objects; four use cases, ports, repository method `list_identities_with_role`, composition | **C12** | 2 |
| Trust & Safety: one use case `GetSafetyOverview`, repository count methods | **C13** | 6 |
| Messaging: one use case `GetOutboxStats`, one repository method | **C14** | 6 |
| Identity: **remove** the two admin routes, their schemas and dependency wiring, and their tests (Identity's use cases untouched) | **Correction 1** | 14 |
| `config/settings.py`, `.env.example` | C10 | 4 |
| `app.py` | mount the admin router | 13 |
| `pyproject.toml` | import-linter contracts | 16 |

**Not touched:** Profile, University, Housing, Search, Media/File, Verification, Booking, Payment, Notification (their existing use cases are *called*, never changed).

### C12. Security amendment (rulebook for Chunk 2)
- Add the five permissions (ADR-166), **role-scoped**, with exactly the stated grants; nothing else changes in the policy table.
- **New inbound use cases**, each authorizing `ADMIN_STAFF_MANAGE` itself except the read: `AssignStaffRole(actor_id, identity_id, role)` — **only `OPERATIONS` is manageable**, any other role (`ADMIN`, `STUDENT`, `SCOUT`) → `RoleNotManageable`; already assigned → success no-op; `RevokeStaffRole` — same rule; not assigned → success no-op; `ListStaff(actor_id, role, page_request)` → identity ids + role, paginated; `GetAssignedRoles(identity_id) -> frozenset[Role]` (no actor; read-only; returns staff roles only).
- Implemented on the **existing** `RoleRepository` (`assign_role`, `revoke_role`, `get_assigned_roles`) plus one new method `list_identities_with_role(role, page_request)`. **Do not change the script route:** the one-liner/script that calls `assign_role` directly keeps working for `ADMIN`.
- Roles are resolved at check time today (confirm in Chunk 1); a role change must therefore take effect on the next authorization with no cache to invalidate.

### C13. Trust & Safety amendment (rulebook for Chunk 6)
`GetSafetyOverview(actor_id) -> SafetyOverview(reviewer | None, approver | None)`: `reviewer` (present if the actor holds `SAFETY_CASE_REVIEW`): `reports_awaiting_triage` (reports in `RECEIVED`), `open_cases_by_status` (every status except `CLOSED`), `high_or_urgent_open_cases`; `approver` (present if the actor holds `SAFETY_ENFORCEMENT_APPROVE`): `enforcement_awaiting_approval` (`PROPOSED`), `enforcement_retrying` (`APPROVED` with `attempts > 0`), `enforcement_failed` (`FAILED` + `REVERSAL_FAILED`). **Neither permission → Security's `Forbidden`.** Counts are aggregate queries only (no rows, no ids, no content). No HTTP route.

### C14. Messaging amendment (rulebook for Chunk 6)
`GetOutboxStats() -> OutboxStats(pending, oldest_pending_age_seconds | None)` — actorless, read-only, one aggregate query on `messaging_outbox` (`dispatched_at IS NULL`), age from the injected `Clock`. No HTTP route; this module authorizes callers.

---

## PART D — CHUNKED IMPLEMENTATION

**Work one chunk at a time, in order, and stop after each Completion Report** (see the Operating Instructions at the top). Each chunk lists only what is specific to it; Part C is the design, and **C12, C13, C14 are the rulebooks for the amendments to Security, Trust & Safety and Messaging.** A failed acceptance item means stop and report — never skip, weaken, or work around a test. Every chunk that touches another module ends by re-running that module's whole suite.

---

### CHUNK 1 — REPOSITORY INSPECTION, ARCHITECTURE MAPPING & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** confirm this specification's assumptions against the real repository and create the empty module. No behavior.

1. Read `AI_instructions/`, all `AI_state/`, and `docs/modules/` for identity, security, verification, payment, messaging, notification, trust_safety.
2. **Confirm Modules 11, 12 and 13 are built as specified.** Report any difference — it changes this plan. If any is missing, stop.
3. **Identity:** exact signatures of `GetIdentityById`, `DisableAccount`, `ReactivateAccount` (requests, responses, errors); **what each does when the account is already in the target state** (no-op or error — Part C7 depends on it); the status values. Locate **everything** that belongs to Identity's two admin routes `POST /api/v1/auth/{identity_id}/disable|reactivate`: the router entries, schemas, dependency wiring, tests (`tests/api/identity/test_admin_endpoints.py`), docs, `AI_state/` mentions, and any frontend-API-doc entry. List each file — Chunk 14 removes them.
4. **Security:** `RoleRepository`'s exact methods (`assign_role`, `revoke_role`, `get_assigned_roles`) and the role set the table allows; **confirm roles are read from the database at authorization time (no cache or token claim)**; `AuthorizationService`'s exact interface and the `Forbidden` class; the exact recipe for adding a role-scoped permission; the existing script/one-liner that assigns roles (and its documented location).
5. **Verification:** `ListPendingReviews` (signature, whether it takes a `PageRequest` and returns a `Page` with `total`, the permission it needs). **Payment:** the pending-disputes list use case (name, signature, `Page.total`, permission — expected `PAYMENT_REVIEW`). **Notification:** `GetInboxStats` and `RequeueDeadEvents` (exact output shapes). **Trust & Safety:** `RequeueFailedEnforcement` (output), its repositories, and how its migration wrote the immutability triggers. **Messaging:** its outbox repository and `Clock` usage.
6. Inspect: shared-kernel `Page`/`PageRequest`/`UnitOfWork`/`Clock`; router and schema conventions; whether a **request/correlation id** is available to application code (Part C4's `request_id` uses it if so); import-linter contracts; how existing concurrency tests provision committed data; the project-wide frontend API doc location; `app_env`.
7. Confirm no admin-operations code exists. Create the empty structure from Part C2 (one-line docstrings, no logic) plus `tests/unit|integration|api/admin_operations/`. Touch nothing else.

**Acceptance criteria:** a written report covering steps 2–6 with exact signatures, every mismatch flagged, and an explicit **proceed / blocked** verdict; scaffolding importable; no file outside the module and test folders changed.

---

### CHUNK 2 — SECURITY AMENDMENT: PERMISSIONS & STAFF-ROLE USE CASES
**[FOR YOU — GEMINI CLI]**

**Objective:** Security gains five permissions and four public use cases. **Security's existing behavior and tests must not change.** Read **Part C12**.

Implement C12: the five role-scoped permissions with exactly the stated grants (`ADMIN_OVERVIEW_VIEW` and `ADMIN_ISSUES_MANAGE` → `OPERATIONS`, `ADMIN`; `ADMIN_AUDIT_VIEW`, `ADMIN_STAFF_MANAGE`, `ADMIN_RECOVERY_RUN` → `ADMIN`); `AssignStaffRole`, `RevokeStaffRole`, `ListStaff`, `GetAssignedRoles` as inbound use cases on the existing repository port plus the one new method `list_identities_with_role`; composition. **Leave the existing role-assignment script untouched.**

**Tests:**
- policy: a parametrized test over the five — exactly the stated roles hold each and **no other role does** (assert the complement); none is ownership-scoped; existing grants unchanged;
- `AssignStaffRole`: needs `ADMIN_STAFF_MANAGE` (`OPERATIONS`, `STUDENT`, `SCOUT` refused; `ADMIN` allowed); **`OPERATIONS` assignable; `ADMIN`, `STUDENT`, `SCOUT` → `RoleNotManageable`**; already assigned → success, still one row; `RevokeStaffRole` mirrors it, including success when not assigned; `ListStaff` returns only identities with the role, paginated, and requires the permission; `GetAssignedRoles` returns the exact set (empty if none) and requires no actor;
- **effect at next check:** assign `OPERATIONS` to an identity and the very next `AuthorizationService.authorize` for an `OPERATIONS`-scoped permission succeeds; revoke it and the next one is refused (real database);
- the existing script/one-liner still assigns `ADMIN`.
- Security's, Identity's, Profile's, Housing's, Verification's, Booking's, Payment's, Messaging's, Notification's and Trust & Safety's suites unchanged; `mypy`, `lint-imports` clean.

**Acceptance criteria:** all pass; no change to existing assertions.

---

### CHUNK 3 — DOMAIN MODEL & POLICIES
**[FOR YOU — GEMINI CLI]**

**Files:** `domain/value_objects.py`, `entities.py`, `policies.py`. Build exactly Part C3 and C6 as entity methods and pure functions.

**Dependencies allowed:** shared-kernel `EntityId`; stdlib. Nothing else.

**Tests** (`tests/unit/admin_operations/domain/`, each its own named test): the list in C3's "Tests (Chunk 3)". Additionally: **parametrized over the whole C6 table** — every (from, to) pair allowed and **every other pair raises `InvalidIssueTransition`**, including from `CLOSED`; `RESOLVED` without a summary raises; the section invariants; `AuditEvent` `ACTION_REQUESTED` needs a reason and an outcome row carries an `outcome_code`; **no attribute anywhere accepts a client-supplied actor** (a source scan for fields named `actor`/`created_by` being set from request-like objects is not meaningful here — instead assert the entities take `actor_id`/`created_by` only as constructor arguments supplied by use cases, by inspecting signatures).

**Acceptance criteria:** tests pass; no import outside the allowed list.

---

### CHUNK 4 — ERRORS, PORTS, DTOs & SETTINGS
**[FOR YOU — GEMINI CLI]**

**Files:** `application/errors.py`, `application/ports/inbound.py`, `outbound.py`; `config/settings.py`, `.env.example`.

1. **Errors** (each extends a shared-kernel category and carries a `code`): `IssueNotFound`, `AccountNotFound` (`NotFoundError`); `InvalidReason`, `InvalidIssue`, `InvalidResolution`, `RoleNotManageable`, `AccountNotActive` (`ValidationError`); `InvalidIssueTransition`, `IssueStateChanged` (`issue_state_changed`), `IdempotencyKeyConflict` (`ConflictError`); `SelfActionNotAllowed`, `AdminAccountProtected` (`ForbiddenError`). `RoleNotManageable` here is the module's own mapping of Security's error of the same meaning — adapters translate, application code never imports Security's.
2. **Ports:** every inbound and outbound port in C5 as `Protocol`s with `@dataclass` request/response types.
3. **Response shapes:** `IssueView`, `IssueEventView`, `AccountView` (`identity_id`, `status`, `created_at`, `roles`), `StaffView` (`identity_id`, `roles`), `AuditEventView`, `OverviewSectionView`, `OverviewView` (the seven named sections), `RecoveryResult` (`action_id`, `requeued`).
4. **Settings** per C10 (the two debug settings are plain strings here; the environment guard comes in Chunk 8).

**Tests:** each error's parent and exact `code`; settings defaults load.

**Acceptance criteria:** `mypy` clean on touched files; tests pass; the **full existing suite is unchanged**; no `fastapi`/`sqlalchemy` import under `application/`.

---

### CHUNK 5 — PERSISTENCE, CONSTRAINTS, TRIGGERS & MIGRATION
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/persistence/models.py`, `issue_repository.py`, `audit_repository.py`. Build the three tables exactly as Part C4 and the repositories against C5.

Rules easy to get subtly wrong: issue status/assignee updates are **conditional on `version`** and return `rowcount == 1` (and bump `version`); `IssueRepository.add` catches the `(created_by, idempotency_key)` violation **by constraint name**; the audit and issue-event repositories expose **no update or delete method**; `count_uncertain(cutoff)` is the **single statement** described in C4; list/count methods are aggregate queries using the C4 indexes; never return ORM rows outside persistence files.

**Migration:** `poetry run alembic revision --autogenerate -m "add admin operations tables"`, then add the two immutability triggers as raw SQL exactly as Trust & Safety's migration did. **Read the whole migration before applying** and confirm every `CHECK`, the unique constraints, the partial index predicates and both triggers.

**Tests** (`tests/integration/admin_operations/`, `integration` marker, `db_session`; constraint tests use raw inserts that bypass the application layer):
- every `CHECK` rejects its violation (enums, `version < 1`, `RESOLVED` without a summary, an `ACTION_REQUESTED` row without a reason);
- unique `(created_by, idempotency_key)` rejects a duplicate; **unique `(action_id, event_type)`** rejects a second request row or second outcome row for one action but allows request + outcome;
- **immutability triggers:** `UPDATE` and `DELETE` on `admin_issue_events` and `admin_audit_events` each fail — raw SQL, ORM, and a `DELETE` of every row;
- conditional update with a stale `version` returns `False` and changes nothing; with the right one it succeeds and bumps `version`;
- `count_uncertain`: a request with no outcome older than the cutoff counts (with the right oldest timestamp); a request **with** a `SUCCEEDED` or a `FAILED` outcome does not; a request newer than the cutoff does not; returns `(0, None)` when none;
- list filters and ordering (`occurred_at DESC, id`) and pagination are stable and non-overlapping.

**Acceptance criteria:** tests pass against the Termux Postgres; `alembic upgrade head` clean, `downgrade` then `upgrade` round-trips; `lint-imports` clean.

---

### CHUNK 6 — OWNER AMENDMENTS: SAFETY OVERVIEW & OUTBOX STATS
**[FOR YOU — GEMINI CLI]**

**Objective:** two owners expose the read-only counts the overview needs. **Their existing behavior and tests must not change; no HTTP route is added.** Read **Part C13** and **Part C14**.

- **Trust & Safety:** `GetSafetyOverview(actor_id)` per C13, plus the aggregate count methods on its repositories. Authorization through its existing `AuthorizationService` use: neither `SAFETY_CASE_REVIEW` nor `SAFETY_ENFORCEMENT_APPROVE` → Security's `Forbidden`. No ids, rows or content in the result.
- **Messaging:** `GetOutboxStats()` per C14, plus the one aggregate method on its outbox repository.

**Tests:**
- **T&S:** an `OPERATIONS`-style actor gets only `reviewer`; an `ADMIN`-style actor only `approver`; both permissions → both; neither → `Forbidden`; counts correct for a seeded mix (reports in each state, cases in each status and priority, actions in each status — assert `reports_awaiting_triage` counts only `RECEIVED`, `open_cases_by_status` excludes `CLOSED`, `high_or_urgent_open_cases` counts only open cases, `enforcement_retrying` counts only `APPROVED` with `attempts > 0`, `enforcement_failed` counts both failed kinds); the result type has no field capable of carrying a reporter, subject or content (assert the field names);
- **Messaging:** `pending` and the oldest age correct for a seeded outbox (dispatched rows excluded, age from `FixedClock`); zero pending → `(0, None)`.
- Trust & Safety's and Messaging's **entire** suites pass unchanged; neither imports `camp_match.modules.admin_operations`.

**Acceptance criteria:** new tests pass; both suites unchanged; `mypy`, `lint-imports` clean.

---

### CHUNK 7 — ADAPTERS FOR OTHER MODULES
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/identity/`, `security/`, `overview/`, `recovery/` (Part C2). Each imports **only** the target module's `application/ports` (and use-case surface), never its `adapters` or `domain`.

- `InProcessAccountProvider` (Identity `GetIdentityById`, `DisableAccount`, `ReactivateAccount`): not-found → `None` from `get`; the two commands return normally on success and **let the owner's `ApplicationError`s propagate unchanged**.
- `InProcessStaffRoleProvider` (Security's four use cases): translate Security's `RoleNotManageable`/`Forbidden` into this module's equivalents where C8 says so; `InProcessAuthorizer` (Security's `AuthorizationService`).
- Overview sources — `VerificationSource`, `PaymentSource`, `SafetySource`, `NotificationSource`, `MessagingSource` — each `fetch(actor_id) -> dict`: call the owner's use case **as the actor** (page size 1 where a `Page.total` is used), map to a plain dict with only the C9 keys, let the owner's `Forbidden` propagate (the use case converts it to `NOT_AUTHORIZED`) and any other exception propagate (→ `UNAVAILABLE`).
- `InProcessNotificationRecovery` (`RequeueDeadEvents`) and `InProcessSafetyRecovery` (`RequeueFailedEnforcement`): return the count.
- When `admin_debug_fail_section` names a section (guarded in Chunk 8's helper for `local`/`test`), that source raises before calling anything.

**Tests** (fakes for the target use cases): mapping both ways; every not-found/forbidden path; **each overview source passes the caller's identity through unchanged and uses page size 1** (assert on the fake); output dictionaries contain exactly the C9 keys and nothing else; owner errors propagate with their type and code intact; recovery adapters return the owner's count; **there is no adapter, port, or import for Housing, Booking, or Payment's write/recovery use cases** (source scan — Payment is touched only by the read-only `PaymentSource`).

**Acceptance criteria:** tests pass; `mypy`, `lint-imports` clean; neighbouring suites unaffected.

---

### CHUNK 8 — THE AUDIT RECORDER & ACCOUNT ACTIONS
**[FOR YOU — GEMINI CLI]**

**Files:** `application/services/audit_recorder.py`, `use_cases/get_account.py`, `disable_account.py`, `reactivate_account.py`, `list_audit_events.py`; the debug-mode guard.

Implement `AuditRecorder` exactly as **C7** (request row in its own unit of work and committed first; the three outcome paths; the outcome-write-failure rule; no automatic retry) and the account use cases exactly as **C8**. `ListAuditEvents` per C8.

**Debug mode:** `admin_debug_account_action_mode` is honored **only** when `app_env` is `local` or `test` (an explicit structural check; ignored otherwise). `downstream_fails` makes the account adapter raise before calling Identity (→ a `FAILED` row); `crash_after_request` raises right after the request row commits **without** writing any outcome and without calling Identity (simulating a crash → an uncertain action).

**Tests (fakes, `FixedClock`):**
- `DisableAccount`: needs `ADMIN_USERS_MANAGE` (`OPERATIONS`, `STUDENT`, `SCOUT` refused); reason shorter than the minimum → `InvalidReason`; **actor equals target → `SelfActionNotAllowed` and nothing audited**; target absent → `AccountNotFound`; **target holding `ADMIN` → `AdminAccountProtected`, nothing audited, owner never called**; success → exactly one `ACTION_REQUESTED` then one `ACTION_SUCCEEDED`, same `action_id`, actor = `actor_id`, reason stored, no account details beyond the target id;
- **ordering proof:** the fake owner records, at the moment `disable` is called, whether a committed request row already exists for the action — it must;
- **fail-closed:** if the request row write fails, the owner is **never called** and the error propagates;
- owner raises an `ApplicationError` → `ACTION_FAILED` with `outcome_code` = its `code`, **the same error re-raised**; owner raises an unexpected exception → `ACTION_FAILED` with the class name, re-raised; **the owner is called exactly once** in every case;
- **outcome write fails** after an owner success → the success result is still returned, ERROR logged with the `action_id`, and **no outcome row exists** (the action is "uncertain"); the use case never invents an outcome;
- debug modes: `downstream_fails` → request + `FAILED`, account untouched; `crash_after_request` → request row only, error raised, owner never called; **both ignored when `app_env="staging"`**;
- `ReactivateAccount` mirrors it (no `ADMIN` protection); a repeated request creates a **new** `action_id`; `GetAccount` returns only `identity_id`, `status`, `created_at`, `roles` and requires the permission; `ListAuditEvents` needs `ADMIN_AUDIT_VIEW`, filters and paginates, newest first;
- logs: no reason text and no account details in any captured log line.

**Acceptance criteria:** tests pass against fakes; no framework imports under `application/`.

---

### CHUNK 9 — STAFF MANAGEMENT
**[FOR YOU — GEMINI CLI]**

**Files:** `use_cases/list_staff.py`, `grant_staff_role.py`, `revoke_staff_role.py`.

Implement C8's rules around `AuditRecorder`: authorize `ADMIN_STAFF_MANAGE`; **manageable roles only (`OPERATIONS`)**; **no self-grant or self-revoke**; grant requires the target to exist and be `ACTIVE`; revoke of an unassigned role is a success no-op; Security's own authorization (it also checks `ADMIN_STAFF_MANAGE`) is a second, independent gate.

**Tests (fakes):** grant `OPERATIONS` → request + success rows with `details.role = OPERATIONS` and no other data; **`ADMIN`, `STUDENT`, `SCOUT` → `RoleNotManageable`, nothing audited, Security never called**; self-grant and self-revoke → `SelfActionNotAllowed`; nonexistent target → `AccountNotFound`; **inactive target → `AccountNotActive`** (grant only); repeated grant → success both times, two audited pairs, Security called idempotently; revoke when not assigned → success; non-`ADMIN` actors refused (`OPERATIONS` included); `ListStaff` returns identity ids and roles only (assert the DTO); Security failing → `FAILED` row and the error re-raised; no reason text in logs.

**Acceptance criteria:** tests pass against fakes.

---

### CHUNK 10 — RECOVERY ACTIONS
**[FOR YOU — GEMINI CLI]**

**Files:** `use_cases/requeue_dead_notification_events.py`, `requeue_failed_safety_enforcement.py`.

Per C8 and ADR-170, around `AuditRecorder`: `RequeueDeadNotificationEvents` needs `ADMIN_RECOVERY_RUN`; `RequeueFailedSafetyEnforcement` needs `ADMIN_RECOVERY_RUN` **and** `SAFETY_ENFORCEMENT_APPROVE`. Both record the returned count in the success row's `details`. **Nothing else is recoverable through this module.**

**Tests (fakes):** `OPERATIONS` refused on both; `ADMIN` allowed on notifications; **safety requeue needs both permissions** (an actor with only `ADMIN_RECOVERY_RUN` is refused — arrange with a policy fake); counts returned and audited; an owner failure → `FAILED` row and the owner's error re-raised; zero items → success with count 0; **a source scan proves the module has no recovery port or adapter for Payment, Booking, Housing, Messaging, or Verification**.

**Acceptance criteria:** tests pass against fakes.

---

### CHUNK 11 — OPERATIONAL ISSUES
**[FOR YOU — GEMINI CLI]**

**Files:** `use_cases/create_issue.py`, `list_issues.py`, `get_issue.py`, `assign_issue.py`, `change_issue_status.py`.

Implement C6 and ADR-165 exactly. `CreateIssue(actor, idempotency_key, category, title, description, priority, references)`: authorize `ADMIN_ISSUES_MANAGE`; validate (no safety category exists to choose); identical replay → the existing issue (`200`), same key with a different body → `IdempotencyKeyConflict`; one unit of work writes the issue and its `CREATED` event. `AssignIssue`: assignee must hold `ADMIN_ISSUES_MANAGE` (via `Authorizer`); allowed only in `OPEN`/`IN_PROGRESS`/`AWAITING_INFORMATION`; conditional update on `version`; `ASSIGNED` event. `ChangeIssueStatus(actor, issue_id, to_status, reason, resolution_summary)`: every requirement in C6; conditional update on `version` (`IssueStateChanged` on a lost race); a `STATUS_CHANGED` event whose `details` carry `from`, `to`, and — as applicable — `reason` / `resolution_summary`; **status never comes from a request field that skips the table**. `GetIssue` returns the issue and its history; `ListIssues` filters by `status`, `priority`, `assignee_id`, `category`, paginated.

**Tests (fakes unless stated):** every transition in C6 succeeds and every other raises, **with the issue unchanged and no history row written**; resolve without a (long enough) summary → `InvalidResolution`; reopen needs a reason and the **earlier summary remains in history**; assign: non-staff assignee refused, assignment in `RESOLVED`/`CLOSED` refused, a stale `version` → `IssueStateChanged` with nothing written; **each successful change writes exactly one history row in the same unit of work** (and neither on a failed commit); create idempotency (replay, conflict, the lost-race path through a fake `add` raising the unique signal); reference cap and types; `OPERATIONS` and `ADMIN` both allowed, `STUDENT`/`SCOUT` refused; **no code path in the module opens a Trust & Safety report** (source scan); issue text never appears in logs.

**Acceptance criteria:** tests pass against fakes.

---

### CHUNK 12 — THE OPERATIONAL OVERVIEW
**[FOR YOU — GEMINI CLI]**

**Files:** `use_cases/get_overview.py`, and the small helper that applies the `admin_debug_fail_section` guard (`local`/`test` only).

Implement C9 and ADR-164 exactly: authorize `ADMIN_OVERVIEW_VIEW`; the seven sections run **sequentially**, each with its own short-lived session and `asyncio.wait_for`; the status mapping (owner `Forbidden` → `NOT_AUTHORIZED`; timeout → `UNAVAILABLE`/`timeout`; any other exception → `UNAVAILABLE`/`source_error`, WARNING log with the section name and error class only); the two own sections read this module's repositories, `admin_actions` additionally requiring `ADMIN_AUDIT_VIEW` (else `NOT_AUTHORIZED`).

**Tests (fakes, `FixedClock`):**
- caller without `ADMIN_OVERVIEW_VIEW` → `Forbidden`; each of the seven sections returns the right shape from its fake source;
- **status mapping:** an owner raising `Forbidden` → `NOT_AUTHORIZED` with **no data and no reason code**; raising `RuntimeError` → `UNAVAILABLE`/`source_error` with **no data**; a source that sleeps past the timeout → `UNAVAILABLE`/`timeout`; **in each case every other section is unaffected**;
- **no fabrication:** assert that no unavailable or unauthorized section carries a `0`, an empty dict, or any default in `data`; no value is ever read from a previous call (two calls → each source called twice, and a changed fake value shows through);
- **least privilege by delegation:** every owner source is called with the **caller's** `actor_id` (assert on the fakes), and a caller who is `ADMIN`-like sees `verification` as `NOT_AUTHORIZED` while an `OPERATIONS`-like caller sees it `OK`;
- `admin_actions` is `NOT_AUTHORIZED` without `ADMIN_AUDIT_VIEW`; its counts come from `count_uncertain` with the configured threshold;
- `as_of` is the injected clock's time; the debug guard forces a named section to fail in `local`/`test` and is **ignored in `staging`**; logs contain no data values and no owner messages.

**Acceptance criteria:** tests pass; no framework imports under `application/`.

---

### CHUNK 13 — HTTP API
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/api/schemas.py`, `router.py`, `dependencies.py`; `app.py` (mount under `/api/v1/admin`).

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/admin/overview` | `ADMIN_OVERVIEW_VIEW` | seven sections |
| GET / POST | `/admin/operations/issues` | `ADMIN_ISSUES_MANAGE` | list (filters, paginated) / create (`201`, replay `200`) |
| GET | `/admin/operations/issues/{issue_id}` | `ADMIN_ISSUES_MANAGE` | issue + history |
| POST | `/admin/operations/issues/{issue_id}/assign` | same | `{assignee_id}` |
| POST | `/admin/operations/issues/{issue_id}/resolve` | same | `{resolution_summary}` |
| POST | `/admin/operations/issues/{issue_id}/status` | same | `{to_status, reason?}` for every other transition |
| GET | `/admin/audit-events` | `ADMIN_AUDIT_VIEW` | filters, paginated |
| GET | `/admin/accounts/{identity_id}` | `ADMIN_USERS_MANAGE` | status and staff roles |
| POST | `/admin/accounts/{identity_id}/disable` · `/reactivate` | `ADMIN_USERS_MANAGE` | `{reason}` |
| GET | `/admin/staff` | `ADMIN_STAFF_MANAGE` | `role` filter, paginated |
| POST | `/admin/staff/{identity_id}/roles` | `ADMIN_STAFF_MANAGE` | `{role, reason}` — grant |
| POST | `/admin/staff/{identity_id}/roles/{role}/revoke` | `ADMIN_STAFF_MANAGE` | `{reason}` |
| POST | `/admin/recovery/notification-events/requeue-dead` | `ADMIN_RECOVERY_RUN` | `{reason}` |
| POST | `/admin/recovery/safety-enforcement/requeue-failed` | `ADMIN_RECOVERY_RUN` (+ `SAFETY_ENFORCEMENT_APPROVE`) | `{reason}` |

All routes use the shared `get_current_identity_id`; authorization is inside the use cases. Request models `extra="forbid"` — an `actor_id`, `created_by`, `status`, or `identity` field in a body → `422`. Register static paths so `{issue_id}`/`{identity_id}` cannot shadow them. Responses are built from the DTOs, never ORM rows. **There is no route that forwards to Housing, Verification, Booking, Payment, or Trust & Safety** (ADR-163).

**Tests** (real HTTP, real database; accounts for a student, a scout, `OPERATIONS`, `ADMIN`, and a dual-role account):
- **every route** returns `401` unauthenticated and `403` for a student and a scout; the permission table above is enforced exactly (an `OPERATIONS` account gets `200` on overview and issues and `403` on audit, accounts, staff and recovery; an `ADMIN` gets `200` on all of them);
- bodies containing actor or status fields → `422`; validation errors in the standard shape;
- **accounts end to end with the real Identity:** disable with a reason → the target genuinely **cannot log in** (reuse Identity's login flow) until reactivated; the audit list shows the request and success rows with the right actor, **and the actor is the token's, never the body's**; self-disable → `403 self_action_not_allowed`; disabling an `ADMIN` → `403 admin_account_protected`; a missing/short reason → `422`;
- **staff end to end:** before the grant, the target gets `403` on `GET /verification/reviews/pending`; after `POST …/roles {OPERATIONS}` the **very next request** gets `200`; after revoke it is `403` again; granting `ADMIN` → `422 role_not_manageable`; self-grant → `403`; an `ADMIN`'s grant appears in the audit list with reason and role;
- **overview end to end** with real Verification, Payment, Trust & Safety, Notification and Messaging data: values match what the owners report; an `OPERATIONS` caller sees `verification` and the reviewer half of `safety`; an `ADMIN` caller sees `payments` and the approver half; **a section made to fail with the debug setting is `UNAVAILABLE` while the others stay `OK`**;
- issues end to end through the lifecycle, including a resolve without a summary (`422`), an invalid transition (`409 invalid_issue_transition`), replayed create (`200`), a stale concurrent update (`409 issue_state_changed`);
- recovery: dead Notification events and failed T&S enforcement requeued through the real owners; an `OPERATIONS` account refused; the audit list shows each;
- pagination on issues, audit, staff.

**Acceptance criteria:** app starts; tests pass; `lint-imports` clean; the report contains the **route table** for `/admin` and confirms none proxies an owner.

---

### CHUNK 14 — CORRECTION 1: RETIRE IDENTITY'S UNAUDITED ADMIN ROUTES
**[FOR YOU — GEMINI CLI]**

**Objective:** there must be exactly one way to disable or reactivate an account over HTTP, and it is audited (ADR-168). **Identity's use cases (`DisableAccount`, `ReactivateAccount`) and everything else in Identity must not change.**

1. Using the file list from Chunk 1 step 3, **remove** `POST /api/v1/auth/{identity_id}/disable` and `/reactivate` from Identity's router, their request/response schemas, their dependency wiring, and **only** the tests that exist solely for those two routes (`tests/api/identity/test_admin_endpoints.py`). Their behavior is already covered, strengthened, by Chunk 13's account tests.
2. Update Identity's module doc and API reference: the two paths are gone; point to `/api/v1/admin/accounts/{id}/disable|reactivate`.
3. **Do not touch** Trust & Safety's `AccountEnforcer` or any other caller of `DisableAccount`.

**Tests:** the two old paths now return `404`/`405` and are absent from the route table; **Identity's remaining suite passes unchanged** (`poetry run pytest tests/unit/identity tests/integration/identity tests/api/identity` shows exactly the pre-existing results minus the removed file); Trust & Safety's enforcement tests for `ACCOUNT_SUSPENSION` still pass; Chunk 13's account tests still pass.

**Acceptance criteria:** all pass; the report lists every file changed and confirms no Identity domain/application file was modified.

---

### CHUNK 15 — RELIABILITY & CONCURRENCY
**[FOR YOU — GEMINI CLI]**

**Objective:** prove the guarantees on a real database. Mostly tests; fix whatever they reveal. Every test file runs **three times in a row**.

**Tests** (`tests/integration/admin_operations/test_reliability.py`, committed data, `asyncio.gather`):
- **audit before action, proven across sessions:** an owner call that, **from a separate session**, queries the audit table at the moment it is invoked, finds the committed `ACTION_REQUESTED` row;
- **fail-closed:** make the audit write fail (inject a failing repository) → the account is **not** disabled;
- **uncertain outcome:** with `crash_after_request`, the request row exists with no outcome; after the configured threshold the **overview's `admin_actions` section reports exactly one uncertain action with the right oldest age**; once a normal retry completes, that old uncertain row is still reported (it is history, not self-healing) — documented;
- **downstream failure:** `downstream_fails` → request + `FAILED`, account unchanged, the error visible to the caller, **never** reported as success; an adapter raising `TimeoutError` → `FAILED` with the class name;
- **concurrent identical account actions:** two simultaneous disables of the same target → two distinct `action_id`s each with its own request and outcome rows, the account ends `DISABLED`, nothing lost;
- **concurrent issue updates:** two reviewers move one issue at once → exactly one succeeds, the other gets `issue_state_changed`, and the history shows exactly one transition; concurrent assignment likewise;
- **concurrent duplicate creates:** 10 simultaneous creates with one idempotency key → exactly one issue and one `CREATED` event;
- **audit/issue consistency:** a forced failure of the history write rolls back the issue change; every change has exactly one history row, in order;
- **immutability:** `UPDATE`/`DELETE` through the ORM on both history tables fail loudly (trigger), and no application path attempts it;
- **recovery on the real stack:** a dead Notification event requeued through the admin route is processed by Notification's worker; a failed Trust & Safety enforcement requeued returns to `APPROVED`; both audited;
- **overview under outage:** with each owner's source forced to fail in turn, only that section is `UNAVAILABLE`.

**Acceptance criteria:** all pass **three consecutive runs**; any defect is fixed in the responsible layer (never patched in a test) and noted in the report.

---

### CHUNK 16 — SECURITY, PRIVACY & REGRESSION SWEEP
**[FOR YOU — GEMINI CLI]**

**Files:** `tests/api/admin_operations/test_admin_security.py`; `pyproject.toml` import-linter contracts.

- **Authorization matrix:** for every route, a parametrized test over {unauthenticated, student, scout, operations, admin, dual-role} asserting the exact expected status. **No privilege implication:** `OPERATIONS` never reaches an `ADMIN`-only route; `ADMIN` still cannot read Trust & Safety notes or evidence content, cannot approve Payment releases it isn't entitled to beyond its existing grants, and gains no Verification permission from this module; granting `OPERATIONS` gives exactly `OPERATIONS`' permissions and nothing else.
- **Privacy:** no response or log line contains issue text, an audit reason, an account's email or credentials; audit responses contain only the stored columns; account lookup returns status and staff roles only.
- **Boundaries:** a source scan proves the module writes no other module's data except through the five outbound mutation ports (Identity disable/reactivate, Security assign/revoke, the two recovery adapters); **no module's tables are referenced**; no proxy routes exist (the `/admin` route table is compared against a written allow-list).
- **Retired routes:** Identity's two paths are absent.
- **Import-linter contracts** (extend the existing list): `admin_operations` `domain`/`application` import no other module and no `fastapi`/`sqlalchemy`; only `adapters/` import other modules' `application/ports`; **no other module imports `camp_match.modules.admin_operations`**. **Deliberately violate each once** (Security importing an A&O symbol; A&O's `application` importing Identity), confirm `lint-imports` fails, remove.
- **Full regression:** `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports` across **all fourteen modules**; then re-run Security's, Identity's, Verification's, Payment's, Messaging's (WebSocket files three times), Notification's and Trust & Safety's suites in isolation and confirm they are unchanged apart from the documented amendments and the removed Identity route tests.

**Acceptance criteria:** every test passes; no skipped or known-failing test.

---

### CHUNK 17 — DOCUMENTATION, MANUAL GUIDE & AI STATE
**[FOR YOU — GEMINI CLI — Part G at the end of this file is the source for the manual testing document]**

1. Write `docs/modules/admin_operations.md` per `09_DOCUMENTATION_RULES.md`: purpose and exclusions (the "delegate, don't duplicate" rule and the staff-tool map from Part F); responsibilities; authorization and the permission table; the issue lifecycle (C6); the audit design (C7) **including the uncertain-action procedure** (find the unresolved request, inspect the owner's actual state — e.g. `GET /admin/accounts/{id}` — decide, and act again through the normal route, which creates a new audited action); the overview's data-source table with definition, interface, authorization, freshness and failure behavior for **each** section; the cross-module contracts; failure and recovery instructions; persistence and transaction boundaries; the append-only guarantees; security and privacy; retention (**an unresolved product decision — nothing is deleted**); configuration; commands; limitations; extension points.
2. **Known limitations, listed plainly and individually:** no end-user ticket intake; staff cannot open Trust & Safety reports (ADR-173); no booking or payment exception views and no background-job health beyond owners' backlogs (ADR-174); no lookup by email; **`ADMIN` role grants are script-only and unaudited by design** (the server's shell is the root of trust), and two colluding administrators could still escalate through `OPERATIONS` grants (Finding 7 — a two-person approval is the named follow-up); an uncertain audit action is surfaced but never auto-reconciled; the overview is computed live per request, so it costs several small queries and has no history; no retention or purge for audit and issue records; the module is backend-only.
3. **Correct earlier documentation (Correction 3 and Correction 1/2):** in the Trust & Safety, Notification and Messaging module docs, rewrite every "Admin & Operations does not exist / no dashboard" limitation to state that the Admin & Operations module now provides the overview data and recovery actions, and that a staff UI remains to be built; update Security's doc (role management via the new use cases, `ADMIN` script-only) and Identity's doc (routes retired, Chunk 14).
4. Create `docs/modules/admin_operations_manual_testing.md` from Part G, **running every command you document** and correcting any that doesn't work.
5. Update the frontend API reference location **only with a pointer** — Nsisong maintains the Front End Doc from Part F.
6. Update `AI_state/`: all the standard files; `ARCHITECTURE_STATE.md` (the first module that only coordinates; request-before-outcome audit; the two corrections); `DATABASE_STATE.md`; `API_STATE.md` (the new `/admin` routes and the two removed Identity routes); `DECISIONS.md` (append ADR-162–174); `SESSION_HANDOFF.md`; `CURRENT_TASK.md`.

**Acceptance criteria:** every document exists and matches the implementation; every documented command was executed; limitations stated without softening.

---

### CHUNK 18 — FINAL AUDIT & COMPLETION REPORT
**[FOR YOU — GEMINI CLI]**

1. From a clean state (`scripts/db_stop.sh`, `scripts/db_start.sh`, `poetry run alembic upgrade head`) run the full four-command suite; then re-run **every concurrency/reliability file three times** as the last step.
2. Answer each plainly — not "done":
   - Can any audited action run without its committed request row? **yes/no, with the evidence.**
   - Can any action be reported as successful when the owner did not return success? yes/no.
   - Can any audit or issue-history row be changed or deleted, by application code or SQL? yes/no (the trigger tests).
   - Can any route reach an owner's data without going through the owner's use case, or proxy an owner's staff workflow? yes/no (the route table and source scan).
   - Can any actor grant `ADMIN`, grant a role to themselves, disable themselves, or disable an `ADMIN` account through the API? yes/no.
   - Does any overview value come from a cache, a default, or another module's tables? yes/no.
   - Does any log or response contain issue text, audit reasons, or account PII beyond the stored/defined fields? yes/no.
   - Do Identity's use cases, or any owner's existing behavior, differ from before other than the documented amendments and the removed Identity routes? yes/no, with evidence.
   - Does any module import Admin & Operations, or does its `domain`/`application` import another module? yes/no (import-linter).
3. **Readiness classification — do not round up:**
   - Overview, issues, audit, staff roles (`OPERATIONS`), account actions, two recovery actions: implemented? yes/no per capability.
   - `ADMIN` role management: **script-only** (ADR-169).
   - End-user ticket intake, booking/payment exception views, email lookup, two-person approval, staff-originated safety reports: **not implemented** (ADR-173/174).
   - Staff UI: **not part of this module.**
4. Report: completed requirements; every command and its real result; known limitations; unresolved decisions (including retention and the two-person approval question); **the exact recommended next step — noting this is the final MVP module and what remains is integration testing across all fourteen modules and the staff and public frontends.** Do not claim completion for anything unimplemented or unverified. Set `CURRENT_TASK.md` to "Admin & Operations complete. All MVP modules specified and implemented. Awaiting direction from Claude."

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

### The handoff's chunk sequence → this document
| Handoff chunk | Here | Note |
|---|---|---|
| 1 Inspection | Chunk 1 | adds checks that Modules 11–13 exist as specified, and locates Identity's two routes |
| 2 Scope and domain decisions | **Parts A and B** | decided up front (ADR-162…174) so Gemini doesn't decide them |
| 3 Contracts and authorization design | Part C, Chunks 2, 4 | permissions and Security's four use cases |
| 4 Domain and application design | Chunk 3 (domain), Chunks 8–12 (use cases) | |
| 5 Persistence and migrations | Chunk 5 | adds immutability triggers |
| 6 Administrative API foundation | Chunk 13 | |
| 7 Operational overview | Chunk 12 (use case), Chunks 6–7 (owner counts and adapters), Chunk 13 (route) | |
| 8 Operational issue management | Chunk 11 | |
| 9 Administrative action auditability | Chunk 8 (recorder), Chunk 5 (tables) | request-before-outcome design |
| 10 Cross-module administrative operations | Chunks 8–10 (accounts, staff, recovery) | **no proxies** for Housing, Verification, Booking, Payment, Safety — ADR-163 |
| 11 Operational health and recovery | Chunks 6, 10, 12 | backlog counts and two recovery actions only |
| 12 Security and privacy verification | Chunk 16 | |
| 13 Automated integration and regression | Chunks 15–16 | tests also live in every chunk |
| 14 Manual testing and documentation | Chunk 17 | also corrects earlier modules' docs |
| 15 Final audit | Chunk 18 | |
| *(not in the handoff)* | Chunk 2 (Security amendment), Chunk 6 (owner counts), **Chunk 14 (retire Identity's routes)** | corrections 1–2, findings 2–3 |

### The handoff's Section 16 tests → where each is proven
| Handoff item | Where |
|---|---|
| 16.1 authorization (unauthenticated, student, no permission, correct permission, no cross-grant, resource-level) | Chunks 8–13 (per use case and per route), Chunk 16 (full matrix) |
| 16.2 overview (approved contracts, partial failure, no fabricated numbers, authorization limits data, no private-table access, freshness) | Chunk 12 (fakes), Chunk 13 (end to end), Chunk 15 (outage per owner) |
| 16.3 issues (create/retrieve, invalid rejected, assignment rules, invalid transitions, unauthorized, concurrency, history, idempotency) | Chunk 11, Chunk 13, Chunk 15 |
| 16.4 audit (records produced, actor correct, success vs failure, target/time/correlation, no sensitive data, restricted reads, audit-failure policy) | Chunks 5, 8, 13, 15 |
| 16.5 cross-module (each owner via its public contract; downstream rejection represented accurately; no direct DB access) | Chunks 7, 13, 16. **Listing, booking, payment and verification *write* operations: not applicable — this module deliberately has none** (ADR-163); their *read* counts are exercised through the overview |
| 16.6 reliability (timeouts, repeats, uncertain outcomes, database failure, worker interruption, concurrency, regression) | Chunk 15; "worker interruption" is **not applicable — there is no worker**; the equivalent is the crash-after-request uncertain-outcome test |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**This is for an internal staff tool, not the public app.** Routes are under `/api/v1/admin`, authenticated with `Authorization: Bearer <access_token>`. Errors use `{"error": {"code", "message"}}`. A normal user (student or scout) always gets `403` on every route here.

### ⚠ Breaking change — update anything that calls the old account routes
`POST /api/v1/auth/{identity_id}/disable` and `POST /api/v1/auth/{identity_id}/reactivate` **no longer exist.** Use `POST /api/v1/admin/accounts/{identity_id}/disable` and `/reactivate`. Same permission, but a written **reason is now required**, you can't disable yourself, you can't disable an administrator account, and every action is recorded in the audit trail.

### Who can do what
| Role | Overview | Issues | Audit | Account actions | Staff roles | Recovery |
|---|---|---|---|---|---|---|
| **Operations** | ✓ | ✓ | – | – | – | – |
| **Admin** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Roles are checked on every request, so a role change takes effect on the person's very next request — no re-login.

### GET /api/v1/admin/overview
Returns independent **sections**. Each is `{ "status": "OK" | "UNAVAILABLE" | "NOT_AUTHORIZED", "as_of": "…", "data": {…} | null, "reason_code": "timeout" | "source_error" | null }`.
```json
{ "verification":  { "status": "OK", "as_of": "…", "data": { "pending_reviews": 4 } },
  "payments":      { "status": "NOT_AUTHORIZED", "as_of": "…", "data": null },
  "safety":        { "status": "OK", "as_of": "…", "data": { "reviewer": { "reports_awaiting_triage": 3, "open_cases_by_status": { "OPEN": 1, "IN_REVIEW": 2 }, "high_or_urgent_open_cases": 1 }, "approver": null } },
  "notifications": { "status": "OK", "as_of": "…", "data": { "pending": 0, "dead": 1 } },
  "messaging":     { "status": "UNAVAILABLE", "as_of": "…", "data": null, "reason_code": "timeout" },
  "issues":        { "status": "OK", "as_of": "…", "data": { "open_by_status": { "OPEN": 2 }, "unassigned_open": 2, "high_priority_open": 0 } },
  "admin_actions": { "status": "OK", "as_of": "…", "data": { "uncertain_actions": 0, "oldest_age_seconds": null } } }
```
**How to show it:** `OK` → the numbers. `NOT_AUTHORIZED` → hide the tile or show "no access" — it is normal, not an error, and depends on the person's role. `UNAVAILABLE` → "couldn't load" with a retry; **never show a zero** for it. The numbers are live, not cached. `dead` notification events, `uncertain_actions`, `enforcement_failed` and a growing `outbox_pending` are the ones that mean "someone should look."

### Operational issues — `/api/v1/admin/operations/issues…`
Internal support tracker. **Created by staff only** — there is no customer-facing ticket form yet. **Safety concerns (fraud, harassment, threats) are not issues:** ask the affected user to file a report in the app.
`POST` body: `{ "idempotency_key", "category" (ACCOUNT | LISTING | BOOKING | PAYMENT | VERIFICATION | PLATFORM | OTHER), "title", "description", "priority" (LOW | NORMAL | HIGH), "references": [ { "type": "IDENTITY" | "LISTING" | "BOOKING" | "PAYMENT" | "VERIFICATION_CASE", "id": "…" } ] }` (up to 5 references; they are pointers for people to click — the server never looks them up). Reuse the same key to retry a create safely (`200`, same issue).
`GET` list: filters `status`, `priority`, `assignee_id`, `category`; paginated. `GET /{id}` returns the issue and its history.
`POST /{id}/assign` `{assignee_id}` (the assignee must be staff). `POST /{id}/resolve` `{resolution_summary}` (required, at least 10 characters). `POST /{id}/status` `{to_status, reason?}` for everything else.
**Statuses:** `OPEN` → `IN_PROGRESS` (needs an assignee) ⇄ `AWAITING_INFORMATION` (needs a reason) → `RESOLVED` → `CLOSED`; a `RESOLVED` issue can be reopened to `IN_PROGRESS` with a reason. `CLOSED` is final. **Errors:** `409 invalid_issue_transition`, `409 issue_state_changed` (someone else changed it — reload), `422 invalid_resolution`, `404 issue_not_found`.

### Accounts — `/api/v1/admin/accounts/{identity_id}` (admin)
`GET` → `{identity_id, status, created_at, roles}` (status and staff roles only; lookup is **by id**, not email). `POST …/disable` and `…/reactivate` with `{"reason": "…"}` (at least 10 characters). **Errors:** `403 self_action_not_allowed`, `403 admin_account_protected` (an administrator account can't be disabled here), `404 account_not_found`, `422 invalid_reason`. If the account service itself is down you get its real error and the audit trail records a failure — **an action is never reported as done unless it was.**

### Staff roles — `/api/v1/admin/staff` (admin)
`GET /staff` → people holding a staff role (`role` filter, paginated). `POST /staff/{identity_id}/roles` `{"role": "OPERATIONS", "reason": "…"}` grants it; `POST /staff/{identity_id}/roles/OPERATIONS/revoke` `{"reason": "…"}` removes it. **Only `OPERATIONS` can be granted here** (`422 role_not_manageable` for anything else — administrators are created outside the app on purpose). You can't change your own roles (`403 self_action_not_allowed`), and the person must have an active account (`422 account_not_active`). Granting twice is harmless.

### Recovery — `/api/v1/admin/recovery/…` (admin)
`POST …/notification-events/requeue-dead` and `POST …/safety-enforcement/requeue-failed`, each `{"reason": "…"}` → `{"action_id", "requeued": N}`. The second also needs the safety-approver permission. These only ask the owning system to retry its own failed work; there is **no** payment, booking or listing retry here, by design.

### Audit — `GET /api/v1/admin/audit-events` (admin)
Filters `actor_id`, `action_type`, `target_id`, `from`, `to`; newest first; paginated. Each action appears as an **`ACTION_REQUESTED` row followed by `ACTION_SUCCEEDED` or `ACTION_FAILED`**, linked by `action_id`. **A request with no outcome after about five minutes is an "uncertain" action** (the server stopped between asking and finishing): check the real state (e.g. the account's status) before deciding to repeat it. Rows are permanent and can't be edited.

### Where staff do everything else (do **not** look for it under `/admin`)
| Task | Where it lives |
|---|---|
| Review verification cases | `/api/v1/verification/reviews/pending` and `/verification/cases/…` (operations) |
| Payment disputes, release, refund | `/api/v1/payments/disputes/pending`, `/payments/disputes/{id}/resolve`, `/payments/{id}/release`, `/payments/{id}/refund` (operations review; release/refund authorizations are admin-only) |
| Safety reports, cases, enforcement | `/api/v1/safety/review/…` |
| Confirm or cancel a booking | Booking's own staff routes (Module 9) |
| Take a listing down for safety | Safety enforcement (listing suspension), not a listing edit |
| Disable or reactivate an account | `/api/v1/admin/accounts/…` (above) |
| Grant or remove operations access | `/api/v1/admin/staff/…` (above); **administrator access is granted outside the app** |

**Known limitations (tell your product people):** no customer-facing support tickets; staff can't file a safety report themselves; no booking or payment exception dashboard; no lookup by email; no payment retry tools; administrator roles can't be managed in the app; no staff screen exists yet — this is the data and actions for one.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — and Gemini's source for the manual-testing document in Chunk 17]

**Preconditions:** `scripts/db_start.sh` running; app running; Modules 9–13 working. Accounts: **Rita** (`OPERATIONS`), **Ade** (`ADMIN`), **Dual** (both roles), **Ada** (Student), **Chidi** (Student — the target for staff grants), **Bola** (Scout). Assign roles with the project's role-assignment script *(Gemini verifies the exact command and writes it down)*. Keep each person's access token. `curl` with `Authorization: Bearer <token>`. Anything marked **(Gemini verifies)** is a table, column or argument Gemini must confirm in Chunk 17 — the guide may contain only commands that were actually run.

Format: **verifies** · **why** · **steps** · **expect** · **if it fails**.

**A1 — Overview as an operations account.** *Steps:* Rita `GET /admin/overview`. *Expect:* `verification` and the **reviewer half** of `safety` are `OK`; `notifications`, `messaging`, `issues` are `OK`; `payments` is `OK` (operations hold payment review) *(Gemini verifies against the real policy)*; `admin_actions` is `NOT_AUTHORIZED`. Cross-check one number against the owner (e.g. `GET /verification/reviews/pending` total). *Why:* the overview must reflect the owners, not invent figures. *If it fails:* a number that disagrees with its owner is blocking.

**A2 — Overview as an admin: different sections.** *Steps:* Ade `GET /admin/overview`. *Expect:* `verification` is `NOT_AUTHORIZED`; `payments` is `OK`; `safety` shows only the **approver** half; `admin_actions` is `OK`. *Why:* each owner decides who sees its data, so the page differs by person. *If it fails:* Ade seeing verification counts means authorization isn't delegated to the owner — blocking.

**A3 — Ordinary users are refused.** *Steps:* no token, then Ada's and Bola's tokens, on `/admin/overview`, `/admin/operations/issues`, `/admin/audit-events`. *Expect:* `401` without a token, `403` for Ada and Bola on all three. *If it fails:* any `200` is blocking.

**A4 — A failing source never becomes a fake number.** *Verifies:* truthful partial results. *Steps:* set `ADMIN_DEBUG_FAIL_SECTION=messaging` (local only), restart, Rita `GET /admin/overview`. *Expect:* `messaging` is `UNAVAILABLE` with `reason_code: "source_error"` and **`data: null`** — not 0 — while every other section is unchanged. Unset it and restart. *If it fails:* a zero, or the whole page failing, is blocking.

**A5 — Permission boundaries between staff.** *Steps:* Rita tries `GET /admin/audit-events`, `GET /admin/staff`, `GET /admin/accounts/<Ada's id>`, and `POST /admin/recovery/notification-events/requeue-dead`; Ade tries the same. *Expect:* Rita `403` on all four; Ade `200`. *Why:* least privilege. *If it fails:* any `200` for Rita is blocking.

**A6 — Issue lifecycle, valid and invalid.** *Verifies:* an issue only moves along legal paths, and every change is recorded. *Why:* the status is not a free-text field. *Steps:* Rita creates an issue (category `PAYMENT`, priority `HIGH`, one `PAYMENT` reference) and sends the **identical** request again; tries to move it to `IN_PROGRESS` before anyone is assigned; assigns it to **Ada** (a student); assigns it to **Ade**; moves it to `IN_PROGRESS`; moves it to `AWAITING_INFORMATION` with no reason, then with a reason; back to `IN_PROGRESS`; tries `CLOSED` straight from `IN_PROGRESS`; resolves with no summary, then with one; closes it; then tries any further change. Finally `GET` the issue. *Expect:* the repeated create returns the **same** issue (`200`); `IN_PROGRESS` without an assignee is refused; assigning to Ada is refused (she isn't staff), to Ade accepted; `AWAITING_INFORMATION` without a reason refused; `CLOSED` from `IN_PROGRESS` → `409 invalid_issue_transition`; resolving without a summary → `422 invalid_resolution`; every change after `CLOSED` → `409`; the issue's history has **exactly one entry per accepted change, in order**. *If it fails:* any accepted illegal transition, or a missing or duplicated history entry, is blocking.

**A7 — Audited account disable, and the old routes are gone.** *Steps:* Ade `POST /admin/accounts/<Chidi's id>/disable` with a reason; Chidi tries to log in; Ade `GET /admin/audit-events`; Ade tries to disable **himself**; Ade tries to disable **Dual** (an admin); Ade reactivates Chidi; then call the **old** `POST /api/v1/auth/<id>/disable`. *Expect:* success; Chidi **cannot log in** until reactivated; the audit shows `ACTION_REQUESTED` then `ACTION_SUCCEEDED` with Ade as actor and the reason; the self-disable → `403 self_action_not_allowed`; disabling an admin → `403 admin_account_protected`; the old route → `404`/`405`. *If it fails:* an action with no audit rows, the actor being anything but Ade, or the old route still working is blocking.

**A8 — A downstream failure is recorded and not reported as success.** *Steps:* set `ADMIN_DEBUG_ACCOUNT_ACTION_MODE=downstream_fails` (local only), restart; Ade tries to disable Chidi; check Chidi's account and the audit list. Unset and restart. *Expect:* an error response; **Chidi is still active**; the audit shows `ACTION_REQUESTED` then **`ACTION_FAILED`** with an outcome code. *If it fails:* a success response, or a disabled Chidi, is blocking.

**A9 — An uncertain outcome is surfaced.** *Verifies:* a crash between "asking" and "finishing" is detectable. *Steps:* set `ADMIN_DEBUG_ACCOUNT_ACTION_MODE=crash_after_request` and `ADMIN_AUDIT_UNCERTAIN_AFTER_SECONDS=5`, restart; Ade tries to disable Chidi (an error); wait 10 seconds; Ade `GET /admin/overview`; check Chidi's real status with `GET /admin/accounts/<id>`; unset both, restart, and disable Chidi properly. *Expect:* the action returns an error; the audit has a request row **with no outcome**; `admin_actions` shows `uncertain_actions: 1` with a growing `oldest_age_seconds`; Chidi is still active (the action never ran); the later proper disable is a **new** audited action. *If it fails:* an invented outcome row, or `uncertain_actions: 0`, is blocking.

**A10 — Staff management takes effect immediately, and is guarded.** *Steps:* Chidi `GET /verification/reviews/pending` (`403`); Ade grants Chidi `OPERATIONS` with a reason; Chidi repeats the call **with the same token**; Ade revokes it; Chidi repeats; Ade tries to grant `ADMIN` to Chidi; Ade tries to grant a role to **himself**; grant to a disabled account. *Expect:* `403` → `200` → `403` with no re-login; `ADMIN` grant → `422 role_not_manageable`; self-grant → `403 self_action_not_allowed`; a disabled target → `422 account_not_active`; the audit shows each grant and revoke with reason and role. *If it fails:* a role needing a re-login, or any `ADMIN` grant succeeding, is blocking.

**A11 — Recovery actions.** *Verifies:* two failed-work retries exist, are audited, and nothing financial can be retried here. *Why:* operators need a safe way to recover stuck work. *Steps:* following Module 12's guide (N12) create a dead notification event (`NOTIFICATION_DEBUG_FAIL_PROCESSING=true`, `NOTIFICATION_INBOX_MAX_ATTEMPTS=1`), then unset the flags and restart; Ade `POST /admin/recovery/notification-events/requeue-dead`; run `poetry run python scripts/run_notification_worker.py`; Rita tries the same route. Then, with a failed safety enforcement in place (Module 13's guide, S12 with exhausted attempts) *(Gemini verifies a quick way to produce one)*, Ade `POST /admin/recovery/safety-enforcement/requeue-failed`. Finally `GET /admin/audit-events`. *Expect:* `{"requeued": N}` with N ≥ 1; the dead event is processed by the worker; Rita `403`; the failed enforcement returns to `APPROVED`; the audit shows each action with its reason and count. (The rule that safety recovery also needs the safety-approver permission is proven by the automated tests with a policy fake — under the real policy both permissions belong to `ADMIN`.) *If it fails:* a requeued event that never processes, or an unaudited recovery, is blocking; and **there must be no recovery route for payments, bookings or listings — finding one is blocking.**

**A12 — Audit access and permanence.** *Steps:* Ade lists the audit with filters (`actor_id`, `action_type`, a date range) and pages; Rita tries (`403`); in `psql` try to change and delete rows *(Gemini verifies:* `update admin_audit_events set reason = 'x' where id = '<id>'` *and* `delete from admin_audit_events …`*, and the same for `admin_issue_events`)*. *Expect:* filters and pagination correct and stable; Rita `403`; every direct `UPDATE`/`DELETE` **fails** with the database's immutability error. *If it fails:* a successful edit or delete is blocking.

**A13 — Regression.** *Steps:* `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`. *Expect:* all green, including Identity's suite (minus the two removed route tests) and every other module. *If it fails:* note the module and test and stop.

**Intentionally absent:** customer-facing ticket tests, booking/payment exception views, email lookup, two-person approval, and any payment/booking/listing recovery — not implemented (ADR-174, ADR-170).

**Automated tests:** `poetry run pytest tests/unit/admin_operations tests/integration/admin_operations tests/api/admin_operations` · fast, no database: `poetry run pytest tests/unit/admin_operations -v` · reliability, three times: `for i in 1 2 3; do poetry run pytest tests/integration/admin_operations/test_reliability.py; done` · everything: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] Every audited action has a **committed request row before** the owner is called, an outcome row after, and fails closed if the request row can't be written; success is reported only on the owner's confirmed success; an uncertain action is surfaced, never invented away — proven on a real database.
- [ ] Audit and issue-history rows cannot be changed or deleted — the database triggers refuse it, and no application path tries.
- [ ] Identity's two unaudited admin routes are gone; disable/reactivate exist only as audited admin routes with a reason, no self-action, and no disabling an administrator; Identity's use cases and other behavior are unchanged.
- [ ] Staff management grants/revokes **`OPERATIONS` only**, never `ADMIN`; no self-grant; target must be active; changes take effect on the next request; every change audited.
- [ ] The overview delegates authorization to each owner (called **as the caller**), marks sections `OK` / `UNAVAILABLE` / `NOT_AUTHORIZED` truthfully, and never shows a cached, defaulted, or fabricated value.
- [ ] No proxy routes exist for Housing, Verification, Booking, Payment or Trust & Safety; the `/admin` route table matches the written allow-list.
- [ ] Only two recovery actions exist, both through their owners' use cases, both audited; nothing financial, booking or listing-related is recoverable here.
- [ ] Operational issues follow the lifecycle table, with conditional updates on `version`, required resolution summaries, idempotent creation, and one history row per change in the same transaction; no safety category and no Trust & Safety report is opened from here.
- [ ] `ADMIN` still cannot read Trust & Safety notes or evidence; `OPERATIONS` reaches no `ADMIN`-only route; this module adds no Verification, Payment or Safety permission to anyone.
- [ ] No module imports Admin & Operations; its `domain`/`application` import no other module — both contracts proven with deliberate-violation checks; no module's tables are referenced.
- [ ] Security, Trust & Safety and Messaging changed only as documented; Housing, Booking, Verification, Payment, Notification, Profile, Search, Media/File untouched; all fourteen modules' suites pass.
- [ ] `docs/modules/admin_operations.md`, the manual guide and `AI_state/` are written; earlier modules' "Admin & Operations does not exist" wording is corrected; every documented command was run; limitations are stated without softening — especially: administrator roles are script-only and unaudited by design, two colluding admins could still escalate through `OPERATIONS` grants, no ticket intake, no staff-originated safety reports, no booking/payment exception views, no retention policy.
- [ ] The Chunk 18 readiness classification is recorded honestly.
