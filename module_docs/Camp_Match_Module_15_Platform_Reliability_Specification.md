# CAMP MATCH — MODULE 15: PLATFORM RELIABILITY & LIFECYCLE INTEGRATION
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Nsisong → Claude, gap-closure and lifecycle-integration request. Scope and five design decisions were confirmed by Nsisong before this file was written (see Part B).**

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** You do not copy chunks or parts. Gemini reads the complete document, then works through the chunks **in order, one at a time**. When a chunk is finished, Gemini stops and gives you a Completion Report; you check it and reply **"Proceed to Chunk N"** (or send corrections). Parts marked **[FOR NSISONG]** are for you — decisions, frontend documentation, the coverage matrix, the manual testing guide — and Gemini reads them only for context.

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

You are the implementation agent for this module. You have been given the **complete** specification in this one file.

1. **Read the entire file before doing anything.** Parts marked **[FOR NSISONG]** are for the human: read them for context and rationale, but they are not instructions to you. **The Design Specification (Part C) is the reference you must internalize fully** — every chunk points back to it ("Part C4", "ADR-176" and so on mean sections of this file). **Part D is your work**, in numbered chunks. **Part G (Manual Testing Guide)** is the source material for the manual-testing document you write in Chunk 24.
2. **Your first action is Chunk 1.** It is inspection and scaffolding and writes no behavior. Do not write any other code first.
3. **Work one chunk at a time, in order.** Do not start a chunk until Nsisong has replied "Proceed to Chunk N". Never combine, reorder, skip, or work ahead — not even small "preparatory" edits for a later chunk.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; every file created or changed; every command you ran with its **real** output; each acceptance criterion marked pass or fail; any deviation, surprise, or open question. Claim nothing you did not verify.
5. **If anything blocks you — a failing acceptance item, the repository contradicting this file, two parts of this file disagreeing, or a decision this file does not make — stop and report it.** Do not choose for yourself, skip a test, weaken a test, or work around it.
6. The Standing Instructions in `AI_instructions/` apply to everything. Change only the files a chunk names (plus anything the Part C16 touch map allows). **This module amends eight finished modules; after every chunk that touches one, re-run that module's full test suite and confirm it is unchanged apart from the documented additions.**

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

This module is different from the ones before it. It is **not a new business domain.** It closes the gaps the first fourteen modules left on purpose, and it connects the modules to each other so that one thing happening in one place has the right effect everywhere else. It therefore **amends** Booking, Housing, Notification, Payment, Messaging, Admin & Operations, Trust & Safety, Verification and Identity — each in a small, fully specified way — and adds one new package, `modules/platform_runtime/`, for the two pieces of shared machinery (the shared event outbox and the background-job runner).

**Explicitly NOT in this module, by your instruction:** the production file/media storage adapter (local storage stays as the test setup), the real payment-provider adapter, automatic refunds (refunds stay a manual `ADMIN` action), and message attachments (they depend on media storage). Email/push delivery and a notification-preferences screen are also not here.

It has **25 chunks**. That is large because it touches many modules; each chunk is small and each leaves the whole suite green.

---

## PART A — FINDINGS AND CORRECTIONS [FOR NSISONG]

### CORRECTIONS I MADE (earlier documents said things that are no longer true after this module)

**Correction 1 — "no scheduler, no daemon" is reversed, for one dedicated process.**
Modules 9–13 each said their work ran from a one-shot script and deliberately had "no loop, daemon or scheduler." That was the right call while the modules were being built one at a time. It is the wrong call for a running application: today, if nobody runs five scripts by hand, **bookings never expire (their inventory stays locked), message and booking notifications never arrive, and approved safety enforcement is never applied.** You chose a **dedicated worker process** (ADR-181). The scripts stay as manual escape hatches; they run the same use cases.

**Correction 2 — "Existing bookings on the listing are untouched" (Module 13, C12) is reversed.**
Module 13 left bookings alone because Booking owns them. That is still the rule: Housing will **announce** that a listing was suspended, and **Booking** will react and change its own bookings. Nothing else writes to a booking.

**Correction 3 — Trust & Safety's two listing notifications are retired (ADR-186).**
`LISTING_SUSPENDED` and the listing form of `RESTRICTION_LIFTED` came from Trust & Safety. After this module Housing is the single source of listing-suspension facts, and Notification listens to Housing. Keeping both would send the scout two notices for one suspension. Trust & Safety stops publishing those two; its communication-restriction notices are unchanged.

**Correction 4 — the scout's "booking confirmed" notice changes from information to a request (ADR-196).**
Today it says a booking "has been confirmed." It will now tell the scout to arrange handover and confirm it. Old rows keep their old text; new rows use the new text.

### FINDING 1 — events can be lost in a crash (the gap I reported)
Booking, Verification and Trust & Safety publish their events **after** the database commit. If the server dies in the instant between the two, the change is saved but nobody is told. Messaging does not have this gap because it writes its event inside the same transaction and a relay delivers it later. **Fix (ADR-175 … ADR-180):** one shared **transactional outbox**. The event is written in the same transaction as the change, a fast post-commit "nudge" delivers it immediately, and a relay job guarantees it eventually arrives even after a crash. Housing and Payment, which publish nothing today, publish through it from day one.

### FINDING 2 — everything that should be automatic is manual
Five scripts do ongoing work and must currently be run by hand (`run_messaging_outbox_relay.py`, `run_notification_worker.py`, `run_safety_worker.py`, `expire_booking_holds.py`, `run_payment_recovery.py`); this module adds a sixth job, the shared outbox relay. (Chunk 1 confirms the full list.) **Fix (ADR-181 … ADR-184):** one worker process, one command, every job on its own interval, a database lease so two workers can never run the same job at once, and job health shown in the Admin overview. Human-judgement actions (`--requeue-dead`, `--requeue-failed`) stay manual. The 48-hour automatic payment release is automated **but switched off by default**, because moving money on a timer should never turn on by accident before the real payment provider exists.

### FINDING 3 — a suspension only reaches the listing itself
Today a suspended listing disappears from search because search requires `PUBLISHED`, but nothing touches the bookings on it, a student with an unpaid hold keeps the room locked, and the scout is told nothing about the bookings. A **disabled scout account** is worse: its listings stay published and bookable. **Fix (ADR-186 … ADR-193):** Housing announces suspensions; Booking cancels every live booking on the listing with a clearly stated reason; a disabled scout's listings are suspended the same way and restored (to `UNAVAILABLE`, never auto-republished) on reactivation. A reconciliation sweep catches anything missed and anything suspended before this module existed.

### FINDING 4 — notifications describe things; they don't ask for things
The booking flow needs people to **act** (student pays; scout confirms handover; student accepts), but Notification only records that something happened. **Fix (ADR-194 … ADR-196):** a notification can carry a fixed **action** that stays "open" until the action happens or the booking closes, and the app can ask for "just the things I need to do."

### FINDING 5 — why the mock payment controls failed silently
Three separate causes, all real: (1) the request models accept anything, so an invented scenario or arbitrary JSON is "valid"; (2) an unknown scenario silently falls back instead of being refused; (3) the webhook use case deliberately **acknowledges everything** (correct for a real provider, which must not retry forever) but returns nothing about what actually happened, so the control endpoint can only say "ok." **Fix (ADR-197 … ADR-199):** strict typed requests with dropdown values, a diagnostic report that says what changed and why not, an inspect endpoint, student notifications for failed or late payments, and a repo-wide guard so no request model anywhere accepts unknown fields again.

### FINDING 6 — rate limits and realtime only work in one process
Both are in memory (ADR-122/123). **Fix (ADR-201, ADR-202):** a Postgres-backed rate limiter and a Postgres `LISTEN/NOTIFY` realtime gateway, each behind the **existing** port and passing the **existing** contract tests. Both are opt-in through settings; the in-memory ones remain the default.

### FINDING 7 — operational tables grow forever
Outboxes, inboxes and read notifications are never cleaned. **Fix (ADR-185):** a daily retention job that purges **only** delivered/processed operational rows. Audit, history, safety, issue, booking and payment records are never touched.

### FINDING 8 — one admin can grant `OPERATIONS` alone
**Fix (ADR-200):** an optional two-person rule. Built and tested, **off by default** so a one-admin team is never locked out.

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-175 … ADR-203)

