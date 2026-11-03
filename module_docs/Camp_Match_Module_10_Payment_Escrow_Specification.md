# CAMP MATCH — MODULE 10: PAYMENT & ESCROW
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Payment & Escrow Module handoff**

---

## HOW TO READ THIS DOCUMENT

Same conventions as every previous module spec, with one addition this handoff specifically asked for: a plain-language explanation section before anything implementation-ready, since this is the module where getting the *concepts* right matters as much as getting the code right. Fifteen chunks requested, delivered with two small merges noted exactly where they happen. This is the highest-stakes module in the project — real money, real custody, real audit obligations — and the precision level matches that throughout, not just in the concurrency-sensitive parts.

**One ground rule stated once, binding for the whole document:** no real payment provider is selected anywhere in this spec, on purpose — that was explicitly off-limits. Everything below is provider-independent, backed by a deterministic mock. A provider capability checklist is included as its own section, for when that decision is ready to be made deliberately.

---

## PART A — PLAIN-LANGUAGE EXPLANATION [FOR NSISONG]

### What this module actually does

Every other module in this project either represents something real (a listing, a verification case, a booking) or decides something (is this allowed, which listings should show first). Payment is different — it's the module responsible for the fact that **money changing hands is not the same event as money being safe to give to someone.** A student paying is one moment. Camp Match being confident enough to hand that money to the property's Scout is a different, later moment, and in between, several things have to be true.

### Why "payment succeeded" and "funds released" are two completely different ideas in this design

