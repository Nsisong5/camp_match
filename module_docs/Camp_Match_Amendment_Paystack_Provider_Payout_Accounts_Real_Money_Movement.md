# CAMP MATCH — AMENDMENT: PAYSTACK PROVIDER, PAYOUT ACCOUNTS & REAL MONEY MOVEMENT
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Nsisong → Claude: "implement the real payment adapter (Paystack). The existing functionality was built for both the mock and the real provider, so we plug the real one in without breaking the application rules and keeping the existing paradigm. Also add scout and student accounts for releasing funds and refunds, because the actual movement of money for refunds and releases isn't implemented yet."**

**This is an amendment, not a new module.** Paystack is an **adapter** behind Module 10's provider ports. The payout destinations, the bank directory and the refund-account flow are **Payment's** new data. Everything is named in the touch map (C15).

**Prerequisites.** Modules 10 and 15 are complete. **Chunks 12 and 13 additionally require the Release Governance amendment** (`Camp_Match_Amendment_Release_Governance_Admin_Tasks_Transaction_Review.md`) to be complete, because they extend its notifications, transaction review and tasks list. If it is not built when you reach Chunk 12, **stop and report**; Chunks 1–11 do not depend on it. If **Module 18** (self-describing requests) is built, every new route must pass its probe suite; if not, follow its recipe anyway.

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** Gemini reads all of it and works through the chunks **in order, one at a time**. After each chunk Gemini stops with a Completion Report; you check it and reply **"Proceed to Chunk N"**. Parts marked **[FOR NSISONG]** are yours.

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

1. **Read the entire file before doing anything.** Part C is the reference every chunk points back to ("C4", "ADR-267").
2. **Your first action is Chunk 1** (inspection, no behavior change).
3. **One chunk at a time, in order**, only after Nsisong replies "Proceed to Chunk N". Never combine, reorder, skip or work ahead.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; files created and changed; every command run with its **real** output; each acceptance criterion marked pass or fail; any deviation or open question. Claim nothing you did not verify.
5. **If anything blocks you — the repository contradicting this file, two parts disagreeing, an acceptance item failing, or a decision this file does not make — stop and report.** Do not choose for yourself and do not weaken a test.
6. **This amendment moves real money.** Where you are unsure whether a provider call succeeded, the answer is **"uncertain — look it up by our own reference"**, never "failed, so try again" and never "succeeded" (C1.3, ADR-268).
7. **No network in the automated suite.** Paystack is exercised in tests only through a fake transport (C4, Chunk 3) and a fake Paystack server (Chunk 14). Real Paystack (its **test mode**, same API, test keys, no real money) is touched only by the **opt-in, test-key-only** sandbox script (Chunk 15) — and only when Nsisong runs it.
8. **Never print, log, serialize, commit or put in a test fixture a real key, token, account number or one-time code.** Fixtures use obviously fake values.
9. The Standing Instructions in `AI_instructions/` apply throughout. After any chunk that touches an existing module, re-run that module's **full** suite; it must pass unchanged apart from the documented additions and the **behavior-change list** (C16).

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

**Your instinct is right, with six exceptions.** Module 10 split a payment provider into five small capabilities (initiate, verify, webhook, refund, payout) and wrote every use case against those ports; the mock implements all five. So a `PaystackPaymentProviderAdapter` plugs in behind a setting, and the mock stays for `local`/`test`. But reading Module 10 against Paystack's real API shows **six places where the ports or use cases are not yet enough** — they are fixed here, in the smallest provider-neutral way (Finding 1).

**What gets built**

- **The adapter** (Chunks 2–6): settings and safety rules, an HTTP client that classifies every outcome as *not sent / rejected / uncertain*, payment initiation and verification, webhooks (signature, parsing, deduplication), and a **conformance suite** that holds the mock and Paystack to the same contract.
- **Refunds** (Chunk 7): Paystack refunds go back through the original payment; the "needs attention" state is modelled honestly.
- **Banks and payout accounts** (Chunks 8–10): a bank list, account-name resolution, and a **scout payout account** (a Paystack transfer recipient, with only the last four digits of the account number kept). A release now pays **the account recorded on the release decision**, and a database rule insists a release decision has one.
- **The student's refund account** (Chunk 11): collected **on demand**, only when Paystack says a refund needs it, used once and **never stored**.
- **Visibility and custody** (Chunks 12–13): scout and student notices, admin tasks, and a **custody check** — is Paystack's balance at least what you currently owe in held funds?

**What I could and could not verify.** I checked Paystack's current documentation for transfers, refunds, webhooks and manual payouts (Finding 2). I **cannot** call Paystack from here, so everything in this file about its behavior must be proven by the sandbox script and your own small test transactions before real money moves. I also did not have Module 10's *code* — only its specification — so Chunk 1 inspects the real code (in particular where a payout's recipient currently comes from, which the specification never says).

**Explicitly NOT in this amendment** (each is a clean later addition): **automatic clawbacks or re-payment of a reversed payout** (a human decides — ADR-278); **paying Paystack's fees on the user's behalf in the ledger** — the platform absorbs them for now (ADR-280); bulk transfers; subaccounts or split payments; multi-currency; Paystack source-IP allow-listing (ADR-272); Safety or platform items in the tasks list; email or SMS delivery of notices; an admin "hold" on releases; and the **legal and licensing question of holding third-party money**, which no code can answer (Decision 1).

It has **16 chunks.**

---

## PART A — FINDINGS AND CORRECTIONS [FOR NSISONG]

### FINDING 1 — six places where Module 10 is not yet enough for a real provider

1. **Paystack needs the payer's email to start a payment.** Module 10's `InitiatePaymentCommand` carries `payment_attempt_id`, `amount`, `idempotency_key` and `return_context` — no email — and `InitiatePayment` never learns the student's email. **Fix (ADR-266):** a small Payment-side port to Identity, and one more field on the command.
2. **Nothing produces a payout's recipient.** `PayoutCapability.initiate_payout(recipient_reference, …)` takes one, but `ExecuteRelease` (Module 10 Chunk 9) never says where it comes from; the mock accepts anything. Paystack needs a **transfer recipient** per scout. **Fix:** scout payout accounts (C8) and a release that pays the account recorded on its decision (C9).
3. **Webhook processing handles card payments only.** `ProcessWebhookEvent` correlates every event to a `PaymentAttempt`. Paystack also sends refund and transfer events; today they would be `UNCORRELATED` and ignored. **Fix (ADR-267):** an operation branch that uses the webhook only as a *trigger* and re-fetches the authoritative status.
4. **The event and result DTOs cannot express what Paystack says.** `NormalizedProviderEvent` carries a payment status; `ProviderRefundResult` cannot say "needs the customer's bank details". **Fix:** provider-neutral additions (C3).
5. **Two Paystack states have no home:** a transfer in **`otp`** (waiting for a confirmation code nobody will enter) and a refund in **`needs-attention`**. Both are mapped explicitly (C4, C6).
6. **Pending operations never time out.** Module 10's recovery job re-checks `PROVIDER_PENDING` operations forever. With a real provider a transfer can hang. **Fix (ADR-270):** a stale threshold that moves a long-pending operation to `RECONCILIATION_REQUIRED` and raises an admin task.

Two more gaps are about visibility rather than flow: **no way to see the provider's balance** against what you owe (Module 10's `ReconcilePayments` only re-verifies payments, and explicitly left settlement out of scope), and **Module 10 ADR-110 ("no real provider selected")** is now superseded — Paystack is selected.

### FINDING 2 — what Paystack's documentation says (checked November 2026; prove it in the sandbox)
- **Collections:** initialize a transaction with the customer's email, an amount in **kobo**, and your own **reference**; verify it by reference. The webhook is signed with **HMAC-SHA512 of the raw request body using your secret key** in `x-paystack-signature`, and Paystack **retries** deliveries.
- **Transfers (payouts):** you create a **transfer recipient** (type `nuban`, bank code, account number), then initiate a transfer **from your Paystack balance** with a **reference of 16–50 characters** (lowercase letters, digits, `-`, `_`); the initiate response is `pending` when the OTP requirement is off and **`otp`** when it is on; you can fetch by id/code or **verify by reference**; transfers report a fee. Paystack documents that a repeated reference prevents a double credit.
- **Refunds:** `POST /refund` against a transaction reference with an optional partial amount; refunds are normally returned to the account the payment came from. When that account was **not returned by the processing rails**, the refund becomes **`needs-attention`** and you must supply the customer's bank details with **`POST /refund/retry_with_customer_details/{id}`** (body `refund_account_details`: `currency`, `account_number`, `bank_id`, where `bank_id` comes from the List Banks call). That endpoint works **only** for a `needs-attention` refund (otherwise `422`) and the account can be **any valid bank account belonging to the customer**. Refund statuses: `pending`, `processing`, `needs-attention`, `failed`, `processed`. Refunds can be listed by your own reference.
- **Where the money sits:** by default Paystack settles collections to your bank account. **Manual payouts** ("Settled to Balance") keeps collections in your Paystack balance so you can pay scouts with Transfers; it is available to **registered businesses** and, in Nigeria, needs a manual payout account with their banking partner. Transfers fail if the balance is short.

### FINDING 3 — what stays exactly as it is
Module 10's state machines (`PaymentAttempt`, `FundDisposition`, the operations), the decision-before-execution rule, the append-only ledger and its balancing invariant, the nine-condition release policy (as extended by the Release Governance amendment), idempotency by the operation's own id, the mock adapter and its controls (`local`/`test` only), and every existing route.

### CORRECTIONS
**Correction 1 — Module 10 Chunk 3's DTOs are extended** (additive, provider-neutral; C3).
**Correction 2 — Module 10 Chunk 7's `ProcessWebhookEvent` gains an operation branch**; the payment branch is unchanged.
**Correction 3 — Module 10 Chunk 9's `ExecuteRelease` now resolves its recipient** from the scout's payout account, recorded on the decision.
**Correction 4 — Module 10 Chunk 11's recovery gains the stale-pending rule.**
**Correction 5 — Module 10's ADR-110 ("a real provider is deferred") is superseded by ADR-265.**

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-265 … ADR-282)
Continuing the log from the Release Governance amendment (247–264).

