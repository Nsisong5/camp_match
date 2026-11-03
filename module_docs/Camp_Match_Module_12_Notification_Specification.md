# CAMP MATCH — MODULE 12: NOTIFICATION
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Notification Module handoff**

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** You do not copy chunks or parts. Gemini reads the complete document, then works through the chunks **in order, one at a time**. When a chunk is finished, Gemini stops and gives you a Completion Report; you check it and reply **"Proceed to Chunk N"** (or send corrections). Parts marked **[FOR NSISONG]** are for you — decisions, frontend documentation, the test-coverage matrix — and Gemini reads them only for context.

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

You are the implementation agent for this module. You have been given the **complete** specification in this one file.

1. **Read the entire file before doing anything.** Parts marked **[FOR NSISONG]** are for the human: read them for context and rationale, but they are not instructions to you. **The Design Specification (Part C) is the reference you must internalize fully** — every chunk points back to it ("Part C5", "ADR-133" and so on mean sections of this file). **Part D is your work**, in numbered chunks. **Part G (Manual Testing Guide)** at the end of this file is the source material for the manual-testing document you write in Chunk 13.
2. **Your first action is Chunk 1.** It is inspection and scaffolding and writes no behavior. Do not write any other code first.
3. **Work one chunk at a time, in order.** Do not start a chunk until Nsisong has replied "Proceed to Chunk N". Never combine, reorder, skip, or work ahead — not even small "preparatory" edits for a later chunk.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; every file created or changed; every command you ran with its **real** output; each acceptance criterion marked pass or fail; any deviation, surprise, or open question. Claim nothing you did not verify.
5. **If anything blocks you — a failing acceptance item, the repository contradicting this file, two parts of this file disagreeing, or a decision this file does not make — stop and report it.** Do not choose for yourself, skip a test, weaken a test, or work around it.
6. The Standing Instructions in `AI_instructions/` apply to everything. Change only the files a chunk names (plus anything that chunk's touch map allows). Do not modify other modules otherwise.

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

The handoff's default sequence has 16 chunks. This document has **14**, because three of its chunks (delivery infrastructure, optional push/email, real-time integration) have nothing to build in the MVP the evidence supports — see Findings 5 and 6. Two chunks the handoff did not list are added: small **event-contract amendments** to Booking and Verification (Chunks 7–8), which the handoff's own rules make unavoidable (Finding 1). The mapping is in Part E.

---

## PART A — FINDINGS [FOR NSISONG]

Notification turns events into user-facing notifications. The handoff's closing rule is the whole module in one line: *the owning module records the business fact; Notification communicates it without becoming responsible for it.* I can't read your code, only the 16 specifications behind it, so I checked this module's assumptions against them. Six real findings.

### FINDING 1 — only Messaging, Identity and Profile publish events. Booking, Payment, Verification and Housing publish none.

I checked every spec for published domain events. The complete list across the system:

| Module | Published events |
|---|---|
| Identity | `UserRegistered`, `AccountDisabled`, `AccountReactivated` |
| Profile | `ProfileCreated` |
| Messaging (Module 11) | `MessageCreated` (via its outbox) |
| Booking, Payment & Escrow, Verification, Housing, Search, Media/File, University | **none** |

`BookingConfirmed` appears in the Phase 1–3 spec only as an illustrative subclass example. The handoff says to integrate events "that exist or can be introduced through the owning module's approved public contract" and forbids reading other modules' tables. So Booking and Verification notifications are only possible if those modules **publish an event** — a small, reviewed amendment to each, the same shape as the Module 7 media amendment. I specify exactly that (Chunks 7–8). I do **not** touch Payment or Housing in this module (ADR-134).

### FINDING 2 — the event bus is in-process, per process, and lets a subscriber's exception escape

Phase 2's `InMemoryEventBus` delivers inside the publishing process, awaits each handler inline, and — as I recorded when specifying Messaging — a handler exception propagates out of `publish`. Three consequences drive this design:

1. **A subscriber is only reached in a process where it was registered.** Events are published from the API process *and* from scripts (`expire_booking_holds.py`, Messaging's outbox relay, Payment's recovery script). If Notification's subscriber is only registered in the API app, `BookingExpired` published by the expiry script reaches nobody. This is the open question Messaging's Chunk 14 left to this module. Answer: **one shared factory builds the bus and registers Notification's subscribers; every process that publishes must use it**, enforced by a test (ADR-140).
2. **A failing Notification handler could fail someone else's business operation** if the publisher doesn't guard. The rule is split cleanly: *publishers* call `publish` best-effort after commit and never let it change their result; *Notification* only raises when it could not durably record the event, which is exactly what Messaging's outbox needs to retry (ADR-132).
3. **An in-process bus can't survive a crash between the producer's commit and the publish.** See Finding 3.

### FINDING 3 — there is no shared outbox, so Notification needs its own durable point of receipt

Messaging has a module-private outbox. Nobody else does. The handoff says to reuse an existing mechanism and not to build a second one, and also forbids an in-memory queue as the only record of pending work. The honest reading: there is no shared mechanism to reuse, so Notification defines the contract it *can* guarantee, which is **"once my handler returns, the event is durable."** It does that with a small **inbox** table (event id as primary key): receive-and-record in one step, then process, with retries from the inbox if processing fails. That gives idempotency, restart recovery, and bounded retries entirely inside Notification (ADR-131, ADR-135).

What it cannot do, and this is a real limit I'm stating plainly: for **Booking and Verification**, an event is lost if the process dies in the instant between the business commit and the publish call. Messaging doesn't have this gap (its outbox re-publishes). The proper fix is a **shared transactional outbox** behind the existing `EventBus` port — a bigger, separate piece of infrastructure touching every producer. I recommend shipping this MVP without it and treating that as a named follow-up. **This is your first decision below.**

### FINDING 4 — Trust & Safety and Admin & Operations don't exist; Payment events don't either

The handoff lists Trust & Safety and Admin & Operations among modules to inspect and integrate. Neither has been specified or built. There is no integration to write and I invent none (no speculative `SafetyActionNotificationRequested`). Payment & Escrow publishes nothing, and a payment notification would carry the most sensitive content in the system for the least added value: `BookingConfirmed` already tells the student their payment worked, without exposing any financial detail. Payment events are deferred (ADR-134).

### FINDING 5 — no external delivery channel is approved or possible, so there is nothing to retry externally

Push needs a provider, credentials, device-token lifecycle and a mobile client that registers tokens. Email needs a provider and verified-email infrastructure (Identity's ADR-018 explicitly deferred email verification). None is in the repository or approved. The handoff says "prefer a small, reliable in-app system" and "implement only channels confirmed to be in scope." **In-app only.** That means no delivery-attempt tables, no fake provider adapters, no provider-timeout handling — building them with no channel would be exactly the speculative infrastructure the handoff warns against. The retry and bounded-attempt machinery the handoff cares about still exists and is fully tested — applied to the part that is real: **event processing** (ADR-130, ADR-135). Preferences are deferred for the same reason: with a single in-app channel, there is nothing for a user to opt out *of*.

### FINDING 6 — there is no real-time notification channel to reuse

Messaging's WebSocket delivers `message.created` only for conversations a connection has subscribed to; it has no user-level notification frame, and the handoff forbids a second socket subsystem. Per its own fallback: the durable API is the MVP mechanism, and the frontend polls a cheap `GET /notifications/unread-count` (ADR-139).

**No contradictions with Modules 1–11 otherwise.** Chunk 1 verifies everything here against the actual repository, including whether Messaging was built as specified; any difference is reported before anything is built.

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-129 … ADR-143)
Continuing the log from Messaging (112–128).

| ADR | Decision | Why |
|---|---|---|
| 129 | Notification is Module 12. REST lives at `/api/v1/notifications` | Matches the flat per-module route style (`/api/v1/bookings`, `/api/v1/payments`). |
| 130 | **MVP scope: in-app notifications only.** Push, email, preferences, device registration, delivery-attempt records and provider adapters are **deferred**. The extension path is documented: add a delivery-attempt table and a `DeliveryChannel` port alongside the existing pipeline | Finding 5. No approved channel exists to build against. |
| 131 | **Notification owns a durable event inbox** (`notification_inbox`, event id as primary key). Contract: *when Notification's handler returns normally, the event is durable and will be processed exactly once in effect.* Receipt failure raises (so Messaging's outbox retries); processing failure never raises (the inbox retries) | Finding 3. This is the strongest guarantee Notification can honestly make without a shared outbox. |
| 132 | **Who guards what.** Publishers (Booking, Verification) call `publish` **after commit, wrapped best-effort**: any exception is logged at WARNING and never changes their result. Messaging already behaves this way. Notification's handler raises only if it failed to durably record the event | Finding 2. Business operations must never fail because of a notification. |
| 133 | **Event contracts are the producer's public contract, and only Notification's adapter layer touches them.** Each producer defines its events in its own `domain/events.py` and exposes them through `application/ports/events.py`. Notification's **`adapters/events/`** is the only code that imports them; it converts each event to a plain payload dictionary, and Notification's `domain` and `application` layers import **nothing** from any other module. Events carry **facts and ids** (and `recipient_id` for Messaging, as already specified). Where a recipient must be resolved — a booking's provider, a verified property's owner — **Notification resolves it** through its own `PropertyOwnerProvider` port (Housing's public contract) during processing, so a lookup failure becomes an inbox retry, not a lost event or a new failure mode in the producer | Ports and adapters applied to events: the consumer defines what it needs and an adapter translates. It also keeps the producer amendments tiny. |
| 134 | **Supported events (MVP), nothing else:** `MessageCreated`; `BookingCreated`, `BookingConfirmed`, `BookingCancelled`, `BookingExpired` (new, Booking amendment); `VerificationDecisionRecorded` (new, Verification amendment). **Deliberately not supported:** Payment/escrow events (Finding 4), Housing listing events (no recipient who needs them), Identity events (`AccountDisabled` reaches a user who can no longer log in), anything Trust & Safety | Handoff §4 and §21: no fabricated events, no notifying about everything. |
| 135 | **Processing = exactly-once effect.** `PENDING → PROCESSED` is a conditional status flip in the **same transaction** as the notification writes, guarded by a row lock, so two workers or a duplicate delivery cannot both produce effects. Failures: bounded attempts with exponential backoff (`next_attempt_at`); after the limit the row is `DEAD` (terminal, loud log, operator can requeue); an unparseable payload is `REJECTED` immediately and never retried | Handoff §7 and §9, applied to the part of the system that exists. |
| 136 | **Message notifications collapse.** At most one **unread** `MESSAGE` notification per `(recipient, conversation)`: a new message increments `event_count` and moves it to the top; once the user reads it, the next message starts a new one. Enforced by a **partial unique index** and an atomic `INSERT … ON CONFLICT … DO UPDATE` | A 50-message conversation producing 50 notifications is a defect, not a feature. Atomic upsert means a concurrent mark-as-read simply causes a fresh row — no lost update. |
| 137 | **Read model:** nullable `read_at`; "unread" is `read_at IS NULL`. Mark-read is a conditional `UPDATE … WHERE id = :id AND recipient_id = :me AND read_at IS NULL`; zero rows means "already read" (idempotent success, timestamp untouched) or "not yours/missing" (`404`). Read-all is one bulk conditional update. **No Security permission** is needed (structurally self-scoped, like every `/me`-style route), and no account-status check (reading your own notifications grants nothing) | Handoff §6.1/§11. A non-owner gets `404 notification_not_found`, same as an unknown id — the Messaging ADR-125 stance. |
| 138 | **Content is fixed templates keyed by notification type.** Never a message body, a person's name, an amount, a verification reason, or a safety detail. Navigation targets are structured references (`{type, id}`), **never URLs** | Handoff §11. |
| 139 | **No real-time channel.** The frontend polls `GET /notifications/unread-count`. Reusing Messaging's socket for user-level frames is a possible later amendment, not part of this module | Finding 6. |
| 140 | **One event-bus factory.** A single `build_event_bus(...)` creates the bus and registers Notification's subscribers. Every composition root that publishes (API app, `expire_booking_holds.py`, Messaging's relay, `scripts/run_payment_recovery.py` — Chunk 1 finds any others) uses it. A guard test fails if any other code constructs `InMemoryEventBus` | Finding 2.1. The failure it prevents is silent. |
| 141 | **Worker = `scripts/run_notification_worker.py`**, once per invocation (no daemon, no scheduler, same stance as every earlier script). Flags: default (process due inbox rows), `--stats`, `--requeue-dead` | The operator recovery path the handoff asks for, using the project's established pattern. |
| 143 | **Producers integrate only through the existing `EventBus` port.** Booking and Verification each gain one constructor parameter, `event_bus: EventBus` — the shared-kernel port, **reused directly**, exactly as Identity does (the project rule is that shared-kernel ports are not redefined per module). They publish from their **application layer only** — never from entities, repositories, routers or adapters — **after commit**, through one shared helper, `publish_best_effort`. They never import, name, or know about Notification | A booking's or verification's business logic and tests stay about bookings and verifications; a notification is a consumer concern. |
| 142 | **No retention/purge in the MVP.** No retention policy exists anywhere in the project; the indexes and `read_at` permit a later purge. Stated as a limitation, not decided silently | Handoff §11.10 says follow existing policy; there is none. |

