# Camp Match Module 12: Notification Manual Testing Guide

## Preconditions
- Start database: `scripts/db_start.sh`
- Run migrations: `poetry run alembic upgrade head`
- Start API application: `poetry run uvicorn camp_match.main:app --reload`
- Two user accounts with profiles created: **Ada** (Student) and **Bola** (Scout). Bola owns a `PUBLISHED`, bookable listing. A third account **Chidi** for isolation tests.
- Keep user access tokens. Use `curl` with `Authorization: Bearer <token>`.

---

## Manual Test Cases

### N1 — A message creates a notification for the recipient only
- **Verifies:** An event becomes a notification for the intended recipient.
- **Steps:** Ada starts a conversation with Bola's listing and sends a message; Bola requests `GET /notifications`; Ada requests `GET /notifications`.
- **Expect:** Bola has one `message.new` notification ("New message" / "You have a new message."), unread; Ada has none (she is not notified of her own message).

### N2 — Nobody sees anyone else's notifications
- **Verifies:** Strict multi-tenant isolation.
- **Steps:** Take Bola's notification ID. As Ada and as Chidi, call `POST /notifications/<id>/read`. As Chidi, call `GET /notifications`.
- **Expect:** `404 notification_not_found` for both users on another's notification; Chidi's list has nothing of Bola's; Bola's notification remains unread.

### N3 — Unread count
- **Verifies:** Unread badge count consistency.
- **Steps:** Bola calls `GET /notifications/unread-count`; compare with `GET /notifications?unread_only=true`.
- **Expect:** Counts match. Ada's count is 0.

### N4 — Mark one read, safely repeatable
- **Steps:** Bola calls `POST /notifications/<id>/read` twice.
- **Expect:** Both calls return `200`; `read_at` timestamp is identical on both calls; unread count decreases to 0.

### N5 — Read-all
- **Steps:** Generate unread notifications for Bola, then Bola calls `POST /notifications/read-all`. Check Ada's unread count is unaffected.
- **Expect:** Returns `{"marked_read": N}` with exact count; only Bola's notifications are marked read.

### N6 — Message collapsing (The 40-messages test)
- **Verifies:** A burst of messages collapses into a single notification with `event_count = 40`.
- **Steps:** Bola marks all read. Ada sends 40 messages in a shell loop:
  ```bash
  for i in $(seq 1 40); do
    curl -s -X POST http://localhost:8000/api/v1/messaging/conversations/<conv_id>/messages \
      -H "Authorization: Bearer <ada_token>" \
      -H "Content-Type: application/json" \
      -d "{\"client_message_id\":\"burst-$i\",\"content\":\"hi $i\"}"
  done
  ```
  Run worker: `poetry run python scripts/run_notification_worker.py`. Bola lists notifications.
- **Expect:** Exactly one `message.new` with `event_count: 40`. Bola marks it read. Ada sends 1 more message → a new notification with `event_count: 1`, while the old one remains untouched at `event_count: 40`.

### N7 — Booking events
- **Verifies:** Booking lifecycle events (`BookingCreated`, `BookingConfirmed`, `BookingCancelled`, `BookingExpired`) reach the correct parties.
- **Steps:** Ada books Bola's listing → Bola gets "New booking". Ada cancels it → Bola gets "Booking cancelled". Another booking created and Bola cancels it → Ada gets "Booking cancelled". For expiry, advance or expire booking holds via `poetry run python scripts/expire_booking_holds.py` → Ada gets "Booking expired"; Bola gets nothing.
- **Expect:** Correct recipient routing per policy.

### N8 — Booking confirmation reaches both
- **Steps:** Complete payment on mock provider and confirm booking.
- **Expect:** Ada gets student confirmation; Bola gets provider confirmation as two distinct records.

### N9 — Verification decision
- **Verifies:** Verification decision notification routing (`PROVIDER` vs `PROPERTY`) and text privacy (no rejection reasons).
- **Steps:** Operations account approves/rejects/revokes Bola's verification case.
- **Expect:** For `PROPERTY`, Bola as property owner is notified (reviewer is not). For `PROVIDER`, provider is notified. No free-text reason appears in notification text.

### N10 — Duplicate event never makes duplicate notification
- **Verifies:** Idempotency via inbox deduplication (`ON CONFLICT (event_id) DO NOTHING`).
- **Steps:** Re-dispatch an already processed event via outbox relay (`poetry run python scripts/run_messaging_outbox_relay.py`) and inspect notifications.
- **Expect:** Notification count and `event_count` are unchanged; logs show `notification_event_duplicate`.

### N11 — Notification failure never breaks business action, and recovers
- **Verifies:** Producer isolation and retry backoff.
- **Steps:** Set `NOTIFICATION_DEBUG_FAIL_PROCESSING=true` and `NOTIFICATION_INBOX_BACKOFF_BASE_SECONDS=1`, restart app. Ada sends message → `201 Created` succeeds. Bola's inbox is empty. Run worker stat: `poetry run python scripts/run_notification_worker.py --stats` shows `PENDING`. Unset flag, restart, wait, run worker. Bola receives notification once.

### N12 — Dead letters and operator requeue
- **Steps:** With failing flag and `NOTIFICATION_INBOX_MAX_ATTEMPTS=2`, send message, run worker twice until `DEAD`. Run `python scripts/run_notification_worker.py --requeue-dead`, then run worker normally.
- **Expect:** Event transitions to `DEAD`, then successfully processed after requeue.
