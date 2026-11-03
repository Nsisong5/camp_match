# CAMP MATCH — MODULE 09: BOOKING
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Booking Module handoff**

---

## HOW TO READ THIS DOCUMENT

Same conventions as every previous module spec. Fifteen chunks requested; fourteen delivered, with two explicitly merged where they'd otherwise duplicate the same use case — noted exactly where that happens. Code stays minimal except where getting the exact sequence of operations wrong would cause real financial/inventory damage, not just a bug — the compensating-transaction logic in Chunk 6 gets the same precision treatment Housing's atomic reservation got in Module 5.

**Note on sequencing:** the Chief Engineer's module list now formally places Media/File at position 8 — matching exactly where it was inserted when built. No renumbering needed anywhere else; referred to as "Module 8" from here on, not "06B."

---

## ARCHITECTURAL INTERPRETATION & FINDINGS [FOR NSISONG]

Booking answers "has this student reserved this accommodation, and what happened to that reservation" — and almost nothing else. It's the module where a search result turns into a real, time-boxed claim on one specific unit, and where this project's various "derive, don't cascade" and "atomic update, not read-then-write" idioms get their highest-stakes exercise yet, because this is the module where getting either wrong costs someone a room or costs the business a double-booked one.

### FINDING 1 — the hardest technical requirement in this spec is already solved

Housing's `AvailabilityPort` (`reserve_slot`/`release_slot`) was built in Module 5 *specifically* anticipating this exact module — its own decision log says so explicitly: *"a future Booking module calling `reserve_slot` and then failing a later step of its own must call `release_slot` itself to undo it"* (Module 5, ADR-056). The Chief Engineer's Chunk 4 calls the Housing inventory contract "the highest-priority integration in Booking" and asks me to define it. There's nothing to define — it already exists, already atomic, already tested against real concurrent requests. This module's job is to consume it correctly, not build it.

### FINDING 2 — Payment & Escrow doesn't exist yet, and that changes what "confirmed" can mean right now

Booking is Module 9; Payment is Module 10 — it comes *after* this one. The handoff's Chunk 7 wants a "Payment Integration Boundary," and Chunk 11 wants confirmation driven by "payment condition satisfied." Neither can be real yet. Rather than leave `CONFIRMED` unreachable, `ConfirmBooking` is built as a genuine inbound port (ready for a future Payment module to call automatically) **and** exposed now through a narrow, staff-only manual endpoint — a deliberate, honest stand-in for a real payment webhook, not a workaround. It also happens to match how an early-stage Nigerian marketplace plausibly operates before a payment gateway is wired up: a bank transfer gets confirmed by a human, not a webhook. See ADR-094.

### FINDING 3 — one Housing fact is not enough to decide "is this bookable"

