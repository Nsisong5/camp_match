# CAMP MATCH — MODULE 11: MESSAGING
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Messaging Module handoff**

---

## HOW TO READ THIS DOCUMENT

Same conventions as every previous module spec. **[FOR YOU — GEMINI CLI]** parts are pasted to Gemini, **[FOR NSISONG]** parts are for you. Standing Instructions live in `AI_instructions/`.

**What to paste, and when:**
- **Part C (Design Specification)** — paste together with Chunk 1, once. Gemini reads it fully before writing anything. Chunks reference it instead of repeating it.
- **Part D chunks 1–17** — one at a time, in order, waiting for each Completion Report. Never two at once.
- **Part G (Manual Testing Guide)** — paste together with Chunk 16.
- **Parts E and F** are for you. Part F goes into your Front End Doc.

The Chief Engineer's handoff listed 16 chunks. This document delivers **17**, with three deliberate differences, each noted again where it happens:
- Its Chunk 5 (core conversations) is **split in two** (our Chunks 5 and 6): cross-module adapters, a new Security permission and a rate limiter are a different kind of work from the conversation use cases that depend on them. Every later chunk therefore shifts by one (handoff 6 = our 7 … handoff 16 = our 17).
- Its Chunk 12 (cross-process delivery) becomes our **Chunk 13**, reshaped: the decision is made by ADR-123, so the chunk enforces and documents it (Finding 4).
- Its Chunk 13 (Notification / Trust & Safety / Media) becomes our **Chunk 14**, reshaped to reliable event publication, because the first two modules it names don't exist and the third is deferred (Findings 1 and 3).

---

## PART A — ARCHITECTURAL INTERPRETATION & FINDINGS [FOR NSISONG]

Messaging answers: *who may talk to whom, what was said, in what order, and who has seen it* — and delivers it live when it can, without live delivery ever being the source of truth. The handoff's central rule — WebSockets are a transport, never the owner of a message — is already how this project thinks (Search owns no facts; Booking calls Housing's port; Payment never touches a provider SDK from its rules). This module applies the same discipline to a socket.

The handoff says to inspect the repository before assuming anything. I can't read your code, only the 15 specifications that produced it, so I applied the "sieve" role against those. Five real findings, all before any implementation content.

### FINDING 1 — the handoff assumes three things that don't exist yet

The handoff repeatedly refers to "the existing Notification module," "existing Trust & Safety capabilities," and "the project's established event mechanism / transactional outbox / rate-limiting infrastructure." Checked against Modules 1–10:

- **There is no Notification module and no Trust & Safety module.** Neither has been specified or built. Module 10's handoff names Messaging as Module 11 and nothing else is queued.
- **The only event mechanism is Phase 2's in-process `InMemoryEventBus`.** It has no persistence, no outbox, and — across ten modules — no real subscriber has ever been wired to it (Identity ADR-022, Profile ADR-034 both chose not to publish events nobody consumes). A handler exception also propagates straight out of `publish`.
- **There is no rate limiting anywhere.** Identity's ADR-020 recorded that as a known gap, and nothing has closed it. No Redis exists either.

I'm not inventing any of the three as if they existed. What I'm doing, in line with the handoff's own instruction ("document the gap and implement the smallest suitable solution"):

- **Notification:** Messaging publishes `MessageCreated` and knows nothing else about notifications. When a Notification module exists it subscribes. Until then the event has no consumer, and that is stated plainly. (ADR-119, ADR-121)
- **Trust & Safety:** one outbound port, `CommunicationRestrictionProvider`, backed *today* by something that does exist — Identity's account status (`ACTIVE`/`SUSPENDED`/`DISABLED`). A suspended or disabled account really can't start conversations or send messages. Blocking, reporting and moderation are named as unbuilt, with the port as the seam. (ADR-120, ADR-121)
- **Reliable publication:** a small module-private **outbox** table, written in the same transaction as the message. Details in ADR-119, with an honest limit: the shared event bus is in-process only, so a cron-run relay script cannot reach subscribers living in the API process. That limit matters the day Notification exists, and is documented rather than hidden.
- **Rate limiting:** a small in-process limiter behind a port. It is per-process, same limitation as the connection registry. One real touch to Phase 2: a new shared error category so "too many requests" can be a real `429` instead of being forced into an unrelated category. (ADR-122)

### FINDING 2 — WebSocket authentication can't simply reuse the HTTP dependency

`get_current_identity_id` reads an `Authorization: Bearer` header from an HTTP request. Browsers can't set that header on a WebSocket. And Identity's `decode_access_token` returns only an identity id — it doesn't expose the token's expiry.

The handoff forbids both a new auth system and secrets in URLs. The approach that satisfies both: the client connects, then sends its **existing access token as the very first frame**. The server validates it with the *same* decode primitive HTTP uses, so there's one authentication mechanism, not two. This needs one small, behavior-preserving extraction in `platform/security/authentication.py` (exactly the kind of location-only change Module 2's ADR-031 made). Because Identity doesn't expose token expiry and I'm not changing Identity for this, the server caps how long a connection stays authenticated with its own setting (default 15 minutes, matching the access-token lifetime) and requires a fresh `auth` frame after that. (ADR-118)

### FINDING 3 — Media/File isn't ready for message attachments, and that's a design decision, not a missing line of code

The handoff allows deferring attachments "if the Media/File contract is not ready." It isn't, for a reason worth understanding:

- Media/File's upload purposes are a fixed, code-defined list (avatar, listing photo, verification evidence). There is no message-attachment purpose.
- Media/File's ADR-079 says uploads happen *only* through the owning module's own endpoint — never "upload, then attach later." A message with `media_ids` is exactly "upload, then attach later." Doing it safely means Messaging staging pending uploads per conversation, a new private-access endpoint with Messaging's own authorization (the way Verification's `GetEvidenceAccess` works), and orphan cleanup.

That's a real, separate design — the same size as the University migration or the Verification media amendment — not a corner of this module. **Attachments are deferred (ADR-124).** The schema leaves a clean additive seam. I'd suggest a short follow-up "Messaging Attachments Amendment" after this ships. Nothing is silently dropped: any request containing `media_ids` is rejected with a clear `422`, not ignored.

### FINDING 4 — your deployment is single-process, and the handoff asks for that to be decided deliberately

Everything so far runs `uvicorn camp_match.main:app` as one process in Termux. The handoff says: if explicitly single-process, an in-memory connection registry is fine *provided the limitation is documented and the seam is preserved.* I'm taking that path (ADR-123): no Redis, no broker. The realtime gateway sits behind a port, there's a settings switch with exactly one valid value today, and a reusable contract test any future cross-process adapter must pass. **This needs your confirmation** (Decision 1 below). If you plan to run multiple workers soon, tell me before Chunk 13.

### FINDING 5 — Booking already told us Messaging would surface "who is the other person"

Booking's Chunk 11 deliberately returns no student name to providers and says: *"If a provider genuinely needs to know who they're renting to, that's Messaging's future concern."* So an inbox that shows only an opaque id would be a real product gap, and Messaging is where it belongs. It gets a Profile-backed **display-info** lookup (name, profile type, profile id — never phone, never preferences), with graceful degradation to `null` if Profile can't answer. This is a bounded N+1 (one lookup per distinct counterpart on one inbox page, page size capped); that cost is stated in the docs, not hidden. (ADR-127)

No contradictions were found otherwise.

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-112 … ADR-128)
Continuing the log from Phase 1–3 (001–013) through Payment (103–111).

