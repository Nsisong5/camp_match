# Camp Match Module 12: Notification

## Purpose and Non-Purpose
- **Purpose:** Provide an in-app notification inbox and event-driven notification dispatch service that consumes domain events from Messaging, Booking, and Verification, enforces strict recipient policies, renders localization-independent notification text via templates, supports message collapsing (ADR-136), and maintains processing reliability via an idempotent event inbox with exponential backoff retry and dead-letter queue recovery (ADR-131, 135).
- **Non-Purpose:** External delivery channels (push notifications, SMS, email), user notification preferences/settings, real-time push to clients (clients poll), delivery-attempt persistence (ADR-130), automatic background daemons for the worker (run manually or via cron per ADR-141), or retention/purge policies (ADR-142).

## Domain Model and Tables
- **Entities:** `Notification`
- **Value Objects:** `NotificationType`, `NotificationCategory`, `TargetType`, `NotificationTarget`, `NotificationDraft`, `InboxStatus`
- **Database Tables:**
  1. `notifications`: `id` (UUID PK), `recipient_id` (UUID FK), `type` (VARCHAR), `category` (VARCHAR), `title` (TEXT), `body` (TEXT), `target_type` (VARCHAR), `target_id` (UUID), `group_key` (VARCHAR, nullable), `event_count` (INTEGER), `source_event_id` (VARCHAR), `read_at` (TIMESTAMPTZ, nullable), `created_at` (TIMESTAMPTZ), `latest_event_at` (TIMESTAMPTZ). Partial unique index on `(recipient_id, group_key)` where `group_key IS NOT NULL AND read_at IS NULL`.
  2. `notification_inbox`: `event_id` (UUID PK), `event_type` (VARCHAR), `payload` (JSONB), `received_at` (TIMESTAMPTZ), `status` (VARCHAR: `PENDING`, `PROCESSED`, `REJECTED`, `DEAD`), `attempts` (INTEGER), `next_attempt_at` (TIMESTAMPTZ), `processed_at` (TIMESTAMPTZ, nullable), `last_error` (TEXT, nullable). Partial index `ix_notification_inbox_due` on `next_attempt_at` where `status = 'PENDING'`.

## Event Contracts (C5) and Recipient Policies
| Event | Fields (Public Contract) | Producer | Recipient Policy & Notification Type |
|---|---|---|---|
| `MessageCreated` | `message_id`, `conversation_id`, `sender_id`, `recipient_id`, `sequence`, `context_type`, `message_created_at` | Messaging | `recipient_id` → `message.new`; `CONVERSATION:conversation_id`; group `message:{conversation_id}`. **Never the sender**. |
| `BookingCreated` | `booking_id`, `student_id`, `property_id`, `listing_id` | Booking | Property owner (via `PropertyOwnerProvider`) → `booking.created.provider`; `BOOKING:booking_id`. |
| `BookingConfirmed` | same four | Booking | Student → `booking.confirmed.student` & Owner → `booking.confirmed.provider`; `BOOKING:booking_id`. |
| `BookingCancelled` | same four + `cancelled_by` | Booking | Non-cancelling parties: student → `booking.cancelled.student`, owner → `booking.cancelled.provider`. Admin cancellation notifies **both**. |
| `BookingExpired` | same four | Booking | Student → `booking.expired.student`; `BOOKING:booking_id`. |
| `VerificationDecisionRecorded` | `case_id`, `target_type` (`PROVIDER`/`PROPERTY`), `target_id`, `decision` (`VERIFIED`/`REJECTED`/`REVOKED`) | Verification | Case owner: `PROVIDER` → `target_id`; `PROPERTY` → property owner. Type corresponds to decision (`verification.verified` / `.rejected` / `.revoked`); `VERIFICATION_CASE:case_id`. **Never the reviewing account**. |