Housing's `reserve_slot` only knows about unit capacity — it has no idea whether the `Listing` wrapping that unit is `PUBLISHED`, `DRAFT`, or `ARCHIVED`. A `DRAFT` listing's unit could still have open capacity and `reserve_slot` would happily hand it out. So "is this listing bookable" is genuinely two separate facts from two different places — `Listing.status == PUBLISHED` (via `GetListing`) **and** unit capacity (via `reserve_slot`'s own atomic check) — and Booking has to check both, not assume the second implies the first.

No contradictions were found elsewhere in the handoff. Several further decisions were mine to make, consistent with the economy this project has favored throughout — see below.

### DECISIONS (ADR-094 … ADR-102) [FOR NSISONG]

Continuing the log from Phase 1–3 (001–013) through the University migration (089–093).

| ADR | Decision | Why |
|---|---|---|
| 094 | `ConfirmBooking` is a real inbound port, exposed now via a `BOOKING_CONFIRM`-gated manual endpoint, standing in for real payment-triggered confirmation | Finding 2. |
| 095 | No new Housing contract is built — this module consumes `AvailabilityPort` exactly as it already exists | Finding 1. |
| 096 | `PENDING` is dropped from the state machine — collapsed into `AWAITING_PAYMENT`. Four states, not five: `AWAITING_PAYMENT`, `CONFIRMED`, `CANCELLED`, `EXPIRED` | Creation is one synchronous, all-or-nothing operation — every precondition passes and inventory is reserved together, or nothing is persisted at all. A state representing "request received, reservation not yet attempted" has no observable window to occupy. |
| 097 | Hold expiration is **computed** from `expires_at` at the moment it's checked, never dependent on a cleanup job having run | The confirmed fifth instance of this project's "derive, don't cascade" idiom (after University & Location's campuses, Housing's listings, Verification's expiry, and now this). Directly resolves the handoff's own "payment arrives right as the hold expires" race (Part 26) — whichever operation checks `expires_at` at its own moment of execution wins, deterministically, with no dependency on background-job timing. |
| 098 | Cancellation is guarded by a conditional status update (`WHERE status IN ('AWAITING_PAYMENT','CONFIRMED')`), same atomic-write discipline as Housing's reservation and Verification's decisions — specifically so a **replayed** cancel request can never release a unit slot that's since been legitimately re-reserved by someone else | This is a real correctness requirement, not a defensive nicety — without it, a duplicate cancellation request arriving after the slot has already been re-booked would silently steal inventory out from under the new booking. |
| 099 | Booking requires the target property to currently be `VERIFIED` | A deliberate product call, not a default the architecture forces — reversible later if the product wants to allow unverified bookings with a warning instead. This platform's whole premise is trustworthy providers, so this MVP leans toward enforcing it. This is Verification's **second** real consumer, after Search. |
| 100 | No separate `booking_history` table | Booking's own row already carries every fact Part 38 asks for (`confirmed_at`, `cancelled_at`/`cancelled_by`/`cancellation_reason`) — its lifecycle (four states, few actors) doesn't have the depth that justified Verification's separate append-only log. |
| 101 | Only **one** new Security permission, `BOOKING_CONFIRM` (role-scoped, `OPERATIONS`+`ADMIN`). Provider-side booking visibility/cancellation reuses the existing `HOUSING_MANAGE` (ownership-scoped, already `ADMIN`-bypassable) | Managing bookings on your own property is the same underlying privilege as managing the property itself — a second permission for the same concept would be sprawl, not precision. |
| 102 | No `ProfileProvider` dependency anywhere in this module | Eligibility only needs authentication (Identity) and the self-booking check (Housing's own property data) — nothing in the handoff restricts booking by profile type, and inventing that restriction would be exactly the kind of unstated business rule the handoff tells me not to invent. |

**One item worth your attention specifically:** ADR-099. Requiring verification before booking is a real product lever, not an architectural inevitability — worth confirming it's actually the product's intent before this ships, since it's the one decision here that directly shapes what students can and can't do, not just how the code is organized.


---

## CHUNK 1 — CODEBASE INSPECTION & ARCHITECTURAL ALIGNMENT
**[FOR YOU — GEMINI CLI]**

**Implementation instructions:**
1. Read `AI_instructions/` in full and `AI_state/CURRENT_STATE.md`, `ARCHITECTURE_STATE.md`, `DATABASE_STATE.md`, `API_STATE.md`.
2. Read `docs/modules/identity.md`, `security.md`, `housing.md`, `verification.md`, `media.md`.
3. Inspect Housing's `application/ports/inbound.py` — confirm `AvailabilityPort`'s exact method signatures (`check_availability`, `reserve_slot`, `release_slot`) and `GetListing`/`GetProperty`'s exact response shapes (specifically: does `GetListing` return `unit_id` and `property_id` directly, and does `GetProperty` return `provider_id`).
4. Inspect Security's `domain/value_objects.py`/`policy.py` — confirm `HOUSING_MANAGE`'s current ownership-scoped behavior and `ADMIN`'s bypass, since this module reuses both exactly as they are.
5. Inspect Verification's `GetVerificationStatus` public port — confirm its exact request/response shape.
6. Report back confirming all of the above, or flag exactly what doesn't match before proceeding.
7. Create the module's empty structure:
```
src/camp_match/modules/booking/__init__.py
src/camp_match/modules/booking/domain/__init__.py
src/camp_match/modules/booking/domain/value_objects.py
src/camp_match/modules/booking/domain/entities.py
src/camp_match/modules/booking/domain/state_machine.py
src/camp_match/modules/booking/application/__init__.py
src/camp_match/modules/booking/application/errors.py
src/camp_match/modules/booking/application/ports/__init__.py
src/camp_match/modules/booking/application/ports/inbound.py
src/camp_match/modules/booking/application/ports/outbound.py
src/camp_match/modules/booking/application/use_cases/__init__.py
src/camp_match/modules/booking/adapters/__init__.py
src/camp_match/modules/booking/adapters/persistence/__init__.py
src/camp_match/modules/booking/adapters/housing/__init__.py
src/camp_match/modules/booking/adapters/verification/__init__.py
src/camp_match/modules/booking/adapters/api/__init__.py
tests/unit/booking/__init__.py
tests/unit/booking/domain/__init__.py
tests/unit/booking/application/__init__.py
tests/integration/booking/__init__.py
tests/api/booking/__init__.py
```

**Acceptance criteria:** written confirmation of steps 1–6; all files from step 7 importable.

---

## CHUNK 2 — BOOKING DOMAIN MODEL
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/value_objects.py`, `domain/entities.py`.

**`value_objects.py`:**
- **`BookingStatus`** (enum) — `AWAITING_PAYMENT`, `CONFIRMED`, `CANCELLED`, `EXPIRED` (ADR-096 — no `PENDING`).
- **`Currency`**, **`BillingPeriod`** — own copies, identical values to Housing's (`NGN`; `YEAR`/`SEMESTER`/`MONTH`), same cross-module duplication discipline as every other shared vocabulary in this project.
- **`PriceSnapshot`** — `amount_kobo` (non-negative int), `currency`, `period`. Immutable once constructed.

**`entities.py` — one entity, `Booking`:** `id` (`EntityId`, permanent), `student_id` (permanent), `listing_id`/`unit_id`/`property_id` (all `EntityId`, permanent — resolved once at creation, never re-fetched from Housing on every read), `status`, `price` (`PriceSnapshot`, permanent), `verification_confirmed_at_booking` (bool, permanent), `idempotency_key` (str, permanent), `expires_at` (permanent — a hold's expiry is fixed at creation, never extended), `created_at`, `confirmed_at`/`cancelled_at`/`cancelled_by`/`cancellation_reason` (all nullable, set only by their respective transitions).

Expose a read-only `is_hold_expired` property (ADR-097): `status == AWAITING_PAYMENT and expires_at < clock.now()` — **note this needs a `Clock` passed in to evaluate, not a bare `datetime.now()`** — same testability discipline as every time-dependent check in this project since Phase 2.

**Tests you must write:** `tests/unit/booking/domain/test_booking.py` — `is_hold_expired` is only true for `AWAITING_PAYMENT` bookings past their `expires_at`, using a `FixedClock` (Phase 2's test double) to prove it deterministically rather than sleeping in a test; every identity-bearing field has no mutation method.

**Acceptance criteria:** new tests pass; no import beyond stdlib + shared-kernel `EntityId`/`Clock`.

---

## CHUNK 3 — BOOKING STATE MACHINE
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/state_machine.py`.

**The legal transition table, exactly:**

| From | To |
|---|---|
| `AWAITING_PAYMENT` | `CONFIRMED` |
| `AWAITING_PAYMENT` | `CANCELLED` |
| `AWAITING_PAYMENT` | `EXPIRED` |
| `CONFIRMED` | `CANCELLED` |

`CANCELLED` and `EXPIRED` are terminal — nothing transitions out of either. There is no `CONFIRMED → EXPIRED` (a confirmed booking has no hold left to expire) and no `EXPIRED → CONFIRMED` (same reasoning as every other "the window closed" rule in this project — an expired hold is gone, not recoverable; a student who still wants the room creates a new booking).

Implement `can_transition`/`transition` with the same signature/error-message discipline as every previous module's state machine (Housing's `Listing`, Verification's `VerificationCase`) — name which rule was violated, not just "invalid transition."

**Tests you must write:** `tests/unit/booking/domain/test_state_machine.py` — every row succeeds; every transition not in the table is individually tested and rejected, including both directions of `CONFIRMED ↔ EXPIRED`.

**Acceptance criteria:** new tests pass; one named test per table row plus one per rejected transition.


---

## CHUNK 4 — HOUSING INVENTORY CONTRACT
**[FOR YOU — GEMINI CLI]**

**Objective:** confirm and wrap, not build (Finding 1) — this chunk's entire job is making Housing's existing port consumable from this module through the normal in-process-adapter pattern, nothing more.

**Files to modify:** `application/ports/outbound.py`.
**Files to create:** `adapters/housing/housing_provider.py`.

**`HousingProvider`** (this module's own outbound port, mirroring Housing's real shape — ADR-095 means this is a thin pass-through, not a redesign): `get_listing(listing_id) -> ListingSummary | None` (carries `unit_id`, `property_id`, `status`, `price_amount_kobo`/`currency`/`period`), `get_property_owner(property_id) -> EntityId | None`, `check_availability(unit_id) -> int`, `reserve_slot(unit_id) -> bool`, `release_slot(unit_id) -> None`.

**`InProcessHousingProvider`:** calls Housing's `GetListing`, `GetProperty`, and `AvailabilityPort` use cases directly — `application.ports` only, never `adapters`/`domain`. The `reserve_slot`/`release_slot`/`check_availability` methods are pure pass-throughs to Housing's existing `AvailabilityPort` — **do not add any additional logic, caching, or retry behavior here**; Housing's own implementation is already the atomic, tested primitive (Module 5, Chunk 7) and wrapping it in anything extra would only add a place for the atomicity guarantee to quietly get lost.

**Tests you must write:** `tests/unit/booking/adapters/test_housing_provider.py` — mirrors every other in-process adapter test in this project: fake underlying use cases, confirm correct mapping, confirm `reserve_slot`'s boolean result passes through unchanged (not reinterpreted).

**Acceptance criteria:** new test passes.

---

## CHUNK 5 — PERSISTENCE
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/persistence/models.py`, `adapters/persistence/repository.py`.

**`bookings`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | primary key |
| `student_id` | UUID | not null, no foreign key — indexed |
| `listing_id`, `unit_id`, `property_id` | UUID | not null, no foreign keys — `property_id` indexed (provider-visibility queries) |
| `status` | text | not null, `CHECK` restricted — indexed (needed for the expiration-finder query) |
| `price_amount_kobo` | bigint | not null |
| `price_currency` | text | not null |
| `price_period` | text | not null |
| `verification_confirmed_at_booking` | boolean | not null |
| `idempotency_key` | text | not null |
| `expires_at` | timestamptz | not null |
| `created_at` | timestamptz | server default |
| `confirmed_at`, `cancelled_at` | timestamptz | nullable |
| `cancelled_by` | UUID | nullable |
| `cancellation_reason` | text | nullable |

**Unique constraint** on `(student_id, idempotency_key)` — the idempotency guarantee (Part 14), database-enforced, not just application-checked.

**`BookingRepository`:** `add` (translating a unique-constraint violation on `(student_id, idempotency_key)` into returning the existing row rather than an error — see Chunk 6 for exactly how the use case uses this), `get_by_id`, `get_by_idempotency_key`, `find_by_student` (paginated), `find_by_property` (paginated), `find_expired_holds(as_of: datetime) -> list[Booking]` (the query the expiration job uses — `status = 'AWAITING_PAYMENT' AND expires_at < as_of`). **The concurrency-safe transitions (ADR-097/098):** `confirm` and `cancel` each perform a conditional `UPDATE ... WHERE status IN (...)` and report whether a row actually matched, same atomic-write discipline as Housing's reservation and Verification's decisions — the calling use cases (Chunks 6/10/12) turn "zero rows matched" into the appropriate specific error.

**Migration:** `poetry run alembic revision --autogenerate -m "add bookings table"`, read before applying.

**Tests you must write:** `tests/integration/booking/test_repository.py` (marked `integration`) — CRUD; the idempotency-key uniqueness constraint; `find_expired_holds` correctly filters by status and time; the conditional-update methods tested exactly like Housing's reservation race (two simulated concurrent `confirm`/`cancel` attempts on one booking — exactly one succeeds).

**Acceptance criteria:** new tests pass against local Termux Postgres; migration applies cleanly; the concurrency test passes reliably across repeated runs.


---

## CHUNK 6 — BOOKING CREATION
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/create_booking.py`.

**`CreateBooking` — steps, in this exact order, with the reasoning for the order stated where it matters:**

1. **Idempotency check first, before anything else:** call `BookingRepository.get_by_idempotency_key(student_id, idempotency_key)`. If found, **return the existing booking as-is — this is a success response, not an error**, and stop here. Nothing below this line runs for a replayed request.
2. Resolve the listing via `HousingProvider.get_listing` — `BookingNotFound`... no — raise `ListingNotBookable` if it doesn't exist at all (a nonexistent listing is never bookable, and a distinct `ListingNotFound` would just be the same information under a different name for this caller).
3. **Self-booking check (Part 19):** resolve the property's owner via `HousingProvider.get_property_owner`; if it equals the caller's `student_id`, raise `SelfBookingNotAllowed`.
4. **Listing-state check (Finding 3) — separate from inventory:** if `listing.status != PUBLISHED`, raise `ListingNotBookable`.
5. **Verification check (ADR-099):** call `VerificationProvider.get_verification_status(PROPERTY, property_id)`; if not currently verified, raise `VerificationRequirementNotSatisfied`.
6. **Reserve inventory — the one irreversible external action in this whole flow, so everything before it must be a pure check with no side effects:** call `HousingProvider.reserve_slot(unit_id)`. `False` → raise `InventoryUnavailable`, stop here, **nothing was reserved, nothing needs to be undone.**
7. **From here on, inventory is held — every failure path below must release it before propagating the error (the compensating-transaction requirement, Part 15/16):** construct the `Booking` entity (`status=AWAITING_PAYMENT`, the price snapshot copied from the listing, `expires_at = clock.now() + hold_duration`, `verification_confirmed_at_booking = True`); attempt `BookingRepository.add`.
8. **If the persistence write fails for any reason:** catch it, call `HousingProvider.release_slot(unit_id)` to compensate, then let the original error propagate (don't swallow it — the caller needs to know creation failed, not get a misleadingly generic error). Log at **ERROR** here specifically (not the usual INFO/WARNING tiers) — a reservation that had to be manually compensated is worth a louder signal than a routine failure, since it represents exactly the "Housing reserved, Booking insert failed" scenario the handoff calls out by name (Part 15).
9. **On success:** log INFO (`"booking_created"`, booking id, listing id, student id, hold expiry); return the booking.

**`hold_duration`** comes from `Settings` (new field, `booking_hold_duration_minutes: int = 30` — a reasonable default, configurable, not hard-coded per Part 23's explicit instruction).

**Tests you must write:** `tests/unit/booking/application/test_create_booking.py`, against fakes — the full happy path; the idempotent-replay path (confirm the fake `HousingProvider.reserve_slot` is **not** called a second time on replay — proving idempotency actually short-circuits before touching inventory again, not just before touching the database again); self-booking rejection; unpublished-listing rejection; unverified-property rejection; inventory-unavailable rejection; **the compensating-release path** — configure the fake repository to raise on `add`, and assert the fake `HousingProvider.release_slot` was called with the right `unit_id` before the error propagates.

**Acceptance criteria:** new tests pass, all against fakes — the compensating-transaction test specifically is non-negotiable; this is the one path in this module where a missed test would hide a real, costly bug (a permanently stuck reservation) rather than just a wrong response.


---

## CHUNK 7 — PAYMENT INTEGRATION BOUNDARY & CONFIRMATION
**[FOR YOU — GEMINI CLI]**

**Note on structure:** the handoff's Chunks 7 and 11 are merged here — both describe the same use case (`ConfirmBooking`) from two angles ("the Payment boundary" and "the confirmation logic"), and splitting them would mean writing the same file twice. Noted explicitly rather than silently deviating.

**Files to create:** `application/use_cases/confirm_booking.py`.

**`ConfirmBooking` — steps:**
1. Look up the booking; `BookingNotFound` if absent.
2. **Check `is_hold_expired` (the computed property, Chunk 2) before anything else** — if true, raise `InvalidBookingStateTransition` with a message naming it as an expiration, not a generic state error (ADR-097's race-resolution rule in practice: even if the stored `status` still reads `AWAITING_PAYMENT` because the cleanup job hasn't run yet, a confirmation attempt past `expires_at` is rejected here, deterministically, every time).
3. Authorize via `BOOKING_CONFIRM` (role-scoped, `OPERATIONS`/`ADMIN` — ADR-094/101).
4. **Concurrency-safe write:** call `BookingRepository.confirm` (the conditional `UPDATE ... WHERE status = 'AWAITING_PAYMENT'` from Chunk 5) — zero rows matched means someone else already confirmed or cancelled it in the meantime; raise `InvalidBookingStateTransition` in that case too, don't silently succeed.
5. Set `confirmed_at`; log INFO.

**This is the entire "Payment Integration Boundary" for this MVP (Finding 2/ADR-094):** there is no outbound port to a Payment module, because there is no Payment module yet. When Module 10 is built, it will call this exact same inbound port in-process — nothing about `ConfirmBooking`'s own logic needs to change for that to happen; only a new caller gets added. Document this explicitly in `docs/modules/booking.md` (Chunk 14) so nobody mistakes the manual endpoint for a permanent design rather than a stand-in.

**Tests you must write:** `tests/unit/booking/application/test_confirm_booking.py` — happy path; expired-hold rejection (using `FixedClock`, same discipline as Chunk 2's test); the concurrency guard (fake repository reports zero rows matched → `InvalidBookingStateTransition`, not a silent success); unauthorized caller rejected.

**Acceptance criteria:** new tests pass, all against fakes.

---

## CHUNK 8 — VERIFICATION INTEGRATION
**[FOR YOU — GEMINI CLI]**

**Objective:** verification, not new code — `CreateBooking` (Chunk 6) already consumes `VerificationProvider` in full. This chunk is the adapter that makes that port real.

**Files to create:** `adapters/verification/verification_provider.py`.

**`InProcessVerificationProvider`:** implements this module's `VerificationProvider` outbound port, calling Verification's existing public `GetVerificationStatus` use case directly — `application.ports` only. Maps its `is_verified`/`verified_on` response straight through; no translation logic needed beyond that, since this module only ever asks one simple question.

**Tests you must write:** `tests/unit/booking/adapters/test_verification_provider.py` — mirrors every other in-process adapter test in this project.

**Acceptance criteria:** new test passes.

---

## CHUNK 9 — EXPIRATION
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/expire_holds.py`, `scripts/expire_booking_holds.py`.

**`ExpireHolds` — steps:** call `BookingRepository.find_expired_holds(as_of=clock.now())`; for each: call `HousingProvider.release_slot(unit_id)`, then the concurrency-safe `BookingRepository` transition to `EXPIRED` (same conditional-update pattern as confirm/cancel — guards against the job somehow running twice concurrently on the same row); log INFO per booking, and a summary (count processed) at the end. **A release failure for one booking must not abort processing the rest** — log that one at WARNING and continue; a stuck hold is recoverable by running the job again, a cascading failure that skips every subsequent booking isn't acceptable.

**`scripts/expire_booking_holds.py`** (ADR — "the MVP may use an existing scheduling mechanism if one exists"; none does, so this is a plain, manually or cron-invoked script, same pattern as University & Location's CSV importer, Module 4): a thin CLI entry point that composes `ExpireHolds` with its real dependencies and runs it once per invocation. **No scheduler, no daemon, no APScheduler/Celery dependency is added to the project** — running this periodically (a simple cron entry, or manually during testing) is an operational concern, documented in `docs/modules/booking.md`, not something this module builds infrastructure for.

**Tests you must write:** `tests/unit/booking/application/test_expire_holds.py` — processes multiple expired holds correctly; a release failure on one doesn't stop the others (assert the fake `HousingProvider` was still called for every booking even after one raised); a booking that's already `CONFIRMED`/`CANCELLED` by the time the job runs (a genuine race with Chunk 7's confirmation) is skipped, not force-expired.

**Acceptance criteria:** new tests pass.

---

## CHUNK 10 — CANCELLATION
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/cancel_booking.py`.

**`CancelBooking` — steps:**
1. Look up the booking; `BookingNotFound` if absent.
2. **Authorize — two paths, same dual-path pattern as Verification's `AddEvidence` (Module 7):** the caller is the booking's `student_id` (structurally self-scoped, no permission needed — matches every other `/me`-style check in this project), **or** the caller holds `HOUSING_MANAGE`, ownership-scoped against the booking's `property_id` (the provider cancelling a booking on their own property, or an `ADMIN` via the existing bypass). Neither matching raises `Forbidden`.
3. Require a non-empty `cancellation_reason`.
4. **Concurrency-safe write (ADR-098 — this is the one that prevents the real correctness bug, not just a convenience check):** call `BookingRepository.cancel` (conditional `UPDATE ... WHERE status IN ('AWAITING_PAYMENT', 'CONFIRMED')`). **Zero rows matched means the booking is already `CANCELLED` or `EXPIRED` — treat this as an idempotent no-op success, not an error, and critically, do not call `release_slot` in this case** (the inventory was already released when it first transitioned to its terminal state — calling release again here is exactly the double-release risk ADR-098 exists to prevent).
5. **Only if the conditional update actually matched a row:** call `HousingProvider.release_slot(unit_id)`; set `cancelled_at`/`cancelled_by`/`cancellation_reason`; log INFO.
6. **Do not implement refund logic anywhere in this use case** — cancellation is a fact Booking records; what, if anything, gets refunded is Payment's future decision entirely, made through whatever contract Module 10 eventually defines.

**Tests you must write:** `tests/unit/booking/application/test_cancel_booking.py` — student self-cancel succeeds and releases inventory; provider cancel (via `HOUSING_MANAGE` ownership) succeeds; an unrelated account gets `Forbidden`; empty reason rejected; **the double-cancel/release proof specifically**: cancel a booking twice in a row (simulating a replayed request) and assert `HousingProvider.release_slot` was called **exactly once**, not twice — this is the test that actually proves ADR-098's reasoning holds, not just that the second call "doesn't error."

**Acceptance criteria:** new tests pass, with the double-cancel test treated as seriously as Chunk 6's compensating-transaction test — both protect against a real inventory-integrity bug, not a cosmetic one.


---

## CHUNK 11 — QUERIES
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/get_booking.py`, `list_my_bookings.py`, `list_bookings_for_property.py`.

**`GetBooking` — steps:** look up; visibility matches Chunk 10's authorization split (student owner, or `HOUSING_MANAGE`-ownership for the property's provider, or `ADMIN`) — anyone else, `Forbidden`.

**`ListMyBookings`** — structurally self-scoped (no target parameter), same discipline as every other `/mine`-style query in this project.

**`ListBookingsForProperty`** — `HOUSING_MANAGE`, ownership-scoped against the given `property_id`. **Response shaping (Part 49 — provider visibility must not leak unrelated student data):** the provider-facing response includes only what's needed to manage the reservation — booking id, status, price snapshot, dates — **no student profile fields at all**, not even a name, since Booking has no `ProfileProvider` (ADR-102) and shouldn't acquire one just to decorate this response. If a provider genuinely needs to know who they're renting to, that's Messaging's future concern, not something to bolt onto this query.

**Tests you must write:** one file per use case — the response-shaping test for `ListBookingsForProperty` specifically (assert the response schema has no field capable of carrying a student's name/email/phone — a structural check, not just "doesn't currently include it").

**Acceptance criteria:** new tests pass.

---

## CHUNK 12 — FASTAPI & AUTHORIZATION
**[FOR YOU — GEMINI CLI]**

**Files to modify (Security, using its own documented extension recipe — Module 3, Section 5):** `modules/security/domain/value_objects.py` (add `BOOKING_CONFIRM` to `Permission`, role-scoped), `modules/security/domain/policy.py` (`BOOKING_CONFIRM` → `OPERATIONS`, `ADMIN`).

**Prohibition:** exactly those two lines — nothing else in Security changes. `HOUSING_MANAGE` is reused as-is (ADR-101) — no changes to it at all.

**Files to create:** `adapters/api/schemas.py`, `adapters/api/router.py`, `adapters/api/dependencies.py`.
**Files to modify:** `app.py`.

**Six endpoints, all under `/api/v1/bookings`:**

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `` | authenticated | `idempotency_key` required in the body |
| GET | `/{id}` | per Chunk 11's visibility rule | |
| GET | `/mine` | authenticated | self-scoped |
| GET | `/for-property/{property_id}` | `HOUSING_MANAGE` | ownership |
| POST | `/{id}/cancel` | per Chunk 10's dual path | `cancellation_reason` required |
| POST | `/{id}/confirm` | `BOOKING_CONFIRM` | the Finding 2 stand-in |

**Request DTO for creation accepts exactly:** `listing_id`, `idempotency_key` — **nothing else** (Part 46's explicit warning: no client-suppliable `status`, `amount`, or anything else server-authoritative). No `unit_id` in the request — it's resolved server-side from the listing, never trusted from the client.

**Prohibition, same as every module before this one:** no business logic in `router.py`.

**Tests you must write:** placeholder only — real API tests arrive in Chunk 13.

**Acceptance criteria:** the app starts; each endpoint enforces the auth/permission combination in its row above.

---

## CHUNK 13 — CONCURRENCY & FAILURE TESTING
**[FOR YOU — GEMINI CLI]**

**This chunk must not be skipped, per the handoff's own instruction — and for good reason: this is where the module's two most financially consequential properties get proven against real concurrent HTTP traffic, not just fakes.**

**Files to create:** `tests/api/booking/test_concurrency.py`, `tests/api/booking/test_failure_scenarios.py`, `tests/api/booking/test_booking_flow.py`.

**`test_concurrency.py`:** create a listing with a unit of capacity 1 (mirroring Housing's own concurrency test pattern, Module 5); fire genuinely concurrent `POST /bookings` requests from different students (`asyncio.gather`, not sequential calls dressed up as concurrent — same standard Housing's own test held itself to); assert exactly one succeeds, confirm the unit's `available_count` lands at exactly 0, not negative. Repeat with capacity 5 and ten concurrent attempts — exactly 5 succeed. **Run this at least three times in a row before considering it passing**, same reliability bar as Housing's own reservation test.

**`test_failure_scenarios.py`:** every scenario the handoff names in its Part 54, as an individual test — nonexistent listing; inactive/unpublished listing; unverified property; concurrent booking (covered above, referenced here); a simulated persistence failure after a successful reservation (confirm the compensating release happens — same as Chunk 6's unit test, now proven through the real repository against a real database, injecting the failure at the database layer); double cancellation (no double release — Chunk 10's proof, now end to end); double release via a replayed cancel arriving after the slot was legitimately re-booked by someone else (the specific scenario ADR-098 was written to prevent — construct it deliberately: cancel, let another student re-book the freed slot, replay the original cancel, confirm the new booking's inventory is untouched).

**`test_booking_flow.py`:** the full happy path through real HTTP — create, confirm (as an `OPERATIONS` account), list mine, list for-property (as the Scout) — and the expiration path — create a booking with a very short hold duration (override via test configuration), wait past it, run `ExpireHolds`, confirm the booking is `EXPIRED` and the unit's capacity is back to available.

**Run everything:** `poetry run pytest`, `poetry run ruff check .`, `poetry run mypy src`, `poetry run lint-imports` — the whole project, every module built so far, green.

**Acceptance criteria:** every scenario above passes, with the concurrency and double-release tests specifically run multiple times and passing reliably, not once by luck.

---

## CHUNK 14 — DOCUMENTATION, FRONTEND API & AI STATE
**[FOR YOU — GEMINI CLI]**

See "Module Documentation Requirements," "Frontend Documentation," and "AI State Requirements" below. Use the standard `CURRENT_TASK.md` status-block format throughout.

---

## CHUNK 15 — FINAL ARCHITECTURE AUDIT
**[FOR YOU — GEMINI CLI]**

Confirm every item in the Completion Checklist below. Run the full project suite one final time from a clean state. Re-run the concurrency and double-release tests from Chunk 13 at least three times each as the very last step before reporting this module complete.


---

## FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**Applies everywhere in this module:** `/bookings/{id}/confirm` is a temporary, staff-only stand-in for real payment confirmation — don't build a student-facing "mark as paid" button around it; it exists for operational use until Payment & Escrow ships.

### POST /api/v1/bookings
**Authentication:** required. **Authorization:** none beyond authentication, except the self-booking rule.
**Request body:** `listing_id`, `idempotency_key` (a client-generated UUID — generate a new one per booking *attempt*, and reuse the exact same value if retrying after a network error, never a fresh one).
**Success — 201** (or **200** if this exact `idempotency_key` was already used — same booking returned either way).
**Errors:** 403 `self_booking_not_allowed`; 422 `listing_not_bookable` / `verification_requirement_not_satisfied`; 409 `inventory_unavailable`.
**Frontend notes:** a hold lasts 30 minutes from creation — show a countdown, and know that it will not be extended by any client action.

### GET /api/v1/bookings/{id}, /mine
Standard lookup patterns. `/mine` is always the caller's own.

### GET /api/v1/bookings/for-property/{property_id}
**Authorization:** `housing.manage` + ownership.
**Frontend notes:** this response never contains the student's name, email, or phone — only the reservation facts. Don't expect it to double as a contact list.

### POST /api/v1/bookings/{id}/cancel
**Authorization:** the booking's own student, or the property's owner.
**Request body:** `cancellation_reason` (required).
**Success — 204**, idempotent — safe to call more than once.
**Frontend notes:** cancellation never triggers a refund by itself — that's a separate, future Payment concern.

### POST /api/v1/bookings/{id}/confirm
**Authorization:** staff only (`booking.confirm`).
**Success — 200.** **Errors:** 422 if the hold has already expired, even if that hasn't been "cleaned up" in the database yet — the expiry check is always live.

---

## MANUAL TESTING GUIDE [FOR NSISONG]

**Preconditions:** `scripts/db_start.sh` running; the app running; a Scout with a **verified** property (run through Module 7's manual guide first if needed) with a listing, two Student accounts, one `OPERATIONS` account.

1. **Create:** as Student A, `POST /bookings` for the listing. Expect `201`, `status: "AWAITING_PAYMENT"`.
2. **Idempotent replay:** repeat the exact same request (same `idempotency_key`). Expect the same booking back, not a new one — and confirm the unit's available count didn't drop a second time.
3. **Self-booking:** as the Scout who owns the property, attempt step 1. Expect `403`.
4. **Unverified property:** revoke the property's verification (via Module 7's revoke endpoint), attempt a new booking on it. Expect `422`.
5. **Confirm:** as the `OPERATIONS` account, `POST /bookings/{id}/confirm`. Expect `200`, `status: "CONFIRMED"`.
6. **Cancel after confirmation:** as Student A, cancel the now-confirmed booking. Expect `204`; confirm the unit's inventory is released.
7. **Cancel twice:** repeat step 6. Expect `204` again, not an error — and confirm (by checking the unit's `available_count` directly) that it didn't increase a second time.
8. **Expiration:** create a fresh booking, then (for testing purposes) directly adjust its `expires_at` to the past via the database, then run `scripts/expire_booking_holds.py` manually. Confirm the booking is now `EXPIRED` and its unit's capacity is available again.
9. **Provider visibility:** as the Scout, `GET /bookings/for-property/{property_id}` — confirm it lists the bookings but includes no student contact information anywhere in the response.

**Failure interpretation:** if step 7's second cancel increases `available_count` again, that's the exact correctness bug ADR-098 exists to prevent — a phantom extra slot that doesn't correspond to anything real. Treat it with the same severity as a failed concurrency test. If step 2 creates a second booking or decrements inventory twice, idempotency isn't actually working and duplicate client submissions will silently double-book students.

---

## AUTOMATED TESTING GUIDE [FOR NSISONG]

- Just Booking: `poetry run pytest tests/unit/booking tests/integration/booking tests/api/booking`
- Domain only (fast, no database): `poetry run pytest tests/unit/booking -v`
- The concurrency and failure-scenario tests specifically, run several times: `for i in 1 2 3; do poetry run pytest tests/api/booking/test_concurrency.py tests/api/booking/test_failure_scenarios.py -v; done`
- Full verification: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`
- After this module, re-run Housing's, Security's, and Verification's suites in isolation to confirm each is unaffected apart from its one documented, intentional addition (Security's new permission).


---

## MODULE DOCUMENTATION REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 14]

Write `docs/modules/booking.md`. Cover: purpose/ownership/non-ownership (this document's Architectural Interpretation, condensed, all three Findings included with reasoning intact); the domain model and state machine table verbatim; the full `CreateBooking` sequence from Chunk 6, including exactly why the ordering is what it is and the compensating-release rule — this is the part most likely to be touched carelessly by a future engineer who doesn't understand why reservation happens before persistence, so it needs to actually explain the reasoning, not just list the steps; the idempotency mechanism; the expiration model and the "computed, not cascaded" rule, explicit about the payment/expiration race resolution; the cancellation idempotency rule (ADR-098) with the double-release scenario spelled out concretely, not just named; the `ConfirmBooking` stand-in (Finding 2) stated plainly as temporary, with the exact shape a future Payment integration would take (same inbound port, a new caller); the authorization table; the scheduler note (a plain script, no infrastructure, how to actually run it); known limitations — no refunds (Payment's future job), no provider-initiated booking modification beyond cancel, no multi-unit/multi-night booking (one booking = one unit, indefinitely, matching Housing's own billing-period model, not date-ranged).

## FRONTEND DOCUMENTATION REQUIREMENTS [reference — already provided above, verbatim, ready to copy]

## AI STATE REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 14]

Update `CURRENT_STATE.md`, `PROGRESS.md`, `COMPLETED_WORK.md`, `ARCHITECTURE_STATE.md` (note this module consumed Housing's `AvailabilityPort` exactly as built, with no changes to it — the first module in this project to need zero modification of an existing contract because the contract was built right the first time), `DATABASE_STATE.md`, `API_STATE.md`, `TEST_STATE.md`, `DECISIONS.md` (append ADR-094–102), `SESSION_HANDOFF.md` — set the next task to Module 10 (Payment & Escrow), with an explicit note that `ConfirmBooking` is waiting for it as a real inbound port, not something Payment needs to request be built. Security's own state should note its sixth permission (`BOOKING_CONFIRM`). Use the standard `CURRENT_TASK.md` status-block format.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] A booking can be created, reserving real inventory atomically through Housing's existing contract — no new Housing code was needed, confirmed by inspection.
- [ ] Idempotent replay returns the same booking, confirmed not to touch inventory a second time.
- [ ] Self-booking, unpublished listings, and unverified properties are all correctly rejected, each with its own distinct error.
- [ ] **The compensating-release path works** — a persistence failure after a successful reservation releases that inventory, proven by a specific test, not assumed.
- [ ] **The concurrency test passes reliably across multiple runs** — exactly one booking succeeds when only one slot exists, no matter how many requests race for it.
- [ ] **The double-cancel/double-release test passes** — a replayed cancellation never releases a slot a second time, proven with the specific scenario where that slot has since been legitimately re-booked by someone else.
- [ ] Hold expiration is correct even when the cleanup job hasn't run — a confirmation attempt past `expires_at` is rejected regardless of stored status.
- [ ] `ConfirmBooking` works as a staff-gated manual action today and is documented plainly as a stand-in, not a permanent design.
- [ ] Provider-facing booking lists never expose student contact information.
- [ ] No refund logic exists anywhere in this module.
- [ ] No cross-module database access in any direction.
- [ ] Unit, integration, API, and architecture tests all pass — every module built so far, together.
- [ ] `docs/modules/booking.md` exists and covers everything above, with the `CreateBooking` ordering and the cancellation idempotency rule explained in enough depth to actually prevent a future regression, not just describe the current behavior.
- [ ] All `AI_state/` files updated, including Security's.
- [ ] Known limitations documented plainly, especially the temporary nature of manual confirmation.