It would be simpler to have one field — `payment_status` — that goes from `PENDING` to `PAID` to `RELEASED`. This project deliberately doesn't do that, for a reason worth understanding: **a successful payment and a safe release are different facts, confirmed by different evidence, that can go wrong independently.** A payment can succeed and then need a full refund three days later because the student never actually got into the room. If "released" were just another value of the same status field, you'd have no way to represent "paid, but we haven't released it yet, and we might never need to." Keeping them as two separate tracked things — a `Payment` (did the money arrive) and a `FundDisposition` (what's allowed to happen to it now) — means each can have its own honest history, and neither one lies about the other.

### Why there's a 48-hour clock, and why it doesn't start when you might expect

The natural instinct is: payment succeeds, start a timer, release the money. This module doesn't do that either. The clock only starts once there's real evidence the student was actually *offered* access to the place they paid for — not when the charge cleared, not when a confirmation email went out. That's deliberate: paying for a room and then disappearing with your money because nobody could get in touch with the Scout would be exactly the outcome Verification and Booking have both been built to prevent. If the handover evidence never shows up, the clock simply never starts, and funds sit held rather than auto-releasing on a payment date that has nothing to do with whether the student got what they paid for.

### The one real, honest gap this handoff asked me to solve myself

Nothing in this project currently owns the fact "this specific student actually received access to this specific room." Verification (Module 7) only ever answered "is this property legitimate," which is a fact about the *property*, true or false regardless of which student eventually books it. This module's handoff was explicit that I shouldn't invent a shortcut around that gap inside Payment itself — so the fix is a small, correctly-scoped addition to **Booking** (Module 9), since a booking already *is* "this specific student, this specific unit" — adding two small facts to it: was access offered, did the student confirm receiving it. See Finding 2 below for the precise shape.

### What "escrow" honestly means here, for now

This module tracks money as *held* and enforces rules about when it's allowed to move — but whether Camp Match's bank/provider arrangement genuinely, legally segregates that money the way real escrow does is a question this module cannot answer on its own; it depends entirely on whichever real payment provider eventually gets chosen and how that integration is structured. Recording an internal `HELD` status is not the same claim as "this money is legally protected the way an escrow agent would protect it." The provider capability checklist at the end of this document exists specifically so that distinction gets checked deliberately, not assumed.


---

## PART B — ARCHITECTURE ASSESSMENT & FINDINGS [FOR NSISONG]

### FINDING 1 — the Booking contract this module needs already exists, waiting

Booking's `ConfirmBooking` (Module 9) was built as a real inbound port with a deliberate, documented stand-in caller — its own decision log says so explicitly: a future Payment module "will call this exact same inbound port in-process... only a new caller gets added" (Module 9, ADR-094). This module is that caller. No change to Booking's `ConfirmBooking` is needed at all. Booking's existing price snapshot (`amount_kobo`/`currency`/`period`) is also exactly the "server-authoritative amount" this handoff asks Payment to trust (Part 9) — nothing new needed there either.

### FINDING 2 — the handover/acceptance gap, and where it actually belongs

Explained in plain language above. Precisely: Booking (Module 9) gains two small new capabilities — `ConfirmHandoverOffered` (the Scout records that access was made available — keys handed over, gate code shared, whatever the actual mechanism is) and `ConfirmHandoverAccepted` (the student confirms they received it as agreed). Both are just timestamped facts on the existing `Booking` entity — no new state in Booking's own lifecycle, no new module. **Disputes do not go through Booking at all** — a dispute is fundamentally "should this money move," which is squarely this module's domain, not Booking's. A student reports a problem directly to Payment.

### FINDING 3 — Verification does not need to be re-checked here

Booking already refuses to create a booking for an unverified property (its own ADR-099). Re-checking verification again at payment time would be redundant, not safer — if a property's verification is revoked *after* a valid booking and payment already exist, that's an operational/Trust & Safety matter for a human to resolve, not something this module should silently re-litigate on every payment event. No `VerificationProvider` dependency is added here.

### DECISIONS (ADR-103 … ADR-111) [FOR NSISONG]

Continuing the log from Phase 1–3 (001–013) through Booking (094–102).

| ADR | Decision | Why |
|---|---|---|
| 103 | Booking's `ConfirmBooking` becomes this module's real caller, unchanged | Finding 1. |
| 104 | Handover facts live on **Booking** (two small new capabilities); disputes are raised directly against **Payment** | Finding 2 — each fact lives with the module whose existing scope actually matches it. |
| 105 | "Release eligible" — including the 48-hour fallback window — is **computed** at the moment a release is evaluated, never a stored state | The sixth confirmed instance of this project's "derive, don't cascade" idiom (after University & Location, Housing, Verification, Booking's expiry, and now this). No background job's timing can ever be the thing that decides whether a release is actually valid. |
| 106 | The ledger is a **simplified, single-sided, append-only movement log** per fund disposition — not full double-entry bookkeeping across a chart of accounts | Stated plainly, not glossed over: this is traceable and sufficient for MVP reconciliation, but it is not a claim of GAAP-style accounting compliance. Worth knowing precisely before any real money depends on it. |
| 107 | A late provider-success signal for an already-terminal payment attempt **never mutates that attempt's historical state** — it creates a separate recovery record instead | The attempt genuinely did expire/fail at the time it did; rewriting that fact to say otherwise would destroy real history. The late signal becomes its own, honestly-dated fact feeding the recovery workflow (Chunk 11). |
| 108 | **Three** new Security permissions, not one — `PAYMENT_REVIEW` (`OPERATIONS`+`ADMIN`), `PAYMENT_AUTHORIZE_RELEASE`/`PAYMENT_AUTHORIZE_REFUND` (**`ADMIN` only**) | The handoff's own "least privilege" instruction, taken literally: being able to *see* a dispute queue and being able to *move money* are different levels of trust, and conflating them would be exactly the "every administrator automatically gets every financial permission" the handoff warns against by name. |
| 109 | No `VerificationProvider` dependency | Finding 3. |
| 110 | No real provider selected or integrated anywhere in this spec | Explicit instruction (Part 26). The mock adapter implements every port in full; see the Provider Capability Checklist. |
| 111 | The provider port is split into **five** narrow capability protocols (initiation, verification, webhooks, refunds, payouts), not one large interface | Direct instruction (Part 7A). A future provider lacking payout support, for instance, can decline that one capability honestly rather than implementing a method it can't actually fulfill. |

**Two items worth your attention specifically, not just information:** ADR-104's split (handover facts on Booking, disputes on Payment) is the single biggest structural decision in this whole module — worth confirming it matches your own mental model of who should be recording what before Gemini builds around it. And ADR-106's ledger honesty matters beyond this codebase — if Camp Match ever needs to show real accounting records to a bank, a provider, or a regulator, this is the exact point where "what the database says" and "what a real ledger would say" might not yet be the same thing.


---

## PART C — CHUNKED IMPLEMENTATION

**Structural note:** the handoff's Chunk 1 ("codebase inspection and integration plan... explain in understandable language") is Parts A and B above, already delivered. Chunk 1 below is scaffolding plus the one small Booking addition Finding 2 requires — nothing more needs inspecting that Parts A/B haven't already covered. **Do not give Gemini more than one chunk at a time.** Wait for each one's Completion Report before issuing the next.

---

### CHUNK 1 — SCAFFOLDING & THE BOOKING ADDITION
**[FOR YOU — GEMINI CLI]**

**Files to create (module: Payment):**
```
src/camp_match/modules/payment/__init__.py
src/camp_match/modules/payment/domain/__init__.py
src/camp_match/modules/payment/domain/value_objects.py
src/camp_match/modules/payment/domain/entities.py
src/camp_match/modules/payment/domain/release_policy.py
src/camp_match/modules/payment/application/__init__.py
src/camp_match/modules/payment/application/errors.py
src/camp_match/modules/payment/application/ports/__init__.py
src/camp_match/modules/payment/application/ports/inbound.py
src/camp_match/modules/payment/application/ports/outbound.py
src/camp_match/modules/payment/application/ports/provider.py
src/camp_match/modules/payment/application/use_cases/__init__.py
src/camp_match/modules/payment/adapters/__init__.py
src/camp_match/modules/payment/adapters/persistence/__init__.py
src/camp_match/modules/payment/adapters/booking/__init__.py
src/camp_match/modules/payment/adapters/provider/__init__.py
src/camp_match/modules/payment/adapters/provider/mock/__init__.py
src/camp_match/modules/payment/adapters/api/__init__.py
tests/unit/payment/__init__.py
tests/unit/payment/domain/__init__.py
tests/unit/payment/application/__init__.py
tests/integration/payment/__init__.py
tests/api/payment/__init__.py
```
`application/ports/provider.py` is separate from `outbound.py` — the five provider-capability protocols (Chunk 3) are a distinct, larger concern from this module's own repository/Booking ports, and keeping them in their own file matches the handoff's own instruction to treat provider contracts as a first-class design surface, not an incidental dependency.

**Files to modify (module: Booking — Finding 2/ADR-104, the one small addition this module needs from an already-shipped module):** `modules/booking/application/use_cases/` (add `confirm_handover_offered.py`, `confirm_handover_accepted.py`), `modules/booking/domain/entities.py` (`Booking` gains `handover_offered_at`/`handover_offered_by`/`handover_accepted_at`, all nullable, permanent once set — no new `BookingStatus` member, these are facts alongside the existing lifecycle, not a new state), `modules/booking/application/ports/inbound.py` (the two new ports), `adapters/persistence/models.py` + migration, `adapters/api/schemas.py`/`router.py` (two new endpoints: `POST /bookings/{id}/handover/offered` — `HOUSING_MANAGE` ownership, the Scout confirms; `POST /bookings/{id}/handover/accepted` — the booking's own student, structurally self-scoped).

**Prohibition:** this is the *only* change to Booking anywhere in this document. No change to `BookingStatus`, the state machine, or any existing use case.

**Tests you must write (in Booking's own test folders):** `tests/unit/booking/application/test_confirm_handover.py` — both facts settable independently, each by the correct actor only (Scout for offered, student for accepted — a mismatched caller gets `Forbidden`); neither settable on a `CANCELLED`/`EXPIRED` booking. Confirm Booking's full pre-existing suite is unaffected.

**Acceptance criteria:** new Booking tests pass; `poetry run pytest tests/unit/booking tests/integration/booking tests/api/booking` shows the same results as before this chunk, plus the new ones; all Payment module files from above importable.


---

### CHUNK 2 — PAYMENT DOMAIN MODEL
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/value_objects.py`, `domain/entities.py`.

**`value_objects.py`:**
- **`Currency`** — own copy, `NGN` only, same as every other module.
- **`Money`** — `amount_kobo` (int, may be negative only when explicitly used for ledger entries — see Chunk 10; non-negative everywhere else), `currency`. Never float, anywhere in this module, full stop.
- **`PaymentAttemptStatus`** (enum) — `INITIATED`, `PENDING`, `SUCCEEDED`, `FAILED`, `EXPIRED`, `CANCELLED`.
- **`FundDispositionStatus`** (enum) — `HELD`, `DISPUTE_HOLD`, `PARTIALLY_RELEASED`, `RELEASED`, `PARTIALLY_REFUNDED`, `REFUNDED`, `RECONCILIATION_REQUIRED`.
- **`OperationStatus`** (enum, shared shape for both release and refund operations) — `DECISION_RECORDED`, `PROVIDER_INITIATED`, `PROVIDER_PENDING`, `SUCCEEDED`, `FAILED`, `RECONCILIATION_REQUIRED`.
- **`DisputeStatus`** (enum) — `OPEN`, `RESOLVED_RELEASE`, `RESOLVED_REFUND`, `RESOLVED_PARTIAL`.
- **`DecisionOrigin`** (enum) — `AUTOMATIC`, `MANUAL`.
- **`LedgerEntryType`** (enum) — `CHARGE`, `HOLD_ALLOCATION`, `RELEASE`, `REFUND`, `REVERSAL`, `CORRECTION`. (No `FEE` — not an MVP requirement; noted as a clean future addition in Chunk 14's documentation, not built now.)

**`entities.py` — five entities, deliberately kept separate rather than one giant aggregate (Part 39):**

- **`PaymentAttempt`** — `id`, `booking_id` (permanent), `student_id` (permanent), `amount` (`Money`, permanent — the trusted snapshot from Booking, never the client's displayed figure), `idempotency_key` (permanent), `status`, `provider_name` (permanent — which adapter handled this attempt), `provider_reference` (nullable, set once the provider session exists), `created_at`, `confirmed_at` (nullable). Expose `record_late_success_signal()` (ADR-107) — does **not** change `status`; it's a marker method the application layer uses to know a late-signal recovery record should be created, called only when the attempt is already in a terminal, non-`SUCCEEDED` state.

- **`Payment`** — the confirmed financial fact, constructed only once a `PaymentAttempt` genuinely reaches `SUCCEEDED` (never constructed for a merely-initiated or pending attempt — a `Payment` existing *is* the proof money arrived). `id`, `payment_attempt_id` (permanent), `booking_id`, `student_id`, `amount` (permanent, immutable forever — this is the historical fact, never touched by a later refund), `provider_reference` (permanent), `confirmed_at` (permanent).

- **`FundDisposition`** — one per `Payment`. `id`, `payment_id` (permanent), `held_amount_kobo` (permanent — equals the payment's amount at construction), `status`, `created_at`. Exposes **computed, never-stored** properties: `released_amount_kobo` / `refunded_amount_kobo` (summed from its own `ReleaseOperation`/`RefundOperation` children with `status == SUCCEEDED`) and `remaining_releasable_kobo` (`held - released - refunded`).

- **`ReleaseOperation`** / **`RefundOperation`** — same shape, two classes (not one generic "FundOperation" — Part 14 explicitly wants release and refund tracked as distinct lifecycles, and collapsing them into one polymorphic type would blur exactly the distinction the handoff insists on): `id`, `fund_disposition_id` (permanent), `amount` (`Money`, permanent), `status`, `decision_id` (permanent, links to the `ReleaseDecision` that authorized it — Chunk 8), `provider_operation_reference` (nullable), `requested_at`, `confirmed_at` (nullable), `failure_reason` (nullable).

- **`Dispute`** — `id`, `fund_disposition_id` (permanent), `raised_by` (permanent), `reason` (permanent, required non-empty), `status`, `raised_at` (permanent), `resolved_at`/`resolved_by`/`resolution_notes` (nullable, set only on resolution).

**Invariants enforced here, not later:** a `Payment`'s `amount` never changes, ever, for any reason — refunds are tracked as separate operations against the `FundDisposition`, never as a mutation of the original payment record (Part 6: "A successful original payment with a pending refund remains a successful original payment"). `FundDisposition.remaining_releasable_kobo` can never go negative — enforce this as a constructor/update-time check on `ReleaseOperation`/`RefundOperation`, not just trust the application layer to have checked first (defense in depth, same discipline as Housing's `Unit.occupied_count` invariant).

**Tests you must write:** `tests/unit/payment/domain/test_fund_disposition.py` — `remaining_releasable_kobo` computes correctly across a mix of succeeded/pending/failed operations (only `SUCCEEDED` ones count); attempting to construct a release/refund operation that would push the remaining balance negative raises at construction, not silently clamps to zero. `tests/unit/payment/domain/test_payment_attempt.py` — `record_late_success_signal` only callable from a terminal non-`SUCCEEDED` state, never mutates `status`.

**Acceptance criteria:** new tests pass; no import beyond stdlib + shared-kernel `EntityId`/`Clock`.


---

### CHUNK 3 — PROVIDER-INDEPENDENT CONTRACTS
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `application/ports/provider.py`.

**Five narrow capability protocols (ADR-111), each independently optional per adapter:**

| Protocol | Methods |
|---|---|
| `PaymentInitiationCapability` | `initiate(command: InitiatePaymentCommand) -> PaymentSessionResult` |
| `PaymentVerificationCapability` | `verify_transaction(provider_reference: str) -> VerifiedProviderTransaction` |
| `WebhookCapability` | `verify_signature(raw_body: bytes, headers: dict) -> bool`; `parse_event(raw_body: bytes) -> NormalizedProviderEvent` |
| `RefundCapability` | `request_refund(provider_reference, amount: Money, idempotency_key: str) -> ProviderRefundResult`; `get_refund_status(provider_operation_reference: str) -> ProviderRefundResult` |
| `PayoutCapability` | `initiate_payout(recipient_reference, amount: Money, idempotency_key: str) -> ProviderPayoutResult`; `get_payout_status(provider_operation_reference: str) -> ProviderPayoutResult` |

**`ProviderCapabilities`** — a plain declarative dataclass, not a protocol: `supports_initiation`, `supports_verification`, `supports_webhooks`, `supports_refunds`, `supports_payouts` (all `bool`). A concrete adapter exposes one of these describing itself; the application layer (Chunk 6 onward) checks it before attempting an operation and raises `UnsupportedProviderCapability` rather than calling a method that would silently no-op or fail unpredictably.

**Normalized DTOs, all plain dataclasses, all treated as untrusted-until-verified where they originate from provider input (never pass a raw provider payload past the adapter boundary):**
- `InitiatePaymentCommand` — `payment_attempt_id`, `amount: Money`, `idempotency_key`, `return_context` (whatever minimal data the checkout flow needs back, e.g. a redirect URL — provider-specific detail stays inside the adapter, not this DTO).
- `PaymentSessionResult` — `provider_reference`, `checkout_reference` (a token/URL the client uses — opaque to the domain), `expires_at`.
- `VerifiedProviderTransaction` — `provider_reference`, `amount: Money`, `normalized_status: PaymentAttemptStatus`, `occurred_at`.
- `NormalizedProviderEvent` — `provider_event_id` (the dedup key), `event_type`, `provider_reference`, `normalized_status`, `amount: Money`, `occurred_at`.
- `ProviderRefundResult` / `ProviderPayoutResult` — `provider_operation_reference`, `normalized_status: OperationStatus`, `amount: Money`, `failure_reason` (nullable).

**Prohibition, stated as plainly as the handoff itself states it:** nothing in `domain/` or `application/use_cases/` may import a provider SDK, `httpx`/`requests` for a provider call, or anything provider-specific by name. If you find yourself importing a provider's library outside `adapters/provider/`, stop.

**Tests you must write:** none — this chunk defines contracts only, same as every other pure-port chunk in this project. `poetry run mypy` clean is the acceptance bar.

**Acceptance criteria:** every protocol and DTO above exists with the exact shape listed.

---

### CHUNK 4 — PERSISTENCE & FINANCIAL INTEGRITY
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/persistence/models.py`, `adapters/persistence/repository.py`.

**Six tables:**

**`payment_attempts`** — `id`, `booking_id` (UUID, no FK), `student_id` (UUID, no FK), `amount_kobo` (bigint, `CHECK > 0`), `currency`, `idempotency_key` (text), `status` (`CHECK` restricted — indexed), `provider_name`, `provider_reference` (nullable, indexed), `created_at`, `confirmed_at` (nullable). **Unique constraint** on `(student_id, idempotency_key)` — same idempotency guarantee as Booking's own table.

**`payments`** — `id`, `payment_attempt_id` (FK, unique — one `Payment` per attempt), `booking_id`, `student_id`, `amount_kobo`, `currency`, `provider_reference`, `confirmed_at`.

**`fund_dispositions`** — `id`, `payment_id` (FK, unique), `held_amount_kobo`, `status` (indexed), `created_at`.

**`release_operations`** / **`refund_operations`** — identical shape: `id`, `fund_disposition_id` (FK), `amount_kobo`, `status` (indexed — needed for the pending-operation recovery job, Chunk 11), `decision_id` (FK to `release_decisions`), `provider_operation_reference` (nullable, **unique when not null** — the provider-side idempotency anchor), `requested_at`, `confirmed_at` (nullable), `failure_reason` (nullable).

**`disputes`** — `id`, `fund_disposition_id` (FK, indexed), `raised_by` (UUID, no FK), `reason`, `status` (indexed — partial unique index: `WHERE status = 'OPEN'`, at most one open dispute per fund disposition, same partial-index technique as Housing's `is_main_campus`), `raised_at`, `resolved_at`/`resolved_by`/`resolution_notes` (nullable).

(`release_decisions`, `provider_webhook_events`, and `ledger_entries` are defined in Chunks 8, 7, and 10 respectively, where they're actually used — splitting the schema across the chunks that need each table keeps each chunk reviewable on its own, rather than asking you to reason about nine tables before any of them have a use case behind them.)

**No foreign keys into Booking's or Identity's tables anywhere** — same cross-module discipline as every other module in this project.

**`PaymentRepository`, `FundDispositionRepository`, `DisputeRepository`:** standard `add`/`get_by_id`/`update` plus the specific lookups each use case needs (`get_attempt_by_idempotency_key`, `find_fund_dispositions_eligible_for_auto_release`, etc. — defined precisely as each consuming chunk needs them, not speculatively here). **Every status transition that matters for correctness (payment confirmation, release/refund execution, dispute resolution) uses the same conditional `UPDATE ... WHERE status = <expected>` pattern as Housing's reservation, Verification's decisions, and Booking's confirm/cancel** — defined precisely in each chunk that performs one, not restated here.

**Migration:** `poetry run alembic revision --autogenerate -m "add payment core tables"`, read closely before applying.

**Tests you must write:** `tests/integration/payment/test_repositories.py` (marked `integration`) — CRUD across all five repositories so far; the idempotency-key uniqueness constraint; the partial unique index on open disputes (attempt to create a second `OPEN` dispute for the same fund disposition, confirm it's rejected at the database level, same bypass-the-application-layer verification discipline as every previous partial-index test in this project).

**Acceptance criteria:** new tests pass against local Termux Postgres; migration applies cleanly.


---

### CHUNK 5 — DETERMINISTIC MOCK ADAPTER
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/provider/mock/mock_provider_adapter.py`, `adapters/provider/mock/mock_control_router.py`.

**`MockPaymentProviderAdapter`:** implements all five capability protocols from Chunk 3, declares `ProviderCapabilities` with every flag `True`. Deterministic scenario control via a `scenario` field accepted on `InitiatePaymentCommand.return_context` (test/dev-only — document this field as mock-specific, never meaningful to a real adapter): `"success"` (default), `"failure"`, `"pending_then_success"`, `"pending_then_failure"`, `"timeout"`, `"duplicate_webhook"`, `"invalid_signature"`, `"amount_mismatch"`, `"uncertain_outcome"` — each produces the exact provider behavior its name describes when the corresponding checkout-simulation/webhook-simulation control is invoked.

**`mock_control_router.py`** — a **separate, small FastAPI router** (not merged into the main payment API router) exposing endpoints like `POST /api/v1/payment-mock-controls/{attempt_id}/simulate-webhook` that let tests and manual QA trigger these scenarios on demand. **This router is only ever mounted when `Settings.app_env` is `local` or `test`** — `app.py` checks this explicitly at startup and simply does not call `include_router` for it otherwise; this is an enforced structural guard, not a documented convention someone could forget (Part 7's explicit requirement: "must never be accessible to ordinary users in a live environment").

**Tests you must write:** `tests/unit/payment/adapters/test_mock_provider_adapter.py` — one test per scenario listed above, confirming the adapter produces exactly the described behavior; `tests/api/payment/test_mock_controls_not_mounted.py` — start the app with `app_env="staging"` (or any non-local/test value) and confirm the mock-control routes return `404`, not just that they're undocumented.

**Acceptance criteria:** new tests pass; the mock-controls-not-mounted test specifically is non-negotiable — a payment mock control reachable in a live-like environment is a real security defect, not a cosmetic one.

---

### CHUNK 6 — PAYMENT INITIATION & BOOKING INTEGRATION
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/booking/booking_provider.py`, `application/use_cases/initiate_payment.py`.

**`BookingProvider`** (outbound port + `InProcessBookingProvider` adapter, same established pattern): `get_booking(booking_id) -> BookingSummary | None` (carries `status`, `student_id`, `property_id`, `amount_kobo`/`currency`/`period`, `expires_at`), `get_handover_status(booking_id) -> HandoverStatus` (carries `offered_at`/`accepted_at`, both nullable — Chunk 1's addition). Calls Booking's `GetBooking` and the two new handover-query equivalents directly, `application.ports` only.

**`InitiatePayment` — steps:**
1. **Idempotency check first** — `get_attempt_by_idempotency_key(student_id, idempotency_key)`; if found, return it as-is, same replay-is-success discipline as Booking's own `CreateBooking`.
2. Resolve the booking via `BookingProvider.get_booking`; `BookingNotFound` if absent.
3. Confirm the caller is the booking's own `student_id` — anyone else, `Forbidden`.
4. Confirm `booking.status == AWAITING_PAYMENT` and the hold is not already expired (compute this the same way Booking itself would — ask Booking for the authoritative fact via `get_booking` rather than re-deriving expiry logic independently; if Booking's own response already reflects "this hold is no longer valid," trust that, don't second-guess it) — anything else, `BookingNotEligibleForPayment`.
5. **Use the booking's price snapshot as the trusted amount — never anything the client supplied** (Part 9's explicit requirement; there is in fact no amount field anywhere in this use case's request DTO at all, by design, not merely by convention).
6. Construct a `PaymentAttempt` (`status=INITIATED`), persist.
7. Check `ProviderCapabilities.supports_initiation`; call `PaymentInitiationCapability.initiate`.
8. On success: update to `status=PENDING`, store `provider_reference`; log INFO; return the checkout reference to the caller.
9. **On provider initiation failure:** update the attempt to `status=FAILED` (the record stays, per Part 9: "preserve an appropriate failure/recovery record rather than losing traceability" — never delete it, never leave it stuck at `INITIATED`); log at WARNING; propagate a clear error.

**Tests you must write:** `tests/unit/payment/application/test_initiate_payment.py`, against fakes — happy path; idempotent replay (confirm the fake provider's `initiate` is **not** called a second time); wrong student rejected; expired/invalid booking state rejected; provider failure leaves the attempt `FAILED`, not stuck or silently discarded.

**Acceptance criteria:** new tests pass, all against fakes.


---

### CHUNK 7 — CONFIRMATION & WEBHOOK PROCESSING
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/process_webhook_event.py`, `application/use_cases/verify_payment_attempt.py`.

**New table, `provider_webhook_events`:** `id`, `provider_name`, `provider_event_id` (text, **unique** — the dedup key, Part 17), `raw_payload_digest` (text — a SHA-256 hex digest of the raw body, for audit/replay verification; **not the raw payload itself**, per Part 17's explicit retention guidance), `normalized_event_type`, `correlated_attempt_id` (nullable UUID, no FK), `processing_status` (`RECEIVED`, `PROCESSED`, `IGNORED_DUPLICATE`, `FAILED_VALIDATION`, `UNCORRELATED` — `CHECK` restricted), `received_at`, `processed_at` (nullable).

**`ProcessWebhookEvent` — steps, in order, each one a real safety requirement, not a nice-to-have:**
1. **Verify signature first, before parsing anything** (`WebhookCapability.verify_signature`) — on failure, record a `provider_webhook_events` row with `processing_status=FAILED_VALIDATION` and stop; **do not attempt to parse or act on the body at all** past this point; log at WARNING (a forged webhook attempt is worth knowing about).
2. Parse into a `NormalizedProviderEvent` (`WebhookCapability.parse_event`).
3. **Deduplicate** — check `provider_event_id` against existing rows; if already present, record this delivery as `IGNORED_DUPLICATE` and stop (acknowledge success to the provider regardless — a duplicate is not a failure from the provider's point of view, and re-acknowledging prevents needless retries).
4. Correlate to a known `PaymentAttempt` via `provider_reference`; not found → `UNCORRELATED`, log at WARNING (this can legitimately happen — a webhook for a test/stale reference — but it's worth watching for), stop.
5. **Verify amount and currency match the attempt's own recorded amount** — a mismatch is never silently accepted; record `FAILED_VALIDATION`, log at ERROR (this is a genuine integrity concern, not routine), and do **not** apply any state change.
6. **Branch on the attempt's current status:**
   - If `PENDING`: this is the expected path — call `verify_payment_attempt` below with the provider's own reported outcome as corroboration, not as the sole source of truth (Part 9's "authoritative verification," not "trust the webhook body alone" — re-verify via `PaymentVerificationCapability.verify_transaction` using the provider's own reference, independent of what the webhook claimed, before treating this as confirmed).
   - If already terminal (`SUCCEEDED`/`FAILED`/`EXPIRED`/`CANCELLED`) **and** the event reports success: call `PaymentAttempt.record_late_success_signal()` (ADR-107) — do **not** change `status`; instead, create and persist a late-recovery record (Chunk 11 defines exactly what happens with it) and stop here, this use case's job ends at flagging it for recovery, not resolving it.
   - If already `SUCCEEDED` and the event reports success again: this is a legitimate re-delivery of a known-good event (not a true duplicate by `provider_event_id`, but the same underlying fact) — record `PROCESSED`, no state change needed, nothing more to do.
7. Record `processing_status=PROCESSED`; log INFO.

**`VerifyPaymentAttempt` — steps (the actual confirmation logic, called both from the webhook path above and potentially from Chunk 11's uncertain-outcome recovery job):**
1. Call `PaymentVerificationCapability.verify_transaction(provider_reference)` — the authoritative check, independent of whatever triggered this call.
2. If the provider confirms success and amount/currency match: **concurrency-safe transition** — conditional `UPDATE payment_attempts SET status='SUCCEEDED' WHERE status='PENDING'` (same atomic-write discipline as every other state-critical write in this project); zero rows matched means someone else already resolved it (a race between the webhook path and a manual/scheduled re-verification) — treat as success anyway if a `Payment` already exists for this attempt, otherwise log and investigate.
3. **Only once that conditional update actually matches:** construct the `Payment` record and the `FundDisposition` (`status=HELD`, `held_amount_kobo` = the payment amount) — **in the same transaction** as the attempt's status update, so a `Payment`/`FundDisposition` pair is never created without its attempt genuinely being marked `SUCCEEDED`, and vice versa.
4. **Notify Booking** — call `ConfirmBooking` (Finding 1) with the booking id. **If Booking rejects this** (the hold had already expired, or something else changed Booking's state in the meantime) — this is exactly the late-payment race the handoff calls out by name (Part 12): do **not** treat this as a processing failure of the payment itself (the money genuinely arrived) — instead, flag the resulting `FundDisposition` for the late-payment recovery workflow (Chunk 11), which determines whether a refund is owed, since Payment must never resurrect an expired booking on its own authority.
5. Log INFO on success, including which path confirmed it.

**Tests you must write:** `tests/unit/payment/application/test_process_webhook_event.py` — every step above as its own test: invalid signature never reaches parsing; duplicate event is a no-op acknowledged as success; uncorrelated event logged and stopped; amount mismatch rejected without a state change; the late-success-signal path creates a recovery record without touching the terminal attempt's status (assert `status` is unchanged after the call). `tests/unit/payment/application/test_verify_payment_attempt.py` — the concurrency guard (fake repository reports zero rows matched on an already-resolved attempt, confirm no duplicate `Payment`/`FundDisposition` is created); the Booking-rejects-confirmation path specifically, confirming it does **not** raise a generic error but instead routes into the recovery flagging described in step 4.

**Acceptance criteria:** new tests pass, all against fakes. The late-success and Booking-rejection paths get the same seriousness as Booking's own compensating-transaction test — these are the two places in this chunk where a missed case means real money gets mishandled, not just a wrong HTTP response.


---

### CHUNK 8 — ESCROW HOLDS & RELEASE POLICY
**[FOR YOU — GEMINI CLI]**

**Objective:** implement the nine-condition release policy from the handoff (Part 10), exactly, as one precise, testable, pure-domain evaluation function plus the use cases that act on its result.

**Files to modify:** `domain/release_policy.py`.
**Files to create:** `application/use_cases/raise_dispute.py`, `application/use_cases/resolve_dispute.py`, `application/use_cases/evaluate_release_eligibility.py`, `application/use_cases/authorize_release.py`, `application/use_cases/execute_release.py`.

**New table, `release_decisions`** (the audit record from Part 10's own field list, implemented verbatim): `id`, `fund_disposition_id` (FK), `decision` (`RELEASE`/`REFUND`, `CHECK` restricted), `amount_kobo`, `currency`, `policy_version` (text — a simple version string identifying this policy's own logic revision, so a historical decision stays traceable to the rules that produced it even after this function changes later), `triggering_fact` (text — `"automatic_48h_fallback"`, `"student_accepted"`, `"dispute_resolved_release"`, `"dispute_resolved_refund"`, `"manual_admin_decision"`), `evidence_reference` (nullable text), `decided_at`, `origin` (`AUTOMATIC`/`MANUAL`), `authorized_by` (nullable UUID, no FK — set only for `MANUAL`), `reason` (text, required non-empty).

**`evaluate_release_eligibility(fund_disposition, booking_summary, handover_status, dispute_status, requested_amount, clock) -> ReleaseEvaluation`** — a pure function, domain-layer, no I/O of its own (everything it needs is passed in by the calling use case, which already fetched it) — `ReleaseEvaluation` carries `eligible: bool` and, if not, `blocking_reason: str` naming exactly which condition failed. **Walks the nine conditions from the handoff, in this exact order, stopping at the first failure:**

1. **Payment confirmed** — a `Payment`/`FundDisposition` exists at all (true by construction if this function is being called on a real `FundDisposition`, but check it explicitly rather than assuming).
2. **Booking still valid** — `booking_summary.status in (AWAITING_PAYMENT, CONFIRMED)` is not actually the right check here since payment already succeeded; the real check is that Booking hasn't independently cancelled this reservation since (`booking_summary.status != CANCELLED`).
3. **Handover offered** — `handover_status.offered_at is not None`. Not offered yet → not eligible, `blocking_reason="handover_not_offered"` — this is a normal, expected "not yet," not an error state.
4. **Handover accepted, or the 48-hour window has elapsed with no dispute** — `handover_status.accepted_at is not None` **or** `clock.now() - handover_status.offered_at >= settings.release_fallback_window` **and** no `OPEN` dispute exists. Neither condition met → not eligible, `blocking_reason="awaiting_acceptance_or_window"`.
5. **No dispute hold** — `dispute_status != OPEN`. An open dispute → not eligible, `blocking_reason="dispute_open"`, regardless of how long it's been open (Part 10, Condition 6: "A pending dispute must never silently expire into an automatic release").
6. **Amount within remaining releasable balance** — `requested_amount <= fund_disposition.remaining_releasable_kobo`. Exceeds it → not eligible, `blocking_reason="amount_exceeds_remaining_balance"`.
7. **No equivalent release already executed** — checked by the calling use case via idempotency (a specific decision/operation reference), not re-derived here.
8. **Authorization** — explicitly **not** checked by this function at all; that's `AuthorizeRelease`'s job via Security, kept separate because "are the facts right" and "is this actor allowed" are different kinds of question, same separation every other module in this project has maintained.
9. **Execute and reconcile** — the next chunk's concern, not evaluation's.

`settings.release_fallback_window` is `Settings.payment_release_fallback_hours: int = 48` — configurable, server-side only, **never influenced by anything client-supplied** (Part 10, Condition 5's explicit requirement).

**`RaiseDispute` — steps:** confirm the caller is the fund disposition's own student (via the linked payment/booking); confirm no `OPEN` dispute already exists (the partial unique index, Chunk 4, is the real guarantee; this is the fast, friendly check in front of it); require a non-empty reason; create the `Dispute`; **set `FundDisposition.status = DISPUTE_HOLD`** (this is what makes condition 5 above actually block — the dispute's mere existence is what `evaluate_release_eligibility` checks); log at WARNING (a dispute is a signal worth noticing, not a routine event).

**`ResolveDispute` — steps:** authorize via `PAYMENT_AUTHORIZE_RELEASE` or `PAYMENT_AUTHORIZE_REFUND` depending on which resolution is being recorded (checked precisely — resolving toward release needs the release permission, toward refund needs the refund permission, even though both are "resolving a dispute"); set the dispute's `resolved_*` fields and status; **clear the `DISPUTE_HOLD` back to `HELD`** if the resolution isn't an immediate refund (so a subsequent release attempt can proceed normally); if the resolution includes a refund amount, delegate to `ExecuteRelease`'s refund counterpart (Chunk 9) rather than duplicating execution logic here.

**`EvaluateReleaseEligibility` (the use case wrapping the pure function) — steps:** gather the real facts (fund disposition, booking summary via `BookingProvider`, handover status via `BookingProvider`, current dispute status) and call the pure function above; return its result as-is. This use case has a legitimate reason to exist as a standalone, callable thing — both the manual release endpoint and the automatic-fallback job (Chunk 11) need the exact same evaluation, and defining it once here means neither can quietly drift out of sync with the other.

**`AuthorizeRelease` — steps:** call `EvaluateReleaseEligibility`; not eligible → raise `ReleaseNotEligible` naming the blocking reason; authorize via `PAYMENT_AUTHORIZE_RELEASE` (manual path) — **the automatic-fallback job, Chunk 11, calls this same use case but with `origin=AUTOMATIC` and no Security check**, since there's no human actor to authorize against in that path, by design, not by oversight; construct and persist the `ReleaseDecision` record (Part 10's field list, in full) **before** any provider call happens (Part 10, Condition 9: "Record the release decision before initiating the external operation"); return the decision.

**Tests you must write:** `tests/unit/payment/domain/test_release_policy.py` — each of the nine conditions tested individually, including the specific "offered but not accepted and window not elapsed" vs "window elapsed with no dispute" vs "window elapsed but dispute open" three-way distinction, since that's the exact nuance Condition 5/6 are about. `tests/unit/payment/application/test_raise_dispute.py`, `test_resolve_dispute.py`, `test_authorize_release.py` — against fakes, covering authorization paths and the decision-recorded-before-execution ordering (assert `ReleaseDecision` exists even if you stop the test before any provider call would happen).

**Acceptance criteria:** new tests pass, all against fakes. The nine-condition test file specifically should read as a direct, line-by-line proof of Part 10 of the original handoff — a future reader should be able to check this spec against that test file and see every condition accounted for.


---

### CHUNK 9 — EXECUTION: RELEASES, REFUNDS, PAYOUTS
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `application/use_cases/execute_release.py` (created in Chunk 8, implemented here).
**Files to create:** `application/use_cases/execute_refund.py`.

**`ExecuteRelease` — steps, continuing from `AuthorizeRelease`'s already-persisted `ReleaseDecision`:**
1. Create the `ReleaseOperation` row (`status=DECISION_RECORDED`, linked to the decision).
2. Check `ProviderCapabilities.supports_payouts` — unsupported → `status=RECONCILIATION_REQUIRED`, log at ERROR (a release decision that can't actually be executed is a real operational problem, not routine), stop; **never silently report success for an unsupported capability** (Part 7A's explicit instruction, applied here).
3. Call `PayoutCapability.initiate_payout`, passing the operation's own `id` as the idempotency key the provider port uses — `status=PROVIDER_INITIATED`, store `provider_operation_reference`.
4. **The provider accepting the request is not proof funds arrived** (Part 14's explicit warning) — `status=PROVIDER_PENDING` until a subsequent verification (immediate, if the capability returns a definitive result synchronously, or via the recovery job in Chunk 11 otherwise) confirms `SUCCEEDED` or `FAILED`.
5. **Concurrency-safe update to the `FundDisposition`** on confirmed success: conditional `UPDATE ... WHERE status IN ('HELD', 'PARTIALLY_RELEASED')` — recompute `status` based on the new `released_amount_kobo` vs `held_amount_kobo` (`PARTIALLY_RELEASED` if less than the full balance, `RELEASED` if it now equals it) — same atomic-write discipline as every status-critical write in this chunk's predecessors.
6. Log INFO on confirmed success; WARNING on `FAILED`/`RECONCILIATION_REQUIRED`.

**`ExecuteRefund` — same shape, with one real difference worth naming explicitly:** refunds can be **automatic** (triggered by the late-payment recovery workflow, Chunk 11, with no human decision behind them) as well as manual (authorized via `PAYMENT_AUTHORIZE_REFUND`, same `ReleaseDecision`-style record first, same decision-before-execution ordering). Steps otherwise mirror `ExecuteRelease` exactly, using `RefundCapability` instead of `PayoutCapability`, and updating `FundDisposition.status` toward `PARTIALLY_REFUNDED`/`REFUNDED` instead.

**Idempotency across both (Part 18):** the `ReleaseOperation`/`RefundOperation`'s own `id` is what's passed to the provider as the idempotency key — if `ExecuteRelease`/`ExecuteRefund` is somehow invoked twice for the same decision (a retried request, a duplicate job run), the **second** call must find the existing operation row (by `decision_id`) already in a non-`DECISION_RECORDED` state and return it as-is rather than initiating a second provider call. Implement this check as the very first step of both use cases, before anything else.

**Tests you must write:** `tests/unit/payment/application/test_execute_release.py`, `test_execute_refund.py` — happy path for each; unsupported-capability handling (status becomes `RECONCILIATION_REQUIRED`, never a false success); the idempotent-retry proof (call the use case twice for the same decision, assert the fake provider's payout/refund method was called **exactly once**); `FundDisposition.status` correctly reflects partial vs full release/refund.

**Acceptance criteria:** new tests pass, all against fakes. The double-invocation idempotency test is as important here as the compensating-transaction tests were in Booking — a duplicate payout is a direct, real financial loss, not a bug report.

---

### CHUNK 10 — LEDGER & RECONCILIATION
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/record_ledger_entry.py`, `application/use_cases/reconcile_payments.py`, `adapters/persistence/ledger_repository.py`.

**New table, `ledger_entries`** (append-only — no repository method ever updates or deletes a row here, same discipline as Verification's history table): `id`, `payment_id` (nullable UUID, no FK), `fund_disposition_id` (nullable UUID, no FK), `entry_type` (`CHECK` restricted — `CHARGE`/`HOLD_ALLOCATION`/`RELEASE`/`REFUND`/`REVERSAL`/`CORRECTION`), `amount_kobo` (bigint — **signed**: positive for inflows (`CHARGE`), negative for outflows (`RELEASE`/`REFUND`) — this is what makes "balance" a plain `SUM`, not a type-dependent calculation), `currency`, `reference_type`/`reference_id` (what triggered this entry — `PAYMENT`/`RELEASE_OPERATION`/`REFUND_OPERATION`, plus that record's id), `created_at`, `description`.

**Posting rule, stated precisely so it's never ambiguous which code path writes which entry:** every use case that changes money's disposition writes exactly one ledger entry, in the *same* database transaction as its own primary state change — `VerifyPaymentAttempt` (Chunk 7) posts one `CHARGE` entry and one `HOLD_ALLOCATION` entry (positive and negative respectively, net zero — the money arrived and immediately became "held," which is itself a real movement worth recording) when it creates the `Payment`/`FundDisposition` pair; `ExecuteRelease`/`ExecuteRefund` (Chunk 9) each post one entry of the matching type on **confirmed** success only (never on `PROVIDER_PENDING` — a ledger entry represents a confirmed fact, not an in-flight attempt).

**The balancing invariant (Part 15), made concrete and testable:** for any `FundDisposition`, `SUM(ledger_entries.amount_kobo WHERE fund_disposition_id = this one) == -(released_amount_kobo + refunded_amount_kobo) + held_amount_kobo`'s own running total should always reconcile to the disposition's own computed `remaining_releasable_kobo`. Write this as an actual repeatable check (`application/use_cases/reconcile_payments.py`'s own internal self-check, not just a one-off test), since this is exactly the kind of invariant that should be *continuously* verifiable, not just verified once at build time.

**`ReconcilePayments` — steps (deliberately modest, given no real provider is selected yet, ADR-110):** for each `FundDisposition` not in a terminal state, re-verify its underlying `Payment`'s `provider_reference` via `PaymentVerificationCapability.verify_transaction` and compare against the internal record; a mismatch (status disagreement, amount disagreement, or a provider reference with no matching internal record at all) is recorded as a new, explicit `RECONCILIATION_REQUIRED` state on the affected disposition — **never silently corrected automatically**. This is a framework proven against the mock adapter's own deterministic "mismatch" scenarios (Chunk 5); a real provider's actual settlement-report/import mechanics are explicitly out of scope until a real provider exists (documented as such in Chunk 14, not glossed over).

**Tests you must write:** `tests/unit/payment/application/test_record_ledger_entry.py` — entries post with the correct sign per type; `tests/integration/payment/test_ledger_balance.py` (marked `integration`, real database) — run a full payment → release → partial refund sequence and assert the balancing invariant holds exactly at every step, not just at the end; `tests/unit/payment/application/test_reconcile_payments.py` — a deliberate mismatch (via the mock adapter's scenario control) is caught and flagged, never silently resolved.

**Acceptance criteria:** new tests pass; the balance-invariant test is the single most important test in this chunk — if it can ever fail even transiently mid-sequence, that's a real ledger-integrity defect, not a timing quirk to wave away.


---

### CHUNK 11 — RECOVERY & BACKGROUND PROCESSING
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/process_late_payment_signal.py`, `application/use_cases/process_automatic_releases.py`, `application/use_cases/reprocess_uncertain_attempts.py`, `scripts/run_payment_recovery.py`.

**No scheduler, no task queue, no new infrastructure (Part 21's own instruction) — same established pattern as Booking's `ExpireHolds` and University & Location's CSV importer:** one script, invoked manually or via a plain cron entry, composing the three use cases below and running each once per invocation.

**`ProcessLatePaymentSignal`** (resolves the recovery records Chunk 7's `record_late_success_signal` creates) **— steps:** for each unresolved late-signal record: re-check the booking's **current** state via `BookingProvider` — if it's since been re-booked by someone else or is otherwise no longer honorable, the money genuinely arrived for a reservation that no longer exists, so initiate an **automatic** refund (origin=`AUTOMATIC`, triggering_fact=`"late_payment_unhonorable_booking"`, no human authorization needed, same reasoning as the handoff's own Part 12: "avoid releasing funds for an invalid booking," by definition this can never become a release); if the booking is somehow still genuinely honorable (e.g., it hadn't actually expired, just appeared to due to a timing quirk the scheduler hadn't caught), proceed through normal `VerifyPaymentAttempt` confirmation instead. Either way, mark the recovery record resolved; log at WARNING either direction (both are noteworthy, neither is routine).

**`ProcessAutomaticReleases`** (the 48-hour fallback, made concrete) **— steps:** find every `FundDisposition` in `HELD` status; for each, call `EvaluateReleaseEligibility` (Chunk 8, the exact same function the manual path uses — no drift possible between the two); eligible **and** the only remaining blocking factor was the time window (not a dispute, not an unresolved handover) → call `AuthorizeRelease` with `origin=AUTOMATIC`, `triggering_fact="automatic_48h_fallback"`, no Security check (there's no actor); not eligible → skip silently, this is the normal case for most dispositions on most runs, not worth logging per-skip. Log a summary count at the end (processed, released, skipped).

**`ReprocessUncertainAttempts`** — finds `PaymentAttempt`s stuck in `PENDING` past a configurable staleness threshold (`Settings.payment_verification_staleness_minutes: int = 15`) and `ReleaseOperation`/`RefundOperation`s stuck in `PROVIDER_PENDING`; re-runs verification/status-check against the provider for each — **a timeout is never treated as proof of failure** (Part 9/14's explicit instruction) — only an authoritative provider response (success, failure, or genuinely "still pending, try again later") updates anything.

**Tests you must write:** one file per use case, against fakes — `ProcessLatePaymentSignal`'s two branches (honorable vs unhonorable booking); `ProcessAutomaticReleases` only acting on genuinely eligible dispositions, confirmed by constructing one `HELD` disposition with an open dispute and one without, asserting only the latter gets released; `ReprocessUncertainAttempts` never flips a `PENDING` attempt to `FAILED` on a bare timeout, only on an authoritative failure response from the fake provider.

**Acceptance criteria:** new tests pass, all against fakes.

---

### CHUNK 12 — FASTAPI & SECURITY INTEGRATION
**[FOR YOU — GEMINI CLI]**

**Files to modify (Security, using its own documented extension recipe):** `modules/security/domain/value_objects.py` (add `PAYMENT_REVIEW`, `PAYMENT_AUTHORIZE_RELEASE`, `PAYMENT_AUTHORIZE_REFUND` to `Permission` — all role-scoped), `modules/security/domain/policy.py` (`PAYMENT_REVIEW` → `OPERATIONS`, `ADMIN`; `PAYMENT_AUTHORIZE_RELEASE`/`PAYMENT_AUTHORIZE_REFUND` → **`ADMIN` only**, ADR-108).

**Prohibition:** exactly those lines — nothing else in Security changes.

**Files to create:** `adapters/api/schemas.py`, `adapters/api/router.py`, `adapters/api/webhook_router.py`, `adapters/api/dependencies.py`.
**Files to modify:** `app.py` (mount both routers, plus the mock-control router from Chunk 5 conditionally).

**Ten endpoints:**

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/api/v1/payments` | authenticated | `booking_id`, `idempotency_key` only |
| GET | `/api/v1/payments/{id}` | owner or `PAYMENT_REVIEW` | |
| GET | `/api/v1/payments/mine` | authenticated | self-scoped |
| POST | `/api/v1/payments/webhooks/{provider_name}` | **provider signature only, no user auth** | separate router, different middleware stack |
| POST | `/api/v1/payments/{id}/disputes` | booking's own student | |
| GET | `/api/v1/payments/{id}/disputes` | owner or `PAYMENT_REVIEW` | |
| GET | `/api/v1/payments/disputes/pending` | `PAYMENT_REVIEW` | |
| POST | `/api/v1/payments/disputes/{id}/resolve` | `PAYMENT_AUTHORIZE_RELEASE` or `_REFUND` (per resolution) | |
| POST | `/api/v1/payments/{id}/release` | `PAYMENT_AUTHORIZE_RELEASE` | manual/early release |
| POST | `/api/v1/payments/{id}/refund` | `PAYMENT_AUTHORIZE_REFUND` | manual refund |

**The webhook router specifically:** no `get_current_identity_id` dependency at all — provider webhooks aren't an authenticated user action, they're validated entirely by `WebhookCapability.verify_signature` inside `ProcessWebhookEvent` itself (Chunk 7). Mounting it on a genuinely separate router (not just a route with a different dependency) makes this structurally obvious to a future reader, not just documented.

**Request DTOs contain only client-authorized fields, by construction, not by convention (Part 20):** no payment-creation DTO anywhere has an `amount`, `status`, or anything resembling one.

**Prohibition, same as every module before this one:** no business logic in `router.py`.

**Tests you must write:** placeholder only — real API tests arrive in Chunk 13.

**Acceptance criteria:** the app starts; the webhook route accepts an unauthenticated request and correctly rejects a bad signature; every other endpoint enforces its row's auth/permission combination.


---

### CHUNK 13 — AUTOMATED TESTS & CONCURRENCY AUDIT
**[FOR YOU — GEMINI CLI]**

**This chunk must not be skipped or abbreviated — the handoff is explicit that a happy-path integration test alone is not sufficient, and for this module specifically, that's correct.**

**Files to create:** `tests/api/payment/test_payment_flow.py`, `test_webhook_scenarios.py`, `test_concurrency.py`, `test_security.py`.

**`test_payment_flow.py`:** the full real-HTTP happy path — initiate, simulate provider success via the mock control, confirm `Payment`/`FundDisposition` exist and Booking is confirmed; handover offered, handover accepted; manual release by an `ADMIN`; confirm the ledger balances at every step along the way, not just at the end.

**`test_webhook_scenarios.py`:** every scenario from Part 7D and Part 22's webhook test list, through real HTTP against the mock-controlled webhook endpoint — valid signature, invalid signature, duplicate event, unknown reference, amount mismatch, out-of-order events, delayed success after expiration (the late-signal path, end to end).

**`test_concurrency.py`, using real concurrent requests against the real test database, same standard as Housing's and Booking's own concurrency tests — not sequential calls dressed up as concurrent:**
- Two simultaneous release attempts against the same `FundDisposition`'s full remaining balance — exactly one succeeds.
- Two simultaneous refund attempts against the same remaining balance — exactly one succeeds, or both succeed only if their combined amount is actually within balance (test both the over-balance and within-balance cases).
- Automatic release racing a dispute being raised at nearly the same instant — the dispute must win (no release executes once `DISPUTE_HOLD` is set, verified by actually racing them, not just testing each path in isolation).
- A refund and a release racing against the same funds — the one that would exceed the remaining balance must fail cleanly, not corrupt the balance.
- **Run this entire file at least three times in a row before considering the module ready** — same reliability bar every concurrency-critical test in this project has been held to.

**`test_security.py`:** a student cannot view another student's payment; a student cannot call any release/refund/dispute-resolution endpoint; `PAYMENT_REVIEW` alone (without `PAYMENT_AUTHORIZE_*`) cannot execute a release or refund — only view; the mock-control router returns `404` outside local/test configuration (re-confirmed here at the full-suite level, not just Chunk 5's isolated test); no response anywhere in this module exposes a provider secret or full raw webhook payload.

**Run everything:** `poetry run pytest`, `poetry run ruff check .`, `poetry run mypy src`, `poetry run lint-imports` — the whole project, every module built so far, green. **Fix every defect found here before proceeding to Chunk 14** — per the handoff's own instruction, this chunk is a gate, not a formality.

**Acceptance criteria:** every scenario above passes, with the concurrency suite specifically run multiple times and passing reliably.

---

### CHUNK 14 — DOCUMENTATION & FRONTEND INTEGRATION
**[FOR YOU — GEMINI CLI]**

See "Module Documentation Requirements," "Frontend Documentation," and "AI State Requirements" below. Use the standard `CURRENT_TASK.md` status-block format throughout.

---

### CHUNK 15 — FINAL ARCHITECTURE & READINESS AUDIT
**[FOR YOU — GEMINI CLI]**

Confirm every item in the Completion Checklist below. Then produce the explicit readiness classification the handoff requires (Part 24) — answer each of the following plainly, in the Completion Report, not just "done":

- Core workflow implemented: yes/no.
- Mock-provider tests passing: yes/no.
- Real provider adapter: absent (expected — none was to be built) or present.
- Provider sandbox integration tested: not applicable (no provider selected).
- Actual custody/release capability verified against a real financial institution: **not verified** — state this explicitly, do not imply otherwise.
- Production/legal/compliance readiness: **not established** — state this explicitly. Nothing in this module constitutes a legal or regulatory opinion.

**Do not round any of these up.** A passing mock-provider test suite proves the internal logic is sound; it proves nothing about whether Camp Match can legally or operationally hold and release real money yet.


---

## PART D — PROVIDER CAPABILITY CHECKLIST [FOR NSISONG — for when you're ready to select a real provider, deliberately, not automatically]

No provider is chosen here, per instruction. When you're ready, evaluate any candidate (Paystack, Flutterwave, or otherwise) against every item below — each one maps directly to something this module's contracts assume:

**Core transaction support**
- [ ] Supports NGN-denominated transactions natively.
- [ ] Checkout/payment-session initiation, with a redirect or embeddable flow suitable for your frontend.
- [ ] A transaction-verification endpoint independent of the webhook (this module calls this *in addition to* trusting a webhook — confirm it exists and is authoritative).

**Webhooks**
- [ ] Documented webhook signature scheme (HMAC or equivalent) — confirm you can implement `WebhookCapability.verify_signature` against it exactly.
- [ ] A stable, unique event identifier per webhook delivery (this module's deduplication depends on one existing).
- [ ] Documented retry/redelivery behavior, so `ProcessWebhookEvent`'s acknowledgment semantics (Chunk 7) can be tuned correctly.

**Refunds**
- [ ] Full refund support.
- [ ] **Partial** refund support, specifically — confirm this explicitly; some providers only support full refunds, which would mean `ExecuteRefund`'s partial-amount path needs to degrade (full refund only) for that provider, declared via `ProviderCapabilities.supports_refunds` with a documented caveat.
- [ ] A refund-status query endpoint, independent of a webhook (for `ReprocessUncertainAttempts`, Chunk 11).

**Payouts / transfers**
- [ ] Payout or transfer-to-recipient capability, with Nigerian bank account support.
- [ ] A payout-status query endpoint, independent of a webhook.
- [ ] Documented payout idempotency mechanism (a client-supplied reference the provider itself deduplicates on) — confirm it exists; this module's own `ReleaseOperation.id`-as-idempotency-key design (Chunk 9) assumes the provider actually honors one.

**The genuinely critical one — real custody, not just split settlement**
- [ ] **Confirm, in writing from the provider's own documentation, whether funds are actually held in a delayed-settlement/custody arrangement you control the release timing of — or whether the provider's "split payment" feature just routes money to the recipient on its own schedule regardless of what this module's `HELD` status says.** This is the single most important item on this checklist (Part 8's own explicit warning) — if the answer is the latter, this module's entire release-policy logic (Chunk 8) becomes a tracking/audit layer describing money that already moved, not actual escrow, and that distinction needs to be understood and decided on deliberately, not discovered after integration.

**Sandbox & operations**
- [ ] A genuine test/sandbox environment, separate credentials from live.
- [ ] Documented merchant/subaccount onboarding requirements (KYB) for a Nigerian business.
- [ ] Rate limits documented, and compatible with this module's expected call patterns (especially `ReprocessUncertainAttempts`'s polling, Chunk 11).

**Compliance — flagged, not resolved here**
- [ ] Confirm with the provider (and separately, with qualified legal/financial advice — not this document) what regulatory obligations apply to Camp Match for holding and disbursing third-party funds in Nigeria, and whether the provider's arrangement satisfies them. **This module makes no claim about this**, per Chunk 15's explicit readiness classification.


---

## FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**Applies everywhere in this module:** no response ever contains a provider secret, a full raw webhook payload, or another student's payment information. Amount fields are always kobo — divide by 100 for display.

### POST /api/v1/payments
**Authentication:** required. **Request body:** `booking_id`, `idempotency_key` (generate once per attempt; reuse on retry after a network error, never generate a new one for the same attempt).
**Success — 201** (or 200 on idempotent replay): `{ "id", "status": "PENDING", "checkout_reference", "expires_at" }`.
**Errors:** 403 (not your booking); 422 `booking_not_eligible_for_payment`.
**Frontend notes:** use `checkout_reference` to drive whatever checkout UI the eventual real provider requires — treat it as opaque.

### GET /api/v1/payments/{id}, /mine
Standard patterns. Response includes `status`, `amount`, `booking_id`, timestamps — never a provider secret, never another student's data.

### POST /api/v1/payments/{id}/disputes
**Authorization:** the payment's own student.
**Request body:** `reason` (required).
**Success — 201.** **Frontend notes:** disputing blocks any pending release immediately — make this clear in the UI copy, since it's a real, immediate effect, not just a complaint form.

### GET /api/v1/payments/{id}/disputes, /payments/disputes/pending
Standard owner/staff visibility patterns.

### POST /api/v1/payments/disputes/{id}/resolve, /payments/{id}/release, /payments/{id}/refund
**Authorization:** staff only, specific permission per action (see Chunk 12's table). **Frontend notes:** these are operational tools, not student-facing — build them into an internal admin surface, not the main app.

---

## MANUAL TESTING GUIDE [FOR NSISONG]

**Preconditions:** `scripts/db_start.sh` running; the app running in `local` config (so mock controls are reachable); a confirmed `AWAITING_PAYMENT` booking (Module 9's own guide) for a Student/Scout pair.

1. **Initiate:** `POST /payments` with the booking id. Expect `201`, `PENDING`.
2. **Simulate success:** use the mock control endpoint to simulate a successful webhook for this attempt. Confirm the payment moves to `SUCCEEDED`, a `Payment` and `FundDisposition` now exist, and — check Booking directly — the booking is now `CONFIRMED`.
3. **Handover:** as the Scout, confirm handover offered; as the Student, confirm handover accepted.
4. **Manual release:** as an `ADMIN`, `POST /payments/{id}/release`. Expect success; confirm `FundDisposition.status` is now `RELEASED`.
5. **Dispute blocks release:** repeat steps 1–3 with a fresh booking, but before releasing, raise a dispute as the Student. Attempt a release as `ADMIN`. Expect rejection — the dispute must block it.
6. **Resolve toward refund:** as `ADMIN` with `PAYMENT_AUTHORIZE_REFUND`, resolve the dispute toward refund. Confirm a `RefundOperation` executes and `FundDisposition.status` reflects it.
7. **Late signal:** simulate a success webhook for an attempt whose booking you've separately let expire first (Module 9's own expiration script). Confirm the original payment attempt's status is untouched (still whatever it was), but a late-recovery record exists, and running the recovery script resolves it toward an automatic refund.
8. **Ledger check:** after the above, query the ledger entries for one of your test fund dispositions directly and confirm they sum to exactly the expected remaining balance.
9. **Security boundary:** as a different Student, attempt to view or act on any of the above payments. Expect rejection on every single endpoint.

**Failure interpretation:** step 5 is the most important check in this entire guide — if a release executes despite an open dispute, that's a direct path to Camp Match losing money it shouldn't have released, and should block everything downstream until fixed. Step 7 failing (the late success silently resurrecting an expired booking, or silently disappearing with no recovery record) is the second most serious — flagged by name in the original handoff for exactly this reason.

---

## AUTOMATED TESTING GUIDE [FOR NSISONG]

- Just Payment: `poetry run pytest tests/unit/payment tests/integration/payment tests/api/payment`
- Domain only (fast, no database): `poetry run pytest tests/unit/payment -v`
- The concurrency suite, run several times: `for i in 1 2 3; do poetry run pytest tests/api/payment/test_concurrency.py -v; done`
- The ledger balance test specifically: `poetry run pytest tests/integration/payment/test_ledger_balance.py -v`
- Full verification: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`
- After this module, re-run Booking's and Security's suites in isolation to confirm each is unaffected apart from its documented, intentional addition.


---

## MODULE DOCUMENTATION REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 14]

Write `docs/modules/payment.md`. Cover: purpose/ownership/non-ownership (Parts A/B of this document, condensed, all three findings included with reasoning intact — a future reader should understand *why* handover facts live on Booking and disputes don't, not just that they do); the five-entity domain model and why each is separate (Payment vs FundDisposition especially, in plain language, not just a field list); the full payment-attempt and fund-disposition state tables; the nine-condition release policy, reproduced in full — this is the part most likely to be revisited when the real policy needs tuning, so it must be immediately usable as a reference, not summarized; the provider-independent contract design and exactly how a real adapter would be added (point to Part D's checklist); the webhook processing sequence and why each step is ordered the way it is; the ledger model, explicitly flagged as simplified/single-sided, not double-entry (ADR-106) — stated plainly so nobody mistakes it for more than it is; idempotency guarantees, listed per operation; the background recovery scripts and how to actually run them; known limitations — explicitly: no real provider, no legal/compliance review, no platform fee modeling, reconciliation framework untested against real settlement data; the Chunk 15 readiness classification, copied verbatim, not softened.

## AI STATE REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 14]

Update `CURRENT_STATE.md`, `PROGRESS.md`, `COMPLETED_WORK.md`, `ARCHITECTURE_STATE.md` (note this is the most complex module built so far, with the highest concurrency/correctness bar, and that it consumed Booking's `ConfirmBooking` exactly as built), `DATABASE_STATE.md`, `API_STATE.md`, `TEST_STATE.md`, `DECISIONS.md` (append ADR-103–111), `SESSION_HANDOFF.md` — set the next task to Module 11 (Messaging), with an explicit note of the Chunk 15 readiness classification so no future session accidentally treats this module as production-ready for real money. Booking's own state should note its two new handover facts. Security's state should note its three new permissions, two of them `ADMIN`-only. Use the standard `CURRENT_TASK.md` status-block format.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] Payment initiation, confirmation, and Booking notification all work end to end against the mock provider.
- [ ] Payment and fund-disposition status are genuinely separate — a successful payment with a pending refund still shows as a successful payment, never overwritten.
- [ ] **The nine-condition release policy is fully implemented and individually tested**, including the specific "offered but not accepted, window not elapsed" vs "window elapsed, no dispute" vs "window elapsed, dispute open" distinction.
- [ ] A dispute genuinely blocks release, proven by racing them concurrently, not just tested sequentially.
- [ ] **The late-payment-signal path never silently resurrects an expired booking and never silently discards a confirmed payment** — both outcomes are explicit, recorded, and tested.
- [ ] Idempotency is proven, not assumed, for initiation, webhook processing, release execution, and refund execution — each with its own specific double-invocation test.
- [ ] The ledger balances exactly at every step of a real payment → release → refund sequence, not just at the end.
- [ ] Mock provider controls are unreachable outside local/test configuration, verified structurally, not just documented.
- [ ] No client request anywhere can supply an authoritative amount, status, or financial decision.
- [ ] Three new Security permissions work correctly, with the two `ADMIN`-only ones genuinely inaccessible to `OPERATIONS`.
- [ ] No cross-module database access in any direction.
- [ ] Unit, integration, API, and architecture tests all pass — every module built so far, together.
- [ ] `docs/modules/payment.md` exists and covers everything above, with the release policy and ledger model explained precisely enough to be a real working reference.
- [ ] All `AI_state/` files updated, including Booking's and Security's.
- [ ] **The Chunk 15 readiness classification is recorded honestly** — mock-tested, not provider-tested; not legally or operationally verified for real custody. This is not optional paperwork; it's the one thing standing between this module and someone assuming it's ready for real money before it is.

