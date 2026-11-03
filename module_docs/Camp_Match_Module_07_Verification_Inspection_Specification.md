# CAMP MATCH — MODULE 07: VERIFICATION & INSPECTION
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Verification & Inspection Module handoff**

---

## HOW TO READ THIS DOCUMENT

Same conventions as the previous six module specs. Thirteen chunks, followed exactly, with the usual surrounding sections. This is the most workflow-heavy module yet — a real state machine, a real two-actor-minimum trust boundary (inspector ≠ decider), and the module that finally closes a loop Module 6 deliberately left open.

**On the standing invitation to flag contradictions — three real findings this time, not one.** All three are architectural, not cosmetic, so they're presented first, before any implementation content.

---

## ARCHITECTURAL INTERPRETATION & FINDINGS [FOR NSISONG]

Verification answers a narrower question than "is this legit" — it answers "did Camp Match's own defined process find enough evidence, at a point in time, to say so." That distinction is the whole point of this module, and it shapes almost every design decision below: nothing here is a permanent fact, everything is a documented conclusion with a reason and a date attached to it.

### FINDING 1 — there is still no media/file storage module, and this is the third time it's mattered

Profile's avatar (Module 2) and Housing's listing photos (Module 5) both already punted on this — they store a bare URL string someone else has to populate, with no real upload/storage mechanism anywhere in the project. Verification evidence is the third module to hit this exact wall, and it's the worst possible one to hit it on: evidence can include identity documents and inspection photos, not just a listing photo. I'm not building a media module here either — that would be real scope creep, a shared-infrastructure decision dressed up as part of this module's spec. But three modules independently reaching the same gap is a pattern, not a coincidence, and it's worth treating as one. See ADR-069 and the recommendation at the end of this section.

### FINDING 2 — no KYC/NIN/BVN port, and that's correct, not a shortcut

Part 25 asks me to define an `IdentityVerificationPort` "only if it provides genuine architectural value" and Part 47 explicitly forbids automated NIN/BVN integration in this pass. Taken together, there's no real external provider to point a port at — so I'm not building one. Provider verification uses the exact same evidence-based, human-reviewed workflow as Property verification (documents submitted, an Operations reviewer looks at them). This isn't a workaround; it's what the handoff itself asks for when both instructions are read together. See ADR-070.

### FINDING 3 — this module is the other half of a promise Module 6 made

Search & Discovery shipped with a `VerificationProvider` that always answers "unknown" — a deliberate stub, explicitly flagged at the time as pending "until Module 7 ships" (Module 6, ADR-063). This is that module. Chunk 10 replaces the stub with a real adapter. This is worth knowing about specifically because it's the first time in this project a previous module's *named, deliberate* gap gets closed by name, rather than just accumulating more gaps — worth treating as a small proof the documentation discipline from a few sessions ago is actually working.

**My recommendation, not a decision I made unilaterally:** given three modules have now independently needed "store a reference to a file somewhere," a small, dedicated Media/File module — even a minimal one, just upload + reference issuance, no fancy processing — would retire this gap properly instead of it recurring a fourth time in Booking or Trust & Safety. Worth considering for the module sequence, whenever convenient — not blocking this one.

### DECISIONS (ADR-069 … ADR-077) [FOR NSISONG]

Continuing the log from Phase 1–3 (001–013) through Search & Discovery (061–068).

| ADR | Decision | Why |
|---|---|---|
| 069 | No media module built here — evidence stores a bare `media_reference` string, same pattern as Profile/Housing | Real infrastructure decision, out of scope for a single module's spec (Finding 1). |
| 070 | No KYC/external-identity port built — provider verification is evidence-based and human-reviewed, same workflow as property verification | Finding 2 — genuinely no implementation to point a port at, and the handoff explicitly forbids building the automated version now. |
| 071 | Two verification target types only — `PROVIDER` and `PROPERTY`. A listing's verification status is always **derived** from its property's, never stored separately | A listing is Housing's marketplace wrapper around a unit within a property — verifying the property IS verifying what a listing represents. Same "derive, don't duplicate" idiom this project keeps reaching for. |
| 072 | Verification requirements are **static, code-defined per target type** (mirroring Security's own role→permission pattern, Module 3) — no `verification_requirements` table | Nothing about MVP requirements needs to be editable at runtime; a database table for a fact that never changes without a code deploy anyway is unjustified weight. |
| 073 | Expiration is **computed at read time** from a stored `expires_at`, never a background-job-triggered state flip. Revocation stays a real, explicit, audited transition | The third confirmed use of this exact pattern (after Module 4's campus availability and Module 5's listing bookability) — worth naming as a settled project idiom, not a one-off. Revocation is different in kind: it's an active decision with a reason and an actor, which expiration by definition never has. |
| 074 | The inspector on a case's inspection may **never** also be that case's decision-maker — a real, tested, enforced invariant | Part 18 asked me to decide and document this explicitly rather than silently designing around it. Enforcing it is the safer, more defensible choice for a trust-critical workflow, and it costs almost nothing to check. |
| 075 | Security's `OPERATIONS` role — defined since Module 3, empty ever since — gets its first real permissions here | Worth flagging as a small milestone: a role that's existed on paper since the very first permission was granted finally does something. |
| 076 | This module's public status port **replaces** Search's `NullVerificationProvider` stub (Module 6) with a real adapter | Finding 3. |
| 077 | Concurrent decisions on one case are prevented with a conditional `UPDATE ... WHERE status = 'DECISION_PENDING'`, checked by affected-row-count | The same atomic-update discipline Housing used for inventory (Module 5) — two reviewers racing to decide the same case is structurally the same problem as two students racing for the same room. |


---

## CHUNK 1 — CONTEXT & ARCHITECTURAL CONTRACT
**[FOR YOU — GEMINI CLI]**

**Implementation instructions:**
1. Read `AI_instructions/` in full and `AI_state/CURRENT_STATE.md`, `ARCHITECTURE_STATE.md`, `DATABASE_STATE.md`, `API_STATE.md`.
2. Read `docs/modules/identity.md`, `profile.md`, `security.md`, `university_location.md`, `housing.md`, `search.md`.
3. Inspect Security's `domain/value_objects.py`/`policy.py` — confirm `OPERATIONS`'s current (empty) permission set, since Chunk 9 gives it its first real grants.
4. Inspect Search's `adapters/verification/verification_provider.py` (`NullVerificationProvider`) and the outbound port it implements — Chunk 10 replaces it.
5. Inspect Housing's `GetProperty` use case (for resolving a property's `provider_id`, needed for ownership checks) and Profile's `GetCurrentUserProfile` (for confirming a caller is a Scout before letting them submit provider verification).
6. Create the module's empty structure:
```
src/camp_match/modules/verification/__init__.py
src/camp_match/modules/verification/domain/__init__.py
src/camp_match/modules/verification/domain/value_objects.py
src/camp_match/modules/verification/domain/entities.py
src/camp_match/modules/verification/domain/state_machine.py
src/camp_match/modules/verification/domain/requirements.py
src/camp_match/modules/verification/application/__init__.py
src/camp_match/modules/verification/application/errors.py
src/camp_match/modules/verification/application/ports/__init__.py
src/camp_match/modules/verification/application/ports/inbound.py
src/camp_match/modules/verification/application/ports/outbound.py
src/camp_match/modules/verification/application/use_cases/__init__.py
src/camp_match/modules/verification/adapters/__init__.py
src/camp_match/modules/verification/adapters/persistence/__init__.py
src/camp_match/modules/verification/adapters/housing/__init__.py
src/camp_match/modules/verification/adapters/profile/__init__.py
src/camp_match/modules/verification/adapters/api/__init__.py
tests/unit/verification/__init__.py
tests/unit/verification/domain/__init__.py
tests/unit/verification/application/__init__.py
tests/integration/verification/__init__.py
tests/api/verification/__init__.py
```
`domain/state_machine.py` and `domain/requirements.py` each get their own file — the state graph and the per-target-type requirement mapping are this module's two real pieces of non-trivial domain logic, same reasoning as Security's `policy.py` and Search's `ranking.py`.