### Status of the three decisions

1. **Reliability tier (Finding 3) — still open; this specification proceeds on the default.** Booking and Verification notifications are *at-most-once* across a crash in the instant between the business commit and the publish; Messaging's are durable. If you later want that closed, a shared transactional outbox is a separate amendment: it would replace the bus adapter behind the existing `EventBus` port (ADR-143), and each producer's publish call would move inside its transaction — a one-line move per use case that amendment would specify. Nothing in Notification's own design changes.
2. **Touching Booking and Verification — approved by Nsisong.** Specified in full in **C12** and Chunks 7–8, within the rules of ADR-143.
3. **In-app only, and collapsed message notifications — confirmed by Nsisong.** Collapsing is ADR-136: **forty messages in a conversation are one notification with a counter**, not forty.

---

## PART C — DESIGN SPECIFICATION
**[FOR YOU — GEMINI CLI — the design: internalize it fully before starting Chunk 1.]**

Where a chunk and this part appear to disagree, **stop and report** instead of choosing.

### C1. Non-negotiable rules specific to this module
1. **Notification never causes a producer's business operation to fail or change.** It never writes to, or reads the tables of, any other module. It touches other modules only through the public contracts named in this part.
2. **Notification never lets an exception from *processing* reach a publisher.** It raises only when **receipt** (the durable inbox insert) fails.
3. **Every event is processed with its own fresh, short-lived session/UoW**, never the publisher's session (the publisher's request is still in flight when an inline handler runs).
4. **Never log notification content, titles, or bodies, or full event payloads.** Log ids, event type, counts, outcome, attempt number, and a short error *class name*.
5. **Never take a recipient, content, or event type from a client.** There is no endpoint that creates a notification.
6. **Import direction:** Notification's `domain` and `application` layers import **nothing** from any other module. Only its `adapters/` do — each producer's `application/ports/events.py` (in `adapters/events/` only) and Housing's public ports (in `adapters/housing/` only). **No producer — Booking, Verification, Messaging, or anyone — may ever import Notification.** Both rules are enforced by import-linter.

