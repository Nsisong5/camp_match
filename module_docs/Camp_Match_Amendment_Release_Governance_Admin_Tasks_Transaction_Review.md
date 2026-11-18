# CAMP MATCH — AMENDMENT: RELEASE GOVERNANCE, ADMIN TASKS & TRANSACTION REVIEW
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Nsisong → Claude: (1) funds may be released only after a student has confirmed an offer — enforced; (2) before an automatic release the admin must be notified at least three times, some hours ahead; (3) the admin must be told when a release is due after a student confirmed, because today nothing tells them; plus an admin "tasks" endpoint, and a separate "transaction review" table that gives the frontend everything an admin needs to understand one transaction. "I am only going to let you know what I think; you decide what is best and how to do it."**

**This is an amendment, not a new module.** It changes **Booking (09), Payment & Escrow (10), Notification (12), Admin & Operations (14)**, the job registry of **Platform Reliability (15)**, and adds **one small system use case to Security**. Every change is named in the touch map (C12); nothing else is touched.

**Prerequisite: Modules 09, 10, 12, 14 and 15 are complete** (Module 15 supplies the outbox, the events and the job worker this amendment relies on). If **Module 18** (self-describing requests) has been built, every new route here must pass its probe suite; if it has not, build the new routes by its recipe anyway (typed enums, a description and a proven example on every field).

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** Gemini reads all of it, then works through the chunks **in order, one at a time**. After each chunk Gemini stops with a Completion Report; you check it and reply **"Proceed to Chunk N"**. Parts marked **[FOR NSISONG]** are yours (findings, decisions, frontend documentation, manual testing guide).

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

1. **Read the entire file before doing anything.** Part C is the reference every chunk points back to ("C3", "ADR-248").
2. **Your first action is Chunk 1** (inspection, no behavior change).
3. **One chunk at a time, in order**, only after Nsisong replies "Proceed to Chunk N". Never combine, reorder, skip or work ahead.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; files created and changed; every command run with its **real** output; each acceptance criterion marked pass or fail; any deviation or open question. Claim nothing you did not verify.
5. **If anything blocks you — the repository contradicting this file, two parts disagreeing, an acceptance item failing, or a decision this file does not make — stop and report.** Do not choose for yourself and do not weaken a test.
6. **This amendment moves money.** Wherever you are unsure whether a payment is allowed to be released, the answer is **no** (C1.6). Never "default to eligible".
7. The Standing Instructions in `AI_instructions/` apply throughout. After any chunk that touches an existing module, re-run that module's **full** suite; it must pass unchanged apart from the documented additions and the entries in the **behavior-change list** (C13).

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

**What you asked for, in one sentence each, and what I decided:**