**Acceptance criteria:** written confirmation of steps 1–5; all files from step 6 importable.

---

## CHUNK 2 — DOMAIN MODEL
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/value_objects.py`, `domain/entities.py`.

**`value_objects.py`:**
- **`VerificationTargetType`** (enum) — `PROVIDER`, `PROPERTY` (ADR-071).
- **`VerificationStatus`** (enum) — `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `INSPECTION_REQUIRED`, `INSPECTION_IN_PROGRESS`, `INSPECTION_COMPLETED`, `DECISION_PENDING`, `VERIFIED`, `REJECTED`, `REVOKED`, `CANCELLED`. **No `EXPIRED` member** — deliberately, per ADR-073; expiration is computed, never stored (Chunk 3 covers exactly how).
- **`EvidenceType`** (enum) — `IDENTITY_DOCUMENT`, `PROPERTY_DOCUMENT`, `INSPECTION_PHOTO`, `LOCATION_EVIDENCE`, `OTHER`.
- **`EvidenceReviewStatus`** (enum) — `PENDING`, `ACCEPTED`, `REJECTED`.
- **`InspectionStatus`** (enum) — `ASSIGNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`.
- **`InspectionResult`** (enum) — `PASSED`, `FAILED`, `PARTIALLY_PASSED`.
- **`ChecklistItem`** (enum, 7 values — the whole MVP checklist, Part 16) — `ACCOMMODATION_EXISTS`, `LOCATION_MATCHES_CLAIM`, `ELECTRICITY_WORKING`, `WATER_AVAILABLE`, `SECURITY_ADEQUATE`, `AMENITIES_MATCH_LISTING`, `GENERAL_CONDITION_ACCEPTABLE`.
- **`DecisionOutcome`** (enum) — `VERIFIED`, `REJECTED`. (No `CONDITIONALLY_VERIFIED`/`REQUIRES_MORE_EVIDENCE` — explicitly future per Part 19, not built now.)