| ADR | Decision | Why |
|---|---|---|
| 175 | **One shared transactional outbox**, table `platform_outbox`. A shared-kernel `UnitOfWork` gains `add_event(event)`; collected events are written **in the same database transaction** at commit and discarded on rollback | Closes Finding 1 for every producer at once, using the one place all producers already go through |
| 176 | **Two delivery paths, one use case.** After a successful commit the UoW makes a best-effort **nudge** (immediate delivery); a **relay job** delivers anything still pending. Delivery is **at-least-once**, so **every subscriber must be idempotent** | Fast in the normal case, guaranteed in the crash case. The rule "subscribers are idempotent" is already true of Notification (inbox primary key) and is made true of the new Booking and Housing subscribers |
| 177 | **Event contracts are registered**, not pickled: each producer registers `(event_type, class, to_payload, from_payload)`; payloads carry **ids and enums only**. An unknown type or invalid payload goes straight to `DEAD` with a code | Deserialization must be explicit and safe; matches Notification's strict-parser stance |
| 178 | **Messaging's own outbox is untouched.** The relay job calls its existing dispatcher. Two outboxes exist and are documented | Messaging's is proven, has its own tests and ordering semantics; rewriting it buys nothing |
| 179 | **Producers migrate** from `publish_best_effort` after commit to `uow.add_event` in the transaction: Booking, Verification, Trust & Safety, and Identity's `AccountDisabled`/`AccountReactivated`. **What is published, and when, does not change.** `UserRegistered` (no subscriber) stays as it is | Only events that someone depends on need the guarantee |
| 180 | **Failure policy:** backoff `min(cap, base·2^(attempts-1))`, `max_attempts` then `DEAD`; `DEAD` rows are requeued only by an audited Admin recovery action | Same shape as Notification's inbox |
| 181 | **A dedicated worker process**, `scripts/run_platform_worker.py`: one asyncio task per job, each with its own interval, graceful shutdown. *(Nsisong's decision.)* | One command replaces five. Matches the single-API-process setup while allowing a second worker later |
| 182 | **Jobs wrap existing use cases; they re-implement nothing.** The old scripts stay and run the same use cases | No drift between "run by hand" and "run by the worker" |
| 183 | **Database lease per job** in `platform_jobs` (one row per job: lease + latest status). Not a history table | Two workers can never run one job at once; the table stays tiny |
| 184 | **`payment_auto_release` is disabled by default** (`platform_jobs_disabled`) | Money must not move on a timer by accident |
| 185 | **Retention touches operational tables only**, through a purge use case owned by each module; never `PENDING`/`DEAD` rows | Audit and money records are never deleted |
| 186 | **Housing is the single source of listing-suspension facts:** `ListingSuspended`, `ListingSuspensionLifted`, each with a `reason_code`. Trust & Safety retires its two listing notification kinds | One suspension → one notice, whatever caused it |
| 187 | Listings gain `suspension_reason` (`SAFETY_ENFORCEMENT`, `OWNER_ACCOUNT_DISABLED`). **A safety suspension always wins** over an account-disable suspension | Reactivating an account must never lift a safety suspension |
| 188 | **A disabled scout's listings are suspended** (reason `OWNER_ACCOUNT_DISABLED`); reactivation lifts **only those** to `UNAVAILABLE`, never to `PUBLISHED`. *(Nsisong: yes.)* | Same pipeline, same safety properties |
| 189 | **Invalidated bookings are `CANCELLED`** with `cancelled_by = NULL` and a structured `closure_code`; a new event `BookingInvalidated` is published, **never** `BookingCancelled`. *(Nsisong's decision.)* | No new status to chase through Payment and the frontends; no duplicate notices |
| 190 | **Every terminal booking carries a `closure` object** `{code, message}` with fixed messages | "The reason is clearly stated," for expired and user-cancelled bookings too |
| 191 | **System-initiated use cases have no actor** (the precedent is Payment's automatic release) and are protected **structurally**: a guard test fails if any HTTP router can reach one | No fake "system user" identity to forge |
| 192 | **Suspension reaction is event-driven plus a reconciliation sweep** | Events deliver the normal case; the sweep catches misses and pre-existing suspensions |
| 193 | **Paid bookings that get invalidated:** refunds stay a manual `ADMIN` action in Payment; Payment's logic does not change for refunds. Automatic release is already blocked for a booking that is not `CONFIRMED` (Chunk 1 proves it). *(Nsisong: OK.)* | Payment is excluded from this module; the funds simply stay held and visible |
| 194 | **Action-required notifications:** `action` + `resolved_at` on a notification; never collapse; resolved by events | The app can show a real to-do list |
| 195 | New Booking events `HandoverOffered`, `HandoverAccepted`; two one-time **reminders** guarded by claim columns on the booking | Reminders without a separate scheduler table and without duplicates |
| 196 | Student gets a **"complete payment"** action when a hold is created; the scout's "confirmed" notice becomes the **"arrange handover"** action | Every moment someone must act is surfaced |
| 197 | Payment: `ProcessWebhookEvent` **returns** a `WebhookProcessingOutcome`; new `PaymentOutcomeRecorded` event; three student notices. **Nothing else in Payment changes** | The one bounded Payment touch this module needs |
| 198 | Mock controls become **strict, typed and diagnostic**; new `scenarios` and inspect endpoints | Finding 5 |
| 199 | **Architecture guard:** every HTTP request model rejects unknown fields (`extra="forbid"`), with a short reviewed allow-list | Stops the whole class of "silently accepted" requests |
| 200 | **Two-person role-grant approval**, setting `admin_role_grant_requires_second_approver`, **default off** | Safe default for a small team |
| 201 | `PostgresRateLimiter` (fixed window) behind the existing `RateLimiter` port | Cross-process limits without Redis |
| 202 | `PostgresNotifyRealtimeGateway` (ids-only payloads) behind the existing `RealtimeGateway` port | Cross-process realtime without Redis |
| 203 | Admin overview gains `background_jobs` and `platform_events` sections and `GET /admin/jobs` | Job health is visible, truthfully |

### Decisions you already made (recorded)
1. Invalidated bookings use `CANCELLED` with a system reason (not a new status). 2. Refunds for paid, invalidated bookings stay manual. 3. A dedicated worker process. 4. Two-person role grants: built, default off. 5. A disabled scout's listings and bookings are included.

### Three small things worth a glance (I chose a default; tell me if you disagree)
- **Wording promise:** the student's "booking cancelled because the listing is no longer available" notice says *"If you already paid, our team will review your payment."* It does **not** promise a refund. Change the sentence in C10 if you want different wording.
- **Reminder timing:** one reminder each, **24 hours** after the booking is confirmed (scout hasn't confirmed handover) and **24 hours** after handover is offered (student hasn't accepted). Both are settings.
- **Not covered:** a disabled **student's** unpaid holds are not cancelled by this module (the hold simply expires). Named in the limitations; easy to add later with the same pipeline.

---

## PART C — DESIGN SPECIFICATION

### C1. Non-negotiable rules specific to this module

1. **No module's business rules move.** Every change to a booking is made by Booking, to a listing by Housing, to a notification by Notification, and so on. This module adds *plumbing* (outbox, jobs) and *reactions* (a module's own subscriber calling that module's own use case).
2. **An event is written in the same transaction as the change it describes.** Never before, never after. Events are **only** added on a *real* transition — not on an idempotent replay, a no-op, or a rejected attempt.
3. **At-least-once delivery means every subscriber is idempotent.** A subscriber that cannot safely run twice for the same event is a defect.
4. **Event payloads contain ids and enums only** — no name, message, amount, reason text, or free text. (Same rule as Notification's inbox.)
5. **System-initiated use cases take no actor** and are never reachable over HTTP. A guard test proves it (ADR-191). Use cases that humans call keep their existing authorization exactly as it is.
6. **No module imports another module's internals.** Cross-module calls go through the other module's `application.ports` using the established in-process adapter pattern. Only `adapters/events/` may import another module's `application/ports/events.py`.
7. **The worker composes; it does not decide.** `adapters/jobs/` wires jobs to use cases and contains no business logic.
8. **Debug switches work only when `app_env` is `local` or `test`** (an explicit structural check, same as every earlier debug flag).
9. **Concurrency safety is by conditional `UPDATE … WHERE`, checked by row count** — never check-then-write.
10. **The honest-readiness rule:** anything not built is named in the docs. No claim of a guarantee the tests do not prove.

### C2. Module layout (new package)

```
modules/platform_runtime/
├── domain/
│   ├── outbox.py          OutboxStatus, backoff function, OutboxRow value object
│   ├── jobs.py            JobDefinition, JobStatus enum (OK/FAILING/STALE/DISABLED/NEVER_RAN), health rules
│   └── errors.py
├── application/
│   ├── ports/
│   │   ├── inbound.py     DeliverOutboxEvent, RelayOutboxEvents, RequeueDeadOutboxEvents,
│   │   │                  GetOutboxStats, RunJob, GetJobStatuses
│   │   ├── outbound.py    OutboxRepository, JobRepository, EventContractRegistry, Clock (shared)
│   │   └── events.py      (none — this module publishes nothing of its own)
│   └── use_cases/
└── adapters/
    ├── persistence/       models, repositories (platform_outbox, platform_jobs, platform_rate_limits)
    ├── registry/          event_contract_registry.py
    ├── nudge/             post_commit_nudger.py
    └── jobs/              job_registry.py (wiring only), one small factory per job
```
Shared-kernel additions (framework-free): `EventContract`, the `add_event` capability on `UnitOfWork`, and an `OutboxNudge` port (Chunk 2). The exact shared-kernel file locations are decided by what Chunk 1 finds; the **behavior** in C3/C4 is fixed.

### C3. The shared outbox — model and database (ADR-175, ADR-177)

**Behavior of `UnitOfWork.add_event(event)`:** the event is held on the unit of work; at `commit()` it is inserted into `platform_outbox` **in the same database transaction** as everything else the unit of work wrote; on rollback or an exception it is discarded with the rest. Adding an event whose `event_id` already exists is **not an error** (`INSERT … ON CONFLICT (event_id) DO NOTHING`). After a *successful* commit, if any events were added, the unit of work calls the registered `OutboxNudge` with their ids, wrapped so that nothing it does can raise or change the commit result.

**`platform_outbox`** (no foreign keys)
| Column | Type | Notes |
|---|---|---|
| `event_id` | UUID | **PK** — the producer's event id; the idempotency key |
| `event_type` | text | not null |
| `payload` | jsonb | not null — ids and enums only |
| `occurred_at` | timestamptz | not null |
| `created_at` | timestamptz | not null |
| `status` | text | `CHECK IN ('PENDING','DELIVERED','DEAD')`, default `PENDING` |
| `attempts` | integer | not null, default 0 |
| `next_attempt_at` | timestamptz | not null; set to `created_at` on insert |
| `last_error` | text | nullable — **error class name or short code only** |
| `delivered_at` | timestamptz | nullable |
Partial index `(next_attempt_at) WHERE status = 'PENDING'`; index `(status, created_at)` for stats and retention.

**`EventContractRegistry`:** `register(EventContract)`, `to_payload(event) -> (event_type, dict)`, `from_payload(event_type, dict, event_id, occurred_at) -> event`. Unknown type → `UnknownEventType`; malformed payload → `InvalidEventPayload`. Each producer registers its contracts in its own `application/ports/events.py`-adjacent adapter file; composition registers them all once (the same place `build_event_bus` lives).

### C4. Delivery algorithm (ADR-176, ADR-180)

`DeliverOutboxEvent(event_id)`:
1. In a transaction: `SELECT … WHERE event_id = :id AND status = 'PENDING' AND next_attempt_at <= now FOR UPDATE SKIP LOCKED`. No row → return `SKIPPED` (someone else has it, or it is done).
2. Rebuild the event through the registry. Unknown type or invalid payload → mark `DEAD` with the code, log ERROR (type and id only), return.
3. `EventBus.publish(event)` — the shared bus built by `build_event_bus`. **A subscriber failure propagates** (the bus's existing behavior; Chunk 1 confirms it) and is caught **here**.
4. Success → `status = DELIVERED`, `delivered_at = now`. Failure → `attempts += 1`, `last_error = <error class>`, `next_attempt_at = now + backoff(attempts)`; `attempts >= platform_outbox_max_attempts` → `DEAD` and log ERROR.

`RelayOutboxEvents(limit)`: list due ids (`status='PENDING' AND next_attempt_at <= now`, ordered by `created_at`), then `DeliverOutboxEvent` each **in its own transaction**; a failure never stops the rest; returns counts (`delivered`, `retrying`, `dead`, `skipped`).

`RequeueDeadOutboxEvents()`: `DEAD → PENDING`, `attempts = 0`, `next_attempt_at = now`. `GetOutboxStats()`: `{pending, dead, oldest_pending_age_seconds}`.

**Ordering:** there is **no ordering guarantee** between different events. The two places that could care are made order-independent by design: Notification's resolution of action items is a conditional update that is correct in any order, and Booking's reactions are conditional updates.

**The nudge** (`adapters/nudge/post_commit_nudger.py`): for each id it calls `DeliverOutboxEvent` in a fresh session, catching everything (WARNING with ids only). `platform_outbox_nudge_enabled` (default `true`) and the local/test-only `platform_debug_disable_nudge` switch it off so delivery depends on the relay alone (used by the manual guide to prove durability).

### C5. The job runner and worker (ADR-181 … ADR-184)

**`platform_jobs`** — one row per job
| Column | Notes |
|---|---|
| `name` | **PK** — a value from the C6 registry |
| `leased_by` | nullable — worker id |
| `lease_expires_at` | nullable |
| `next_run_at` | not null |
| `last_started_at`, `last_finished_at` | nullable |
| `last_status` | `OK` / `FAILED` / null |
| `last_error` | nullable — error class only |
| `consecutive_failures` | integer, default 0 |
| `last_summary` | jsonb — small counts only (e.g. `{"delivered": 3}`) |

**`RunJob(name)`** — the one algorithm every job follows:
1. **Acquire the lease** with one conditional statement: `UPDATE platform_jobs SET leased_by = :me, lease_expires_at = now + lease WHERE name = :n AND next_run_at <= now AND (lease_expires_at IS NULL OR lease_expires_at < now)`. Zero rows → return `NOT_DUE_OR_LEASED`. (A crashed worker's lease simply expires.)
2. Run the job's callable under `asyncio.wait_for(platform_worker_job_timeout_seconds)`.
3. Record the result in a new transaction: success → `last_status = OK`, `consecutive_failures = 0`, `last_summary`; failure or timeout → `last_status = FAILED`, `consecutive_failures += 1`, `last_error = <class>`. Always clear the lease. `next_run_at = finished + interval` on success, `+ min(cap, interval · 2^failures)` on failure.
4. Nothing a job raises ever leaves `RunJob`; the worker must not die because a job did.

**Health (derived, never stored):** `DISABLED` (named in `platform_jobs_disabled`); `NEVER_RAN`; `FAILING` (`consecutive_failures >= platform_job_failing_after_failures`); `STALE` (`now − last_finished_at > interval × platform_job_stale_after_multiplier` and not failing); otherwise `OK`.

**`scripts/run_platform_worker.py`:** composes real dependencies through `build_event_bus`; on start, upserts one `platform_jobs` row per registered job; starts **one asyncio task per enabled job** (each loops: sleep until due → `RunJob`); handles `SIGINT`/`SIGTERM` by letting the current run finish, then exiting. Flags: `--once` (run every enabled job once, ignoring intervals, print counts, exit), `--only <name>` (with or without `--once`), `--list` (jobs, intervals, enabled), `--stats` (the C5 table, human-readable). A unique worker id (hostname + pid) is logged at start.

### C6. The job registry (ADR-182, ADR-184)

| Job name | Wraps (existing use case unless marked new) | Default interval | Notes |
|---|---|---|---|
| `platform_outbox_relay` | `RelayOutboxEvents` (new, Chunk 4) | 3 s | the guarantee behind the nudge |
| `messaging_outbox_relay` | Messaging's `DispatchOutboxEvents` batch | 5 s | same code as `run_messaging_outbox_relay.py` |
| `notification_inbox` | `ProcessPendingInbox` | 15 s | retry of failed event processing |
| `safety_enforcement` | `ProcessEnforcementQueue` | 30 s | applies approved enforcement, expires restrictions |
| `booking_hold_expiry` | `ExpireHolds` | 60 s | **frees inventory** — the worst gap when manual |
| `payment_recovery` | `ProcessLatePaymentSignal` + `ReprocessUncertainAttempts` | 60 s | no automatic release here |
| `payment_auto_release` | `ProcessAutomaticReleases` | 3600 s | **disabled by default** |
| `booking_reminders` | `PublishBookingReminders` (new, Chunk 12) | 300 s | |
| `suspended_listing_reconcile` | `ReconcileSuspendedListingBookings` (new, Chunk 12) | 300 s | backstop for missed events |
| `retention_sweep` | `RunRetentionSweep` (new, Chunk 19) | 86400 s | operational tables only |

**Stays manual (documented, not automated):** `run_safety_worker.py --requeue-failed`, Notification's requeue-dead, the new platform requeue-dead, and Payment's financial release/refund actions — each is a human decision with an audited route. `scripts/db_start.sh`, `db_stop.sh`, `messaging_ws_client.py` are developer tools.

Each chunk that creates a job's use case adds that job's registry entry. Chunk 8 registers only the jobs whose use cases already exist.

### C7. Event contracts (the public contract; ids and enums only)

Each is a frozen dataclass extending the shared-kernel `DomainEvent` (`event_id`, `occurred_at`).

| Event | Fields | Producer | Published when |
|---|---|---|---|
| `ListingSuspended` | `listing_id`, `owner_id`, `reason_code` (`SAFETY_ENFORCEMENT`/`OWNER_ACCOUNT_DISABLED`) | Housing | a listing **actually enters** `SUSPENDED` |
| `ListingSuspensionLifted` | `listing_id`, `owner_id`, `reason_code` | Housing | a listing **actually leaves** `SUSPENDED` |
| `BookingInvalidated` | `booking_id`, `student_id`, `property_id`, `listing_id`, `reason_code` (`LISTING_SUSPENDED`/`OWNER_ACCOUNT_DISABLED`), `was_confirmed` (bool) | Booking | the conditional update **matched a row** |
| `HandoverOffered` | `booking_id`, `student_id`, `property_id`, `listing_id` | Booking | first time only |
| `HandoverAccepted` | same four | Booking | first time only |
| `BookingReminderDue` | same four + `kind` (`HANDOVER_NOT_OFFERED`/`ACCEPTANCE_PENDING`) | Booking | the reminder claim matched |
| `PaymentOutcomeRecorded` | `payment_attempt_id`, `booking_id`, `student_id`, `outcome` (`FAILED`/`LATE_SUCCESS`/`NEEDS_REVIEW`) | Payment | a real transition, once per attempt per outcome |

Existing events keep their fields exactly: `BookingCreated`, `BookingConfirmed`, `BookingCancelled`, `BookingExpired`, `VerificationDecisionRecorded`, `SafetyUpdatePublished`, `AccountDisabled`, `AccountReactivated`, `MessageCreated` (the last via Messaging's own outbox).

### C8. Housing rulebook (Chunks 9 and 10)

- **Migration:** nullable column `suspension_reason` (`CHECK IN ('SAFETY_ENFORCEMENT','OWNER_ACCOUNT_DISABLED')`, null unless `SUSPENDED`). Every currently `SUSPENDED` row is backfilled `SAFETY_ENFORCEMENT` (all existing suspensions came from Trust & Safety). **Read the migration before applying; `downgrade` must work.**
- **Events through the outbox:** `SuspendListingForSafety` and `LiftListingSuspension` add `ListingSuspended` / `ListingSuspensionLifted` **only when the conditional update changed a row**. The idempotent no-op paths publish nothing.
- **Safety wins (ADR-187):** `SuspendListingForSafety` on a listing already `SUSPENDED` with reason `OWNER_ACCOUNT_DISABLED` **upgrades** it in place (conditional update: `suspension_reason = 'SAFETY_ENFORCEMENT'`, `suspension_reference = :ref`), returns success, and publishes **no second** `ListingSuspended` (the listing was already announced as suspended). On a listing already suspended for safety it stays a no-op. `LiftListingSuspension` follows the existing rules and lifts whichever reason is present when called by the safety route.
- **Owner-visible reason:** an owner's own view of a `SUSPENDED` listing carries `status_detail: {code, message}` — `SUSPENDED_SAFETY` ("This listing was suspended following a safety review. Contact support if you have questions.") or `SUSPENDED_ACCOUNT` ("This listing is hidden because your account is not active."). Fixed strings; no case detail ever.
- **System use cases (no actor, no HTTP; ADR-191):** `SuspendListingsForDisabledOwner(owner_id, source_event_id)` — for each of the owner's listings in `PUBLISHED` or `UNAVAILABLE` and **not** already suspended, set `SUSPENDED` / `OWNER_ACCOUNT_DISABLED` / `suspension_reference = owner_id`, publish `ListingSuspended`; process in pages of `housing_owner_suspension_batch_size`, **each listing in its own transaction**; replay-safe. `LiftOwnerAccountSuspensions(owner_id, source_event_id)` — lift **only** listings suspended with reason `OWNER_ACCOUNT_DISABLED` **and** reference = that owner → `UNAVAILABLE`, publish `ListingSuspensionLifted`. `ListSuspendedListingIds(limit, after_id)` — a paged system query for the reconciliation sweep.
- **Subscriber:** `adapters/events/identity_subscriber.py` (imports only Identity's `application/ports/events.py`) handles `AccountDisabled` → `SuspendListingsForDisabledOwner` and `AccountReactivated` → `LiftOwnerAccountSuspensions`. Registered in `build_event_bus`.
- **Listing-visibility audit (Chunk 9):** list **every** code path that reads a listing's status or serves listing data to non-owners — Search, Housing's public detail and list routes, a property's public listing list, Booking creation, Messaging's new-conversation rule, any public Media/File access to a listing's files — and prove each treats `SUSPENDED` as invisible to everyone but the owner (who sees it with `status_detail`) and staff. **A path that does not is fixed in Chunk 9 if it is inside Housing; if it is another module's, stop and report with the proposed touch.**

### C9. Booking rulebook (Chunks 11 and 12)

- **Migration:** nullable `closure_code` (`CHECK IN ('STUDENT_CANCELLED','PROVIDER_CANCELLED','STAFF_CANCELLED','HOLD_EXPIRED','LISTING_SUSPENDED','OWNER_ACCOUNT_DISABLED','CANCELLED_UNSPECIFIED')`), `handover_reminder_sent_at`, `acceptance_reminder_sent_at` (all nullable). **Backfill:** `EXPIRED → HOLD_EXPIRED`; `CANCELLED` with `cancelled_by = student_id → STUDENT_CANCELLED`; every other `CANCELLED → CANCELLED_UNSPECIFIED`. `status` values do **not** change.
- **`closure` on every booking response:** `{code, message}` for `CANCELLED`/`EXPIRED`, `null` otherwise. Fixed messages, in Booking's domain: `STUDENT_CANCELLED` "Cancelled by the student." · `PROVIDER_CANCELLED` "Cancelled by the host." · `STAFF_CANCELLED` "Cancelled by Camp Match staff." · `HOLD_EXPIRED` "The hold expired because payment wasn't completed in time." · `LISTING_SUSPENDED` "Cancelled because the listing was suspended." · `OWNER_ACCOUNT_DISABLED` "Cancelled because the host's account is no longer active." · `CANCELLED_UNSPECIFIED` "Cancelled."
- **Existing use cases** set `closure_code` on their transitions (`CancelBooking` by who cancelled — Chunk 1 confirms how the owner and staff cases are distinguished; `ExpireHolds` → `HOLD_EXPIRED`). Their behavior is otherwise unchanged.
- **`InvalidateBookingsForListing(listing_id, reason_code, source_event_id)`** (system, no actor): page through bookings with `status IN ('AWAITING_PAYMENT','CONFIRMED')` for that listing in batches of `booking_invalidation_batch_size`; for **each** booking, **in its own transaction**: conditional `UPDATE … WHERE status IN ('AWAITING_PAYMENT','CONFIRMED')` setting `status = 'CANCELLED'`, `cancelled_at`, `cancelled_by = NULL`, `closure_code`; **only if a row matched**: `HousingProvider.release_slot(unit_id)` and `uow.add_event(BookingInvalidated)`. **Zero rows matched → already closed → skip; never release the slot twice** (ADR-098's rule, applied here). A failure on one booking is logged WARNING and the batch continues; the whole call is safe to run again.
- **Race with payment:** if Payment confirms a booking at the same moment, exactly one conditional update wins. If invalidation wins, Payment's existing late-payment path flags the money for the existing manual review — **Payment is not changed here** (ADR-193).
- **Subscriber:** `adapters/events/housing_subscriber.py` handles `ListingSuspended` → `InvalidateBookingsForListing(listing_id, reason_code)`. **`ListingSuspensionLifted` does nothing to bookings** (they stay cancelled; a student rebooks).
- **`ReconcileSuspendedListingBookings(limit)`** (system): `HousingProvider.list_suspended_listing_ids` (new method on the existing port; the adapter calls Housing's `ListSuspendedListingIds`), then `InvalidateBookingsForListing` for each (reason from the listing: safety → `LISTING_SUSPENDED`, account → `OWNER_ACCOUNT_DISABLED`). Nothing live found → returns zeros quickly.
- **Handover events:** `ConfirmHandoverOffered`/`ConfirmHandoverAccepted` (built in Module 10) add `HandoverOffered`/`HandoverAccepted` **only on the first successful set**; a repeated call that changes nothing publishes nothing.
- **`PublishBookingReminders(limit)`** (system): (a) `status = 'CONFIRMED' AND handover_offered_at IS NULL AND handover_reminder_sent_at IS NULL AND confirmed_at <= now − booking_handover_reminder_after_seconds` → claim with a conditional update setting `handover_reminder_sent_at = now`, and **if the claim matched**, add `BookingReminderDue(HANDOVER_NOT_OFFERED)`; (b) `status = 'CONFIRMED' AND handover_offered_at IS NOT NULL AND handover_accepted_at IS NULL AND acceptance_reminder_sent_at IS NULL AND handover_offered_at <= now − booking_acceptance_reminder_after_seconds` → same with `ACCEPTANCE_PENDING`. One reminder each, ever, per booking; the claim and the event are one transaction.
- **Event publishing in existing use cases:** `CreateBooking`, `ConfirmBooking`, `CancelBooking`, `ExpireHolds` move from `publish_best_effort` to `uow.add_event` (Chunk 5) — same events, same conditions.

### C10. Notification rulebook (Chunks 13 and 14)

**The action model (ADR-194).** New enum `NotificationAction`: `COMPLETE_PAYMENT`, `OFFER_HANDOVER`, `ACCEPT_HANDOVER`. A `Notification` gains `action` (nullable) and `resolved_at` (nullable). Rules: an action requires a `target`; `resolved_at` may only be set when `action` is set; `resolve(now) -> bool` is true only the first time. `action_required = action is not None and resolved_at is None`. **Action notifications never collapse. Reading one does not resolve it** — only the underlying fact does. Database: columns `action` (`CHECK` against the enum), `resolved_at`; partial index `(recipient_id) WHERE action IS NOT NULL AND resolved_at IS NULL`; migration alters the `category` and `type` `CHECK`s (**read it**; `downgrade` restores them). Repository: `resolve_actions(target_type, target_id, actions, now) -> int` (conditional update, idempotent, order-independent).

**API additions:** `GET /notifications` accepts `action_required=true`; every notification object gains `action` (string or null), `action_required` (bool) and `resolved_at`; `GET /notifications/unread-count` gains `action_required_count`.

**New categories and types** (Notification still imports nothing from any other module; only `adapters/events/` imports producers' event ports):

| Type | Category | Action | Title | Body |
|---|---|---|---|---|
| `booking.created.student` | BOOKING | `COMPLETE_PAYMENT` | Complete your payment | Your booking is on hold. Complete payment before the hold expires to keep it. |
| `booking.confirmed.provider` *(reworded)* | BOOKING | `OFFER_HANDOVER` | Action needed: arrange handover | A booking on one of your listings is confirmed and paid. Arrange access with the student, then confirm the handover in the app. |
| `handover.offered.student` | BOOKING | `ACCEPT_HANDOVER` | Confirm you have access | Your host says access to your place is ready. Confirm in the app once you have it. |
| `handover.accepted.provider` | BOOKING | — | Handover confirmed | The student confirmed they received access. |
| `booking.handover_reminder.provider` | BOOKING | — | Reminder: confirm handover | A paid booking on one of your listings is still waiting for you to confirm handover. |
| `booking.acceptance_reminder.student` | BOOKING | — | Reminder: confirm access | Your host offered access to your place. Please confirm in the app once you have it. |
| `booking.invalidated.student` | BOOKING | — | Booking cancelled | Your booking was cancelled because the listing is no longer available. If you already paid, our team will review your payment. |
| `booking.invalidated.provider` *(collapsible; group `booking-invalidated:{listing_id}`)* | BOOKING | — | Bookings cancelled | Bookings on one of your suspended listings were cancelled. |
| `housing.listing_suspended` | **HOUSING** (new) | — | Listing suspended | One of your listings has been suspended and is no longer visible. Existing bookings on it are being cancelled. Contact support if you have questions. |
| `housing.listing_suspension_lifted` | HOUSING | — | Listing suspension lifted | A suspension on one of your listings was lifted. It is not live yet — review it and publish it again when you're ready. |
| `payment.failed.student` | **PAYMENT** (new) | — | Payment failed | Your payment didn't go through. If your booking hold hasn't expired, you can try again. |
| `payment.late.student` | PAYMENT | — | Payment received late | We received your payment after your booking hold expired. Our team will review it. |
| `payment.review.student` | PAYMENT | — | Payment under review | There was a problem confirming your payment. Our team will review it. |

Targets: booking-related → `BOOKING:booking_id`; housing → `LISTING:listing_id` (the `LISTING` target type exists from Module 13; Chunk 1 confirms); payment → `BOOKING:booking_id`. Templates stay fixed strings: no placeholders, no names, amounts, or URLs.

**Recipient policy and resolution (added to the existing table):**

| Event | Creates | Resolves (on `BOOKING:booking_id`) |
|---|---|---|
| `BookingCreated` | existing provider notice **plus** student → `booking.created.student` | — |
| `BookingConfirmed` | student → `booking.confirmed.student` (unchanged); provider → `booking.confirmed.provider` with `OFFER_HANDOVER` | `COMPLETE_PAYMENT` |
| `HandoverOffered` | student → `handover.offered.student` with `ACCEPT_HANDOVER` | `OFFER_HANDOVER` |
| `HandoverAccepted` | provider → `handover.accepted.provider` | `ACCEPT_HANDOVER` |
| `BookingCancelled`, `BookingExpired` | existing notices | **all three** actions |
| `BookingInvalidated` | student → `booking.invalidated.student`; provider → `booking.invalidated.provider` **unless** `reason_code = OWNER_ACCOUNT_DISABLED` (they cannot read it) | **all three** actions |
| `BookingReminderDue` | `HANDOVER_NOT_OFFERED` → provider reminder; `ACCEPTANCE_PENDING` → student reminder | — |
| `ListingSuspended` | owner → `housing.listing_suspended` **unless** `reason_code = OWNER_ACCOUNT_DISABLED` | — |
| `ListingSuspensionLifted` | owner → `housing.listing_suspension_lifted` **unless** `reason_code = OWNER_ACCOUNT_DISABLED` | — |
| `PaymentOutcomeRecorded` | student → `payment.failed.student` / `.late.student` / `.review.student` by `outcome` (nothing for success — `BookingConfirmed` covers it) | — |

The listing owner is `ListingSuspended.owner_id` (the event carries it so Notification needs no lookup). Provider of a booking is resolved by the existing `PropertyOwnerProvider`. **Trust & Safety stops publishing `LISTING_SUSPENDED` and the listing form of `RESTRICTION_LIFTED`** (ADR-186); Notification's parser **still accepts** both kinds (an in-flight event must not be `REJECTED`) and the old `safety.listing_suspended` type stays in the enum for old rows.

### C11. Payment and the mock controls (Chunks 15 and 16)

**Bounded Payment touch (ADR-197).** (1) `ProcessWebhookEvent` returns `WebhookProcessingOutcome` — `PROCESSED_CONFIRMED`, `PROCESSED_NO_CHANGE`, `IGNORED_DUPLICATE`, `REJECTED_INVALID_SIGNATURE`, `REJECTED_AMOUNT_MISMATCH`, `UNCORRELATED`, `LATE_SUCCESS_FLAGGED`, `PROVIDER_REPORTED_FAILURE` — plus a `reason_code`. **The real webhook route ignores it and acknowledges exactly as today.** (2) `PaymentOutcomeRecorded` is added through `uow.add_event` in the **same transaction** as the state change: `FAILED` on the attempt's transition to `FAILED`; `LATE_SUCCESS` when a late success signal or a Booking rejection of a paid confirmation is flagged; `NEEDS_REVIEW` on an amount mismatch (and on an uncertain-outcome exhaustion if Chunk 1 finds that state exists). **Once per attempt per outcome**, using a deterministic `event_id` (uuid5 of `attempt_id:outcome`) so a redelivered webhook collapses at the outbox primary key. Nothing else in Payment changes — not release, refund, ledger, or reconciliation logic.

**Mock controls — the new contract (ADR-198).** Mounted only when `app_env` is `local` or `test` (unchanged guard). Chunk 1 lists every existing mock-control route and request model; **each** is rewritten to this:
- **Strict typed requests:** `model_config = ConfigDict(extra="forbid")`; `scenario` is an **enum** of exactly the nine values (`success`, `failure`, `pending_then_success`, `pending_then_failure`, `timeout`, `duplicate_webhook`, `invalid_signature`, `amount_mismatch`, `uncertain_outcome`); every field has a description and an example so Swagger shows a **dropdown and a sensible example body**, never `additionalProp1`. An unknown value or unknown field → `422` whose message names every allowed value.
- **`GET /api/v1/payment-mock-controls/scenarios`** → each scenario with a plain-English `description`, which control to call it with, and its `expected_result` (attempt status and booking status afterwards).
- **`GET /api/v1/payment-mock-controls/{attempt_id}`** (inspect) → `{attempt_id, attempt_status, scenario, booking: {id, status, closure}|null, payment_created: bool, recent_webhooks: [{received_at, processing_status}] (last 10, **no raw payloads**), next_steps: [plain sentences]}`. Unknown attempt → `404` saying so.
- **Every action returns a `MockControlReport`:** `{ok, action, attempt: {id, status_before, status_after}, booking: {id, status_before, status_after}|null, payment_created, webhook_outcome, reason_code, message, next_steps}`. `ok` is **true only if the documented expected result for that scenario actually happened**; otherwise `ok` is false and `message` says, in plain English, **what happened instead and why** (e.g. "The webhook was received but ignored: this booking's hold had already expired, so the payment was flagged for late-payment review."). A control can **never** return a bare "success" when nothing changed.
- Acting on an attempt in a state where the action cannot apply → `409` with a plain message. Booking status is read through the existing `BookingProvider` port.
- **Repo-wide guard (ADR-199):** a test scans every router's request models; each must have `extra="forbid"`, except a short allow-list in the test file with a comment explaining each entry.

### C12. Admin amendment (Chunk 18)

- **Overview sections** (same sequential, per-section-session, timeout, `NOT_AUTHORIZED`/`UNAVAILABLE` rules as Module 14's C9): `background_jobs` → `{jobs: [{name, health, interval_seconds, last_finished_at, consecutive_failures}], unhealthy}` via a `PlatformRuntimeProvider` adapter over `GetJobStatuses`; `platform_events` → `{pending, dead, oldest_pending_age_seconds}` via `GetOutboxStats`. Both require `ADMIN_OVERVIEW_VIEW`. `admin_debug_fail_section` accepts both new names.
- **`GET /api/v1/admin/jobs`** → the full status rows (includes `last_summary`, `last_error` class). Same permission.
- **Recovery:** `POST /api/v1/admin/recovery/platform-events/requeue-dead` — the third recovery action, built exactly like the two from Module 14 (same permission as those two — Chunk 1 names it; same audited request/outcome recorder; refuses without a reason).
- **Two-person role grants (ADR-200).** When `admin_role_grant_requires_second_approver` is `false` (default) behavior is **exactly today's**. When `true`: the existing grant route records an `admin_role_grant_requests` row (`id`, `target_identity_id`, `role` (`OPERATIONS` only), `requested_by`, `reason`, `status` `PENDING`/`APPROVED`/`REJECTED`, `decided_by`, `decided_at`, `decision_reason`, `created_at`, `expires_at`) and returns `202` with it; a **different** admin approves or rejects it through `POST /admin/staff/role-requests/{id}/approve|reject` (with a reason); only approval performs the grant, through the **existing audited grant path** (so the audit trail is complete). Rules: approver ≠ requester; approver ≠ target; expiry is **computed** from `expires_at` (`admin_role_grant_request_ttl_seconds`), never by a job; a duplicate pending request for the same target and role returns the existing one; a request that is no longer `PENDING` → `409`. **Revocation is never gated** (revoking is the safe direction). `GET /admin/staff/role-requests` lists them.

### C13. Retention rulebook (Chunk 19; ADR-185)

`RunRetentionSweep` calls one purge use case per owning module, each deleting in batches of `retention_batch_size` (repeat up to a per-run cap), **never** touching `PENDING`/`DEAD` rows:
| Table | Purged when |
|---|---|
| `platform_outbox` | `DELIVERED` and older than `retention_platform_outbox_days` (7) |
| `messaging_outbox` | dispatched and older than `retention_messaging_outbox_days` (7) |
| `notification_inbox` | `PROCESSED`/`REJECTED` and older than `retention_notification_inbox_days` (14) |
| `notification_notifications` | read (and, for action items, resolved) and older than `retention_notification_read_days` (90) |
| `platform_rate_limits` | window older than `retention_rate_limit_hours` (24) |
**Never purged by this module:** any audit, history, safety, issue, booking, payment, ledger, verification or message-content table. A guard test lists the purge targets and fails if one is added without an explicit review.

### C14. Messaging cross-process rulebook (Chunks 20 and 21)

- **`PostgresRateLimiter`** implements the existing `RateLimiter.check(key, limit, window_seconds)`. Table `platform_rate_limits(key, window_start, count, PRIMARY KEY (key, window_start))`. One atomic statement: `INSERT … ON CONFLICT (key, window_start) DO UPDATE SET count = count + 1 RETURNING count`; `allowed = count <= limit`; `retry_after_seconds` = time to the end of the window, rounded up. **Fixed window** (a burst of up to 2× the limit across a window boundary is possible — documented, unlike the in-memory sliding window). Selected by `messaging_rate_limiter_backend` (`in_memory` default, `postgres`). **The per-connection WebSocket command limiter stays in memory** (a connection lives in one process).
- **`PostgresNotifyRealtimeGateway`** implements `RealtimeGateway.push`. It issues `pg_notify('camp_match_realtime', <json>)` where the JSON contains **ids only** (`kind`, `conversation_id`, `message_id`, `user_ids`), well under the 8000-byte limit. Every API process runs a **listener task** (started in the app `lifespan`) on a dedicated `LISTEN` connection; for each notification it, for each local connected user, loads the message through Messaging's `GetMessageForParticipant` and pushes through the existing in-memory connection registry. **All delivery goes through NOTIFY, including to the sender's own process** (no direct push — that would double-deliver). The listener reconnects with backoff; messages missed while disconnected are covered by history (ADR-117 — realtime is best-effort). `messaging_realtime_backend` becomes `Literal["in_memory", "postgres_notify"]`, default `in_memory`. **If any `RealtimeEvent` kind carries data that cannot be rebuilt from ids through a public Messaging use case, stop and report.** Both backends must pass the **existing** `RealtimeGateway` contract suite.

### C15. Settings (`config/settings.py`, `.env.example`)

| Setting | Default |
|---|---|
| `platform_outbox_batch_size` | 50 |
| `platform_outbox_max_attempts` | 8 |
| `platform_outbox_backoff_base_seconds` / `_cap_seconds` | 5 / 300 |
| `platform_outbox_nudge_enabled` | `true` |
| `platform_debug_disable_nudge` | `false` — honored **only** when `app_env` is `local`/`test` |
| `platform_worker_job_timeout_seconds` | 120 (lease = timeout + 30) |
| `platform_jobs_disabled` | `"payment_auto_release"` (comma-separated job names) |
| `platform_job_<name>_interval_seconds` (one per C6 job) | the C6 defaults |
| `platform_job_failure_backoff_cap_seconds` | 300 |
| `platform_job_failing_after_failures` | 3 |
| `platform_job_stale_after_multiplier` | 3 |
| `retention_platform_outbox_days` / `retention_messaging_outbox_days` | 7 / 7 |
| `retention_notification_inbox_days` / `retention_notification_read_days` | 14 / 90 |
| `retention_rate_limit_hours` / `retention_batch_size` | 24 / 500 |
| `booking_invalidation_batch_size` | 50 |
| `booking_handover_reminder_after_seconds` / `booking_acceptance_reminder_after_seconds` | 86400 / 86400 |
| `housing_owner_suspension_batch_size` | 100 |
| `admin_role_grant_requires_second_approver` / `admin_role_grant_request_ttl_seconds` | `false` / 259200 |
| `messaging_rate_limiter_backend` | `in_memory` (`Literal["in_memory","postgres"]`) |
| `messaging_realtime_backend` | `in_memory` (widened to `Literal["in_memory","postgres_notify"]`) |
Invalid values fail startup. Matching `.env.example` entries.

### C16. Touch map — the **only** files outside `modules/platform_runtime/` this module changes

| Module | What changes | Chunk |
|---|---|---|
| shared kernel | `EventContract`, `UnitOfWork.add_event`, `OutboxNudge` port | 2–3 |
| Booking | outbox publishing; `closure_code`; invalidation, reminders, reconcile; handover events; Housing subscriber; `HousingProvider.list_suspended_listing_ids` | 5, 11, 12 |
| Verification | outbox publishing only | 5 |
| Trust & Safety | outbox publishing; retire two listing kinds | 6, 14 |
| Identity | outbox publishing for `AccountDisabled`/`AccountReactivated` only | 6 |
| Housing | `suspension_reason`; events; owner `status_detail`; system use cases; Identity subscriber | 9, 10 |
| Notification | action model; new categories/types/templates/policies/parsers/subscribers; purge use case | 13, 14, 19 |
| Payment | `WebhookProcessingOutcome`; `PaymentOutcomeRecorded`; mock-control rewrite | 15, 16 |
| Messaging | outbox-stats/purge hooks; `PostgresRateLimiter`; `PostgresNotifyRealtimeGateway`; settings widening | 19–21 |
| Admin & Operations | two overview sections; `GET /admin/jobs`; third recovery action; two-person role grants | 18 |
| composition | `app.py`, `build_event_bus`, scripts, migrations, settings, import-linter contracts | throughout |
**Not touched:** Search (verified, not changed, unless Chunk 1's audit proves otherwise — then stop and report), Media/File, University, Profile, Security (no new permissions).

---

## PART D — CHUNKED IMPLEMENTATION

Every chunk ends with the same two obligations, stated once here: **(a)** run the full test suite of every module the chunk touched and report the real result, and **(b)** run `lint-imports` and report it. Chunks add tests in the module's existing test folders (`tests/unit/<module>/…`, `tests/integration/<module>/…` marked `integration`, `tests/api/<module>/…`) following that module's existing conventions.

---

### CHUNK 1 — REPOSITORY INSPECTION, ARCHITECTURE MAPPING & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** learn what is actually in the repository and prove or disprove every assumption this file makes. **Write no behavior.** Create only the empty `modules/platform_runtime/` skeleton (C2) with package files, and add `platform_runtime` to the import-linter contracts so its `domain`/`application` layers are framework-free and import no other module.

**Inspect and report each of these, with file paths and the exact signatures/behavior:**
1. **Shared kernel:** `UnitOfWork` (port and every implementation — one shared, or one per module?), `EventBus`/`InMemoryEventBus` (**exact behavior when a handler raises**; does it call every subscriber or stop at the first failure?), `publish_best_effort`, `DomainEvent`, `Clock`, `EntityId`, `Page`/`PageRequest`, `RateLimitedError`.
2. **Commit boundaries:** for `CreateBooking`, `ConfirmBooking`, `CancelBooking`, `ExpireHolds`, the Verification decision use cases, Trust & Safety's publishing use cases, Identity's `DisableAccount`/`ReactivateAccount`: **where exactly does the transaction commit, and where is the event published today?** If any commit happens outside the use case (e.g. at request level), say so — it changes Chunk 5.
3. **Composition:** where `build_event_bus` lives and every caller; every place that constructs a bus; every file in `scripts/` and what each one composes; how `app.py` uses `lifespan`; the database driver (is `asyncpg` the driver — Chunk 21 needs a dedicated `LISTEN` connection).
4. **Notification:** the exact `NotificationType`/`NotificationCategory`/`TargetType` members now (after Module 13's safety kinds — does `TargetType.LISTING` exist?), the `ProcessInboxEvent` transaction shape, and how collapsing is configured.
5. **Booking:** the exact `CancelBooking` authorization (how an owner-cancel and a staff-cancel are told apart); whether `CreateBooking` requires the listing to be `PUBLISHED`; the repository methods that find bookings by listing; the Module 10 handover use cases' exact names and whether they already report "changed or not."
6. **Housing:** `ListingStatus` values, `SuspendListingForSafety`/`LiftListingSuspension`, how a listing's owner is determined, and the **listing-visibility audit** (C8): every path that reads or serves listing data to non-owners. **Report whether Search reads live Housing data or keeps its own projection.** Report any public media route that ignores listing status.
7. **Payment:** `ProcessWebhookEvent`'s real return type; where the attempt moves to `FAILED`; where late success is flagged; whether `AuthorizeRelease`/`EvaluateReleaseEligibility` blocks a booking that is not `CONFIRMED` (**prove it with a test run**, ADR-193); every mock-control route, its path, and its current request/response model.
8. **Messaging:** `RealtimeGateway` and `RateLimiter` implementations and contract suites; the list of `RealtimeEvent` kinds and what each carries; `GetMessageForParticipant`; how the outbox dispatcher and `run_messaging_outbox_relay.py` are composed.
9. **Admin & Operations:** the permission used by the existing recovery routes and staff-management routes; the overview-section registration pattern; the audited-action recorder entry points.
10. **Project conventions:** how request models are declared (is `extra="forbid"` used anywhere?), router/schema conventions, how existing concurrency tests provision committed data, the frontend API doc location, and the `AI_state/` files.

**Output:** a **mapping table** (assumption in this file → what the repository actually has) and a list of **every difference**. A difference that changes a later chunk must be reported now.

**Acceptance criteria:** the skeleton imports; `lint-imports` is clean with the new contracts; the existing full suite is unchanged; the mapping table is complete. **Stop after this chunk even if everything matches.**

---

### CHUNK 2 — SETTINGS, ERRORS & SHARED-KERNEL ADDITIONS
**[FOR YOU — GEMINI CLI]**

**Objective:** the foundations that need no database yet.

Implement: every setting in **C15** (typed, defaulted, validated; `platform_debug_disable_nudge` and every debug switch honored only in `local`/`test`; the two backend settings as `Literal`s — the realtime one **widened**, existing tests for the old value still pass) with `.env.example`; the platform errors (`UnknownEventType`, `InvalidEventPayload`, each extending the shared-kernel category and carrying a `code`); in the shared kernel: the frozen `EventContract` value object, the `OutboxNudge` port, and the **`add_event` capability on the `UnitOfWork` port** (and a fake/in-memory unit of work that supports it, for tests). Pure domain code in `modules/platform_runtime/domain/` (C3/C4/C5): `OutboxStatus`, the backoff function `min(cap, base · 2^(attempts-1))` (attempts ≥ 1), the job-health derivation (C5), `JobDefinition`.

**Tests:** settings defaults and invalid values fail startup (including the widened realtime value `postgres_notify` now being accepted); backoff doubles, caps, rejects attempts < 1; every health state derived correctly from a `FixedClock` table (never ran, failing, stale, disabled, ok — including the exact boundary at `interval × multiplier`); the fake unit of work discards events on rollback and keeps them on commit.

**Acceptance criteria:** new tests pass; the existing suite is unchanged; `domain`/`application` of the new package import no framework and no other module.

---

### CHUNK 3 — THE OUTBOX: PERSISTENCE, REGISTRY & UNIT-OF-WORK INTEGRATION
**[FOR YOU — GEMINI CLI]**

**Objective:** make `uow.add_event` real.

Implement C3: the `platform_outbox` table and migration (**read it before applying; `downgrade` must work**); `OutboxRepository` (`add` with `ON CONFLICT DO NOTHING`, `claim`, `mark_delivered`, `record_failure`, `mark_dead`, `list_due`, `requeue_dead`, `stats`); the `EventContractRegistry` adapter; the SQL unit-of-work integration so events are inserted **in the same transaction** at commit and the post-commit nudge hook is called **after** a successful commit and only if events were added, with all nudge failures swallowed. If the project has more than one `UnitOfWork` implementation, extend each; **if a module's use cases do not go through a unit of work you can extend, stop and report.**

**Tests:** `tests/unit/platform_runtime/…` — registry round-trips every contract and rejects unknown type and malformed payload with the right error; add-twice with one id is a no-op. `tests/integration/platform_runtime/` (real DB) — **atomicity:** a business write plus an event commit together; an exception after `add_event` leaves **neither**; a commit that fails leaves no outbox row; events added on one unit of work never appear on another; the nudge hook is called after commit, not before, and a nudge that raises changes nothing.

**Acceptance criteria:** tests pass; the migration round-trips; `lint-imports` clean.

---

### CHUNK 4 — OUTBOX DELIVERY: NUDGE, RELAY, REQUEUE & STATS
**[FOR YOU — GEMINI CLI]**

**Objective:** deliver what the outbox holds.

Implement C4: `DeliverOutboxEvent`, `RelayOutboxEvents`, `RequeueDeadOutboxEvents`, `GetOutboxStats`; the post-commit nudger and its settings; register every existing and new event contract in the composition (one place); make `build_event_bus` the single place that also wires the nudger, and keep the existing guard test that fails if any code constructs `InMemoryEventBus` outside it. Add a small system script `scripts/run_platform_outbox_relay.py` (default: run `RelayOutboxEvents` once, print counts; `--stats`) as the manual escape hatch.

**Tests:** unit (fakes) — a due event is delivered and marked `DELIVERED`; a subscriber that raises → `attempts + 1`, backoff set, still `PENDING`; reaching max attempts → `DEAD`; unknown type → `DEAD` immediately with its code; a row not yet due is skipped; a `DELIVERED` row is never delivered again; relay: one failing event never stops the others and counts are exact. Integration (real DB) — **two concurrent deliveries of one event: exactly one runs it** (run three times); **crash simulation:** commit an event, never nudge, run the relay → delivered once; **idempotent subscriber:** deliver the same event twice through a subscriber test double → effect happens once; requeue moves only `DEAD`; stats exact.

**Acceptance criteria:** tests pass; the debug-disable-nudge switch is **ignored** when `app_env="staging"` (test it).

---

### CHUNK 5 — PRODUCER MIGRATION A: BOOKING & VERIFICATION
**[FOR YOU — GEMINI CLI]**

**Objective:** Booking and Verification stop publishing after commit and add their events inside the transaction (ADR-179). **Behavior must not change:** the same events, with the same fields, under the same conditions, and **none on replay, no-op or rejection.**

Implement C9's last bullet for Booking (`CreateBooking`, `ConfirmBooking`, `CancelBooking`, `ExpireHolds`) and the three Verification decision use cases; replace `publish_best_effort` calls with `uow.add_event` at the Chunk-1-identified points; register their contracts. `publish_best_effort` itself stays in the shared kernel (still used for non-critical publishes).

**Tests:** **every existing Booking and Verification test passes unmodified except for the fake-bus assertions, which change to assert on the fake unit of work's collected events** (list each changed assertion in the report). New: for each use case, the event is collected exactly on the real transition and **not** on replay, no-op, `Forbidden`, or a failed conditional update; a commit failure leaves no event; an integration test per module proves the business row and the outbox row commit together and an end-to-end delivery reaches Notification exactly as before (the existing Notification end-to-end tests still pass).

**Acceptance criteria:** Booking's and Verification's **entire** suites and Notification's pass; no behavior changed.

---

### CHUNK 6 — PRODUCER MIGRATION B: TRUST & SAFETY AND IDENTITY ACCOUNT EVENTS
**[FOR YOU — GEMINI CLI]**

**Objective:** same treatment for Trust & Safety's `SafetyUpdatePublished` and Identity's `AccountDisabled`/`AccountReactivated`.

Move Trust & Safety's publishes (every kind **including** the two listing kinds, which are retired later in Chunk 14 — do not retire them here) and Identity's two account events onto `uow.add_event`; register contracts. Identity's `UserRegistered` is **not** touched (ADR-179).

**Tests:** existing T&S and Identity suites pass (fake-bus assertions converted as in Chunk 5, listed in the report); each safety kind is collected exactly once on its real transition and **not** on a failed or retried-before-success enforcement attempt; account events collected on a real disable/reactivate only (disabling an already-disabled account publishes nothing, if that is Identity's current behavior — Chunk 1 told you); the T&S enforcement worker's per-action transaction still isolates failures.

**Acceptance criteria:** T&S's and Identity's entire suites pass; the T&S → Notification end-to-end tests still pass.

---

### CHUNK 7 — THE JOB RUNNER CORE
**[FOR YOU — GEMINI CLI]**

**Objective:** the lease-and-run machinery, with no real jobs yet.

Implement C5: the `platform_jobs` table and migration (**read it**); `JobRepository` (`ensure_job`, `try_acquire`, `record_success`, `record_failure`, `list_statuses`); `RunJob` (the exact four steps of C5, including the timeout and failure backoff); `GetJobStatuses` (health derived per C5).

**Tests:** unit (fakes, `FixedClock`) — not-due and still-leased return `NOT_DUE_OR_LEASED` and run nothing; success clears the lease, resets failures, sets `next_run_at = finished + interval`; failure and timeout increment failures and push `next_run_at` out by the capped backoff; **a job that raises never propagates**; health states from the table. Integration (real DB) — **two workers racing for one due job: exactly one acquires** (three runs); an expired lease is taken over; a live lease is not; a crashed run (lease never cleared) becomes runnable after expiry.

**Acceptance criteria:** tests pass; the migration round-trips.

---

### CHUNK 8 — THE WORKER PROCESS & JOB REGISTRY
**[FOR YOU — GEMINI CLI]**

**Objective:** one command that runs everything.

Implement C5's script and C6's registry for the jobs whose use cases already exist: `platform_outbox_relay`, `messaging_outbox_relay`, `notification_inbox`, `safety_enforcement`, `booking_hold_expiry`, `payment_recovery` (the late-signal and uncertain-attempt use cases only), `payment_auto_release` (registered, **disabled by default** via `platform_jobs_disabled`). Each job is a small factory in `adapters/jobs/` that builds its use case from the real composition and calls it; **no business logic**. Intervals come from the settings. The old scripts **stay unchanged and keep working**; add a test that each old script and its job call the **same use case class**.

**Tests:** the registry has exactly the named jobs; disabled jobs do not start and show `DISABLED`; `--once` runs every enabled job exactly once and prints counts; `--only` runs one; `--list` and `--stats` output is correct; a job that raises does not stop the others or the process (a test job); `SIGTERM` finishes the current run and exits (test with a controllable fake job); the worker composes the bus through `build_event_bus` (the existing guard still passes); `payment_auto_release` does not run unless explicitly enabled, **and when enabled runs `ProcessAutomaticReleases` and nothing else**.

**Acceptance criteria:** tests pass; with the real DB, `poetry run python scripts/run_platform_worker.py --once` completes and prints a count line per job.

---

### CHUNK 9 — HOUSING AMENDMENT A: EVENTS, SUSPENSION REASON, OWNER STATUS & VISIBILITY AUDIT
**[FOR YOU — GEMINI CLI]**

**Objective:** Housing announces suspensions and states the reason to its owner; every read path honors `SUSPENDED`. **Housing's existing behavior, return values, errors and tests must not change** except as C8 states. Read **Part C8** — it is the rulebook.

Implement: the `suspension_reason` column and migration with the safety backfill; `ListingSuspended`/`ListingSuspensionLifted` (added only on a real change); the **safety-wins upgrade rule**; the owner's `status_detail`; contracts registered. Then perform the **visibility audit** from Chunk 1's findings and add one regression test per read path.

**Tests:** suspend from `PUBLISHED`/`UNAVAILABLE` → event once with `reason_code = SAFETY_ENFORCEMENT`; suspending an already-safety-suspended listing → no event, no change; **suspending a listing already suspended for `OWNER_ACCOUNT_DISABLED` → upgraded in place, success, no second event** (the reason and reference now the safety ones); lift → event once, status `UNAVAILABLE`; lifting a non-suspended listing follows the existing rule and publishes nothing; the owner's response includes `status_detail`, a public caller's does not see the listing at all. **Visibility regression, one test each:** a `SUSPENDED` listing is absent from Search results and discovery; public listing detail returns not-found to a student; absent from a property's public listing list; `CreateBooking` is refused; a new conversation about it is refused; any public media route is refused (if one existed and was fixed, say so). The owner still reads it; `OPERATIONS`/`ADMIN` still read it where they could before.

**Acceptance criteria:** Housing's entire suite, Search's, Booking's, Messaging's unchanged apart from the additions; the migration round-trips.

---

### CHUNK 10 — HOUSING AMENDMENT B: DISABLED-OWNER PROPAGATION
**[FOR YOU — GEMINI CLI]**

**Objective:** a disabled scout's listings drop out; reactivation restores them to `UNAVAILABLE` only.

Implement the three system use cases and the Identity subscriber from **C8** (`SuspendListingsForDisabledOwner`, `LiftOwnerAccountSuspensions`, `ListSuspendedListingIds`; `adapters/events/identity_subscriber.py` importing only Identity's `application/ports/events.py`), registered in `build_event_bus`. They take **no actor** and are **not** reachable by any router (add the structural guard test: no router module imports them).

**Tests:** owner with three listings (`PUBLISHED`, `UNAVAILABLE`, `DRAFT`) disabled → the first two `SUSPENDED` with `OWNER_ACCOUNT_DISABLED` and reference = owner id, the draft untouched, one `ListingSuspended` each; a listing already suspended for safety is **left exactly as it is** and publishes nothing; replaying the same event changes nothing and publishes nothing; reactivation lifts **only** the account-reason ones to `UNAVAILABLE` (never `PUBLISHED`), leaves the safety one suspended, publishes `ListingSuspensionLifted` for each lifted; paging (more listings than the batch size) processes all; one listing failing does not stop the rest; the subscriber is idempotent when the same event is delivered twice; an owner with no listings is a clean no-op; `ListSuspendedListingIds` pages correctly.

**Acceptance criteria:** tests pass; Housing's and Identity's suites unchanged.

---

### CHUNK 11 — BOOKING AMENDMENT A: THE CLOSURE MODEL & INVALIDATION
**[FOR YOU — GEMINI CLI]**

**Objective:** every closed booking says why; Booking can invalidate a booking safely. Read **Part C9**.

Implement: the migration (columns, `CHECK`, the backfill — **read it; `downgrade` must work**); the `closure` value object with the fixed messages in Booking's domain and its place on every booking response (schema + DTO); `CancelBooking`/`ExpireHolds` setting `closure_code`; `InvalidateBookingsForListing` exactly as C9 (conditional update, slot release only on a matched row, `BookingInvalidated` through `add_event`, per-booking transactions, failure isolation, paging); the new `BookingInvalidated` contract. **Do not wire the subscriber yet.** Add the structural guard that no router reaches the system use case.

**Tests:** every closure code and message; backfill correctness against a seeded table; `AWAITING_PAYMENT` and `CONFIRMED` bookings both become `CANCELLED` with `cancelled_by` null, `closure_code` set, slot released, event collected with `was_confirmed` correct; an already `CANCELLED`/`EXPIRED` booking is skipped, **the slot is not released twice** (assert the fake `HousingProvider` call count), and no event; one booking's slot-release failure is logged and the batch continues; paging; **concurrency (integration, three runs):** invalidation racing `ConfirmBooking` on one booking — exactly one wins and the end state is consistent (never `CONFIRMED` with a released slot); invalidation racing a student `CancelBooking` — exactly one release; replay of the whole call changes nothing. Booking's existing cancel/expire tests pass.

**Acceptance criteria:** Booking's entire suite unchanged apart from the additions; the migration round-trips.

---

### CHUNK 12 — BOOKING AMENDMENT B: THE REACTION, RECONCILIATION, HANDOVER EVENTS & REMINDERS
**[FOR YOU — GEMINI CLI]**

**Objective:** Booking reacts to suspensions on its own and reminds people to act. Read **Part C9**.

Implement: `adapters/events/housing_subscriber.py` (imports only Housing's `application/ports/events.py`; `ListingSuspended` → `InvalidateBookingsForListing`; `ListingSuspensionLifted` → nothing), registered in `build_event_bus`; `HousingProvider.list_suspended_listing_ids` (port method + in-process adapter); `ReconcileSuspendedListingBookings`; the `HandoverOffered`/`HandoverAccepted` events added to the Module 10 handover use cases **on the first successful set only**; `PublishBookingReminders` with the claim-then-event rule; the contracts for all four new events; add the two job registry entries `booking_reminders` and `suspended_listing_reconcile` (C6).

**Tests:** subscriber: a `ListingSuspended` event invalidates every live booking on that listing and nothing on another listing; delivering the same event twice is harmless; `ListingSuspensionLifted` leaves bookings cancelled; reason code maps correctly. Reconcile: finds live bookings on a listing already `SUSPENDED` (including one suspended before this module existed) and invalidates them; finds nothing → zero counts. Handover: first `ConfirmHandoverOffered` publishes one event, a repeat publishes none (same for accepted); each by the correct actor only (existing rules unchanged). Reminders: a `CONFIRMED` booking past the threshold with no handover gets **one** `BookingReminderDue(HANDOVER_NOT_OFFERED)` and a second run adds none; same for `ACCEPTANCE_PENDING`; a booking that is cancelled, already offered, or already accepted gets none; **two concurrent reminder runs → exactly one event** (integration, three runs); the claim and the event commit together. End to end with the real bus and `--once`: suspend a listing (through Housing's use case) → run the platform relay → the bookings are `CANCELLED`/`LISTING_SUSPENDED`.

**Acceptance criteria:** Booking's, Housing's, Payment's suites unchanged apart from the additions.

---

### CHUNK 13 — NOTIFICATION AMENDMENT A: THE ACTION-REQUIRED MODEL
**[FOR YOU — GEMINI CLI]**

**Objective:** a notification can carry an open action. **Notification's existing behavior and tests must not change.** Read **Part C10, "The action model."**

Implement: `NotificationAction`; the `action` and `resolved_at` fields and their invariants on `Notification`; `resolve(now) -> bool`; the migration (columns, `CHECK`s, the partial index — **read it; `downgrade` must work**); `NotificationRepository.resolve_actions`; the API additions (`action_required` filter, the three new response fields, `action_required_count` on the unread-count response). No new event handling yet.

**Tests:** domain — an action without a target raises; `resolved_at` without an action raises; `resolve` is true once, then false with `resolved_at` unchanged; `action_required` is correct in all three states. Repository (real DB) — `resolve_actions` resolves only matching `(target, action)` rows, is idempotent, and is correct whichever order create and resolve happen in; an action notification does **not** collapse. API — `action_required=true` returns only open items and only the caller's own; the count matches; marking an action notification **read does not resolve it**; old rows (no action) serialize with `action: null`, `action_required: false`; another user's items are never returned.

**Acceptance criteria:** Notification's entire suite unchanged apart from the additions; the migration round-trips.

---

### CHUNK 14 — NOTIFICATION AMENDMENT B: NEW EVENTS, TEMPLATES, POLICIES & RESOLUTION
**[FOR YOU — GEMINI CLI]**

**Objective:** Notification renders every new event and resolves action items. Read **Part C10** end to end — it is the rulebook.

Implement: the `HOUSING` and `PAYMENT` categories; every new `NotificationType` with its **exact** C10 title and body (and the reworded `booking.confirmed.provider` with its action); strict parsers for `ListingSuspended`, `ListingSuspensionLifted`, `BookingInvalidated`, `HandoverOffered`, `HandoverAccepted`, `BookingReminderDue`, `PaymentOutcomeRecorded` (anything malformed or unknown → `REJECTED`, never guessed); the C10 recipient-policy and resolution tables; subscriber registration and `event_to_payload` conversions through the existing `register_notification_subscribers`; the migration for the `CHECK`s (**read it**). Then, in **Trust & Safety**, stop publishing `LISTING_SUSPENDED` and the listing form of `RESTRICTION_LIFTED` (ADR-186); Notification's parser still accepts both.

**Tests:** each new event → the exact title, body, type, category, target, action and recipient from C10, and **nobody else**; `OWNER_ACCOUNT_DISABLED` reasons produce no owner/provider notice; `BookingInvalidated` notices for several bookings on one listing **collapse for the scout** (one row, `event_count` correct) but not for students; the full resolution table — `BookingConfirmed` resolves the student's `COMPLETE_PAYMENT`, `HandoverOffered` resolves the scout's `OFFER_HANDOVER`, `HandoverAccepted` resolves the student's `ACCEPT_HANDOVER`, and cancel/expire/invalidate resolve all three — **including when the resolving event is processed before the creating one**; a duplicate event creates nothing and resolves nothing twice; templates contain no placeholder, name, amount or URL; the migration round-trips and old types still insert; T&S still emits its other kinds and **no longer** emits the two listing kinds, and exactly **one** notice reaches a scout for one suspension (the Housing one); **the full end-to-end with the real bus and relay:** Ada books → Ada has an open `COMPLETE_PAYMENT` item; booking confirmed → it resolves and Bola has an open `OFFER_HANDOVER`; handover offered → Bola's resolves and Ada has `ACCEPT_HANDOVER`; accepted → Ada's resolves and Bola is informed.

**Acceptance criteria:** Notification's, Trust & Safety's, Booking's, Housing's suites unchanged apart from the documented additions; `lint-imports` clean (Notification's `domain`/`application` still import nothing from other modules).

---

### CHUNK 15 — PAYMENT AMENDMENT: WEBHOOK OUTCOME & PAYMENT EVENTS
**[FOR YOU — GEMINI CLI]**

**Objective:** the bounded Payment touch of **C11**, and nothing more. **Payment's behavior, return values to the real webhook route, errors and tests must not change** except for the additions.

Implement: `WebhookProcessingOutcome` and `reason_code` as the return of `ProcessWebhookEvent` (the real webhook route still ignores it and acknowledges exactly as before); `PaymentOutcomeRecorded` through `uow.add_event` **in the same transaction** as the state change, with the deterministic `event_id`; the contract registered; Chunk 1's proof that automatic release is blocked for a booking that is not `CONFIRMED`, turned into a permanent test.

**Tests:** every webhook branch returns the right outcome (invalid signature, duplicate, uncorrelated, amount mismatch, late success, provider-reported failure, normal confirmation, repeated success); **the webhook route's HTTP response is byte-for-byte what it was before for every branch** (regression test); `FAILED`, `LATE_SUCCESS`, `NEEDS_REVIEW` events collected exactly once per attempt per outcome — a redelivered webhook adds none; no event on a normal success; the event and the state change commit together and a failure leaves neither; **release is refused for a `CANCELLED` booking** (the invalidation case) and the funds stay `HELD`; the event contains no amount or reason text.

**Acceptance criteria:** Payment's **entire** suite passes unchanged apart from the additions; no refund, release, ledger or reconciliation logic changed (list the files touched).

---

### CHUNK 16 — THE MOCK CONTROLS REWRITE
**[FOR YOU — GEMINI CLI]**

**Objective:** no mock control can fail silently or accept nonsense again. Read **Part C11, "Mock controls — the new contract."**

Using Chunk 1's list of every mock-control route, rewrite **each** to the contract: strict `extra="forbid"` models; the nine-value `scenario` enum; descriptions and examples on every field; `GET …/scenarios`; `GET …/{attempt_id}` inspect; every action returning a `MockControlReport` whose `ok` is true only when the documented expected result happened and whose `message` explains, in plain English, what happened instead when it did not; `409` for an action that cannot apply; `404` for an unknown attempt. Booking status is read through the existing `BookingProvider` port. The `app_env` guard is unchanged.

**Tests (API):** an unknown scenario → `422` whose message **names every allowed value**; an unknown field → `422`; a missing body where one is required → `422`; the OpenAPI schema for each control shows an enum and examples (assert no `additionalProperties: true` free-form body and no `additionalProp1`); **one test per scenario** asserting the report's `ok`, the attempt and booking before/after, and the exact plain-English `message`; the **silent-failure regression:** simulate a success webhook after the hold has expired → the report says `ok: false` and explains that the payment was flagged for late review, and the booking is unchanged; invalid signature → rejected and said so; amount mismatch → said so; duplicate → said so; an attempt in a terminal state → `409`; unknown attempt → `404`; inspect shows the right state, the last webhook outcomes, no raw payloads, and sensible `next_steps`; the controls remain unreachable (`404`) outside `local`/`test`; **end-to-end:** a failed payment produces the student's `payment.failed.student` notification once the relay runs.

**Acceptance criteria:** Payment's suite and the full API suite pass; nothing in the controls can return a bare "success" when nothing changed.

---

### CHUNK 17 — THE REQUEST-MODEL GUARD
**[FOR YOU — GEMINI CLI]**

**Objective:** make "silently accepted request" impossible project-wide (ADR-199).

Add `tests/architecture/test_request_models_forbid_extra.py`: discover every router, collect every request body model (and every model nested in one), and fail unless each has `extra="forbid"`, with a **short allow-list inside the test** where every entry carries a comment explaining why. Fix every violation the scan finds **only by adding `extra="forbid"`**; if adding it would break an existing test or a documented client behavior, **stop and report** instead of fixing.

**Tests:** the guard passes; a deliberately violating model in a test fixture makes it fail (proving it works); the allow-list is empty or each entry justified.

**Acceptance criteria:** the full suite passes; list every model changed.

---

### CHUNK 18 — ADMIN AMENDMENT: JOB HEALTH, PLATFORM EVENTS & TWO-PERSON ROLE GRANTS
**[FOR YOU — GEMINI CLI]**

**Objective:** staff can see job and event health, recover dead events, and (optionally) require a second approver for role grants. Read **Part C12**. **Admin's existing behavior and tests must not change** while `admin_role_grant_requires_second_approver` is `false`.

Implement: the `PlatformRuntimeProvider` port and in-process adapter; the `background_jobs` and `platform_events` overview sections; `GET /admin/jobs`; the third recovery action built **exactly** like the existing two (same permission, same audited recorder, reason required); the `admin_role_grant_requests` table and migration (**read it**), the request/approve/reject/list use cases and routes, wired into the existing grant path as C12 describes.

**Tests:** both sections `OK`/`NOT_AUTHORIZED`/`UNAVAILABLE` per Module 14's rules (and fail-injected via `admin_debug_fail_section`); numbers equal the platform use cases' own; `GET /admin/jobs` shape and permission; the recovery action: reason required, audited request-then-outcome rows, only `DEAD` rows requeued, refused for `OPERATIONS`. **Two-person rule, setting off:** the grant route behaves exactly as before. **Setting on:** a grant returns `202` and grants **nothing**; the same admin cannot approve their own request; the target cannot approve; a second admin approves → the role is granted through the audited path and the audit shows **both** people; rejection grants nothing; an expired request cannot be approved (`FixedClock`); a duplicate pending request returns the existing one; a non-pending request → `409`; **concurrent double-approval → exactly one grant** (three runs); revoking is never gated; granting `ADMIN` is still refused.

**Acceptance criteria:** Admin's **entire** suite unchanged apart from the additions.

---

### CHUNK 19 — RETENTION
**[FOR YOU — GEMINI CLI]**

**Objective:** operational tables stop growing. Read **Part C13**.

Implement the purge use case in each owning module (Platform's outbox, Messaging's outbox, Notification's inbox and read notifications, the rate-limit table's cleanup when that table exists — wire it in Chunk 20), `RunRetentionSweep` calling them in batches with a per-run cap, and the `retention_sweep` job registry entry. The purge methods delete **only** the rows C13 names.

**Tests:** each purge removes only rows older than its threshold **and** in the right status; `PENDING`/`DEAD`/unread/unresolved rows are **never** deleted at any age; batches and the per-run cap behave; **the guard test:** the list of purge targets is asserted exactly, so a new target cannot be added silently, and no audit, history, safety, issue, booking, payment, ledger, verification or message-content table appears in it; a second sweep is a clean no-op.

**Acceptance criteria:** Messaging's and Notification's suites unchanged apart from the additions.

---

### CHUNK 20 — MESSAGING CROSS-PROCESS A: THE DATABASE RATE LIMITER
**[FOR YOU — GEMINI CLI]**

**Objective:** limits that hold across processes. Read **Part C14, first bullet.**

Implement `PostgresRateLimiter` behind the existing `RateLimiter` port: the `platform_rate_limits` table and migration (**read it**), the one-statement atomic increment, `retry_after_seconds`; selection by `messaging_rate_limiter_backend`; wire the table's cleanup into Chunk 19's sweep. The per-connection WebSocket command limiter stays in memory.

**Tests:** build (or reuse) one **shared `RateLimiter` contract suite** run against **both** adapters: within-limit allowed, over-limit refused, window resets, key isolation, `retry_after` correct. Integration — **concurrency:** 50 simultaneous checks against a limit of 10 → exactly 10 allowed (three runs); **two separate processes' worth of connections** share the count; an invalid backend value fails startup; the default remains `in_memory`.

**Acceptance criteria:** Messaging's entire suite passes with the default backend **and** with `postgres`.

---

### CHUNK 21 — MESSAGING CROSS-PROCESS B: THE NOTIFY REALTIME GATEWAY
**[FOR YOU — GEMINI CLI]**

**Objective:** realtime that works with more than one API process. Read **Part C14, second bullet.** If any `RealtimeEvent` kind cannot be rebuilt from ids, **stop and report.**

Implement `PostgresNotifyRealtimeGateway` (ids-only `pg_notify`), the listener task started in the app `lifespan` (dedicated connection, reconnect with backoff, clean shutdown), the local delivery through the existing connection registry using `GetMessageForParticipant`, and the setting wiring. Add the Module 11 `RealtimeGateway` **contract suite** run against both gateways.

**Tests:** the contract suite passes for both; the NOTIFY payload contains only ids and is far below 8000 bytes (assert the size for a 1,000-recipient fake); a notification is delivered to a connected recipient and **not** to a non-participant; **the sender's own process receives it through NOTIFY exactly once** (no double delivery); a listener disconnect → reconnect → later messages delivered, and the missed one is recoverable from history; a listener failure never affects `SendMessage`'s result. Integration — **two app instances on one database:** a message sent through one reaches a socket connected to the other.

**Acceptance criteria:** Messaging's entire suite passes with `in_memory` (default) **and** `postgres_notify`.

---

### CHUNK 22 — END-TO-END & RELIABILITY SUITES
**[FOR YOU — GEMINI CLI]**

**Objective:** prove the whole module works together, over real HTTP and a real database, using the real bus and `run_platform_worker.py --once` (or its in-process equivalent) as the only background mechanism.

Write `tests/integration/platform_runtime/test_end_to_end.py` and `test_reliability.py` covering, **each as its own test**:
1. **The action flow:** book → pay (through the mock controls) → scout confirms handover → student accepts, asserting every notification and every resolution in order.
2. **Suspension propagation:** a scout with one listing, an `AWAITING_PAYMENT` booking and a `CONFIRMED` booking → suspend through the real Trust & Safety path → run the worker once → the listing is gone from search and detail; both bookings are `CANCELLED` with `closure.code = LISTING_SUSPENDED`; slots released; students notified individually; the scout has **one** suspension notice and **one collapsed** "bookings cancelled" notice; the paid booking's funds are still `HELD` and **cannot be auto-released**.
3. **Lift:** the lift event notifies the scout; bookings stay cancelled; the listing is `UNAVAILABLE`; republishing makes it bookable again.
4. **Account disable and reactivate:** a disabled scout's listings vanish and their bookings are invalidated; reactivation restores them to `UNAVAILABLE` only; **a safety-suspended listing stays suspended through both**.
5. **Safety wins:** account-disable then safety-suspend the same listing → reactivation does **not** lift it.
6. **Durability:** with the nudge disabled and no worker running, create a booking → the event waits in the outbox → one worker `--once` run delivers it; a subscriber that fails twice then succeeds is delivered exactly once in effect; a dead event is requeued through the Admin route and then delivered.
7. **Automation:** an unpaid hold past its expiry is expired by the worker, the slot freed, the student notified — no script run by hand.
8. **Reconciliation:** a listing suspended **directly in the database before** the worker runs (simulating pre-existing data) has its bookings invalidated by the sweep.
9. **Mock-control honesty:** a success webhook after expiry reports `ok: false` with the reason, and the student gets the late-payment notice.
10. **Concurrency:** invalidation racing payment confirmation; two workers running the same job; two reminder runs — each three times.
11. **Reminders:** one each, never twice.
12. **Job health:** stop updating a job → the overview shows `STALE`; make a job fail → `FAILING`; recover → `OK`.

**Acceptance criteria:** all pass three consecutive times; the **entire** project suite passes.

---

### CHUNK 23 — SECURITY, PRIVACY & REGRESSION SWEEP
**[FOR YOU — GEMINI CLI]**

**Objective:** adversarial verification.

Tests to write, each its own test: **no system use case is reachable over HTTP** (the structural guard, re-run over every router); no event payload, outbox row, job summary, log line or notification contains a name, message body, amount, reason text or email (scan a full flow's rows and captured logs); `last_error` fields hold only error class names or short codes; a student or scout cannot call any `/admin/*` route; `OPERATIONS` cannot call the new recovery route or the role-request routes; the mock controls return `404` when `app_env` is not `local`/`test`; every debug switch is ignored outside `local`/`test`; the worker never logs a secret or a token; a scout cannot read another scout's notifications or action items; `ADMIN` cannot approve their own role request; **the full existing suite passes.** Re-run `lint-imports` and confirm the architecture rules (framework-free domain/application, no cross-module internals, only `adapters/events/` imports other modules' event ports) hold for every changed module.

**Acceptance criteria:** all pass; any finding is fixed and re-tested, or reported as blocking.

---

### CHUNK 24 — DOCUMENTATION, MANUAL GUIDE & AI STATE
**[FOR YOU — GEMINI CLI]**

**Objective:** make the module understandable and operable.

Write: `docs/modules/platform_runtime.md` (purpose, the outbox and delivery model, the job registry table from C6, how to run the worker, the recovery table — *crash between commit and nudge → relay; subscriber fails → backoff then `DEAD` → audited requeue; worker dies mid-job → lease expires; worker not running at all → events and jobs simply wait, visible in the overview*); amendments to the Booking, Housing, Notification, Payment, Messaging, Admin & Operations, Trust & Safety, Verification and Identity module docs (new events, new fields, new routes, the corrected sentences from Part A); the **project-wide frontend API document** updated from **Part F**; update every `AI_state/` file the Standing Instructions require; update `.env.example` and the README's "how to run" so it says **start the API and the worker**.

**The manual testing guide** is `docs/manual_testing/module_15.md`, written from **Part G** and obeying these rules, because the reader is not a backend specialist: **(1)** a one-page "Start here" with the cast of test accounts and the copy-paste helper functions, each explained in one line; **(2)** every test uses the same five headings — *What this proves (in one plain sentence)* · *Do this* · *You should see* · *If you don't* · *Cleanup*; **(3)** every step is a **runnable command** with a short example of the real output you got; **(4)** no jargon without a one-line explanation the first time it appears; **(5)** commands that need a restart say so in bold; **(6)** a "Stuck?" section at the end listing the five most likely problems (worker not running, wrong token, forgot to unset a debug flag, a timing wait that was too short, database not started) and the fix for each; **(7)** it contains **only commands you actually ran** — anything in Part G marked *(Gemini verifies)* must be confirmed or corrected against the real repository.

**Acceptance criteria:** every doc exists and is accurate; no document claims a guarantee the tests do not prove; **the manual guide's commands were each run and the real outputs are in the report.**

---

### CHUNK 25 — FINAL AUDIT & COMPLETION REPORT
**[FOR YOU — GEMINI CLI]**

**Objective:** verify and report. Write no new features.

Run the **entire** suite three times and report the results; run `lint-imports`; apply every migration to a fresh database and then downgrade and re-upgrade the ones this module added; verify the C16 touch map (every changed file outside `modules/platform_runtime/` is listed and justified); fill the Completion Checklist; and classify readiness honestly in **three lists: ready for production use; ready for testing only; not built.** The last list must include at least: the production media adapter, the real payment adapter, automatic refunds, message attachments, email/push, a disabled student's unpaid holds, the fixed-window (not sliding) behavior of the database rate limiter, and the fact that the two outboxes (Messaging's and the shared one) remain separate.

**Acceptance criteria:** the report is complete and every claim in it is backed by a command output you ran.

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

### Your requests → where they are built and proven

| Your request | Built in | Proven in |
|---|---|---|
| 1. Fixes for the gaps (lost events, single-process limits, role grants, retention, job health) | Chunks 3–6, 18–21 | Chunks 3–6, 18–22 |
| 2. Automate the manual scripts (messaging relay, notification worker, safety worker, payment recovery, hold expiry) | Chunks 7–8, 12, 19 | Chunks 8, 22 (test 7, test 12) |
| 3. Scout notified when a listing is suspended "or the likes" (suspension lifted, bookings cancelled, handover confirmed) | Chunks 9, 14 | Chunks 14, 22 (tests 2–3) |
| 4. Scout notified when an action is required; student must accept again | Chunks 12–14 | Chunks 14, 22 (test 1) |
| 5. Suspension propagates everywhere; bookings invalidated with a clear reason | Chunks 9–12 | Chunks 9, 11, 12, 22 (tests 2–5, 8) |
| 6. Mock payment controls informative; failures notified | Chunks 15–17 | Chunks 15–17, 22 (test 9) |
| Your five decisions (CANCELLED reason, manual refunds, dedicated worker, role-grant rule, disabled-scout propagation) | ADR-189, 193, 181, 200, 188 | Chunks 11, 15, 8, 18, 10 |

### Gap list from my earlier summary → fix
| Gap | Fix | Chunk |
|---|---|---|
| Events lost between commit and publish | Shared transactional outbox | 3–6 |
| Realtime only in one process | Postgres NOTIFY gateway (opt-in) | 21 |
| Rate limits per process | Postgres limiter (opt-in) | 20 |
| Message attachments deferred | Stays deferred — depends on media storage | — |
| No two-person role approval | Built, default off | 18 |
| Operational tables grow forever | Retention sweep | 19 |
| No job or event health visibility | Overview sections and `GET /admin/jobs` | 18 |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

### Notifications (action-required)
- Every notification object now has **`action`** (`"COMPLETE_PAYMENT"`, `"OFFER_HANDOVER"`, `"ACCEPT_HANDOVER"`, or `null`), **`action_required`** (true while the action is still open), and **`resolved_at`**.
- `GET /api/v1/notifications?action_required=true` returns only open to-dos. `GET /api/v1/notifications/unread-count` now also returns **`action_required_count`**.
- An action notification **stays open even after it is marked read**. It closes by itself when the thing it asks for happens (payment made, handover confirmed, handover accepted) or when the booking is cancelled, expired or invalidated. Show it as a to-do, not just an unread message.
- Two new **categories**: `HOUSING`, `PAYMENT`. New **types** are listed in C10 — render the title and body the server sends; do not rewrite them.
- The scout's `booking.confirmed.provider` notification now means **"you need to arrange and confirm handover."** Link it to the booking.

### Bookings
- Every booking response now has **`closure`**: `null` while the booking is live; for `CANCELLED` and `EXPIRED` bookings an object `{ "code": "...", "message": "..." }`. **Show `closure.message` to the user.** Codes: `STUDENT_CANCELLED`, `PROVIDER_CANCELLED`, `STAFF_CANCELLED`, `HOLD_EXPIRED`, `LISTING_SUSPENDED`, `OWNER_ACCOUNT_DISABLED`, `CANCELLED_UNSPECIFIED`.
- A booking cancelled because a listing was suspended has `status: "CANCELLED"`, `cancelled_by: null`, and `closure.code: "LISTING_SUSPENDED"`. There is **no new status value.**

### Listings
- A scout's own view of a suspended listing includes **`status_detail`** `{code, message}` — show the message. Suspended listings are absent from search, public detail and a property's public list for everyone except the owner and staff.
- A scout whose **account is disabled** has their listings suspended automatically; when the account is reactivated the listings come back as **`UNAVAILABLE`** — the scout must publish them again.

### Mock payment controls (local/test only)
- `GET /api/v1/payment-mock-controls/scenarios` lists every scenario with a description and the expected result — build the dropdown from it.
- Every control takes a **typed** body (a `scenario` enum, no free JSON) and returns a **report**: `ok`, `message` (plain English), the attempt and booking **before/after**, and `next_steps`. **Show `message`.** A `422` lists the allowed values.
- `GET /api/v1/payment-mock-controls/{attempt_id}` shows the current state of an attempt.
- Students now get notifications for a **failed**, **late** or **under-review** payment.

### Admin
- `GET /api/v1/admin/overview` gains `background_jobs` and `platform_events` sections. `GET /api/v1/admin/jobs` lists each job's health.
- `POST /api/v1/admin/recovery/platform-events/requeue-dead` (admin).
- When two-person approval is on: granting a role returns **`202`** with a pending request; `GET /api/v1/admin/staff/role-requests` lists them; a different admin calls `…/role-requests/{id}/approve` or `/reject`.

### Realtime and limits
- No client change. If the server runs with `MESSAGING_REALTIME_BACKEND=postgres_notify`, WebSocket behavior is identical.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — and Gemini's source for `docs/manual_testing/module_15.md` in Chunk 24]

**Read this first.** You are going to *use* the app the way a person would and check that it does the right thing. You don't need to understand the code. Each test tells you what to do and what you should see. If you see something different, the "If you don't" line tells you whether it is a real bug.

**Two programs must be running now, not one:**
1. **The API** (as always).
2. **The worker** — `poetry run python scripts/run_platform_worker.py` in a **second** Termux session. *This is new, and it replaces every script you used to run by hand.* Leave it running. It prints a line each time a job runs.

**The cast** (create them if you haven't): **Ada** (a student), **Bola** (a scout who owns a published listing with at least 2 units), **Ade** (`ADMIN`), **Rita** (`OPERATIONS`). *(Gemini verifies the real emails and how roles are assigned, and writes them down.)*

**Two helpers** — paste once per Termux session. `login` gives you a token; `api` calls the server and prints the answer tidily. *(Gemini verifies the login path and field names.)*
```
BASE=http://localhost:8000/api/v1
login() { curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d "{\"email\":\"$1\",\"password\":\"$2\"}" | jq -r '.access_token'; }
api() { curl -s -X "$1" "$BASE$2" -H "Authorization: Bearer $3" -H 'Content-Type: application/json' ${4:+-d "$4"} | jq .; }
```
Then, for each person: `ADA=$(login ada@example.com password)` and likewise `BOLA`, `ADE`, `RITA`. Anything marked **(Gemini verifies)** is a path, field or command Gemini must confirm before it goes in the real guide.

**Test layout:** *What this proves* · *Do this* · *You should see* · *If you don't* · *Cleanup*.

---

**M1 — The worker is alive and watching itself.**
*What this proves:* the new background process runs and the app can tell when it stops.
*Do this:* as Ade, `api GET /admin/overview $ADE`. Look at `background_jobs`. Now **stop the worker** (Ctrl+C in its session), wait about 15 seconds, and look again.
*You should see:* with the worker running, every job `OK` (a job that has not run yet shows `NEVER_RAN` for a moment after a fresh start; give it a few seconds) and `payment_auto_release` as `DISABLED`. After you stop it and wait longer than three times a job's interval, the fast jobs flip to `STALE`.
*If you don't:* every job `NEVER_RAN` or `STALE` while the worker is running means the worker is not recording its runs — a real bug.
*Cleanup:* start the worker again.

**M2 — Messages and notifications arrive with no script.**
*What this proves:* the message relay and the notification worker now run on their own.
*Do this:* as Ada, send Bola a message about Bola's listing *(Gemini verifies the route)*. Wait 10 seconds. As Bola, list notifications.
*You should see:* a "New message" notification for Bola. You ran **no script**.
*If you don't:* check the worker is running (M1). If it is, this is a real bug.

**M3 — An unpaid hold expires by itself and frees the room.**
*What this proves:* hold expiry is automatic.
*Do this:* set the local hold duration to something short such as 60 seconds **and restart the API** *(Gemini verifies the setting name)*. As Ada, create a booking on Bola's listing and note the booking id and the listing's available units. Wait about two minutes. As Ada, `GET` the booking and the listing again.
*You should see:* the booking is `EXPIRED`, with a `closure` saying the hold expired because payment wasn't completed in time; the listing's available units are back to what they were; Ada has a "Booking expired" notification.
*If you don't:* units still reduced after two minutes means hold expiry did not run — a real bug.
*Cleanup:* put the hold duration back and restart the API.

**M4 — "You need to do something" notifications (the main flow).**
*What this proves:* each person is told when it is their turn, and the to-do disappears when they act.
*Do this, in order:*
1. Ada creates a booking on Bola's listing. As Ada: `api GET "/notifications?action_required=true" $ADA`.
2. Complete the payment using the mock controls *(see M6 for the controls; use the scenario `success`)*. Wait 10 seconds. Look at Ada's and Bola's action lists.
3. As Bola, confirm the handover *(Gemini verifies the route from Module 10)*. Wait 10 seconds. Look at Bola's and Ada's lists.
4. As Ada, accept the handover. Wait 10 seconds. Look at both lists again.
*You should see:* step 1 → Ada has one open item, "Complete your payment." Step 2 → Ada's item is **gone**; Bola has one open item, "Action needed: arrange handover." Step 3 → Bola's item is gone; Ada has "Confirm you have access." Step 4 → Ada's item is gone; Bola gets a plain "Handover confirmed" notice. `action_required_count` on unread-count matches the lists at every step.
*If you don't:* an item that never disappears, or one that appears for the wrong person, is a real bug.

**M5 — Reminders.**
*What this proves:* a person who forgets to act gets exactly one nudge.
*Do this:* set `BOOKING_HANDOVER_REMINDER_AFTER_SECONDS=60` and `BOOKING_ACCEPTANCE_REMINDER_AFTER_SECONDS=60` **and restart the API and the worker**. Repeat M4 up to step 2, then wait about six minutes without confirming handover. As Bola, list notifications.
*You should see:* one "Reminder: confirm handover" notification. Wait six more minutes: still **one**, not two.
*If you don't:* two reminders is a real bug. No reminder at all after seven minutes: check the worker, then it is a real bug.
*Cleanup:* remove both settings and restart.

**M6 — The payment controls now explain themselves.**
*What this proves:* you can no longer send nonsense and be told "ok."
*Do this:* start a payment so you have an `attempt_id`. Then: (a) `api GET /payment-mock-controls/scenarios $ADA`; (b) send a scenario with a made-up name; (c) send the webhook simulator the default body; (d) use `success` and read the report; (e) `api GET /payment-mock-controls/$ATTEMPT $ADA`. *(Gemini verifies the exact control paths and bodies.)*
*You should see:* (a) nine scenarios, each described in plain English. (b) a `422` that **lists every allowed scenario**. (c) a typed example body in Swagger (a dropdown, not "additionalProp1"), and a report. (d) `ok: true`, the attempt and booking before and after, and a sentence saying what happened. (e) the attempt's current state and what to try next.
*If you don't:* a made-up scenario that is accepted, or a report that says `ok` when the booking didn't change, is a real bug.

**M7 — The control tells you when it didn't work.**
*What this proves:* the exact silent failure you reported is fixed.
*Do this:* create a booking, let its hold expire (M3's short setting), then use the success webhook on its payment attempt.
*You should see:* `ok: false` and a plain message such as "received but ignored — the hold had already expired; the payment was flagged for late-payment review." The booking stays `EXPIRED`. Ada gets a "Payment received late" notification.
*If you don't:* a bare success with an unchanged booking is a real bug.

**M8 — Payment failures notify the student.**
*Do this:* start a payment and run the `failure` scenario. Wait 10 seconds. As Ada, list notifications.
*You should see:* "Payment failed — if your booking hold hasn't expired, you can try again."

**M9 — Suspending a listing cleans up everything.**
*What this proves:* one suspension removes the listing everywhere and closes its bookings with a clear reason.
*Setup:* Ada has **two** bookings on Bola's listing — one unpaid (`AWAITING_PAYMENT`) and one paid (`CONFIRMED`). Suspend the listing using Module 13's flow: Ada or Bola files a report, Rita reviews and proposes a listing suspension, **Ade** approves it *(Gemini writes every command out in full from Module 13's guide)*. Wait about 20 seconds.
*You should see:* as Ada, searching does **not** return the listing and opening it gives "not found"; **both** bookings are `CANCELLED` and each shows `closure.message`: "Cancelled because the listing was suspended"; the room's units are free again; Ada has **one notification per booking**; as Bola, the listing shows `SUSPENDED` with a `status_detail` message, and Bola has **one** "Listing suspended" notice and **one** "Bookings cancelled" notice (not one per booking). The paid booking's funds are still held: as Ade, asking to release them is refused.
*If you don't:* a booking that is still live after a minute, a listing that still shows in search, or two suspension notices for Bola is a real bug.

**M10 — Lifting a suspension.**
*Do this:* as Ade, lift the suspension through Module 13's flow. Wait 20 seconds.
*You should see:* Bola gets "Listing suspension lifted — publish it again when you're ready." The listing is `UNAVAILABLE` (**not** live). The two bookings **stay cancelled**. Bola republishes; Ada can book it again.

**M11 — Disabling a scout hides their listings.**
*Do this:* as Ade, disable Bola through the audited account route `POST /admin/accounts/<id>/disable` with a reason *(Gemini verifies)*. Wait 20 seconds. Then reactivate Bola and wait again.
*You should see:* while disabled, Bola's listings are gone from search and their live bookings are `CANCELLED` with the closure "the host's account is no longer active"; Bola gets no notification (they cannot log in). After reactivation the listings come back as `UNAVAILABLE`, **not** live, and the bookings stay cancelled. **If one of Bola's listings was safety-suspended before, it is still suspended.**

**M12 — Nothing is lost if the worker is off.**
*What this proves:* an event is never dropped; it just waits.
*Do this:* set `PLATFORM_DEBUG_DISABLE_NUDGE=true` **and restart the API** (this removes the fast path so only the worker delivers). **Stop the worker.** As Ada, create a booking. As Ade, `GET /admin/overview` and note `platform_events.pending`. Check that Bola has **no** new notification yet. Now **start the worker**. Wait 10 seconds.
*You should see:* `pending` is 1 or more while the worker is off; after the worker starts it drops to 0 and Bola gets the "New booking" notification.
*If you don't:* a notification that never arrives, or `pending` that never falls, is a real bug.
*Cleanup:* unset the flag and restart.

**M13 — A stuck event can be retried by an admin.**
*Do this:* make events fail on purpose using the local debug setting *(Gemini verifies a quick way to make one platform event reach `DEAD`)*, confirm `platform_events.dead` is 1 in the overview, remove the failure, then as Ade `POST /admin/recovery/platform-events/requeue-dead` with a reason. As Rita, try the same call.
*You should see:* Ade succeeds and the event is delivered shortly after; Rita is refused (`403`); the audit list shows who did it and why.

**M14 — Two admins for a role grant (optional rule).**
*Do this:* set `ADMIN_ROLE_GRANT_REQUIRES_SECOND_APPROVER=true` **and restart the API.** Have a second admin account (Ade2). As Ade, grant `OPERATIONS` to a student, Chidi. Then try to approve it as Ade. Then approve as Ade2.
*You should see:* Ade's grant returns `202` "pending" and Chidi still has **no** access; Ade cannot approve their own request; after Ade2 approves, Chidi gets the role immediately; the audit shows both admins. Turn the setting off again and a grant works in one step as before.

**M15 — Old rows are cleaned up.**
*Do this:* set the retention days to `0` or `1` *(Gemini verifies the safe values)*, run `poetry run python scripts/run_platform_worker.py --once --only retention_sweep`, and look at the counts.
*You should see:* old delivered or processed rows are removed; **unread notifications, dead events and every booking, payment and audit record are untouched.**

**M16 — Two API processes, one chat (optional).**
*Do this:* set `MESSAGING_REALTIME_BACKEND=postgres_notify` and `MESSAGING_RATE_LIMITER_BACKEND=postgres`. Start the API on **two ports** (8000 and 8001). Connect Bola's WebSocket to 8001 using the project's `messaging_ws_client.py`; send Ada's message through 8000.
*You should see:* Bola's socket on 8001 receives it instantly. Sending more messages than the limit, split between the two ports, is refused with `429` as a **combined** total.
*If you don't:* Bola's socket not receiving it is a real bug.

**Stuck?** (1) Nothing happens at all → the **worker** isn't running; start it. (2) `401` or `403` → your token expired or belongs to someone else; run `login` again. (3) Something odd after a test → you left a **debug flag** set; unset it and restart. (4) A "wait N seconds" test failed → wait a little longer, the worker runs on timers. (5) Connection errors → the database isn't up; run `scripts/db_start.sh`.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] **Chunk 1** mapping table complete; every difference from this file reported before Chunk 2 began.
- [ ] `platform_outbox` exists; `uow.add_event` writes in the same transaction as the business change and is discarded on rollback; the nudge cannot affect a commit.
- [ ] Booking, Verification, Trust & Safety and Identity's account events are published through the outbox; **no behavior or event field changed**; every changed fake-bus assertion was listed.
- [ ] Delivery is at-least-once with backoff and `DEAD`; every subscriber proven idempotent; two concurrent deliveries run once.
- [ ] `scripts/run_platform_worker.py` runs every C6 job on its interval; the DB lease prevents double-running; `payment_auto_release` is disabled by default and runs only `ProcessAutomaticReleases` when enabled; the old scripts still work and call the same use cases.
- [ ] Housing announces `ListingSuspended`/`ListingSuspensionLifted` only on real changes; `suspension_reason` exists; **safety wins** over account-disable; the owner sees `status_detail`; **every listing read path was audited** and each has a regression test.
- [ ] A disabled scout's listings are suspended and restored to `UNAVAILABLE` only on reactivation; safety suspensions are never lifted by reactivation.
- [ ] Booking: every closed booking has `closure`; invalidation uses conditional updates, releases a slot only on a matched row, and never twice; the Housing subscriber, the reconciliation sweep, and the handover events and reminders all work; **refunds remain manual and auto-release is blocked for a non-`CONFIRMED` booking.**
- [ ] Notification: the action model works and **reading never resolves an action**; every C10 template matches **exactly**; the scout gets exactly **one** notice per suspension; the resolution table is order-independent; Trust & Safety no longer publishes its two listing kinds.
- [ ] Payment changed only as C11 states; the real webhook route's responses are byte-identical; `PaymentOutcomeRecorded` is once-per-attempt-per-outcome.
- [ ] Every mock control is strict, typed, enum-driven and diagnostic; a control cannot report success when nothing changed; the repo-wide `extra="forbid"` guard passes.
- [ ] Admin: `background_jobs` and `platform_events` sections, `GET /admin/jobs`, the third audited recovery action, and the two-person rule (default off, fully tested when on).
- [ ] Retention purges only the named operational rows; the guard test fixes the purge list.
- [ ] `PostgresRateLimiter` and `PostgresNotifyRealtimeGateway` pass the shared contract suites; Messaging's suite passes with **both** backends.
- [ ] End-to-end and reliability suites pass **three consecutive times**; the whole project suite passes.
- [ ] **Security sweep:** no system use case reachable over HTTP; no names, amounts, message bodies or reason text in events, rows, summaries or logs; debug flags ignored outside `local`/`test`.
- [ ] Docs written; frontend API doc updated from Part F; AI state updated; **the manual guide (`docs/manual_testing/module_15.md`) follows the plain-language rules and every command in it was run.**
- [ ] The final report classifies readiness in three honest lists (production-ready / testing-only / not built).