1. **"Funds can only be released after a student confirms an offer — enforced."** "Confirmed an offer" means, in this codebase, the **scout offered the handover and the student accepted it** (Booking's `handover_offered_at` and `handover_accepted_at`). I enforce it in **four independent places**, for **every** way money can be released — admin release, automatic release, and a dispute resolved in the scout's favour — with **no override for any role**, including `ADMIN`. One of the four is a **database rule** that makes it impossible to even *record* a release decision without the student's confirmation. While reading Module 10 I also found a hole that makes "confirmed" untrustworthy today — Finding 2 — and this amendment closes it.
2. **"Notify the admin at least three times before an automatic release."** After the student confirms, a **notice period** starts (default 48 hours). The system sends **three warnings** (defaults: 24, 12 and 3 hours before the automatic release) and **an automatic release cannot happen unless all three were recorded as sent** — enforced in code and by a database rule. If the warning job is late, the release is **pushed back**, never shortened. If there is no active admin to receive a warning, the release is **blocked**.
3. **"The admin should be told a release is due."** The moment the student confirms, every admin who can release funds gets an **action notification** ("release funds") that stays open until the money is released, refunded, disputed, or the booking closes. That is the same action mechanism Module 15 built for students and scouts.
4. **The admin "tasks" endpoint:** `GET /api/v1/admin/tasks` — a live, per-source to-do list for the signed-in staff member (payments first; open operational issues and pending verification reviews too). It is **computed per request**, exactly like Module 14's overview, so it can never go stale and Admin never copies another module's data.
5. **The "transaction review" table:** a new table owned by Payment, **one row per confirmed payment**, giving the frontend the full picture of a transaction — who, how much, where it is in its life, what the student and scout have done, how long until an automatic release and how many warnings went out, disputes, release/refund operations, and what the admin can do next. It is **not** the ledger. A detail endpoint adds the live children (operations, disputes, ledger entries, warnings, timeline) so the screen needs one call.

**Explicitly NOT in this amendment** (each is a clean later addition): an **admin "hold/postpone"** of an automatic release (Decision 5 below); email or push for admin warnings (Module 12 is in-app only); notifying the scout when funds are released; automating refunds; Safety or platform items in the tasks list (they have no list contract yet); a hard guarantee that a warning was **read** (only that it was durably sent); any change to what the student or scout sees.

It has **14 chunks.**

---

## PART A — FINDINGS AND CORRECTIONS [FOR NSISONG]

### FINDING 1 — today the money can leave without the student ever confirming
Module 10's release policy (condition 4) says a release is allowed when the handover is **accepted, *or* 48 hours have passed since it was *offered* with no dispute**. So a scout who offers a handover and a student who never responds — or never even saw it — triggers an automatic release after 48 hours. That directly contradicts your rule 1. The fallback is **removed** (Correction 1).

### FINDING 2 — "student confirmed" is not trustworthy yet: acceptance does not require an offer
Module 10 added `ConfirmHandoverOffered` and `ConfirmHandoverAccepted` to Booking and its test list says the two facts are "settable independently", refusing only a `CANCELLED`/`EXPIRED` booking. Read literally, **a student can record "accepted" before any offer exists, and even on a booking that has not been paid.** Then "confirmed an offer" would be a lie: nobody offered anything. Enforcing your rule on top of that foundation would be enforcing nothing. **Fix (ADR-249):** Booking refuses `accepted` unless `offered` is already recorded and the booking is `CONFIRMED`; the release policy independently requires `offered_at` **and** `accepted_at` **and** `accepted_at ≥ offered_at`. **Chunk 1 checks the real code** (the spec may not match what Gemini built) and counts any existing bookings whose data already breaks this.

### FINDING 3 — the admin has no signal at all
- Payment publishes **no event** for "a release is now possible". Notification (Module 12) never supported Payment events for staff.
- Module 14's overview counts **pending disputes** and nothing else about payments; Module 14 explicitly deferred "booking and payment exception views" (ADR-174).
- There is **no list endpoint** for payments. The only way an admin finds a releasable payment today is to already know its id (`GET /payments/{id}`).
- The automatic-release job (`payment_auto_release`) exists, is **off by default**, and when it fires it only writes a summary log line — **no one is told before or after**.

### FINDING 4 — Notification has no way to find "the admins"
Module 12 decides recipients from the event (a booking's student, a property's owner). Nothing can answer "who holds the permission to release funds?". Security has `list_identities_with_role` (added for Module 14's staff list) but no use case an adapter can call without a human actor. **Fix (ADR-255):** one small Security **system** use case.

### FINDING 5 — Notification is in-app only, and that limits what "notified" can honestly mean
Module 12 (ADR-130) deferred email and push. So "three warnings" means **three in-app notifications, durably recorded**. If no admin opens the app during the notice period, nobody sees them. The system makes the failure modes safe (no active admin → release blocked; late warnings → release delayed), and the warnings also show in the tasks list and the transaction review, but **a real delivery channel is worth adding before you turn automatic release on in production.** (Decision 4.)

### FINDING 6 — Admin's own rules decide how "tasks" must be built
Module 14 forbids Admin from copying or proxying other modules' data (ADR-163) and makes the overview **computed per request, no cache, no read model** (ADR-164). So the tasks endpoint is built the same way: each source answers **as the requesting staff member**; a source the caller cannot see is `NOT_AUTHORIZED`; a source that is down is `UNAVAILABLE`; nothing is stored in Admin. The **only new stored data** is Payment's own: the release schedule, the warnings, and the transaction review.

### FINDING 7 — a disputed release could dodge your rule
Module 10's `ResolveDispute` can resolve in the scout's favour ("release") and clear the hold so a release can proceed. A student who disputes *because* they never got access has, by definition, not confirmed. With no gate here, "resolve toward release" would be a back door around rule 1. **Fix (ADR-263):** resolving toward release (fully or in part) requires the confirmation too; without it the only available resolution is a refund. This has a consequence you should know about — Decision 2.

### FINDING 8 — a paid booking that is later cancelled leaves money in limbo
Module 15 tells the student "our team will review your payment" when a paid booking is invalidated, but nothing tells **the team**. The transaction review makes this visible (stage `BOOKING_CLOSED_FUNDS_HELD`) and the tasks list surfaces it ("decide on a refund").

### CORRECTIONS
**Correction 1 — Module 10's "48-hour fallback" (condition 4, ADR-105, `payment_release_fallback_hours`, trigger `automatic_48h_fallback`) is replaced.** The notice period now runs **from the student's confirmation**, not from the offer, and an automatic release can never happen without that confirmation. The old setting is removed; the old trigger value stays readable on historical decisions.
**Correction 2 — Module 10 Chunk 1's "both facts settable independently" is replaced** by ordered handover (Finding 2).
**Correction 3 — Module 14 ADR-174 deferred "payment exception views"; this amendment builds the payment half** (tasks + transaction review). Booking exception views remain deferred.
**Correction 4 — Module 14 ADR-162 ("Admin publishes and consumes no events") stays true.** Admin is pull-based. The new events flow from Payment to Notification only.

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-247 … ADR-264)
Continuing the log from Module 18 (233–246).

| ADR | Decision | Why |
|---|---|---|
| 247 | **"Student confirmed an offer" = Booking's `handover_offered_at` is set, `handover_accepted_at` is set, and `accepted_at ≥ offered_at`.** Booking is the single source of truth; Payment reads it through `BookingProvider` at decision time and never keeps its own authoritative flag | One fact, one owner; avoids a copy that can disagree |
| 248 | **Enforced in four independent layers, no override for any role:** (1) the pure release policy; (2) `AuthorizeRelease` **and** `ExecuteRelease` both re-check; (3) a **database `CHECK`** on `release_decisions` — a `RELEASE` decision cannot be stored without `student_confirmed_at`; (4) the reconcile job reports any release decision lacking it. Applies to admin release, automatic release **and** dispute-resolved release | "Must be enforced" — a rule that lives in one function is a rule one bug can break |
| 249 | **Booking amendment:** `ConfirmHandoverAccepted` requires `offered_at` to be set; both handover confirmations require the booking to be `CONFIRMED`. Repeats stay idempotent; existing rows that already break the order are treated as **unconfirmed** | Finding 2 |
| 250 | **The no-confirmation fallback is removed.** The notice period starts when Payment **opens the release schedule** after confirmation (never earlier, so a delayed event cannot shorten it). `payment_release_fallback_hours` is replaced by `payment_auto_release_delay_hours` | Finding 1 |
| 251 | **Release schedule and warnings are authoritative Payment tables.** The minimum of **three** warnings is a **code constant** (`MIN_RELEASE_WARNINGS = 3`): settings may add warnings, never remove them. A second **database `CHECK`** forbids an `AUTOMATIC` release decision recorded with fewer than three warnings | Your rule 2, enforced where it cannot be forgotten |
| 252 | **The notice period is derived and fail-safe.** Earliest automatic release = `max(window start + delay, last warning sent + final-warning lead)`; **one warning per run** and a minimum spacing between warnings, so a late job cannot send three at once; a warning is recorded as sent **only if an active approver exists** | A late worker delays money; it never shortens the notice |
| 253 | **A dispute restarts the notice.** When a dispute is raised the current warnings are superseded (kept as history); when it is resolved without a full refund a **new** cycle starts with fresh warnings | Warnings sent before a three-week dispute are stale |
| 254 | **Payment publishes five events through the shared outbox** (ids and enums only): `PaymentReleaseDue`, `PaymentAutoReleaseWarning`, `PaymentFundsReleased`, `PaymentFundsRefunded`, `PaymentDisputeRaised`. Only Notification consumes them | Module 15 pattern; Payment decides *what happened*, Notification decides *who is told* |
| 255 | **Staff recipients:** a new Security **system** use case `ListIdentitiesHoldingPermission`; Notification's adapter resolves "release approvers" (holders of `PAYMENT_AUTHORIZE_RELEASE`, currently `ADMIN` only) and keeps only `ACTIVE` accounts | Finding 4 |
| 256 | **New notification action `RELEASE_FUNDS`** with the existing action model: it stays open until the money is released or refunded, a dispute is raised, or the booking closes. Staff notices target `BOOKING:booking_id` | Reuses Module 15's mechanism and its resolve-by-target rule |
| 257 | **Transaction review:** one row per confirmed `Payment`, owned by Payment, written **only by Payment's own use cases in the same transaction as the change it reflects** (never by a copy job). `stage` and `next_action` are **pure, clock-free functions of stored facts**. Money sums on the row are a denormalized copy of the authoritative operations and are **reconciled and rebuildable** | You asked for a table; the guard-rails keep it honest |
| 258 | **Detail view = the row + live authoritative children + a live eligibility evaluation + best-effort display context.** Never raw provider payloads, webhook bodies, checkout tokens or secrets | Comprehensive for the admin, safe for the platform |
| 259 | **Review routes belong to Payment** (`/api/v1/payments/review/…`, `PAYMENT_REVIEW`). Admin does **not** proxy them (ADR-163); tasks point at them with a structured target | Delegate, don't duplicate |
| 260 | **`GET /api/v1/admin/tasks`:** computed per request; sections per source with `OK`/`UNAVAILABLE`/`NOT_AUTHORIZED` (ADR-164); **no tasks table**. v1 sources: `PAYMENT`, `ISSUES`, `VERIFICATION`. Safety and platform items are deferred and named | Finding 6 |
| 261 | **No new Security permissions.** Tasks need `ADMIN_OVERVIEW_VIEW`; each source applies its own permission as the caller; each item carries `can_act` computed by the owner for the caller | Least privilege unchanged |
| 262 | **Jobs:** new `payment_release_warnings`; `payment_auto_release` stays; both are **disabled by default** together (ADR-184). New `payment_review_reconcile` (enabled — it moves no money). The worker warns at startup if auto-release is enabled while warnings are disabled | Money must not move on a timer by accident |
| 263 | **Dispute resolution toward release (full or partial) requires student confirmation**; without it only a refund resolution is accepted | Finding 7 |
| 264 | **No admin hold/postpone in this amendment** (see Decision 5) | Scope; a hold changes who controls the scout's money and needs its own audited design |

### Decisions I need you to confirm (I chose a default for each)
1. **"Confirmed an offer" = the student accepted the scout's handover offer.** If you meant a different "offer" (for example, the student accepting something earlier in the booking), tell me before Chunk 3 — it changes the definition in ADR-247.
2. **Removing the fallback has a hard consequence: if a student never confirms, the money stays held indefinitely.** Neither admin release nor automatic release can move it, and a dispute resolved for the scout cannot either. The only exit is a refund. To keep this from becoming a silent trap, an aged "handover unconfirmed" **task** appears after `payment_handover_unconfirmed_alert_hours` (default 7 days) so a human decides — chase the student, or refund. Is that the behaviour you want?
3. **Defaults:** notice period 48 hours after confirmation; warnings at 24, 12 and 3 hours before; at least 60 minutes between warnings and 60 minutes between the last warning and the release. All settings; three is a fixed floor.
4. **Warnings are in-app only.** I would add a real channel (email or push) before enabling automatic release in production. Until then it stays disabled by default, as Module 15 already decided.
5. **Admin cannot pause an automatic release.** Their tools after a warning are: release now, refund, or leave it. Only the **student's** dispute can pause it. I recommend a small, audited "hold" as the next amendment — say the word.

---

## PART C — DESIGN SPECIFICATION [FOR YOU — GEMINI CLI]

### C1. Rules every chunk obeys

1. **Student confirmation is required for every release, with no override (ADR-247, 248).** Admin release, automatic release and dispute-resolved release alike. No role, flag, setting or script path bypasses it.
2. **Booking is the source of truth for handover facts.** Payment reads them through `BookingProvider` at the moment it decides. Event payloads carry ids only, so every subscriber **re-reads** the current facts; subscribers are **idempotent and order-independent** (no ordering guarantee exists between outbox events — Module 15 C4).
3. **An event is added with `uow.add_event` in the same transaction as the change it describes, and only on a real transition** (never on a replay or a no-op). Payloads are ids and enums only.
4. **System use cases take no actor and are never reachable over HTTP**; a guard test proves it (Module 15, ADR-191). This covers `OpenReleaseSchedule`, `RestartReleaseSchedule`, `DispatchReleaseWarnings`, `SyncBookingFactsForReview`, `RebuildTransactionReview`, `ReconcileTransactionReviews`.
5. **Only Payment writes the release schedule, the warnings and the transaction review.** Admin reads through ports **as the caller** and stores nothing. Notification learns of Payment only through events. No foreign key crosses a module boundary (inside Payment, foreign keys between its own tables are fine).
6. **Fail safe — never default to eligible.** An unreadable booking, a missing schedule, an unrecorded warning, an unresolvable approver list, any exception during evaluation → **not eligible**, logged, retried later. The only way money moves is a positive, complete evaluation.
7. **Notification templates are fixed strings**: no names, amounts, numbers, hours or URLs (Module 12, ADR-138).
8. **Money-moving automation is off by default**, and so is the warning job that must precede it (ADR-262).
9. **No new Security permission; no existing permission is widened.** `PAYMENT_REVIEW` (OPERATIONS+ADMIN) sees; `PAYMENT_AUTHORIZE_RELEASE` / `PAYMENT_AUTHORIZE_REFUND` (ADMIN) move money.
10. **Never log** amounts, names, dispute reasons, notes or provider payloads. Log ids, enums, counts and short error class names.
11. **Concurrency is by conditional `UPDATE … WHERE`, `INSERT … ON CONFLICT DO NOTHING`, or `SELECT … FOR UPDATE SKIP LOCKED`, checked by row count** — never check-then-write.
12. **New routes follow Module 18's recipe** (typed enums, `description` and a proven `examples` entry on every field, declared rules).
13. **Honest readiness:** everything not built is named in the docs.

### C2. Layout (paths confirmed or adjusted by Chunk 1; behavior fixed here)

```
modules/payment/
├── domain/        release_policy.py (rewritten)   release_schedule.py (new)   review_stage.py (new)
│                  value_objects.py (+ReviewStage, ReviewNextAction, WarningStage, EvaluationMode)
├── application/
│   ├── ports/     outbound.py (+ReleaseScheduleRepository, TransactionReviewRepository,
│   │              ReleaseApproverProvider, TransactionContextProvider)   events.py (+5 events)
│   └── use_cases/ open_release_schedule.py  restart_release_schedule.py  dispatch_release_warnings.py
│                  sync_booking_facts_for_review.py  rebuild_transaction_review.py
│                  reconcile_transaction_reviews.py  list_transaction_reviews.py
│                  get_transaction_review.py  get_transaction_review_summary.py  list_payment_tasks.py
│                  (rewrites: evaluate_release_eligibility, authorize_release, execute_release,
│                   resolve_dispute, process_automatic_releases; small edits: verify_payment_attempt,
│                   raise_dispute, execute_refund path)
└── adapters/      persistence/ (models, repositories)   events/booking_subscriber.py
                   security/release_approver_provider.py   context/transaction_context_provider.py
                   api/ review_router.py  review_schemas.py   jobs/ (factories)
modules/booking/       confirm_handover_offered.py, confirm_handover_accepted.py (ordering rules)
modules/security/      application/use_cases/list_identities_holding_permission.py (system)
modules/notification/  action RELEASE_FUNDS; 6 types; parsers; policies; StaffRecipientProvider
modules/admin_operations/ application/use_cases/get_tasks.py  ports TaskSource  adapters/tasks/*
```

### C3. Student confirmation and the release policy (ADR-247, 248, 250, 251, 263)

**Definition.** `student_confirmed_at` = `handover_accepted_at` **iff** `handover_offered_at is not None and handover_accepted_at is not None and handover_accepted_at >= handover_offered_at`; otherwise `None`.

**The rewritten pure function** (`domain/release_policy.py`; no I/O, no clock — the instant is passed in):
`evaluate_release_eligibility(fund_disposition, booking, handover, dispute, requested_amount, schedule, approvers_available, mode, now, settings_view) -> ReleaseEvaluation`
with `mode ∈ {MANUAL, AUTOMATIC}` and `ReleaseEvaluation(eligible, blocking_reason, student_confirmed_at, earliest_auto_release_at)`. Conditions are checked **in this order; the first failure is returned**:

| # | Condition | `blocking_reason` | Modes |
|---|---|---|---|
| 1 | A confirmed `Payment` and a `FundDisposition` exist | `no_confirmed_payment` | both |
| 2 | Booking is **`CONFIRMED`** (not cancelled, expired or invalidated) | `booking_not_confirmed` | both |
| 3 | Handover was offered | `handover_not_offered` | both |
| 4 | **Student confirmation (definition above)** | **`student_confirmation_required`** | both |
| 5 | No open dispute (`status != DISPUTE_HOLD`, no `OPEN` dispute) | `dispute_open` | both |
| 6 | `requested_amount ≤ remaining_releasable` and `> 0` | `amount_exceeds_remaining_balance` | both |
| 7 | A release schedule exists for the **current cycle** | `release_schedule_missing` | auto |
| 8 | `now ≥ window_starts_at + auto_release_delay` | `auto_release_window_not_elapsed` | auto |
| 9 | Every active warning of the current cycle has `sent_at` **and** their count ≥ `MIN_RELEASE_WARNINGS` (**3**) | `release_warnings_pending` | auto |
| 10 | `now ≥ last_warning_sent_at + final_warning_min_lead` | `final_warning_too_recent` | auto |
| 11 | At least one active release approver exists | `no_release_approver_available` | auto |

`earliest_auto_release_at` = `max(window_starts_at + delay, last_warning_sent_at + lead)` when all warnings are sent, otherwise `None` (it is derived on every read, never stored).
Conditions 1–2 and 5–6 are unchanged in spirit from Module 10 (condition 2 is now `CONFIRMED` rather than "not cancelled", matching Module 15's "auto-release is blocked for a non-`CONFIRMED` booking"). **Condition 3 is Module 10's existing "handover offered" check, unchanged; condition 4 replaces Module 10's "accepted, or 48 hours elapsed" rule; conditions 7–11 are new.** Module 10's remaining conditions (idempotency, authorization, decision-before-execution) stay in the use cases exactly as they are.

**The four enforcement layers (ADR-248):**

| Layer | Where | What it does |
|---|---|---|
| 1 | The pure policy | Returns `student_confirmation_required`; used by manual **and** automatic paths |
| 2 | `AuthorizeRelease` **and** `ExecuteRelease` | `AuthorizeRelease` evaluates (condition 4 included) and stores `student_confirmed_at` on the `ReleaseDecision`; `ExecuteRelease` **re-checks that the stored decision carries it** before any provider call, and refuses (`ReleaseNotEligible`, ERROR log) if not |
| 3 | The database | `release_decisions` gains `student_confirmed_at` and `warnings_sent_count`, plus two `CHECK`s (below) |
| 4 | `ReconcileTransactionReviews` | Reports any `RELEASE` decision (including legacy ones) that lacks `student_confirmed_at` |

```sql
ALTER TABLE release_decisions ADD COLUMN student_confirmed_at timestamptz NULL;
ALTER TABLE release_decisions ADD COLUMN warnings_sent_count smallint NULL;
ALTER TABLE release_decisions ADD CONSTRAINT ck_release_requires_student_confirmation
  CHECK (decision <> 'RELEASE' OR student_confirmed_at IS NOT NULL) NOT VALID;
ALTER TABLE release_decisions ADD CONSTRAINT ck_auto_release_requires_three_warnings
  CHECK (NOT (decision = 'RELEASE' AND origin = 'AUTOMATIC') OR warnings_sent_count >= 3) NOT VALID;
```
`NOT VALID` makes PostgreSQL enforce both rules on every **new** row while leaving historical rows untouched. Use raw SQL if Alembic's helper has no `postgresql_not_valid` option. **Do not run `VALIDATE CONSTRAINT`** — legacy rows may legitimately violate it; they are reported (layer 4), not rewritten. The `3` in the SQL and `MIN_RELEASE_WARNINGS` in code must be equal; a test asserts it.

**`ResolveDispute` (ADR-263).** A resolution that releases money (`RESOLVED_RELEASE`, or `RESOLVED_PARTIAL` with a release amount > 0) evaluates condition 4; if it fails the use case raises `ReleaseNotEligible` with `student_confirmation_required` **and writes nothing**. `RESOLVED_REFUND` and the refund part of a partial resolution need no confirmation. After a resolution that clears the hold and leaves funds held, call `RestartReleaseSchedule` (C4).

**New decision trigger value** for automatic releases: `automatic_after_confirmation_window`. `automatic_48h_fallback` is no longer produced; it stays valid on historical rows (the column is plain text — add no `CHECK` on it).

### C4. The release schedule, the warnings and the notice period (ADR-250 … 253)

**`release_schedules`** (authoritative; one row per fund disposition): `id`, `fund_disposition_id` (FK, **UNIQUE**), `payment_id`, `booking_id`, `student_confirmed_at` (permanent — the instant of the confirmation that opened it), `cycle` (smallint ≥ 1), `window_starts_at` (start of the current notice period), `created_at`, `updated_at`.
**`release_warnings`** (authoritative): `id`, `release_schedule_id` (FK), `cycle`, `warning_number` (smallint ≥ 1), `due_at`, `sent_at` (nullable), `superseded_at` (nullable), `created_at`; **UNIQUE `(release_schedule_id, cycle, warning_number)`**; partial index `(due_at) WHERE sent_at IS NULL AND superseded_at IS NULL`.

**`OpenReleaseSchedule(payment_id)`** (system) — called by `SyncBookingFactsForReview` when the confirmation first becomes valid. In one transaction: re-evaluate that the disposition is `HELD`, confirmation is valid (C3), no open dispute, booking `CONFIRMED`, remaining > 0; `INSERT … ON CONFLICT (fund_disposition_id) DO NOTHING`; **only if a row was inserted** (a real transition): set `window_starts_at = now` (never `student_confirmed_at`, so a delayed event cannot shorten the notice), insert the cycle-1 warning rows (`due_at = window_starts_at + delay − offset_i`), update the review row, and `add_event(PaymentReleaseDue)`. A replay inserts nothing and emits nothing.

**`RestartReleaseSchedule(payment_id)`** (system) — called after a dispute is resolved without a full refund while the confirmation is still valid and funds remain: one conditional `UPDATE release_schedules SET cycle = cycle + 1, window_starts_at = now … WHERE fund_disposition_id = :d AND cycle = :expected` (row count 1 or nothing happens); mark the old cycle's **unsent** warnings `superseded_at = now` (sent ones stay as history); insert the new cycle's rows; update the review row; `add_event(PaymentReleaseDue)` again so the admin's action notification reappears.

**`DispatchReleaseWarnings(limit)`** (system; job `payment_release_warnings`). For schedules whose disposition is `HELD`, booking `CONFIRMED`, no open dispute: take the lowest-numbered unsent, unsuperseded warning of the current cycle that is **due** (`due_at ≤ now`) **and** whose predecessor is sent **and** `now ≥ predecessor.sent_at + warning_min_spacing`. **At most one warning per schedule per run.** Steps per warning: (1) `ReleaseApproverProvider.count_active_approvers() ≥ 1` — if **0**, claim nothing, log ERROR `no_release_approver_available`, move on; (2) claim with `UPDATE release_warnings SET sent_at = now WHERE id = :id AND sent_at IS NULL` — row count 0 means someone else did it; (3) on a claim, in the **same transaction**, update the review row's counters and `add_event(PaymentAutoReleaseWarning(payment_id, booking_id, student_id, cycle, warning_stage))`. `warning_stage` is `FIRST` (number 1), `FINAL` (the last number of the cycle), otherwise `REMINDER`.
"Sent" therefore means **durably queued to Notification** in the same commit as the record — not "read".

**Why late jobs cannot shorten the notice.** Condition 9 requires every warning sent; condition 10 forces `final_warning_min_lead` after the last one; the spacing rule forbids three warnings in one burst. If the warning job is down for a day, the release is *later*, never sooner.

**Worked timeline (defaults).** Confirmation at T0 → schedule opens, admins get **"release funds"** (action). Warnings due at T0+24h, T0+36h, T0+45h. Nominal automatic release T0+48h. If all three were sent on time, `earliest_auto_release_at = max(T0+48h, T0+45h+60min) = T0+48h`. The `payment_auto_release` job (hourly, if enabled) then releases at its next run after that instant.

**Settings validation (startup fails otherwise).** The offsets list has **at least three** entries, each a positive integer, **strictly decreasing**, and the first offset is **less than** `payment_auto_release_delay_hours`.

### C5. The transaction review (ADR-257, 258)

**`transaction_reviews`** — one row per confirmed `Payment`; owned and written only by Payment.

| Column | Type / rule | Notes |
|---|---|---|
| `id` | UUID PK | |
| `payment_id` | UUID FK, **UNIQUE** | |
| `fund_disposition_id` | UUID FK, **UNIQUE** | |
| `payment_attempt_id` | UUID FK | |
| `booking_id`, `student_id` | UUID, indexed, no FK | |
| `provider_id`, `property_id` | UUID nullable, no FK | snapshots at payment time; `provider_id` resolved through a Housing/Booking port; null only if the lookup failed (the reconcile job repairs it) |
| `amount_kobo`, `currency` | bigint `CHECK > 0`, `NGN` | the permanent fact |
| `provider_name`, `provider_reference` | text | |
| `paid_at` | timestamptz | the payment's `confirmed_at` |
| `booking_status` | text `CHECK` in Booking's statuses | updated by Booking events |
| `handover_offered_at`, `handover_accepted_at` | timestamptz nullable | snapshots; set once |
| `student_confirmed_at` | timestamptz nullable | set only when the C3 definition holds |
| `release_cycle`, `release_window_starts_at` | smallint / timestamptz nullable | copied from the schedule |
| `warnings_required`, `warnings_sent`, `last_warning_sent_at` | smallint / smallint / timestamptz nullable | copied from the current cycle |
| `open_dispute_id`, `dispute_count` | UUID nullable / smallint | |
| `released_kobo`, `refunded_kobo` | bigint `≥ 0` | denormalized from the operations (reconciled); `CHECK (released_kobo + refunded_kobo <= amount_kobo)` |
| `stage` | text `CHECK` — indexed | below |
| `next_action`, `next_action_since` | text `CHECK` / timestamptz nullable | below; partial index `WHERE next_action <> 'NONE'` |
| `created_at`, `updated_at`, `version` | | conditional updates on `version` |

**`stage` and `next_action` are pure, clock-free functions of the stored facts** (`domain/review_stage.py`; first match wins). Anything that depends on the current time (an aged handover, an automatic-release countdown) is computed at read time, **never stored**.

| # | Condition | `stage` | `next_action` |
|---|---|---|---|
| 1 | disposition `RECONCILIATION_REQUIRED` or a release/refund operation in `RECONCILIATION_REQUIRED` | `RECONCILIATION_REQUIRED` | `RECONCILE_OPERATION` |
| 2 | an `OPEN` dispute | `DISPUTED` | `RESOLVE_DISPUTE` |
| 3 | nothing remains held (`remaining = 0`) | `RELEASED` (only releases) / `REFUNDED` (only refunds) / `SETTLED_SPLIT` (both) | `NONE` |
| 4 | booking is `CANCELLED`/`EXPIRED` and funds remain | `BOOKING_CLOSED_FUNDS_HELD` | `DECIDE_REFUND` |
| 5 | `student_confirmed_at` set | `RELEASE_DUE` | `RELEASE_FUNDS` |
| 6 | `handover_offered_at` set | `AWAITING_STUDENT_CONFIRMATION` | `NONE` |
| 7 | otherwise | `AWAITING_HANDOVER_OFFER` | `NONE` |

`next_action_since` = the instant the row entered its current `next_action` (set on the transition, never moved by a no-op write).

**Who writes the row — always in the same transaction as the change it reflects:**

| Moment | Use case | Writes |
|---|---|---|
| Payment confirmed | `VerifyPaymentAttempt` (small edit) | creates the row; resolves `provider_id`/`property_id`; calls the booking sync |
| Handover offered / accepted; booking cancelled / expired / invalidated | `SyncBookingFactsForReview` (via the Booking subscriber) | re-reads Booking's facts; updates snapshots, `student_confirmed_at`, `booking_status`, stage; may call `OpenReleaseSchedule` |
| Dispute raised / resolved | `RaiseDispute` / `ResolveDispute` | `open_dispute_id`, `dispute_count`, stage; emits `PaymentDisputeRaised`; resolve may call `RestartReleaseSchedule` |
| Release / refund succeeds | `ExecuteRelease` / refund path | `released_kobo` / `refunded_kobo`, stage; emits `PaymentFundsReleased` / `PaymentFundsRefunded` |
| Warning sent; schedule opened / restarted | the schedule use cases | the warning and window columns |

**`RebuildTransactionReview(payment_id)`** (system) recomputes the **whole row** from the authoritative sources (payment tables, schedule, warnings, operations, disputes, and Booking through the port). **`ReconcileTransactionReviews(limit)`** (system; job `payment_review_reconcile`): (a) creates a row for every payment that has none (this **is** the backfill for existing payments); (b) for each row, recomputes and **repairs** any difference in stage, next action or sums, counting each repair; (c) reports every `RELEASE` decision lacking `student_confirmed_at` (layer 4); (d) reports bookings whose handover facts are out of order (Finding 2). It never moves money.

**Backfill behaviour to expect.** A legacy payment whose handover was already accepted gets a schedule opened with `window_starts_at = now`, so the **full** notice period applies and each such payment produces one "release funds" notification. Intended.

### C6. Events and Notification (ADR-254 … 256)

**New Payment events** (each extends the shared-kernel `DomainEvent`; registered in the `EventContractRegistry`; ids and enums only):

| Event | Fields | Published when |
|---|---|---|
| `PaymentReleaseDue` | `payment_id`, `booking_id`, `student_id`, `cycle` | a schedule is opened or a cycle restarts |
| `PaymentAutoReleaseWarning` | same + `warning_stage` (`FIRST`/`REMINDER`/`FINAL`) | a warning is claimed |
| `PaymentFundsReleased` | `payment_id`, `booking_id`, `student_id`, `origin` (`AUTOMATIC`/`MANUAL`) | a release operation becomes `SUCCEEDED` |
| `PaymentFundsRefunded` | same | a refund operation becomes `SUCCEEDED` |
| `PaymentDisputeRaised` | `payment_id`, `booking_id`, `student_id` | a dispute is created |

**Security — `ListIdentitiesHoldingPermission(permission) -> list[identity_id]`** (system; no actor; inbound port; never routed). Derived from Security's own role→permission policy and its existing `list_identities_with_role`. It returns **ids only**.

**Notification additions** (Module 12 / 15 rules: Notification's `domain`/`application` import nothing from other modules; only `adapters/` do).
- **Action:** `NotificationAction.RELEASE_FUNDS`. Migration alters the `action` `CHECK` (read it; `downgrade` restores it).
- **New outbound port `StaffRecipientProvider.list_release_approvers() -> list[EntityId]`**, adapter in `adapters/security/` calling Security's new use case and keeping only `ACTIVE` accounts (through Identity's public port). Result is cached for nothing — resolved at processing time.
- **Six types**, category `PAYMENT` (exists since Module 15), target `BOOKING:booking_id`, recipients = **release approvers**:

| Type | Action | Title | Body |
|---|---|---|---|
| `payment.release_due.staff` | `RELEASE_FUNDS` | Action needed: release funds | A student confirmed their handover. The held payment is ready to review and release. |
| `payment.auto_release_warning_first.staff` | — | Automatic release approaching | Funds for a confirmed booking will be released automatically unless they are released or refunded first. Review the transaction. |
| `payment.auto_release_warning_reminder.staff` | — | Reminder: automatic release | Funds for a confirmed booking are still due to be released automatically. Review the transaction. |
| `payment.auto_release_warning_final.staff` | — | Final notice: automatic release | Funds for a confirmed booking will be released automatically very soon. Review the transaction now. |
| `payment.dispute_raised.staff` | — | Payment dispute raised | A student raised a dispute on a held payment. Release is paused until it is resolved. |
| `payment.funds_auto_released.staff` | — | Funds released automatically | Funds for a confirmed booking were released automatically. |

- **Recipient and resolution policy:**

| Event | Creates | Resolves (on `BOOKING:booking_id`) |
|---|---|---|
| `PaymentReleaseDue` | release approvers → `payment.release_due.staff` (`RELEASE_FUNDS`) | — |
| `PaymentAutoReleaseWarning` | release approvers → the type for `warning_stage` | — |
| `PaymentDisputeRaised` | release approvers → `payment.dispute_raised.staff` | `RELEASE_FUNDS` |
| `PaymentFundsReleased` | if `origin = AUTOMATIC`: approvers → `payment.funds_auto_released.staff` | `RELEASE_FUNDS` |
| `PaymentFundsRefunded` | — | `RELEASE_FUNDS` |
| `BookingCancelled`, `BookingExpired`, `BookingInvalidated` | (existing notices unchanged) | **adds `RELEASE_FUNDS`** to the actions they already resolve |

Warnings do **not** collapse (distinct events, no `group_key`); the release-due action never collapses (Module 15). Strict parsers reject anything malformed; a recipient list of zero is `PROCESSED` with a WARNING `notification_no_recipient` (as Module 12 does), never a guessed recipient.

### C7. The admin tasks endpoint (ADR-260, 261)

**`GET /api/v1/admin/tasks`** — permission `ADMIN_OVERVIEW_VIEW` (`OPERATIONS`, `ADMIN`). Query: `source` (repeatable: `PAYMENT`, `ISSUES`, `VERIFICATION`; default all), `type` (repeatable task type), `priority` (`NORMAL`/`HIGH`), `limit_per_source` (1–100, default `admin_tasks_per_source_limit_default`).

`GetTasks(actor, filters)` follows Module 14 C9 exactly: authorize `ADMIN_OVERVIEW_VIEW`; then **sequentially**, each source in its **own short-lived session**, under `asyncio.wait_for(admin_overview_section_timeout_seconds)`, calls its `TaskSource.fetch(actor_id, filters, limit)` **as the requesting staff member**. `Forbidden` → `NOT_AUTHORIZED`; timeout or any other exception → `UNAVAILABLE` (WARNING with source name and error class only). Nothing is cached, stored or defaulted.

```json
{
  "as_of": "2026-11-16T09:30:00Z",
  "sections": [
    {
      "source": "PAYMENT", "status": "OK", "as_of": "2026-11-16T09:30:00Z", "total": 3,
      "items": [
        {
          "task_id": "PAYMENT:RELEASE_DUE:4b0f…",
          "type": "RELEASE_DUE", "priority": "HIGH",
          "since": "2026-11-14T08:00:00Z", "due_at": null,
          "subject": {"type": "PAYMENT", "id": "4b0f…"},
          "target": {"type": "BOOKING", "id": "91ac…"},
          "facts": {"stage": "RELEASE_DUE", "amount_kobo": 18000000, "currency": "NGN",
                    "warnings_sent": 1, "warnings_required": 3,
                    "earliest_auto_release_at": null, "auto_release_enabled": true},
          "required_permission": "PAYMENT_AUTHORIZE_RELEASE", "can_act": true
        }
      ]
    },
    {"source": "ISSUES", "status": "OK", "as_of": "…", "total": 0, "items": []},
    {"source": "VERIFICATION", "status": "NOT_AUTHORIZED", "as_of": "…", "total": null, "items": [], "reason_code": "forbidden"}
  ]
}
```
**`task_id` is deterministic** (`<SOURCE>:<TYPE>:<subject id>`), so the frontend can key rows and detect resolution by absence. **`type` and `title`:** Admin returns a **type code only**; the frontend owns the wording. **`facts`** carries only small, non-sensitive scalars named by the owning source.

**Task catalog (v1):**

| Source | Type | Appears when (derived live) | Priority | `required_permission` to act |
|---|---|---|---|---|
| PAYMENT | `RELEASE_DUE` | review `next_action = RELEASE_FUNDS` | `HIGH` once ≥ 1 warning was sent, else `NORMAL` | `PAYMENT_AUTHORIZE_RELEASE` |
| PAYMENT | `RESOLVE_DISPUTE` | `next_action = RESOLVE_DISPUTE` | `HIGH` | `PAYMENT_AUTHORIZE_RELEASE` (or `_REFUND` for a refund resolution) |
| PAYMENT | `DECIDE_REFUND` | `next_action = DECIDE_REFUND` | `NORMAL` | `PAYMENT_AUTHORIZE_REFUND` |
| PAYMENT | `RECONCILE_OPERATION` | `next_action = RECONCILE_OPERATION` | `HIGH` | `PAYMENT_REVIEW` |
| PAYMENT | `FOLLOW_UP_HANDOVER` | stage `AWAITING_STUDENT_CONFIRMATION` and `handover_offered_at < now − payment_handover_unconfirmed_alert_hours` | `NORMAL` | `PAYMENT_REVIEW` |
| ISSUES | `ISSUE_ASSIGNED_TO_ME`, `ISSUE_UNASSIGNED` | the caller's own open/in-progress issues; unassigned open issues | `HIGH` if the issue is `HIGH`, else `NORMAL` | `ADMIN_ISSUES_MANAGE` |
| VERIFICATION | `REVIEW_PENDING` | Verification's `ListPendingReviews` as the caller | `NORMAL` | Verification's own review permission |

Within a section: priority `HIGH` first, then `since` ascending (oldest first). **`can_act` is computed by the owning source for the caller** (does the caller hold `required_permission`?), so an `OPERATIONS` user sees payment tasks with `can_act: false`.
**Ports (Admin):** `TaskSource` (`fetch(actor_id, filters, limit) -> TaskSection`, raising the owner's `Forbidden`); adapters in `adapters/tasks/`: `payment_task_source.py` (Payment's `ListPaymentTasks`), `issues_task_source.py` (Admin's own repository), `verification_task_source.py` (Verification's `ListPendingReviews`). **Deferred and named:** Safety (`GetSafetyOverview` has counts only), platform dead-letters.
**Overview extension:** the `payments` section gains `release_due` and `handover_unconfirmed` counts from Payment's summary use case, beside `pending_disputes`.

### C8. The transaction review endpoints (Payment, `PAYMENT_REVIEW`)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/payments/review/transactions` | list; filters `stage` (repeatable), `next_action`, `needs_action` (bool: `next_action != NONE`), `booking_id`, `student_id`, `provider_id`, `paid_from`, `paid_to`; `sort` (`ACTION_SINCE_ASC` default when `needs_action=true`, else `PAID_AT_DESC`; also `PAID_AT_ASC`); shared `PageRequest`; rows come from the table only (fast) |
| GET | `/api/v1/payments/review/transactions/{payment_id}` | full detail |
| GET | `/api/v1/payments/review/transactions/by-booking/{booking_id}` | same detail, found by booking (what a notification's `BOOKING` target needs); `404` if none |
| GET | `/api/v1/payments/review/summary` | counts by `stage` and by `next_action`, `release_due_oldest_since`, `warnings_pending`, `auto_release_enabled` |

An unknown id is a plain `404`. The existing `GET /payments/{id}`, `/mine`, disputes and release/refund routes are **unchanged** (the review routes sit on a static `review` segment, as `/payments/disputes/pending` already does).

**List row:** `payment_id`, `booking_id`, `student_id`, `provider_id`, `amount_kobo`, `currency`, `paid_at`, `stage`, `next_action`, `next_action_since`, `released_kobo`, `refunded_kobo`, `warnings_sent`, `warnings_required`, `open_dispute`: bool, `can_release`: bool (caller holds `PAYMENT_AUTHORIZE_RELEASE` **and** `next_action = RELEASE_FUNDS`).

**Detail** (everything live from the authoritative tables except the snapshot facts; **never** raw provider payloads, webhook bodies, checkout tokens or secrets):
```json
{
  "as_of": "…",
  "transaction": {"payment_id": "…", "payment_attempt_id": "…", "fund_disposition_id": "…", "booking_id": "…",
                  "amount_kobo": 18000000, "currency": "NGN", "paid_at": "…",
                  "provider_name": "…", "provider_reference": "…",
                  "stage": "RELEASE_DUE", "next_action": "RELEASE_FUNDS", "next_action_since": "…"},
  "parties": {"student": {"id": "…", "display_name": null}, "provider": {"id": "…", "display_name": null}},
  "listing": {"listing_id": "…", "property_id": "…", "title": null, "property_name": null},
  "context_status": "AVAILABLE",
  "booking": {"id": "…", "status": "CONFIRMED", "handover": {"offered_at": "…", "accepted_at": "…", "student_confirmed": true}},
  "funds": {"held_kobo": 18000000, "released_kobo": 0, "refunded_kobo": 0, "remaining_kobo": 18000000, "disposition_status": "HELD"},
  "release": {
    "eligible_now": true, "blocking_reason": null,
    "decisions": [{"id": "…", "decision": "RELEASE", "amount_kobo": 18000000, "origin": "MANUAL",
                   "triggering_fact": "student_accepted", "decided_at": "…", "authorized_by": "…",
                   "student_confirmed_at": "…"}],
    "auto": {"enabled": true, "delay_hours": 48, "cycle": 1, "window_starts_at": "…",
             "earliest_auto_release_at": null, "blocking_reason": "release_warnings_pending",
             "warnings": {"required": 3, "sent": 1,
                          "items": [{"number": 1, "stage": "FIRST", "due_at": "…", "sent_at": "…"},
                                    {"number": 2, "stage": "REMINDER", "due_at": "…", "sent_at": null},
                                    {"number": 3, "stage": "FINAL", "due_at": "…", "sent_at": null}]}}
  },
  "operations": {"releases": [{"id": "…", "amount_kobo": 0, "status": "SUCCEEDED", "requested_at": "…", "confirmed_at": "…", "failure_reason": null}],
                 "refunds": []},
  "disputes": [{"id": "…", "status": "OPEN", "raised_at": "…", "raised_by": "…", "reason": "…",
                "resolved_at": null, "resolved_by": null, "resolution_notes": null}],
  "attempts": [{"id": "…", "status": "SUCCEEDED", "created_at": "…", "confirmed_at": "…"}],
  "ledger": {"balanced": true, "entries": [{"type": "CHARGE", "amount_kobo": 18000000, "created_at": "…"}]},
  "timeline": [{"at": "…", "kind": "PAYMENT_CONFIRMED", "actor": {"type": "SYSTEM"}, "detail": {}}],
  "available_actions": {"release": {"allowed": true, "reason": null},
                        "refund": {"allowed": true, "reason": null},
                        "resolve_dispute": {"allowed": false, "reason": "no_open_dispute"}}
}
```
- **`release.eligible_now`/`blocking_reason`** come from a **live** manual-mode evaluation (C3) — the screen shows the truth even if the stored row lags. `release.auto.blocking_reason` is the live automatic-mode result.
- **`timeline`** is assembled **at read time** (no timeline table) from timestamps that already exist: `PAYMENT_CONFIRMED`, `HANDOVER_OFFERED`, `HANDOVER_ACCEPTED`, `RELEASE_SCHEDULE_OPENED`, `AUTO_RELEASE_WARNING_SENT` (with `warning_stage`), `RELEASE_SCHEDULE_RESTARTED`, `DISPUTE_RAISED`, `DISPUTE_RESOLVED`, `RELEASE_DECISION_RECORDED`, `RELEASE_EXECUTED`, `REFUND_REQUESTED`, `REFUND_EXECUTED`; each with `actor.type` ∈ `STUDENT`/`PROVIDER`/`ADMIN`/`SYSTEM`; `detail` holds enums and ids only.
- **`display_name`, `title`, `property_name`** are **best-effort** through `TransactionContextProvider` (an adapter composing Booking, Housing and Profile **public** ports). Where a public read does not exist, the field is `null` and `context_status` is `PARTIAL`; if the lookup fails, `UNAVAILABLE`. **A context failure never fails the request.** Chunk 1 records which fields the public ports can supply; add nothing that needs a new cross-module contract.
- **`ledger.balanced`** reuses Module 10's existing reconciliation invariant; this endpoint never changes it.
- **`available_actions`** is computed for the caller: the right permission **and** the live evaluation.

### C9. Settings (`config/settings.py`, `.env.example`; invalid values fail startup)

| Setting | Default | Rule |
|---|---|---|
| `payment_auto_release_delay_hours` | `48` | int ≥ 2; **replaces** `payment_release_fallback_hours` (removed) |
| `payment_release_warning_offsets_hours` | `"24,12,3"` | comma list; ≥ 3 entries; positive; strictly decreasing; first < delay |
| `payment_release_warning_min_spacing_minutes` | `60` | int ≥ 1 |
| `payment_release_final_warning_min_lead_minutes` | `60` | int ≥ 1 |
| `payment_handover_unconfirmed_alert_hours` | `168` | int ≥ 1 |
| `admin_tasks_per_source_limit_default` | `20` | 1–100 |
| `platform_jobs_disabled` | `"payment_auto_release,payment_release_warnings"` | default widened; both money-related jobs stay off until deliberately enabled |
| `platform_job_payment_release_warnings_interval_seconds` | `300` | |
| `platform_job_payment_review_reconcile_interval_seconds` | `86400` | |

`MIN_RELEASE_WARNINGS = 3` is a **constant in code, not a setting.**

### C10. Jobs (registered in Module 15's `job_registry.py`; wiring only)

| Job | Wraps | Interval | Default |
|---|---|---|---|
| `payment_release_warnings` | `DispatchReleaseWarnings` | 300 s | **disabled** |
| `payment_auto_release` | rewritten `ProcessAutomaticReleases` (below) | 3600 s | **disabled** (unchanged) |
| `payment_review_reconcile` | `ReconcileTransactionReviews` | 86400 s | **enabled** (moves no money) |

**`ProcessAutomaticReleases` (rewritten).** Instead of scanning every `HELD` disposition, it lists reviews with `stage = RELEASE_DUE` (indexed), and for each calls `EvaluateReleaseEligibility(mode=AUTOMATIC)`; eligible → `AuthorizeRelease(origin=AUTOMATIC, triggering_fact="automatic_after_confirmation_window")`, which records the decision (with `student_confirmed_at` and `warnings_sent_count`) **before** any provider call, then `ExecuteRelease`. Not eligible → skip silently. One summary log line (processed, released, skipped).
**Worker startup consistency check:** if `payment_auto_release` is enabled while `payment_release_warnings` is disabled, log WARNING "automatic release will never fire: no warnings are being sent". (The release itself is already impossible without warnings — condition 9 — so this is a clarity message, not the safety.)

### C11. Errors and blocking reasons

No new `ApplicationError` classes are needed in Payment: `ReleaseNotEligible` keeps its existing code and status and carries the new `blocking_reason` values of C3. **New Booking errors:** `HandoverNotOffered` (`409 handover_not_offered`) and, **only if Booking has no existing error for "booking is not in the right state"**, `BookingNotConfirmedForHandover` (`409`). Chunk 1 maps the existing ones; use them where they exist. Review routes: `404` for an unknown id; `403` for a missing permission, as everywhere.

### C12. Touch map — the only changes outside the new files

| Module / file | Change | Chunk |
|---|---|---|
| Booking | handover ordering and status rules; nothing else | 2 |
| Security | **one** system use case + port; no permission change | 5 |
| Payment | domain, tables, use cases, adapters, routes, jobs per C2 | 3, 4, 6–8, 10 |
| Notification | action, types, templates, parsers, policies, `StaffRecipientProvider`, resolution additions, two `CHECK` alterations | 9 |
| Admin & Operations | `GetTasks`, `TaskSource`, adapters, the route, overview `payments` extension | 11 |
| Platform Reliability | job registry entries and defaults; worker consistency check | 8 |
| `config/settings.py`, `.env.example`, `app.py`, `pyproject.toml` (import-linter) | per C9 and the new routes/contracts | as needed |

**Must not change:** any other module; any existing success response; any protected error; Module 10's refund flow beyond maintaining the review row and publishing `PaymentFundsRefunded`; the ledger's invariants.

### C13. Behavior-change list (known now; Chunk 1 completes it)

| Where | Before | After |
|---|---|---|
| Release policy | released on student acceptance **or** 48 h after the offer with no dispute | **student confirmation is mandatory** for every release; the window runs from confirmation and needs three warnings |
| `POST /bookings/{id}/handover/accepted` | allowed with no offer, on any non-closed booking | `409 handover_not_offered` without an offer; refused unless the booking is `CONFIRMED` |
| `POST /bookings/{id}/handover/offered` | allowed on any non-closed booking | refused unless the booking is `CONFIRMED` (only if Chunk 1 shows it is not already) |
| `POST /payments/{id}/release` (and the dispute resolve route) | could succeed without acceptance | `ReleaseNotEligible` with `student_confirmation_required` |
| `payment_release_fallback_hours` | existed | removed; replaced by `payment_auto_release_delay_hours` |
| `platform_jobs_disabled` default | `payment_auto_release` | `payment_auto_release,payment_release_warnings` |
| Notification | no staff notices | six staff types and the `RELEASE_FUNDS` action |

---

## PART D — CHUNK INSTRUCTIONS [FOR YOU — GEMINI CLI]

**Every chunk ends the same way:** run the linter, the type checker, `poetry run lint-imports`, and the **full test suite of every module the chunk touched** (Chunks 1, 12 and 14 run the entire suite). Report the real output.

---

### CHUNK 1 — INSPECTION & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** learn what is really in the repository and measure the current data. **No behavior change.**

**Part one — inspect and report** (a written report with real output, before any file is created):

1. **Booking.** Exactly what `ConfirmHandoverOffered` and `ConfirmHandoverAccepted` check today: booking status, actor, **whether `accepted` requires `offered`**, idempotent-repeat behavior, which errors they raise, when `HandoverOffered`/`HandoverAccepted` are published. Then run **read-only** SQL and report counts: bookings with `accepted_at` set and `offered_at` null; with `accepted_at < offered_at`; with either set while `status != 'CONFIRMED'`.
2. **Payment as built.** The real `release_policy.py` conditions (compare with Module 10's nine conditions and Module 15's `CONFIRMED` rule); `EvaluateReleaseEligibility`, `AuthorizeRelease`, `ExecuteRelease`, `ResolveDispute` and `ProcessAutomaticReleases` as written; `ReleaseNotEligible`'s real code and status; the `release_decisions` columns and the `triggering_fact` values in use; the refund use cases' names; every use of `payment_release_fallback_hours` and `automatic_48h_fallback` (code, tests, docs, `.env.example`); how Payment already uses `uow.add_event` (Module 15); the exact fields of `BookingSummary` and `HandoverStatus` — in particular **whether a provider/owner id and a listing id are available**, and if not, which public port (Housing's `GetProperty`) supplies the provider.
3. **Existing money data.** Counts of payments, fund dispositions by status, release decisions by `origin` and `triggering_fact`, and **how many `RELEASE` decisions have no accepted handover** (these will be reported, not changed).
4. **Notification as built.** The real enums and their database `CHECK` constraint names for category, type and action; the action model and `resolve_actions`; the strict parsers; the recipient policies; how Module 15 added the `PAYMENT` category; where templates live.
5. **Security.** `list_identities_with_role`, the policy file, `AuthorizationService`, and which Identity public port reports an account's status.
6. **Admin.** The overview's `payments` source; the real signature and item fields of Verification's `ListPendingReviews`; the issue repository's list filters; the overview's per-section runner (reuse it); the real name of the section-timeout setting.
7. **Platform.** `job_registry.py`, how `platform_jobs_disabled` is parsed, how event contracts are registered, `build_event_bus`, and the Housing subscriber as the pattern to copy.
8. **Display context.** Which of listing title, property name, campus name, student display name and provider display name each module's **existing public use cases** can supply without any new cross-module contract. Report per field; do not invent any.
9. **Tests that will change.** List every existing test that asserts "released after acceptance **or** 48 hours", the fallback setting, or an acceptance recorded before any offer. These are the only existing tests you will be allowed to edit, and only on the assertion lines.
10. **Conventions:** test folders, import-linter configuration, the frontend-documentation file, the AI-state files.
11. Any difference between this file and what you found. Do not "fix" this file.

**Part two — scaffolding.** Create the empty modules and folders in C2 (each with a docstring), and add the import-linter contracts: Payment's `adapters/events` may import Booking's `application/ports/events.py`; Payment's `adapters/security` may import Security's `application/ports`; Notification's `adapters/security` may import Security's and Identity's `application/ports`; Admin's `adapters/tasks` may import Payment's, Verification's and its own ports; nothing else is new. They must pass on the empty packages.

**Prohibition:** no behavior, no settings, no migrations.

**Acceptance criteria:** the full existing suite passes unchanged; `lint-imports` passes; the report answers all eleven items with real output.

---

### CHUNK 2 — BOOKING AMENDMENT: ORDERED HANDOVER
**[FOR YOU — GEMINI CLI]**

**Objective:** make "the student confirmed the offer" a trustworthy fact. Read **Finding 2, ADR-249**, C11, C13.

**Change only Booking's two handover use cases** (and their API error mapping):
1. `ConfirmHandoverAccepted` requires `handover_offered_at` to be set → otherwise `HandoverNotOffered` (`409 handover_not_offered`).
2. **Both** use cases require the booking to be `CONFIRMED`. Use Booking's existing "wrong state" error if Chunk 1 found one; otherwise add `BookingNotConfirmedForHandover` (`409`).
3. A repeated call that would change nothing stays an idempotent success and publishes **no** event (Module 15, unchanged). A mismatched actor stays `Forbidden`. Both facts stay permanent once set.
4. **Do not** rewrite or delete any existing row. Rows that already break the order stay as they are; the policy (C3) treats them as **unconfirmed**.

**Prohibition:** no new column, no migration, no change to `BookingStatus`, the state machine, any other use case, the events' fields, or the reminders.

**Tests you must write (Booking's folders, including API):** accept before offer → `409 handover_not_offered`, nothing stored; offer then accept → both succeed, `accepted_at ≥ offered_at`; offer on an `AWAITING_PAYMENT` booking → refused; accept on `CANCELLED`/`EXPIRED` → refused; repeat of each call → success, **no second event**; the wrong actor → `Forbidden`; the existing handover tests updated **only** where they asserted the old "independent" behavior (list each edit).

**Acceptance criteria:** the new tests pass; Booking's full suite passes apart from the listed assertion edits; Module 15's reminder tests still pass.

---

### CHUNK 3 — SETTINGS AND THE PURE DOMAIN
**[FOR YOU — GEMINI CLI]**

**Objective:** the rules as pure, testable code. Read **C3, C4, C5, C9**, ADR-247, 250–252.

**Build:**
1. The settings in **C9** (including the startup validation of the offsets list) and **remove** `payment_release_fallback_hours` from `config/settings.py` and `.env.example`; update every reference Chunk 1 found.
2. New value objects: `ReviewStage`, `ReviewNextAction`, `WarningStage`, `EvaluationMode`; the constant `MIN_RELEASE_WARNINGS = 3`.
3. `domain/release_policy.py` rewritten to **C3** — the eleven ordered conditions, both modes, `ReleaseEvaluation`, the `student_confirmed_at` definition, `earliest_auto_release_at`. **No I/O and no clock** — `now` is passed in.
4. `domain/release_schedule.py`: the pure planning of a cycle (`due_at` for each offset, the `warning_stage` mapping, current-cycle selection, the effective earliest-release computation).
5. `domain/review_stage.py`: the C5 derivation of `stage` and `next_action`.

**Prohibition:** no database, no use cases, no routes.

**Tests you must write (`tests/unit/payment/domain/`, no fakes needed):**
- **Policy:** each of the eleven conditions failing individually, with the exact `blocking_reason`; the **order** (a case failing two conditions returns the earlier one); manual vs automatic mode; the confirmation definition — accepted-before-offered is **unconfirmed**, equal timestamps are **confirmed**, offered-only and neither are unconfirmed; a `CANCELLED`, `EXPIRED` and `AWAITING_PAYMENT` booking each blocked.
- **The three-way distinction Module 10 tested** is re-expressed: offered/not accepted → blocked (`student_confirmation_required`) **at any elapsed time**, including 30 days; accepted + window not elapsed → manual eligible, automatic blocked; accepted + window elapsed + warnings missing → automatic blocked.
- **Notice period:** the worked timeline of C4 exactly; a late final warning pushes `earliest_auto_release_at` later; fewer than three warnings never eligible even if more time passes; `MIN_RELEASE_WARNINGS` equals the SQL literal (read it from the migration file in Chunk 4 — leave this assertion as a TODO that Chunk 4 completes, and say so).
- **Stages:** every row of the C5 table; **precedence** (reconciliation beats dispute beats settled beats closed booking beats release-due beats awaiting); no stage depends on time (call the function twice with different `now` values passed by a wrapper and assert identical output).
- **Settings:** two offsets rejected; non-decreasing offsets rejected; first offset ≥ delay rejected; a four-offset list accepted; the removed setting no longer exists.

**Acceptance criteria:** tests pass; the existing suite passes except the tests Chunk 1 listed for the old fallback, which you update **only on the assertion lines** and list.

---

### CHUNK 4 — PERSISTENCE AND THE DATABASE RULES
**[FOR YOU — GEMINI CLI]**

**Objective:** the tables, and the two database rules that make the policy impossible to bypass. Read **C3 (SQL), C4, C5**, ADR-248, 251, 257.

**Build** the models, migration and repositories for: `release_schedules`, `release_warnings`, `transaction_reviews` (columns, `CHECK`s, unique constraints and indexes exactly as C4/C5), and the two new `release_decisions` columns with the **two `NOT VALID` constraints** of C3. Define the repository ports (`ReleaseScheduleRepository`, `TransactionReviewRepository`) with the conditional-update methods the use cases will need: schedule insert-on-conflict, cycle restart conditional on the expected cycle, warning claim (`WHERE sent_at IS NULL`), review update conditional on `version`.

**Migration:** read it closely before applying. Use raw SQL for `NOT VALID` if Alembic's helper cannot express it. `downgrade` must work and must drop both constraints and columns. **No data is rewritten.**

**Prohibition:** no use case yet; do not run `VALIDATE CONSTRAINT`.

**Tests you must write (integration, bypassing the application layer):**
- inserting a `RELEASE` decision with `student_confirmed_at` null is **rejected by the database**; with it set, accepted; a `REFUND` decision without it is accepted;
- inserting an `AUTOMATIC` `RELEASE` with `warnings_sent_count` of 0, 2 or null is rejected; with 3 accepted; a `MANUAL` release needs no warning count;
- **both constraints are present and not validated** (`convalidated = false` in the system catalog) so legacy rows are untouched; the migration test applies to a database that already contains an old-style release decision and still succeeds;
- unique constraints (one schedule per disposition; one warning per `(schedule, cycle, number)`; one review per payment); the review's `CHECK` on released + refunded ≤ amount; the stage and next-action `CHECK`s;
- the conditional claim: two simultaneous claims of one warning → exactly one row count of 1;
- the `MIN_RELEASE_WARNINGS` ↔ SQL literal assertion promised in Chunk 3.

**Acceptance criteria:** tests pass against local Postgres; the migration applies and rolls back cleanly; the full Payment suite passes.

---

### CHUNK 5 — SECURITY AMENDMENT: WHO CAN APPROVE RELEASES
**[FOR YOU — GEMINI CLI]**

**Objective:** let other modules ask "who holds this permission?" without a human actor. Read C6 (Security), ADR-255, 261.

**Add** the system use case `ListIdentitiesHoldingPermission(permission) -> list[identity_id]` with its inbound port and composition, derived from Security's own policy and `list_identities_with_role`. Ids only. **No permission is added or changed.**

**Prohibition:** no HTTP route; no actor parameter; nothing else in Security.

**Tests you must write:** `PAYMENT_AUTHORIZE_RELEASE` returns exactly the accounts holding `ADMIN`; `PAYMENT_REVIEW` returns `OPERATIONS` and `ADMIN`; a permission nobody holds returns an empty list; a policy snapshot test proves the role→permission table is **unchanged**; a guard test proves the use case is reachable by no route (Module 15's system-use-case guard extended).

**Acceptance criteria:** tests pass; Security's full suite passes unchanged.

---

### CHUNK 6 — PAYMENT: BOOKING SYNC, THE RELEASE SCHEDULE AND THE REVIEW ROW
**[FOR YOU — GEMINI CLI]**

**Objective:** Payment learns the handover facts, opens the notice period, and keeps the transaction review current. Read **C4, C5, C6 (events)**, ADR-253, 254, 257, C1.2–1.5.

**Build:**
1. The ports `ReleaseApproverProvider` (declare now; implemented in Chunk 7) and `TransactionContextProvider` (declared; implemented in Chunk 10); the events `PaymentReleaseDue` and `PaymentDisputeRaised` in Payment's `application/ports/events.py` and their registry registration.
2. `SyncBookingFactsForReview(booking_id)` (system): finds the payment for the booking (none → no-op); **re-reads** Booking's facts through `BookingProvider`; updates the review row's snapshots, `student_confirmed_at` (only when the C3 definition holds), `booking_status` and derived stage/next action; calls `OpenReleaseSchedule` when the confirmation has just become valid.
3. `OpenReleaseSchedule` and `RestartReleaseSchedule` exactly per C4.
4. `adapters/events/booking_subscriber.py`: subscribes to Booking's `HandoverOffered`, `HandoverAccepted`, `BookingCancelled`, `BookingExpired`, `BookingInvalidated`, each calling `SyncBookingFactsForReview`; registered in `build_event_bus`. Imports only Booking's events port.
5. Small edits to existing use cases, **writing the review row in the same transaction**: `VerifyPaymentAttempt` (create the row; resolve `provider_id`/`property_id` through the port Chunk 1 found; a failed lookup leaves them null and logs a WARNING — payment confirmation must **never** fail because of it); `RaiseDispute` (sets `open_dispute_id`, `dispute_count`, derives stage, `add_event(PaymentDisputeRaised)`); `ResolveDispute` (clears the dispute fields and calls `RestartReleaseSchedule` when the hold clears with funds remaining — the enforcement gate itself is Chunk 7).

**Prohibition:** no change to what `VerifyPaymentAttempt`, `RaiseDispute` or `ResolveDispute` return or to their existing authorization; do not publish release/refund events yet.

**Tests you must write (unit with fakes, plus integration):** `SyncBookingFactsForReview` is **idempotent and order-independent** (process `HandoverAccepted` before `HandoverOffered`, twice, in either order → the same final row); an out-of-order pair (accepted before offered) leaves `student_confirmed_at` null; the schedule is opened **exactly once** for concurrent deliveries and `PaymentReleaseDue` is emitted exactly once (assert the outbox row count); `window_starts_at` is the processing time, not the confirmation time; warning rows are created with the right `due_at`s; a dispute raised moves the row to `DISPUTED` and emits the event in the same transaction (roll the transaction back → neither the row change nor the event persists); `RestartReleaseSchedule` increments the cycle only for the expected cycle, supersedes unsent warnings, keeps sent ones, and re-emits `PaymentReleaseDue`; booking cancelled after payment → `BOOKING_CLOSED_FUNDS_HELD` with `DECIDE_REFUND`; a booking with no payment → the subscriber does nothing; a lookup failure during payment confirmation does not fail the confirmation.

**Acceptance criteria:** tests pass; the full Payment and Booking suites pass unchanged apart from listed edits.

---

### CHUNK 7 — PAYMENT: ENFORCEMENT, WARNINGS AND AUTOMATIC RELEASE
**[FOR YOU — GEMINI CLI]**

**Objective:** the money rules. Read **C3, C4, C10**, ADR-248, 251–252, 263, **C1.6**.

**Build:**
1. `EvaluateReleaseEligibility` rewritten to gather the facts (disposition, booking, handover, dispute, schedule, `ReleaseApproverProvider`) and call the pure function; **any exception while gathering → not eligible** (C1.6), logged.
2. `AuthorizeRelease`: evaluates (manual **or** automatic); on success persists the `ReleaseDecision` **with `student_confirmed_at` and, for automatic, `warnings_sent_count`**, before any provider call. `ExecuteRelease`: **re-checks the stored decision carries `student_confirmed_at`** (and the warnings count for automatic) and refuses with `ReleaseNotEligible` + ERROR log otherwise — **before** any provider call.
3. `ResolveDispute`: the confirmation gate of C3/ADR-263 (nothing written on refusal); refund resolutions unaffected.
4. `ReleaseApproverProvider` adapter in `adapters/security/` (counts **active** holders of `PAYMENT_AUTHORIZE_RELEASE` through Security's new use case and Identity's status port; **any failure counts as zero**).
5. `DispatchReleaseWarnings` per C4 (one per schedule per run, spacing, predecessor sent, approver present, conditional claim, event in the same transaction, review counters updated).
6. `ProcessAutomaticReleases` rewritten per C10 (lists reviews at `RELEASE_DUE`; evaluates in automatic mode; `triggering_fact="automatic_after_confirmation_window"`).
7. Publish `PaymentFundsReleased` and `PaymentFundsRefunded` (with `origin`) when a release or refund operation becomes `SUCCEEDED`, and update the review row's `released_kobo`/`refunded_kobo` and stage in the same transaction. Register `PaymentAutoReleaseWarning` (step 5), `PaymentFundsReleased` and `PaymentFundsRefunded` in the `EventContractRegistry`.

**Prohibition:** no job registration yet (Chunk 8); no Notification code; no change to the provider ports, the ledger invariants or the refund flow beyond what step 7 names.

**Tests you must write (unit with fakes + integration; every bypass attempt is a test):**
- **Layer 1–2:** `AuthorizeRelease` by an `ADMIN` on an unconfirmed payment → `ReleaseNotEligible(student_confirmation_required)` and **no decision row**; offered-not-accepted for any elapsed time → still refused; a **hand-crafted decision lacking the confirmation** (inserted through the repository, bypassing `AuthorizeRelease`) given to `ExecuteRelease` → refused and **the fake provider is never called**.
- **Layer 3 (database)** is covered in Chunk 4; add one integration test proving the application path also cannot write a decision without it.
- **Dispute path:** resolve-for-release without confirmation → refused, nothing written; with confirmation → hold clears, a new cycle starts with fresh warnings and `PaymentReleaseDue` is re-emitted; resolve-for-refund without confirmation → succeeds.
- **Automatic:** blocked before the window; blocked with 0, 1 or 2 warnings sent; blocked within the final-warning lead; blocked with no active approver; blocked with an open dispute; **released when every condition holds** and the decision row carries `warnings_sent_count ≥ 3` and `student_confirmed_at`; **a late warning job delays the release** (advance the clock past the nominal time with the final warning sent late → released only after the lead).
- **Warnings:** at most one per schedule per run (a clock far past all three due times still sends one per run, spaced); ordering enforced; **no approver → nothing claimed, ERROR logged**; two dispatchers racing one warning → exactly one event in the outbox; a dispute open → nothing dispatched.
- **Races (concurrency audit):** a dispute raised while the automatic job evaluates → the dispute wins (no release); two automatic runs → one release operation; the manual release racing the automatic one → one release operation (Module 10's existing idempotency holds).
- **No `automatic_48h_fallback` decision is ever produced.**
- **Failure-safe:** `BookingProvider` raising during evaluation → not eligible, no exception escapes the job.

**Acceptance criteria:** tests pass; the full Payment suite passes apart from listed edits; the nine-condition test file from Module 10 is updated to the eleven conditions and reads as a line-by-line proof of C3.

---

### CHUNK 8 — JOBS, RECONCILE AND BACKFILL
**[FOR YOU — GEMINI CLI]**

**Objective:** wire the jobs, and give the review table one repair path. Read **C5 (rebuild/reconcile), C9, C10**, ADR-262.

**Build:**
1. `RebuildTransactionReview` and `ReconcileTransactionReviews` per C5 (create missing rows, repair differences, report layer-4 and out-of-order findings, never move money).
2. Register `payment_release_warnings` and `payment_review_reconcile` in `job_registry.py`; keep `payment_auto_release`; set the **new `platform_jobs_disabled` default**; add the worker's startup consistency WARNING.
3. A `--once` run prints the new counts.

**Prohibition:** the registry stays wiring only; no business logic in the factories.

**Tests you must write:** reconcile **creates** rows for payments that have none (the backfill) and opens schedules for already-confirmed ones with `window_starts_at = now`; **repairs** a deliberately corrupted row (wrong stage, wrong released sum) and counts the repair; reports a legacy `RELEASE` decision without `student_confirmed_at` and an out-of-order booking, **changing neither**; it calls **no provider method** and writes **no ledger entry**; a second run changes nothing; the registry contains exactly the old jobs plus the two new ones; `payment_auto_release` and `payment_release_warnings` show `DISABLED` by default and `payment_review_reconcile` is enabled; the consistency WARNING appears when auto-release is enabled and warnings are not; `--list` and `--stats` include the new jobs.

**Acceptance criteria:** tests pass; the platform and Payment suites pass; running `python scripts/run_platform_worker.py --only payment_review_reconcile --once` on a database with existing payments creates their rows (paste the output).

---

### CHUNK 9 — NOTIFICATION AMENDMENT: TELLING THE ADMIN
**[FOR YOU — GEMINI CLI]**

**Objective:** the notices. Read **C6**, ADR-254–256, and Module 12 C1/C5, Module 15 C10.

**Build:** `NotificationAction.RELEASE_FUNDS` (migration alters the `action` `CHECK`; read it; `downgrade` restores it); the six types, templates and policies of C6 (**exact** titles and bodies); the `StaffRecipientProvider` port and its `adapters/security/` adapter; strict parsers for the five Payment events; the subscribers registered in `build_event_bus`; the resolution additions (the three Booking events now also resolve `RELEASE_FUNDS`; the three Payment events resolve it as listed).

**Prohibition:** Notification's `domain`/`application` import nothing from any other module; only `adapters/` do; no other module imports Notification; no template contains a placeholder, a name, an amount, a number of hours or a URL.

**Tests you must write:** every event → the **exact** title, body, type, category, target, action and recipients of C6, **and nobody else** (a student and a scout never receive a staff notice); recipients are exactly the **active** approvers (a disabled admin gets nothing); **zero approvers → the event is `PROCESSED` with a WARNING and no guessed recipient**; the `RELEASE_FUNDS` action **stays open after being read** and resolves on `PaymentFundsReleased`, `PaymentFundsRefunded`, `PaymentDisputeRaised`, `BookingCancelled`, `BookingExpired` and `BookingInvalidated`, in **any order** (resolution is order-independent); three warnings produce **three separate rows** (no collapsing); `PaymentFundsReleased(origin=MANUAL)` creates no auto-release notice; a malformed or unknown event is `REJECTED`; a duplicate delivery changes nothing; the old types and Module 15's student payment notices are untouched; `GET /notifications?action_required=true` returns an open release action for an admin.

**Acceptance criteria:** tests pass; the full Notification suite passes unchanged apart from the additions.

---

### CHUNK 10 — THE TRANSACTION REVIEW: READ SIDE AND ROUTES
**[FOR YOU — GEMINI CLI]**

**Objective:** what the frontend reads. Read **C5, C7 (Payment's `ListPaymentTasks`), C8**, ADR-258, 259.

**Build:** `ListTransactionReviews`, `GetTransactionReview`, `GetTransactionReviewByBooking`, `GetTransactionReviewSummary`, and **`ListPaymentTasks(actor, filters, limit)`** (the Payment source Admin will call: reads review rows by `next_action`, adds the time-derived `FOLLOW_UP_HANDOVER` items, computes `priority`, `can_act`, and the `facts`); the `TransactionContextProvider` adapter in `adapters/context/` (only what Chunk 1 proved the public ports can supply; failure → `PARTIAL`/`UNAVAILABLE`, never an error); the four routes of C8, authorized with `PAYMENT_REVIEW`; the timeline assembler (read-time, from existing timestamps). Request/response models follow Module 18's recipe.

**Prohibition:** no raw provider payload, webhook body, checkout token or secret anywhere in any response; no write on any of these routes; no change to the existing payment routes.

**Tests you must write:** list filters, sorts and paging; `needs_action` hides settled rows; the detail contains every C8 section with the right data for a representative transaction in **each stage**; the timeline is ordered and uses only the listed kinds; `can_release` and `available_actions` differ correctly for `OPERATIONS` (cannot release) and `ADMIN`; **a failing context provider → `context_status: UNAVAILABLE` and a normal `200`**; `release.eligible_now` reflects the **live** evaluation even when the stored row is deliberately stale; a response scan proves no forbidden key (`raw`, `payload`, `signature`, `secret`, `token`) appears; unknown ids → `404`; a student or scout → `403`; the existing `GET /payments/{id}` response is byte-identical; every example parses against its model; `ListPaymentTasks` returns the right types, priorities and `can_act`, and a `FOLLOW_UP_HANDOVER` appears only after the threshold (injected clock).

**Acceptance criteria:** tests pass; the full Payment suite passes.

---

### CHUNK 11 — ADMIN TASKS
**[FOR YOU — GEMINI CLI]**

**Objective:** the to-do list. Read **C7**, ADR-260, 261 and Module 14 C9.

**Build:** `GetTasks`, the `TaskSource` port, the three adapters (`payment_task_source`, `issues_task_source`, `verification_task_source`), `GET /api/v1/admin/tasks` (`ADMIN_OVERVIEW_VIEW`), the overview `payments` extension (`release_due`, `handover_unconfirmed` beside `pending_disputes`), and the settings of C9. Reuse the overview's section runner so timeout and failure behave identically.

**Prohibition:** Admin stores nothing, caches nothing and reads no other module's tables; no proxy route; no new permission.

**Tests you must write:** each source independently `OK`, `NOT_AUTHORIZED` (a caller lacking that owner's permission) or `UNAVAILABLE` (an owner that raises or times out) **without affecting the others**; an `OPERATIONS` user sees payment tasks with `can_act: false` while an `ADMIN` sees `true` for release; ordering (`HIGH` first, then oldest); `task_id` is deterministic and stable across two calls; `source`, `type`, `priority` and `limit_per_source` filters and bounds (0 and 101 → validation error); the ISSUES source returns the caller's own and unassigned open issues only; the VERIFICATION source maps Verification's pending reviews; **no number is invented** — an owner outage never yields zeros; the overview's new counts equal Payment's summary; the import-linter contracts hold (Admin's `domain`/`application` import nothing from other modules).

**Acceptance criteria:** tests pass; the full Admin suite passes unchanged apart from the additions.

---

### CHUNK 12 — END-TO-END, CONCURRENCY AND SECURITY
**[FOR YOU — GEMINI CLI]**

**Objective:** prove the whole thing works together and cannot be bypassed. Run the **entire** suite first.

**Write `tests/e2e/test_release_governance.py` (real database, real outbox, the worker run with `--once` between steps, injected clock):**
1. **Manual path:** book → pay (mock controls) → scout offers → student accepts → the admin has **one open "release funds" notification** and the tasks list shows `RELEASE_DUE` with `can_act: true` → the admin releases → the notification resolves, the task disappears, the review is `RELEASED`, the ledger balances.
2. **Automatic path** (jobs enabled in the test settings): after acceptance, advance the clock through the three warning times → **three warning notifications**, then one automatic release; the decision row records the confirmation and `warnings_sent_count ≥ 3`; the admin gets "funds released automatically".
3. **Never confirmed:** offered but not accepted; advance 30 days → admin release refused, automatic release skipped, **nothing moves**; after the alert threshold a `FOLLOW_UP_HANDOVER` task appears.
4. **Dispute:** raised after the first warning → the release action resolves, warnings stop, no automatic release; resolved for release **with** confirmation → a new cycle, fresh warnings, `PaymentReleaseDue` again; resolved for release **without** confirmation → refused, only a refund is possible.
5. **Booking cancelled after payment:** stage `BOOKING_CLOSED_FUNDS_HELD`, a `DECIDE_REFUND` task, the release action resolved.
6. **No admin available:** with no active approver the warnings are not sent and the automatic release is blocked; adding an admin lets both proceed, and the notice period is still full.

**Concurrency tests** (each run several times): confirmation racing a dispute; two warning dispatchers; two automatic-release runs; manual and automatic release racing; reconcile racing a use case that updates the same review (version conflict is handled, nothing lost).

**Security tests:** a student and a scout get `403` on every review route and on tasks; `OPERATIONS` cannot release or refund; the tasks endpoint without a token → `401`; **captured logs contain no amount, name, dispute reason or provider payload** across all flows; a bypass attempt matrix (admin release, dispute release, direct decision insert, direct `ExecuteRelease`) all fail for an unconfirmed payment.

**Regression:** the complete suites of Booking, Payment, Notification, Admin, Platform Reliability, Security, Verification, Messaging, Identity and Housing.

**Acceptance criteria:** all pass; report the real counts.

---

### CHUNK 13 — DOCUMENTATION AND AI STATE
**[FOR YOU — GEMINI CLI]**

**Write:**
1. `docs/modules/payment_release_governance.md` — the rule in one paragraph; the four enforcement layers; the notice period and the worked timeline; the review table and stages; the tasks catalog; the settings; the jobs; and **"How to operate it"** (enable `payment_release_warnings` **and** `payment_auto_release` together; what each blocking reason means; what to do about each task type).
2. Update the Payment, Booking, Notification, Admin, Security and Platform module docs with a short "Release governance" note (what changed, what did not).
3. The **frontend documentation**: add **Part F** of this file, completing the behavior-change list with the real entries.
4. The **manual testing guide** from **Part G**, **running every scenario yourself** and replacing each expected output with the real response; mark anything you could not run **not verified** — never invent an output.
5. ADR rows **247–264** in the decision log.
6. **AI state:** module-complete status, the new tables, jobs and settings, the Known Limitations list (below), and the legacy-data findings from Chunk 1.

**Known limitations to state plainly:** warnings are in-app only and prove "durably sent", not "read"; no admin hold/postpone; a student who never confirms keeps the money held indefinitely (a task prompts a human); display names and titles are best-effort; Safety and platform items are not in the tasks list; legacy release decisions made before this amendment may lack a confirmation (reported, not altered); the review's money columns are a reconciled copy, repaired daily.

**Acceptance criteria:** every document exists; the manual guide contains only real outputs or "not verified"; the full suite passes.

---

### CHUNK 14 — FINAL AUDIT
**[FOR YOU — GEMINI CLI]**

1. Run the **entire** test suite, linters, type checker and `lint-imports`; paste the summary.
2. **Bypass audit:** for each of — `POST /payments/{id}/release` as `ADMIN`, the dispute resolve route, a direct `release_decisions` insert, and a direct `ExecuteRelease` call — on a payment **without** student confirmation, show the real refusal.
3. **Database audit:** show both constraints exist and are `NOT VALID` (`convalidated = false`), and show the two rejected inserts.
4. **Reference audit:** a repository-wide search finds **no** remaining use of `payment_release_fallback_hours` or production use of `automatic_48h_fallback`.
5. Confirm: `payment_auto_release` and `payment_release_warnings` are disabled by default; no new Security permission; every new system use case is unreachable by HTTP; no response contains a provider payload.
6. **Completion Report — three lists:** (a) **Verified** (command and output); (b) **Implemented but not verifiable in this environment** (and why); (c) **Not done** (and why). Do not blur them.

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

| What you asked for | Where it is built |
|---|---|
| **Release only after the student confirms an offer — enforced** | C3 (four layers) · Chunks 2–4, 7 · tested by bypass attempts in Chunks 7, 12, 14 |
| …and the loophole that made "confirmed" meaningless | Finding 2 · ADR-249 · Chunk 2 |
| …including a dispute resolved in the scout's favour | Finding 7 · ADR-263 · Chunk 7 |
| **Notify the admin at least three times before an automatic release** | C4 · ADR-251, 252 · Chunks 3, 4, 7 (code rule + database rule + dispatcher) |
| **Notify the admin when a release is due after a student confirmed** | C6 · ADR-254–256 · Chunks 6, 9 |
| **An admin "tasks" endpoint** | C7 · ADR-260, 261 · Chunk 11 |
| **A "transaction review" table with enough information for the frontend** | C5, C8 · ADR-257–259 · Chunks 4, 6, 10 |
| Not the ledger | C5 (separate table; the ledger is only *read* into the detail) |
| **Where it goes in the existing modules** | C12 touch map — Booking, Payment, Notification, Admin, Security (one use case), Platform (jobs) |
| **A new instruction file, not a new module** | this file |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

### What changed in behavior (check these)

| Where | Before | Now |
|---|---|---|
| `POST /api/v1/bookings/{id}/handover/accepted` | could succeed with no offer | **`409 handover_not_offered`** until the scout has offered; refused unless the booking is `CONFIRMED` |
| `POST /api/v1/bookings/{id}/handover/offered` | allowed on any non-closed booking | refused unless the booking is `CONFIRMED` |
| `POST /api/v1/payments/{id}/release` and the dispute **resolve** route | could succeed without the student's acceptance | refused with the existing release-not-eligible error and `blocking_reason: "student_confirmation_required"` — **for every role** |
| Automatic release | 48 h after the *offer* | only after the student **confirmed**, after a notice period, and only after **three warnings** |
| Notifications | none for admins | six staff notices and a new action, `RELEASE_FUNDS` |

### The release rule, in plain words (for tooltips)
Money is released only when **the scout offered the handover and the student confirmed they received it**. There is no override. The admin may release at any time after the confirmation. If the admin does nothing, an **automatic release** happens only after a notice period (default 48 hours after confirmation) **and** three warnings (default 24, 12 and 3 hours before) — and only if the platform's automatic release is switched on.

### `blocking_reason` — what each means (the release/evaluation answer)

| `blocking_reason` | Say this to the admin |
|---|---|
| `no_confirmed_payment` | No confirmed payment exists for this transaction |
| `booking_not_confirmed` | The booking is cancelled, expired or not confirmed |
| `handover_not_offered` | The scout has not offered the handover yet |
| `student_confirmation_required` | **The student has not confirmed the handover** — funds cannot be released |
| `dispute_open` | A dispute is open; resolve it first |
| `amount_exceeds_remaining_balance` | The amount is more than what is still held |
| `release_schedule_missing` | *(automatic only)* the notice period has not started |
| `auto_release_window_not_elapsed` | *(automatic only)* the notice period is still running |
| `release_warnings_pending` | *(automatic only)* the three warnings have not all been sent |
| `final_warning_too_recent` | *(automatic only)* the last warning was sent too recently |
| `no_release_approver_available` | *(automatic only)* no admin is available to receive the warnings |

### Notifications for admins
Same API as before (`GET /notifications`, `?action_required=true`, `unread-count`). New types, all category `PAYMENT`, target `{type: "BOOKING", id: <booking id>}`:

| `type` | Action | Meaning |
|---|---|---|
| `payment.release_due.staff` | **`RELEASE_FUNDS`** | A student confirmed — funds are ready to release. **Stays open until** the funds are released or refunded, a dispute is raised, or the booking closes (reading it does not close it) |
| `payment.auto_release_warning_first.staff` / `…_reminder.staff` / `…_final.staff` | — | Automatic release is approaching. These three arrive as **separate** notifications |
| `payment.dispute_raised.staff` | — | A dispute paused the release |
| `payment.funds_auto_released.staff` | — | Funds were released automatically |

**To open the transaction from a notification:** call `GET /api/v1/payments/review/transactions/by-booking/{booking_id}` with the notification's target id.
**Honest limit:** notifications are **in-app only** (polling); there is no email or push yet.

### `GET /api/v1/admin/tasks` — the admin's to-do list
Needs the overview permission (`OPERATIONS`, `ADMIN`). Query (all optional): `source` (repeatable: `PAYMENT`, `ISSUES`, `VERIFICATION`), `type`, `priority` (`NORMAL`/`HIGH`), `limit_per_source` (1–100, default 20).
The response is a list of **sections**, one per source, each with its own `status` (`OK`, `UNAVAILABLE`, `NOT_AUTHORIZED`) — **render each section on its own; one failing section must not blank the page.** Each item has a stable `task_id` (use it as the row key), a `type` code (**you** choose the wording), `priority`, `since`, `subject`, `target`, a small `facts` object, `required_permission` and **`can_act`** (disable the action button when false; show the task anyway).

| `type` | Show as | What the admin does |
|---|---|---|
| `RELEASE_DUE` | Funds ready to release | Review, then release (`POST /payments/{id}/release`). `facts` shows warnings sent vs required and, when known, the earliest automatic release |
| `RESOLVE_DISPUTE` | Dispute needs a decision | Resolve it (`POST /payments/disputes/{id}/resolve`) |
| `DECIDE_REFUND` | Paid booking was closed — funds held | Decide on a refund (`POST /payments/{id}/refund`) |
| `RECONCILE_OPERATION` | A money operation needs checking | Investigate (read-only for `OPERATIONS`) |
| `FOLLOW_UP_HANDOVER` | Student has not confirmed for a long time | Chase the student, or refund — funds **cannot** be released until the student confirms |
| `ISSUE_ASSIGNED_TO_ME` / `ISSUE_UNASSIGNED` | Operational issue | Open it in the issues screen |
| `REVIEW_PENDING` | Verification review waiting | Open the verification queue |

### The transaction review (Payment, needs `PAYMENT_REVIEW`)
- `GET /api/v1/payments/review/transactions` — list. Filters: `stage` (repeatable), `next_action`, `needs_action=true`, `booking_id`, `student_id`, `provider_id`, `paid_from`, `paid_to`; `sort` (`ACTION_SINCE_ASC`, `PAID_AT_DESC`, `PAID_AT_ASC`); `page`, `page_size`. Each row has `can_release` (enable the Release button).
- `GET /api/v1/payments/review/transactions/{payment_id}` and `/by-booking/{booking_id}` — the full detail.
- `GET /api/v1/payments/review/summary` — counts for dashboard tiles, plus `auto_release_enabled` (**do not promise an automatic release in the UI when this is false**).

| `stage` | Plain meaning | Typical `next_action` |
|---|---|---|
| `AWAITING_HANDOVER_OFFER` | Paid; the scout has not offered the handover | — |
| `AWAITING_STUDENT_CONFIRMATION` | Offered; waiting for the student | — (becomes `FOLLOW_UP_HANDOVER` after a long wait) |
| `RELEASE_DUE` | The student confirmed; funds can be released | `RELEASE_FUNDS` |
| `DISPUTED` | A dispute is open | `RESOLVE_DISPUTE` |
| `BOOKING_CLOSED_FUNDS_HELD` | The booking was cancelled/expired after payment; money is still held | `DECIDE_REFUND` |
| `RECONCILIATION_REQUIRED` | A money operation is in an uncertain state | `RECONCILE_OPERATION` |
| `RELEASED` / `REFUNDED` / `SETTLED_SPLIT` | Nothing is held any more | — |

**The detail screen should show, in order:** the header (`transaction`, `stage`, `next_action`) → the people and listing (`parties`, `listing` — **names and titles can be `null`; show the id and a "name unavailable" note, and watch `context_status`**) → the money (`funds`) → the handover (`booking.handover`) → **the release panel** (`release.eligible_now` and `blocking_reason`; the automatic-release countdown from `release.auto`, with the **three warnings** and which have been sent) → disputes → operations → the `timeline` → the `ledger` (as a secondary tab) → the buttons from `available_actions`. Amounts are in **kobo**; format them for display.

**Known limitations (tell your product people):** admin warnings are in-app only and show "sent", not "read"; the admin **cannot pause** an automatic release (only the student's dispute can); a student who never confirms leaves the money held until a human refunds it; names and titles are best-effort; the tasks list has no Safety or platform items yet; releases made before this change may lack a recorded confirmation (they are reported to the team, not altered).

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — Gemini turns this into the testing document in Chunk 13, running every step]

**Before you start:** run the API **and the worker** (`python scripts/run_platform_worker.py`). You need a **student** (Ada), a **scout** (Bola) with a listing, an **admin**, and an **operations** account. Book the listing as Ada and pay through the payment mock controls so the booking is `CONFIRMED` and a payment exists. For the time-based scenarios, the guide uses small SQL edits to move times back (local only); it also shows how to turn the jobs on.

**G1 — A student cannot confirm before an offer.** As Ada, `POST /bookings/{id}/handover/accepted` **before** Bola has offered.
*You should see:* `409` `handover_not_offered`; nothing changes.

**G2 — The admin is told.** As Bola, `POST …/handover/offered`; as Ada, `POST …/handover/accepted`. Wait ten seconds. As the admin, `GET /notifications?action_required=true`.
*You should see:* one open notification **"Action needed: release funds"**; Ada and Bola get no staff notice; the **operations** account gets none either.

**G3 — The admin's to-do list.** As the admin, `GET /admin/tasks`.
*You should see:* a `PAYMENT` section, `status: OK`, with a `RELEASE_DUE` item, `priority: NORMAL`, `can_act: true`, and the booking as its `target`. As **operations**, the same call shows the item with `can_act: false`.

**G4 — Open the transaction.** `GET /payments/review/transactions/by-booking/<booking id>`.
*You should see:* stage `RELEASE_DUE`, `release.eligible_now: true`, `warnings.required: 3`, `sent: 0`, the handover times, the funds (`remaining` equals the amount), and a timeline with payment, offer, acceptance and "release schedule opened".

**G5 — Release it.** `POST /payments/{id}/release` as the admin.
*You should see:* success. Then: the admin's "release funds" notification is **gone from the open list**; `GET /admin/tasks` no longer shows the item; the review shows stage `RELEASED` and a release decision that records the student's confirmation.

**G6 — The rule has no loopholes.** Make a second booking; as Bola **offer** but **do not** have the student accept. As the admin, try `POST /payments/{id}/release`.
*You should see:* refused with `blocking_reason: "student_confirmation_required"` — **even though you are an admin**. In the review, `release.eligible_now` is `false` with the same reason. Wait: nothing ever moves it.

**G7 — A dispute pauses everything.** On a confirmed, unreleased payment, as Ada `POST /payments/{id}/disputes`. Wait ten seconds.
*You should see:* the admin's "release funds" action **closes** and a "Payment dispute raised" notice arrives; the task becomes `RESOLVE_DISPUTE` (`HIGH`); the review stage is `DISPUTED`. Resolve it **for release** → accepted (Ada had confirmed) and a **new** notice period starts. On the unconfirmed booking of G6, a dispute resolved **for release** is refused; resolved **for refund** works.

**G8 — The three warnings and the automatic release.** In `.env` set `PLATFORM_JOBS_DISABLED=` (empty) and restart the worker. On a confirmed payment, look at `release.auto.warnings` — three items, none sent. Move time back (local only):
```sql
UPDATE release_schedules SET window_starts_at = window_starts_at - interval '47 hours';
UPDATE release_warnings SET due_at = due_at - interval '47 hours' WHERE sent_at IS NULL;
```
Run `python scripts/run_platform_worker.py --only payment_release_warnings --once`.
*You should see:* **one** warning (the worker sends at most one per run). As the admin: "Automatic release approaching". Move `sent_at` back an hour (`UPDATE release_warnings SET sent_at = sent_at - interval '2 hours' WHERE sent_at IS NOT NULL;`), run again → the second, then again → the third ("Final notice…"). Run `--only payment_auto_release --once` **before the third** → nothing is released (`release_warnings_pending`). After the third, shift `sent_at` back two hours and the window past 48 h, run it again → the funds are released **automatically**, and the admin gets "Funds released automatically". The decision shows `origin: AUTOMATIC`, the confirmation time and `warnings_sent_count: 3`.

**G9 — The database refuses it too.** In `psql`, try to insert a `RELEASE` row into `release_decisions` with `student_confirmed_at` empty.
*You should see:* the database rejects it (the constraint `ck_release_requires_student_confirmation`).

**G10 — A paid booking that was cancelled.** Cancel a paid, confirmed booking. Wait ten seconds. As the admin open the tasks.
*You should see:* a `DECIDE_REFUND` task and stage `BOOKING_CLOSED_FUNDS_HELD`; any open "release funds" notification for that booking is closed.

**G11 — The student who never confirms.** On the G6 booking, move the offer back: `UPDATE transaction_reviews SET handover_offered_at = handover_offered_at - interval '8 days' WHERE booking_id = '<id>';`
*You should see:* a `FOLLOW_UP_HANDOVER` task (the daily reconcile job would put the edited time back, so check it straight away). Its `facts` make clear nothing can be released until the student confirms.

**G12 — Existing payments get their review rows.** Run `python scripts/run_platform_worker.py --only payment_review_reconcile --once`.
*You should see:* a summary of rows created and repaired; every earlier payment now appears in `GET /payments/review/transactions`. A payment whose handover was already accepted shows an open "release funds" notification and a fresh notice period.

**G13 — Switches stay safe.** `python scripts/run_platform_worker.py --list` on a fresh `.env`.
*You should see:* `payment_auto_release` and `payment_release_warnings` **DISABLED**; `payment_review_reconcile` enabled.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] **A release is impossible without the student's confirmation** — admin release, automatic release and dispute-resolved release all refuse; the direct database insert is rejected (Chunks 4, 7, 14)
- [ ] **Acceptance requires a prior offer, and a `CONFIRMED` booking** (Chunk 2)
- [ ] **An automatic release is impossible without three recorded warnings**, in code and in the database, and a late job only delays it (Chunks 3, 4, 7)
- [ ] **The admin gets a "release funds" action the moment the student confirms**, and it closes when the money is released, refunded, disputed, or the booking closes (Chunks 6, 9, 12)
- [ ] **No active admin → warnings are not recorded and automatic release is blocked** (Chunks 7, 12)
- [ ] **`GET /api/v1/admin/tasks` works per source, independently, with `can_act`** (Chunk 11)
- [ ] **The transaction review exists for every confirmed payment, including existing ones**, and the detail returns everything the screen needs without raw provider data (Chunks 8, 10)
- [ ] **The ledger is untouched and the review is reconciled daily** (Chunk 8)
- [ ] **Both automatic jobs are disabled by default; no new Security permission** (Chunks 5, 8, 14)
- [ ] **No remaining use of the old 48-hour fallback** (Chunk 14)
- [ ] **The manual testing guide contains only real outputs or an explicit "not verified"** (Chunk 13)
- [ ] **Every new response and request follows the self-describing recipe** (Chunk 10)

---

*End of the amendment specification.*
