# CAMP MATCH — MODULE 10: PAYMENT & ESCROW DOCUMENTATION

## 1. Purpose & Ownership
Module 10 owns payment processing, custody tracking (escrow holds), release policies, refunds, disputes, and financial ledger logging.
- **Ownership:** `src/camp_match/modules/payment/`
- **Key Boundaries:** Does not own Booking (relies on Booking for reservation state and uses `ConfirmBooking` via `BookingConfirmationPort`). Does not own provider-specific SDKs (uses provider-independent capability protocols).

## 2. Domain Model & Entities
- **PaymentAttempt:** Tracks checkout initiation, provider reference, idempotency keys, and status (`INITIATED`, `PENDING`, `SUCCEEDED`, `FAILED`, `EXPIRED`, `CANCELLED`).
- **Payment:** Immutable historical record of a successfully confirmed payment.
- **FundDisposition:** Tracks the held amount of a payment and its lifecycle across holds, disputes, releases, and refunds (`HELD`, `DISPUTE_HOLD`, `PARTIALLY_RELEASED`, `RELEASED`, `PARTIALLY_REFUNDED`, `REFUNDED`, `RECONCILIATION_REQUIRED`).
- **ReleaseOperation / RefundOperation:** Tracks execution attempts for releases and refunds.
- **Dispute:** Tracks student-raised disputes on fund dispositions.

## 3. The 9-Condition Release Policy
Funds held in escrow are eligible for release only when all conditions are satisfied:
1. Payment confirmed and FundDisposition exists.
2. Booking is active and not cancelled.
3. Handover has been offered by the scout.
4. Handover accepted by student OR 48-hour fallback window elapsed with no open dispute.
5. No open dispute exists.
6. Requested amount is within remaining releasable balance.
7. Decision recorded prior to external operation execution.
8. Provider payout capability supported.
9. Audit decision persisted.

## 4. Provider-Independent Contracts
Provider abstraction via five capability protocols: `PaymentInitiationCapability`, `PaymentVerificationCapability`, `WebhookCapability`, `RefundCapability`, and `PayoutCapability`.

## 5. Webhook Processing Sequence
1. Verify signature (`WebhookCapability.verify_signature`).
2. Parse event (`WebhookCapability.parse_event`).
3. Deduplicate by `provider_event_id`.
4. Correlate to `PaymentAttempt` by `provider_reference`.
5. Verify amount and currency match.
6. Process verification / late success signals.
7. Record `PROCESSED`.

## 6. Ledger & Reconciliation
Append-only `ledger_entries` log signed monetary movements (`CHARGE`, `HOLD_ALLOCATION`, `RELEASE`, `REFUND`, `REVERSAL`, `CORRECTION`). ReconcilePayments verifies active fund dispositions against provider verification records.

## 7. Known Limitations & Readiness Classification
- **Real Provider:** Absent (Mock provider used).
- **Custody / Release Verification:** **Not verified** against a real financial institution.
- **Production / Legal Readiness:** **Not established**. Nothing in this module constitutes a legal or regulatory opinion.