| ADR | Decision | Why |
|---|---|---|
| 265 | **Paystack is an adapter behind Module 10's capability ports.** `domain/` and `application/use_cases/` never import it or any HTTP client for a provider call (Module 10 Chunk 3's prohibition stands). A setting `payment_provider` (`mock` / `paystack`) chooses it at the composition root; `mock` stays the default; the mock controls stay `local`/`test` **and only when the provider is `mock`** | Your instruction, and the paradigm |
| 266 | **Contract changes are minimal and provider-neutral:** `InitiatePaymentCommand` gains `payer_email` (from a new Payment-side `PayerContactProvider` port to Identity); `NormalizedProviderEvent` gains a `subject_kind` (`PAYMENT`/`REFUND`/`PAYOUT`) and an optional `operation_status`; `ProviderRefundResult` gains `provider_status_detail`; operation rows gain `provider_operation_id`, and refund operations `provider_status_detail` | Findings 1.1, 1.3, 1.4 |
| 267 | **A webhook is a trigger, never the truth.** For payments (already so, Module 10) **and** for refunds and payouts, the use case re-fetches the authoritative status from the provider and applies it through **one** shared `ApplyOperationOutcome` path that the recovery job also uses | Money state must come from one verified source |
| 268 | **Never blind-retry.** Every provider call's outcome is classified `NOT_SENT` (never left our machine), `REJECTED` (the provider definitively refused it), or `UNCERTAIN` (it may have been processed). `UNCERTAIN` is resolved by **looking up our own reference**, never by calling again; a duplicate-reference reply means "adopt the existing one" | A duplicate payout is a direct financial loss |
| 269 | **References come from our own ids**: payment `cm-<attempt id>`; refunds and transfers use the operation's own UUID string (36 lowercase characters, inside Paystack's 16–50 rule). Every call is therefore idempotent and every outcome findable | Module 10 already passes the operation id as the idempotency key |
| 270 | **Strict response parsing; unknown never means success.** An unrecognised status keeps the operation pending with a WARNING; an operation still pending after `payment_operation_stale_hours` (default 24) becomes `RECONCILIATION_REQUIRED` and an admin task | Finding 1.6 |
| 271 | **Key safety:** a **live** key is refused outside `production`; the secret key is a `SecretStr`, never logged, serialized or echoed; the base URL must be `https` on an allow-listed host (overridable only in `local`/`test` for the fake server) | One typo must not move real money from a laptop |
| 272 | **No Paystack source-IP allow-list in v1.** The constant-time HMAC signature is the control; an IP allow-list behind proxies is easy to mis-configure and lock yourself out | Deferred, named |
| 273 | **Payout destinations belong to Payment** (`payout_accounts`). Only the provider's **recipient code**, the bank, the **resolved account name** and the **last four digits** are stored; the **full account number is never stored** | Data minimisation |
| 274 | **Account-name confirmation by re-resolution:** the client sends the account name it showed the user (`expected_account_name`); the server re-resolves and requires a match. **No fuzzy matching against profile names** | Simple, honest, no false rejections |
| 275 | **A release pays the account recorded on its decision** (`release_decisions.payout_account_id`, with a database `CHECK` for new `RELEASE` rows). A release is blocked while the scout has **no active account** or changed it within `payout_account_change_cooloff_hours` (default 24) | A hijacked account must not be able to receive an already-decided release; cool-off gives time to notice |
| 276 | **The student's refund account is on demand and never stored:** collected only for a refund Paystack marked `needs-attention`, used once with the retry endpoint, only an audit row (bank code, last four, outcome) kept | We never become a bank-details database |
| 277 | **Account resolution is restricted and rate-limited:** only a holder of `PAYOUT_ACCOUNT_MANAGE` or a student with a refund awaiting an account may resolve; `bank_resolve_max_per_hour` (default 10) per person | Otherwise it is a "who owns this account number" oracle |
| 278 | **Transfers in `otp` and payouts that are `reversed` map to `RECONCILIATION_REQUIRED` and are never auto-resolved**; no automatic clawback or re-payment | A human decides when money comes back |
| 279 | **Custody coverage is a read-only metric:** Paystack balance versus the total still held, shown to staff and raising an admin task when short. It takes no automatic action | The question that decides whether escrow is real |
| 280 | **The platform absorbs Paystack's fees in this amendment; the ledger is unchanged.** Reported fees are recorded informationally (`provider_fee_kobo`) | A fee policy changes pricing; it needs your decision first (Decision 2) |
| 281 | **Chunks 12–13 require the Release Governance amendment**; Chunks 1–11 stand alone | Dependency made explicit |
| 282 | **One conformance suite holds every provider to the same contract** (mock and Paystack-on-a-fake-transport), and a fake Paystack server drives the end-to-end tests. Real Paystack behavior is proven **only** by the sandbox script and the go-live checklist | Honesty about what a fake can prove |

### Decisions I need you to confirm (I chose a default for each)
1. **Custody and licensing (not a code question).** To hold funds until release you must use Paystack's manual payouts, which needs a registered business and, in Nigeria, a manual payout account with their banking partner. That makes **Camp Match itself hold third-party money**. Module 10 flagged this and never resolved it. **Get qualified legal and financial advice and Paystack's written confirmation before live money.** Chunks 1–11 can be built and tested in the sandbox without it; **going live cannot wait for it.**
2. **Who bears Paystack's fees?** Default: **the platform absorbs them** and the scout is paid the full booking amount. If you want to charge the student or deduct from the scout, that is a pricing and ledger change I will specify separately.
3. **Transfer OTP must be off for automatic payouts.** With OTP on, every transfer waits for a code sent to the business phone. Turning it off means **anyone holding the secret key can move money**, so the key's protection (and any key-level restrictions Paystack offers) becomes critical. This amendment treats an `otp` transfer as "needs a human" and tells admins.
4. **Cool-off after a payout-account change: 24 hours.** Shorter is friendlier, longer is safer. It is a setting.
5. **Naira only.** One currency (`NGN`) end to end.
6. **A needs-attention refund goes to whatever valid account the student supplies** (Paystack allows it to differ from the paying account). The student confirms the resolved account name first.

---

## PART C — DESIGN SPECIFICATION [FOR YOU — GEMINI CLI]

### C1. Rules every chunk obeys

1. **Provider specifics stay inside `adapters/provider/paystack/`** (ADR-265). `domain/` and `application/use_cases/` import no provider library, no HTTP client for a provider call, and nothing named after Paystack.
2. **A webhook is a trigger, never the truth** (ADR-267). Money state changes only from an authoritative lookup applied through the single `ApplyOperationOutcome` path.
3. **Never blind-retry** (ADR-268). Every provider call is classified `NOT_SENT`, `REJECTED` or `UNCERTAIN` (C4). `UNCERTAIN` is resolved only by **looking up our own reference**.
4. **Strict parsing** (ADR-270). A response that does not match the expected shape, or carries a status not in the mapping table, is **never** success.
5. **Money is integer kobo, currency is `NGN`.** Amounts from the provider are compared to ours as integers; any mismatch is an integrity failure (Module 10 Chunk 7 step 5), never rounded or "close enough".
6. **Secrets and personal data (ADR-271, 273, 276):** the secret key is a `SecretStr` and appears in no log, repr, error, response, fixture or test output. A **full bank account number is never stored and never logged** — it exists only in a request, in memory, and in the one outbound call that needs it. Logs carry our references, provider status words and last-four digits only.
7. **Module 10's disciplines are unchanged:** decision before execution, the operation's own id as the idempotency key, a ledger entry only on **confirmed** success and in the same transaction as its state change, conditional `UPDATE … WHERE` checked by row count.
8. **System use cases take no actor and are never on HTTP**; a guard test proves it (Module 15, ADR-191): `ApplyOperationOutcome`, `ReprocessOperation`, `PromptMissingPayoutAccounts`, `GetProviderCoverage`.
9. **Events are added with `uow.add_event` in the same transaction as the change, only on real transitions; ids and enums only** (Module 15).
10. **Notification templates are fixed strings** with no names, amounts, numbers or URLs (Module 12).
11. **Both providers obey one contract** (ADR-282): anything a use case relies on must be proven by the conformance suite against the mock **and** Paystack-on-a-fake-transport.
12. **No network in the automated suite.**
13. **New routes follow Module 18's recipe** (typed enums, `description` and a proven example on every field).

### C2. Layout (paths confirmed or adjusted by Chunk 1; behavior fixed here)

```
modules/payment/
├── domain/        payout_account.py (new)   value_objects.py (+ProviderStatusDetail, SubjectKind, FailureReason,
│                  AccountEventPurpose/Action/Outcome)   release_policy.py (+payout conditions)
├── application/
│   ├── ports/     provider.py (+4 capabilities, DTO additions, ProviderUncertainOutcome)
│   │              outbound.py (+PayerContactProvider, PropertyOwnerProvider, PayoutAccountRepository,
│   │                          AccountEventRepository, PayoutPromptRepository)
│   └── use_cases/ apply_operation_outcome.py  reprocess_operation.py  list_banks.py  resolve_bank_account.py
│                  set_payout_account.py  get_my_payout_account.py  provide_refund_account.py
│                  prompt_missing_payout_accounts.py  get_provider_coverage.py
│                  (edits: initiate_payment, process_webhook_event, execute_release, execute_refund,
│                   evaluate_release_eligibility, authorize_release, reprocess_uncertain_attempts)
└── adapters/
    ├── provider/paystack/  adapter.py  client.py  errors.py  mapping.py  webhook.py  schemas.py
    ├── provider/mock/      (extended to the four new capabilities; unchanged otherwise)
    ├── identity/payer_contact_provider.py   housing/property_owner_provider.py
    ├── persistence/        payout_accounts, account_events, payout_prompts repositories + models
    └── api/                banks_router.py (banks, resolve)  payout_account_router.py  refund_account_router.py
modules/security/   one new permission: PAYOUT_ACCOUNT_MANAGE
modules/notification/ (Chunk 12) 2 actions, 1 target type, 5 types, strict parsers, policies
modules/admin_operations/ (Chunk 13) no new code beyond the Payment task source's new item types
tests/support/fake_paystack.py   tests/fixtures/paystack/*.json   tests/contract/provider/
scripts/paystack_sandbox_check.py   (opt-in, test keys only)
```

### C3. Provider contract changes (additive; Module 10 Chunk 3's DTOs, ADR-266)