| ADR | Decision | Why |
|---|---|---|
| 112 | Messaging is Module 11. REST lives under `/api/v1/messaging/…`, WebSocket at `/api/v1/messaging/ws` | Matches Verification's `/api/v1/verification/…` precedent and the project rule that business endpoints live under `/api/v1`. The handoff's `/ws/messaging` and flat `/conversations` were candidates, not mandates. |
| 113 | Every conversation is **context-bound**: `LISTING` or `BOOKING`, never a free-form direct message. Deduplication is one unique `dedupe_key` column: `listing:{listing_id}:{enquirer_id}` or `booking:{booking_id}`. Creation is `INSERT … ON CONFLICT DO NOTHING`, then read the winner | The handoff says this is "not a public chat network." One unique column enforced by the database is the simplest thing that survives two simultaneous taps, and is the same database-guarantees-it-first pattern as every uniqueness rule since Module 1. |
| 114 | **Authoritative order = a per-conversation, gap-free `sequence`**, assigned by one atomic `UPDATE conversations SET last_sequence = last_sequence + 1 … RETURNING` inside the send transaction. Timestamps are display data only | The row lock from that single statement serializes concurrent senders, so sequences commit in order with no gaps and no ties — the same atomic-conditional-write discipline as Housing's reservation. Message ids are UUID4 (ADR-006) and aren't sortable, so they can't be the order. |
| 115 | **Read state is per participant**: `last_read_sequence` on the participant row, advanced only by a monotonic conditional `UPDATE … WHERE last_read_sequence < :new`. Unread counts are **derived at query time** with one batched query per inbox page, never a stored counter. The sender's own messages are never "unread" to them. Sending does **not** auto-advance your own read position | The derive-don't-cascade idiom, seventh instance. A conditional update makes repeats safe and concurrent updates unable to regress the position. |
| 116 | **Idempotency:** `client_message_id` is **required** on every send (HTTP and WebSocket), 1–64 chars of `[A-Za-z0-9_-]`, unique per `(sender_id, client_message_id)` in the database. A replay returns the original message (`200`, `replayed: true`, no new event). The same key with different content or a different conversation is `409 client_message_id_conflict` | Matches Booking's/Payment's `(student_id, idempotency_key)` precedent. Required rather than optional because the lost-acknowledgement case (the handoff's 15.4) is exactly when a client needs it, and optional keys leave a gap exactly where retries happen. |
| 117 | **Use cases are transport-neutral. HTTP and WebSocket adapters only parse, call, and serialize.** Live delivery goes through a `RealtimeGateway` port, called best-effort *after* commit. The database is the only source of truth; a failed push never affects the saved message | The handoff's central requirement. Making realtime best-effort, with durability coming only from history, is what lets a socket drop, a worker die, or a push fail without any message meaning changing. |
| 118 | **WebSocket auth:** the client's first frame is `auth` carrying its existing access token; validated by the same decode primitive HTTP uses (extracted to `platform/security/authentication.py`, location change only). No token ever appears in a URL. A connection's authenticated lifetime is capped by `messaging_ws_auth_ttl_seconds` (default 900); after that, commands fail with `auth_expired` until a new `auth` frame for the **same** identity succeeds, or the socket closes | Finding 2. Cap exists because Identity doesn't expose token expiry and this module must not change Identity. Revocation caveat, stated plainly: access tokens are stateless in Identity and can't be individually revoked; the real defenses are the 15-minute cap and the account-status check on every protected operation. |
| 119 | **Reliable publication via a module-private outbox.** Send writes message + outbox row in one transaction. After commit it makes a best-effort dispatch of that row to the shared `EventBus`; any row left undispatched is picked up by `scripts/run_messaging_outbox_relay.py` (plain script, no scheduler — same pattern as `expire_booking_holds.py`). Delivery is **at-least-once**; `event_id` is stable across retries so consumers dedupe. Only `MessageCreated` is published, carrying no message body | Finding 1. No `ConversationCreated`, `ReadAdvanced` etc. — no subscriber exists, same reasoning as Identity ADR-022. |
| 120 | **Eligibility gate:** a new role-scoped Security permission `MESSAGING_PARTICIPATE`, granted to `STUDENT` and `SCOUT` only (so you need a profile to message; `ADMIN`/`OPERATIONS` hold nothing), **plus** Identity account status `ACTIVE` for the actor on every operation and for the counterpart on create/send, via `CommunicationRestrictionProvider` | Security's documented two-line recipe, used again. Checking account status per operation (a primary-key lookup, no cache) is what makes "a restriction introduced after connection takes effect on the next protected operation" literally true. |
| 121 | Notification and Trust & Safety do not exist. Messaging's only integration points are the `MessageCreated` event and the `CommunicationRestrictionProvider` port. Blocking, reporting, moderation queues are **unbuilt and documented as dependencies** | Finding 1. A port with a real adapter today (Identity status), not a stub that always says yes. |
| 122 | Rate limiting: a small `RateLimiter` port with an **in-process sliding-window adapter** owned by Messaging. New shared `RateLimitedError(ApplicationError)` → HTTP `429` (with `Retry-After`) added to Phase 2's errors and the platform error handlers | The one place this module genuinely needs a category the five-way error shape lacks. Per-process limitation documented, same as the connection registry. |
| 123 | **Single-process realtime for the MVP.** In-memory connection registry behind `RealtimeGateway`; `messaging_realtime_backend` setting accepts exactly one value, `in_memory`, and any other value fails startup. A reusable `RealtimeGateway` contract test is written so a future cross-process adapter has a defined bar to meet | Finding 4. No claim of cross-worker delivery anywhere. |
| 124 | **Attachments deferred** to a follow-up amendment. Requests containing `media_ids` get `422` | Finding 3. |
| 125 | A nonparticipant gets **`404 conversation_not_found`**, identical to a nonexistent id | Knowing an id must not even confirm it exists. A deliberate difference from Profile/Housing's 403-on-ownership, because conversation ids are guessable-in-principle private identifiers. |
| 126 | **Policies, stated once.** New `LISTING` conversation: listing must exist and be `PUBLISHED` (a sold-out `PUBLISHED` listing still allows enquiry — availability is derived, not a status). New `BOOKING` conversation: caller must be the booking's student or the property's provider, and the booking must be `AWAITING_PAYMENT` or `CONFIRMED`. **Existing conversations are never closed or blocked by listing/booking state changes** — history stays, sending continues. A booking conversation is separate from a listing conversation between the same two people | Handoff 6.2/6.4/6.5. Messaging creates no state of its own for this; there is no conversation `status` column in the MVP. |
| 127 | Inbox/detail show the counterpart's `profile_id`, `display_name`, `profile_type` through a Profile-backed `ProfileProvider`; `null` if unavailable | Finding 5. |
| 128 | Messages are **immutable and never deleted**; there are no edit/delete endpoints, and **no administrative way to browse conversations** | Handoff 4.2 and 13.4. Least privilege by absence. |

### Three decisions I need you to confirm before Chunk 1 (not just information)

1. **ADR-123 — single process.** Confirm you're running one `uvicorn` process for the foreseeable MVP. If not, tell me now; cross-worker delivery changes Chunk 13 materially.
2. **ADR-126 — sold-out listings.** I allow starting an enquiry on a `PUBLISHED` listing even if it has zero availability ("will anything open up?"). Say so if the product would rather block it. It's one condition in one use case.
3. **ADR-124 — attachments deferred.** Say so if image-in-chat is needed for the first release; then the amendment becomes the next spec, not "someday."

---

## PART C — DESIGN SPECIFICATION
**[FOR YOU — GEMINI CLI — paste with Chunk 1. Read fully before writing anything.]**

This part fixes the target design. Part D tells you how to build it, one chunk at a time. Where a chunk and this part appear to disagree, **stop and report** instead of choosing.

### C1. Non-negotiable rules specific to this module
1. **One implementation per capability.** Sending, reading, creating conversations, authorizing access exist **once**, in `application/use_cases/`. The HTTP router and the WebSocket handler parse input, call a use case, and serialize the result. If you find a business rule in either adapter, it's in the wrong place.
2. **The application layer never sees a socket.** No `WebSocket`, no connection id, no frame format, no `Request`, below `adapters/`.
3. **Never hold a database session across an `await` on a socket.** A WebSocket connection lives minutes or hours; the pool defaults to 5. Every command is handled with a **fresh, short-lived session/UoW** built from `app.state.db_session_factory`, closed before the next frame is awaited. Do **not** use `Depends(get_db_session)` on the WebSocket endpoint. (Chunk 10 has a test that proves this.)
4. **No cross-module imports except `application.ports`** (the established adapter rule). Messaging consumes: Housing's `GetListing` and `GetProperty`; Booking's `GetBooking`; Identity's `GetIdentityById`; Profile's `GetCurrentUserProfile`; Security's `AuthorizationService`. Never their `adapters` or `domain`.
5. **Never log message content, access tokens, or `Authorization` values.** Log ids, lengths, sequences, close codes. A log-capture test enforces it.
6. **Never take sender, participant, timestamp, sequence, or read state from the client.**

### C2. Module layout
```
src/camp_match/modules/messaging/
├── domain/        value_objects.py  entities.py  events.py
├── application/
│   ├── errors.py
│   ├── ports/     inbound.py  outbound.py
│   ├── services/  participant_guard.py          # shared authorization helper, not a port
│   └── use_cases/ find_or_create_conversation.py  list_conversations.py  get_conversation.py
│                  send_message.py  get_message_history.py  mark_conversation_read.py
│                  authorize_connection.py  authorize_subscription.py  dispatch_outbox_events.py
└── adapters/
    ├── persistence/   models.py  repository.py  outbox_repository.py
    ├── listing/       listing_provider.py       # Housing
    ├── booking/       booking_provider.py       # Booking
    ├── profile/       profile_provider.py       # Profile (display info)
    ├── restriction/   identity_restriction_provider.py
    ├── ratelimit/     in_memory_rate_limiter.py
    ├── realtime/      connection_manager.py  in_memory_gateway.py
    ├── events/        eventbus_dispatcher.py    # outbox → shared EventBus
    └── api/           schemas.py  router.py  dependencies.py
                       ws_protocol.py  ws_handler.py  ws_router.py
scripts/run_messaging_outbox_relay.py
scripts/messaging_ws_client.py                   # manual-testing helper (Chunk 16)
```

### C3. Domain model

**`ConversationContext`** (value object) — `type` (`LISTING` | `BOOKING`), exactly one of `listing_id` / `booking_id` (the other is `None`; both set or neither raises `ValueError`). Provides `dedupe_key(enquirer_id)`: `listing:{listing_id}:{enquirer_id}` or `booking:{booking_id}` (ADR-113).

**`Conversation`** — `id`, `context`, `participant_ids` (exactly two **distinct** `EntityId`s — fewer, more, or equal raises at construction; this is the one-to-one invariant), `dedupe_key`, `last_sequence` (int ≥ 0), `last_activity_at`, `created_at`. `id`, `context`, `participant_ids` permanent. No status field (ADR-126). Method `counterpart_of(user_id)` raising `ValueError` for a non-member.

**`ConversationParticipant`** — `conversation_id`, `user_id`, `joined_at`, `last_read_sequence` (int ≥ 0, default 0), `last_read_message_id` (`EntityId | None`), `last_read_at` (`datetime | None`).

**`Message`** — `id`, `conversation_id`, `sender_id`, `sequence` (int ≥ 1), `content`, `client_message_id`, `created_at`. Immutable (frozen). No edit method exists.

**`MessageContent`** — `create(raw: str, max_length: int)`: strip surrounding whitespace; empty after strip raises; longer than `max_length` raises (**never truncates**); internal newlines preserved. Raises `ValueError`; the use case turns that into `InvalidMessageContent`.

**`ClientMessageId`** — 1–64 chars matching `^[A-Za-z0-9_-]+$`, else `ValueError`.

**`SequenceCursor`** — opaque string cursor: `base64url("s:" + str(sequence))`. `encode(sequence)`, `decode(raw) -> int` (any malformed/negative/non-`s:` value raises `ValueError` → `InvalidHistoryCursor`). Opaque to clients so the representation can change.

**Read-position rule (pure function):** `should_advance(current_sequence, target_sequence) -> bool` — true only when `target > current`. Used by the use case; the database repeats the same rule in its conditional `UPDATE` (defense in depth).

**Domain event** `MessageCreated` (extends shared-kernel `DomainEvent`) — `message_id`, `conversation_id`, `sender_id`, `recipient_id`, `sequence`, `context_type`, `message_created_at`. **No content.** Must round-trip losslessly (same `event_id`, same `occurred_at`) through a JSON payload — the outbox depends on it.

**Tests (Chunk 2):** every invariant above, individually.

### C4. Database (all tables prefixed `messaging_`; no foreign keys into any other module)

**`messaging_conversations`**
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `context_type` | text | `CHECK IN ('LISTING','BOOKING')` |
| `listing_id`, `booking_id` | UUID | nullable, no FK. `CHECK` that exactly the one matching `context_type` is non-null |
| `dedupe_key` | text | not null, **unique** (ADR-113) |
| `last_sequence` | bigint | not null, default 0, `CHECK >= 0` — the sequence generator (ADR-114) |
| `last_activity_at` | timestamptz | not null; set to creation time, then only ever raised via `GREATEST(...)` |
| `created_at`/`updated_at` | timestamptz | server defaults |

**`messaging_participants`**
| Column | Type | Notes |
|---|---|---|
| `conversation_id` | UUID | FK → conversations (same module) |
| `user_id` | UUID | no FK (cross-module identity reference) |
| `joined_at` | timestamptz | |
| `last_read_sequence` | bigint | not null, default 0, `CHECK >= 0` |
| `last_read_message_id` | UUID | nullable, FK → messages; written in the **same** `UPDATE` as `last_read_sequence`, so they can't disagree |
| `last_read_at` | timestamptz | nullable |
PK `(conversation_id, user_id)`; index on `(user_id)` (inbox lookup).

**`messaging_messages`**
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `conversation_id` | UUID | not null |
| `sender_id` | UUID | not null |
| `sequence` | bigint | not null, `CHECK >= 1` |
| `content` | text | not null, `CHECK (char_length(content) BETWEEN 1 AND 10000)` — a hard database ceiling above the configurable limit, so a config change can never need a migration |
| `client_message_id` | text | not null |
| `created_at` | timestamptz | not null — supplied from the injected `Clock` (business-meaningful, per `07_DATABASE_RULES.md`) |

Constraints: **unique `(conversation_id, sequence)`** (also serves history and unread queries); **unique `(sender_id, client_message_id)`** (ADR-116); **composite FK `(conversation_id, sender_id)` → `messaging_participants (conversation_id, user_id)`** — the database itself refuses a message from a non-member.

**`messaging_outbox`**
| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK; **this is the event's `event_id`** and never changes |
| `event_type` | text | `MessageCreated` |
| `payload` | jsonb | the event fields (ids as strings; no content) |
| `occurred_at` | timestamptz | |
| `dispatched_at` | timestamptz | nullable |
| `attempts` | integer | not null, default 0 |
| `last_error` | text | nullable — exception **class name only**, never a message or payload |
Partial index on `(occurred_at) WHERE dispatched_at IS NULL`.

One migration (`add messaging tables`), read before applying — four tables, several `CHECK`s, one composite FK, one partial index.

### C5. Ports

**Inbound** (`Protocol` + `execute`, plain `@dataclass` request/response, `actor_id: str` first on everything user-initiated — consistent with every earlier module): `FindOrCreateConversation`, `ListConversations`, `GetConversation`, `SendMessage`, `GetMessageHistory`, `MarkConversationRead`, `AuthorizeConnection`, `AuthorizeSubscription`, `DispatchOutboxEvents`.

**Outbound** (Messaging's own copies, per the established discipline):
- **`ConversationRepository`** — `add(conversation) -> bool` (`False` on `dedupe_key` conflict), `get_by_id`, `get_by_dedupe_key`, `list_for_participant(user_id, page_request) -> Page`, `get_participant(conversation_id, user_id)`.
- **`MessageRepository`** — `next_sequence(conversation_id, message_created_at) -> int` (the atomic bump from ADR-114: one `UPDATE … SET last_sequence = last_sequence + 1, last_activity_at = GREATEST(last_activity_at, :ts) … RETURNING last_sequence`), `add(message)` (raises `DuplicateClientMessageId` — an internal signal, not an application error — on the `(sender_id, client_message_id)` unique violation; never lets a raw database error escape), `get_by_client_message_id(sender_id, client_message_id)`, `get_in_conversation(conversation_id, message_id)`, `list_tail(conversation_id, limit)`, `list_before(conversation_id, sequence, limit)`, `list_after(conversation_id, sequence, limit)`, `last_messages(conversation_ids) -> dict` (joins on `conversations.last_sequence` — one query for a whole inbox page), `unread_counts(user_id, conversation_ids) -> dict` (one grouped query, see C7), `advance_read_position(conversation_id, user_id, sequence, message_id, at) -> bool` (the conditional `UPDATE … WHERE last_read_sequence < :sequence`; `False` means "no change", which is success).
- **`OutboxRepository`** — `add(event)`, `get(event_id)`, `claim_pending(limit)` (`SELECT … FOR UPDATE SKIP LOCKED` inside the dispatch transaction), `mark_dispatched(event_id, at)`, `record_failure(event_id, error_class_name)`.
- **`ListingProvider`** — `get_listing_context(listing_id) -> ListingContext | None` (`provider_id`, `status` as a string), `get_property_owner(property_id) -> EntityId | None`. Implemented by calling Housing's `GetListing` then `GetProperty`.
- **`BookingProvider`** — `get_booking_context(booking_id, requester_id) -> BookingContext | None` (`student_id`, `property_id`, `listing_id`, `status`). Calls Booking's `GetBooking` **as the requester**, so Booking's own visibility rule (student, property owner via `HOUSING_MANAGE`, admin) is the first gate; `BookingNotFound` **and** `Forbidden` both map to `None`. Messaging then re-checks that the requester is exactly the student or the property's owner, so an admin's bypass never makes a third person a participant.
- **`ProfileProvider`** — `get_display_info(identity_id) -> ParticipantDisplay | None` (`profile_id`, `display_name`, `profile_type` string only).
- **`CommunicationRestrictionProvider`** — `check(actor_id, counterpart_id | None) -> RestrictionDecision(allowed: bool, reason: str | None)`. Today's adapter asks Identity's `GetIdentityById`: actor must be `ACTIVE`; if a counterpart is supplied, they must be `ACTIVE` too; an unknown identity is not allowed. This is the seam a future Trust & Safety module (blocks, suspensions) plugs into.
- **`RealtimeGateway`** — `push(user_ids, event: RealtimeEvent) -> None`. Best-effort by contract; never raises to the caller for delivery problems.
- **`MessageEventDispatcher`** — `dispatch(event_id) -> None`. Best-effort single-row dispatch used right after commit.
- **`RateLimiter`** — `check(key: str, limit: int, window_seconds: int) -> RateLimitResult(allowed: bool, retry_after_seconds: int)`.
- Reused directly: shared-kernel `Clock`, `EntityId`, `Page`/`PageRequest`, `UnitOfWork`, `EventBus`; Security's `AuthorizationService`.

### C6. Application services and use-case steps

**`ParticipantGuard.require_participant(actor_id, conversation_id) -> Conversation`** (a plain application service, used by every conversation-scoped use case so the rule exists once):
1. `CommunicationRestrictionProvider.check(actor_id, None)` — not allowed → `CommunicationRestricted`.
2. `AuthorizationService.authorize(actor_id, Permission.MESSAGING_PARTICIPATE)` — anything but `ALLOWED` raises Security's existing `Forbidden`.
3. Load the conversation; if absent **or the actor isn't a member**, raise `ConversationNotFound` (ADR-125 — same error either way).

**`FindOrCreateConversation`** — input: `context_type`, `listing_id` or `booking_id`.
1. Rate limit `conversation_create:{actor}` → `RateLimitExceeded`.
2. Steps 1–2 of the guard (restriction on actor; `MESSAGING_PARTICIPATE`).
3. Resolve context. `LISTING`: `get_listing_context`; absent → `ConversationContextNotFound`; counterpart = `provider_id`; if `actor == provider_id` → `SelfConversationNotAllowed`. `BOOKING`: `get_booking_context(booking_id, actor)`; `None` → `ConversationContextNotFound`; resolve the property owner via `ListingProvider.get_property_owner`; actor must equal `student_id` or that owner, else `ConversationContextNotFound`; counterpart = the other one.
4. Compute `dedupe_key` and look up an existing conversation. **If found, return it (`created = False`) — even if the listing/booking has since changed state** (ADR-126).
5. Only when creating: `LISTING` requires status `PUBLISHED`; `BOOKING` requires `AWAITING_PAYMENT` or `CONFIRMED` — else `ConversationContextUnavailable`.
6. Restriction check with the counterpart supplied → `CommunicationRestricted`.
7. In a `UnitOfWork`: `ConversationRepository.add` (conversation + both participants in one transaction). If it returns `False` (a concurrent request won), read the existing row by `dedupe_key` and return it with `created = False`. **Never** check-then-insert.
8. Log INFO `conversation_created` (ids, context type — nothing else). Return the conversation view.

**`SendMessage`** — input: `conversation_id`, `client_message_id`, `content`; also rejects any `media_ids` at the adapter schema level (ADR-124).
1. Rate limit `message_send:{actor}`.
2. `ParticipantGuard.require_participant` → conversation.
3. Restriction check with the counterpart → `CommunicationRestricted`.
4. Build `ClientMessageId` and `MessageContent` (limits from `Settings`); `ValueError` → `InvalidClientMessageId` / `InvalidMessageContent`.
5. **Idempotency lookup** by `(actor, client_message_id)`: found with the same conversation and identical content → return it as a **replay** (`replayed = True`; steps 6–7 do not run; nothing is published); found otherwise → `ClientMessageIdConflict`.
6. In one `UnitOfWork`: `next_sequence` (takes the row lock) → build the `Message` with `created_at = clock.now()` → `MessageRepository.add` → `OutboxRepository.add(MessageCreated …)` → commit. On `DuplicateClientMessageId` (a concurrent identical send won the race): roll back, reload by `(actor, client_message_id)`, and apply step 5's replay-or-conflict rule. A rollback leaves no sequence gap because the bump rolls back too.
7. **After commit, each step independently best-effort** (catch everything, log WARNING with ids only, never change the result): `RealtimeGateway.push([both participants], message.created event)`, then `MessageEventDispatcher.dispatch(event_id)`. These use their **own** sessions; they are not part of the committed transaction.
8. Log INFO `message_sent` (message id, conversation id, sequence, `content_length`). Return `SendMessageResult(message, replayed)`.

**`GetMessageHistory`** — input: `conversation_id`, `limit`, optional `before` **or** `after` cursor (both given → `InvalidHistoryCursor`). Guard first. `limit` default 30, max 100 (settings); out of range → `ValidationError`. Fetch `limit + 1` rows in the requested direction to learn whether more exist without a count query. **Items are always returned in ascending `sequence` order.**
- no cursor → the newest `limit` messages;
- `before=c` → up to `limit` messages with `sequence < c`, ending immediately before `c`;
- `after=c` → up to `limit` messages with `sequence > c`, starting immediately after `c`.

Response: `items`, `has_older`, `has_newer`, `older_cursor` (cursor of the first item; use with `before`), `newer_cursor` (cursor of the last item; use with `after`). `has_newer` is `false` for the no-cursor query and `true` for a `before` query. Every item carries `sequence` and its own `cursor`. `client_message_id` appears on an item **only when the viewer is its sender** (this is how a client that lost an acknowledgement matches its pending send to history).

**`MarkConversationRead`** — input: `conversation_id`, `up_to_message_id`. Guard; `get_in_conversation` — absent, **or belonging to a different conversation**, → `InvalidReadPosition` (one error for both; don't reveal which); if `should_advance(current, target)` is false, return success with the **current** state (idempotent, no write); otherwise `advance_read_position` (a `False` return from a lost race is also success — someone else advanced it further). Return `last_read_message_id` and the recomputed `unread_count`.

**Unread definition (stated once):** for participant *P* in conversation *C*: the count of messages in *C* with `sender_id != P` and `sequence > P.last_read_sequence`. One grouped query for a whole inbox page:
`SELECT m.conversation_id, count(*) FROM messaging_messages m JOIN messaging_participants p ON p.conversation_id = m.conversation_id AND p.user_id = :me WHERE m.conversation_id = ANY(:ids) AND m.sender_id <> :me AND m.sequence > p.last_read_sequence GROUP BY m.conversation_id`.

**`ListConversations`** — actor eligibility (steps 1–2 of the guard only); `list_for_participant` ordered by `last_activity_at DESC, id DESC` (deterministic tie-break), shared `PageRequest`/`Page`; then **three batched lookups for the whole page, never per conversation**: `last_messages`, `unread_counts`, and `get_display_info` once per *distinct* counterpart. Preview = first 100 characters of the latest message's content, computed at read time. Never loads message history.

**`GetConversation`** — guard, then the same single-conversation view.

**`AuthorizeConnection(actor_id)`** — restriction check + `MESSAGING_PARTICIPATE` only. **`AuthorizeSubscription(actor_id, conversation_id)`** — `ParticipantGuard`. The WebSocket handler calls these; it contains no eligibility logic of its own.

**`DispatchOutboxEvents`** — `execute(limit)`: in a transaction, `claim_pending(limit)`; for each row rebuild the `MessageCreated` event (same `event_id`/`occurred_at`) and `EventBus.publish` it; success → `mark_dispatched`; an exception from `publish` → `record_failure(error class name)`, WARNING log, **continue with the rest**; commit. `dispatch_one(event_id)`: the same for a single row (skips silently if already dispatched or claimed elsewhere). Because the shared bus lets a handler exception escape `publish`, one failing subscriber leaves the row pending and it will be re-published to *all* subscribers later — consumers must dedupe on `event_id`.

### C7. Errors (`application/errors.py`; each extends a shared-kernel category and carries a `code`)

| Error | Extends | `code` |
|---|---|---|
| `ConversationNotFound` | `NotFoundError` | `conversation_not_found` |
| `ConversationContextNotFound` | `NotFoundError` | `conversation_context_not_found` |
| `SelfConversationNotAllowed` | `ForbiddenError` | `self_conversation_not_allowed` |
| `CommunicationRestricted` | `ForbiddenError` | `communication_restricted` |
| `ConversationContextUnavailable` | `ValidationError` | `conversation_context_unavailable` |
| `InvalidMessageContent` | `ValidationError` | `invalid_message_content` |
| `InvalidClientMessageId` | `ValidationError` | `invalid_client_message_id` |
| `InvalidHistoryCursor` | `ValidationError` | `invalid_history_cursor` |
| `InvalidReadPosition` | `ValidationError` | `invalid_read_position` |
| `ClientMessageIdConflict` | `ConflictError` | `client_message_id_conflict` |
| `RateLimitExceeded` | `RateLimitedError` (new, Chunk 3) | `rate_limit_exceeded` |

Message text for `CommunicationRestricted` is deliberately generic ("You can't send messages in this conversation right now.") whether the actor or the counterpart was the cause, so one user can't learn the other's account state. Database failure during a send is **not** wrapped in an application error: it propagates as an unexpected exception — the generic `500` over HTTP, an `internal_error` frame over WebSocket — and never produces a success acknowledgement (same stance as Media's `MediaUploadFailed`).

### C8. Settings (new fields in `config/settings.py` and `.env.example`; every limit configurable, none hard-coded in the connection manager)

| Setting | Default |
|---|---|
| `messaging_max_message_length` | 2000 |
| `messaging_history_default_limit` / `messaging_history_max_limit` | 30 / 100 |
| `messaging_send_rate_limit` / `_window_seconds` | 30 / 60 |
| `messaging_conversation_create_rate_limit` / `_window_seconds` | 10 / 3600 |
| `messaging_ws_auth_timeout_seconds` | 10 |
| `messaging_ws_auth_ttl_seconds` | 900 |
| `messaging_ws_reauth_grace_seconds` | 60 |
| `messaging_ws_idle_timeout_seconds` | 90 |
| `messaging_ws_max_frame_bytes` | 16384 |
| `messaging_ws_max_connections_per_user` | 5 |
| `messaging_ws_max_subscriptions_per_connection` | 50 |
| `messaging_ws_send_timeout_seconds` | 5 |
| `messaging_ws_command_rate_limit` / `_window_seconds` | 60 / 60 |
| `messaging_ws_connect_rate_limit` / `_window_seconds` (per client host) | 20 / 60 |
| `messaging_ws_max_protocol_violations` | 5 |
| `messaging_realtime_backend` | `in_memory` (only valid value, ADR-123) |
| `messaging_outbox_batch_size` | 100 |
| `messaging_debug_failing_subscriber` | `False` (honored only when `app_env` is `local`/`test`, Chunk 14) |

### C9. WebSocket protocol v1 (authoritative — Chunks 10, 11, 16 and the frontend docs all follow this)

**Envelope.** Text frames, JSON objects. Client → server: `{"type": "...", "request_id": "..."(optional, ≤64 chars, echoed back), …fields}`. Unknown fields are rejected (`extra="forbid"` on every command model). Server → client: `{"type": "...", …}`.

**Connection lifecycle.** The route is `GET /api/v1/messaging/ws` (WebSocket upgrade). The server accepts the upgrade, then waits up to `messaging_ws_auth_timeout_seconds` for the first frame, which **must** be `auth`. Anything else, malformed JSON, or silence → close `4401`. No conversation data is sent before `auth.ok`.

| Client command | Fields | Server response |
|---|---|---|
| `auth` | `access_token` | `auth.ok` `{user_id, protocol_version: 1, auth_expires_in_seconds}`; failure → close `4401`; not eligible (`AuthorizeConnection`) → close `4403`; too many connections for this user → close `4429` |
| `conversation.subscribe` | `conversation_id` | `subscribed` `{conversation_id}` — only after `AuthorizeSubscription`; limit per connection enforced |
| `conversation.unsubscribe` | `conversation_id` | `unsubscribed` `{conversation_id}` (idempotent) |
| `message.send` | `conversation_id`, `client_message_id`, `content` | `message.accepted` `{request_id, message, replayed}` **only after the message is committed** |
| `read.advance` | `conversation_id`, `up_to_message_id` | `read.accepted` `{request_id, conversation_id, last_read_message_id, unread_count}` |
| `ping` | — | `pong` |

| Server event | When | Fields |
|---|---|---|
| `message.created` | a new message was committed in a conversation **this connection is subscribed to** (delivered to both participants' subscribed connections — including the sender's other devices, and the originating connection) | `event_id`, `message` |
| `error` | any failed command | `{request_id?, code, message}` using the same `code` values as HTTP (`conversation_not_found`, `communication_restricted`, `rate_limit_exceeded`, `invalid_message_content`, …) plus protocol codes below |
| `auth.expired` | the connection's authenticated lifetime ran out | — (see below) |

**Protocol error codes** (in `error` frames): `invalid_json`, `invalid_command` (schema failure, unknown field, missing field), `unknown_command`, `auth_required`, `auth_expired`, `subscription_limit`, `internal_error`.

**Rules.**
- `message.accepted` ≠ `message.created`. The first is the sender's receipt after persistence; the second is the live event. The originating connection can receive **both** for one message; clients dedupe on `message.id`.
- Live events can arrive out of order across concurrent senders (post-commit pushes race). Every message carries `sequence`; a client that sees a sequence jump fetches `GET …/messages?after=<its last cursor>`. This is also the reconnection path.
- Re-authentication: when the auth TTL elapses the server sends `auth.expired`; every command except `auth`/`ping` then returns `error auth_expired`; a valid `auth` frame for the **same** user restores it; no valid `auth` within `messaging_ws_reauth_grace_seconds` → close `4401`. A different user's token is rejected with close `4401`.
- Idle: no frame of any kind from the client within `messaging_ws_idle_timeout_seconds` → close `4408`. Clients send `ping` roughly every 30 seconds.
- Frame larger than `messaging_ws_max_frame_bytes` → close `1009`. More than `messaging_ws_max_protocol_violations` malformed frames → close `4400`. Command rate exceeded → `error rate_limit_exceeded` (connection stays open).
- Close codes: `4400` protocol abuse · `4401` unauthenticated/auth failed/timeout · `4403` not eligible · `4408` idle · `4429` too many connections · `1009` frame too large · `1011` internal. Never put a reason string containing a token or user data in a close frame.

### C10. Touch map — the **only** files outside `modules/messaging/` this module changes
| File | Change | Chunk |
|---|---|---|
| `shared_kernel/application/errors.py` | add `RateLimitedError(ApplicationError)` | 3 |
| `platform/errors/http_error_handlers.py` | `RateLimitedError` → `429` (+ `Retry-After` when set), WARNING log | 3 |
| `modules/security/domain/value_objects.py`, `policy.py` | add `MESSAGING_PARTICIPATE` (role-scoped) → `STUDENT`, `SCOUT` | 5 |
| `platform/security/authentication.py` | extract a token-decode helper reused by `get_current_identity_id` (**behavior unchanged**) | 10 |
| `config/settings.py`, `.env.example` | C8 settings | 3 |
| `app.py` | mount the REST router and the WebSocket router; build connection manager / rate limiter in `lifespan` on `app.state` (not module globals) | 9–10 |
| `pyproject.toml` | import-linter contracts | 15 |
| `scripts/` | two new scripts | 14, 16 |

**Not touched:** Identity, Profile, University & Location, Housing, Search, Media/File, Verification, Booking, Payment. After every chunk that touches shared code, re-run the affected modules' suites and confirm they are unchanged.

---

## PART D — CHUNKED IMPLEMENTATION

**Do not give Gemini more than one chunk at a time.** Wait for each Completion Report before issuing the next. Each chunk below lists only what is specific to it; Part C is the design, the Standing Instructions are already in `AI_instructions/`. Use the standard `CURRENT_TASK.md` status-block format throughout. **A failed acceptance item means stop and report — never skip, weaken, or work around a test.**

---

### CHUNK 1 — REPOSITORY INSPECTION, ARCHITECTURE MAPPING & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** confirm this specification's assumptions against the real repository, and create the empty module structure. No behavior.

**Implementation instructions:**
1. Read `AI_instructions/` in full, `AI_state/CURRENT_STATE.md`, `ARCHITECTURE_STATE.md`, `DATABASE_STATE.md`, `API_STATE.md`, and `docs/modules/` for identity, profile, security, housing, booking, media, payment.
2. Inspect and record exact signatures/shapes for each of these — they are what Messaging will call:
   - Identity's `GetIdentityById` (request, response, `IdentityNotFound`).
   - Profile's `GetCurrentUserProfile` (accepts an arbitrary `identity_id`? what exactly does the response carry for `display_name`/`profile_type`/`id`?).
   - Housing's `GetListing` and `GetProperty` (does `GetListing` return `property_id` and `status`; does `GetProperty` return `provider_id`).
   - Booking's `GetBooking` (**how does it take the caller's identity**, which errors does it raise for not-found vs not-permitted, what fields does the response carry: `student_id`, `property_id`, `listing_id`, `status`).
   - Security's `AuthorizationService` and the `Forbidden` class; the exact steps to add a `Permission`.
   - `platform/security/authentication.py`: **exactly how `get_current_identity_id` obtains and calls the token-decode capability.** Is the decode logic callable without a `Request`? (Chunk 10 depends on the answer.)
3. Inspect infrastructure: `shared_kernel` (`EventBus`, `InMemoryEventBus` behavior when a handler raises, `UnitOfWork`, `Page`, `Clock`); how `app.py` composes modules and uses `lifespan`; how the existing **concurrency tests** (Housing's, Booking's, Payment's) provision *committed* data and run genuinely concurrent requests — Messaging's concurrency tests must reuse that technique.
4. Confirm: no existing messaging/WebSocket code, no rate limiter, no outbox, no Notification or Trust & Safety code anywhere. **Report anything that exists — it changes the plan.**
5. Confirm the WebSocket server dependency is present and importable under Termux (`poetry run python -c "import websockets"`), since `uvicorn[standard]` is expected to supply it. **If it isn't, that is a blocker — report it, do not substitute a library.**
6. Determine and record the WebSocket **test technique**: the project's API tests use `httpx.AsyncClient` with `ASGITransport`, which does not speak WebSocket. Preferred: a pytest fixture that runs the app under `uvicorn.Server` on an ephemeral port in the test's event loop, with the `websockets` client library (already installed per step 5) for sockets and `httpx` for REST against the same server. Confirm it can share the project's test-database strategy. Report the plan; do not build it yet.
7. Create the empty structure from Part C2 (every file with a one-line docstring, plus the matching `tests/unit|integration|api/messaging/` packages). No logic.
8. Do **not** modify any other module. Do not create `docs/modules/messaging.md` yet.

**Acceptance criteria:** a written report covering steps 2–6 — every signature stated exactly, every mismatch with this specification flagged, and an explicit "**proceed / blocked**" verdict; all scaffolding files importable; no file outside `modules/messaging/` and the test folders changed.

---

### CHUNK 2 — DOMAIN MODEL
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/value_objects.py`, `domain/entities.py`, `domain/events.py`.

Build exactly what Part C3 specifies: `ConversationContext` (with `dedupe_key`), `Conversation`, `ConversationParticipant`, `Message`, `MessageContent`, `ClientMessageId`, `SequenceCursor`, `should_advance`, and the `MessageCreated` event with its lossless JSON round trip (provide `to_payload()`/`from_payload()` on the event, or an equivalent pair, preserving `event_id` and `occurred_at`).

**Dependencies you may use:** shared-kernel `EntityId`, `DomainEvent`; stdlib (`dataclasses`, `enum`, `re`, `base64`, `datetime`, `json`). Nothing else.

**Tests you must write** (`tests/unit/messaging/domain/`), each as its own named test:
- `ConversationContext`: listing-only OK, booking-only OK, both/neither raises; `dedupe_key` shape for both types, and that two different enquirers on one listing produce different keys.
- `Conversation`: two distinct participants OK; one, three, or two equal raise; `counterpart_of` correct, and raises for a non-member; `id`/`context`/`participant_ids` have no mutation path.
- `MessageContent`: trims; empty and whitespace-only raise; exactly `max_length` OK, `max_length + 1` raises, **content is never truncated**; internal newlines preserved.
- `ClientMessageId`: valid forms; empty, 65 chars, spaces, and `/` all raise.
- `SequenceCursor`: round-trips; garbage, empty, negative, and a valid-base64-but-wrong-prefix value all raise.
- `should_advance`: equal → false, lower → false, higher → true.
- `MessageCreated`: payload round trip preserves `event_id` and `occurred_at`; payload contains **no content field**.
- `Message` is immutable.

**Acceptance criteria:** new tests pass; manually confirm no import outside the allowed list.

---

### CHUNK 3 — APPLICATION ERRORS, PORTS & THE TWO SHARED-KERNEL ADDITIONS
**[FOR YOU — GEMINI CLI]**

**Files to modify (this module):** `application/errors.py`, `application/ports/inbound.py`, `application/ports/outbound.py`. **Outside this module (ADR-122, small and explicit):** `shared_kernel/application/errors.py`, `platform/errors/http_error_handlers.py`, `config/settings.py`, `.env.example`.

1. **Shared kernel:** add `RateLimitedError(ApplicationError)` with an optional `retry_after_seconds: int | None` attribute. Nothing else changes in that file.
2. **Platform handler:** add a handler for `RateLimitedError` → `429`, same `{"error": {"code", "message"}}` shape, `Retry-After` header when `retry_after_seconds` is set, **WARNING** log (code and path, no traceback) — the same conventions as Identity's Chunk 8 handlers. Existing handlers untouched.
3. **Errors:** the eleven errors from Part C7, each with its exact parent and `code`.
4. **Ports:** every inbound and outbound port from Part C5, as `Protocol`s and plain `@dataclass` request/response types, every method `...`. Define the DTOs from the "Response shapes" table at the end of this chunk. Define `DuplicateClientMessageId` here as a plain internal exception (not an `ApplicationError`).
5. **Settings:** add every field in Part C8 with the stated defaults; `messaging_realtime_backend` is a `Literal["in_memory"]` so any other value fails settings validation at startup. Matching `.env.example` entries.

**Response shapes** (plain dataclasses; HTTP/WebSocket schemas are built from these later):
- `ParticipantView`: `user_id`, `profile_id | None`, `display_name | None`, `profile_type | None`.
- `MessageView`: `id`, `conversation_id`, `sender_id`, `content`, `sequence`, `cursor`, `created_at`, `client_message_id | None` (populated only for the viewer's own messages).
- `ConversationView`: `id`, `context_type`, `listing_id | None`, `booking_id | None`, `counterpart: ParticipantView`, `last_message: LastMessageView | None` (`id`, `sender_id`, `preview`, `sequence`, `created_at`), `last_activity_at`, `unread_count`, `last_read_message_id | None`, `created_at`.
- `FindOrCreateResult`: `conversation: ConversationView`, `created: bool`.
- `SendMessageResult`: `message: MessageView`, `replayed: bool`.
- `HistoryPage`: `items: list[MessageView]`, `has_older`, `has_newer`, `older_cursor | None`, `newer_cursor | None`.
- `ReadResult`: `conversation_id`, `last_read_message_id | None`, `unread_count`.
- `RealtimeEvent`: `type` (`message.created`), `conversation_id`, `event_id`, `payload: dict` — transport-neutral data only; no socket types.

**Tests you must write:** `tests/unit/messaging/application/test_errors.py` (parent class and exact `code` for each of the eleven); `tests/api/platform/test_error_mapping.py` extended: a test-only route raising `RateLimitedError` returns `429`, the standard shape, and `Retry-After` when set; `tests/unit/config/test_settings.py` extended: defaults load; an invalid `messaging_realtime_backend` fails validation.

**Acceptance criteria:** `poetry run mypy` clean on every file touched; new tests pass; the **full existing suite is unchanged** (`poetry run pytest`); the application layer imports nothing from `fastapi` or `sqlalchemy`.

---

### CHUNK 4 — PERSISTENCE, CONSTRAINTS & OUTBOX
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/persistence/models.py`, `adapters/persistence/repository.py`, `adapters/persistence/outbox_repository.py`.

Build the four tables exactly as Part C4, inheriting the shared `Base`, with the project naming convention. Implement `ConversationRepository`, `MessageRepository`, and `OutboxRepository` against Part C5's method list. Rules that are easy to get subtly wrong:

- `ConversationRepository.add` inserts the conversation with `INSERT … ON CONFLICT (dedupe_key) DO NOTHING`, and **only if a row was inserted** inserts the two participant rows in the same transaction; it returns `False` otherwise. It never raises on a `dedupe_key` collision.
- `MessageRepository.next_sequence` is **one statement**: `UPDATE messaging_conversations SET last_sequence = last_sequence + 1, last_activity_at = GREATEST(last_activity_at, :ts), updated_at = now() WHERE id = :id RETURNING last_sequence`. Never read-then-write. A missing row (no `RETURNING`) raises a plain internal error — the use case already verified the conversation exists.
- `MessageRepository.add` catches the `(sender_id, client_message_id)` unique violation **specifically** (by constraint name, not by catching all integrity errors — the composite-FK violation must stay distinguishable and loud) and raises `DuplicateClientMessageId`.
- `advance_read_position` is `UPDATE messaging_participants SET last_read_sequence = :s, last_read_message_id = :m, last_read_at = :t WHERE conversation_id = :c AND user_id = :u AND last_read_sequence < :s`; return `rowcount == 1`.
- `list_tail`/`list_before`/`list_after` always **return ascending `sequence`**, fetching with the correct internal ordering and reversing where needed; they accept `limit` and return up to `limit + 1` rows so the use case can compute `has_older`/`has_newer` (document which).
- `last_messages` and `unread_counts` are **single queries for a list of conversation ids** (Part C6) — never a loop.
- `OutboxRepository.claim_pending` uses `FOR UPDATE SKIP LOCKED` and must be called inside a transaction.
- Never return ORM rows outside this module's persistence files.

**Migration:** `poetry run alembic revision --autogenerate -m "add messaging tables"`. **Read it before applying** — confirm the composite FK, both unique constraints, every `CHECK`, and the partial index appear exactly as Part C4 states; hand-correct anything autogenerate missed.

**Tests you must write** (`tests/integration/messaging/`, marked `integration`, using the `db_session` fixture; each constraint test **bypasses the application layer** with raw inserts, same discipline as every earlier module):
- conversation add/get by id and by `dedupe_key`; a second `add` with the same key returns `False` and leaves exactly one conversation with exactly two participants;
- the `(conversation_id, sequence)` unique constraint; the `(sender_id, client_message_id)` unique constraint raises `DuplicateClientMessageId` through the repository;
- **the composite FK rejects a message whose sender is not a participant of that conversation** (raw insert);
- the `CHECK`s: both/neither context ids, negative `last_sequence`, empty content;
- `next_sequence`: 1, 2, 3 on successive calls; `last_activity_at` never decreases when called with an older timestamp;
- `list_*` ordering and `limit + 1` behavior at the exact page boundary, no overlap and no gap across `before` pages;
- `advance_read_position`: forward succeeds (`True`), equal/lower returns `False` and changes nothing;
- `last_messages` / `unread_counts` correct for several conversations in **one call** each (assert query count if the project has a query-counting helper; otherwise assert by inspecting the emitted SQL once);
- outbox: add, claim, mark dispatched, record failure increments `attempts` and stores only a class name; a second concurrent `claim_pending` does not return rows the first has claimed.

**Acceptance criteria:** tests pass against the local Termux Postgres; `poetry run alembic upgrade head` applies cleanly; `poetry run lint-imports` still clean (no SQLAlchemy outside `adapters/persistence/`).

---

### CHUNK 5 — CROSS-MODULE ADAPTERS, THE NEW PERMISSION & THE RATE LIMITER
**[FOR YOU — GEMINI CLI]**

**Objective:** everything the use cases will lean on that lives in another module, plus the small in-process limiter. Same narrow in-process-adapter pattern as every earlier module.

**Files to create:** `adapters/listing/listing_provider.py`, `adapters/booking/booking_provider.py`, `adapters/profile/profile_provider.py`, `adapters/restriction/identity_restriction_provider.py`, `adapters/ratelimit/in_memory_rate_limiter.py`.
**Files to modify (Security, its documented recipe, exactly these two):** `modules/security/domain/value_objects.py` (add `MESSAGING_PARTICIPATE`, `"messaging.participate"`, **role-scoped**), `modules/security/domain/policy.py` (grant to `STUDENT` and `SCOUT` only — **not** `ADMIN`, **not** `OPERATIONS`, ADR-120/128).

- **`InProcessListingProvider`**: calls Housing's `GetListing`, then `GetProperty` for `provider_id`; translates to Messaging's own `ListingContext` (status as a plain string). Not-found → `None`. `get_property_owner` likewise.
- **`InProcessBookingProvider`**: calls Booking's `GetBooking` **with the requester's identity**; maps Booking's not-found **and** its forbidden/not-permitted error both to `None` (so a non-party learns nothing). Use whatever exact error classes Chunk 1 found.
- **`InProcessProfileProvider`**: calls Profile's `GetCurrentUserProfile` for an arbitrary identity; maps **only** `profile_id`, `display_name`, `profile_type`; `ProfileNotFound` → `None`. **No phone, no preferences, no avatar, ever.**
- **`IdentityBackedRestrictionProvider`**: per Part C5 — actor `ACTIVE`; counterpart `ACTIVE` when supplied; `IdentityNotFound` or any non-`ACTIVE` status → `allowed=False` with a reason code (`account_not_active` / `counterpart_unavailable`) used only for logging. No caching.
- **`InMemorySlidingWindowRateLimiter`**: per-key timestamp deque; pruning on each check; uses the injected `Clock`; returns `retry_after_seconds` rounded up. Keys are namespaced by caller (`message_send:{id}` etc.). Bounded memory: drop a key's deque when it empties. Document that it is **per-process**.

**Import rule:** each adapter imports only the target module's `application.ports` (and use-case surface), never its `adapters`/`domain`.

**Tests you must write:**
- one unit test file per adapter with fakes for the use case it calls: mapping correct both ways; every `None`/not-found/forbidden path; the profile adapter's output has no field capable of carrying a phone number; the booking adapter maps `Forbidden` to `None`;
- `tests/unit/security/domain/test_policy.py` extended: `MESSAGING_PARTICIPATE` is granted to `STUDENT` and `SCOUT`, and is **not** in `ADMIN`'s or `OPERATIONS`' sets;
- limiter: allows up to the limit; the next call is denied with a positive `retry_after_seconds`; allowed again after the window (using `FixedClock`, no sleeping); two keys don't affect each other; empty keys are released.
- Re-run Security's, Identity's, Profile's, Housing's, Booking's suites and confirm they are unchanged apart from the one policy assertion.

**Acceptance criteria:** new tests pass; mypy clean; `lint-imports` clean; neighbouring suites unaffected.

---

### CHUNK 6 — CORE CONVERSATION USE CASES
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/services/participant_guard.py`, `application/use_cases/find_or_create_conversation.py`, `list_conversations.py`, `get_conversation.py`, `authorize_connection.py`, `authorize_subscription.py`.

Implement exactly the steps in Part C6 for `ParticipantGuard`, `FindOrCreateConversation`, `ListConversations`, `GetConversation`, `AuthorizeConnection`, `AuthorizeSubscription`. Shared fakes under `tests/support/messaging_fakes.py` (in-memory repositories, fake providers, a fake rate limiter, `FixedClock`) — reused by Chunks 7–8.

**Tests you must write** (against fakes — no database, no other module's real code):
- **Creation:** a Student creates a `LISTING` conversation with the listing's Scout (success, `created=True`); repeated call returns the same conversation with `created=False`; two different students enquiring on one listing get two different conversations; the provider enquiring on their own listing → `SelfConversationNotAllowed`; nonexistent listing → `ConversationContextNotFound`; `DRAFT`, `UNAVAILABLE`, `ARCHIVED` listing → `ConversationContextUnavailable` **for a new conversation**, but an **existing** conversation is still returned after the listing becomes `ARCHIVED` (ADR-126); a `PUBLISHED` listing with zero availability still allows creation.
- **Booking context:** the booking's student and the property's owner can each open it, the other being the counterpart; a third user, and an admin who is neither, → `ConversationContextNotFound`; `CANCELLED`/`EXPIRED` booking blocks a **new** conversation but not an existing one; a listing conversation and a booking conversation between the same two people are two conversations.
- **Eligibility:** actor with no profile (`MESSAGING_PARTICIPATE` denied) → Security's `Forbidden`; suspended/disabled actor → `CommunicationRestricted`; disabled **counterpart** at creation → `CommunicationRestricted` with the generic message; rate limit exceeded → `RateLimitExceeded`.
- **Concurrency seam (unit level):** a fake repository whose `add` returns `False` makes the use case return the existing conversation as `created=False` — proving the check-then-insert path isn't relied on. (The real proof is Chunk 15's database test.)
- **Guard:** non-member and nonexistent conversation raise the **same** `ConversationNotFound`.
- **Inbox:** a page of conversations calls `last_messages` and `unread_counts` **once each**, and `get_display_info` once **per distinct counterpart**, regardless of page size (assert fake call counts); ordered by `last_activity_at` desc with deterministic tie-break; preview is at most 100 characters; a failing `ProfileProvider` yields a `ParticipantView` of nulls, not an error.
- `AuthorizeConnection`/`AuthorizeSubscription` accept and reject correctly.

**Acceptance criteria:** new tests pass, all against fakes; no `fastapi`/`sqlalchemy` import anywhere under `application/`.

---

### CHUNK 7 — MESSAGE CREATION & HISTORY
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/send_message.py`, `application/use_cases/get_message_history.py`.

Implement `SendMessage` and `GetMessageHistory` exactly as Part C6. Production wiring for the two post-commit ports is **null adapters for now** — `NullRealtimeGateway` and `NullMessageEventDispatcher` (in `adapters/realtime/` and `adapters/events/`) — replaced by real ones in Chunks 11 and 14. Same approach as Search's `NullVerificationProvider`.

**Hard rules (re-read Part C6 step 6 and 7):** the sequence bump, message insert, and outbox insert are **one transaction**; the post-commit steps never run inside it, each is individually wrapped so a failure in one cannot stop the other or alter the returned result; nothing about the client's timing or socket enters this layer.

**Tests you must write** (against fakes):
- happy path: message persisted with the next sequence, `created_at` from `FixedClock`, outbox row written in the same unit of work (assert via the fake UoW that all three writes happened before commit), result `replayed=False`;
- **sender comes from `actor_id` only** — there is no parameter through which any other sender could be supplied;
- nonparticipant → `ConversationNotFound`; restricted actor / restricted counterpart → `CommunicationRestricted`, **nothing written**;
- invalid content (empty, whitespace-only, over `max_length`) → `InvalidMessageContent`; invalid `client_message_id` → `InvalidClientMessageId`; neither writes anything, **and an unauthorized actor gets the authorization error before any content-validation error** (a nonparticipant can't probe validation rules);
- **idempotency:** identical resend → `replayed=True`, the same message id, **no second write, no second outbox row, no push, no dispatch**; same key + different content → `ClientMessageIdConflict`; same key + different conversation → `ClientMessageIdConflict`;
- **the lost-race path:** a fake repository whose `add` raises `DuplicateClientMessageId` after the pre-check passed → the use case reloads and returns a replay (or the conflict), and the unit of work was rolled back (no outbox row left behind);
- a fake `RealtimeGateway` that raises, and a fake dispatcher that raises → the send **still returns success** and the message is stored; both failures logged at WARNING; a log-capture assertion that **no log line contains the message content**;
- a persistence failure (fake `add` raises something unexpected) → the exception propagates, **no push and no dispatch were attempted**;
- rate limit exceeded → `RateLimitExceeded`, nothing written;
- **history:** newest page with no cursor; `before` page ends exactly before the cursor; `after` page starts exactly after it; ascending order in all three; `has_older`/`has_newer` correct including exactly at a boundary; walking `before` pages from the newest back to the start yields every message exactly once with no overlap; `before` and `after` together → `InvalidHistoryCursor`; malformed cursor → `InvalidHistoryCursor`; `limit` 0 / above max → validation error; `client_message_id` present on the viewer's own messages and **`None` on the counterpart's**; a nonparticipant → `ConversationNotFound`.

**Acceptance criteria:** new tests pass, all against fakes. The replay test and the lost-race test are non-negotiable — they protect the lost-acknowledgement guarantee the whole module is built around.

---

### CHUNK 8 — READ POSITIONS & UNREAD COUNTS
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/mark_conversation_read.py`. Unread counting is already part of `ListConversations`/`GetConversation` (Chunk 6); this chunk completes the read path and proves the semantics end to end.

Implement `MarkConversationRead` as Part C6.

**Tests you must write:**
- *unit (fakes):* forward advance updates position and returns the recomputed unread; **repeating the same request is safe** and writes nothing the second time; a lower position is a no-op success that returns the current state (**no regression**); a message from a *different* conversation, and a nonexistent message id, both → `InvalidReadPosition`; a nonparticipant → `ConversationNotFound`; one participant's advance leaves the other's position untouched.
- *integration (real database, `tests/integration/messaging/test_read_state.py`):* **unread definition end to end** — A sends three messages; B's unread is 3, A's own unread is 0 (own messages never count); B reads up to the second → 1; B reads up to the third → 0; A sending after that does not change A's unread; B's unread rises only for A's new messages; **concurrent advances** (`asyncio.gather` of several `advance_read_position` calls with different targets, using the project's committed-data concurrency technique) always end at the **highest** target, never lower; sending does not move the sender's own read position.

**Acceptance criteria:** new tests pass; the concurrent-advance test passes reliably across **three consecutive runs**.

---

### CHUNK 9 — HTTP API ADAPTERS
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/api/schemas.py`, `adapters/api/router.py`, `adapters/api/dependencies.py`. **Files to modify:** `app.py` (mount the router under `/api/v1/messaging`; build the `RateLimiter` once in `lifespan` and store it on `app.state`).

**Six endpoints, all authenticated via the shared `get_current_identity_id` (from `platform/security/authentication.py` — do not define another):**

| Method | Path | Success | Notes |
|---|---|---|---|
| POST | `/conversations` | `201` new / `200` existing | body: `context_type`, plus `listing_id` **or** `booking_id` |
| GET | `/conversations` | `200` | `page`, `page_size` (shared `PageRequest` bounds) |
| GET | `/conversations/{conversation_id}` | `200` | |
| GET | `/conversations/{conversation_id}/messages` | `200` | `limit`, `before`, `after` |
| POST | `/conversations/{conversation_id}/messages` | `201` new / `200` replay | body: `client_message_id`, `content` |
| POST | `/conversations/{conversation_id}/read` | `200` | body: `up_to_message_id` |

**Schemas:** every request model uses `extra="forbid"` — so a client-supplied `sender_id`, `status`, `sequence`, `created_at`, or `media_ids` gets a `422` naming the unrecognized field, never silently ignored (ADR-124/C1 rule 6). `content` is `str` with **no** `max_length` here — the length rule lives in the use case via `Settings`, so there is exactly one source of the limit. Response schemas are built from the application DTOs, never from ORM rows. `conversation_id` path values that aren't valid UUIDs → `422`.

**Prohibition:** no business logic in `router.py`; dependency functions only compose use cases with real adapters, with the null realtime/dispatcher adapters from Chunk 7 still in place.

**Tests you must write** (`tests/api/messaging/`, real HTTP via the shared `client` fixture, registering/logging in real Identity accounts, creating profiles, a Scout with a `PUBLISHED` listing):
- unauthenticated request to **every** route → `401` before any messaging logic runs;
- **sender identity comes from authentication:** a body containing `sender_id` → `422`; a message sent by A shows `sender_id == A`;
- create conversation: `201` then `200` with the same id on repeat; a Student with no profile → `403`; the provider on their own listing → `403 self_conversation_not_allowed`; unknown listing → `404 conversation_context_not_found`; `ARCHIVED` listing → `422 conversation_context_unavailable`;
- a nonparticipant gets **`404 conversation_not_found`** on `GET /conversations/{id}`, on its `messages`, on `POST …/messages`, and on `POST …/read` — and the body is byte-identical to the response for a random unknown id;
- inbox shows only the caller's conversations; the counterpart block shows name/type/profile id and **no phone**;
- send: `201`, then the identical request again → `200` with the same message id and `replayed: true`; same key with different content → `409 client_message_id_conflict`; empty/over-long content → `422 invalid_message_content`; `media_ids` present → `422`;
- history pagination through real HTTP: walk `before` pages with a small `limit` over ≥ 7 messages, assert every message appears exactly once in the documented order; an `after` request returns only newer messages; `before`+`after` → `422 invalid_history_cursor`;
- read: advancing affects only the caller (the other participant's `unread_count` is unchanged); advancing with a message id from another conversation → `422 invalid_read_position`;
- a user whose Identity account has been disabled (via Module 3's admin endpoint) gets `403 communication_restricted` on send and on create;
- exceeding the send rate limit → `429` with `Retry-After`;
- validation errors use the project's standard `{"error": {"code", "message"}}` shape.

**Acceptance criteria:** the app starts; every test above passes; `poetry run lint-imports` clean; Identity's, Profile's, Housing's, Booking's suites unaffected.

---

### CHUNK 10 — WEBSOCKET PROTOCOL & CONNECTION LIFECYCLE
**[FOR YOU — GEMINI CLI]**

**Objective:** an authenticated, well-behaved socket that can connect, authenticate, stay healthy, and clean up after itself. **No messaging commands yet** — `conversation.subscribe`, `message.send`, `read.advance` arrive in Chunk 11. This chunk proves the lifecycle in isolation, which is where WebSocket bugs actually live.

**Files to create:** `adapters/api/ws_protocol.py`, `adapters/api/ws_handler.py`, `adapters/api/ws_router.py`, `adapters/realtime/connection_manager.py`.
**Files to modify:** `platform/security/authentication.py` (below), `app.py` (mount the WebSocket route at `/api/v1/messaging/ws`; create the `ConnectionManager` in `lifespan` and store it on `app.state`, closing every connection on shutdown).

**Part one — the authentication helper (ADR-118).** Per Chunk 1's finding, extract the token-decode step that `get_current_identity_id` uses into a small function callable **without an HTTP request** (taking a raw token string, returning the identity id or raising the same `InvalidCredentials`). `get_current_identity_id` then calls it. **A location change only** — same header parsing, same decode call, same error behavior. Identity's, Profile's, and every other module's existing suites must pass **unmodified**; if any doesn't, you changed behavior — stop and report. Update `AI_instructions/08_API_RULES.md` with one sentence noting the helper exists for non-HTTP transports.

**Part two — `ws_protocol.py`:** Pydantic models for every client command in Part C9 (`auth`, `conversation.subscribe`, `conversation.unsubscribe`, `message.send`, `read.advance`, `ping`), all `extra="forbid"`, plus builders for every server frame. The module is the *only* place frame shapes are defined. Only `auth` and `ping` are *handled* in this chunk; the others parse but answer `error unknown_command` until Chunk 11.

**Part three — `ConnectionManager`:** a focused adapter (Part C1 rule 1 — it never decides eligibility or touches persistence). It tracks `user_id → {connection_id → Connection}` supporting **multiple connections per user**; per-connection subscribed conversation ids; a **per-connection send lock** so two tasks never write to one socket at once; send with a timeout (`messaging_ws_send_timeout_seconds`) where a timeout or any send error **removes that connection only**, closes it, and logs — never raising to the caller; `register`/`unregister` idempotent; removing the last connection of a user removes the user entry (no leak). It must have no import of anything under `application/` or `domain/`.

**Part four — the handler.** Per connection: accept; apply the per-host connect rate limit (`messaging_ws_connect_rate_limit`, key from `websocket.client.host`, never from `X-Forwarded-For`) → over the limit closes `4429`; wait up to `messaging_ws_auth_timeout_seconds` for the first frame, which must be a valid `auth` → otherwise close `4401`; decode the token with the Part-one helper (failure → `4401`); call `AuthorizeConnection` (not allowed → `4403`); enforce `messaging_ws_max_connections_per_user` (→ `4429`, do **not** evict existing connections); register; send `auth.ok`. Then loop: receive with `messaging_ws_idle_timeout_seconds` (silence → close `4408`); frame over `messaging_ws_max_frame_bytes` → close `1009`; invalid JSON → `error invalid_json`; schema failure → `error invalid_command`; count protocol violations and close `4400` past the limit; `ping` → `pong`. **Auth expiry:** track `authenticated_until = now + messaging_ws_auth_ttl_seconds`; at expiry send `auth.expired`, answer every command except `auth`/`ping` with `error auth_expired`, accept a fresh `auth` for the **same** `user_id` (different user → close `4401`), and close `4401` after `messaging_ws_reauth_grace_seconds`. Use the injected `Clock`. **Everything in `finally`:** unregister the connection no matter how the handler exits.

**Hard rules.** Never log the token, the `auth` frame, or any frame content; log connection id, user id, close code, and event names only (`ws_connection_accepted`, `ws_auth_failed` with a *category*, `ws_connection_closed`, `ws_protocol_violation`, `ws_rate_limited`). Never hold a database session while awaiting the socket (Part C1 rule 3): `AuthorizeConnection` is invoked with a session that is closed before the next `await` on the socket. Close frames carry a short fixed reason string, never user data.

**Tests you must write** (`tests/api/messaging/test_ws_lifecycle.py`, using the live-server technique agreed in Chunk 1):
- a connection that sends a valid `auth` for an eligible user gets `auth.ok` with `protocol_version` 1;
- **rejections:** no frame within the timeout → `4401`; first frame not `auth` → `4401`; garbage JSON as first frame → `4401`; invalid token → `4401`; expired token (built via the Identity JWT adapter with a past `exp`, as Identity's own tests do) → `4401`; a user with **no profile** → `4403`; a **disabled** account → `4403`; in every rejection case assert that **no conversation data was sent**;
- the 6th connection for one user is closed `4429` while the first five stay open and working;
- **multiple connections per user:** closing one of a user's connections leaves the other registered and responsive; the manager's registry is empty after all close (no leak) — assert via a manager introspection method intended for tests;
- idle connection closed `4408`; `ping` keeps it alive past what would otherwise be the idle limit (shrink the timeouts through settings in the test, do not sleep for real minutes);
- oversized frame → `1009`; repeated malformed frames → `4400`; a single malformed frame → `error` and the connection stays open;
- auth TTL: after expiry (short TTL via settings) commands get `auth_expired`, a fresh `auth` for the same user restores service, a token for a *different* user closes `4401`, no re-auth closes `4401`;
- **disconnect cleanup:** abrupt client close (no close handshake) still removes the connection;
- **pool-safety proof:** with `database_pool_size` at its default of 5, open **10 idle authenticated connections** and confirm an ordinary HTTP request still succeeds (proves no connection holds a session);
- log-capture test: a complete connect/auth/ping/close cycle produces no log line containing the access token;
- the manager's send-failure path: a connection whose send raises is removed and the other connections are untouched (unit test on the manager with a fake socket).

**Acceptance criteria:** all pass; Identity's full suite passes unmodified; `poetry run lint-imports` clean; run the lifecycle file **three times in a row** — socket tests that pass once by timing luck are not evidence.

---

### CHUNK 11 — WEBSOCKET INTEGRATION WITH THE USE CASES
**[FOR YOU — GEMINI CLI]**

**Objective:** the three real commands and live delivery — through the **same** use cases HTTP uses. If you write a business rule in a socket handler in this chunk, stop.

**Files to create:** `adapters/realtime/in_memory_gateway.py` (the real `RealtimeGateway`). **Files to modify:** `adapters/api/ws_handler.py`, `adapters/api/dependencies.py` (swap the null gateway for the real one; the real gateway is built from the `ConnectionManager` on `app.state`).

- `conversation.subscribe` → `AuthorizeSubscription` → `ConnectionManager.subscribe`; enforce `messaging_ws_max_subscriptions_per_connection` (→ `error subscription_limit`); success → `subscribed`. `conversation.unsubscribe` is idempotent. A nonparticipant gets `error conversation_not_found` — identical for a nonexistent id.
- `message.send` → build the **same** `SendMessage` request HTTP builds, with `actor_id` taken **only** from the connection's authenticated user → on success `message.accepted {request_id, message, replayed}`; any `ApplicationError` → an `error` frame with its `code`; any other exception → log ERROR (ids only), `error internal_error`, and **never** a `message.accepted`. Apply the per-connection command rate limit (`messaging_ws_command_rate_limit`) before dispatching — over the limit → `error rate_limit_exceeded`, no use case call.
- `read.advance` → `MarkConversationRead` → `read.accepted`.
- Each command gets a **fresh short-lived session/UoW**, closed before the next `await` on the socket.
- **`InMemoryRealtimeGateway.push(user_ids, event)`**: for each target user, for each of that user's connections **subscribed to `event.conversation_id`**, send `message.created {event_id, message}` via the manager. It decides nothing about eligibility — the use case already chose the recipients from the persisted participants; the gateway only filters by subscription. Per-connection failures are handled inside the manager and never raise.

**Tests you must write** (live server; REST for setup; reuse the lifecycle fixtures):
- **subscribe:** a participant can; a nonparticipant gets `conversation_not_found` and **never receives events for it**; 51st subscription → `subscription_limit`;
- **send:** a valid `message.send` is **persisted** (verify by `GET …/messages`), and `message.accepted` arrives **only after** that — assert the row exists at the moment the ack is observed; the other participant's subscribed connection receives `message.created` with the same message id and a `sequence`; an **unrelated** connected user receives nothing (assert with a bounded wait); an unsubscribed connection of a participant receives nothing; the sender's **second connection** (subscribed) receives `message.created`, and the originating connection receives both `message.accepted` and `message.created` (documented behavior);
- **no impersonation:** a `message.send` carrying `sender_id` → `error invalid_command`, nothing persisted;
- **same rules as HTTP:** empty content, over-length content, and a `media_ids` field each produce the matching `error` with the same `code` HTTP returns; a restricted (disabled) user → `communication_restricted`; rate-limit-exceeded commands do not reach the use case;
- **`client_message_id` retry:** the same `message.send` twice → the second `message.accepted` has `replayed: true`, same message id, and `GET …/messages` shows one message; same key with different content → `error client_message_id_conflict`;
- **a persistence failure produces no false success:** patch the repository's `add` to raise (via the project's established dependency-override technique) and assert the client receives `error internal_error`, **no `message.accepted`**, and nothing is persisted;
- **a failed socket send never deletes the saved message:** close the recipient's socket abruptly just before a send; the message is still in history and the sender still gets `message.accepted`;
- **a restriction introduced after connection:** connect and authenticate a user, subscribe, then disable the account through Module 3's admin endpoint; the next `message.send` returns `communication_restricted` and nothing is persisted;
- `read.advance`: updates only the caller's position; `read.accepted` carries the new `unread_count`;
- **pool-safety re-proof** with active sending: 10 authenticated connections, several sending, HTTP still served.

**Acceptance criteria:** all pass; confirm by reading `ws_handler.py` that it imports **no repository and no ORM type** and contains no eligibility/sequence/idempotency logic; HTTP suite from Chunk 9 unchanged; run the file **three times**.

---

### CHUNK 12 — RECONNECTION, RECOVERY & ORDERING
**[FOR YOU — GEMINI CLI]**

**Objective:** prove the recovery model works; fix anything it uncovers. Mostly tests, because the mechanism is history + cursors + idempotency, which already exist.

**Tests you must write** (`tests/api/messaging/test_recovery_and_ordering.py`, live server):
- **offline recipient:** B disconnects; A sends five messages; all five are persisted (history) while B has no connection; B reconnects, re-authenticates, subscribes, calls `GET …/messages?after=<last cursor B knew>` and receives exactly the missed five in order, none duplicated;
- **dedupe on overlap:** B subscribes (live events begin) and *then* fetches history so a message appears in both; applying the documented client rule (dedupe on `message.id`, order by `sequence`) yields each message exactly once — implement the rule once in a small test helper that also serves as the reference for the frontend docs;
- **lost acknowledgement:** the client sends `message.send` and its socket is severed before `message.accepted` arrives (sever from the test side right after the send frame); reconnect; **(a)** history shows the message with the sender's own `client_message_id` populated, and **(b)** resending the same `message.send` returns `replayed: true` with the same id — exactly one message exists;
- **ordering under concurrency:** many concurrent sends in one conversation from both participants (the project's concurrent-request technique, committed data): assert sequences are exactly `1..N` with **no gaps and no duplicates**, history order equals sequence order, and walking history by `before` pages reproduces the same order; run it with several different `N` and conversation counts;
- **live events may be out of order:** assert every `message.created` carries a `sequence`, and a client applying the gap-detection rule (a jump → fetch `after`) ends with the complete ordered history;
- **multi-device:** the same user on two connections; one disconnects; the other keeps receiving; reconnecting a third connection recovers via history;
- **a recipient disconnecting mid-delivery does not prevent persistence** (covered in Chunk 11; re-assert here at scale: 20 sends to a recipient whose socket dies after the 5th);
- `last_activity_at` never regresses: construct the case where a later-sequenced message carries an *older* timestamp (via `FixedClock` manipulation in an integration test) and assert the conversation's `last_activity_at` did not decrease.

**Acceptance criteria:** all pass; the concurrency-ordering test passes **three runs in a row**; any bug found is fixed in the responsible layer (never patched in a test), with a one-line note in the Completion Report.

---

### CHUNK 13 — THE CROSS-PROCESS DELIVERY DECISION
**[FOR YOU — GEMINI CLI]**

**Objective:** make the single-process limitation **explicit, enforced, and replaceable** — and claim nothing more (ADR-123). **Precondition:** Nsisong has confirmed single-process deployment in writing. If that confirmation is missing, **stop and report** — do not proceed.

**Files to modify:** `app.py`/`lifespan`, `adapters/api/dependencies.py`. **Files to create:** `tests/contract/messaging/realtime_gateway_contract.py` (a reusable test mixin/suite).

1. At startup log INFO `messaging_realtime_backend=in_memory single_process=true`. Resolve the gateway from `Settings.messaging_realtime_backend` through one small factory — `in_memory` is the only branch; the settings type already rejects other values (Chunk 3), so the factory is where a future adapter would be added.
2. Write the **`RealtimeGateway` contract suite**: a set of behaviors any implementation must pass (delivers only to subscribed connections of the named users; a failing connection never raises to the caller; unsubscribed or foreign connections receive nothing; push to a user with no connections is a silent no-op). Run it against the in-memory gateway now. Document that a future cross-process adapter must pass the same suite.
3. **Do not** add Redis, a broker, or any cross-process mechanism. **Do not** write any test or documentation sentence that implies cross-worker delivery.
4. Add a short "Deployment limitations" section to `docs/modules/messaging.md` stub (full document in Chunk 16): per-process connection registry; per-process rate limiter; what happens with two workers (a message sent through worker 1 reaches only connections on worker 1 live; everyone still recovers through history); and the exact steps to add a cross-process adapter.

**Tests:** the contract suite against the in-memory gateway; a settings test that an unsupported backend fails startup.

**Acceptance criteria:** tests pass; no new infrastructure dependency in `pyproject.toml`; the limitation is documented in the module doc and the Completion Report.

*(Reshaped from the handoff's Chunk 12 "decide and implement" — the decision is made by ADR-123, so this chunk enforces and documents it.)*

---

### CHUNK 14 — EVENT PUBLICATION & THE NOTIFICATION CONTRACT
**[FOR YOU — GEMINI CLI]**

**Objective:** make "a saved message's event is never silently lost" true, using the outbox from Chunk 4. *(This replaces the handoff's Chunk 13: there is no Notification module to wire, no Trust & Safety module to extend — their seams were built in Chunks 5–6 — and attachments are deferred, ADR-124. What genuinely remains is reliable publication.)*

**Files to create:** `application/use_cases/dispatch_outbox_events.py`, `adapters/events/eventbus_dispatcher.py` (the real `MessageEventDispatcher`, replacing the null one), `scripts/run_messaging_outbox_relay.py`.

1. Implement `DispatchOutboxEvents` exactly per Part C6. The `MessageEventDispatcher` adapter calls `dispatch_one(event_id)` in its **own session**.
2. `scripts/run_messaging_outbox_relay.py`: a thin entry point composing `DispatchOutboxEvents` with real dependencies, running `execute(messaging_outbox_batch_size)` **once per invocation**. No scheduler, no daemon, no new dependency — invoked manually or by plain cron, same as `scripts/expire_booking_holds.py`. It prints a summary (claimed, dispatched, failed).
3. **Dev-only failing subscriber:** when `Settings.messaging_debug_failing_subscriber` is `True` **and** `app_env` is `local` or `test`, register on `app.state`'s `EventBus` a subscriber for `MessageCreated` that always raises. `app.py` checks `app_env` explicitly and registers nothing otherwise — a structural guard, same stance as Payment's mock-control router. This exists so the failure path can be *demonstrated*; it is never active in any other environment.
4. **Honest limitation to document (and to put in the module doc):** the shared event bus is in-process. A relay run as a separate script publishes to a bus in *its own* process, whose subscribers are whatever that script composes. Today there are no subscribers, so a published event reaches nobody. When a Notification module exists it must either register its subscriber in the relay's composition root, or consume the outbox through a contract it defines — a decision for that module's spec, not this one. Events published before any consumer existed are marked dispatched and are not replayed.
5. Write `docs/contracts/` (or the project's established location for cross-module contracts — follow Chunk 1's finding) a **`MessageCreated` event contract**: field list from Part C3, "no message body," at-least-once delivery, `event_id` stable across retries, consumers must dedupe.

**Tests you must write:**
- `MessageCreated` published through the dispatcher has every Part C3 field and **no content**, with `event_id` equal to the outbox row id;
- `dispatch_one` marks a row dispatched; a second call is a no-op; a row already claimed by another transaction is skipped (real DB);
- **a failing subscriber does not lose or roll back the message:** with the failing subscriber active, send a message — the message is in history, the outbox row remains `dispatched_at IS NULL` with `attempts >= 1` and `last_error` holding only a class name, and the send still returned success;
- **recovery:** with the failing subscriber removed, run the relay — the row is dispatched exactly once and a recording subscriber sees it once; run the relay again — nothing is re-published;
- **duplicate-tolerance:** manually reset a dispatched row and re-run — the recording subscriber receives an event with the **same `event_id`** both times (the property consumers dedupe on);
- one failing row does not stop the rest of the batch;
- the failing subscriber is **not** registered when `app_env="staging"` even if the setting is `True` (mirror Chunk 5's mock-controls-not-mounted test from Module 10);
- a message persisted while the dispatcher itself raises is still returned and still in history.

**Acceptance criteria:** tests pass; the documentation limitation above is present; no Notification code or placeholder module was created.

---

### CHUNK 15 — SECURITY, RELIABILITY & REGRESSION COMPLETION
**[FOR YOU — GEMINI CLI]**

**Objective:** close every gap against the Chief Engineer's required test list (Part E maps each item to a file). **Fix every defect found before Chunk 16** — this chunk is a gate.

**Files to create:** `tests/integration/messaging/test_conversation_race.py`, `tests/api/messaging/test_messaging_security.py`, plus whatever Part E shows is still missing.

- **The duplicate-conversation race (real database, committed data, `asyncio.gather` — not sequential calls):** 10 concurrent `FindOrCreateConversation` calls for the same `(listing, student)` → **exactly one** conversation row, exactly two participant rows, exactly one caller sees `created=True`; repeat for a `BOOKING` context; repeat with two different students on one listing (→ exactly two conversations). Run **three times in a row**.
- **Concurrent equivalent sends:** concurrent identical `(sender, client_message_id)` sends → one message, one outbox row, the rest replays.
- **`test_messaging_security.py`:** a nonparticipant cannot read history, send, read-advance, or subscribe, with a response indistinguishable from an unknown id; a Student cannot read another pair's conversation by guessing an id; an `ADMIN` with no profile is refused (`MESSAGING_PARTICIPATE` is not theirs) — **there is no administrative path to read conversations**, assert none exists in the route table; a log-capture test across HTTP *and* WebSocket sends asserting no message content, no access token, and no `Authorization` value appears anywhere in the captured logs; no response contains another user's phone number or `identity`-internal fields beyond the documented ids.
- Confirm no business logic in `router.py`, `ws_handler.py`, or `connection_manager.py` by inspection and say so in the report.
- **Import-linter contracts** (extend the existing list, same pattern as every module): `camp_match.modules.messaging.domain` and `.application` must not import `fastapi` or `sqlalchemy`; nothing outside `camp_match.modules.messaging` may import its `adapters.*`; each cross-module adapter (`listing`, `booking`, `profile`, `restriction`) may import only the target module's `application.ports`/use-case surface, never `adapters` or `domain`; `adapters/realtime` must not import `application` or `domain`. **Deliberately violate the new cross-module contract once**, confirm `lint-imports` fails, remove the violation.
- **Run everything:** `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports` — the whole project, all eleven modules, green. Then re-run, **in isolation**, Identity's, Security's, Profile's, and Booking's suites and confirm they are unchanged apart from the documented additions (the policy assertion; the helper extraction; the `429` handler tests).

**Acceptance criteria:** every test above passes; every concurrency/WebSocket test file passes **three consecutive runs**; no known-failing or skipped test.

---

### CHUNK 16 — DOCUMENTATION, FRONTEND REFERENCE & AI STATE
**[FOR YOU — GEMINI CLI — paste Part G (Manual Testing Guide) together with this chunk]**

1. Write `docs/modules/messaging.md` per `09_DOCUMENTATION_RULES.md`, covering every item in the Chief Engineer's list (purpose and non-purpose; domain model and tables; use cases and ports; module boundaries; conversation creation, eligibility and the ADR-126 policies; persistence, ordering and idempotency; the WebSocket architecture and protocol — reproduce Part C9 **verbatim**; authentication and its ADR-118 caveats; connection lifecycle and cleanup; multi-device behavior; reconnection and recovery; read-state semantics and the unread definition; event publication and the outbox with its at-least-once and in-process-bus limitations; Trust & Safety and Media/File integration status; configuration table from Part C8; testing strategy and exact commands; known limitations; extension points). Include the **Deployment limitations** section from Chunk 13.
2. **Known limitations, listed plainly and individually:** single-process realtime and per-process rate limiting (ADR-122/123); no Notification consumer exists, so `MessageCreated` currently reaches nobody (ADR-121); no blocking/reporting/moderation (ADR-121); **no attachments** (ADR-124), with the follow-up recommended; access tokens aren't individually revocable and connection lifetime is capped by configuration rather than token expiry (ADR-118); inbox is offset-paginated and can shift between pages while messages arrive; counterpart display info is one Profile lookup per distinct counterpart per inbox page (ADR-127); live events may arrive out of order and clients must order by `sequence`; no edit, delete, group chat, typing indicators, receipts, or read-receipts to the counterpart.
3. Create `scripts/messaging_ws_client.py`: a tiny developer tool — `--url`, `--token` (or `MESSAGING_TOKEN` env var); connects with the `websockets` library, sends the `auth` frame, then prints every incoming frame and sends each line typed on stdin as a raw JSON frame. Never prints the token. Used by Part G.
4. Create `docs/modules/messaging_manual_testing.md` from Part G, **running every command you document** and correcting any that doesn't work in this repository — the guide must contain only commands you have verified.
5. Update `docs/modules/security.md` (the new permission and its grants) and the project-wide frontend API reference location Chunk 1 found, **only to add a pointer** — Nsisong maintains the Front End Doc from Part F.
6. Update `AI_state/`: `CURRENT_STATE.md`, `PROGRESS.md`, `COMPLETED_WORK.md`, `ARCHITECTURE_STATE.md` (first module with a long-lived transport and its own outbox; the four shared-code touches), `DATABASE_STATE.md` (four tables, one migration), `API_STATE.md` (six REST endpoints and the WebSocket route), `TEST_STATE.md`, `DECISIONS.md` (append ADR-112–128), `SESSION_HANDOFF.md`. Security's own state notes the new permission; Identity's/Platform's notes the helper extraction; the shared kernel's notes `RateLimitedError`. `CURRENT_TASK.md` in the standard status-block format.

**Acceptance criteria:** every document above exists and matches the implementation (no speculative endpoints or fields); every documented command was executed; `docs/modules/messaging.md` states the limitations in item 2 without softening.

---

### CHUNK 17 — FINAL AUDIT & COMPLETION REPORT
**[FOR YOU — GEMINI CLI]**

1. Run the full suite from a clean state (`scripts/db_stop.sh`, `scripts/db_start.sh`, `poetry run alembic upgrade head`, then the four commands from Chunk 15). Re-run **every** concurrency and WebSocket test file three times each as the very last step.
2. Audit against this specification and **answer each plainly** in the Completion Report — not "done":
   - Business logic duplicated inside a transport adapter: yes/no (evidence: the files inspected).
   - Direct cross-module database access anywhere: yes/no.
   - Any operation lacking an authorization check: list or "none," with how you verified.
   - Duplicate-conversation race: tested against a real database? yes/no.
   - A path by which a message could be acknowledged before commit: yes/no.
   - A path by which a failed push, failed dispatch, or failed notification could lose or roll back a saved message: yes/no.
   - Read state owned by participants, never by messages: confirmed? yes/no.
   - WebSocket disconnect leaks (registry empty after all close; no held DB session): confirmed? yes/no.
   - Reconnection recovery proven by test: yes/no.
3. **Readiness classification — do not round up:**
   - Core HTTP + WebSocket messaging implemented: yes/no.
   - Cross-worker real-time delivery: **not implemented** (single-process, ADR-123).
   - Rate limiting effective across processes: **no** (per-process).
   - Notification delivery: **no consumer exists**; the event is published and durable-until-dispatched only.
   - Trust & Safety: **only Identity account status**; no blocking/reporting.
   - Attachments: **not implemented** (ADR-124).
4. Report: completed requirements; every test command and its real result; known limitations; unresolved issues; the exact recommended next step. **Do not claim completion for anything unimplemented or unverified.** Set `CURRENT_TASK.md` to "Messaging complete. Awaiting next module specification from Claude."

---

## PART E — TEST COVERAGE MATRIX [FOR NSISONG]

Every item in the Chief Engineer's Section 18, and where it is proven. Nothing is left implicit.

| Handoff item | Where | Notes |
|---|---|---|
| 18.1 (1–4, 11, 12) participant send, nonparticipant, impersonation, validation, eligibility, restrictions | Chunk 6–7 unit tests; Chunk 9 API | |
| 18.1 (5) activity metadata | Chunk 4 (`next_sequence`), Chunk 12 | `last_activity_at` never regresses |
| 18.1 (6–8) read positions per participant, cross-conversation, no regression | Chunk 8 | |
| 18.1 (9–10) idempotent replay, conflicting key | Chunk 7, Chunk 9, Chunk 11 | |
| 18.2 (1–11) HTTP | Chunk 9 | 8 (concurrent creation): Chunk 15 |
| 18.3 (1–10) WS auth/authz | Chunks 10–11 | 7 (rate limit / payload): Chunk 10–11 |
| 18.4 (1–12) real-time | Chunks 11–12 | 12 (restriction after connect): Chunk 11 |
| 18.5 (1–5) read state | Chunk 8 | 5 (concurrent advances): Chunk 8 |
| 18.6 (1) event contract fields | Chunk 14 | |
| 18.6 (2–4) notification failure, publication failure recovery, duplicate events | Chunk 14 | via the dev-only failing subscriber and the relay |
| 18.6 (5) attachments through Media/File | **Not applicable** | deferred, ADR-124 |
| 18.6 (6) listing/booking eligibility via public contracts | Chunks 5–6, import-linter in Chunk 15 | |
| 18.6 (7) runs without payment providers | the whole suite | none is involved |
| 18.6 (8) multi-worker delivery | **Not applicable** | not claimed, ADR-123 |

Handoff Section 17's index list is covered by Part C4 (membership lookup → `messaging_participants(user_id)`; history → the `(conversation_id, sequence)` unique index; idempotency → `(sender_id, client_message_id)`; outbox → the partial index). No other index is added.

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**Applies everywhere:** all REST routes are under `/api/v1/messaging` and need `Authorization: Bearer <access_token>`. Errors use the standard `{"error": {"code", "message"}}` shape. A conversation you aren't in returns `404 conversation_not_found`, exactly like one that doesn't exist. Amounts don't appear in this module.

### POST /api/v1/messaging/conversations
**Purpose:** start (or get) a conversation about a listing or a booking.
**Body:** `{"context_type": "LISTING", "listing_id": "…"}` or `{"context_type": "BOOKING", "booking_id": "…"}`. No other fields; extra fields → `422`.
**Success:** `201` for a new conversation, `200` if it already existed — **same body either way**, so tapping "Message House Scout" repeatedly is always safe.
**Errors:** `403 forbidden` (no profile yet) · `403 communication_restricted` · `403 self_conversation_not_allowed` · `404 conversation_context_not_found` · `422 conversation_context_unavailable` (listing not published / booking cancelled or expired) · `429 rate_limit_exceeded`.
**Response (`ConversationView`):** `id`, `context_type`, `listing_id`/`booking_id`, `counterpart {user_id, profile_id, display_name, profile_type}` (any may be `null`), `last_message {id, sender_id, preview, sequence, created_at}` or `null`, `last_activity_at`, `unread_count`, `last_read_message_id`, `created_at`.
**Frontend notes:** an existing conversation keeps working even after the listing is archived or the booking is cancelled — you can always reopen it.

### GET /api/v1/messaging/conversations
Your inbox, newest activity first. `page`, `page_size`. Returns the standard `{items, total, page, page_size}` shape. **Frontend notes:** order can shift between pages while new messages arrive; refresh from page 1 after a live event rather than trying to patch pages.

### GET /api/v1/messaging/conversations/{conversation_id}
One `ConversationView`.

### GET /api/v1/messaging/conversations/{conversation_id}/messages
**Query:** `limit` (default 30, max 100), and at most one of `before` / `after` (cursors).
- No cursor → the **newest** `limit` messages.
- `before=<cursor>` → the page of older messages ending just before it.
- `after=<cursor>` → the next newer messages starting just after it (use this to catch up after being offline).
**Response:** `{items, has_older, has_newer, older_cursor, newer_cursor}`. **`items` are always oldest → newest.** To load older history, pass `older_cursor` as `before`; to catch up, pass the `cursor` of the newest message you already have (or `newer_cursor`) as `after`. Each item: `{id, conversation_id, sender_id, content, sequence, cursor, created_at, client_message_id}` — `client_message_id` is present **only on your own messages**.
**Errors:** `422 invalid_history_cursor`.

### POST /api/v1/messaging/conversations/{conversation_id}/messages
**Body:** `{"client_message_id": "<uuid you generate>", "content": "…"}` — exactly these. **Generate one `client_message_id` per send attempt, and reuse the identical value when retrying after a timeout or dropped connection. Never generate a fresh one for a retry** — that is what makes a retry safe.
**Success:** `201` new, `200` if that `client_message_id` was already saved (`replayed: true`, same message). `201`/`200` bodies: `{message, replayed}`.
**Errors:** `403 communication_restricted` · `404 conversation_not_found` · `409 client_message_id_conflict` (same id, different content or conversation) · `422 invalid_message_content` (empty, or longer than 2000 characters) · `422 invalid_client_message_id` · `429 rate_limit_exceeded`.
**Frontend notes:** content is never truncated for you — validate length client-side too. Attachments are **not supported yet**; sending `media_ids` returns `422`.

### POST /api/v1/messaging/conversations/{conversation_id}/read
**Body:** `{"up_to_message_id": "…"}`. **Success `200`:** `{conversation_id, last_read_message_id, unread_count}`. Safe to repeat; reading "backwards" changes nothing and returns the current state. **Errors:** `404`; `422 invalid_read_position`.
**Unread rule:** unread counts only messages **from the other person** after your read position. Your own messages are never unread to you. Sending a message does **not** mark things read — call this endpoint when the user actually views the conversation.

### WebSocket: `wss://<host>/api/v1/messaging/ws`
The socket is for **live updates and fast sending**. REST is the source of truth: everything you need survives a dropped socket.

**1. Connect, then authenticate with your first frame** (no token in the URL, ever):
`{"type": "auth", "access_token": "<current access token>"}` → `{"type": "auth.ok", "user_id": "…", "protocol_version": 1, "auth_expires_in_seconds": 900}`. You have 10 seconds to send it. A failed login closes the socket with code **4401**; not eligible (no profile / account restricted) → **4403**; more than 5 connections for one user → **4429**.
**2. Re-authenticate before the lifetime runs out.** About every 15 minutes the server sends `{"type": "auth.expired"}`; send a fresh `auth` frame with a newly refreshed access token (same user) within 60 seconds or the socket closes with **4401**.
**3. Keep it alive:** send `{"type": "ping"}` about every 30 seconds; the server answers `{"type": "pong"}`. 90 seconds of silence closes the socket (**4408**). Frames over 16 KB close it (**1009**).
**4. Subscribe to conversations you want live events for** (max 50 per connection): `{"type": "conversation.subscribe", "conversation_id": "…"}` → `{"type": "subscribed", "conversation_id": "…"}`. Unsubscribe with `conversation.unsubscribe`.
**5. Send:** `{"type": "message.send", "request_id": "r1", "conversation_id": "…", "client_message_id": "<uuid>", "content": "…"}`.
→ **`message.accepted`** `{request_id, message, replayed}` means **saved**. Until you receive it, show the message as *sending*. If the socket drops first, you don't know — **reconnect and either resend the same frame (same `client_message_id`) or look in history**; never guess.
**6. Receive:** `{"type": "message.created", "event_id": "…", "message": {…}}` for every new message in a conversation you're subscribed to — including ones you sent from another tab or device, and **also your own message right after `message.accepted`** (you may get both for one message; **dedupe on `message.id`**).
**7. Advance read position:** `{"type": "read.advance", "request_id": "r2", "conversation_id": "…", "up_to_message_id": "…"}` → `{"type": "read.accepted", "request_id": "r2", "conversation_id": "…", "last_read_message_id": "…", "unread_count": 0}`.
**8. Errors:** `{"type": "error", "request_id": "r1", "code": "…", "message": "…"}` with the same `code`s as REST, plus `invalid_json`, `invalid_command`, `unknown_command`, `auth_required`, `auth_expired`, `subscription_limit`, `rate_limit_exceeded`, `internal_error`.

**The rules that keep a client correct:**
- **Order by `sequence`, not arrival time.** Live events from concurrent senders can arrive out of order.
- **If you see a gap** (you have 11, you receive 14), fetch `GET …/messages?after=<cursor of 11>` and merge. The same fetch is your **reconnection** step.
- **Reconnect recipe:** reconnect → `auth` → `GET /conversations` (counts and previews) → for each open conversation fetch `after` its last known message → re-`subscribe` → resume. Deduplicate by `message.id`.
- **Live delivery is best-effort; history is the truth.** A pushed event can be missed, repeated, or late. A saved message never is.
- Real-time delivery currently works within a single server process (deployment limitation). Nothing about that changes the recipe above.

**Example (condensed JavaScript):**
```js
const token = () => session.accessToken;
const seen = new Map();            // conversationId -> Map(messageId -> message)
const lastCursor = new Map();      // conversationId -> cursor of newest message held

async function loadInbox() {
  const r = await fetch('/api/v1/messaging/conversations?page=1&page_size=30',
                        { headers: { Authorization: `Bearer ${token()}` } });
  return (await r.json()).items;
}
function merge(convId, msgs) {                       // dedupe + order by sequence
  const m = seen.get(convId) ?? new Map(); seen.set(convId, m);
  for (const x of msgs) m.set(x.id, x);
  const newest = [...m.values()].sort((a, b) => a.sequence - b.sequence).at(-1);
  if (newest) lastCursor.set(convId, newest.cursor);
}
async function catchUp(convId) {
  let after = lastCursor.get(convId);
  for (;;) {
    const q = after ? `&after=${encodeURIComponent(after)}` : '';
    const r = await fetch(`/api/v1/messaging/conversations/${convId}/messages?limit=100${q}`,
                          { headers: { Authorization: `Bearer ${token()}` } });
    const page = await r.json(); merge(convId, page.items);
    if (!page.has_newer) break; after = page.newer_cursor;
  }
}
function connect(openConvIds) {
  const ws = new WebSocket(`wss://${location.host}/api/v1/messaging/ws`);
  ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', access_token: token() }));
  ws.onmessage = async (e) => {
    const f = JSON.parse(e.data);
    if (f.type === 'auth.ok') {
      for (const id of openConvIds) { await catchUp(id); ws.send(JSON.stringify({ type: 'conversation.subscribe', conversation_id: id })); }
      setInterval(() => ws.send('{"type":"ping"}'), 30000);
    } else if (f.type === 'message.created') {
      merge(f.message.conversation_id, [f.message]);     // gap? -> catchUp(...)
    } else if (f.type === 'message.accepted') {
      merge(f.message.conversation_id, [f.message]);     // flip "sending" -> "sent"
    } else if (f.type === 'auth.expired') {
      refreshAccessToken().then(() => ws.send(JSON.stringify({ type: 'auth', access_token: token() })));
    } else if (f.type === 'error') { /* show f.code */ }
  };
  ws.onclose = () => setTimeout(() => connect(openConvIds), 2000);   // reconnect -> catchUp runs again
  return ws;
}
function send(ws, convId, text) {
  const id = crypto.randomUUID();      // keep this value if you must retry
  ws.send(JSON.stringify({ type: 'message.send', request_id: id, conversation_id: convId, client_message_id: id, content: text }));
}
async function markRead(convId, messageId) {
  await fetch(`/api/v1/messaging/conversations/${convId}/read`, { method: 'POST',
    headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ up_to_message_id: messageId }) });
}
```
**Known limitations (tell your product people):** no attachments yet; no edit/delete; no typing indicators or read-receipts shown to the other person; no group chats; live delivery covers one server process.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — and paste to Gemini with Chunk 16]

**Preconditions for every test:** `scripts/db_start.sh` running; app running (`poetry run uvicorn camp_match.main:app --reload`); two logged-in accounts with profiles — **Ada** (Student) and **Bola** (Scout) — and Bola owns a `PUBLISHED` listing (Modules 2 and 5). Keep both access tokens handy. For WebSocket tests use two Termux sessions with the helper (Gemini verifies this exact form in Chunk 16): `poetry run python scripts/messaging_ws_client.py --url ws://localhost:8000/api/v1/messaging/ws --token <ACCESS_TOKEN>` — it connects, authenticates, prints everything it receives, and sends each line you type as a frame. REST calls use `curl` with `Authorization: Bearer <token>`.

Each test lists: **verifies** (what) · **why** (why it matters) · **steps** · **expect** · **if it fails** (what that looks like and where to look).

**M1 — Start a conversation and send by HTTP.** *Verifies:* a student can contact a listing's Scout and messages are saved. *Why:* the core purpose. *Steps:* as Ada `POST /conversations` with the listing id; as Ada `POST …/messages` with a fresh `client_message_id`; as Bola `GET /conversations` and `GET …/messages`. *Expect:* `201`, then `201`; Bola sees the conversation with `unread_count: 1` and Ada's text. *If it fails:* `403` → Ada has no profile; `422 conversation_context_unavailable` → the listing isn't `PUBLISHED`; check the app log for the request id.

**M2 — Live delivery.** *Verifies:* a message appears instantly for a connected, subscribed recipient. *Why:* the reason WebSockets exist. *Steps:* open the helper as Bola, then type `{"type":"conversation.subscribe","conversation_id":"<id>"}`; as Ada send a message by HTTP. *Expect:* Bola's terminal prints a `message.created` frame. *If it fails:* no `subscribed` reply → check `4403`/`4401` close codes and that the token is fresh; subscribed but nothing arrives → confirm the app is a **single** process (live delivery doesn't cross processes).

**M3 — Offline recipient and recovery.** *Verifies:* a message is saved while the recipient is disconnected, and recoverable after. *Why:* real networks drop; nothing may be lost. *Steps:* close Bola's helper; as Ada send three messages; reconnect Bola, re-`auth`, then `GET …/messages?after=<cursor of the last message Bola had>`. *Expect:* exactly the three missed messages, in order. *If it fails:* missing messages mean persistence failed — check the log for `message_sent` lines and any ERROR.

**M4 — Two tabs, one user.** *Verifies:* one user can be connected twice; closing one doesn't break the other. *Why:* people use phone and laptop. *Steps:* open two helper sessions as Bola, subscribe both; close one; send a message from Ada. *Expect:* the remaining session still receives it. *If it fails:* the remaining one is silent → cleanup removed the wrong connection; look for `ws_connection_closed` lines.

**M5 — A stranger can't read a conversation.** *Verifies:* knowing a conversation id grants nothing. *Why:* privacy. *Steps:* register a third account **Chidi** with a profile; as Chidi `GET /conversations/<id>`, `GET …/messages`, `POST …/messages`; also subscribe over the helper. *Expect:* `404 conversation_not_found` everywhere, identical to a made-up id; the subscription answers `conversation_not_found`; Chidi never receives live frames. *If it fails:* any `200`/`403` here is a privacy bug — stop and report.

**M6 — Bad WebSocket credentials.** *Verifies:* an unauthenticated or invalid connection is refused with no data. *Why:* security. *Steps:* connect and wait 10 s without sending anything; connect and send a garbage token; connect with a token for a **disabled** account (disable via Module 3's endpoint). *Expect:* closes with 4401, 4401, 4403; nothing but the close. *If it fails:* any data before `auth.ok` is a bug.

**M7 — Duplicate-tap protection.** *Verifies:* "Message House Scout" can't create duplicates, even simultaneously. *Why:* a real double-tap race. *Steps:* run the same `POST /conversations` five times quickly; then in a shell run ten in parallel (`seq 10 | xargs -P10 -I{} curl -s -X POST …`). *Expect:* every response carries the **same** conversation id; `GET /conversations` for Ada shows one. *If it fails:* two conversations means the uniqueness guarantee is broken — blocking.

**M8 — Read state and unread counts.** *Verifies:* unread counts follow each person's own read position. *Why:* the inbox badge. *Steps:* Ada sends three messages; Bola `GET /conversations` (unread 3); Bola `POST …/read` up to the second (unread 1), then the third (0); Ada sends again (Bola's unread 1; **Ada's own unread stays 0**). *Expect:* exactly those numbers; repeating the same `read` call changes nothing. *If it fails:* Ada's unread rising from her own messages, or Bola's reset by Ada, means read state isn't participant-specific.

**M9 — Pagination.** *Verifies:* history pages are stable and complete. *Why:* long conversations. *Steps:* send 12 messages; `GET …/messages?limit=5`; follow `older_cursor` as `before` until `has_older` is false. *Expect:* all 12 exactly once, oldest-to-newest within each page. *If it fails:* a repeated or missing message means the ordering/cursor logic is wrong.

**M10 — Restriction on an existing conversation.** *Verifies:* a suspended user can't keep talking in a conversation that already existed. *Why:* a restriction must not be bypassable. *Steps:* with Ada connected and subscribed, disable Ada's account (Module 3's endpoint); have Ada send over the open socket. *Expect:* `error communication_restricted`; nothing saved; Bola sees no new message. *If it fails:* a saved message after the disable is blocking.

**M11 — Notification-side failure never loses a message.** *Verifies:* a failing downstream consumer can't lose or undo a saved message, and the event is recovered later. *Why:* the outbox's reason to exist. *Steps:* set `MESSAGING_DEBUG_FAILING_SUBSCRIBER=true` (local only), restart, send a message; confirm via `GET …/messages` it was saved and the send returned success; check the outbox row (`psql … -c "select attempts, dispatched_at, last_error from messaging_outbox"`) shows `dispatched_at` empty, `attempts ≥ 1`; unset the flag, restart, run `poetry run python scripts/run_messaging_outbox_relay.py`. *Expect:* the script reports one dispatched; the row now has `dispatched_at`. *If it fails:* a message missing from history after a subscriber failure is blocking. *(Note: no Notification module exists yet, so "dispatched" means published to the in-process bus.)*

**M12 — Idle and dead-connection handling.** *Verifies:* silent connections are closed, and `ping` keeps one alive. *Why:* otherwise dead phones pile up. *Steps:* connect and authenticate, send nothing for 90 s; repeat sending `{"type":"ping"}` every 30 s. *Expect:* the first closes with 4408; the second stays open. *If it fails:* connections that never close indicate a resource leak.

**Intentionally absent:** attachment authorization tests (attachments are deferred, ADR-124) and multi-worker tests (not implemented, ADR-123). If either is later built, these tests become required.

**Automated tests:** `poetry run pytest tests/unit/messaging tests/integration/messaging tests/api/messaging` · domain only (fast, no database): `poetry run pytest tests/unit/messaging -v` · WebSocket and race tests, three times: `for i in 1 2 3; do poetry run pytest tests/api/messaging tests/integration/messaging/test_conversation_race.py; done` · everything: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`. Integration and API tests need `scripts/db_start.sh` running.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] Sending, reading, and conversation creation each exist **once**, in use cases; the router and WebSocket handler contain no rules (confirmed by inspection in Chunks 11 and 15).
- [ ] A message is committed **before** `message.accepted` or an HTTP `201` — proven by a test that sees the row at ack time, and by a forced persistence failure producing no success.
- [ ] Duplicate conversation creation is impossible under concurrency, proven on a real database across three runs.
- [ ] A retried send never duplicates, including after a lost acknowledgement; a conflicting reuse of an id is rejected.
- [ ] Ordering is a gap-free per-conversation sequence, proven under concurrent senders; history pages never overlap or skip.
- [ ] Read state is per participant, monotonic, and safe under concurrent advances; own messages are never unread.
- [ ] A nonparticipant gets the same `404` as an unknown id on every REST and WebSocket operation, and never receives live events.
- [ ] A restriction introduced after a connection exists is enforced on the next send/create.
- [ ] A failed push, failed dispatch, or failed downstream consumer never loses or rolls back a saved message; an undispatched event is recovered by the relay.
- [ ] Disconnects leave no registry entries and no held database sessions (10 idle connections with a pool of 5 still serve HTTP).
- [ ] No token, `Authorization` value, or message content appears in any log.
- [ ] Identity, Profile, Security, Housing, Booking suites unchanged apart from the documented additions; the helper extraction changed location only.
- [ ] `docs/modules/messaging.md`, the manual guide, and `AI_state/` are written, every documented command was actually run, and the limitations are stated without softening — especially: single-process real-time, no Notification consumer, no blocking/reporting, no attachments.
- [ ] The Chunk 17 readiness classification is recorded honestly.