**`entities.py`:**
- **`VerificationCase`** — `id`, `target_type`, `target_id` (`EntityId`, permanent), `status`, `submitted_by` (`EntityId`, permanent), `previous_case_id` (`EntityId | None`, permanent — links a resubmission to what it's replacing), `expires_at` (`datetime | None`, set only on approval), `revoked_at`/`revoked_by`/`revocation_reason` (all nullable, set only by revocation), `created_at`/`updated_at`. Exposes a read-only `is_currently_valid` property: `status == VERIFIED and (expires_at is None or expires_at > now)` and `revoked_at is None` — this is the one thing every consumer of this entity actually wants, computed once, correctly, in one place rather than re-derived by every caller.
- **`Evidence`** — `id`, `verification_case_id` (permanent), `evidence_type`, `media_reference` (str — see Finding 1), `submitted_by` (`EntityId`, permanent), `source_description` (free text), `captured_at` (`datetime | None`), `inspection_id` (`EntityId | None`, permanent), `review_status`, `review_notes`, `created_at` — **`media_reference`, `submitted_by`, `evidence_type`, and `created_at` are immutable after construction; only `review_status`/`review_notes` can ever change, and only before the parent case reaches a terminal decision** (ADR / Part 12 — enforce this as a method precondition, not just a convention).
- **`Inspection`** — `id`, `verification_case_id` (permanent), `inspector_id` (`EntityId`, permanent), `assigned_by` (`EntityId`, permanent), `status`, `assigned_at`, `started_at`/`completed_at` (nullable), `result` (nullable until completed), `notes`.
- **`InspectionObservation`** — `id`, `inspection_id` (permanent), `item` (`ChecklistItem`, permanent — one row per item, enforce no duplicates within one inspection), `passed` (bool), `notes` (nullable), `created_at`.
- **`VerificationDecision`** — `id`, `verification_case_id` (permanent, one per case), `outcome`, `reason` (required, non-empty — **required for both outcomes, not just rejection**, per Part 3/21's "why was this verified" requirement), `decided_by` (permanent), `decided_at`.

**Tests you must write:** `tests/unit/verification/domain/test_verification_case.py` (`is_currently_valid` is true only for `VERIFIED` + not expired + not revoked, tested against each of those three conditions individually) and `tests/unit/verification/domain/test_evidence.py` (review status changes before a decision succeed; the same attempt after the parent case's decision is recorded raises).

**Acceptance criteria:** new tests pass; no import beyond stdlib + shared-kernel `EntityId`.


---

## CHUNK 3 — VERIFICATION STATE MACHINE
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/state_machine.py`.

**The legal transition table, exactly — implement as an explicit lookup, not scattered `if` statements:**

| From | To | Guard |
|---|---|---|
| `DRAFT` | `SUBMITTED` | — |
| `DRAFT` | `CANCELLED` | — |
| `SUBMITTED` | `UNDER_REVIEW` | — |
| `UNDER_REVIEW` | `INSPECTION_REQUIRED` | only if `target_type == PROPERTY` |
| `UNDER_REVIEW` | `DECISION_PENDING` | only if `target_type == PROVIDER`, **or** `target_type == PROPERTY` and the reviewer explicitly judges no inspection is needed |
| `INSPECTION_REQUIRED` | `INSPECTION_IN_PROGRESS` | an `Inspection` has been assigned |
| `INSPECTION_IN_PROGRESS` | `INSPECTION_COMPLETED` | the assigned `Inspection`'s status is `COMPLETED` (all 7 checklist items recorded) |
| `INSPECTION_COMPLETED` | `DECISION_PENDING` | — |
| `DECISION_PENDING` | `VERIFIED` | a `VerificationDecision` with outcome `VERIFIED` exists; decider ≠ inspector (ADR-074) |
| `DECISION_PENDING` | `REJECTED` | a `VerificationDecision` with outcome `REJECTED` exists |
| `VERIFIED` | `REVOKED` | — |

Everything not in this table is illegal, including every transition out of `REJECTED`, `REVOKED`, and `CANCELLED` — all three are terminal. Note there is **no** `VERIFIED → EXPIRED` row (ADR-073) and **no** transition back from `DECISION_PENDING` to an earlier state (ADR — kept out deliberately; re-submission after rejection is a new case, linked via `previous_case_id`, not a reopened old one).

Implement `can_transition(current: VerificationStatus, target: VerificationStatus, target_type: VerificationTargetType) -> bool` and `transition(case: VerificationCase, target: VerificationStatus) -> None` (raises `ValueError` on an illegal transition, identifying which rule was violated in the message — this matters for debugging a workflow this deep).

**Tests you must write:** `tests/unit/verification/domain/test_state_machine.py` — every row in the table above succeeds under its stated guard and fails without it (specifically: `UNDER_REVIEW → INSPECTION_REQUIRED` succeeds for a `PROPERTY` case and fails for a `PROVIDER` case); every transition NOT in the table is individually tested and rejected, not just "some invalid transition somewhere"; nothing transitions out of any of the three terminal states.

**Acceptance criteria:** new tests pass; running them alone shows one named test per table row plus one per rejected transition, not a handful of combined assertions.

---

## CHUNK 4 — REQUIREMENTS & VERIFICATION RULES
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/requirements.py`.

**Static, code-defined per target type (ADR-072) — the domain equivalent of Security's role→permission table:**

| Target type | Required evidence types | Inspection required? |
|---|---|---|
| `PROVIDER` | `IDENTITY_DOCUMENT` (at least one, `review_status == ACCEPTED`) | never |
| `PROPERTY` | `PROPERTY_DOCUMENT` (at least one, accepted) | always |

**One function, `decision_prerequisites_satisfied(case, evidence, inspection) -> tuple[bool, str | None]`** — returns whether the case is actually ready for a decision and, if not, why (a human-readable reason, since "not ready" alone isn't useful to a reviewer trying to figure out what's missing). Checks: every required evidence type has at least one `ACCEPTED` record; for `PROPERTY`, the associated `Inspection` is `COMPLETED` with a non-null `result`.

**This does not gate whether a decision use case can be *called*** — a reviewer is always allowed to reject a case that's missing requirements (rejection doesn't need prerequisites, only approval does). Approving a case that doesn't satisfy its prerequisites raises `EvidenceRequirementNotSatisfied`, with the specific missing requirement in the message.

**Tests you must write:** `tests/unit/verification/domain/test_requirements.py` — a `PROVIDER` case with an accepted identity document is ready; without one, isn't, with the correct reason string; a `PROPERTY` case with accepted property documents but an incomplete inspection isn't ready; rejection is allowed regardless of what's satisfied.

**Acceptance criteria:** new tests pass.


---

## CHUNK 5 — EVIDENCE & PROVENANCE
**[FOR YOU — GEMINI CLI]**

**Objective:** verification, not new code — Chunk 2's `Evidence` entity already carries every provenance field this chunk asks for, and its immutability rule is already enforced there. This chunk fills the gaps: the application-level rule for *how* evidence review works, and the privacy discipline around it.

**Files to create:** `application/use_cases/add_evidence.py`, `application/use_cases/review_evidence.py`.

**`AddEvidence` — steps:** look up the case; confirm it's not in a terminal state (`DRAFT` through `DECISION_PENDING` only — evidence can't be added to a case that's already been decided, even to a `VERIFIED` one, without a new case); construct a new `Evidence` record, `review_status = PENDING`; persist; log INFO (`"evidence_added"`, case id, evidence type — **never** the `media_reference` value or any detail of the evidence's content, per Part 26).

**`ReviewEvidence` — steps:** look up the evidence and its case; confirm the case isn't yet decided; set `review_status`/`review_notes`; persist; log INFO with the same restraint as above.

**Privacy discipline, stated once here, binding for every chunk in this module (Part 26):** never log a NIN, BVN, raw document content, or biometric data, under any circumstance, at any log level. Never include evidence content in an error message. The public-facing status port (Chunk 9) returns a status and a date — nothing about evidence ever crosses that boundary.

**Tests you must write:** `tests/unit/verification/application/test_add_evidence.py` and `test_review_evidence.py` (against fakes) — adding evidence to a terminal-state case is rejected; review status changes correctly; capture log output during both operations and assert no evidence-identifying string appears in it (the same log-content assertion pattern Identity used for passwords, Module 1).

**Acceptance criteria:** new tests pass, including the log-content assertion.

---

## CHUNK 6 — INSPECTION WORKFLOW
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/assign_inspector.py`, `application/use_cases/start_inspection.py`, `application/use_cases/record_inspection_observation.py`, `application/use_cases/complete_inspection.py`.

**`AssignInspector` — steps:** look up the case, confirm status is `INSPECTION_REQUIRED`; confirm the proposed inspector currently holds `VERIFICATION_INSPECT` via `AuthorizationService` (role-scoped check, no ownership context yet — nothing to own until the `Inspection` exists); create the `Inspection` (`status = ASSIGNED`); transition the case to `INSPECTION_IN_PROGRESS`; log INFO.

**`StartInspection` — steps:** look up the inspection; authorize via `VERIFICATION_INSPECT`, ownership-scoped against `inspection.inspector_id` — only the assigned inspector may start it; set `status = IN_PROGRESS`, `started_at = now`; log INFO.

**`RecordInspectionObservation` — steps:** look up the inspection; authorize the same ownership-scoped way; confirm status is `IN_PROGRESS`; reject a duplicate observation for an already-recorded `ChecklistItem` (`InspectionAlreadyCompleted` doesn't fit — raise a dedicated, honestly-named check here: reuse `InvalidVerificationTransition` for "this item was already recorded," since it's the same category of "you're trying to do this out of the correct order"); persist; log INFO.

**`CompleteInspection` — steps:** look up the inspection, authorize (ownership); confirm all 7 `ChecklistItem`s have a recorded observation — raise a clear error naming which are missing if not; compute `result` from the observations (**explicit rule, not left to the caller to guess**: all 7 passed → `PASSED`; zero passed → `FAILED`; anything in between → `PARTIALLY_PASSED`); set `status = COMPLETED`, `completed_at = now`; transition the case to `INSPECTION_COMPLETED`; log INFO with the computed result.

**Tests you must write:** one test file per use case above, against fakes — covering the happy path, the wrong-inspector rejection (a different `OPERATIONS` account, not just an unauthenticated one — this is the "inspectors cannot modify unrelated inspections" test Part 41 explicitly asks for), the incomplete-checklist rejection on `CompleteInspection`, and all three `result` outcomes from the scoring rule.

**Acceptance criteria:** new tests pass.


---

## CHUNK 7 — REVIEW, DECISION & AUDIT
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/start_review.py`, `application/use_cases/request_inspection.py`, `application/use_cases/mark_ready_for_decision.py`, `application/use_cases/approve_verification.py`, `application/use_cases/reject_verification.py`, `application/use_cases/revoke_verification.py`, `application/use_cases/record_history_event.py`.

**`StartReview`** (`SUBMITTED → UNDER_REVIEW`), **`RequestInspection`** (`UNDER_REVIEW → INSPECTION_REQUIRED`, `PROPERTY` only — the state machine's own guard from Chunk 3 rejects this for `PROVIDER`, this use case just calls `transition` and lets that guard do the real work), **`MarkReadyForDecision`** (`UNDER_REVIEW → DECISION_PENDING`, for cases that don't need inspection) — all three: look up, authorize via `VERIFICATION_REVIEW` (role-scoped, no ownership dimension — a reviewer reviews other people's cases by definition), transition, log INFO.

**`ApproveVerification` — steps:** look up the case and its inspection (if any); authorize via `VERIFICATION_REVIEW`; **enforce ADR-074**: if an inspection exists, `decided_by` must not equal `inspection.inspector_id` — raise `UnauthorizedVerificationAction` if it does, with a message naming the actual rule, not just "forbidden"; call `decision_prerequisites_satisfied` (Chunk 4) — raise `EvidenceRequirementNotSatisfied` if not ready; require a non-empty `reason`; **the concurrency-safe write (ADR-077)**: persist the decision and the case's new status in one repository call that conditionally updates the case only `WHERE status = 'DECISION_PENDING'`, checking the affected-row-count — zero rows means someone else already decided it first, raise `DecisionNotAllowed`, not a generic error; set `expires_at` (12 months from now for `PROPERTY`, 24 months for `PROVIDER` — state these exact constants plainly in the code, not as bare numbers); publish a `record_history_event` entry; log INFO.

**`RejectVerification` — steps:** same lookup/authorize/reason-required/concurrency-safe pattern, no prerequisite check (rejection never needs the case to be "ready") — no decider≠inspector rule either, since rejecting doesn't carry the same risk approving does, but document this asymmetry explicitly rather than leaving it to be noticed.

**`RevokeVerification` — steps:** look up a `VERIFIED` case (anything else raises `InvalidVerificationTransition`); authorize via `VERIFICATION_REVIEW`; require a non-empty `revocation_reason`; set `revoked_at`/`revoked_by`/`revocation_reason`, transition to `REVOKED`; log at **WARNING**, not INFO — revocation is a meaningfully different kind of event from a routine state change and deserves to stand out in the logs.

**`RecordHistoryEvent`** — a small internal helper, not exposed via any port, called by every use case above (and Chunks 5/6's use cases) at the point of every meaningful action (Part 21's list): appends one `verification_history` row (append-only — no use case anywhere in this module ever updates or deletes a history row). This is this module's audit trail — deliberately minimal, Verification-specific, not a general project-wide audit framework (Part 21's own instruction).

**Tests you must write:** one file per use case, against fakes — the concurrency guard specifically (`tests/unit/verification/application/test_approve_verification_concurrency.py`, or fold into `test_approve_verification.py`): simulate a fake repository whose conditional update reports zero affected rows and confirm `DecisionNotAllowed` is raised, not a silent success; the decider≠inspector rejection; the prerequisite-not-satisfied rejection; revocation logging at WARNING specifically (capture log level, not just message content).

**Acceptance criteria:** new tests pass, all against fakes.


---

## CHUNK 8 — APPLICATION LAYER
**[FOR YOU — GEMINI CLI]**

**Objective:** the remaining use cases — case creation/submission and every query. (Chunks 5–7 already implemented the evidence, inspection, and decision use cases in full, rather than defining them abstractly here and implementing them there — a deliberate restructuring for a module this workflow-heavy, where separating "the rule" from "the use case that enforces it" would have meant splitting nearly every file in two for no real benefit. Noted explicitly rather than silently deviating from the suggested chunk boundaries.)

**Files to create:** `application/use_cases/create_verification_case.py`, `submit_verification_case.py`, `get_verification_case.py`, `get_verification_history.py`, `get_verification_status.py`, `list_my_verification_cases.py`, `list_my_inspections.py`, `list_pending_reviews.py`.

**`CreateVerificationCase` — steps:** resolve the target's true owner — for `PROVIDER`, that's `target_id` itself (you're verifying yourself); for `PROPERTY`, look it up via `HousingProvider` (Chunk 9) to get `provider_id`; authorize via `VERIFICATION_MANAGE`, ownership-scoped against that resolved owner; confirm no other *in-flight* case exists for this exact `(target_type, target_id)` (the partial-uniqueness rule — Chunk 10's database constraint is the real guarantee, this is the fast, friendly check in front of it, same two-layer pattern as every previous module's uniqueness handling); construct in `DRAFT`; persist; record history; log INFO.

**`SubmitVerificationCase` — steps:** look up, authorize (same ownership check as creation), transition `DRAFT → SUBMITTED`, record history, log INFO.

**`GetVerificationCase` — steps:** look up; **role-scoped response shaping, not a permission gate**: the case's own owner sees their evidence and status but not internal reviewer notes; an `OPERATIONS`/`ADMIN` caller (checked via `AuthorizationService` with the role-scoped `VERIFICATION_REVIEW` permission) sees everything, including review notes; anyone else gets `Forbidden`. Implement this as two different response DTOs built from the same entity, not one DTO with fields conditionally nulled out — the same "structurally separate, not filtered at serialization time" discipline Profile used for its public/private views (Module 2).

**`GetVerificationHistory` — steps:** same visibility rule as above, returns the append-only history list.

**`GetVerificationStatus`** (ADR-076, Chunk 10 wires this to Search) **— steps:** the *public* port — takes `target_type`/`target_id`, no authorization required beyond authentication, returns `{is_verified: bool, verified_on: date | None}` — nothing else, ever, regardless of who's asking. Resolves `is_currently_valid` (Chunk 2) for the most recent case matching the target, if any (no case at all → `is_verified: False`).

**`ListMyVerificationCases`/`ListMyInspections`** — structurally self-scoped, same discipline as Profile's `/me` and Housing's `/mine` — no target parameter, always the caller's own.

**`ListPendingReviews`** — `VERIFICATION_REVIEW` required (role-scoped); returns cases in `SUBMITTED`/`UNDER_REVIEW`/`DECISION_PENDING` — the Operations queue.

**Tests you must write:** one file per use case, against fakes — the two-shape response test for `GetVerificationCase` specifically (assert the owner's response object has no `review_notes` attribute at all, not just that it's null); the public status port returning `False` for a target with no case, `True` only while genuinely current (not expired, not revoked).

**Acceptance criteria:** new tests pass, all against fakes.


---

## CHUNK 9 — PORTS & CROSS-MODULE CONTRACTS
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `application/ports/inbound.py`, `application/ports/outbound.py`.

**Inbound:** one `Protocol`/dataclass pair per use case from Chunks 5–8, plus the public `GetVerificationStatus` port other modules will actually consume in-process.

**Outbound:**
- **`VerificationCaseRepository`**, **`EvidenceRepository`**, **`InspectionRepository`**, **`DecisionRepository`**, **`HistoryRepository`** — five repositories, one per aggregate/table from Chunk 11's schema, each with the methods its use cases actually need (`add`, `get_by_id`, `update`, and the specific lookups above — no generic CRUD interface, same discipline as every previous module).
- **`HousingProvider`** — one method, `get_property_owner(property_id: EntityId) -> EntityId | None` — the smallest possible contract, deliberately narrower than Search's `HousingProvider` from Module 6, since this module needs exactly one fact from Housing, not a rich listing projection.
- **`ProfileProvider`** — `is_scout(identity_id: EntityId) -> bool`.
- Reused: shared-kernel `Clock`, `EntityId`, `Page`/`PageRequest`, `UnitOfWork`.
- **No `IdentityVerificationPort`** (Finding 2/ADR-070) — confirmed here, not silently omitted.
- **No media/file port** — `media_reference` is a plain string field, not a port-mediated capability (Finding 1/ADR-069).

**Acceptance criteria:** `poetry run mypy` clean; every port above exists with a matching signature.

---

## CHUNK 10 — PERSISTENCE & ADAPTERS
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/persistence/models.py`, `adapters/persistence/repository.py` (all five repositories, one file — they're small enough and share enough infrastructure that splitting them further would just be ceremony), `adapters/housing/housing_provider.py`, `adapters/profile/profile_provider.py`.

**`verification_cases`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | primary key |
| `target_type` | text | not null, `CHECK` restricted |
| `target_id` | UUID | not null, **no foreign key** — cross-module reference to either an identity or a property |
| `status` | text | not null, `CHECK` restricted — indexed |
| `previous_case_id` | UUID | nullable, self-referencing foreign key |
| `submitted_by` | UUID | not null, no foreign key |
| `expires_at` | timestamptz | nullable |
| `revoked_at`, `revoked_by`, `revocation_reason` | timestamptz / UUID / text | all nullable |
| `created_at`/`updated_at` | timestamptz | server defaults |

**Partial unique index** on `(target_type, target_id)` `WHERE status IN ('DRAFT','SUBMITTED','UNDER_REVIEW','INSPECTION_REQUIRED','INSPECTION_IN_PROGRESS','INSPECTION_COMPLETED','DECISION_PENDING')` — at most one in-flight case per target, database-enforced, not just application-checked (same partial-index technique Housing used for `is_main_campus`, Module 5).

**`verification_evidence`** — `id`, `verification_case_id` (FK), `evidence_type`, `media_reference` (text), `submitted_by` (UUID, no FK), `source_description` (text, nullable), `captured_at` (timestamptz, nullable), `inspection_id` (UUID, nullable FK), `review_status`, `review_notes` (text, nullable), `created_at`.

**`inspections`** — `id`, `verification_case_id` (FK), `inspector_id` (UUID, no FK), `assigned_by` (UUID, no FK), `status`, `assigned_at`, `started_at`/`completed_at` (nullable), `result` (nullable), `notes` (text, nullable).

**`inspection_observations`** — `id`, `inspection_id` (FK), `item`, `passed` (boolean), `notes` (text, nullable), `created_at`. Unique constraint on `(inspection_id, item)`.

**`verification_decisions`** — `id`, `verification_case_id` (FK, **unique** — one decision per case), `outcome`, `reason` (text, not null), `decided_by` (UUID, no FK), `decided_at`.

**`verification_history`** — `id`, `verification_case_id` (FK), `event_type` (text), `actor_id` (UUID, nullable), `occurred_at`, `details` (text, nullable). **Append-only** — no repository method for updating or deleting a row here, ever.

**The concurrency-safe decision write (ADR-077, Chunk 7):** `DecisionRepository.record_decision` performs the insert into `verification_decisions` and the case-status update in one transaction, with the status update conditioned on `WHERE status = 'DECISION_PENDING'` — return whether the update actually matched a row; the calling use case (Chunk 7) is what turns "zero rows" into `DecisionNotAllowed`.

**Migration:** `poetry run alembic revision --autogenerate -m "add verification tables"`, read closely before applying — six tables, several `CHECK` constraints, one partial index, worth extra care.

**Tests you must write:** `tests/integration/verification/test_repositories.py` (marked `integration`) — CRUD across all five repositories; the partial unique index genuinely rejects a second in-flight case for the same target (bypass the application layer deliberately to prove it, same discipline as every previous module's constraint tests); the concurrency-safe decision write, tested exactly like Housing's reservation race (Module 5) — two simulated concurrent decision attempts on one case, exactly one succeeds.

**Acceptance criteria:** new tests pass against local Termux Postgres; migration applies cleanly; the decision-concurrency test passes reliably across repeated runs, same bar as Housing's reservation test.


---

## CHUNK 11 — FASTAPI & AUTHORIZATION
**[FOR YOU — GEMINI CLI]**

**Objective:** wire everything to HTTP, and give Security's three new permissions real grants — including `OPERATIONS`'s first ones ever (ADR-075).

**Files to modify (Security, using its own documented extension recipe — Module 3, Section 5):** `modules/security/domain/value_objects.py` (add `VERIFICATION_MANAGE`, `VERIFICATION_INSPECT`, `VERIFICATION_REVIEW` to `Permission`, the first two declared **ownership-scoped**, the third **role-scoped only**), `modules/security/domain/policy.py` (`VERIFICATION_MANAGE` → `SCOUT`, `ADMIN`; `VERIFICATION_INSPECT` → `OPERATIONS`, `ADMIN`; `VERIFICATION_REVIEW` → `OPERATIONS`, `ADMIN`).

**Prohibition:** exactly those two files, exactly the permission-registration lines.

**Files to create:** `adapters/api/schemas.py`, `adapters/api/router.py`, `adapters/api/dependencies.py`.
**Files to modify:** `app.py`.

**Seventeen endpoints, all under `/api/v1/verification`:**

| Method | Path | Permission | Ownership check |
|---|---|---|---|
| POST | `/cases` | `VERIFICATION_MANAGE` | target's resolved owner |
| POST | `/cases/{id}/submit` | `VERIFICATION_MANAGE` | case's `submitted_by` |
| POST | `/cases/{id}/evidence` | `VERIFICATION_MANAGE` | case's `submitted_by` |
| GET | `/cases/{id}` | authenticated | role-scoped shaping (Chunk 8), not a gate |
| GET | `/cases/{id}/history` | authenticated | same |
| GET | `/cases/mine` | authenticated | structurally self-scoped |
| POST | `/cases/{id}/start-review` | `VERIFICATION_REVIEW` | — |
| POST | `/cases/{id}/request-inspection` | `VERIFICATION_REVIEW` | — |
| POST | `/cases/{id}/assign-inspector` | `VERIFICATION_REVIEW` | — |
| POST | `/cases/{id}/ready-for-decision` | `VERIFICATION_REVIEW` | — |
| POST | `/cases/{id}/approve` | `VERIFICATION_REVIEW` | — |
| POST | `/cases/{id}/reject` | `VERIFICATION_REVIEW` | — |
| POST | `/cases/{id}/revoke` | `VERIFICATION_REVIEW` | — |
| GET | `/reviews/pending` | `VERIFICATION_REVIEW` | — |
| GET | `/inspections/mine` | authenticated | structurally self-scoped |
| POST | `/inspections/{id}/start` | `VERIFICATION_INSPECT` | `inspection.inspector_id` |
| POST | `/inspections/{id}/observations` | `VERIFICATION_INSPECT` | `inspection.inspector_id` |
| POST | `/inspections/{id}/complete` | `VERIFICATION_INSPECT` | `inspection.inspector_id` |

Plus the one public endpoint, outside `/verification` since it's meant for general consumption: `GET /api/v1/verification-status/{target_type}/{target_id}` — authenticated only, no permission, returns the public `{is_verified, verified_on}` shape from `GetVerificationStatus`.

**Prohibition, same as every module before this one:** no business logic in `router.py`.

**Tests you must write:** placeholder only — real API tests arrive in Chunk 12.

**Acceptance criteria:** the app starts; each endpoint enforces the permission/ownership combination in its row above.

---

## CHUNK 12 — TESTING, DOCUMENTATION & AI STATE
**[FOR YOU — GEMINI CLI]**

**Files to create:** `tests/api/verification/test_provider_flow.py`, `test_property_flow.py`, `test_authorization.py`, `test_search_integration.py`; extend the import-linter contract list.

**`test_provider_flow.py`:** a Scout creates a `PROVIDER` case → submits → adds an identity-document evidence record → an `OPERATIONS` account starts review, marks ready-for-decision (no inspection), approves with a reason → confirm `GET /verification-status/PROVIDER/{id}` now shows `is_verified: true`.

**`test_property_flow.py`:** a Scout creates a `PROPERTY` case for one of their properties → submits → adds evidence → an `OPERATIONS` account reviews, requests inspection → **a different** `OPERATIONS` account is assigned as inspector, starts, records all 7 observations, completes → confirm the case auto-advanced to `INSPECTION_COMPLETED` → the **reviewing** account (not the inspector) approves → confirm `is_verified: true`. Also: the inspector attempting to approve their own inspection's case is rejected (ADR-074, proven end to end); a second concurrent approval attempt on an already-decided case is rejected, not silently accepted.

**`test_authorization.py`:** a Student can't create any verification case; a Scout can't create one for a property they don't own; an inspector can't touch an inspection assigned to someone else; a non-`OPERATIONS`/`ADMIN` account can't review anything.

**`test_search_integration.py`:** after a `PROPERTY` case is approved, confirm a listing on that property now shows `verification_state: "VERIFIED"` in `GET /search` results (Chunk 10 of the Search Discovery Guide below covers wiring this) — the actual end-to-end proof Module 6's stub is genuinely retired.

**Extend import-linter:** `camp_match.modules.verification.domain` and `.application` must not import `fastapi` or `sqlalchemy`; nothing outside the module may import its `adapters.*` directly; the Housing/Profile adapters may import only those modules' `application.ports`.

**Documentation:** write `docs/modules/verification.md` per the Module Documentation Requirements below. Update `AI_state/` per the AI State Requirements below, using the standard `CURRENT_TASK.md` status-block format.

**Cross-module integration required in this chunk — replacing Search's stub (ADR-076):**
**Files to modify (Search, Module 6):** `adapters/verification/verification_provider.py` — replace `NullVerificationProvider`'s body with `InProcessVerificationProvider`, calling this module's `GetVerificationStatus` once per distinct `property_id` in the candidate batch (not once per listing — same N+1 discipline as every batched lookup in this project), mapping the result to Search's own `VerificationState.VERIFIED`/`UNVERIFIED`. Confirm Search's full pre-existing test suite still passes, and that the specific stub-returns-UNKNOWN tests from Module 6 are updated to reflect the new real behavior rather than left asserting the old placeholder.

**Acceptance criteria:** every scenario above passes; Search's suite passes with the stub genuinely replaced, not just left in place alongside unused new code.

---

## CHUNK 13 — FINAL INTEGRATION & VERIFICATION
**[FOR YOU — GEMINI CLI]**

Run the full seven-module suite from a clean state. Confirm Security's and Search's suites specifically are unaffected apart from the documented, intentional additions (three permissions; one stub replaced). Confirm every item in the Completion Checklist below.


---

## FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**Applies everywhere in this module:** evidence content (documents, photos) is never returned through any Verification endpoint — only metadata about it (type, status, when it was submitted). Reviewer notes are never visible to the case owner.

### POST /api/v1/verification/cases
**Authorization:** must own the target (yourself, for `PROVIDER`; the property, for `PROPERTY`).
**Request body:** `target_type` (`PROVIDER`/`PROPERTY`), `target_id`.
**Success — 201**, `status: "DRAFT"`. **Errors:** 409 if an in-flight case already exists for this target; 403 if you don't own it.

### POST /api/v1/verification/cases/{id}/submit, /evidence
Standard owner-only actions on a `DRAFT`/in-progress case. Evidence request body: `evidence_type`, `media_reference`, `source_description` (optional), `captured_at` (optional).

### GET /api/v1/verification/cases/{id}, /history, /mine
Owner sees their own case with evidence and status, no reviewer notes. Reviewers/admins see everything. `/mine` is always your own, no id needed.

### POST /api/v1/verification/cases/{id}/start-review, /request-inspection, /ready-for-decision, /assign-inspector, /approve, /reject, /revoke
Reviewer/admin only. `approve`/`reject`/`revoke` all require a `reason` (non-empty string) in the body. `assign-inspector` requires `inspector_id`.

### GET /api/v1/verification/reviews/pending
Reviewer/admin only — the review queue.

### GET /api/v1/verification/inspections/mine, POST .../start, /observations, /complete
Inspector-only, always scoped to the caller's own assignments. `observations` body: `item`, `passed`, `notes` (optional) — call once per checklist item.

### GET /api/v1/verification-status/{target_type}/{target_id}
**Authentication:** required. **Authorization:** none — this is the one genuinely public-facing endpoint in the module.
**Success — 200:** `{ "is_verified": bool, "verified_on": date | null }`. Nothing else, ever.
**Frontend notes:** this is what a "Verified" badge should be built from — never infer verification from any other endpoint's response shape.

---

## MANUAL TESTING GUIDE [FOR NSISONG]

**Preconditions:** `scripts/db_start.sh` running; the app running; a Scout with a property (Module 5), a Student account, and two accounts holding `OPERATIONS` (assigned the same direct-database way Security's own guide describes, Module 3) — you need two so one can review and a different one can inspect.

1. **Provider verification, the fast path:** as the Scout, `POST /verification/cases` with `target_type: "PROVIDER"`, your own identity id. Submit it. Add an `IDENTITY_DOCUMENT` evidence record. As Operations Account A: start review, mark ready-for-decision, approve with a reason.
2. **Confirm it's live:** `GET /verification-status/PROVIDER/{your identity id}` — expect `is_verified: true`.
3. **Property verification, the full path:** create a `PROPERTY` case for the Scout's property, submit, add a `PROPERTY_DOCUMENT`. As Operations Account A: start review, request inspection, assign Operations Account **B** as inspector.
4. **As Account B:** start the inspection, record all 7 checklist observations, complete it.
5. **As Account A (not B):** approve, with a reason. Confirm success.
6. **The inspector/decider rule:** repeat steps 3–4 with a fresh property, but this time have Account **B** (the inspector) attempt the approval themselves. Expect `403`.
7. **Double-decision race:** with a case sitting in `DECISION_PENDING`, have two requests attempt to approve/reject it as close together as you can manage. Confirm exactly one succeeds.
8. **Search integration:** after step 5's property is verified, `GET /search` for a listing on that property — confirm `verification_state: "VERIFIED"` appears where it previously would have shown `UNKNOWN`.
9. **Boundary check:** as the Student, attempt step 1. Expect `403`.

**Failure interpretation:** step 6 succeeding would be a real trust-integrity failure, not a cosmetic bug — the whole point of separating inspection from decision is that one person can't do both, and if that's not actually enforced, the audit trail's credibility is compromised. Treat it as blocking. Step 7 failing (more than one decision recorded) is the same severity class as Housing's double-booking bug.

---

## AUTOMATED TESTING GUIDE [FOR NSISONG]

- Just Verification: `poetry run pytest tests/unit/verification tests/integration/verification tests/api/verification`
- Domain only: `poetry run pytest tests/unit/verification -v`
- The concurrency and inspector/decider tests specifically: `poetry run pytest tests/api/verification/test_property_flow.py -v`
- Full verification: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`
- After this module, re-run Security's and Search's suites in isolation to confirm both are unaffected apart from the documented, intentional changes (three permissions; the stub replacement).


---

## MODULE DOCUMENTATION REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 12]

Write `docs/modules/verification.md`. Cover: purpose/ownership/non-ownership (this document's Architectural Interpretation, condensed, including all three Findings — a future reader should understand *why* there's no media port and no KYC port, not just that there isn't one); the domain model; the full state machine table from Chunk 3, verbatim; the static requirements table from Chunk 4; the evidence provenance/immutability model; the inspection workflow and the exact checklist scoring rule; the decision workflow, the inspector/decider separation rule, and the concurrency-safe write; the authorization table from Chunk 11 in full; every cross-module contract, including the one this module *satisfies* for Search (point back to ADR-076); known limitations, explicitly listed: no media storage (Finding 1, with the recommendation), no automated KYC (Finding 2, and why that's correct not incomplete), no `EXPIRED` state (computed instead — explain this so nobody "fixes" it into a stored transition later), `CONDITIONALLY_VERIFIED`/`REQUIRES_MORE_EVIDENCE` not implemented.

## AI STATE REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 12]

Update `CURRENT_STATE.md`, `PROGRESS.md`, `COMPLETED_WORK.md`, `ARCHITECTURE_STATE.md` (note this is the first module with a genuine multi-actor authorization workflow — three permissions, two of them ownership-scoped, one role-scoped only), `DATABASE_STATE.md`, `API_STATE.md`, `TEST_STATE.md`, `DECISIONS.md` (append ADR-069–077), `SESSION_HANDOFF.md`. Security's state should note `OPERATIONS`'s first real permissions. Search's state should note its stub was replaced, not just extended. Use the standard `CURRENT_TASK.md` status-block format.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] Every transition in Chunk 3's table works; every transition outside it is rejected, individually verified, not sampled.
- [ ] The one-in-flight-case-per-target rule is enforced at the database level, not just the application layer.
- [ ] Evidence is immutable in every field except review status/notes, and even those freeze once a decision is recorded — verified by attempting a change after decision and confirming rejection.
- [ ] The inspection checklist requires all 7 items before completion; the `PASSED`/`FAILED`/`PARTIALLY_PASSED` scoring rule matches the specification exactly.
- [ ] **The inspector/decider separation is enforced and proven end to end** — this is the module's most important trust property.
- [ ] **The concurrent-decision race is prevented and proven reliably across repeated runs** — same severity as Housing's double-booking test.
- [ ] Both new roles' first-ever real permissions (`OPERATIONS`'s two, `SCOUT`'s one addition) work correctly and don't leak beyond their intended scope.
- [ ] Search's stub is genuinely replaced — a real verified property shows up as verified in real search results.
- [ ] No evidence content, NIN/BVN, or biometric data appears in any log line, anywhere, verified by the specific log-content test from Chunk 5.
- [ ] The public status endpoint returns only `is_verified`/`verified_on` — nothing else, checked by inspecting the actual response body, not just the schema.
- [ ] No cross-module database access in any direction.
- [ ] Unit, integration, API, and architecture tests all pass — all seven modules together.
- [ ] `docs/modules/verification.md` exists and covers everything above, including all three Findings with their reasoning intact.
- [ ] All `AI_state/` files updated, including Security's and Search's.
- [ ] Known limitations documented plainly — especially the media-storage gap and its recommendation, so it doesn't get silently rediscovered a fourth time.