- `InitiatePaymentCommand` **+ `payer_email: str`** (required, validated as an email, never logged).
- `PaymentSessionResult.expires_at` becomes **nullable** (Paystack has no checkout expiry; the attempt's own hold expiry governs).
- `VerifiedProviderTransaction`, `ProviderRefundResult`, `ProviderPayoutResult` **+ `fee_kobo: int | None`** (informational, ADR-280).
- `NormalizedProviderEvent` **+ `subject_kind: SubjectKind` (`PAYMENT`/`REFUND`/`PAYOUT`/`UNSUPPORTED`), `operation_status: OperationStatus | None`, `provider_operation_reference: str | None`.**
- `ProviderRefundResult` **+ `provider_operation_id: str | None`, `provider_status_detail: ProviderStatusDetail | None`** (closed set: `needs_customer_account`). `ProviderPayoutResult` **+ `provider_operation_id: str | None`.**
- **Four new optional capabilities** (each independently optional; each adds a bool to `ProviderCapabilities`):

| Capability | Methods | Flag |
|---|---|---|
| `BankDirectoryCapability` | `list_banks() -> list[Bank]`; `resolve_account(bank_code, account_number) -> ResolvedAccount` | `supports_bank_directory` |
| `PayoutRecipientCapability` | `create_recipient(account_name, bank_code, account_number) -> RecipientResult` (`recipient_reference` opaque) | `supports_payout_recipients` |
| `RefundRecoveryCapability` | `retry_refund_with_account(provider_operation_id, bank_code, account_number) -> ProviderRefundResult` | `supports_refund_recovery` |
| `ProviderBalanceCapability` | `get_available_balance() -> Money` | `supports_balance` |

`Bank(code, name)` and `ResolvedAccount(account_name)` are plain dataclasses; a provider's internal bank id never leaves the adapter.
- **`ProviderUncertainOutcome`** (exception) — raised by any money-moving capability call whose outcome is `UNCERTAIN`; it carries our reference. **Definitive outcomes are returned as results**, never raised: a definitive failure is a result with `normalized_status=FAILED` and a `failure_reason` from the closed set `FailureReason`: `provider_unreachable`, `provider_rejected`, `provider_insufficient_balance`, `provider_auth_failed`, `provider_rate_limited`, `invalid_recipient`.
- **Use cases:** `ExecuteRelease` / `ExecuteRefund` catch `ProviderUncertainOutcome` and leave the operation `PROVIDER_PENDING` with the reference we generated, so recovery looks it up (never re-issues the call).
- The **mock adapter** implements all four new capabilities deterministically (a small fixed bank list; `resolve_account` returns a fixed name; `create_recipient` returns `mock-rcp-<uuid>`; `get_available_balance` is controllable from the mock controls; `retry_refund_with_account` succeeds) so every flow can be built and tested without Paystack.

### C4. The Paystack adapter (`adapters/provider/paystack/`)

**Client rules.** One `httpx.AsyncClient` per adapter instance; `Authorization: Bearer <secret>`; JSON; a fixed `User-Agent`; **TLS verification on; redirects not followed**; separate connect and read timeouts from settings; **exactly one attempt per call** — there is no automatic retry inside the client. (Read-only lookups by reference may be repeated up to two more times with a short fixed backoff; that is the only retry anywhere.) Responses are parsed with **strict Pydantic models** (`schemas.py`); extra unknown fields are ignored, missing or mistyped required fields are `UNCERTAIN`.

**Endpoint map** (the request parameters for the bank, resolve and balance calls were not re-checked against Paystack's documentation by the author of this specification; **the sandbox script (Chunk 15) must confirm them before Chunks 8 and 13 are accepted**):

| Capability | Paystack call | Notes |
|---|---|---|
| Initiate | `POST /transaction/initialize` | `email` = `payer_email`; `amount` = kobo integer; `currency` `NGN`; `reference` = **`cm-<payment_attempt_id>`**; `callback_url` from settings; `metadata` = `{"payment_attempt_id": "<uuid>"}` (an id only, no personal data). `provider_reference` = the returned reference; `checkout_reference` = the returned `authorization_url` |
| Verify | `GET /transaction/verify/{reference}` | amount, currency, status, fees → `VerifiedProviderTransaction` |
| Refund | `POST /refund` | `transaction` = the payment's provider reference; `amount` = kobo; `currency`; **`reference` = the refund operation's UUID string**; short fixed notes with no personal data |
| Refund status | `GET /refund?reference=<our reference>` (or by id when `provider_operation_id` is known) | no match → "not found", never "failed" |
| Refund recovery | `POST /refund/retry_with_customer_details/{id}` | `refund_account_details`: `currency` `NGN`, `account_number`, `bank_id` (the adapter maps our `bank_code` to Paystack's id from the cached bank list); valid only for a `needs-attention` refund (otherwise `422`) |
| Recipient | `POST /transferrecipient` | `type` `nuban`, `name` = the **resolved** account name, `account_number`, `bank_code`, `currency` `NGN` → `recipient_reference` = the returned recipient code |
| Payout | `POST /transfer` | `source` `balance`; `amount` kobo; `recipient`; **`reference` = the payout operation's UUID string** (36 lowercase characters — inside Paystack's 16–50 rule); a short fixed `reason` |
| Payout status | `GET /transfer/verify/{reference}` | by our reference |
| Banks | `GET /bank` (Nigeria, NGN, all pages) | result cached by the application (C7) |
| Resolve | `GET /bank/resolve` | `account_number`, `bank_code` → `account_name` |
| Balance | `GET /balance` | the `NGN` entry, kobo |

The adapter **asserts** reference formats before sending (lowercase letters, digits, `-`, `_`; length 16–50 for transfers); a violation is a definitive local failure, **nothing is sent**.

**Outcome classification (ADR-268) — every call, no exceptions:**

| What happened | Class | Result |
|---|---|---|
| Connection refused, DNS failure, TLS failure, connect timeout — **before the request was written** | `NOT_SENT` | definitive failure `provider_unreachable` |
| `2xx` with `status: true` and a body that parses | success | map the status (below) |
| `2xx` with `status: false` or an unparsable body | `UNCERTAIN` | `ProviderUncertainOutcome` |
| `400` / `422` | `REJECTED` | `provider_rejected` (label `provider_insufficient_balance` when the message matches a small tested list — a wrong label never changes safety) |
| `401` / `403` | `REJECTED` | `provider_auth_failed` and an ERROR log (a configuration fault) |
| `404` | `REJECTED` | `provider_rejected`; for a lookup it means "not found" |
| **`409`** (duplicate reference) | `UNCERTAIN` | resolved by looking up our reference and **adopting** what exists |
| `429` | `NOT_SENT` (the provider did not process it) | `provider_rate_limited` |
| `5xx`, read timeout, connection reset or protocol error **after** the request was written | `UNCERTAIN` | `ProviderUncertainOutcome` |

**Status mapping — only these; anything else is "unknown".**

| Subject | Provider status | Internal result |
|---|---|---|
| Payment | `success` | `SUCCEEDED` — **only** if amount and currency equal ours (else Module 10's mismatch path) |
| Payment | `failed`, `reversed` | `FAILED` |
| Payment | `abandoned`, `ongoing`, `pending`, `processing`, `queued` | `PENDING` |
| Transfer | `success` | `SUCCEEDED` |
| Transfer | `pending` | `PROVIDER_PENDING` |
| Transfer | **`otp`** | **`RECONCILIATION_REQUIRED`**, `failure_reason` `provider_otp_required` |
| Transfer | `failed` | `FAILED`, `provider_rejected` |
| Transfer | **`reversed`** | **`RECONCILIATION_REQUIRED`**, `failure_reason` `payout_reversed` |
| Refund | `pending`, `processing` | `PROVIDER_PENDING` |
| Refund | **`needs-attention`** | `PROVIDER_PENDING` with `provider_status_detail = needs_customer_account` |
| Refund | `processed` | `SUCCEEDED` |
| Refund | `failed` | `FAILED`, `provider_rejected` |
| Any | an unrecognised string | stays pending, **WARNING** (provider status word logged); never success. After `payment_operation_stale_hours` → `RECONCILIATION_REQUIRED` (C6) |

**Logging:** method, path template, HTTP status, duration, outcome class, and our reference. **Never** a body, a header, an email, an account number, a key.

### C5. Webhooks (`webhook.py`, and Module 10's `ProcessWebhookEvent`)

- **`verify_signature(raw_body, headers)`** — read `x-paystack-signature` case-insensitively; compute **HMAC-SHA512 of the raw bytes with the secret key** (hex); compare with `hmac.compare_digest`; a missing header, an empty header or a missing secret is **`False`**. The route must hand the adapter the **raw request bytes** (Chunk 1 confirms; if it parses JSON first, fix that **before** anything else).
- **`parse_event(raw_body)`** — supported: `charge.success` (`subject_kind=PAYMENT`, reference from the data's `reference`, amount/currency from the data); `refund.pending`, `refund.processing`, `refund.processed`, `refund.failed`, `refund.needs-attention` (`REFUND`); `transfer.success`, `transfer.failed`, `transfer.reversed` (`PAYOUT`, reference from the data's `reference`). **Correlation fields for refund events must be confirmed against sandbox-captured payloads** (Chunk 5); if the payload does not carry our refund reference, correlate by the **transaction reference** to the payment's open refund operations — safe, because the event is only a trigger. Anything else → `subject_kind=UNSUPPORTED`.
- **`provider_event_id`** (the dedupe key) = `"<event name>:<data.id>"`; an event with no `data.id` is `FAILED_VALIDATION`.
- **`provider_webhook_events`** gains `correlated_operation_id` (nullable UUID, no FK) and the `processing_status` `CHECK` gains **`IGNORED_UNSUPPORTED`** (migration; `downgrade` restores).
- **Operation branch of `ProcessWebhookEvent`** (after signature → parse → dedupe, unchanged): `PAYMENT` → Module 10's existing branch, untouched. `REFUND` / `PAYOUT` → find the matching operation(s) (payout by `provider_operation_reference`; refund as above); none → `UNCORRELATED` (WARNING); found → call **`ReprocessOperation(operation_id)`**, which performs the authoritative status lookup and applies it with `ApplyOperationOutcome`; record `PROCESSED` with `correlated_operation_id`. If the lookup is inconclusive (provider unreachable), the event is still acknowledged — the recovery job finishes the job. `UNSUPPORTED` → `IGNORED_UNSUPPORTED`, acknowledged.
- The route stays **signature-authenticated, exempt from Module 18's probes, and acknowledges exactly as Module 10 specifies.**

### C6. Applying outcomes and recovery (`ApplyOperationOutcome`, `ReprocessOperation`)

**`ApplyOperationOutcome(operation, provider_result)`** (system) is the **only** place that moves a release or refund operation after the provider has been called. It performs, in one transaction: the conditional status update (`WHERE status IN (…)`), the `FundDisposition` update on confirmed success, the ledger entry on confirmed success (Module 10 Chunk 10), the `provider_operation_id`, `provider_status_detail`, `failure_reason` and `provider_fee_kobo` columns, and the events of C11. A transition that changes nothing publishes nothing.

**`ReprocessOperation(operation_id)`** (system): looks the operation up **by our reference** through `get_refund_status` / `get_payout_status`; "not found" after the provider was reachable and the call was originally uncertain, **and** older than a short grace (`payment_operation_lookup_grace_minutes`, default 10) → the call never happened → `FAILED` (`provider_unreachable`); otherwise applies the result. **It never issues a new payout or refund.**

**Module 10 Chunk 11's `ReprocessUncertainAttempts`** now delegates every `PROVIDER_PENDING` operation to `ReprocessOperation`, and gains the **stale rule**: an operation still `PROVIDER_PENDING` after `payment_operation_stale_hours` becomes `RECONCILIATION_REQUIRED` (`failure_reason` unchanged), so a human sees it (admin task, Chunk 13).

**`needs-attention` refunds:** the operation stays `PROVIDER_PENDING` with `provider_status_detail = needs_customer_account`; the stale rule applies; the student flow (C10) can finish it.

### C7. Bank directory and account resolution

- **`GET /api/v1/payments/banks`** — any signed-in user. `ListBanks` returns `[{code, name}]` sorted by name from an **in-process cache** (`bank_directory_cache_ttl_seconds`, default 86400); on a provider failure it serves a stale copy for up to 7 days, otherwise `503 provider_unavailable`. Under the mock it returns the mock's fixed list.
- **`POST /api/v1/payments/bank-accounts/resolve`** — body `{bank_code, account_number}` → `{account_name}`. **Authorized only** if the caller holds `PAYOUT_ACCOUNT_MANAGE` **or** has a refund awaiting an account (ADR-277). `account_number` must be exactly ten digits; `bank_code` must be in the directory. Rate limit: `bank_resolve_max_per_hour` per person, counted from `payment_account_events`. A provider "no such account" is a single generic `422 account_not_found` (no hints); a provider outage is `503`. The number is never logged or stored.
- **`payment_account_events`** (append-only, never purged): `id`, `identity_id`, `purpose` (`PAYOUT`/`REFUND`), `action` (`RESOLVE`/`SET`/`REPLACE`/`SUBMIT_REFUND`), `outcome` (`SUCCESS`/`REJECTED`/`PROVIDER_ERROR`/`NAME_MISMATCH`/`RATE_LIMITED`), `bank_code`, `account_last4`, `created_at`. No account name, no number.

### C8. Scout payout accounts (ADR-273 … 275, 277)

**`payout_accounts`** (owned by Payment): `id`, `owner_identity_id`, `provider_name`, `provider_recipient_code` (**internal; never in any response**), `bank_code`, `bank_name`, `account_name` (the **resolved** name), `account_last4`, `status` (`ACTIVE`/`REPLACED`), `release_hold_until` (nullable), `created_at`, `replaced_at`, `version`; **partial unique index** on `(owner_identity_id, provider_name) WHERE status = 'ACTIVE'`.

**`SetPayoutAccount(actor, bank_code, account_number, expected_account_name)`** — steps: authorize `PAYOUT_ACCOUNT_MANAGE`; rate limit; validate; **if the actor's active account already has the same `bank_code` and `account_last4`, return it unchanged** (no provider call); resolve the account and require the resolved name to equal `expected_account_name` (trimmed, case-insensitive) → else `409 account_name_changed` and an audit row; `create_recipient`; then **one transaction**: lock the current active row, mark it `REPLACED`, insert the new `ACTIVE` row with `release_hold_until = now + payout_account_change_cooloff_hours` **only when an account was replaced**, write the audit row, `add_event(PayoutAccountActivated(provider_id, change_kind))`. A recipient created at the provider but never saved (a failure between the two steps) is harmless and is logged.

**`GetMyPayoutAccount(actor)`** → `{has_account, bank_code, bank_name, account_name, account_last4, release_hold_until}` (no recipient code).

**Routes:** `GET /api/v1/payments/payout-account`, `PUT /api/v1/payments/payout-account` (`bank_code`, `account_number`, `expected_account_name`). **Security:** a new permission **`PAYOUT_ACCOUNT_MANAGE`** granted to the scout role (and dual-role); staff do **not** hold it. The scout manages **only their own** account (identity from the token, never the body).

### C9. Releases pay the account on the decision (ADR-275)

**Two new release-policy conditions**, inserted **after the dispute check** and evaluated in **both** modes (they are named `5a` and `5b` so existing numbering is not disturbed; if the Release Governance amendment is built, its eleven-condition list gains them in the same position):

| # | Condition | `blocking_reason` |
|---|---|---|
| 5a | the booking's provider has an **active** payout account | `payout_account_missing` |
| 5b | `release_hold_until` is null or has passed | `payout_account_cooling_off` |

**Destination resolution.** The booking's provider id comes from the transaction review's `provider_id` snapshot if the Release Governance amendment is built, otherwise from the new `PropertyOwnerProvider` (Housing's public port, as Notification already does). 

**`release_decisions`** gains `payout_account_id` (nullable FK to `payout_accounts`) and a **`NOT VALID`** `CHECK` so every **new** release decision carries one while historical rows are untouched:
```sql
ALTER TABLE release_decisions ADD COLUMN payout_account_id uuid NULL REFERENCES payout_accounts(id);
ALTER TABLE release_decisions ADD CONSTRAINT ck_release_has_payout_account
  CHECK (<decision column> <> 'RELEASE' OR payout_account_id IS NOT NULL) NOT VALID;
```
(Use the real name of the column that separates release from refund decisions; Chunk 1 finds it. Use raw SQL for `NOT VALID` if Alembic's helper cannot. **Do not run `VALIDATE CONSTRAINT`.**)

**`AuthorizeRelease`** evaluates 5a/5b and records the account's id on the decision. **`ExecuteRelease`** (Module 10 Chunk 9, with its first-step idempotency check unchanged) now: (0) loads the account **named on the decision** (not "the scout's current account" — a replacement after the decision does not redirect it) and refuses with `ReleaseNotEligible(payout_account_missing)` if it cannot; (1–2) as before; (3) calls `initiate_payout(recipient_reference = that account's recipient code, …)` with the operation's UUID as the idempotency key; an `UNCERTAIN` outcome leaves `PROVIDER_PENDING`; **a definitive provider success and the ledger entry follow Module 10 exactly**; `otp` and `reversed` map per C4.

### C10. The student's refund account (ADR-276)

**`POST /api/v1/payments/{payment_id}/refund-account`** — body `{bank_code, account_number, expected_account_name}`; the caller must be the payment's student (**a non-owner gets the same `404` as "no refund is waiting"**). `ProvideRefundAccount`: find the payment's refund operation that is `PROVIDER_PENDING` with detail `needs_customer_account` (none → `404 no_refund_awaiting_account`); rate limit; resolve and require the name to equal `expected_account_name`; call `RefundRecoveryCapability.retry_refund_with_account(provider_operation_id, bank_code, account_number)`; apply the result through `ApplyOperationOutcome`; write the audit row (`SUBMIT_REFUND`, bank code, last four, outcome); `add_event(PaymentRefundAccountSubmitted)`. **The number is used once and never stored.** An `UNCERTAIN` result leaves the operation as it is; the student sees "processing" and recovery looks it up.

### C11. Events and notifications (Chunk 12 — requires the Release Governance amendment)

**New Payment events** (ids and enums only; registered in the `EventContractRegistry`):

| Event | Fields | Published when |
|---|---|---|
| `PaymentPayoutAccountRequired` | `provider_id`, `booking_id` | the prompt job finds a due release whose provider has no active account (at most once per provider per `payout_account_prompt_interval_hours`) |
| `PayoutAccountActivated` | `provider_id`, `change_kind` (`FIRST`/`REPLACED`) | `SetPayoutAccount` commits |
| `PaymentRefundNeedsAccount` | `payment_id`, `booking_id`, `student_id` | a refund operation first enters `needs_customer_account` |
| `PaymentRefundAccountSubmitted` | `payment_id`, `booking_id`, `student_id` | `ProvideRefundAccount` commits |
| *(amendment's)* `PaymentFundsReleased` | **+ `provider_id`** (additive) | unchanged trigger |

**`PromptMissingPayoutAccounts`** (system; job `payment_payout_account_prompts`, hourly, enabled — it moves no money): reviews at `RELEASE_DUE` whose provider has no active account, one bulk lookup, rate-limited per provider through `payout_account_prompts` (`provider_id`, `last_prompted_at`).

**Notification additions** (Module 12/15 rules): actions **`ADD_PAYOUT_ACCOUNT`** and **`PROVIDE_REFUND_ACCOUNT`** (migration alters the `action` `CHECK`; `downgrade` restores); target type **`PAYOUT_ACCOUNT`** (id = the provider's identity id; the `CHECK` is altered likewise); five types, all category `PAYMENT`:

| Type | Recipient | Action / target | Title | Body |
|---|---|---|---|---|
| `payment.payout_account_required.provider` | the scout | `ADD_PAYOUT_ACCOUNT` · `PAYOUT_ACCOUNT:provider_id` | Add your payout account | A student confirmed their handover and a payment is waiting for you. Add a bank account so we can pay you. |
| `payment.payout_account_changed.provider` | the scout | — · `PAYOUT_ACCOUNT:provider_id` | Payout account changed | Your payout account was changed. If this was not you, contact support now. |
| `payment.payout_sent.provider` | the scout (`provider_id`) | — · `BOOKING:booking_id` | Payout sent | A payout for a confirmed booking has been sent to your bank account. |
| `payment.refund_needs_account.student` | the student | `PROVIDE_REFUND_ACCOUNT` · `BOOKING:booking_id` | Action needed: add a bank account for your refund | We could not return your refund to your original payment method. Add a bank account to receive it. |
| `payment.refund_processed.student` | the student | — · `BOOKING:booking_id` | Refund processed | Your refund has been processed. It can take a few working days to reach you. |

**Resolution:** `ADD_PAYOUT_ACCOUNT` resolves on `PayoutAccountActivated` (target `PAYOUT_ACCOUNT:provider_id`); `PROVIDE_REFUND_ACCOUNT` resolves on `PaymentRefundAccountSubmitted`, `PaymentFundsRefunded`, and the booking-closing events already resolving actions on `BOOKING:booking_id`. `payment.payout_account_changed.provider` is created **only** when `change_kind = REPLACED`. `payment.payout_sent.provider` on `PaymentFundsReleased`; `payment.refund_processed.student` on `PaymentFundsRefunded`. Parsers are strict; the **scout and student never receive a staff notice and vice versa.**

### C12. Admin visibility and custody (Chunk 13 — requires the Release Governance amendment)

- **Transaction review detail** gains: `release.payout_destination` = `{status (ACTIVE|MISSING|COOLING_OFF), bank_name, account_last4, account_name, release_hold_until}` (staff with `PAYMENT_REVIEW` only; never the recipient code); `operations.refunds[].provider_status_detail` and `.provider_fee_kobo`; `operations.releases[].failure_reason`. The blocking-reason list gains `payout_account_missing` and `payout_account_cooling_off`.
- **Tasks (`PAYMENT` source) gain three types:** `PAYOUT_ACCOUNT_MISSING` (a `RELEASE_DUE` transaction whose provider has no active account; `required_permission` `PAYMENT_REVIEW`; `facts` carry ids only), `REFUND_NEEDS_ACCOUNT` (a refund waiting for the student's account; `NORMAL`), `PROVIDER_BALANCE_LOW` (coverage short; `HIGH`; subject type `PLATFORM`). Existing `RECONCILE_OPERATION` already covers stale, `otp` and `reversed` operations; its `facts` now include `failure_reason`.
- **Custody coverage — `GetProviderCoverage()`** (system, read-only): `held_total_kobo` = the sum of `remaining_releasable` over dispositions still held; `provider_balance_kobo` from `ProviderBalanceCapability` (short timeout, best effort, cached 60 seconds); `coverage_ok = provider_balance_kobo >= held_total_kobo` — **deliberately conservative** (it does not subtract payouts still pending), so a brief false alarm is possible and a false all-clear is not. Under the mock, or if the lookup fails, `provider_balance_kobo` and `coverage_ok` are `null`. `GET /payments/review/summary` gains `provider_coverage {provider_balance_kobo, held_total_kobo, coverage_ok, checked_at}`. It is a **necessary** condition for escrow being real, not a sufficient one, because the balance may also contain money that is not escrow.

### C13. Settings (`config/settings.py`, `.env.example`; invalid values fail startup)

| Setting | Default | Rule |
|---|---|---|
| `payment_provider` | `mock` | `mock` or `paystack` (reuse the existing setting if Chunk 1 finds one) |
| `paystack_secret_key` | none | `SecretStr`; **required** when the provider is `paystack`; prefix `sk_test_` or `sk_live_` |
| `paystack_base_url` | `https://api.paystack.co` | `https` only; host must be `api.paystack.co` unless `app_env` is `local`/`test` |
| `paystack_callback_url` | none | required when `paystack`; `https` unless `local`/`test` |
| `paystack_connect_timeout_seconds` / `paystack_read_timeout_seconds` | `5` / `15` | > 0 |
| `payout_account_change_cooloff_hours` | `24` | integer ≥ 0 |
| `bank_resolve_max_per_hour` | `10` | integer ≥ 1 |
| `bank_directory_cache_ttl_seconds` | `86400` | integer ≥ 60 |
| `payment_operation_stale_hours` | `24` | integer ≥ 1 |
| `payment_operation_lookup_grace_minutes` | `10` | integer ≥ 1 |
| `payout_account_prompt_interval_hours` | `24` | integer ≥ 1 |
| `platform_job_payment_payout_account_prompts_interval_seconds` | `3600` | |

**Startup refusal matrix (ADR-271):** `paystack` without a key, a callback URL or with a non-https/non-allow-listed base URL → refuse to start; a **live** key when `app_env != production` → refuse; a **test** key in `production` → start with a loud WARNING ("this deployment cannot take real money"); the mock-control routes are mounted **only** when `app_env` is `local`/`test` **and** `payment_provider = mock`; the `paystack` provider in `local`/`test` is allowed with a test key. Also **register** `payment_payout_account_prompts` in the job registry (Chunk 12).

### C14. Errors and blocking reasons

New blocking reasons (`ReleaseNotEligible`, existing code/status): `payout_account_missing`, `payout_account_cooling_off`. New HTTP errors (use the project's standard envelope): `422 account_not_found`, `409 account_name_changed`, `429 resolve_rate_limited`, `404 no_refund_awaiting_account`, `503 provider_unavailable`; `403` for a missing `PAYOUT_ACCOUNT_MANAGE`; ordinary `422 validation_error` for malformed input. Failure reasons stored on operations come only from the closed set in C3 plus `provider_otp_required` and `payout_reversed`; **no raw provider message is ever stored or returned.**

### C15. Touch map — the only changes outside the new files

| Module / file | Change | Chunk |
|---|---|---|
| Payment | ports and DTOs (C3); `InitiatePayment` (payer email); `ProcessWebhookEvent` (operation branch); `ExecuteRelease`/`ExecuteRefund`/`AuthorizeRelease`/policy (C9); recovery (C6); new use cases, tables, routes | 2–11 |
| Payment mock adapter | the four new capabilities | 6 |
| Identity | **no change** — Payment reads the payer's email through the new `PayerContactProvider` using Identity's existing public port | 4 |
| Security | one new permission, `PAYOUT_ACCOUNT_MANAGE` (scout role); nothing else | 9 |
| Notification | actions, target type, five types, parsers, policies | 12 |
| Admin & Operations | none beyond Payment's task source and summary additions | 13 |
| Platform Reliability | one job registered; stale rule is in Payment's recovery use case | 12 |
| `config/settings.py`, `.env.example`, `app.py`, `pyproject.toml` (import-linter, `httpx` if absent) | per C13 and the new routes | as needed |

**Must not change:** the ledger and its invariant; the state machines; the mock controls' routes and the rule that they are `local`/`test` only; any other module; any existing success response; the webhook route's acknowledgement behavior.

### C16. Behavior-change list (known now; Chunk 1 completes it)

| Where | Before | After |
|---|---|---|
| Release | any recipient, none defined | **blocked** until the scout has an active payout account; blocked for `payout_account_change_cooloff_hours` after a change |
| Release decision | no destination | records `payout_account_id`; database rule for new `RELEASE` rows |
| `InitiatePaymentCommand` | no email | `payer_email` required |
| Webhooks | card payments only | refund and transfer events trigger authoritative lookups |
| Recovery | pending operations wait forever | stale pending → `RECONCILIATION_REQUIRED` after 24 h |
| Refund | outcome only `SUCCEEDED`/`FAILED`/pending | pending can carry `needs_customer_account`; student can supply an account |
| Settings | mock only | `payment_provider`, Paystack and payout settings; startup refusal matrix |
| Security | — | permission `PAYOUT_ACCOUNT_MANAGE` for scouts |

---

## PART D — CHUNK INSTRUCTIONS [FOR YOU — GEMINI CLI]

**Every chunk ends the same way:** run the linter, the type checker, `poetry run lint-imports`, and the **full test suite of every module the chunk touched** (Chunks 1, 14 and 16 run the entire suite). Report the real output. **The automated suite never touches the network.**

---

### CHUNK 1 — INSPECTION & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** learn what is really in the repository. **No behavior change.**

**Part one — inspect and report** (real output, before any file is created):

1. **Provider seam as built.** `application/ports/provider.py`: the exact protocols, DTOs, `ProviderCapabilities`, errors. How the provider is **chosen at the composition root** (is there already a setting? a registry?). The mock adapter and its controls (and the `app.py` mounting rule). Compare with Module 10 Chunks 3 and 5 and Module 15's mock-control rewrite; list differences.
2. **Where a payout's recipient comes from today.** Read `ExecuteRelease` and the mock's `initiate_payout`: what is passed as `recipient_reference`? (The specification never says; report the real answer.)
3. **Outcome handling.** Where do `ExecuteRelease`, `ExecuteRefund` and `ReprocessUncertainAttempts` each update operation status, the `FundDisposition` and the ledger — one place or duplicated? (Chunk 7 extracts the shared `ApplyOperationOutcome`; report how much duplication exists.)
4. **Webhooks.** The webhook route: does it pass **raw bytes** to `verify_signature`, or parse JSON first? `provider_webhook_events` columns and the real `CHECK` constraint name and values; the response the route returns for a valid, a duplicate and an invalid-signature delivery.
5. **Operations.** The real `release_operations` / `refund_operations` columns, statuses and `CHECK`s; the column that separates release from refund decisions in `release_decisions`; `payment_attempts` columns.
6. **Recovery.** `ReprocessUncertainAttempts` and `ReconcilePayments` as built.
7. **Other modules' public ports.** Identity's way to get an account's email; Housing's way to get a property's owner; Security's policy, the role names (scout, dual-role) and where permissions are defined; whether the **Release Governance amendment is built**, and which of its chunks.
8. **Dependencies and tooling.** Whether `httpx` is a dependency (version); the Pydantic and FastAPI versions; how API tests obtain tokens; whether `httpx.MockTransport` and `httpx.ASGITransport` are usable in the existing test setup.
9. **Platform.** The job registry, how `platform_jobs_disabled` is parsed, the event-contract registry, the system-use-case guard test.
10. **Tests that will change:** every existing test asserting anything this amendment changes (C16), including any asserting that a release needs no destination.
11. **Sandbox.** Ask Nsisong whether Paystack **test** keys exist yet (informational; Chunks 1–14 do not need them).
12. Any difference between this file and what you found. Do not "fix" this file.

**Part two — scaffolding.** Create the empty packages in C2 (each with a docstring). Add import-linter contracts: `domain` and `application` of Payment may not import `httpx` or `adapters.provider.paystack`; only `adapters/provider/paystack` may import `httpx`; Payment's `adapters/identity` and `adapters/housing` may import those modules' `application/ports`. They must pass on the empty packages.

**Prohibition:** no behavior, no settings, no migrations.

**Acceptance criteria:** the full existing suite passes unchanged; `lint-imports` passes; the report answers all twelve items with real output.

---

### CHUNK 2 — SETTINGS, SECRETS AND SAFETY RULES
**[FOR YOU — GEMINI CLI]**

**Objective:** make it impossible to start in a dangerous configuration. Read **C13**, ADR-265, 271.

**Build:** every setting in **C13** (reuse an existing `payment_provider` setting if Chunk 1 found one) in `config/settings.py` and `.env.example` (comments only, **no real values**); `paystack_secret_key` as `SecretStr`; the **startup refusal matrix** of C13; the structural rule that the mock-control routes mount **only** when `app_env` is `local`/`test` **and** `payment_provider = mock`. Do **not** wire the Paystack adapter yet.

**Prohibition:** no HTTP client, no adapter, no route.

**Tests you must write:** each refusal and each acceptance of the matrix (`paystack` without key; without callback URL; `http://` base URL; foreign host; live key in `staging`/`local`; test key in `production` → starts with a WARNING; live key in `production` → starts); **the secret never appears** in `repr`, `str`, `model_dump()`, JSON dumps, structured log output, or any HTTP response (assert on captured output with a recognisable fake key); the mock-control routes return `404` when `payment_provider = paystack` even in `local`; the existing `404`-in-staging test still passes; defaults reproduce today's behavior exactly (`mock`).

**Acceptance criteria:** tests pass; the full Payment suite passes unchanged.

---

### CHUNK 3 — THE PAYSTACK HTTP CLIENT
**[FOR YOU — GEMINI CLI]**

**Objective:** one careful way to talk to Paystack. Read **C4 (client rules, classification), C1.3–1.6**, ADR-268, 270, 271.

**Build** `adapters/provider/paystack/client.py`, `errors.py`, `schemas.py` (the response envelope and the first models), exactly per C4's **client rules** and **outcome classification table**: one `httpx.AsyncClient`, bearer auth, JSON, fixed `User-Agent`, TLS verification on, redirects not followed, separate connect/read timeouts, **one attempt per call**, read-only lookups retried at most twice with fixed backoff, strict parsing, the log rule. Provide the three outcome classes and the exception/result types the capabilities will use. Create `tests/support/fake_paystack.py` — a small stateful ASGI app (start with transaction initialize/verify; every later chunk extends it) usable through `httpx.ASGITransport`, with **scenario hooks** (success, definitive reject, `409`, `429`, `5xx`, slow response, connection failure) — and `tests/fixtures/paystack/` with JSON shaped like Paystack's documented responses, **using obviously fake values**.

**Prohibition:** no capability implementations yet; no import from `domain/` or `application/`; the client never retries a `POST`.

**Tests you must write (fake transport, no network):** **every row of the classification table** produces the right class; a connect failure never reaches the wire (assert zero requests recorded); a read timeout after the request was written is `UNCERTAIN`; a `POST` is attempted **exactly once** in every failure mode; a `GET` lookup is retried at most twice; `3xx` is not followed and is not success; an unparsable `2xx` is `UNCERTAIN`; `status: false` on `2xx` is `UNCERTAIN`; **no log line, exception message or repr contains the key, an email, or an account number**; TLS verification is on (assert the client's configuration); the timeouts come from settings.

**Acceptance criteria:** tests pass; the full Payment suite passes unchanged.

---

### CHUNK 4 — INITIATION AND VERIFICATION
**[FOR YOU — GEMINI CLI]**

**Objective:** a student can start a payment and the platform can confirm it. Read **C3, C4**, ADR-266, 269, 270.

**Build:**
1. The additive DTO changes of **C3** for initiation and verification (`payer_email`, nullable `expires_at`, `fee_kobo`).
2. The Payment-side port **`PayerContactProvider`** and its adapter in `adapters/identity/` (Identity's existing public port; returns the payer's email; never logs it); edit `InitiatePayment` to obtain it and set `payer_email` on the command. **Nothing else about `InitiatePayment` changes.**
3. `PaystackPaymentProviderAdapter` with **`PaymentInitiationCapability`** and **`PaymentVerificationCapability`** per C4's endpoint map and **status mapping**; `reference = "cm-<payment_attempt_id>"`; the `callback_url` from settings; `metadata` an id only. Declare `ProviderCapabilities` with **only** initiation and verification true.
4. The mock adapter accepts and ignores `payer_email`.

**Prohibition:** do not wire the adapter into the composition root yet (Chunk 6); do not change Module 10's `VerifyPaymentAttempt` logic.

**Tests you must write:** the initialize request body is **exactly** `{email, amount (integer kobo), currency NGN, reference cm-<id>, callback_url, metadata{payment_attempt_id}}` — no other personal data; the returned `authorization_url` becomes `checkout_reference`; **every payment status row** of the mapping table; `success` with a different amount or currency is **not** reported as success to the use case (it reaches Module 10's mismatch path); an unknown status is `PENDING` with a WARNING and **never** `SUCCEEDED`; `409` on initiate is resolved by verifying the reference (adopt), never by a second initiate; a connect failure leaves the attempt `FAILED` (Module 10's existing rule) with nothing sent; `InitiatePayment` replay does not call the provider twice; the payer's email is never in a log or a response; all existing initiation tests pass unchanged against the mock.

**Acceptance criteria:** tests pass; the full Payment suite passes unchanged apart from tests that construct `InitiatePaymentCommand` (add the field, list each edit).

---

### CHUNK 5 — WEBHOOKS: SIGNATURE, PARSING, DEDUPLICATION
**[FOR YOU — GEMINI CLI]**

**Objective:** accept Paystack's events safely. Read **C5**, ADR-267, 272.

**Build:** the `NormalizedProviderEvent` additions of C3; `webhook.py` (**`verify_signature`** — HMAC-SHA512 over the **raw bytes**, constant-time, `False` on any missing piece; **`parse_event`** for `charge.success`, the five `refund.*` events and the three `transfer.*` events; everything else `UNSUPPORTED`; the dedupe key `"<event>:<data.id>"`); the migration adding `provider_webhook_events.correlated_operation_id` and the `IGNORED_UNSUPPORTED` status (read it; `downgrade` restores); if Chunk 1 found the route parses JSON before verifying, **fix the route to pass the raw bytes first**. Add `supports_webhooks = True` to the adapter's capabilities. The **payment** branch of `ProcessWebhookEvent` stays exactly as it is; for `REFUND`/`PAYOUT` events record `RECEIVED` and acknowledge — the operation branch arrives in Chunk 7.

**Prohibition:** no money state changes from this chunk's code; no change to the route's acknowledgement behavior.

**Tests you must write:** a correctly signed body verifies; **any change to a single byte of the body** fails verification; a wrong key, a missing header, an empty header, an upper-case header name and a missing secret behave as specified (`False` except the case-insensitive header, which verifies); comparison is constant-time (assert `hmac.compare_digest` is used); each supported event parses to the right `subject_kind`, reference and operation status from **fixtures captured from Paystack's documented samples** (mark any field whose real name you could not confirm and **list it for the sandbox script**); an unknown event is `UNSUPPORTED` and recorded `IGNORED_UNSUPPORTED`; the same delivery twice is `IGNORED_DUPLICATE`; an event without `data.id` is `FAILED_VALIDATION`; an invalid signature never reaches parsing (Module 10's test, still passing); the raw-bytes rule (a body whose JSON re-serialization differs from the original bytes still verifies when the signature was computed over the original).

**Acceptance criteria:** tests pass; the full Payment suite passes unchanged.

---

### CHUNK 6 — THE CONFORMANCE SUITE AND THE SWITCH
**[FOR YOU — GEMINI CLI]**

**Objective:** hold both providers to one contract, then make the switch. Read **C3, C1.11**, ADR-265, 282.

**Build:**
1. `tests/contract/provider/` — a **parametrized suite** run against the **mock adapter** and the **Paystack adapter on the fake Paystack server**, asserting only what the use cases rely on: initiate is idempotent for one reference; verify maps statuses per the contract; a duplicate or invalid webhook behaves per the contract; **an unknown provider status is never reported as success**; amounts are integers; a capability's flag is `True` **iff** its methods work and a `False` flag makes the use case raise `UnsupportedProviderCapability`. (Later chunks add their capabilities to the suite.)
2. The composition-root switch: `payment_provider = paystack` constructs the Paystack adapter from settings; `mock` is unchanged and remains the default.
3. Extend the **mock adapter** to the four new capabilities of C3 (deterministic, as specified there) — implemented now, **declared** `False` until their chunks if you prefer, but they must exist.

**Prohibition:** no change to any use case; no refund or payout code yet.

**Tests you must write:** the conformance suite itself (it is the test); startup with each provider; the capability-flag truthfulness test; a regression run of **all of Module 10's existing tests under the mock** (unchanged); one `httpx` import audit — nothing under `domain/` or `application/` imports a provider library.

**Acceptance criteria:** the suite passes for both providers; Module 10's suite passes unchanged; `lint-imports` passes.

---

### CHUNK 7 — REFUNDS, THE SHARED OUTCOME PATH AND RECOVERY
**[FOR YOU — GEMINI CLI]**

**Objective:** real refunds, and one trustworthy place where operation outcomes are applied. Read **C4 (refund rows), C5 (operation branch), C6**, ADR-267, 268, 270.

**Build:**
1. **`ApplyOperationOutcome`** and **`ReprocessOperation`** (C6) — **extracted from the existing code** that `ExecuteRelease`, `ExecuteRefund` and `ReprocessUncertainAttempts` already contain. This is a **behavior-preserving refactor**: all of Module 10's tests for those use cases must pass **unchanged** before you add anything new.
2. The schema additions: `provider_operation_id` on both operation tables; `provider_status_detail` and `provider_fee_kobo` on refund operations (and `provider_fee_kobo` on release operations); the `ProviderStatusDetail` and `FailureReason` closed sets; migration, `downgrade` works.
3. **`RefundCapability`** on the Paystack adapter (`request_refund`, `get_refund_status`) per C4, with `needs-attention` mapped to `PROVIDER_PENDING` + `needs_customer_account`, partial amounts supported; catch `ProviderUncertainOutcome` in `ExecuteRefund` (C3). Set `supports_refunds = True`.
4. **The operation branch of `ProcessWebhookEvent`** (C5): refund events find the payment's open refund operations; payout events find a payout by reference (payout data arrives in Chunk 10); each calls `ReprocessOperation`.
5. **Recovery:** `ReprocessUncertainAttempts` delegates `PROVIDER_PENDING` operations to `ReprocessOperation` and gains the **stale rule** (`payment_operation_stale_hours`); `ReprocessOperation` implements the **lookup grace** (`payment_operation_lookup_grace_minutes`).

**Prohibition:** nothing may call `request_refund` a second time for the same operation (Module 10's first-step idempotency check stays); no new money path outside `ApplyOperationOutcome`.

**Tests you must write:** the **refactor proof** (Module 10's operation tests unchanged and passing); the refund request body (`transaction`, kobo `amount`, `currency`, `reference` = the operation's UUID, fixed notes, no personal data); full and partial refunds; **every refund status row**; `needs-attention` stays pending with the detail; an `UNCERTAIN` response leaves `PROVIDER_PENDING` and the next recovery run **looks up by reference and never refunds again** (assert the fake recorded exactly one refund request); `409` adopts; "not found" before the grace is not failure, after the grace with a reachable provider it is `FAILED`; a webhook for a refund triggers a **lookup** and the lookup result — not the webhook body — is what is applied (send a webhook claiming `processed` while the fake says `pending`: the operation stays pending); a replayed webhook changes nothing; the ledger gets one entry on confirmed success and none otherwise; the stale rule moves a long-pending operation to `RECONCILIATION_REQUIRED`; add refunds to the conformance suite.

**Acceptance criteria:** tests pass; the full Payment suite passes.

---

### CHUNK 8 — BANK DIRECTORY AND ACCOUNT RESOLUTION
**[FOR YOU — GEMINI CLI]**

**Objective:** a trustworthy bank list and a guarded account-name lookup. Read **C7, C13**, ADR-274, 277.

**Build:** `BankDirectoryCapability` on the Paystack adapter (list with paging, resolve) and on the mock; `ListBanks` with the in-process cache and stale-serving rule; `ResolveBankAccount` with its authorization (holder of the new permission **`PAYOUT_ACCOUNT_MANAGE`**, or a student with a refund awaiting an account), the ten-digit and directory checks, the rate limit, and the generic `422 account_not_found`; the **`payment_account_events`** table, repository (append-only) and migration; the two routes of C7; the **Security** change — add `PAYOUT_ACCOUNT_MANAGE` to the scout and dual-role permission sets and nothing else. Set `supports_bank_directory = True`.

**Prohibition:** no payout-account storage yet; the full account number is never stored or logged.

**Tests you must write:** the cache serves within the TTL, refreshes after it, serves stale on provider failure, and returns `503 provider_unavailable` when there is nothing to serve; a scout resolves; a student **without** a waiting refund and a non-scout get `403`; a student **with** a waiting refund resolves; the rate limit (the eleventh attempt in an hour → `429`); the number must be ten digits and the bank must exist; a provider "no such account" yields exactly `account_not_found` with no hint; a provider outage yields `503`; **the account number appears in no log, event row, response or exception**; audit rows hold bank code and last four only; Security's policy snapshot shows **only** the new permission added; the routes under the mock work end to end; Module 18 recipe (enums/examples); add to the conformance suite.

**Acceptance criteria:** tests pass; the full Payment and Security suites pass unchanged apart from the permission addition.

---

### CHUNK 9 — SCOUT PAYOUT ACCOUNTS
**[FOR YOU — GEMINI CLI]**

**Objective:** a scout can register where their money goes. Read **C8**, ADR-273–275.

**Build:** the `PayoutAccount` entity and invariants; the `payout_accounts` table (partial unique index), repository and migration; `PayoutRecipientCapability` on the Paystack adapter (`POST /transferrecipient` with the **resolved** name) and the mock; `SetPayoutAccount` and `GetMyPayoutAccount` exactly per C8, including the **same-account no-op before any provider call**, the `expected_account_name` re-resolution, the cool-off only on replacement, the single transaction (lock, replace, insert, audit, event) and the `PayoutAccountActivated` event (class and registry entry; consumed in Chunk 12); the routes `GET`/`PUT /api/v1/payments/payout-account`. Set `supports_payout_recipients = True`.

**Prohibition:** the recipient code is never in any response or log; no change to the release policy yet (Chunk 10).

**Tests you must write:** first account → `ACTIVE`, no cool-off, `FIRST`; replacement → old `REPLACED`, new `ACTIVE` with `release_hold_until` set, `REPLACED`; the **same bank and last four** returns the current account and the fake records **no** recipient call; a name that no longer matches → `409 account_name_changed` and an audit row; a recipient failure leaves **no** row; a database failure after the recipient call leaves **no partial state** (one `ACTIVE` at most); two simultaneous `PUT`s end with exactly one `ACTIVE`; a non-scout and staff get `403`; a scout cannot touch another's account (identity from the token); responses contain no recipient code and no full number; audit rows are written for success and each failure outcome; the event is added in the same transaction (roll back → no event); add to the conformance suite.

**Acceptance criteria:** tests pass; the full Payment suite passes.

---

### CHUNK 10 — PAYOUTS: THE RELEASE PAYS THE RIGHT ACCOUNT
**[FOR YOU — GEMINI CLI]**

**Objective:** real releases. Read **C4 (payout rows), C9**, ADR-268, 275, 278.

**Build:**
1. **`PayoutCapability`** on the Paystack adapter (`POST /transfer`, `GET /transfer/verify/{reference}`) with the **transfer status mapping** of C4 (`otp` and `reversed` → `RECONCILIATION_REQUIRED`); `reference` = the operation's UUID; the adapter asserts the 16–50 lowercase rule; catch `ProviderUncertainOutcome` in `ExecuteRelease`. Set `supports_payouts = True`.
2. The **`PropertyOwnerProvider`** port and adapter (Housing's public port) — used only when the Release Governance amendment's review row is not available.
3. **Policy conditions 5a/5b** and the `payout_account_id` column and **`NOT VALID` `CHECK`** of C9 (migration; `downgrade` works; do not validate); `AuthorizeRelease` records the account; `ExecuteRelease` loads **the account named on the decision**.
4. Payout events in the webhook operation branch (Chunk 7's code, now with payouts) and payout status in `ReprocessOperation`.

**Prohibition:** never pay "the scout's current account" — only the one on the decision; no automatic clawback; Module 10's decision-before-execution and first-step idempotency are untouched.

**Tests you must write:** **a release without an active account → `ReleaseNotEligible(payout_account_missing)`**, no decision row, the fake provider never called; within the cool-off → `payout_account_cooling_off`; after it → eligible; the decision records `payout_account_id`; **the database rejects a new `RELEASE` decision without it** (insert bypassing the application) while an old-style row inserted before the migration remains untouched (`convalidated = false`); **replace the account after the decision but before execution → the transfer goes to the account named on the decision**; the transfer body is `{source balance, amount kobo, recipient = that account's code, reference = operation UUID, fixed reason}`; **every transfer status row**, including `otp` → `RECONCILIATION_REQUIRED` with `provider_otp_required` and a reversed payout → `RECONCILIATION_REQUIRED` with `payout_reversed` (and nothing is auto-repaid); an `UNCERTAIN` response → `PROVIDER_PENDING`, then lookup by reference finds it and applies it with **exactly one** transfer recorded by the fake; "not found" after the grace → `FAILED`; **double invocation of `ExecuteRelease` → one transfer** (Module 10's test, still passing); insufficient balance → `FAILED` with `provider_insufficient_balance`; a `transfer.success` webhook claiming success while the fake says pending leaves the operation pending; fee recorded informationally; the ledger entry on confirmed success only; all Module 10 and Release Governance release tests pass (they now create a payout account in their fixtures — list each fixture edit); add payouts to the conformance suite.

**Acceptance criteria:** tests pass; the full Payment suite passes apart from listed fixture edits.

---

### CHUNK 11 — THE STUDENT'S REFUND ACCOUNT
**[FOR YOU — GEMINI CLI]**

**Objective:** finish a `needs-attention` refund. Read **C10**, ADR-276.

**Build:** `RefundRecoveryCapability` on the Paystack adapter (`retry_with_customer_details`; the `bank_code`→`bank_id` mapping stays inside the adapter) and the mock; `ProvideRefundAccount` and `POST /api/v1/payments/{payment_id}/refund-account` per C10; the `PaymentRefundAccountSubmitted` event class and registry entry. Set `supports_refund_recovery = True`.

**Prohibition:** the account number is never stored or logged; no new money path outside `ApplyOperationOutcome`.

**Tests you must write:** a student with a waiting refund submits → the fake receives `refund_account_details` with the right bank id and the operation moves per the result; a **non-owner gets the same `404`** as "none waiting"; no waiting refund → `404 no_refund_awaiting_account`; a name mismatch → `409 account_name_changed`; the rate limit applies; a retry for a refund that is **not** `needs-attention` is never sent (guard before the call); an `UNCERTAIN` result leaves the operation unchanged and recovery looks it up; the audit row holds bank code, last four and outcome only; **no number in any log, row or response**; the event is added in the same transaction; add to the conformance suite.

**Acceptance criteria:** tests pass; the full Payment suite passes.

---

### CHUNK 12 — EVENTS, NOTIFICATIONS AND THE PROMPT JOB  *(requires the Release Governance amendment)*
**[FOR YOU — GEMINI CLI]**

**First:** confirm the amendment is built (its events, `transaction_reviews`, `RELEASE_FUNDS` action). **If not, stop and report.**

**Objective:** tell scouts and students what they need to do. Read **C11**, Module 12 C1/C5, Module 15 C10.

**Build:** the events of C11 (`PaymentPayoutAccountRequired`, `PaymentRefundNeedsAccount` — published by `ApplyOperationOutcome` on the **first** transition into `needs_customer_account`; the two from Chunks 9 and 11 already exist) and the additive `provider_id` on `PaymentFundsReleased`; **`PromptMissingPayoutAccounts`** with `payout_account_prompts` (table, repository, migration) and the job `payment_payout_account_prompts` (hourly, **enabled**) registered in the job registry; Notification: the two actions and the `PAYOUT_ACCOUNT` target type (migration alters both `CHECK`s; `downgrade` restores), the five types with the **exact** titles and bodies of C11, strict parsers, subscribers and the resolution rules.

**Prohibition:** Notification's `domain`/`application` import nothing from other modules; no template contains a placeholder, name, amount or URL; staff notices are untouched.

**Tests you must write:** each event → the exact notification (type, category, target, action, recipient) **and nobody else**; the prompt job emits once per provider per interval and **again after the interval**; it does nothing for a scout who has an account; `ADD_PAYOUT_ACCOUNT` **stays open after being read** and resolves on `PayoutAccountActivated`; `payment.payout_account_changed.provider` only for `REPLACED`; `PROVIDE_REFUND_ACCOUNT` resolves on submission, on `PaymentFundsRefunded` and on booking-closing events, in any order; the needs-account event is published **once** (a replayed recovery run publishes nothing); the payout-sent notice reaches the right scout through `provider_id`; malformed events are rejected; the job is enabled by default and appears in `--list`.

**Acceptance criteria:** tests pass; the Notification, Payment and Platform suites pass.

---

### CHUNK 13 — ADMIN VISIBILITY AND CUSTODY COVERAGE  *(requires the Release Governance amendment)*
**[FOR YOU — GEMINI CLI]**

**First:** confirm the amendment is built (transaction review routes and `GET /admin/tasks`). **If not, stop and report.**

**Objective:** admins can see money that is stuck or uncovered. Read **C12**, ADR-278–280.

**Build:** `GetProviderCoverage` (system, read-only) and its place in `GET /payments/review/summary`; `ProviderBalanceCapability` on the Paystack adapter (`GET /balance`, the `NGN` entry) and the mock (controllable); the review-detail additions (`release.payout_destination`, refund `provider_status_detail`/`provider_fee_kobo`, release `failure_reason`) and the two new blocking reasons; the three new task types in Payment's task source (`PAYOUT_ACCOUNT_MISSING`, `REFUND_NEEDS_ACCOUNT`, `PROVIDER_BALANCE_LOW`) with `facts` carrying ids and enums only; `RECONCILE_OPERATION` facts gain `failure_reason`. Set `supports_balance = True`.

**Prohibition:** coverage takes **no** automatic action; no recipient code in any response; Admin stores nothing and gains no new code beyond what its existing Payment task source returns.

**Tests you must write:** coverage is `false` when the fake balance is below the held total, `true` when equal or above, `null` under the mock and when the lookup fails (an outage is never reported as zero or as OK); the formula is exactly the conservative one of C12; the summary and the `PROVIDER_BALANCE_LOW` task agree; `PAYOUT_ACCOUNT_MISSING` appears only for a due release whose provider has no active account; `REFUND_NEEDS_ACCOUNT` appears for a waiting refund and disappears after submission; stale, `otp` and `reversed` operations appear as `RECONCILE_OPERATION` with the right `failure_reason`; `OPERATIONS` sees the tasks with `can_act: false` where only `ADMIN` can act; the detail shows the payout destination to staff only and never a recipient code or full number; add the balance capability to the conformance suite.

**Acceptance criteria:** tests pass; the Payment and Admin suites pass.

---

### CHUNK 14 — END-TO-END, CONCURRENCY AND SECURITY
**[FOR YOU — GEMINI CLI]**

**Objective:** prove it works together and cannot be misused. Run the **entire** suite first. Extend the **fake Paystack server** to everything in C4 (initialize, verify, refund with every status, retry-with-details, recipients, transfers with every status, banks, resolve, balance, signed webhook emission, scenario hooks).

**Write `tests/e2e/test_paystack_money_flow.py`** (real database, real outbox, the worker run with `--once` between steps, the fake server through `httpx.ASGITransport`, an injected clock):
1. **Collect:** book → initiate (the fake returns an authorization URL) → the signed `charge.success` webhook → a verification lookup → the payment is confirmed, held and booking confirmed.
2. **Release:** scout sets a payout account → offer → accept → the admin releases → the transfer is created once → `transfer.success` → `RELEASED`, one ledger entry, a payout notice to the scout.
3. **Release blocked:** a scout with no account → blocked (`payout_account_missing`) → the scout is prompted → adds an account → still blocked until the cool-off applies **only if** an account was replaced (a first account has none) → released.
4. **Account swapped mid-flight:** decision made, account replaced, execution pays the decided account.
5. **Pending payout:** the fake says pending, then success on the second poll → one transfer in total.
6. **Uncertain payout:** the fake times out after accepting the transfer → `PROVIDER_PENDING` → recovery finds it by reference → success, **one** transfer.
7. **`otp` and `reversed`:** the operation lands in `RECONCILIATION_REQUIRED` with the right reason and an admin task, and **nothing is repaid automatically**.
8. **Refund (original rails):** booking closed after payment → admin refund → `processed` → refund notice, ledger balanced.
9. **Refund needs attention:** `needs-attention` → student prompted → submits an account → retry → `processed`.
10. **Stale:** a pending operation older than the threshold → `RECONCILIATION_REQUIRED`.
11. **Coverage:** balance below held → the summary and a task show it.

**Concurrency tests (each several runs):** two simultaneous `PUT payout-account`; webhook and recovery racing on one operation (one outcome applied); two `ExecuteRelease` calls (one transfer); duplicate webhook delivery; dispute racing a release (existing guarantee holds).

**Security tests:** the secret key appears in **no** log, response or fixture across all flows; **no account number or recipient code** appears anywhere outside the single outbound call; a forged webhook (wrong signature, tampered body) changes nothing; the mock controls are unreachable under `paystack`; a student/scout/staff permission matrix for every new route; a scout cannot read or change another scout's account; the resolve endpoint cannot be used as an oracle (rate limit, authorization, generic error).

**Regression:** the complete suites of Payment, Booking, Notification, Admin, Security, Platform, Identity, Housing, Messaging and Verification.

**Acceptance criteria:** all pass; report real counts.

---

### CHUNK 15 — SANDBOX SCRIPT, RUNBOOK, DOCUMENTATION AND AI STATE
**[FOR YOU — GEMINI CLI]**

**Write:**
1. **`scripts/paystack_sandbox_check.py`** — opt-in, **refuses any key that is not `sk_test_`**, never runs in CI, prints no secret. It performs, against Paystack's test environment: initialize a transaction and print the checkout URL; verify a reference you give it; list banks and **print the exact response shape of the bank, resolve and balance calls**; resolve a test account; create a test recipient; fetch the balance; create a refund against a payment made with **each refund-scenario test card documented on Paystack's Test payments page** (success, failed, needs attention) and print the statuses it reports; and — only with an explicit flag — initiate one small test transfer and verify it by reference. It also **prints every field name the webhook parser and the correlation rules rely on**, so Nsisong can compare them with the first real test webhooks (Chunk 5's "unconfirmed" list). Output is a report, not a pass/fail.
2. **`docs/modules/paystack_provider.md`** — what is built; the capability map; the outcome classification and status tables; the safety rules; the settings; **a runbook**: (a) Paystack dashboard setup — test keys, the webhook URL `https://<host>/api/v1/payments/webhooks/paystack`, the callback URL, manual payouts and the **transfer OTP** setting, and the operational meaning of each; (b) testing webhooks locally through a tunnel (mention Termux); (c) what each `failure_reason` and task type means and what an operator does; (d) the **go-live checklist**: legal/custody advice obtained, Paystack written confirmation, a verified business with manual payouts, live key only in `production`, small real transactions first, balance topped up, jobs enabled **deliberately** (`payment_auto_release`, `payment_release_warnings`, recovery), daily check of the coverage figure.
3. Update the Payment, Notification, Security and Platform module docs with a short "Paystack provider" note.
4. The **frontend documentation**: add **Part F** of this file, completing the behavior-change list with the real entries.
5. The **manual testing guide** from **Part G**, **running every scenario you can against the fake server and, only if Nsisong supplies test keys, the sandbox**; mark anything not run **not verified** — never invent an output.
6. ADR rows **265–282** in the decision log; **AI state:** module-complete status, new tables/jobs/settings/permission, the Known Limitations list below.

**Known limitations to state plainly:** real Paystack behavior is **unproven until the sandbox script and go-live checklist are completed**; refund and payout webhook correlation fields are provisional until confirmed; custody/licensing is **not** resolved by this software; the platform absorbs Paystack fees; a reversed payout and an `otp` transfer need a human; no IP allow-list; a refund account must be supplied by the student for `needs-attention` cases; naira only.

**Acceptance criteria:** the script runs against the fake server in a test; every document exists; the manual guide contains only real outputs or "not verified"; the full suite passes.

---

### CHUNK 16 — FINAL AUDIT
**[FOR YOU — GEMINI CLI]**

1. Run the **entire** suite, linters, type checker and `lint-imports`; paste the summary.
2. **Isolation audit:** a repository-wide search proves nothing under `domain/` or `application/` imports `httpx` or `adapters.provider.paystack`.
3. **Secrets audit:** search the repository, fixtures, logs from a full test run and the OpenAPI document for the test key, any `sk_` string, any full account number and any recipient code: **none**.
4. **Database audit:** show `ck_release_has_payout_account` exists and is `NOT VALID`, the partial unique index on `payout_accounts`, and the rejected insert of a new `RELEASE` decision without an account.
5. **Mock audit:** the mock adapter still passes the whole conformance suite and Module 10's original tests; mock controls are unreachable under `paystack` and in `staging`.
6. Confirm: the default `payment_provider` is `mock`; a live key is refused outside production; no raw provider message is stored or returned; every new system use case is unreachable by HTTP; no new money path exists outside `ApplyOperationOutcome` (show the search).
7. **Completion Report — three lists:** (a) **Verified** (command and output); (b) **Implemented but not verifiable here** (and why — chiefly everything that needs real Paystack); (c) **Not done** (and why). Do not blur them.

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

| What you asked for | Where it is built |
|---|---|
| **The real payment adapter (Paystack)** | C4, C5 · ADR-265 · Chunks 2–6 |
| **Plug in without breaking the rules; keep the paradigm** | C1 · ADR-265–270 · Chunk 6 (the conformance suite holds mock and Paystack to one contract) · Chunk 1 (import-linter) |
| **The existing mock keeps working** | ADR-265 · Chunk 6 · Chunk 16 (mock audit) |
| **Real refunds (moving money back)** | C4, C6 · ADR-267, 268 · Chunk 7 |
| **Real releases (moving money to the scout)** | C4, C9 · ADR-275, 278 · Chunk 10 |
| **A scout account for releases** | C8 · ADR-273–275 · Chunks 8–10 |
| **A student account for refunds** | C10 · ADR-276 · Chunk 11 |
| The gaps in Module 10 that a plain swap would have hit | Finding 1 (six items) · C3 · Chunks 4, 5, 7, 10 |
| Telling scouts and students what to do | C11 · Chunk 12 |
| Letting admins see stuck money and whether you can cover it | C12 · ADR-279 · Chunk 13 |
| Proving it works without touching real money | Chunk 14 (fake Paystack server) · Chunk 15 (opt-in sandbox script) |
| What you must decide outside code | Part B, Decisions 1–6 (custody and licensing first) |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

### What changes for payers (students)
The flow is the same; the checkout is Paystack's.
1. The student starts a payment with the **existing initiate-payment call**. With Paystack, the `checkout_reference` in the response is a **Paystack checkout web address**: send the student's browser there.
2. Paystack sends the student back to **your callback page** (the address configured as `paystack_callback_url`) with a reference in the web address.
3. **Never treat the redirect as proof of payment.** On the callback page, ask the API for the payment attempt's status (the existing status call) and show "confirming…" until it says `SUCCEEDED` (the server confirms through Paystack and its signed webhook). A student who closes the page mid-payment is still handled by the server.
4. **No Paystack keys, ever, in the frontend.** The frontend only receives the checkout address.

### Scouts: payout account screens (needs the scout role)
| Call | Use |
|---|---|
| `GET /api/v1/payments/banks` | Fill the bank dropdown: `[{code, name}]`. Any signed-in user. May answer `503 provider_unavailable` |
| `POST /api/v1/payments/bank-accounts/resolve` `{bank_code, account_number}` | Returns `{account_name}`. **Limited to 10 per hour.** An unknown account is always the same `422 account_not_found` |
| `GET /api/v1/payments/payout-account` | `{has_account, bank_code, bank_name, account_name, account_last4, release_hold_until}` |
| `PUT /api/v1/payments/payout-account` `{bank_code, account_number, expected_account_name}` | Save or replace the account |

**The screen must be two steps:** (1) the scout picks the bank and types the account number → call *resolve* → **show the returned account name and ask "Is this your account?"**; (2) on confirmation call `PUT` with **the same name** as `expected_account_name`. If the name changed in between you get `409 account_name_changed` — go back to step 1. **We never keep the full account number; only the last four digits are shown afterwards.**
**After a change, payouts to the new account wait** until `release_hold_until` (24 hours by default). Show this clearly ("For your security, payouts to a new account start after …").
**A scout with no account** cannot be paid. Show a prominent "Add a payout account" banner whenever they have a confirmed booking, and use the notification below.

### Students: finishing a refund
Most refunds return automatically to the original payment. Sometimes Paystack cannot (notably for bank-transfer payments) and the refund waits. The student then gets a notification with action **`PROVIDE_REFUND_ACCOUNT`** (target: the booking).
- Screen: bank dropdown → account number → **resolve and confirm the name** (same two-step pattern) → `POST /api/v1/payments/{payment_id}/refund-account` `{bank_code, account_number, expected_account_name}`.
- Answers: success (the refund continues, show "processing"); `404 no_refund_awaiting_account` (nothing is waiting — also what a wrong payment id gets); `409 account_name_changed`; `429` (rate limit).
- **The account can be any valid bank account belonging to the student**, not only the one they paid from. We do not keep it.

### New notifications (same API as before)
| `type` | For | Action | Meaning |
|---|---|---|---|
| `payment.payout_account_required.provider` | scout | **`ADD_PAYOUT_ACCOUNT`** (target `PAYOUT_ACCOUNT:<scout id>`) | A payment is waiting; add a bank account. Stays open until an account is added |
| `payment.payout_account_changed.provider` | scout | — | Security notice: the account was changed. Shown only after a **replacement** |
| `payment.payout_sent.provider` | scout | — | A payout was sent |
| `payment.refund_needs_account.student` | student | **`PROVIDE_REFUND_ACCOUNT`** (target the booking) | The refund needs a bank account. Stays open until submitted, refunded, or the booking closes |
| `payment.refund_processed.student` | student | — | The refund was processed; it can take a few working days to arrive |

### New reasons a release can be blocked (admin screens; same release-not-eligible error)
| `blocking_reason` | Say this |
|---|---|
| `payout_account_missing` | The scout has not added a payout account |
| `payout_account_cooling_off` | The scout changed their payout account recently; payouts resume after the cooling-off period |

### Admin additions (these appear only if the Release Governance amendment is built)
- **Transaction review detail:** `release.payout_destination` = `{status: ACTIVE | MISSING | COOLING_OFF, bank_name, account_last4, account_name, release_hold_until}`; refund operations show `provider_status_detail` (`needs_customer_account`) and `provider_fee_kobo`; release operations show a `failure_reason`.
- **Tasks:** new types `PAYOUT_ACCOUNT_MISSING` (chase the scout), `REFUND_NEEDS_ACCOUNT` (the student has not supplied an account), `PROVIDER_BALANCE_LOW` (see below). `RECONCILE_OPERATION` now carries a `failure_reason`: `provider_otp_required`, `payout_reversed`, or the provider was silent for too long.
- **Money coverage:** `GET /api/v1/payments/review/summary` gains `provider_coverage {provider_balance_kobo, held_total_kobo, coverage_ok, checked_at}`. **`coverage_ok: false` means Paystack's balance is lower than the money you currently hold for others — treat it as urgent.** `null` means "could not be checked" (or the mock is in use) — **never read null as OK**.

### Failure reasons you may see on an operation (codes only; never a provider message)
`provider_unreachable`, `provider_rejected`, `provider_insufficient_balance`, `provider_auth_failed`, `provider_rate_limited`, `invalid_recipient`, `provider_otp_required`, `payout_reversed`.

### What changed in behavior (check these)
| Where | Before | Now |
|---|---|---|
| Releasing funds | no destination needed | **blocked until the scout has an active payout account**, and for the cooling-off period after a change |
| Starting a payment | no email sent to a provider | the student's email is sent to Paystack (the frontend sends nothing new) |
| Refunds | succeeded or failed | can **wait for the student's bank account** |
| Pending payouts and refunds | could wait forever | after 24 hours they become an admin task |
| Scouts | no account screen | payout account screens above |

**Known limitations (tell your product people):** real Paystack behavior is unproven until the sandbox checks and the go-live checklist are done; naira only; a reversed or OTP-blocked payout needs a person; Paystack's fees are absorbed by the platform for now; the money-coverage check is a warning light, not a guarantee; whether Camp Match may hold users' money is a legal question this software does not answer.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — Gemini turns this into the testing document in Chunk 15, running what it can]

**Before you start:** have a student, a scout with a published listing, an admin and an operations account. Keep `PAYMENT_PROVIDER=mock` for G1–G2. For anything marked **(sandbox)** you need Paystack **test** keys (`sk_test_…`) — never a live key — and your API reachable by Paystack for webhooks (a tunnel works from Termux). Anything Gemini cannot run is written up as **not verified**.

**G1 — The app refuses dangerous settings.** Start with `PAYMENT_PROVIDER=paystack` and no key; then with a `sk_live_` key while `APP_ENV=local`.
*You should see:* the app **refuses to start** with a clear message each time. Nothing connects to Paystack.

**G2 — The mock still works exactly as before.** With the default provider, run a full booking, payment (mock controls), handover and release.
*You should see:* the same results as before this change — except that a **release needs a payout account** (G6), so add one first.

**G3 — A real test payment (sandbox).** `PAYMENT_PROVIDER=paystack`, test key, callback URL set. Run `python scripts/paystack_sandbox_check.py` (it prints what it found and refuses live keys). As the student start a payment, open the returned checkout address, and pay with one of **Paystack's published test cards**.
*You should see:* you land on your callback page; the attempt becomes `SUCCEEDED`, the booking `CONFIRMED`, and the payment is held. The script's report lists the field names Paystack actually sent.

**G4 — A forged webhook does nothing.** POST to `/api/v1/payments/webhooks/paystack` with a made-up body and a wrong `x-paystack-signature`.
*You should see:* the delivery is recorded as failed validation and **no payment or refund changes**; changing one character of a real, signed body does the same.

**G5 — Banks and name check.** As the scout `GET /api/v1/payments/banks`, then resolve a **test** account with `POST …/bank-accounts/resolve`.
*You should see:* a bank list; an account name for a valid test account; the same generic `account_not_found` for a bad one; the eleventh resolve in an hour is refused (`429`). As a student with no waiting refund the call is `403`.

**G6 — Add and change a payout account.** As the scout, resolve → confirm the name → `PUT …/payout-account`. Then change it to a different account.
*You should see:* the first account is `ACTIVE` with no waiting period; after the change the new account shows a `release_hold_until` about 24 hours ahead; the response **never** shows the full number or any provider code; sending a different name than the one resolved gives `409 account_name_changed`.

**G7 — A scout with no account.** Confirm a handover for a scout who has no account.
*You should see:* the admin's release is refused with `payout_account_missing`; within the hour the scout gets **"Add your payout account"** (an action that stays open until they add one); the admin's tasks list shows `PAYOUT_ACCOUNT_MISSING`. After the scout adds an account the action closes; if it was a **replacement**, release waits for the cooling-off period.

**G8 — Pay the scout (sandbox, small amount only).** With a test key and the explicit flag, release a small held amount.
*You should see:* one transfer created; the operation moves to pending then succeeded (by webhook or the recovery check); one ledger entry; the scout gets "Payout sent". If the transfer asks for an OTP, the operation lands in **needs a person** with `provider_otp_required` — switch the dashboard's transfer OTP setting only after reading the runbook.

**G9 — Swap the account after the decision.** Make a release decision, change the scout's account, then let the release execute.
*You should see:* the money goes to the **account that was on the decision**.

**G10 — Refunds.** Close a paid booking and refund it as the admin.
*You should see:* the refund moves pending → processed, the student gets "Refund processed", and the ledger balances. **To see the needs-attention path in the sandbox**, pay with the test card that Paystack's *Test payments* page lists for the "needs attention" refund outcome (that page also lists test bank details), then refund that payment: the student is prompted, supplies an account, and the refund completes. The fake server shows the same path offline.

**G11 — Stuck money is visible.** Leave a payout or refund pending past 24 hours (the fake server can do this).
*You should see:* it becomes **needs a person** and appears in the admin tasks list.

**G12 — The money warning light.** `GET /api/v1/payments/review/summary`.
*You should see:* `provider_coverage` with the balance, the held total and `coverage_ok`. Under the mock the balance is `null` — that means "not checked", not "fine".

**G13 — Nothing secret leaks.** Search the server logs from all of the above for your key, a full account number, or a recipient code.
*You should see:* none.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] **The default is still the mock, and the mock passes the whole conformance suite and Module 10's original tests** (Chunks 6, 16)
- [ ] **The app refuses to start in a dangerous configuration** (live key outside production, missing key, non-Paystack host) (Chunk 2)
- [ ] **No outcome is ever guessed:** a timeout is looked up by our own reference, never retried; an unknown status is never success (Chunks 3, 4, 7, 10)
- [ ] **Webhooks are verified on the raw bytes and are only triggers**; a forged or tampered one changes nothing (Chunks 5, 7)
- [ ] **Refunds work, including the "needs attention" path** (Chunks 7, 11)
- [ ] **A release pays the account recorded on its decision, and a new decision without one is rejected by the database** (Chunk 10)
- [ ] **A scout without an account, or within the cooling-off period, cannot be paid; they are told** (Chunks 10, 12)
- [ ] **Account numbers and the secret key appear nowhere: no log, response, row or fixture** (Chunks 2, 8, 14, 16)
- [ ] **Stuck, OTP-blocked and reversed payouts become admin tasks; nothing is repaid automatically** (Chunks 7, 10, 13)
- [ ] **Admins can see whether Paystack's balance covers what is held** (Chunk 13)
- [ ] **The sandbox script exists, refuses live keys, and lists the webhook fields to confirm** (Chunk 15)
- [ ] **Real Paystack behavior has been proven in the sandbox and with small real transactions before any real user's money moves** (your go-live checklist)
- [ ] **The custody and licensing question has been answered by qualified advisers and by Paystack in writing** (outside this software)

---

*End of the amendment specification.*