### C2. Module layout
```
src/camp_match/modules/notification/
├── domain/        value_objects.py  entities.py  templates.py  inbox.py
├── application/
│   ├── errors.py
│   ├── ports/     inbound.py  outbound.py
│   ├── parsing/   event_parsers.py              # strict per-event payload parsing
│   ├── policies/  recipient_policies.py         # event -> drafts
│   └── use_cases/ list_notifications.py  get_unread_count.py  mark_notification_read.py
│                  mark_all_read.py  receive_event.py  process_inbox_event.py
│                  process_pending_inbox.py  requeue_dead_events.py  get_inbox_stats.py
└── adapters/
    ├── persistence/  models.py  notification_repository.py  inbox_repository.py
    ├── housing/      property_owner_provider.py
    ├── events/       subscribers.py  registration.py
    └── api/          schemas.py  router.py  dependencies.py
scripts/run_notification_worker.py
```
Plus, outside this module: the single bus factory (Chunk 10; location per Chunk 1's finding), `application/ports/events.py` in Messaging, Booking, Verification (Chunks 7–8), and Booking's and Verification's own `domain/events.py` additions.

### C3. Domain model

**Enums.** `NotificationCategory`: `MESSAGE`, `BOOKING`, `VERIFICATION`. `TargetType`: `CONVERSATION`, `BOOKING`, `VERIFICATION_CASE`. `InboxStatus`: `PENDING`, `PROCESSED`, `REJECTED`, `DEAD`.

**`NotificationType`** (enum; each member knows its category and whether it is *collapsible*): `MESSAGE_NEW` (`message.new`, collapsible), `BOOKING_CREATED_PROVIDER`, `BOOKING_CONFIRMED_STUDENT`, `BOOKING_CONFIRMED_PROVIDER`, `BOOKING_CANCELLED_STUDENT`, `BOOKING_CANCELLED_PROVIDER`, `BOOKING_EXPIRED_STUDENT`, `VERIFICATION_VERIFIED`, `VERIFICATION_REJECTED`, `VERIFICATION_REVOKED` — dotted string values like `booking.confirmed.student`. Type is chosen by *recipient perspective* so each template is a fixed string with no conditionals.

**`NotificationTarget`** — value object `(type: TargetType, id: EntityId)`. There is no URL field anywhere.

**`Notification`** (entity) — `id`, `recipient_id`, `type`, `category` (must equal `type.category`, else `ValueError`), `title`, `body`, `target` (optional), `group_key` (optional; only for collapsible types), `event_count` (int ≥ 1, default 1), `source_event_id`, `created_at`, `latest_event_at`, `read_at` (optional). Methods: `mark_read(now) -> bool` — sets `read_at` and returns `True` only if it was unread; calling again returns `False` and **leaves `read_at` unchanged**. `is_read`. Title ≤ 100 chars, body ≤ 300, both non-empty.

**`NotificationDraft`** — value object produced by policy: `recipient_id`, `type`, `target`, `group_key`. Title and body are looked up from templates, never carried.

**`templates.py`** — one pure function `render(type) -> (title, body)` over this fixed table (the **only** place notification prose exists; no event field ever flows into it):

| Type | Title | Body |
|---|---|---|
| `message.new` | New message | You have a new message. |
| `booking.created.provider` | New booking | A student has reserved one of your listings. Payment is pending. |
| `booking.confirmed.student` | Booking confirmed | Your booking has been confirmed. |
| `booking.confirmed.provider` | Booking confirmed | A booking on one of your listings has been confirmed. |
| `booking.cancelled.student` | Booking cancelled | Your booking was cancelled. |
| `booking.cancelled.provider` | Booking cancelled | A booking on one of your listings was cancelled. |
| `booking.expired.student` | Booking expired | Your booking hold expired because payment wasn't completed. |
| `verification.verified` | Verification approved | Your verification was approved. |
| `verification.rejected` | Verification not approved | Your verification was not approved. Open the case for details. |
| `verification.revoked` | Verification revoked | Your verification was revoked. Open the case for details. |

**`inbox.py`** — pure functions: `next_delay_seconds(attempts, base, cap) -> int` = `min(cap, base * 2 ** (attempts - 1))` (attempts ≥ 1); `is_terminal(status)`.

**Tests (Chunk 2):** every invariant individually — category/type mismatch raises; empty or over-length title/body raise; `group_key` on a non-collapsible type raises; `mark_read` first call true, second call false and `read_at` identical; `event_count` < 1 raises; every `NotificationType` has a template and a category; no template string contains a format placeholder or a name/amount/URL; backoff doubles, never exceeds the cap, rejects attempts < 1.

### C4. Database (all tables prefixed `notification_`; no foreign keys into any other module)

**`notification_notifications`**
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `recipient_id` | UUID | not null; identity reference, no FK |
| `type` | text | `CHECK` against the ten type values |
| `category` | text | `CHECK IN ('MESSAGE','BOOKING','VERIFICATION')` |
| `title`, `body` | text | not null |
| `target_type` | text | nullable; `CHECK` against `TargetType` |
| `target_id` | UUID | nullable; `CHECK` that both target columns are null or both non-null |
| `group_key` | text | nullable |
| `event_count` | integer | not null, default 1, `CHECK >= 1` |
| `source_event_id` | UUID | not null — the event that **created** the row |
| `created_at` | timestamptz | not null |
| `latest_event_at` | timestamptz | not null — list ordering key |
| `read_at` | timestamptz | nullable |
Indexes/constraints: **unique `(source_event_id, recipient_id)`** (defense in depth against duplicate creation); **partial unique `(recipient_id, group_key) WHERE group_key IS NOT NULL AND read_at IS NULL`** (the collapse guarantee, ADR-136); **list index `(recipient_id, latest_event_at DESC, id DESC)`**; **partial index `(recipient_id) WHERE read_at IS NULL`** (unread counts).

**`notification_inbox`**
| Column | Type | Notes |
|---|---|---|
| `event_id` | UUID | **PK** — the producer's `event_id`; this *is* the idempotency key |
| `event_type` | text | not null |
| `payload` | jsonb | not null — ids and enums only; never content |
| `received_at` | timestamptz | not null |
| `status` | text | `CHECK IN ('PENDING','PROCESSED','REJECTED','DEAD')`, default `PENDING` |
| `attempts` | integer | not null, default 0 |
| `next_attempt_at` | timestamptz | not null; set to `received_at` on insert |
| `last_error` | text | nullable — **error class name or short code only** |
| `processed_at` | timestamptz | nullable |
Partial index on `(next_attempt_at) WHERE status = 'PENDING'`.

One migration, **read before applying**.

### C5. Event contracts and recipient policies (ADR-133/134)

Each event is a frozen dataclass extending the shared-kernel `DomainEvent` (which supplies `event_id` and `occurred_at`). The fields below are the **contract**; Chunks 7–8 define the new ones, Notification's parsers (`event_parsers.py`) validate each strictly (missing field, wrong type, malformed id, unknown enum value → the event is `REJECTED`, never guessed at).

| Event | Fields (public contract) | Producer |
|---|---|---|
| `MessageCreated` | `message_id`, `conversation_id`, `sender_id`, `recipient_id`, `sequence`, `context_type`, `message_created_at` (already specified in Module 11) | Messaging |
| `BookingCreated` | `booking_id`, `student_id`, `property_id`, `listing_id` | Booking (Chunk 7) |
| `BookingConfirmed` | same four | Booking |
| `BookingCancelled` | same four + `cancelled_by` (identity id) | Booking |
| `BookingExpired` | same four | Booking |
| `VerificationDecisionRecorded` | `case_id`, `target_type` (`PROVIDER`/`PROPERTY`), `target_id`, `decision` (`VERIFIED`/`REJECTED`/`REVOKED`) | Verification (Chunk 8) |

No event carries a price, amount, cancellation reason, evidence, rejection reason, message body or any name.

**Recipient policy** (`recipient_policies.py`, application layer; input is the parsed event, output is a list of `NotificationDraft`):

| Event | Recipient(s) → type; target; group key |
|---|---|
| `MessageCreated` | `recipient_id` → `message.new`; `CONVERSATION:conversation_id`; group `message:{conversation_id}`. **Never the sender** |
| `BookingCreated` | provider → `booking.created.provider`; `BOOKING:booking_id` |
| `BookingConfirmed` | student → `booking.confirmed.student`; provider → `booking.confirmed.provider` |
| `BookingCancelled` | every party **except** `cancelled_by`: student → `booking.cancelled.student`, provider → `booking.cancelled.provider`. If `cancelled_by` is neither party (an administrator), **both** are notified |
| `BookingExpired` | student → `booking.expired.student` (the provider is deliberately not notified) |
| `VerificationDecisionRecorded` | the case's owner → `verification.verified` / `.rejected` / `.revoked` by `decision`; `VERIFICATION_CASE:case_id`. Owner: `PROVIDER` → `target_id` (you verify yourself); `PROPERTY` → `PropertyOwnerProvider.get_owner(target_id)`. **Never the reviewing account** |

"Provider" (a booking's) and "owner" (a verified property's) are both resolved by `PropertyOwnerProvider.get_owner(property_id)`. Outcomes: found → proceed; **`None` (property not found) → the drafts that need that person are skipped, and the event is marked `PROCESSED` with a WARNING `notification_no_recipient`** — never a guessed recipient; a transient failure (anything raised) → inbox retry. If a policy yields zero drafts, the event is still marked `PROCESSED`. The event carries no recipient for Booking or Verification **on purpose**: the producer states what happened; Notification decides who needs to know.

### C6. Ports

**Inbound** (`Protocol` + `execute`, `@dataclass` request/response): `ListNotifications`, `GetUnreadCount`, `MarkNotificationRead`, `MarkAllRead`, `ReceiveEvent`, `ProcessInboxEvent`, `ProcessPendingInbox`, `RequeueDeadEvents`, `GetInboxStats`.

**Outbound:**
- **`NotificationRepository`** — `create_or_collapse(notification) -> CreateOutcome` (`CREATED` / `COLLAPSED`; one atomic statement for collapsible types: `INSERT … ON CONFLICT (recipient_id, group_key) WHERE group_key IS NOT NULL AND read_at IS NULL DO UPDATE SET event_count = event_count + 1, latest_event_at = GREATEST(latest_event_at, EXCLUDED.latest_event_at)`; plain insert otherwise), `list_for_recipient(recipient_id, unread_only, category, page_request) -> Page`, `count_unread(recipient_id)`, `mark_read(notification_id, recipient_id, now) -> bool` (conditional update; `True` iff changed), `exists_for_recipient(notification_id, recipient_id) -> bool`, `mark_all_read(recipient_id, category | None, now) -> int`.
- **`InboxRepository`** — `add(event_id, event_type, payload, now) -> bool` (`INSERT … ON CONFLICT (event_id) DO NOTHING`; `True` iff inserted), `claim(event_id) -> InboxRow | None` (`SELECT … WHERE event_id = :id AND status = 'PENDING' FOR UPDATE SKIP LOCKED`; must run inside a transaction), `mark_processed(event_id, now)`, `mark_rejected(event_id, code, now)`, `record_failure(event_id, error_class, next_attempt_at, dead: bool)`, `list_due(now, limit) -> list[event_id]` (no lock), `requeue_dead() -> int`, `stats() -> dict[status, int]`.
- **`PropertyOwnerProvider`** — `get_owner(property_id) -> EntityId | None`; adapter calls Housing's `GetProperty` and maps `provider_id`; not-found → `None`; anything else propagates. Used for booking providers and for `PROPERTY` verification owners.
- Reused: shared-kernel `Clock`, `EntityId`, `Page`/`PageRequest`, `UnitOfWork`, `EventBus`.

### C7. Use cases

**`ReceiveEvent(event_id, event_type, payload)`** (plain values — the adapter has already converted the event) — the subscriber's step 1, **own session/UoW**: `InboxRepository.add` → commit. Returns `inserted: bool`. **A failure here propagates** (this is the one place Notification raises). Log INFO `notification_event_received` or `notification_event_duplicate`.

**`ProcessInboxEvent(event_id)`**:
1. In a UoW: `claim(event_id)`; `None` → return `SKIPPED` (already processed, rejected, dead, or claimed by another worker).
2. Parse the payload with the strict parser for `event_type`; failure → `mark_rejected('invalid_payload')`, commit, log WARNING `notification_event_rejected`, return `REJECTED`. (An `event_type` with no registered parser is the same.)
3. Run the recipient policy (calls `PropertyOwnerProvider` where needed), render templates, build `Notification`s (`created_at`/`latest_event_at` from `Clock`, `source_event_id` = the event id).
4. `create_or_collapse` each draft; `mark_processed`; **commit — the writes and the status flip are one transaction.** Log INFO `notification_created` / `notification_collapsed` (counts, type keys, never content).
5. **Any exception in steps 2–4:** roll back, then in a **new** transaction `record_failure` with `attempts + 1`; if that reaches `notification_inbox_max_attempts` → status `DEAD`, ERROR log `notification_event_dead`; otherwise `next_attempt_at = now + next_delay_seconds(...)`, WARNING log `notification_processing_failed` (event id, type, attempt, error class name). **Return `FAILED`; never raise.**
Inline processing from the subscriber ignores `next_attempt_at`; the worker honors it.

**`ProcessPendingInbox(limit)`** — `list_due(now, limit)`, then `ProcessInboxEvent` **once per id, each in its own transaction**, so one failing row cannot affect the others. Returns counts per outcome.

**`ListNotifications`** — `actor_id` from auth only; filters `unread_only`, `category`; shared `PageRequest` (the project's existing bounds); ordered `latest_event_at DESC, id DESC`. **`GetUnreadCount`** — `count_unread`, same definition as the list's unread filter. **`MarkNotificationRead`** — `mark_read`; if `False`, `exists_for_recipient`: yes → idempotent success returning the current notification, no → `NotificationNotFound` (404, identical for another user's id and an unknown id). **`MarkAllRead`** — `mark_all_read`, returns the count. **`RequeueDeadEvents`**, **`GetInboxStats`** — thin wrappers for the worker script.

### C8. Subscriber behavior (`adapters/events/subscribers.py`, `registration.py`)

`register_notification_subscribers(event_bus, session_factory, clock, settings)` subscribes one handler per supported event type (the six in C5). Each handler first converts the event with `event_to_payload(event)` (in the same adapter file: dataclass fields only; ids → strings, enums → their values, datetimes → ISO-8601; `event_id` and `occurred_at` passed separately) — because **Notification's application layer never sees a producer's classes**. Then:
1. `ReceiveEvent` — **no try/except**: failure propagates (Messaging's outbox relies on that).
2. If `inserted`: `ProcessInboxEvent`, wrapped in `try/except Exception` that logs WARNING and returns — processing is already protected inside the use case, this is the outer belt.
A duplicate (`inserted = False`) returns immediately. **The handler returning means the event is durable.**

### C9. Errors (each extends a shared-kernel category and carries a `code`)
`NotificationNotFound` (`NotFoundError`, `notification_not_found`). That is the only user-facing application error; invalid filter values are rejected as ordinary `422`s by the schemas. Event-processing outcomes are return values and log lines, not exceptions.

### C10. Settings (`config/settings.py`, `.env.example`)
| Setting | Default |
|---|---|
| `notification_inbox_max_attempts` | 8 |
| `notification_inbox_backoff_base_seconds` | 30 |
| `notification_inbox_backoff_cap_seconds` | 3600 |
| `notification_worker_batch_size` | 100 |
| `notification_debug_fail_processing` | `False` — honored **only** when `app_env` is `local` or `test` (Chunk 10); makes `ProcessInboxEvent` raise inside its protected step so the failure path can be demonstrated |

### C11. Touch map — the **only** files outside `modules/notification/` this module changes
| File | Change | Chunk |
|---|---|---|
| `shared_kernel/application/` | one small helper `publish_best_effort(event_bus, event, logger)` — catches everything, logs WARNING with the event type and id only | 7 |
| `modules/messaging/application/ports/events.py` | **new**: re-export `MessageCreated` | 7 |
| Booking: `domain/events.py`, `application/ports/events.py`, the four use cases, their composition | four new events; best-effort post-commit publish; `event_bus` constructor parameter (**C12**) | 7 |
| Payment's composition only: where it constructs Booking's `ConfirmBooking` (its Booking adapter wiring and `scripts/run_payment_recovery.py`) | pass the bus; **no Payment logic changes** | 7, 10 |
| Verification: `domain/events.py`, `application/ports/events.py`, `ApproveVerification`, `RejectVerification`, `RevokeVerification`, their composition | one new event; best-effort post-commit publish; `event_bus` constructor parameter (**C12**) | 8 |
| bus factory + `app.py` + `scripts/expire_booking_holds.py` + `scripts/run_messaging_outbox_relay.py` + `scripts/run_payment_recovery.py` + any other composition root found in Chunk 1 | use the single factory | 10 |
| `config/settings.py`, `.env.example` | C10 | 3 |
| `pyproject.toml` | import-linter contracts | 12 |

**Not touched:** Identity, Profile, Security, University, Housing, Search, Media/File, and Payment & Escrow's logic. After every chunk that touches another module, re-run that module's suite and confirm it is unchanged apart from the documented fake-bus additions and new assertions.

### C12. How Booking and Verification integrate — the rulebook for Chunks 7 and 8

**The shape (ports and adapters, applied to events).** A producer's use case does its business work, commits, then tells the world what happened through the **`EventBus` port**. It does not know who listens. Notification's *adapter* subscribes, translates the event into plain data, and hands it to Notification's own use cases. Nothing flows the other way.

**What Booking and Verification must do**
1. Define their events as frozen dataclasses in their own `domain/events.py`, extending shared-kernel `DomainEvent`, with `occurred_at` from the injected `Clock` (as Identity's events do). **Ids and enums only** — no price, no reason, no free text, no names.
2. Re-export them from `application/ports/events.py` — their public event contract.
3. Take `event_bus: EventBus` (the shared-kernel port, **not** a new Booking-specific or Verification-specific port — shared-kernel ports are not redefined) as a constructor parameter on the use cases below, and publish with `publish_best_effort` **after commit**.
4. Publish **from the use case only** — never from an entity, repository, router, or adapter.

**What they must never do:** import, mention, or depend on Notification; let a publish failure change a result, an error, a log level, or a database write; publish before commit; publish on a no-op, a replay, or a refused operation; put anything in an event they would not be comfortable seeing in a log.

**Booking** — events `BookingCreated`, `BookingConfirmed`, `BookingExpired` (`booking_id`, `student_id`, `property_id`, `listing_id`) and `BookingCancelled` (the same four plus `cancelled_by`, the caller's identity id):

| Use case | Publishes | Exactly when | Never when |
|---|---|---|---|
| `CreateBooking` | `BookingCreated` | at the success step (step 9), after the booking is persisted **and committed** | the idempotent-replay return (step 1); any rejection in steps 2–6; a failed `add` including the compensating-release path (step 8) |
| `ConfirmBooking` | `BookingConfirmed` | after the conditional confirm matched a row and committed | the hold-expired rejection; a zero-row match (someone else already moved it); an authorization failure |
| `CancelBooking` | `BookingCancelled`, `cancelled_by` = the caller | only when the conditional cancel **actually transitioned** the booking | the idempotent no-op branch (an already-cancelled booking is a success that changes nothing — it must neither release inventory nor publish) |
| `ExpireHolds` | `BookingExpired`, once per booking | per booking, after *that booking's* transition succeeded and committed | a `release_slot` failure for that booking; a zero-row match (already terminal) |

`ConfirmBooking` is called by Payment from two processes — the API (webhook) and `scripts/run_payment_recovery.py` — and `ExpireHolds` runs in `scripts/expire_booking_holds.py`. Every one of those composition roots must construct the use case with a real bus (Chunk 7 passes the existing one; Chunk 10 swaps in the shared factory).

**Verification** — one event, `VerificationDecisionRecorded(case_id, target_type, target_id, decision)`. **No reason, no decider identity, no expiry, no evidence, no owner field.** (Who to notify is Notification's job — C5.)

| Use case | Publishes | Exactly when | Never when |
|---|---|---|---|
| `ApproveVerification` | `decision = VERIFIED` | after the concurrency-safe write matched (`WHERE status = 'DECISION_PENDING'`) and committed | `UnauthorizedVerificationAction` (decider is the inspector), `EvidenceRequirementNotSatisfied`, a missing reason, a zero-row match (`DecisionNotAllowed`) |
| `RejectVerification` | `decision = REJECTED` | same conditional write matched and committed | a missing reason, a zero-row match, any refusal |
| `RevokeVerification` | `decision = REVOKED` | after the `VERIFIED → REVOKED` transition committed | a case that isn't `VERIFIED` (`InvalidVerificationTransition`), a missing reason |

Not decisions, so **never published**: `CreateVerificationCase`, `SubmitVerificationCase`, evidence and inspection steps, assignments, cancellation of a case.

**The consumer side (Chunks 9–10)** converts these to payloads in `adapters/events/`, parses them strictly, resolves recipients with `PropertyOwnerProvider`, and renders fixed templates. A producer never learns any of that happened.

---

## PART D — CHUNKED IMPLEMENTATION

**Work one chunk at a time, in order, and stop after each Completion Report** (see the Operating Instructions at the top). Each chunk lists only what is specific to it; Part C is the design, and **C12 is the rulebook for the Booking and Verification chunks**. Use the standard `CURRENT_TASK.md` status-block format. **A failed acceptance item means stop and report — never skip, weaken, or work around a test.**

---

### CHUNK 1 — REPOSITORY INSPECTION, ARCHITECTURE MAPPING & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** confirm this specification's assumptions against the real repository and create the empty module. No behavior.

1. Read `AI_instructions/`, all `AI_state/` files, and `docs/modules/` for messaging, booking, verification, payment, housing.
2. **Confirm Messaging (Module 11) is built as specified:** `MessageCreated` exists with the fields in Part C5; `messaging_outbox` exists; `DispatchOutboxEvents` publishes to the shared `EventBus`; `scripts/run_messaging_outbox_relay.py` exists. **Report any difference — it changes this plan.** If Messaging is not built, stop and report.
3. Inspect the event system: the `EventBus` port's exact subscribe/publish API and how a subscriber is registered by event type; the exact behavior of `InMemoryEventBus` when a handler raises; **every place `InMemoryEventBus` (or any `EventBus`) is constructed** — `app.py`, every script in `scripts/` (at least `expire_booking_holds.py`, `run_messaging_outbox_relay.py`, `run_payment_recovery.py`), Payment's wiring of Booking's `ConfirmBooking`, and tests. List them all; this is the composition-root inventory Chunk 10 depends on.
4. **For each producer, find the exact commit boundary.** For Booking's `CreateBooking`, `ConfirmBooking`, `CancelBooking`, `ExpireHolds`, and for every Verification use case that moves a case to `VERIFIED`, `REJECTED`, or `REVOKED`: where does the transaction commit — inside the use case (via `UnitOfWork`), or when the request-scoped session closes *after* the use case returns? **Part C1 and ADR-132 require publishing only after commit.** If a use case cannot commit before publishing without restructuring, **stop and report which one and why.** Also record: how Identity (`UserRegistered`) publishes today, for comparison.
5. **Booking:** for `CreateBooking`, `ConfirmBooking`, `CancelBooking`, `ExpireHolds` confirm the step numbers and branches that Part C12's table refers to (idempotent-replay return, compensating release, conditional confirm/cancel, per-booking transition in expiry), and what each has available at its success point: `booking_id`, `student_id`, `property_id`, `listing_id`, and who the caller is for a cancellation. **Verification:** confirm `ApproveVerification`, `RejectVerification`, `RevokeVerification` exist as C12 states, how each performs its conditional write, and that the case carries `target_type`, `target_id`, and its id. Report any field or branch that **isn't** as C12 assumes — that is a spec gap, not something to invent.
6. Inspect Housing's `GetProperty` (does it return the provider/owner identity, and what does it raise for not-found). Confirm Payment calls Booking's `ConfirmBooking` in-process from **both** the API (webhook) and `scripts/run_payment_recovery.py`, and report exactly how Payment constructs it.
7. Inspect: shared-kernel `Page`/`PageRequest`; the router/schema conventions; `/me`-style self-scoped route handling; existing import-linter contracts and **where composition code may live** (is `platform/` allowed to import module adapters?); how the existing concurrency tests provision committed data; the project-wide frontend API doc location.
8. Confirm: no notification-related code exists anywhere.
9. Create the empty structure from Part C2 (one-line docstrings, no logic) and the test packages `tests/unit|integration|api/notification/`. Touch nothing else.

**Acceptance criteria:** a written report covering steps 2–8, every signature stated exactly, every mismatch with this specification flagged, and an explicit **proceed / blocked** verdict; scaffolding importable; no file outside the module and test folders changed.

---

### CHUNK 2 — DOMAIN MODEL
**[FOR YOU — GEMINI CLI]**

**Files:** `domain/value_objects.py`, `domain/entities.py`, `domain/templates.py`, `domain/inbox.py`.

Build exactly Part C3. **Dependencies allowed:** shared-kernel `EntityId`; stdlib. Nothing else.

**Tests** (`tests/unit/notification/domain/`), each its own named test — the full list is the "Tests (Chunk 2)" paragraph in Part C3. In addition: `NotificationType` values match the table in C3 exactly (a parametrized test over all ten), and `render()` raises for a non-member.

**Acceptance criteria:** tests pass; confirm manually no import outside the allowed list.

---

### CHUNK 3 — ERRORS, PORTS, DTOs & SETTINGS
**[FOR YOU — GEMINI CLI]**

**Files:** `application/errors.py`, `application/ports/inbound.py`, `application/ports/outbound.py`; `config/settings.py`, `.env.example`.

1. `NotificationNotFound` per C9. 2. Every inbound and outbound port in C6 as `Protocol`s with `@dataclass` request/response types. 3. Settings per C10 (`notification_debug_fail_processing` is a plain bool here; the environment guard comes in Chunk 10).
4. **Response shapes:** `NotificationView` — `id`, `category`, `type` (the dotted key), `title`, `body`, `target: {type, id} | None`, `event_count`, `is_read`, `read_at | None`, `created_at`, `latest_event_at`. `UnreadCountResult` — `unread_count`. `MarkAllReadResult` — `marked_read`. `ProcessOutcome` enum — `PROCESSED`, `SKIPPED`, `REJECTED`, `FAILED`. `CreateOutcome` enum — `CREATED`, `COLLAPSED`. `InboxRow` — `event_id`, `event_type`, `payload`, `attempts`.

**Tests:** `NotificationNotFound` parent and code; settings defaults load.

**Acceptance criteria:** `poetry run mypy` clean on touched files; tests pass; **full existing suite unchanged**; no `fastapi`/`sqlalchemy` import under `application/`.

---

### CHUNK 4 — PERSISTENCE, CONSTRAINTS & MIGRATION
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/persistence/models.py`, `notification_repository.py`, `inbox_repository.py`.

Build both tables exactly as Part C4 and both repositories against C6. Rules that are easy to get subtly wrong:
- `create_or_collapse` for collapsible types is **one atomic statement** (the `INSERT … ON CONFLICT (recipient_id, group_key) WHERE group_key IS NOT NULL AND read_at IS NULL DO UPDATE …` in C6) — the conflict target must repeat the index's predicate exactly. Distinguish `CREATED` from `COLLAPSED` reliably (e.g. via `RETURNING (xmax = 0)`, or the project's equivalent; state which you used). Non-collapsible types use a plain insert.
- `mark_read` is `UPDATE … WHERE id = :id AND recipient_id = :me AND read_at IS NULL`; return `rowcount == 1`. `mark_all_read` is one statement.
- `InboxRepository.add` is `INSERT … ON CONFLICT (event_id) DO NOTHING`; `claim` uses `FOR UPDATE SKIP LOCKED` and must refuse to run outside a transaction.
- `list_for_recipient` and `count_unread` use the C4 indexes and never load unrelated rows. Never return ORM rows outside the persistence files.

**Migration:** `poetry run alembic revision --autogenerate -m "add notification tables"`. **Read it before applying** — confirm both partial indexes (with their exact predicates), the unique `(source_event_id, recipient_id)`, every `CHECK`, and the target-columns-both-or-neither check appear as C4 states; hand-correct anything autogenerate missed.

**Tests** (`tests/integration/notification/`, marked `integration`, `db_session` fixture; constraint tests use raw inserts that bypass the application layer):
- create/read round trip; `unique (source_event_id, recipient_id)` rejects a duplicate; every `CHECK` rejects its violation (type/category values, `event_count < 1`, half-set target);
- **collapse:** two collapsible creates for the same `(recipient, group_key)` → one row, `event_count = 2`, second returns `COLLAPSED`; after `mark_read`, the next create makes a **new** row; different conversations and different recipients never collapse into each other; `latest_event_at` never moves backwards when an older event collapses in;
- `mark_read`: first call `True`, second `False`, `read_at` unchanged; another user's id → `False` and the row untouched; `mark_all_read` affects only the caller, only unread, only the category when given, and returns the exact count;
- `count_unread` agrees with the `unread_only` list for the same user; list ordering `latest_event_at DESC, id DESC` is deterministic and non-overlapping across pages;
- inbox: `add` returns `True` then `False` for the same id; `claim` returns a row once and a second concurrent `claim` of the same row skips (two sessions, committed data); `record_failure` stores a class name only; `list_due` honors `next_attempt_at` and status; `requeue_dead` resets only `DEAD` rows; `stats` is correct.

**Acceptance criteria:** tests pass against the Termux Postgres; `alembic upgrade head` clean; `lint-imports` clean.

---

### CHUNK 5 — READ USE CASES
**[FOR YOU — GEMINI CLI]**

**Files:** `application/use_cases/list_notifications.py`, `get_unread_count.py`, `mark_notification_read.py`, `mark_all_read.py`. Shared fakes under `tests/support/notification_fakes.py` (in-memory repositories, `FixedClock`), reused in Chunks 9–11.

Implement Part C7 for these four.

**Tests (fakes, no database):** list returns only the caller's notifications; filters `unread_only` and `category`; ordering; `get_unread_count` equals the unread list's length; mark-read: owned/unread → marked and returned; **repeated → success, `read_at` unchanged**; another user's id and an unknown id both → `NotificationNotFound` with identical messages; read-all: returns the exact count, never touches other users' rows, category-scoped when given, zero when nothing is unread; **there is no parameter anywhere through which a recipient id other than `actor_id` could be supplied.**

**Acceptance criteria:** tests pass; no framework imports under `application/`.

---

### CHUNK 6 — HTTP API
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/api/schemas.py`, `router.py`, `dependencies.py`; `app.py` (mount under `/api/v1/notifications`).

| Method | Path | Success |
|---|---|---|
| GET | `/notifications` | `200` — `page`, `page_size`, `unread_only` (bool), `category` (enum); standard `{items, total, page, page_size}` |
| GET | `/notifications/unread-count` | `200` — `{unread_count}` |
| POST | `/notifications/{notification_id}/read` | `200` — the updated `NotificationView` |
| POST | `/notifications/read-all` | `200` — `{marked_read}`; optional body `{category}` |

All authenticated via the shared `get_current_identity_id`; no Security permission (ADR-137). Request models `extra="forbid"`. Register the static paths in an order that cannot be shadowed by `{notification_id}`. **No business logic in the router; no endpoint creates, edits or deletes a notification.** Response schemas are built from the DTOs, never ORM rows; `target` is `{type, id}` and never a URL.

**Tests** (`tests/api/notification/`, real HTTP, seeded through the repository since there is no create endpoint):
- unauthenticated → `401` on **every** route;
- a user lists only their own; another user's notifications never appear in any page;
- **unread count is scoped:** two users with different counts each see their own;
- mark-read owned → `200`; repeat → `200`, same `read_at`; **another user's id → `404 notification_not_found`, with a body byte-identical to a random unknown id**, and the row is unchanged;
- read-all affects only the caller (assert the other user's unread count is unchanged), honors `category`;
- pagination with `page_size` smaller than the data: pages don't overlap or skip; `unread_only` agrees with the unread count; invalid `page_size`/`category`/malformed UUID → `422` in the standard error shape;
- a request body containing `recipient_id` or `user_id` anywhere → `422`;
- the responses contain no field named like a URL/link/redirect.

**Acceptance criteria:** app starts; tests pass; `lint-imports` clean; other modules' suites unaffected.

---

### CHUNK 7 — BOOKING & MESSAGING: PUBLISHING THE EVENTS
**[FOR YOU — GEMINI CLI]**

**Objective:** Booking publishes four events, and Messaging exposes its existing one as a public contract. **Booking's behavior, return values, errors and existing tests must not change.** Read **Part C12** first — it is the rulebook, including the exact "publishes when / never when" table you implement.

**Part one — the shared helper.** In `shared_kernel/application/`, add `publish_best_effort(event_bus, event, logger)`: awaits `event_bus.publish(event)` inside `try/except Exception`; on failure logs **WARNING** with `event_type` and `event_id` only (no payload) and returns. Nothing else changes in the shared kernel.

**Part two — Messaging.** Create `modules/messaging/application/ports/events.py` re-exporting `MessageCreated`. No other change to Messaging.

**Part three — Booking.**
1. `domain/events.py`: `BookingCreated`, `BookingConfirmed`, `BookingExpired`, `BookingCancelled` per C12 (frozen dataclasses extending `DomainEvent`, `occurred_at` from the injected `Clock`). Ids only.
2. `application/ports/events.py`: re-export the four.
3. Add the required constructor parameter `event_bus: EventBus` (the shared-kernel port — **do not create a Booking-specific publisher port**) to `CreateBooking`, `ConfirmBooking`, `CancelBooking`, `ExpireHolds`, and publish with `publish_best_effort` exactly where C12's table says, **in the use case only**, after commit (Chunk 1 step 4 told you where each commit happens). If a use case cannot publish after its commit without restructuring it, **stop and report**.
4. Wire the new parameter in every place these use cases are constructed: Booking's `dependencies.py`; `scripts/expire_booking_holds.py`; and **every place `ConfirmBooking` is constructed for Payment** — its Booking adapter's wiring and `scripts/run_payment_recovery.py`. Use the bus each root already has for now; **Chunk 10 replaces all of them with the shared factory.** No Payment logic changes.
5. **Existing tests:** they construct these use cases, so their construction needs a recording fake bus (`tests/support/`). That is the **only** permitted change to existing Booking or Payment tests besides new assertions. If any other existing assertion must change, you altered behavior — stop and report.

**New tests (fakes):**
- each use case publishes its event **exactly once** on the success path, with the correct field values, `occurred_at` from `FixedClock`, and **no price/reason field present**;
- **never-published cases, one test each, asserting the fake bus recorded nothing:** `CreateBooking` idempotent replay; `CreateBooking` rejected at each of steps 2–6; `CreateBooking` where `add` fails and the compensating release runs; `ConfirmBooking` on an expired hold; `ConfirmBooking` zero-row match; `CancelBooking` on an already-cancelled booking (and assert it **also** did not release inventory); `CancelBooking` zero-row match; `ExpireHolds` for a booking whose release fails (while another booking in the same run **is** published); `ExpireHolds` zero-row match;
- `CancelBooking` records `cancelled_by` = the caller, for a student, a provider, and an admin caller;
- **commit failure:** a fake `UnitOfWork` whose commit raises → nothing published;
- **a bus whose `publish` raises never changes the use case's result or return value** — success is still returned, a WARNING is logged, and the log line holds no payload;
- `publish_best_effort` unit tests: swallows the exception, logs type and id only, returns normally.

**Acceptance criteria:** new tests pass; Booking's **entire** suite, Payment's suite, and Messaging's suite pass with only the documented fake-bus additions; `poetry run mypy` and `poetry run lint-imports` clean; manually confirm no file in Booking, Payment, or Messaging imports anything from `camp_match.modules.notification`.
---

### CHUNK 8 — VERIFICATION: PUBLISHING THE DECISION EVENT
**[FOR YOU — GEMINI CLI]**

**Objective:** Verification publishes one event when a case reaches a final decision. **Verification's behavior, return values, errors and existing tests must not change.** Read **Part C12** — it is the rulebook, including the exact table you implement.

**Files (Verification):** `domain/events.py`, `application/ports/events.py`, `ApproveVerification`, `RejectVerification`, `RevokeVerification`, and their composition.

1. `domain/events.py`: `VerificationDecisionRecorded(case_id, target_type, target_id, decision)` — frozen dataclass extending `DomainEvent`, `occurred_at` from the injected `Clock`; `decision` is an enum/string limited to `VERIFIED`, `REJECTED`, `REVOKED`. **No reason, no decider identity, no expiry, no evidence, no owner field.** Re-export from `application/ports/events.py`.
2. Add the required constructor parameter `event_bus: EventBus` (the shared-kernel port — **no Verification-specific publisher port**) to the three use cases and publish via `publish_best_effort` exactly where C12's table says, after commit, from the use case only. Reuse `shared_kernel`'s helper from Chunk 7.
3. Wire the parameter wherever these use cases are constructed (Verification's `dependencies.py`, and any script or other composition root Chunk 1 found); use the existing bus for now — **Chunk 10 swaps in the shared factory.**
4. **Existing tests:** recording fake bus only, same rule as Chunk 7. Anything else changing means you altered behavior — stop and report.

**New tests (fakes):**
- each of the three use cases publishes `VerificationDecisionRecorded` **exactly once** on success with the correct `case_id`, `target_type`, `target_id` and `decision` — one test per decision, and per target type (`PROVIDER` and `PROPERTY`);
- **never published, one test each:** approve/reject by the case's own inspector (`UnauthorizedVerificationAction`); approve with unsatisfied evidence requirements; approve/reject/revoke with a missing reason; a zero-row match (`DecisionNotAllowed`); revoke of a case that isn't `VERIFIED`; **every non-decision step** — create, submit, evidence, assignment, inspection steps, cancellation;
- commit failure (fake `UnitOfWork` raising) → nothing published;
- a raising bus never changes the result — success is still returned, WARNING logged without payload;
- the event dataclass has no free-text field (assert its field names).

**Acceptance criteria:** new tests pass; Verification's **entire** suite passes with only the documented fake-bus additions; Housing's and Search's suites (which read verification state) unaffected; `mypy` and `lint-imports` clean; manually confirm Verification imports nothing from `camp_match.modules.notification`.
---

### CHUNK 9 — INBOX RECEIPT, PROCESSING & POLICIES
**[FOR YOU — GEMINI CLI]**

**Files:** `application/parsing/event_parsers.py`, `application/policies/recipient_policies.py`, `application/use_cases/receive_event.py`, `process_inbox_event.py`, `process_pending_inbox.py`, `requeue_dead_events.py`, `get_inbox_stats.py`; `adapters/housing/property_owner_provider.py`.

Implement Part C5–C7 exactly: a strict parser per supported event type (rejects missing/extra-typed/malformed values; unknown enum → rejected); the recipient policy table; `ReceiveEvent`; `ProcessInboxEvent` with the single-transaction rule, the three failure outcomes, backoff, and the `DEAD` transition; `ProcessPendingInbox`; the two operator use cases; and the Housing-backed `PropertyOwnerProvider` (imports only Housing's public ports).

**Tests (fakes, `FixedClock`, no sleeping):**
- **per event, the intended notifications and nothing else:** `MessageCreated` → one notification for `recipient_id`, none for the sender; `BookingCreated` → provider only; `BookingConfirmed` → student and provider (two distinct records); `BookingCancelled` by the student → provider only, by the provider → student only, **by an administrator → both**; `BookingExpired` → student only; each `VerificationDecisionRecorded` decision → the right type to `owner_id`;
- **templates only:** rendered title/body equal the C3 table; no id, name, or event field text appears in any title or body;
- **unsupported event type** and **every malformed payload shape** → `REJECTED`, zero notifications, never retried;
- **provider unresolvable:** `get_owner` returns `None` → provider-side drafts skipped, event `PROCESSED`, WARNING logged, **student-side drafts still created** where the policy has them; `get_owner` raises → the whole event `FAILED`, **nothing** partially written (assert zero notifications), attempts incremented, `next_attempt_at` per the backoff function;
- backoff across attempts 1…N; reaching `notification_inbox_max_attempts` → `DEAD` with an ERROR log; `ProcessPendingInbox` skips rows whose `next_attempt_at` is in the future and processes due ones, one row's failure not stopping others;
- **`ReceiveEvent`:** first call inserts (`inserted=True`); the same event again → `False`; a failing repository **raises** (the one place it should);
- **processing never raises:** a repository that raises mid-write → `FAILED`, nothing escaped;
- logs: assert no notification title/body, no payload, and no recipient content appears in captured logs;
- `RequeueDeadEvents` resets only `DEAD`; `GetInboxStats` counts;
- **verification recipients:** a `PROVIDER` case notifies `target_id` with no Housing lookup; a `PROPERTY` case notifies the property's owner via `get_owner`, **never** the reviewing account (the event doesn't even carry it); `get_owner` returning `None` → `PROCESSED`, zero notifications, WARNING `notification_no_recipient`; `get_owner` raising → `FAILED`, retried;
- **forty messages, one notification:** with the fake repository implementing the same collapse rule, process 40 distinct `MessageCreated` events for one `(recipient, conversation)` → exactly **one** notification with `event_count = 40`; events for a second conversation, and for a second recipient, never collapse into it;
- the application layer's parsers accept **plain dictionaries only** — a test that imports nothing from any producer module.

**Acceptance criteria:** tests pass against fakes; no `fastapi`/`sqlalchemy` under `application/`.

---

### CHUNK 10 — SUBSCRIBERS, THE SINGLE BUS FACTORY & THE WORKER
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/events/subscribers.py`, `registration.py`; the bus factory (location per Chunk 1 step 7); `scripts/run_notification_worker.py`; every composition root from Chunk 1 step 3.

1. Implement C8 exactly. Handlers use a fresh session per call (C1 rule 3).
2. Create **one** `build_event_bus(...)` factory that constructs the shared `InMemoryEventBus` and calls `register_notification_subscribers`. **Replace every direct construction** of the bus in `app.py` and in each script that publishes or composes a publishing use case: `expire_booking_holds.py`, `run_messaging_outbox_relay.py`, `run_payment_recovery.py`, and any other root Chunk 1 found — Payment's recovery composes Booking's confirm, so it must have the subscribers too. Report the final list.
3. `notification_debug_fail_processing`: when `True` **and** `app_env` is `local` or `test`, `ProcessInboxEvent`'s protected step raises. `app.py`/the factory checks `app_env` explicitly and ignores the flag otherwise — a structural guard, same stance as Payment's mock-control router and Messaging's debug subscriber.
4. `scripts/run_notification_worker.py`: default = compose and run `ProcessPendingInbox(notification_worker_batch_size)` **once**, printing counts per outcome; `--stats` prints `GetInboxStats`; `--requeue-dead` runs `RequeueDeadEvents` and prints the count. **No loop, no daemon, no scheduler, no new dependency.** Verify the existing scripts' argument-handling style and follow it.

**Tests:**
- **end to end, real database, real bus:** register the subscribers and publish a `MessageCreated` → a notification exists for the recipient; publish `BookingCreated` (seeding a real Housing property for the owner lookup) → one for the provider;
- **handler-returns-means-durable:** the inbox row exists the instant the handler returns, `PROCESSED` on the happy path;
- **a processing failure does not propagate:** with `notification_debug_fail_processing=True`, publishing returns normally, the inbox row is `PENDING` with `attempts = 1`, and **no notification exists**; with the flag removed, running the worker processes it exactly once;
- **a receipt failure does propagate** (a session factory that raises): the handler raises — and a `publish_best_effort` caller around it still returns normally;
- the debug flag is **ignored** when `app_env="staging"`;
- **guard test:** a test that scans `src/` and `scripts/` and fails if `InMemoryEventBus(` is constructed anywhere except the factory;
- **every publishing process has the subscribers:** for each composition root, build its bus via the same path it uses and assert a Notification handler is registered for all six event types;
- worker script: default run, `--stats`, `--requeue-dead` each tested through their `main()` against the test database;
- **`event_to_payload` round trip:** for each of the six events, convert, parse with the strict parser, and get the same field values back (ids as `EntityId`, enums as enums); a converted payload contains no field named like a body, reason, name, or amount;
- **the adapter layer is the only importer:** `adapters/events/` imports the producers' `application/ports/events.py`; nothing under `domain/` or `application/` does (Chunk 12 makes this a lint contract; assert it here too with a source scan).

**Acceptance criteria:** tests pass; Booking's, Messaging's, Payment's suites unaffected; no direct `InMemoryEventBus(` left outside the factory.

---

### CHUNK 11 — RELIABILITY & CONCURRENCY
**[FOR YOU — GEMINI CLI]**

**Objective:** prove the guarantees in ADR-131 and ADR-135 on a real database. Mostly tests; fix whatever they reveal.

**Tests** (`tests/integration/notification/test_reliability.py`, committed data, genuinely concurrent via `asyncio.gather`, each run **three times in a row**):
- **duplicate delivery:** publish the *same* event (same `event_id`) 10 times concurrently → exactly **one** inbox row, exactly **one** set of notifications, collapse counts correct;
- **two workers:** ten `PENDING` inbox rows, two `ProcessPendingInbox` runs concurrently → every event processed exactly once (no duplicates, none missed);
- **same event, receipt and worker racing:** the inline handler and a worker pick up the same row → exactly one effect;
- **restart recovery:** leave rows `PENDING` (simulating a crash after receipt), start a fresh session/worker → they are processed; rows already `PROCESSED` are untouched;
- **failure between receipt and processing:** processing raises after the inbox insert → the event is not lost, is retried, and the retry produces exactly one notification;
- **atomicity:** force a failure *after* some drafts are written but before the status flip (e.g. a second draft's insert fails) → **zero** notifications persisted and the row not `PROCESSED`;
- **collapse under concurrency:** 20 concurrent `MessageCreated` events for one conversation → exactly one unread notification with `event_count = 20`; interleave a mark-read → afterwards the sum of `event_count` over that conversation's notifications is exactly 20 (nothing lost, nothing double-counted);
- **forty in a row on a real database:** 40 `MessageCreated` events for one conversation delivered one after another → exactly **one** unread notification with `event_count = 40`; read it, send 5 more → a **new** notification with `event_count = 5`, and the first is untouched at 40;
- **concurrent read operations:** many concurrent mark-read calls on one notification → one `True`, the rest `False`, `read_at` set once;
- **DEAD letter:** an event that always fails reaches `DEAD` after exactly `notification_inbox_max_attempts` attempts, never earlier; `--requeue-dead` brings it back with `attempts = 0`;
- **producer isolation (real stack):** with the failing-processing flag on, create a booking and send a message through the real HTTP API → both succeed (`201`) and persist; the notifications appear after the worker runs.

**Acceptance criteria:** all pass **three consecutive runs**; any defect is fixed in the responsible layer (never patched in a test) and noted in the report.

---

### CHUNK 12 — SECURITY, PRIVACY & REGRESSION SWEEP
**[FOR YOU — GEMINI CLI]**

**Files:** `tests/api/notification/test_notification_security.py`; `pyproject.toml` import-linter contracts.

- **Privacy, end to end:** drive a real message send, a booking create/confirm/cancel/expire, and a verification decision through their real modules; for every resulting notification assert the title/body equal the fixed templates and contain **no** message text, no name, no phone, no amount, no reason, no URL; a log-capture across the whole flow asserts no notification body, no payload, no message content, and no access token appears in any log line.
- **Isolation:** one user can never read, mark, or count another user's notifications through any route; a participant in a conversation is not notified of **their own** messages; a non-recipient never gets a notification from an event naming someone else.
- **No creation path:** assert the route table contains no endpoint that creates or modifies a notification's content or recipient, and no admin/browse-everyone route.
- **Import-linter contracts** (extend the existing list, same pattern as every module): Notification's `domain` and `application` must not import `fastapi`/`sqlalchemy` **and must not import any other module at all**; only Notification's `adapters/events/` may import other modules' `application/ports/events.py`, and only `adapters/housing/` may import Housing's `application.ports`; nothing may import another module's `adapters` or `domain`; **Messaging, Booking, Verification, Housing, Payment and every other module must not import `camp_match.modules.notification`**. **Deliberately violate each of the two new contracts once** (Booking importing a Notification symbol; Notification's `application` importing a Booking event), confirm `lint-imports` fails each time, remove the violations.
- **Full regression:** `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports` across **all twelve modules**; then re-run Messaging's, Booking's, Verification's, and Payment's suites in isolation and confirm they are unchanged apart from the documented fake-bus additions.

**Acceptance criteria:** every test above passes; no skipped or known-failing test.

---

### CHUNK 13 — DOCUMENTATION, MANUAL GUIDE & AI STATE
**[FOR YOU — GEMINI CLI — Part G at the end of this file is the source for the manual testing document]**

1. Write `docs/modules/notification.md` per `09_DOCUMENTATION_RULES.md` covering: purpose and non-purpose; boundaries; domain model and tables; the event-contract table (C5) and recipient policies; the **receipt/processing/retry lifecycle** with the recovery behavior at **every** failure point (receipt fails, processing fails, worker dies mid-run, duplicate event, two workers, retries exhausted → `DEAD`, operator requeue); the collapse rule; API with request/response examples; security and privacy rules (C1, ADR-138); configuration (C10); local development and the worker script; testing strategy and exact commands; integration notes for **future producers** (how to add a new event: producer's `events.py` + `ports/events.py` re-export + best-effort publish after commit; Notification's parser + policy + templates + subscriber registration + tests).
2. **Known limitations, listed plainly and individually:** Booking and Verification events are at-most-once across a crash between commit and publish (Messaging's are durable) — a shared outbox is the named follow-up (ADR-131); in-app only — no push, email, preferences, or device registration, and **no delivery-attempt tables** (ADR-130); no real-time channel — clients poll (ADR-139); Payment, Housing, Identity and Trust & Safety events are not supported (ADR-134); no retention or purge (ADR-142); no rate limiting on the read endpoints (Identity's ADR-020 gap continues); message notifications collapse to one per conversation (ADR-136); the worker is run manually or by cron, not a daemon (ADR-141); `DEAD` events need an operator.
3. Create `docs/modules/notification_manual_testing.md` from Part G, **running every command you document**, correcting any that doesn't work in this repository.
4. Update the booking, verification, and messaging module docs with a short "Published events" section (fields, when published, best-effort). Update `docs/modules/security.md` only if anything changed there (nothing should have).
5. Update the frontend API reference location Chunk 1 found **only with a pointer** — Nsisong maintains the Front End Doc from Part F.
6. Update `AI_state/`: `CURRENT_STATE.md`, `PROGRESS.md`, `COMPLETED_WORK.md`, `ARCHITECTURE_STATE.md` (the first event *consumer*; the bus factory; the three producer amendments), `DATABASE_STATE.md` (two tables, one migration), `API_STATE.md` (four endpoints), `TEST_STATE.md`, `DECISIONS.md` (append ADR-129–143), `SESSION_HANDOFF.md`; `CURRENT_TASK.md` in the standard format.

**Acceptance criteria:** every document exists and matches the implementation (no speculative endpoints or fields); every documented command was executed; limitations stated without softening.

---

### CHUNK 14 — FINAL AUDIT & COMPLETION REPORT
**[FOR YOU — GEMINI CLI]**

1. From a clean state (`scripts/db_stop.sh`, `scripts/db_start.sh`, `poetry run alembic upgrade head`) run the full four-command suite, then re-run **every concurrency/reliability test file three times** as the last step.
2. Answer each plainly — not "done":
   - Can any Notification failure — receipt, processing, or a raised exception — change the result of a booking, message, or verification decision? **yes/no, with the evidence** (which tests prove it).
   - Is there a path that publishes an event *before* the producer's commit? yes/no, per producer.
   - Does any code path write a notification without the inbox status flip in the same transaction? yes/no.
   - Can a duplicate event or two workers produce duplicate notifications? yes/no, proven on a real database.
   - Does any title/body/log contain message text, names, amounts, reasons, or URLs? yes/no.
   - Can any user read or change another user's notification? yes/no.
   - Does every process that publishes an event register the Notification subscribers? yes/no, with the list of roots and the guard test.
   - Does any producer import Notification, or does Notification's `domain`/`application` import any other module? yes/no (the import-linter result for both contracts).
   - Did Booking's or Verification's behavior, return values, or existing assertions change in any way other than the fake-bus additions? yes/no, with evidence.
3. **Readiness classification — do not round up:**
   - In-app notification creation, listing, unread count, read, read-all: implemented? yes/no.
   - Messaging events: durable end to end (outbox → inbox).
   - Booking and Verification events: **at-most-once across a producer crash between commit and publish**.
   - Push, email, preferences, device registration, delivery attempts: **not implemented** (ADR-130).
   - Real-time delivery: **not implemented**; polling.
   - Payment/escrow, Housing, Trust & Safety notifications: **not implemented** (ADR-134).
4. Report: completed requirements; every command and its real result; known limitations; unresolved issues; the exact recommended next step. **Do not claim completion for anything unimplemented or unverified.** Set `CURRENT_TASK.md` to "Notification complete. Awaiting next module specification from Claude."

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

### The handoff's chunk sequence → this document
| Handoff chunk | Here | Note |
|---|---|---|
| 1 Inspection | Chunk 1 | adds composition-root inventory and commit-boundary check |
| 2 Domain and scope decisions | Part A/B + Chunk 2 | scope decided in ADR-130/134 |
| 3 Public contracts / event design | Part C5 and C12, Chunks 7–8 | contracts *created* for Booking and Verification (Finding 1) |
| 4 Domain implementation | Chunk 2 | |
| 5 Persistence | Chunk 4 | |
| 6 In-app creation | Chunk 9 | |
| 7 User-facing read APIs | Chunks 5–6 | |
| 8 Event processing and idempotency | Chunks 9–11 | |
| 9 Policies and preferences | Chunk 9 (policies); preferences **deferred** | ADR-130 |
| 10 Delivery infrastructure | **Not applicable** | no channel exists (Finding 5); retry/backoff built for event processing instead |
| 11 Optional push/email | **Not applicable** | not approved |
| 12 Real-time integration | **Not applicable** | decision recorded, ADR-139 |
| 13 Security, privacy, operations | Chunk 12; worker `--stats`/`--requeue-dead` in Chunk 10 | |
| 14 Integration and regression | Chunks 11–12 | |
| 15 Manual guide and docs | Chunk 13 | |
| 16 Final audit | Chunk 14 | |

### The handoff's Section 15 tests → where each is proven
| Handoff item | Where |
|---|---|
| 15.1 domain (creation, invariants, read-state, policies) | Chunk 2; policies in Chunk 9 |
| 15.2 API (own list, isolation, unread scoping, read, repeat read, read-all, pagination/validation, unauthenticated) | Chunk 6; preference endpoints **not applicable** |
| 15.3 event processing (intended notification, unsupported, duplicates, multi-recipient, invalid payload, concurrent duplicates, persistence failure, retry recovery) | Chunks 9–11 |
| 15.4 delivery (provider success/failure/timeout/tokens) | **Not applicable** (no channel); "delivery failure never deletes a notification or reverses a business operation" is covered by the Chunk 11 producer-isolation test |
| 15.5 integration/regression (events follow real contracts; module independence; suites pass) | Chunks 7–8, 10, 12 |
| 15.6 reliability/concurrency (two workers, concurrent reads, interruption, duplicate after restart, failure between creation and delivery) | Chunk 11 |

### The handoff's Definition of Done
Everything is covered except the three items it makes conditional on features not built — "retry behavior and terminal failures documented and tested" is satisfied for **event processing** (`DEAD`, backoff, requeue), not for external providers; "optional push/email implemented only if approved" is satisfied by not implementing them.

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**Applies everywhere:** routes are under `/api/v1/notifications`, authenticated with `Authorization: Bearer <access_token>`. Errors use `{"error": {"code", "message"}}`. You only ever see **your own** notifications; another person's id behaves exactly like an id that doesn't exist (`404 notification_not_found`). There is **no way to create a notification from the client** — they appear as a result of things that happen elsewhere (a message arrives, a booking changes, a verification is decided).

### GET /api/v1/notifications
**Query:** `page`, `page_size`, `unread_only` (`true`/`false`), `category` (`MESSAGE` | `BOOKING` | `VERIFICATION`).
**Response:** standard `{items, total, page, page_size}`, newest activity first. Each item:
```json
{
  "id": "…", "category": "BOOKING", "type": "booking.confirmed.student",
  "title": "Booking confirmed", "body": "Your booking has been confirmed.",
  "target": { "type": "BOOKING", "id": "…" },
  "event_count": 1, "is_read": false, "read_at": null,
  "created_at": "…", "latest_event_at": "…"
}
```
**Notes:** `title` and `body` are ready to display. `target` tells you what to open when the user taps: `CONVERSATION` → that conversation, `BOOKING` → that booking, `VERIFICATION_CASE` → that verification case. **It is a reference, not a URL** — you decide the screen. Order can shift between pages while new notifications arrive; refetch from page 1 rather than patching.

### GET /api/v1/notifications/unread-count
**Response:** `{"unread_count": 3}`. Same definition as `unread_only=true`. **This is the call to poll** for your badge (see below).

### POST /api/v1/notifications/{notification_id}/read
**Success `200`:** the updated notification. **Safe to repeat** — a second call returns `200` with the original `read_at` unchanged. **Errors:** `404 notification_not_found` (not yours, or doesn't exist), `422` malformed id.

### POST /api/v1/notifications/read-all
**Body (optional):** `{"category": "BOOKING"}` to mark only that category. **Success `200`:** `{"marked_read": 4}` (zero if nothing was unread).

### How new messages appear (important)
A burst of messages in one conversation produces **one** unread `message.new` notification for that conversation, whose **`event_count`** goes up — **forty messages in a row are one notification with `event_count: 40`, not forty notifications.** Show "New message" for `event_count: 1` and "N new messages" for more; the body text is always the same generic sentence — **it never contains the message text or the sender's name**. Once the user reads that notification, the *next* message in the conversation creates a fresh one. (To show the actual messages and the unread state of the chat itself, use the Messaging module's own endpoints.)

### Staying up to date
There is **no push and no live channel for notifications** in this release. While the app is in the foreground, poll `GET /notifications/unread-count` every 30–60 seconds, and refetch the list when the number changes or the user opens the notifications screen. You don't need to refetch after your own actions: they notify the *other* person, not you.

**Who gets notified of what:** new message → the recipient · new booking → the listing's provider · booking confirmed → student and provider · booking cancelled → the other party (both, if an administrator cancelled) · booking expired → the student · verification approved / not approved / revoked → the case owner.

```js
async function unreadCount() {
  const r = await fetch('/api/v1/notifications/unread-count', { headers: { Authorization: `Bearer ${token()}` } });
  return (await r.json()).unread_count;
}
async function loadNotifications(page = 1) {
  const r = await fetch(`/api/v1/notifications?page=${page}&page_size=20`, { headers: { Authorization: `Bearer ${token()}` } });
  return r.json();
}
async function open(n) {                                   // mark read, then route by target
  await fetch(`/api/v1/notifications/${n.id}/read`, { method: 'POST', headers: { Authorization: `Bearer ${token()}` } });
  const routes = { CONVERSATION: `/chat/${n.target?.id}`, BOOKING: `/bookings/${n.target?.id}`, VERIFICATION_CASE: `/verification/${n.target?.id}` };
  if (n.target) navigate(routes[n.target.type]);
}
setInterval(async () => { badge.set(await unreadCount()); }, 45000);
```
**Known limitations (tell your product people):** no push notifications or email yet; no notification preferences; no live updates (polling); no payment or listing notifications yet; notifications are not automatically deleted.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — and Gemini's source for the manual-testing document in Chunk 13]

**Preconditions:** `scripts/db_start.sh` running; app running; Messaging working (Module 11). Two accounts with profiles — **Ada** (Student) and **Bola** (Scout) — and Bola owns a `PUBLISHED`, bookable listing (Modules 2, 5). A third account **Chidi** for isolation tests. Keep their access tokens. Use `curl` with `Authorization: Bearer <token>`. Anything marked **(Gemini verifies)** is a table/column or script argument Gemini must confirm in Chunk 13 and write down exactly — the guide may only contain commands that were actually run.

Format: **verifies** · **why** · **steps** · **expect** · **if it fails**.

**N1 — A message creates a notification for the recipient only.** *Verifies:* an event becomes a notification for the right person. *Why:* the core purpose. *Steps:* Ada starts a conversation with Bola's listing and sends a message (Module 11 endpoints); Bola `GET /notifications`; Ada `GET /notifications`. *Expect:* Bola has one `message.new` ("New message" / "You have a new message."), unread; Ada has none — **she isn't notified of her own message**. *If it fails:* nothing for Bola → run `poetry run python scripts/run_notification_worker.py --stats` (a `PENDING` or `DEAD` row says processing is stuck; nothing at all says the event never arrived — check the app log for `notification_event_received`).

**N2 — Nobody sees anyone else's notifications.** *Verifies:* isolation. *Why:* privacy. *Steps:* take Bola's notification id; as Ada and as Chidi `POST /notifications/<id>/read`; as Chidi `GET /notifications`. *Expect:* `404 notification_not_found` for both, byte-identical to a made-up id; Chidi's list has nothing of Bola's; Bola's notification is still unread. *If it fails:* any `200` here is a privacy bug — stop.

**N3 — Unread count.** *Verifies:* the badge number. *Why:* it's the polled call. *Steps:* as Bola `GET /notifications/unread-count`; compare with `GET /notifications?unread_only=true`. *Expect:* the same number (1 so far); Ada's own count is 0. *If it fails:* the two numbers differing means the count and the list disagree on "unread."

**N4 — Mark one read, safely repeatable.** *Steps:* Bola `POST /notifications/<id>/read` twice. *Expect:* both `200`; `read_at` identical both times; unread count now 0. *If it fails:* a changed `read_at` on the second call is a bug.

**N5 — Read-all.** *Steps:* generate two more notifications for Bola (N7 below works), then Bola `POST /notifications/read-all`; check Ada's unread count didn't change; repeat with `{"category":"BOOKING"}` on fresh ones. *Expect:* `{"marked_read": N}` with the exact count; only Bola's affected; category-scoped when given. *If it fails:* another user's count moving is blocking.

**N6 — Message collapsing (the "40 messages" test).** *Verifies:* a chat burst is one notification. *Why:* otherwise 40 messages = 40 notifications. *Steps:* Bola reads everything (N5); Ada sends **40 messages in a row** using a small shell loop with a different `client_message_id` each time *(Gemini verifies and writes the exact loop, e.g. `for i in $(seq 1 40); do curl … -d "{\"client_message_id\":\"burst-$i\",\"content\":\"hi $i\"}"; done`)*; run `poetry run python scripts/run_notification_worker.py --stats` (nothing should be pending); Bola lists. *Expect:* **exactly one** `message.new` with `event_count: 40` and the generic text "You have a new message." Bola marks it read; Ada sends one more → a **new** notification with `event_count: 1`, and the old one is unchanged. *If it fails:* more than one notification for the burst means collapsing isn't working — blocking; a count that isn't 40 means an event was lost or double-counted.

**N7 — Booking events.** *Verifies:* each booking event reaches the right person. *Steps:* Ada books Bola's listing → Bola gets "New booking". Ada cancels it → Bola gets "Booking cancelled". Create another booking and have Bola cancel it → **Ada** gets "Booking cancelled" and Bola does not. For expiry, make a booking's hold expired *(Gemini verifies the exact table/column and writes the exact `psql` command)* and run `poetry run python scripts/expire_booking_holds.py` → **Ada** gets "Booking expired"; Bola gets nothing. *Expect:* exactly as stated; **the expiry notification arriving proves scripts publish to Notification** (this is the multi-process wiring test). *If it fails:* the expiry one missing while the others work means the script isn't using the shared bus factory — blocking.

**N8 — Confirmation reaches both.** *Steps:* complete a payment on the mock provider and let the booking confirm *(Gemini verifies the exact Payment mock-control calls from Module 10)*. *Expect:* Ada gets "Booking confirmed"/"Your booking has been confirmed."; Bola gets "…A booking on one of your listings has been confirmed." — two separate records.

**N9 — Verification decision.** *Steps:* have an `OPERATIONS`/`ADMIN` account approve Bola's verification case (Module 7 endpoints), and in another run reject/revoke. *Expect:* for a **property** case, **Bola as the property's owner** is notified (the reviewer is not); for a **provider** case, the provider is. Bola gets "Verification approved" / "…not approved. Open the case for details." / "…revoked…", target type `VERIFICATION_CASE`, and **no rejection reason in the text**. *If it fails:* any free-text reason appearing in a notification is a privacy bug.

**N10 — A duplicate event never makes a duplicate notification.** *Verifies:* idempotency. *Why:* events are delivered more than once in real systems. *Steps:* after N1, reset Messaging's outbox row *(Gemini verifies:* `update messaging_outbox set dispatched_at = null where …`*)* and run `poetry run python scripts/run_messaging_outbox_relay.py`; list Bola's notifications. *Expect:* the relay reports one dispatched; **Bola's notifications and `event_count` are unchanged**; the app log shows `notification_event_duplicate`. *If it fails:* a new notification or a bumped `event_count` means duplicate protection is broken — blocking.

**N11 — Notification failure never breaks the business action, and recovers.** *Verifies:* the core rule. *Why:* a booking or message must never fail because a notification did. *Steps:* set `NOTIFICATION_DEBUG_FAIL_PROCESSING=true` and `NOTIFICATION_INBOX_BACKOFF_BASE_SECONDS=1` (local only), restart; Ada sends a message → still `201`; Bola's list is empty; `poetry run python scripts/run_notification_worker.py --stats` shows one `PENDING`; check the inbox row (`select status, attempts, last_error from notification_inbox`) shows `attempts ≥ 1` and a **class name only** in `last_error`. Unset the flag, restart, wait 2 seconds, run the worker. *Expect:* worker reports one processed; Bola now has the notification **exactly once**. *If it fails:* the message send failing while the flag is on is blocking; a notification that never appears means retry is broken.

**N12 — Dead letters and the operator.** *Steps:* with the failing flag, set `NOTIFICATION_INBOX_MAX_ATTEMPTS=2`; send a message; run the worker twice (waiting past the backoff); `--stats`. *Expect:* one `DEAD`, an ERROR log `notification_event_dead`; unset the flag; `poetry run python scripts/run_notification_worker.py --requeue-dead` then run the worker normally → processed once. *If it fails:* a `DEAD` row that retries forever, or never recovers after requeue, is a bug.

**Intentionally absent:** preference and device-registration tests (not implemented, ADR-130), provider-delivery tests (no external channel), live-update tests (ADR-139).

**Automated tests:** `poetry run pytest tests/unit/notification tests/integration/notification tests/api/notification` · fast, no database: `poetry run pytest tests/unit/notification -v` · reliability, three times: `for i in 1 2 3; do poetry run pytest tests/integration/notification/test_reliability.py; done` · everything: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] **Ports and adapters hold:** Notification's `domain` and `application` import no other module; only its `adapters/events/` import producers' `application/ports/events.py`, and only `adapters/housing/` imports Housing's ports; **no producer imports Notification** — both contracts proven with a deliberate-violation check.
- [ ] Booking and Verification gained only the shared-kernel `EventBus` parameter and best-effort post-commit publishes (C12); no Booking- or Verification-specific publisher port was created; their behavior and existing assertions are unchanged apart from the fake-bus additions.
- [ ] Forty messages in a conversation produce one notification with `event_count = 40`, on fakes and on a real database.
- [ ] No notification failure — receipt or processing — can change a booking, message, or verification decision; proven by a real-stack test.
- [ ] Booking and Verification events are published only after commit, only on real transitions, never on idempotent repeats or refused operations, and never change their producer's result.
- [ ] The handler returning means the event is durable; processing is exactly-once in effect on a real database across duplicate delivery, two workers, and restart (three consecutive runs).
- [ ] Notification writes and the inbox status flip are one transaction; a partial failure leaves nothing behind.
- [ ] Retries are bounded with exponential backoff; exhausted events are `DEAD` and recoverable by `--requeue-dead`; unparseable events are rejected immediately.
- [ ] Every process that publishes registers the subscribers via the single factory; the guard test fails on any other bus construction; the expiry-script notification arrives.
- [ ] Message notifications collapse to one unread per conversation, correct under concurrency and mark-read races.
- [ ] Every notification's text is a fixed template — no message text, names, amounts, reasons, or URLs — and no log line contains content or payloads.
- [ ] A user can never read, count, or mark another user's notification; foreign and unknown ids are indistinguishable.
- [ ] No endpoint creates or edits a notification; targets are references, never URLs.
- [ ] Identity, Profile, Security, Housing, Search, Media/File, Messaging, Booking, Verification, Payment suites unchanged apart from the documented fake-bus additions and new assertions.
- [ ] `docs/modules/notification.md`, the manual guide, and `AI_state/` are written, every documented command was run, and the limitations are stated without softening — especially: at-most-once Booking/Verification events across a producer crash, in-app only, polling only, no Payment events.
- [ ] The Chunk 14 readiness classification is recorded honestly.