## Receipt, Processing, and Retry Lifecycle
1. **Receipt (`ReceiveEvent`)**: Subscribers receive domain events from the event bus, convert them via `event_to_payload()`, and record them idempotently in `notification_inbox` (`INSERT ... ON CONFLICT (event_id) DO NOTHING`). Duplicates return `False`. Failures propagate to trigger best-effort warning logs.
2. **Inline Processing (`ProcessInboxEvent`)**: Executed inline upon receipt or by the worker script. Implements the single-transaction rule: claims the row (`SELECT ... FOR UPDATE SKIP LOCKED`), parses payload with strict parsers, resolves recipient policies (querying Housing for property owner if needed), creates notifications (collapsing if collapsible and unread), and marks inbox row `PROCESSED` in one atomic transaction.
3. **Failure Outcomes & Backoff**:
   - **`REJECTED`**: Unsupported event type or malformed payload. Marked `REJECTED` with code `invalid_payload`, never retried.
   - **`FAILED`**: Transient error (e.g. database error during processing). Rolls back transaction, records failure in a new transaction, increments `attempts`, and computes `next_attempt_at` using exponential backoff with jitter/cap (`30 * 2^(attempts-1)` seconds).
   - **`DEAD`**: Reaching `notification_inbox_max_attempts` (default 8). Logged as ERROR `notification_event_dead`. Can be operator-requeued via `RequeueDeadEvents`.

## Collapse Rule (ADR-136)
Message notifications (`message.new`) carry a `group_key` (`message:{conversation_id}`). While unread, subsequent messages in the same conversation increment `event_count` and update `latest_event_at` via an atomic upsert (`ON CONFLICT (recipient_id, group_key) WHERE group_key IS NOT NULL AND read_at IS NULL UPDATE SET event_count = event_count + 1`). Once marked read, the next message creates a fresh notification row.

## HTTP API Endpoints
- `GET /api/v1/notifications`: List notifications for authenticated user. Query params: `unread_only` (bool), `category` (string), `page`, `page_size`.
- `GET /api/v1/notifications/unread-count`: Get unread count.
- `POST /api/v1/notifications/{id}/read`: Mark specific notification as read.
- `POST /api/v1/notifications/read-all`: Mark all notifications (optionally filtered by category) as read.

## Security and Privacy
- **Strict Isolation:** Authenticated users can only read, count, or mark their own notifications (`actor_id` derived exclusively from valid JWT bearer token). Cross-tenant access attempts return 404/403.
- **Data Privacy:** Notification titles and bodies are strictly generated from predefined templates. No personal data, message text, names, amounts, cancellation reasons, or URLs appear in any notification title or body.
- **Log Sanitation:** Logs contain no notification body, payload content, message text, or access tokens.
- **No Creation/Modification API:** There are no endpoints to create, update, delete, or broadcast notifications from the API; notifications are purely event-driven from internal module domains.

## Configuration & Local Development
- **Settings:** `notification_inbox_max_attempts` (default 8), `notification_inbox_backoff_base_seconds` (default 30), `notification_inbox_backoff_cap_seconds` (default 3600), `notification_worker_batch_size` (default 100), `notification_debug_fail_processing` (bool).
- **Worker Script (`scripts/run_notification_worker.py`)**:
  - Run once (processes pending batch): `python scripts/run_notification_worker.py`
  - View stats: `python scripts/run_notification_worker.py --stats`
  - Requeue dead events: `python scripts/run_notification_worker.py --requeue-dead`

## Testing Strategy
- Unit tests (`tests/unit/notification/`): Domain invariants, rendering templates, strict event parsers, recipient policies, and use cases with fakes and `FixedClock`.
- Integration tests (`tests/integration/notification/`): Real database persistence, concurrency, double delivery, multi-worker race conditions, and retry backoff.
- API tests (`tests/api/notification/`): HTTP endpoints, authentication, pagination, and authorization isolation.

## Known Limitations
1. **At-Most-Once Event Publication:** Booking and Verification events use best-effort publishing after commit; a crash between commit and publish may lose the event (Messaging uses a durable outbox; ADR-131).
2. **In-App Only:** No push notifications, SMS, email, user preferences, or device registration. No delivery-attempt tracking tables (ADR-130).
3. **Polling Real-Time:** No real-time WebSocket or SSE channel for notifications; clients poll REST endpoints (ADR-139).
4. **Excluded Modules:** Payment, Housing, Identity, and Trust & Safety domain events do not currently trigger notifications (ADR-134).
5. **No Retention / Purge:** Notifications remain indefinitely in the database (ADR-142).
6. **No Rate Limiting:** Read endpoints do not have rate limiting (Identity ADR-020 gap continues).
7. **Message Collapse:** Message notifications collapse into a single summary notification per conversation while unread (ADR-136).
8. **Manual Worker Execution:** The inbox processor worker is executed manually or via external cron, not as an internal automated background daemon (ADR-141).
9. **Dead Letter Intervention:** `DEAD` status inbox rows can be requeued via Admin & Operations recovery route (`POST /api/v1/admin/recovery/notification-events/requeue-dead`), while staff UI remains to be built.
