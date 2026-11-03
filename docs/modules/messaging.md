# Camp Match Module 11: Messaging

## Purpose and Non-Purpose
- **Purpose:** Provide secure, reliable, real-time messaging between students and housing scouts (or regarding bookings), supporting inbox pagination, history cursors, idempotent message sending, read-state tracking, and outbox event publication.
- **Non-Purpose:** File/media attachments (deferred per ADR-124), content moderation/blocking/reporting (handled by Trust & Safety / Identity restrictions), or cross-worker multi-process real-time distribution (single-process in-memory per ADR-123).

## Domain Model and Tables
- **Entities:** `Conversation`, `Message`, `Participant`.
- **Value Objects:** `ConversationContext`, `MessageContent`, `ClientMessageId`.
- **Database Tables:**
  1. `messaging_conversations`: `id`, `context_type`, `listing_id`, `booking_id`, `dedupe_key`, `last_sequence`, `last_activity_at`, `created_at`, `updated_at`.
  2. `messaging_participants`: `id`, `conversation_id`, `user_id`, `last_read_message_id`, `joined_at`.
  3. `messaging_messages`: `id`, `conversation_id`, `sender_id`, `sequence`, `content`, `client_message_id`, `created_at`. Unique index on `(conversation_id, sequence)` and `(sender_id, client_message_id)`.
  4. `messaging_outbox`: `id`, `event_type`, `payload`, `status`, `attempts`, `created_at`, `dispatched_at`, `last_error`.

## Use Cases and Ports
- **Inbound Use Cases:**
  - `FindOrCreateConversation`: idempotently starts or retrieves a conversation.
  - `ListConversations`: retrieves the user's inbox sorted by recent activity.
  - `GetConversation`: retrieves conversation details.
  - `SendMessage`: sends a message with idempotency (`client_message_id`).
  - `GetMessageHistory`: pages through history using `before`/`after` cursors.
  - `MarkConversationRead`: updates read state and returns unread count.
  - `AuthorizeConnection`: checks account status, profile existence, and communication restrictions.
  - `AuthorizeSubscription`: checks conversation participation.
  - `DispatchOutboxEvents`: relays pending outbox events to the event bus.

## Published Events
- **Events:** `MessageCreated`.
- **Fields:** `message_id`, `conversation_id`, `sender_id`, `recipient_id`, `sequence`, `context_type`, `message_created_at`.
- **Delivery:** Published via outbox relay (`scripts/run_messaging_outbox_relay.py`) to the event bus.

## Module Boundaries & Cross-Module Adapters
- **Housing:** `ListingProvider` verifies listing existence and published status.
- **Booking:** `BookingProvider` verifies booking existence and eligibility.
- **Profile:** `ProfileProvider` resolves counterpart display information and profile types.
- **Security / Restriction:** `IdentityBackedRestrictionProvider` checks account status and restrictions (`MESSAGING_PARTICIPATE`).

## WebSocket Architecture & Protocol
- **Transport:** `/api/v1/messaging/ws` WebSocket endpoint.
- **Lifecycle & Authentication:** 10-second auth timeout, token validation via ADR-118 helper, max 5 connections per user, idle timeout (90s), command rate limiting (`messaging_ws_command_rate_limit`).
- **Commands:** `auth`, `conversation.subscribe`, `conversation.unsubscribe`, `message.send`, `read.advance`, `ping`.
- **Responses/Events:** `auth.ok`, `auth.expired`, `subscribed`, `unsubscribed`, `message.accepted`, `message.created`, `read.accepted`, `pong`, `error`.

## Known Limitations
- **Single-Process Real-Time:** Live delivery is restricted to a single server process (ADR-123).
- **No Attachments:** Media/file attachments are deferred (ADR-124).
- **No Blocking/Reporting:** Moderation is limited to identity account suspension.
- **Out-of-Order Live Events:** Clients must order live events by `sequence`.
