# CAMP MATCH — MODULE 13: TRUST & SAFETY
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Trust & Safety Module handoff**

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** You do not copy chunks or parts. Gemini reads the complete document, then works through the chunks **in order, one at a time**. When a chunk is finished, Gemini stops and gives you a Completion Report; you check it and reply **"Proceed to Chunk N"** (or send corrections). Parts marked **[FOR NSISONG]** are for you — decisions, frontend documentation, the test-coverage matrix — and Gemini reads them only for context.

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

You are the implementation agent for this module. You have been given the **complete** specification in this one file.

1. **Read the entire file before doing anything.** Parts marked **[FOR NSISONG]** are for the human: read them for context and rationale, but they are not instructions to you. **The Design Specification (Part C) is the reference you must internalize fully** — every chunk points back to it ("Part C5", "ADR-133" and so on mean sections of this file). **Part D is your work**, in numbered chunks. **Part G (Manual Testing Guide)** at the end of this file is the source material for the manual-testing document you write in Chunk 19.
2. **Your first action is Chunk 1.** It is inspection and scaffolding and writes no behavior. Do not write any other code first.
3. **Work one chunk at a time, in order.** Do not start a chunk until Nsisong has replied "Proceed to Chunk N". Never combine, reorder, skip, or work ahead — not even small "preparatory" edits for a later chunk.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; every file created or changed; every command you ran with its **real** output; each acceptance criterion marked pass or fail; any deviation, surprise, or open question. Claim nothing you did not verify.
5. **If anything blocks you — a failing acceptance item, the repository contradicting this file, two parts of this file disagreeing, or a decision this file does not make — stop and report it.** Do not choose for yourself, skip a test, weaken a test, or work around it.
6. The Standing Instructions in `AI_instructions/` apply to everything. Change only the files a chunk names (plus anything that chunk's touch map allows). Do not modify other modules otherwise.

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

The Chief Engineer's handoff listed 15 chunks. This document delivers **20**. The reason is not the module itself — it is that Trust & Safety can't do its job without four small, reviewed amendments to modules that are already built (Security, Housing, Messaging, Notification), and each amendment is its own chunk with its own gate (Findings 2–5). Where a handoff chunk was split or reshaped, it is noted where it happens; the mapping is in Part E.

---

## PART A — FINDINGS [FOR NSISONG]

Trust & Safety owns *reports, investigation, decisions, and the coordination of enforcement*; every other module stays the authority over its own resources. That sentence from the handoff is the whole design, and it has a hard consequence: every enforcement action has to land in a module that is **willing and able to apply it**. I checked each against the 18 specifications behind your code. Nine real findings, all before any implementation content.

### FINDING 1 — what already exists, and what T&S can lean on
- **Identity** already has `DisableAccount` / `ReactivateAccount` as real, tested use cases (Module 1), exposed over HTTP by Module 3's admin endpoint. They contain **no authorization of their own** — the caller does it. T&S can use them as-is.
- **Messaging** was built with a deliberate seam for exactly this module: its `CommunicationRestrictionProvider` port, backed today only by Identity account status. It also has **no administrative way to read conversations** (ADR-128) — on purpose.
- **Notification** exists (Module 12) and supports six events. None are safety events.
- **Verification** gives the precedent for two things this module needs: an append-only **history** table written in the same transaction as a state change, and a **separation-of-duties** rule (the inspector can't be the decider).
- **Not present:** a shared audit module, a shared rate limiter, an Admin & Operations module, any safety role or permission.

### FINDING 2 — Security has no safety roles, so permissions must be designed deliberately
Security's roles are `STUDENT`, `SCOUT` (derived from Profile), and `ADMIN`, `OPERATIONS` (assigned and stored). `ADMIN`'s only special power is bypassing *ownership* matching (ADR-041); on role-scoped permissions it holds exactly what the policy table grants. That is useful: **ADMIN does not automatically get safety access** (the handoff's explicit requirement). I add six permissions with explicit grants — see ADR-151 — and split duties: `OPERATIONS` investigates, `ADMIN` approves high-impact enforcement, and no one approves what they proposed. This is a Security amendment (two small files, the documented recipe), with a product decision for you below.

### FINDING 3 — Housing has no safety hold, and without one a listing "suspension" can be undone by the listing's owner
The only existing way to take a listing down is `UnpublishListing`/`ArchiveListing`, which the **owner** can reverse by republishing. A scammer who has been caught could simply republish. The handoff says Housing applies "the supported listing-state change through its public contract" — there isn't a supported one that survives its owner. So Housing needs a small amendment: a new `SUSPENDED` listing state that only a safety use case can enter or leave, which the owner cannot touch (ADR-154). Search, Booking and Messaging already require `PUBLISHED`, so they are unaffected.

### FINDING 4 — Messaging can't serve evidence and has nowhere to store a restriction
- **Evidence.** The handoff says to retrieve message content for an investigator "through an appropriate access-controlled contract." No such contract exists, and the obvious one — an admin message reader — is precisely what Messaging's ADR-128 forbids. The design that respects both: when a **participant** reports messages, T&S asks Messaging, *as that participant*, for just the reported messages (a new participant-scoped lookup, no admin power), and stores a **frozen, hashed snapshot of only those messages**, restricted to authorized reviewers and audited on every view. The reporter has legitimately shared what they could already see; nothing else about the conversation is exposed. **This is a privacy-sensitive choice — decision 3 below.**
- **Restriction.** Messaging must own and enforce its own restriction state ("Messaging and other modules enforce their own rules," handoff 9.2). Today it has none, so it gets a small `messaging_restrictions` table and two use cases, and its existing restriction seam gains a second source (ADR-155). This keeps the dependency one-way (T&S → Messaging) and avoids a Messaging ↔ T&S cycle.

### FINDING 5 — Notification must learn four safety facts, and T&S — not Notification — must decide who may be told
Who is allowed to hear what about a case (reporter vs reported user) is safety policy; Notification can't know it. So T&S publishes one event naming the **recipient** and a **coarse kind**, and Notification (amended, per the Module 12 rulebook) renders fixed, non-identifying text. No case ids, reporter identities, notes, or decisions ever reach it (ADR-157). Tier-2 reliability applies, as for Booking and Verification.

### FINDING 6 — Payment & Escrow has no inbound contract for safety, and shouldn't
The handoff is emphatic that T&S never touches payments, and Payment has no safety-hold or dispute-intake port. The honest MVP: a payment-related concern is investigated like any other, and its outcome is recorded as a `REFERRED` decision (recorded rationale, no downstream call). Any financial action stays a manual, human step inside Payment's own workflow. **Payment is untouched** (ADR-153).

### FINDING 7 — "who is the accused" must never come from the client
If a report could name any user id, the system would leak which ids exist and let anyone flood someone with reports. So a report names a **resource** the reporter can legitimately see — a listing, a booking they are party to, or a conversation they are in — and T&S **derives** the accountable user from that resource through the owning module. Free-form "report this user" and anonymous reports are not supported (ADR-145). User-level reports (e.g. impersonation seen only on a public profile) are a named deferral; today they are reported through the listing, booking or message that exposes them.

### FINDING 8 — enforcement is a distributed operation, so "applied" can only mean "the owner confirmed it"
A local database transaction cannot make Identity's, Housing's or Messaging's change atomic with T&S's own record. The design is therefore a small durable state machine: an action is `APPROVED` (authorized, not yet effective), becomes `APPLIED` **only** when the owning module's use case returns success, and is retried by a worker with bounded backoff if it fails. Every downstream call carries the action's id as an idempotency reference, so "the downstream succeeded but we crashed before recording it" is recovered by simply retrying (ADR-152).

### FINDING 9 — a handful of handoff items don't apply yet, and I won't invent them
- **Event consumption:** the handoff allows T&S to consume other modules' events "only if necessary for approved workflows." None is — reports are explicit user actions. **T&S consumes nothing.** The handoff's duplicate-event tests are satisfied by the report idempotency key and enforcement idempotency instead, and I say so.
- **Admin & Operations** doesn't exist: reviewers get a deliberately minimal set of API routes, not a dashboard.
- **Appeals, investigator-attached evidence, file evidence, retention/purge** are deferred, with the data model left extensible (ADR-160). File evidence needs Media/File to gain a safety purpose and hits the same upload-then-attach design problem as Messaging's attachments.

Chunk 1 verifies everything here against the actual repository — including that Modules 11 and 12 were built as specified — and reports differences before anything is built.

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-144 … ADR-161)
Continuing the log from Notification (129–143).

| ADR | Decision | Why |
|---|---|---|
| 144 | Trust & Safety is Module 13. Reporter routes: `/api/v1/safety/reports…`. **All reviewer and approver routes live under a separate `/api/v1/safety/review/…` namespace** | The handoff: never expose investigator functions through a route meant for ordinary users. A separate namespace makes that visible in the route table and testable. |
| 145 | **Reports are allegations about a resource, never about a typed-in user.** Subject types: `LISTING`, `BOOKING`, `CONVERSATION` (with 1–5 selected message ids). The reporter must be able to see the resource through its owning module. **The accountable user is derived** (listing → its owner; booking → the other party; conversation → the sender of the reported messages, who must be the other participant). Authentication is required; **no anonymous reports** | Finding 7. Also the handoff's "do not accept arbitrary resource identifiers" and "do not make reporter identity optional everywhere." |
| 146 | **Evidence is captured at intake and immutable:** `MESSAGE_SNAPSHOT` (the selected messages only, fetched through Messaging's new participant-scoped lookup *as the reporter*, with a SHA-256 of the snapshot, classed `RESTRICTED`) and `RESOURCE_REFERENCE` (the validated listing/booking, classed `INTERNAL`). Investigator-attached references and file evidence are **deferred** | Finding 4. Reconciles "evidence for investigators" with Messaging's no-admin-reading rule, and records provenance (who, when, via which contract). |
| 147 | **Intake creates only a report** (`RECEIVED`). A reviewer then **opens a case from it or links it to an existing case** — both authorized and audited, never automatic. Other reports on the same subject are shown as a count hint only | Handoff 5.2 and 7.4: reports aren't convictions, and cases must not be auto-merged. |
| 148 | **Case lifecycle** is the handoff's seven states (`OPEN`, `TRIAGED`, `IN_REVIEW`, `AWAITING_INFORMATION`, `ESCALATED`, `RESOLVED`, `CLOSED`) with the transition table in C6. Every change is a **conditional update on the case `version`**; a lost race is `409 case_state_changed`. A case has a `cycle` counter (starts at 1, incremented on reopen); the database allows **at most one final decision per cycle** (partial unique index) | Handoff 7.1 and 16.2.10: invalid or racing changes cannot silently overwrite each other. |
| 149 | **Append-only records, enforced by the database.** Notes, decisions, evidence and case history are protected by triggers that reject `UPDATE` and `DELETE`. Corrections are *new* rows referencing the original | Handoff 5.4 and 15.3: "attempts to modify or erase audit history." A trigger holds even if application code is wrong. |
| 150 | **Allegation → observation → corroborated fact → finding is structural.** The report description is the allegation. Notes have a `kind` (`OBSERVATION`, `WORKING_NOTE`, `CORROBORATED_FACT`); a `CORROBORATED_FACT` must cite ≥ 1 evidence item of the case. A `VIOLATION_ESTABLISHED` decision must cite ≥ 1 corroborated fact, plus a written rationale. **Nothing derives a finding from report counts, categories or scores** | Handoff 8.2 and 9.1. |
| 151 | **Authorization: six new role-scoped Security permissions.** `SAFETY_REPORT_SUBMIT` → `STUDENT`, `SCOUT`. `SAFETY_CASE_REVIEW` and `SAFETY_EVIDENCE_VIEW` → `OPERATIONS`. `SAFETY_ENFORCEMENT_APPROVE`, `MESSAGING_RESTRICT`, `HOUSING_SAFETY_SUSPEND` → `ADMIN`. **`ADMIN` holds no investigative or evidence permission by default.** Separation of duties: a `WARNING` is authorized by the reviewer who proposes it; **every other enforcement type needs approval by an `ADMIN` who is not the proposer**. **No actor may touch a case they are the subject or a reporter of** — they get the same `404` as an unknown case | Finding 2. Precedent: Verification's decider ≠ inspector rule. |
| 152 | **Enforcement is a durable state machine** (C7). `APPLIED` is recorded **only** after the owning module's use case returns success. Downstream calls are idempotent by `reference = action id`. A worker retries `APPROVED` and `REVERSAL_PENDING` actions with bounded exponential backoff; exhausted actions become `FAILED` / `REVERSAL_FAILED` (terminal, loud log) and an operator can requeue. A **duplicate** of a live proposal is impossible (partial unique index) | Findings 8 and handoff 9.4. |
| 153 | **Enforcement types (MVP): `WARNING`, `COMMUNICATION_RESTRICTION`, `LISTING_SUSPENSION`, `ACCOUNT_SUSPENSION`.** Targets are never free-form: the user is the case's derived subject; a listing must be a `LISTING` subject of the case's reports. **Payment concerns produce a `REFERRED` decision only — no financial action exists in this module** | Handoff 10: T&S never touches money. |
| 154 | **Housing amendment:** new listing status `SUSPENDED`; use cases `SuspendListingForSafety` (from `PUBLISHED`/`UNAVAILABLE`) and `LiftListingSuspension` (→ `UNAVAILABLE`, never auto-republished); both idempotent; the **owner cannot publish, unpublish or archive a `SUSPENDED` listing**; new permission `HOUSING_SAFETY_SUSPEND`. Existing bookings are not touched (Booking owns them) | Finding 3. |
| 155 | **Messaging amendment:** `GetMessageForParticipant` (participant-scoped read; no HTTP route; no admin path); table `messaging_restrictions`; use cases `RestrictCommunication` / `LiftCommunicationRestriction` (idempotent by `source_reference`); a restricted user cannot **send or start** conversations (reading is unaffected); the restriction is checked inside Messaging's existing restriction seam, so Messaging imports nothing from T&S; new permission `MESSAGING_RESTRICT` | Finding 4. |
| 156 | **Visibility matrix (C8).** The **reporter** sees only their own reports with a coarse status (`Received` / `Under review` / `Reviewed`) — never case, priority, decisions or enforcement. The **reported user** has **no API access to any report or case**; they hear only about an enforcement effect on them. **Reviewers** see cases and reporter ids but need the separate `SAFETY_EVIDENCE_VIEW` to read restricted evidence, and **every evidence view is audited**. **Approvers** see summary, rationale and proposals, not notes or evidence | Handoff 11.1, 15.5, 8.3. |
| 157 | **Notifications:** T&S owns who may be told; it publishes `SafetyUpdatePublished(recipient_id, kind, reference)` (six kinds). Notification (amended per the Module 12 rulebook) renders fixed text. No case id, reporter, note, decision or priority ever appears. The reported user is **never** told a report exists — only that a warning, restriction or listing suspension applies | Finding 5. |
| 158 | **Report rate limit is database-backed:** a count of the reporter's reports in a window (default 5 per 24 h), raising the shared `RateLimitedError`. Plus a **duplicate-open-report rule** (same reporter, same subject, same category, still open → `409` carrying their own report id). Independent users reporting the same listing is never blocked | Handoff 6.4. A DB count is correct across processes, unlike an in-memory limiter; a tiny overshoot under a race is accepted and documented. |
| 159 | **Audit = `safety_case_events`** (append-only), written **in the same transaction** as the state change it records, following Verification's history pattern. Covers submission, linking, triage, assignment, transitions, notes, decisions, enforcement steps, **evidence views**, reopening. No competing audit subsystem | Finding 1; handoff 5.7 and 14.1. |
| 160 | **Deferred, with extension points:** appeals (decisions carry `supersedes`/`cycle`; actions can be reversed), investigator-attached evidence, file evidence, user-level reports, retention and purge (nothing is ever deleted; no retention policy exists to implement) | Handoff 9.5, 8.4. |
| 161 | **T&S consumes no events.** It publishes `SafetyUpdatePublished` through the shared `EventBus` port with `publish_best_effort`, after commit, from application use cases only (Module 12's C12 rules). That event is tier-2: at-most-once across a crash between commit and publish | Finding 9. The shared-outbox follow-up covers it, same as Booking and Verification. |

### Four decisions I need you to confirm before Chunk 1
1. **Roles (ADR-151).** `OPERATIONS` investigates, `ADMIN` approves, `ADMIN` can't read restricted evidence, and no one approves their own proposal. Is that how your team will actually staff this? (One person *can* hold both roles; the four-eyes rule still applies to them.)
2. **Amending four finished modules.** Security (six permissions), Housing (`SUSPENDED`), Messaging (participant lookup + restrictions), Notification (safety kinds). Each is small and fully specified; without them, T&S can record reports and decisions but **cannot enforce anything**. Approve?
3. **Message evidence snapshots (ADR-146).** Reported messages — and only those — are copied into T&S, restricted and audited, so investigators can read what was reported. The alternative is references only, which leaves investigators unable to see the evidence. Confirm you accept this privacy trade-off, and that your privacy policy tells users that reported content is shared with Camp Match's safety team.
4. **Deferrals (ADR-160).** No appeals, no investigator-attached evidence, no file evidence, no user-level reports, no retention policy. Say so if any is needed for the first release.

---

## PART C — DESIGN SPECIFICATION
**[FOR YOU — GEMINI CLI — the design: internalize it fully before starting Chunk 1.]**

Where a chunk and this part appear to disagree, **stop and report** instead of choosing.

### C1. Non-negotiable rules specific to this module
1. **Trust & Safety never writes another module's data and never reads another module's tables.** It acts only through the public use cases named in this part. Other modules enforce their own rules.
2. **Applied means confirmed.** An enforcement action is marked `APPLIED` only when the owning module's use case returned success. A request being sent is not success.
3. **An allegation is never a finding.** No code path may set, infer, or default a finding, a violation, or a "substantiated" flag from a report, a report count, a category, or a priority.
4. **Application and domain layers import nothing from any other module.** Only `adapters/` do, through other modules' `application/ports` (and, for events, `application/ports/events.py`) — enforced by import-linter. **No other module may import Trust & Safety.** (Housing, Messaging and Notification gain *new* public use cases or event handlers that T&S calls or that react to T&S's event — never an import of T&S.)
5. **Never log** report descriptions, message content, note text, decision rationale, or evidence content. Log ids, enums, counts, outcomes, and short error class names.
6. **Never take reporter, subject user, actor, status, priority, or timestamps from a client.**
7. **Every state change and its history record are one transaction** (`UnitOfWork`). A change without its `safety_case_events` row — or the reverse — must be impossible.
8. **Unauthorized access to a case, report, evidence or enforcement action returns `404`**, identical to a nonexistent id, wherever revealing existence would leak (everything except a plain missing-permission `403`).

### C2. Module layout
```
src/camp_match/modules/trust_safety/
├── domain/        value_objects.py  entities.py  policies.py  events.py
├── application/
│   ├── errors.py
│   ├── ports/     inbound.py  outbound.py  events.py          # events.py = public event contract
│   ├── services/  case_access.py                              # authorization + conflict-of-interest, one place
│   └── use_cases/ submit_report.py  list_my_reports.py  get_my_report.py
│                  list_review_queue.py  open_case_from_report.py  link_report_to_case.py
│                  list_cases.py  get_case.py  triage_case.py  assign_case.py  change_case_status.py
│                  view_evidence.py  add_note.py  get_case_history.py  record_decision.py
│                  propose_enforcement.py  approve_enforcement.py  reject_enforcement.py
│                  reverse_enforcement.py  process_enforcement_queue.py  requeue_failed_enforcement.py
└── adapters/
    ├── persistence/   models.py  report_repository.py  case_repository.py  evidence_repository.py
    │                  note_repository.py  decision_repository.py  enforcement_repository.py
    ├── listing/       listing_subject_provider.py          # Housing (read)
    ├── booking/       booking_subject_provider.py          # Booking (read)
    ├── messaging/     message_evidence_provider.py         # Messaging (participant lookup)
    ├── enforcement/   account_enforcer.py  listing_enforcer.py  communication_enforcer.py
    └── api/           schemas.py  reporter_router.py  review_router.py  dependencies.py
scripts/run_safety_worker.py
```

### C3. Domain model

**Enums.** `ReportCategory`: `SCAM_OR_FRAUD`, `MISLEADING_LISTING`, `HARASSMENT`, `IMPERSONATION`, `PAYMENT_CONCERN`, `THREAT_OR_DANGER`, `OTHER`. `SubjectType`: `LISTING`, `BOOKING`, `CONVERSATION`. `ReportStatus`: `RECEIVED`, `LINKED`, `CLOSED`. `CasePriority`: `ORDINARY`, `HIGH`, `URGENT`. `CaseStatus`: the seven states in ADR-148. `EvidenceType`: `MESSAGE_SNAPSHOT`, `RESOURCE_REFERENCE`. `Confidentiality`: `RESTRICTED`, `INTERNAL`. `NoteKind`: `OBSERVATION`, `WORKING_NOTE`, `CORROBORATED_FACT`. `DecisionType`: `NO_VIOLATION_ESTABLISHED`, `INSUFFICIENT_EVIDENCE`, `VIOLATION_ESTABLISHED`, `REFERRED`, `FURTHER_INVESTIGATION_REQUIRED`. `EnforcementType`: the four in ADR-153. `EnforcementStatus`: the nine in C7. `SafetyUpdateKind`: `REPORT_RECEIVED`, `REPORT_REVIEWED`, `WARNING_ISSUED`, `COMMUNICATION_RESTRICTED`, `LISTING_SUSPENDED`, `RESTRICTION_LIFTED`.

**`Report`** — `id`, `reporter_id`, `category`, `subject_type`, `subject_id` (listing id / booking id / conversation id), `subject_user_id` (**derived**, internal), `description` (`ReportDescription`: trimmed, `safety_report_description_min`–`max` characters, else `ValueError`), `status`, `idempotency_key`, `request_fingerprint`, `created_at`. The reporter can never equal `subject_user_id`. **No attribute on `Report` can express "substantiated."**

**`EvidenceItem`** (immutable) — `id`, `report_id`, `evidence_type`, `resource_type`, `resource_id`, `conversation_id | None`, `snapshot | None` (a plain dict for `MESSAGE_SNAPSHOT`: `message_id`, `conversation_id`, `sender_id`, `content`, `sequence`, `created_at`), `content_sha256 | None` (sha256 of the canonical JSON of `snapshot`), `collected_by`, `collected_at`, `source` (a fixed string naming the contract used), `confidentiality`. Invariant: `MESSAGE_SNAPSHOT` requires snapshot, hash and `RESTRICTED`; hash must verify.

**`SafetyCase`** — `id`, `category`, `priority` (default `ORDINARY`), `status` (starts `OPEN`), `subject_user_id`, `assigned_to | None`, `version` (int ≥ 1), `cycle` (int ≥ 1), `created_by`, `created_at`, `updated_at`, `resolved_at | None`, `closed_at | None`. Transition methods enforce C6's table and raise `InvalidCaseTransition`; they do not know about permissions.

**`InvestigationNote`** (immutable) — `id`, `case_id`, `author_id`, `kind`, `content` (1–`safety_note_max_length`), `cited_evidence_ids` (tuple; **required non-empty for `CORROBORATED_FACT`**), `corrects_note_id | None`, `created_at`.

**`CaseDecision`** (immutable) — `id`, `case_id`, `cycle`, `decision_type`, `is_final` (derived: every type except `FURTHER_INVESTIGATION_REQUIRED`), `rationale` (`safety_rationale_min`–`max`), `cited_evidence_ids`, `cited_note_ids`, `decided_by`, `decided_at`. Rule: **`VIOLATION_ESTABLISHED` requires ≥ 1 cited note, and every cited note must be a `CORROBORATED_FACT` of the same case** (the use case verifies the notes' kind and case; the entity verifies non-empty).

**`EnforcementAction`** — `id`, `case_id`, `decision_id`, `action_type`, `target_user_id | None`, `target_listing_id | None` (exactly one set, matching the type: `LISTING_SUSPENSION` → listing, the rest → user), `target_key` (`user:{id}` / `listing:{id}`), `ends_at | None` (required for `COMMUNICATION_RESTRICTION`, at most `safety_restriction_max_days` ahead; forbidden for the others), `status`, `rationale`, `proposed_by`, `proposed_at`, `approved_by | None`, `approved_at | None`, `rejected_reason | None`, `attempts`, `next_attempt_at | None`, `last_error | None` (class name), `applied_at | None`, `reversed_by | None`, `reversal_reason | None`, `reversed_at | None`. Transition methods enforce C7.

**`SafetyUpdatePublished`** (event, extends shared-kernel `DomainEvent`) — `recipient_id`, `kind`, `reference_type | None` (`SAFETY_REPORT` / `LISTING`), `reference_id | None`. **Nothing else.**

**Pure policy functions (`policies.py`):** `status_for_reporter(report_status) -> str` (`RECEIVED`→"Received", `LINKED`→"Under review", `CLOSED`→"Reviewed"); `is_high_impact(action_type) -> bool` (everything except `WARNING`); `validate_restriction_end(ends_at, now, max_days)`; `backoff_delay_seconds(attempts, base, cap)`; `queue_sort_key(report)` — `THREAT_OR_DANGER` first, then oldest first (an explainable, fixed ordering, not a score).

**Tests (Chunk 3):** every invariant individually — reporter ≠ subject; description bounds; evidence hash verifies and tampering is detected; each case transition in C6 allowed/denied; `CORROBORATED_FACT` without citations raises; `VIOLATION_ESTABLISHED` without notes raises; target/type consistency and `ends_at` rules for every enforcement type; the pure policy functions; the event has no field beyond the five listed.

### C4. Database (all tables prefixed `safety_`; no foreign keys into any other module)

| Table | Columns (all `not null` unless noted) and constraints |
|---|---|
| `safety_reports` | `id` PK; `reporter_id`; `category`; `subject_type`; `subject_id`; `subject_user_id`; `description`; `status`; `idempotency_key`; `request_fingerprint`; `created_at`. **Unique `(reporter_id, idempotency_key)`**; **partial unique `(reporter_id, subject_type, subject_id, category) WHERE status <> 'CLOSED'`** (duplicate-open rule); `CHECK`s on the enums and `reporter_id <> subject_user_id`; index `(reporter_id, created_at DESC)`; index `(status, created_at)` for the queue. |
| `safety_cases` | `id` PK; `category`; `priority`; `status`; `subject_user_id`; `assigned_to` null; `version` (`CHECK >= 1`); `cycle` (`CHECK >= 1`); `created_by`; `created_at`; `updated_at`; `resolved_at` null; `closed_at` null. Indexes `(status, priority, created_at)` and `(assigned_to) WHERE assigned_to IS NOT NULL`. |
| `safety_case_reports` | `report_id` **PK** (a report belongs to at most one case); `case_id` FK; `linked_by`; `linked_at`. Index `(case_id)`. |
| `safety_evidence` | `id` PK; `report_id` FK; `evidence_type`; `resource_type`; `resource_id`; `conversation_id` null; `snapshot` jsonb null; `content_sha256` null; `collected_by`; `collected_at`; `source`; `confidentiality`. `CHECK`: a `MESSAGE_SNAPSHOT` has snapshot + hash + `RESTRICTED`. Index `(report_id)`. **Immutable (trigger).** |
| `safety_notes` | `id` PK; `case_id` FK; `author_id`; `kind`; `content`; `cited_evidence_ids` jsonb; `corrects_note_id` null FK; `created_at`. `CHECK`: `CORROBORATED_FACT` has a non-empty citation list. Index `(case_id, created_at)`. **Immutable (trigger).** |
| `safety_decisions` | `id` PK; `case_id` FK; `cycle`; `decision_type`; `is_final`; `rationale`; `cited_evidence_ids` jsonb; `cited_note_ids` jsonb; `decided_by`; `decided_at`. **Partial unique `(case_id, cycle) WHERE is_final`**. Index `(case_id, decided_at)`. **Immutable (trigger).** |
| `safety_enforcement_actions` | columns per C3; `target_key`; **partial unique `(case_id, action_type, target_key) WHERE status IN ('PROPOSED','APPROVED','APPLIED','REVERSAL_PENDING')`** (no live duplicate); partial index `(next_attempt_at) WHERE status IN ('APPROVED','REVERSAL_PENDING')`; `CHECK`s on the enums, attempts `>= 0`, exactly one target set. |
| `safety_case_events` | `id` PK; `case_id` null FK; `report_id` null FK; `event_type`; `actor_id` null (system); `occurred_at`; `details` jsonb. `CHECK (case_id IS NOT NULL OR report_id IS NOT NULL)`. Index `(case_id, occurred_at, id)`. **Immutable (trigger).** |

**Immutability triggers** (ADR-149): a `BEFORE UPDATE OR DELETE` trigger on `safety_evidence`, `safety_notes`, `safety_decisions`, `safety_case_events` raising an exception. Written as raw SQL in the migration (`op.execute`) with a matching `downgrade`. **Read the migration before applying**; confirm every constraint, partial index (exact predicate) and trigger. `details` jsonb holds ids and enums only — never text content.

### C5. Ports

**Inbound** (`Protocol` + `execute`, `@dataclass` request/response, `actor_id: str` first on everything user-initiated): the 20 use cases in C2.

**Outbound:**
- **Repositories** — `ReportRepository`, `CaseRepository` (cases, `case_reports`, and `case_events`), `EvidenceRepository`, `NoteRepository`, `DecisionRepository`, `EnforcementRepository`. Method lists are in the chunks that use them; every state change is a **conditional update** (`WHERE id = :id AND version = :v`, or `WHERE status = :expected`) returning `rowcount == 1`.
- **`ListingSubjectProvider`** — `get_listing(listing_id, viewer_id) -> ListingSubject | None` (`owner_id`, status string). `None` when absent or not visible to that viewer. Housing's `GetListing` + `GetProperty`.
- **`BookingSubjectProvider`** — `get_booking(booking_id, viewer_id) -> BookingSubject | None` (`student_id`, `provider_id`). Booking's `GetBooking` as the viewer, plus the owner via Housing; `NotFound` **and** `Forbidden` both map to `None`.
- **`MessageEvidenceProvider`** — `get_message(viewer_id, conversation_id, message_id) -> MessageSnapshotSource | None` (`message_id`, `conversation_id`, `sender_id`, `content`, `sequence`, `created_at`). Messaging's new `GetMessageForParticipant` **as the viewer**; any error maps to `None`.
- **`AccountEnforcer`** — `disable(identity_id)`, `reactivate(identity_id)` (Identity's `DisableAccount`/`ReactivateAccount`).
- **`ListingEnforcer`** — `suspend(actor_id, listing_id, reference)`, `lift(actor_id, listing_id, reference)` (Housing's new use cases).
- **`CommunicationEnforcer`** — `restrict(actor_id, user_id, ends_at, reference)`, `lift(actor_id, reference)` (Messaging's new use cases).
- All three enforcers **raise** `TransientEnforcementError` (retry) or `PermanentEnforcementError` (never retry — e.g. downstream "not found" or "invalid state"); success is a normal return. Both exception types are defined in T&S's application layer; the adapters translate the other module's errors, they never let them leak.
- Reused: shared-kernel `Clock`, `EntityId`, `Page`/`PageRequest`, `UnitOfWork`, `EventBus`, `RateLimitedError`, `publish_best_effort`; Security's `AuthorizationService`.

### C6. Case lifecycle (ADR-148)

| From | To | Via | Requires | Permission |
|---|---|---|---|---|
| (report) | `OPEN` | open case from report | the report is `RECEIVED` | `SAFETY_CASE_REVIEW` |
| `OPEN` | `TRIAGED` | triage | priority; **reason required for `HIGH`/`URGENT`** | review |
| `TRIAGED` | `IN_REVIEW` | status | an assignee exists | review |
| `IN_REVIEW` | `AWAITING_INFORMATION` | status | reason | review |
| `AWAITING_INFORMATION` | `IN_REVIEW` | status | — | review |
| `TRIAGED` / `IN_REVIEW` | `ESCALATED` | status | reason | review |
| `ESCALATED` | `IN_REVIEW` | status | reason | **approve** (`SAFETY_ENFORCEMENT_APPROVE`) |
| `IN_REVIEW` | `RESOLVED` | status | a **final decision exists for the current cycle** | review |
| `ESCALATED` | `RESOLVED` | status | a final decision exists | **approve** |
| `RESOLVED` | `CLOSED` | status | **no enforcement action in `PROPOSED`, `APPROVED`, `REVERSAL_PENDING`, `FAILED`, `REVERSAL_FAILED`** | review |
| `RESOLVED` | `IN_REVIEW` | reopen (status) | reason; `cycle` + 1 | review |
| `CLOSED` | `IN_REVIEW` | reopen (status) | reason; `cycle` + 1 | **approve** |

Every transition: authorization → conflict-of-interest check → state check → conditional update on `version` (version + 1) → one `safety_case_events` row, **one transaction**. Same-state requests and any pair not in the table raise `InvalidCaseTransition`. Linking reports to a `CLOSED` case is not allowed. When a case reaches `RESOLVED`, each linked report becomes `CLOSED`, and each reporter gets `REPORT_REVIEWED`. Reopen sets reports back to `LINKED`.

Priority changes after triage use `triage` again on a non-`OPEN` case (allowed in `TRIAGED`, `IN_REVIEW`, `ESCALATED`); every change is a history row with its reason. Assignment: `assign_to` must be an identity holding `SAFETY_CASE_REVIEW` (checked through `AuthorizationService`); assigning does not change state.

### C7. Enforcement state machine (ADR-152, ADR-153)

| From | To | Trigger | Who |
|---|---|---|---|
| (new) | `PROPOSED` | propose, any type except `WARNING` | review |
| (new) | `APPROVED` → `APPLIED` | propose `WARNING` — authorized by the proposer, applied immediately (publish `WARNING_ISSUED`; no downstream call) | review |
| `PROPOSED` | `APPROVED` | approve | approve; **approver ≠ proposer, approver ≠ subject** |
| `PROPOSED` | `REJECTED` | reject (reason) | approve |
| `APPROVED` | `APPLIED` | downstream success | system |
| `APPROVED` | `FAILED` | `PermanentEnforcementError`, or attempts exhausted | system |
| `FAILED` | `APPROVED` | operator requeue (attempts reset) | worker flag |
| `APPLIED` | `REVERSAL_PENDING` | reverse (reason; not for `WARNING`) | approve |
| `REVERSAL_PENDING` | `REVERSED` | downstream success | system |
| `REVERSAL_PENDING` | `REVERSAL_FAILED` | permanent error / exhausted | system |
| `REVERSAL_FAILED` | `REVERSAL_PENDING` | operator requeue | worker flag |
| `APPLIED` | `EXPIRED` | `ends_at` passed (communication restrictions only) | worker |

Proposing requires: the case is `IN_REVIEW`, `TRIAGED`, or `ESCALATED`; a **final `VIOLATION_ESTABLISHED` decision exists for the current cycle**; the target matches C3's rule (the case's `subject_user_id`, or a listing that is a `LISTING` subject of one of the case's reports); the conflict-of-interest check passes. The partial unique index makes a live duplicate impossible; the use case turns that violation into `409 duplicate_enforcement_action`.

**Applying** (inline right after approval, and by the worker): within a transaction, claim the row (`FOR UPDATE SKIP LOCKED`, `status = 'APPROVED'`); call the enforcer for the type with `reference = action id` and, for apply, `actor = approved_by` (reverse: `reversed_by`); **only on normal return** set `APPLIED`, `applied_at`, write the history row, commit, then publish the notification (best-effort). On `TransientEnforcementError`: roll back the claim's work, record `attempts + 1`, `next_attempt_at = now + backoff_delay_seconds(...)`, `last_error` = class name, history row `ENFORCEMENT_ATTEMPT_FAILED`; at `safety_enforcement_max_attempts` → `FAILED` plus an ERROR log. On `PermanentEnforcementError`: `FAILED` immediately. **Never** `APPLIED` on any exception. Reversal mirrors this with `REVERSAL_PENDING`.

**Recovery table (document every row in the module doc):** downstream unavailable → retried with backoff; downstream succeeded but T&S crashed before recording → row still `APPROVED`, the retry re-sends the same `reference`, the owner module treats it as already applied (idempotent), and T&S records `APPLIED`; duplicate approval request → second approval fails `InvalidEnforcementTransition`; downstream state already changed by someone else → handled per the owner (suspend an already-suspended listing succeeds as a no-op; a downstream "invalid state" is permanent → `FAILED` for an operator to look at); worker dies mid-run → unclaimed rows are picked up by the next run, claimed-but-uncommitted work rolled back.

**Known limitation to state in docs:** `ACCOUNT_SUSPENSION` uses Identity's `DisableAccount`, which does not remember *who* disabled an account. If an administrator separately disabled the same account before T&S applied its action, reversing T&S's action re-enables it. Documented, not solved here.

### C8. Visibility and authorization matrix

| Who | May | May **not** |
|---|---|---|
| **Reporter** (`SAFETY_REPORT_SUBMIT`) | submit; list/get **their own** reports: `id`, category, subject type/id, description, coarse status, `created_at` | see case, priority, assignee, notes, decisions, enforcement, other reporters, or the derived subject user |
| **Reported user** | nothing via the API | learn a report or case exists; learn who reported |
| **Reviewer** (`SAFETY_CASE_REVIEW`, `OPERATIONS`) | queue, open/link/triage/assign/status, notes, decisions, propose enforcement (and a warning outright), read case history, see reporter ids and evidence **metadata** | read restricted evidence content without `SAFETY_EVIDENCE_VIEW`; approve non-warning enforcement; act on a case they are subject/reporter of |
| **Evidence viewer** (`SAFETY_EVIDENCE_VIEW`) | read restricted evidence content — **each view writes a history row** | anything else |
| **Approver** (`SAFETY_ENFORCEMENT_APPROVE`, `ADMIN`) | case **summary** (status, priority, category, decisions with rationale, enforcement actions), approve/reject/reverse enforcement, handle `ESCALATED`/reopen-from-`CLOSED` | see notes, evidence content, reporter ids; approve what they proposed |

Case detail is **assembled per viewer**: the reviewer response and the approver response are different DTOs (no field-nulling). Evidence in a case response is metadata only (`id`, type, resource reference, collected_by role, `collected_at`, `source`, `confidentiality`); content comes only from the separate evidence-view route.

### C9. Notification contract (ADR-157, ADR-161)

`SafetyUpdatePublished` is published **after commit, best-effort**, from the application layer:

| Kind | Published when | Recipient | Reference |
|---|---|---|---|
| `REPORT_RECEIVED` | a report is accepted (new, not a replay) | reporter | `SAFETY_REPORT:report_id` |
| `REPORT_REVIEWED` | the case a report belongs to reaches `RESOLVED` | each linked report's reporter | `SAFETY_REPORT:report_id` |
| `WARNING_ISSUED` | a warning is applied | the subject user | none |
| `COMMUNICATION_RESTRICTED` | a communication restriction is `APPLIED` | the subject user | none |
| `LISTING_SUSPENDED` | a listing suspension is `APPLIED` | the subject user (the listing's owner) | `LISTING:listing_id` |
| `RESTRICTION_LIFTED` | a communication restriction or listing suspension is `REVERSED` or the restriction `EXPIRED` | the subject user | `LISTING:listing_id` for a listing, else none |

No notification for `ACCOUNT_SUSPENSION` (the user can no longer sign in). Notification's side is Chunk 14.

### C10. Settings (`config/settings.py`, `.env.example`)

| Setting | Default |
|---|---|
| `safety_report_rate_limit_count` / `_window_seconds` | 5 / 86400 |
| `safety_report_description_min` / `_max` | 10 / 2000 |
| `safety_max_reported_messages` | 5 |
| `safety_note_max_length` | 4000 |
| `safety_rationale_min` / `_max` | 20 / 4000 |
| `safety_restriction_max_days` | 90 |
| `safety_enforcement_max_attempts` | 6 |
| `safety_enforcement_backoff_base_seconds` / `_cap_seconds` | 60 / 3600 |
| `safety_worker_batch_size` | 100 |
| `safety_debug_fail_enforcement` | `False` — honored **only** when `app_env` is `local` or `test` (Chunk 13); makes enforcers raise `TransientEnforcementError` so the failure path can be demonstrated |

### C11. Touch map — the **only** files outside `modules/trust_safety/` this module changes

| Module / file | Change | Chunk |
|---|---|---|
| Security: `domain/value_objects.py`, `domain/policy.py` | six permissions (C8/ADR-151), role-scoped, with the grants stated | 2 |
| Housing: entity/enums, migration, two new use cases, owner use cases' guards, composition | **C12** | 6 |
| Messaging: one new use case, `messaging_restrictions` table, two new use cases, the restriction adapter's second source, composition | **C13** | 7 |
| Notification: event parser, policy, templates, enums, migration, subscriber registration | **C14** | 14 |
| `config/settings.py`, `.env.example` | C10 | 4 |
| `app.py`, bus factory (Module 12's `build_event_bus`) | mount routers; T&S publishes through the existing bus | 15, 16 |
| `pyproject.toml` | import-linter contracts | 18 |

**Not touched:** Identity (its use cases are called as-is), Profile, University, Search, Media/File, Verification, Booking, Payment & Escrow. After every chunk that touches another module, re-run that module's suite and confirm it is unchanged apart from the documented additions.

### C12. Housing amendment — the rulebook for Chunk 6
- `ListingStatus` gains `SUSPENDED`. DB `CHECK` on the listing status column updated by migration (**read it**); new nullable column `suspension_reference` (UUID).
- `SuspendListingForSafety(actor_id, listing_id, source_reference)`: authorize `HOUSING_SAFETY_SUSPEND` (role-scoped; `ADMIN`); allowed from `PUBLISHED` and `UNAVAILABLE`; **already `SUSPENDED` → success, no change** (idempotent, retry-safe); `DRAFT`/`ARCHIVED` → `InvalidListingStateTransition`; persists status and reference with a **conditional update**.
- `LiftListingSuspension(actor_id, listing_id, source_reference)`: same permission; `SUSPENDED` → **`UNAVAILABLE`** (the owner republishes through the normal readiness checks; never auto-republish); a listing that is not `SUSPENDED` → success no-op if its reference is absent/cleared, else `InvalidListingStateTransition`.
- **The owner's** `PublishListing`, `UnpublishListing`, `ArchiveListing` (and property-level archive, if it cascades) **must reject a `SUSPENDED` listing** with `InvalidListingStateTransition`.
- Every existing place that switches on listing status must be found in Chunk 1 and confirmed to treat `SUSPENDED` like "not available/not published" (Search, Booking, Messaging's new-conversation rule, Housing's own schemas/enums). Frontends must expect the new value.
- **Existing bookings on the listing are untouched** — Booking owns them.

### C13. Messaging amendment — the rulebook for Chunk 7
- `GetMessageForParticipant(actor_id, conversation_id, message_id) -> MessageView`: uses the existing `ParticipantGuard`; the message must belong to that conversation; **any failure is `ConversationNotFound`** (one error for nonparticipant, missing conversation, missing message). **No HTTP route. No admin path.** Exposed through Messaging's inbound ports only.
- `messaging_restrictions`: `id`, `user_id`, `starts_at`, `ends_at`, `source_reference` (**unique**), `status` (`ACTIVE` | `LIFTED`), `lifted_at` null, `created_at`; index `(user_id) WHERE status = 'ACTIVE'`.
- `RestrictCommunication(actor_id, user_id, ends_at, source_reference)`: authorize `MESSAGING_RESTRICT` (`ADMIN`); `ends_at` must be in the future; **idempotent by `source_reference`** (same reference → success, no second row).
- `LiftCommunicationRestriction(actor_id, source_reference)`: same permission; sets `LIFTED`; already lifted → success; **unknown reference → `RestrictionNotFound`** (so T&S can treat "nothing to lift" distinctly).
- **Enforcement point:** the real `CommunicationRestrictionProvider` adapter becomes a composite of its existing Identity-status check **and** an active, unexpired row in `messaging_restrictions` for the **actor**; the restriction check applies **only when a counterpart is supplied** (conversation creation and sends) — reads, history and read-position updates stay available. Messaging imports nothing from Trust & Safety.

### C14. Notification amendment — the rulebook for Chunk 14
Follows Module 12's C12 pattern. T&S's `domain/events.py` defines `SafetyUpdatePublished`; `application/ports/events.py` re-exports it. In Notification: `NotificationCategory.SAFETY`; six `NotificationType`s — `safety.report_received`, `safety.report_reviewed`, `safety.warning_issued`, `safety.communication_restricted`, `safety.listing_suspended`, `safety.restriction_lifted`; `TargetType` gains `SAFETY_REPORT` and `LISTING`; fixed templates:

| Type | Title | Body |
|---|---|---|
| `safety.report_received` | Report received | Thank you. We've received your report and will review it. |
| `safety.report_reviewed` | Report reviewed | We've reviewed your report. Thank you for helping keep Camp Match safe. |
| `safety.warning_issued` | Safety notice | You've received a warning about activity on your account. Please follow Camp Match's community and safety guidelines. |
| `safety.communication_restricted` | Messaging restricted | Your ability to send messages has been restricted. Contact support if you have questions. |
| `safety.listing_suspended` | Listing suspended | One of your listings has been suspended following a safety review. Contact support if you have questions. |
| `safety.restriction_lifted` | Restriction lifted | A safety restriction on your account has been lifted. |

Recipient policy: the event's own `recipient_id` (T&S decides who may be told); `kind` → type; target from `reference`. One migration altering the three `CHECK` constraints (`type`, `category`, `target_type`) — read it. Collapse does not apply to safety types.

---

## PART D — CHUNKED IMPLEMENTATION

**Work one chunk at a time, in order, and stop after each Completion Report** (see the Operating Instructions at the top). Each chunk lists only what is specific to it; Part C is the design, and **C12, C13, C14 are the rulebooks for the amendments to Housing, Messaging and Notification.** A failed acceptance item means stop and report — never skip, weaken, or work around a test. Every chunk that touches another module ends by re-running that module's whole suite.

---

### CHUNK 1 — REPOSITORY INSPECTION, ARCHITECTURE MAPPING & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** confirm this specification's assumptions against the real repository and create the empty module. No behavior.

1. Read `AI_instructions/`, all `AI_state/`, and `docs/modules/` for identity, security, housing, booking, messaging, notification, verification, payment.
2. **Confirm Modules 11 (Messaging) and 12 (Notification) are built as specified.** Messaging: `ParticipantGuard`, `MessageView`, `CommunicationRestrictionProvider` and its Identity-backed adapter, `RateLimitedError`/`429` handler, `publish_best_effort`. Notification: `build_event_bus` factory, the six supported events, `NotificationType`/`TargetType` enums and the migration that holds their `CHECK`s. **Report any difference — it changes this plan.** If either is missing, stop.
3. **Identity:** exact signatures of `DisableAccount` / `ReactivateAccount` (request, response, errors, and whether disabling an already-disabled account is a no-op); the account status values.
4. **Security:** the exact recipe for adding a permission; whether it is **role-scoped** (declared alongside the permission); how `OPERATIONS` and `ADMIN` are assigned today (script name/arguments) and that one identity can hold both; `AuthorizationService`'s exact interface; how an arbitrary identity's permission can be checked (needed for "assignee must hold `SAFETY_CASE_REVIEW`").
5. **Housing:** `ListingStatus` and every place it is switched on or enumerated (entity, schemas, DB `CHECK`, Search eligibility, Booking, Messaging's new-conversation rule, tests); `GetListing`'s visibility rules (who can see a `DRAFT`/`UNAVAILABLE`/`PUBLISHED` listing) and `GetProperty`'s owner field; the owner's `PublishListing`/`UnpublishListing`/`ArchiveListing` and whether archiving a property cascades to listings.
6. **Booking:** `GetBooking`'s signature, visibility rules and errors. **Messaging:** exactly where `ParticipantGuard` and the `CommunicationRestrictionProvider` call sites live (create-conversation and send use the counterpart form; guard uses `None`).
7. **Verification:** how its history table is written and made append-only (if at all) — T&S reuses the pattern. Existing triggers anywhere in migrations? (Report how migrations that use raw SQL are written.)
8. Inspect: shared-kernel `Page`/`PageRequest`/`UnitOfWork`; router and schema conventions; how existing concurrency tests provision committed data; import-linter contracts and the Module 12 bus factory's location; the project-wide frontend API doc location.
9. Confirm no safety-related code exists. Create the empty structure from Part C2 (one-line docstrings, no logic) plus `tests/unit|integration|api/trust_safety/`. Touch nothing else.

**Acceptance criteria:** a written report covering steps 2–8 with exact signatures, every mismatch flagged, and an explicit **proceed / blocked** verdict; scaffolding importable; no file outside the module and test folders changed.

---

### CHUNK 2 — SECURITY: THE SIX PERMISSIONS
**[FOR YOU — GEMINI CLI]**

**Files (Security, its documented recipe, exactly these):** `domain/value_objects.py`, `domain/policy.py`.

Add, all **role-scoped**: `SAFETY_REPORT_SUBMIT` (`"safety.report.submit"`) → `STUDENT`, `SCOUT`; `SAFETY_CASE_REVIEW` (`"safety.case.review"`) → `OPERATIONS`; `SAFETY_EVIDENCE_VIEW` (`"safety.evidence.view"`) → `OPERATIONS`; `SAFETY_ENFORCEMENT_APPROVE` (`"safety.enforcement.approve"`) → `ADMIN`; `MESSAGING_RESTRICT` (`"messaging.restrict"`) → `ADMIN`; `HOUSING_SAFETY_SUSPEND` (`"housing.safety.suspend"`) → `ADMIN`. **Grant nothing else to anyone** — in particular `ADMIN` gets none of the three investigative/evidence permissions and `OPERATIONS` gets none of the three ADMIN ones.

**Tests:** `tests/unit/security/domain/test_policy.py` extended with a parametrized test over all six: exactly the stated roles hold each, and **no other role** does (assert the complement explicitly); `is_ownership_scoped` is `False` for all six; the existing permissions' grants are unchanged.

**Acceptance criteria:** tests pass; Security's, Identity's, Profile's, Housing's, Booking's, Messaging's suites unchanged; `mypy`, `lint-imports` clean.

---

### CHUNK 3 — DOMAIN MODEL & POLICIES
**[FOR YOU — GEMINI CLI]**

**Files:** `domain/value_objects.py`, `entities.py`, `policies.py`, `events.py`. Build exactly Part C3 and C6/C7's transition tables as entity methods and pure functions.

**Dependencies allowed:** shared-kernel `EntityId`, `DomainEvent`; stdlib (`dataclasses`, `enum`, `hashlib`, `json`, `datetime`). Nothing else.

**Tests** (`tests/unit/trust_safety/domain/`, each its own named test): the full list is the "Tests (Chunk 3)" paragraph in C3. In addition, **parametrized over the entire tables**: for `SafetyCase`, every (from, to) pair in C6 is allowed and **every other pair raises `InvalidCaseTransition`**; for `EnforcementAction`, every row in C7 is allowed and every other (from, to) pair raises; `is_high_impact`; `queue_sort_key` puts `THREAT_OR_DANGER` first then oldest-first and ignores everything else; `backoff_delay_seconds` doubles, caps, rejects attempts < 1; **no attribute or method anywhere in the domain is named like `substantiated`, `confirmed`, `guilty`, or `violation_established` except the `DecisionType` member** (a source scan — this guards rule C1.3).

**Acceptance criteria:** tests pass; no import outside the allowed list.

---

### CHUNK 4 — ERRORS, PORTS, DTOs & SETTINGS
**[FOR YOU — GEMINI CLI]**

**Files:** `application/errors.py`, `application/ports/inbound.py`, `outbound.py`, `events.py`; `config/settings.py`, `.env.example`.

1. **Errors** (each extends a shared-kernel category and carries a `code`): `ReportNotFound`, `CaseNotFound`, `EvidenceNotFound`, `EnforcementActionNotFound` (`NotFoundError`, `report_not_found` …); `InvalidReportSubject`, `InvalidReportDescription`, `InvalidIdempotencyKey`, `TransitionRequirementNotMet`, `InvalidNote`, `InvalidDecision`, `InvalidEnforcementRequest` (`ValidationError`); `DuplicateOpenReport` (carries the reporter's own existing report id), `IdempotencyKeyConflict`, `InvalidCaseTransition`, `CaseStateChanged` (`case_state_changed`), `ReportAlreadyLinked`, `DuplicateEnforcementAction`, `InvalidEnforcementTransition` (`ConflictError`); `SeparationOfDutiesViolation` (`ForbiddenError`); `ReportRateLimitExceeded` (extends the shared `RateLimitedError`, code `rate_limit_exceeded`). Plus the two plain internal exceptions `TransientEnforcementError`, `PermanentEnforcementError` (not `ApplicationError`s).
2. **Ports:** every inbound and outbound port in C5 as `Protocol`s with `@dataclass` request/response types. `application/ports/events.py` re-exports `SafetyUpdatePublished`.
3. **Response shapes:** `ReporterReportView` (`id`, `category`, `subject_type`, `subject_id`, `description`, `status` — the coarse string, `created_at`); `ReportAck` (`report_id`, `status`, `created_at`, `replayed`); `ReviewerReportView` (adds `reporter_id`, `case_id | None`, `similar_report_count`); `ReviewerCaseView` (case fields, linked reports, evidence **metadata**, notes, decisions, enforcement actions, `viewer_kind`); `ApproverCaseView` (case summary, decisions with rationale, enforcement actions); `EvidenceMetadataView`; `EvidenceContentView`; `NoteView`; `DecisionView`; `EnforcementView`; `CaseEventView`. **Reviewer and approver views are separate types** (C8).
4. **Settings:** per C10 (the debug flag is a plain bool here; the environment guard comes in Chunk 13).

**Tests:** each error's parent and exact `code`; `ReportRateLimitExceeded` maps to `429` through the existing handler; settings defaults load.

**Acceptance criteria:** `mypy` clean on touched files; tests pass; the **full existing suite is unchanged**; no `fastapi`/`sqlalchemy` import under `application/`.

---

### CHUNK 5 — PERSISTENCE, CONSTRAINTS, TRIGGERS & MIGRATION
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/persistence/models.py` and the six repository files. Build all eight tables exactly as Part C4 and the repositories against C5.

Rules that are easy to get subtly wrong:
- Every state-changing repository method is a **conditional `UPDATE`** returning `rowcount == 1` (case: `WHERE id = :id AND version = :v`; enforcement: `WHERE id = :id AND status = :expected`).
- `EnforcementRepository.claim_for_attempt(id)` uses `FOR UPDATE SKIP LOCKED` and must refuse to run outside a transaction; `list_due(now, limit)` takes no lock.
- `ReportRepository.add` catches the `(reporter_id, idempotency_key)` violation and the duplicate-open-report violation **by constraint name** and raises distinct internal signals — never a blanket integrity-error catch.
- Evidence, notes, decisions and case events repositories expose **no update or delete method at all**.
- `similar_report_count(subject_type, subject_id, excluding_report_id)` and `count_recent_by_reporter(reporter_id, since)` are single aggregate queries using the C4 indexes.
- Never return ORM rows outside persistence files.

**Migration:** `poetry run alembic revision --autogenerate -m "add safety tables"`, then add the four immutability triggers as raw SQL (`op.execute`, with `downgrade` that drops them). **Read the whole migration before applying** and confirm every `CHECK`, both partial unique indexes' exact predicates, the partial indexes, and the triggers.

**Tests** (`tests/integration/trust_safety/`, `integration` marker, `db_session`; constraint tests use raw inserts that bypass the application layer):
- every `CHECK` rejects its violation, including `reporter_id = subject_user_id`, a `MESSAGE_SNAPSHOT` without snapshot/hash/`RESTRICTED`, a `CORROBORATED_FACT` with no citations, a case event with neither case nor report;
- idempotency unique and duplicate-open partial unique: the second insert is rejected; a **`CLOSED`** report of the same triple does not block a new one; a different reporter on the same subject is not blocked;
- `safety_case_reports.report_id` PK: a report cannot belong to two cases;
- the **partial unique on final decisions** per `(case_id, cycle)`: a second final decision in one cycle is rejected; a non-final one is not; a final one in the next cycle is allowed;
- the **partial unique on live enforcement actions**: a second live action for the same `(case, type, target)` is rejected; after the first becomes `REVERSED`/`REJECTED`/`EXPIRED`/`FAILED`, a new one is allowed;
- **immutability triggers:** `UPDATE` and `DELETE` on `safety_evidence`, `safety_notes`, `safety_decisions`, `safety_case_events` each fail with the trigger's exception — via raw SQL, via the ORM, and via a direct `TRUNCATE`-free `DELETE` of every row;
- conditional updates: a case update with a stale `version` returns `False` and changes nothing; enforcement `claim_for_attempt` skips a row locked by another session (two sessions, committed data);
- `count_recent_by_reporter` and `similar_report_count` correct at window boundaries.

**Acceptance criteria:** tests pass against the Termux Postgres; `alembic upgrade head` clean, and `downgrade` then `upgrade` round-trips; `lint-imports` clean.

---

### CHUNK 6 — HOUSING AMENDMENT: THE SAFETY HOLD
**[FOR YOU — GEMINI CLI]**

**Objective:** Housing gains a `SUSPENDED` listing state that only a safety use case can enter or leave. **Housing's existing behavior, return values, errors and tests must not change** except where a listing is `SUSPENDED`. Read **Part C12** — it is the rulebook.

Implement C12 in Housing: the status value, the migration, the nullable `suspension_reference`, `SuspendListingForSafety`, `LiftListingSuspension` (both with the **conditional update** idiom and the exact idempotency rules), the owner-use-case guards, and the composition. Update every place Chunk 1 found that enumerates or switches on listing status.

**Tests:**
- suspend from `PUBLISHED` and from `UNAVAILABLE` → `SUSPENDED`, reference stored; suspend an already-`SUSPENDED` listing → success, unchanged; suspend `DRAFT`/`ARCHIVED` → `InvalidListingStateTransition`;
- lift → **`UNAVAILABLE`** (never `PUBLISHED`); lift a non-suspended listing follows C12's no-op/error rule exactly;
- permission: a caller without `HOUSING_SAFETY_SUSPEND` (a `SCOUT` owner, a `STUDENT`, an `OPERATIONS` account) → `Forbidden` on both; `ADMIN` allowed; **the owner of the listing is refused** even though they own it;
- **the owner cannot escape:** `PublishListing`, `UnpublishListing`, `ArchiveListing` on a `SUSPENDED` listing each raise `InvalidListingStateTransition`, and the listing is unchanged;
- a `SUSPENDED` listing is **not** returned by Search, **cannot** be booked, and **cannot** start a new Messaging conversation (integration-level checks using those modules' existing public use cases);
- concurrent duplicate suspends → one effective transition, both calls succeed;
- the migration round-trips (`downgrade` then `upgrade`).

**Acceptance criteria:** new tests pass; **Housing's entire suite**, Search's, Booking's, Messaging's, Verification's suites pass unchanged; `mypy`, `lint-imports` clean.

---

### CHUNK 7 — MESSAGING AMENDMENT: PARTICIPANT LOOKUP & RESTRICTIONS
**[FOR YOU — GEMINI CLI]**

**Objective:** Messaging gains one participant-scoped read and its own restriction state. **No HTTP route is added. Messaging's behavior for unrestricted users must not change.** Read **Part C13**.

Implement C13: `GetMessageForParticipant` on the existing `ParticipantGuard`; the `messaging_restrictions` table and migration (**read it**); `RestrictCommunication` and `LiftCommunicationRestriction` with the exact idempotency rules; and the composite restriction adapter, which applies the new check **only when a counterpart is supplied**. Add both new inbound use cases to Messaging's ports. Update composition.

**Tests:**
- `GetMessageForParticipant`: a participant gets the message; a **nonparticipant**, a missing conversation, a message from a **different** conversation, and a missing message all raise the **identical** `ConversationNotFound`;
- `RestrictCommunication`: needs `MESSAGING_RESTRICT` (`ADMIN` only; `OPERATIONS`, `STUDENT`, `SCOUT` refused); past `ends_at` rejected; **same `source_reference` twice → one row, both succeed**; `LiftCommunicationRestriction` idempotent; unknown reference → `RestrictionNotFound`;
- **enforcement:** a restricted user's `CreateConversation` and `SendMessage` (HTTP **and** WebSocket) → `403 communication_restricted`, nothing persisted; the same user can still list conversations, read history, and advance read position; the counterpart can still message the restricted user and the message is saved; the restriction **expires** at `ends_at` without any job (a `FixedClock` test); a lifted restriction no longer blocks; a restriction on A does not affect B;
- a restriction **applied after a WebSocket connection exists** blocks the next `message.send` (reuses the Module 11 live-server technique);
- Messaging's **entire** suite passes unchanged; no file in Messaging imports `camp_match.modules.trust_safety`.

**Acceptance criteria:** new tests pass; all of Messaging's HTTP, WebSocket, recovery and concurrency suites pass (**three consecutive runs** of the WebSocket files); `mypy`, `lint-imports` clean.

---

### CHUNK 8 — T&S ADAPTERS FOR OTHER MODULES
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/listing/`, `booking/`, `messaging/`, `enforcement/` (Part C2). Each imports **only** the target module's `application/ports` (and use-case surface), never its `adapters` or `domain`.

- `InProcessListingSubjectProvider`: Housing `GetListing` as the viewer, then `GetProperty` for the owner; `None` for not-found **and** not-visible.
- `InProcessBookingSubjectProvider`: Booking `GetBooking` as the viewer; owner via Housing; `NotFound` **and** `Forbidden` → `None`.
- `InProcessMessageEvidenceProvider`: Messaging `GetMessageForParticipant` as the viewer; **every** error → `None`; map only the fields in C5.
- `InProcessAccountEnforcer` (Identity `DisableAccount`/`ReactivateAccount`), `InProcessListingEnforcer` (Housing's new use cases), `InProcessCommunicationEnforcer` (Messaging's new use cases): translate outcomes per C5 — success returns; Housing/Messaging "invalid state", "not found", and "forbidden" → `PermanentEnforcementError`; `RestrictionNotFound` on **lift** → treated as success (nothing to lift); any other exception → `TransientEnforcementError`. When `safety_debug_fail_enforcement` is on (guarded in Chunk 13), they raise `TransientEnforcementError` before calling anything.

**Tests** (fakes for the target use cases): mapping correct both ways; every not-found/forbidden path; the message provider's output has no field beyond C5's; each enforcer's error classification **exhaustively** (a parametrized table of downstream exception → Transient/Permanent/success); enforcers pass `reference` through unchanged.

**Acceptance criteria:** tests pass; `mypy`, `lint-imports` clean; neighbouring suites unaffected.

---

### CHUNK 9 — REPORT INTAKE
**[FOR YOU — GEMINI CLI]**

**Files:** `application/services/case_access.py` (start of it), `use_cases/submit_report.py`, `list_my_reports.py`, `get_my_report.py`.

`SubmitReport(actor_id, idempotency_key, category, description, subject)` per ADR-145/146/158, as one use case, in this order:
1. Authorize `SAFETY_REPORT_SUBMIT` (Security's `Forbidden` otherwise).
2. Validate `idempotency_key` (1–64 chars `[A-Za-z0-9_-]`), category, description (`InvalidReportDescription`), and the subject shape (a `MESSAGE` subject has 1–`safety_max_reported_messages` **distinct** message ids).
3. **Idempotency lookup** by `(actor, key)`: same `request_fingerprint` (sha256 of the normalized request) → return the existing report as a **replay** (no new rows, no event); different → `IdempotencyKeyConflict`.
4. **Rate limit:** `count_recent_by_reporter` ≥ limit → `ReportRateLimitExceeded` (with `retry_after_seconds`).
5. **Resolve the subject** through the provider ports **as the reporter** (C3/ADR-145): `LISTING` → owner; `BOOKING` → the other party; `CONVERSATION` → each message via `MessageEvidenceProvider`, all from **one** sender who is **not** the reporter. Any `None`, any own message, a reporter who owns the listing, or a mixed-sender set → `InvalidReportSubject` (one generic message — never say which check failed).
6. **Duplicate-open check:** an open report by this reporter on the same triple → `DuplicateOpenReport` carrying that report's id.
7. In one `UnitOfWork`: insert the report (`RECEIVED`), the evidence rows (snapshots + sha256 for messages; a `RESOURCE_REFERENCE` for listing/booking), and a `REPORT_SUBMITTED` history row. A unique-violation race on the idempotency key or duplicate-open index → rollback, reload, and apply step 3/6's rules.
8. After commit, `publish_best_effort(SafetyUpdatePublished(REPORT_RECEIVED))`. Log INFO `safety_report_accepted` (ids, category, subject type).
9. Return `ReportAck` (`report_id`, `status`, `created_at`, `replayed`) — **no case, priority, or subject-user information.**

`ListMyReports` / `GetMyReport`: reporter-scoped, `ReporterReportView` only (coarse status via `status_for_reporter`); another user's id → `ReportNotFound`.

**Tests (fakes; each the handoff's 16.1 item):** valid report accepted; reporter comes from `actor_id` only (no parameter can override it); invalid category, invalid/unsupported subject, mixed or own messages, own listing → rejected with the **same generic** `InvalidReportSubject`; unauthorized message/conversation ids rejected; a listing the reporter can't see rejected; accepted report **does not** create a case, priority or finding (assert the fake case repository is untouched); **idempotency:** replay returns the same report with no new rows/events/evidence, a conflicting body → `IdempotencyKeyConflict`; the lost-race path (fake `add` raising the unique signal) reloads and replays; duplicate-open → `DuplicateOpenReport` with the reporter's own id, while a **different** reporter on the same listing is accepted; rate limit exceeded at the boundary with `retry_after_seconds`; evidence rows created with the right provenance (`collected_by` = reporter, `source` string, `sha256` verifies, `RESTRICTED` for snapshots); the acknowledgement contains no case information; the `REPORT_RECEIVED` event is published exactly once and **not** on a replay; a **raising** bus never changes the result; a log-capture test asserts **no description and no message content** appears in logs; `ListMyReports` returns only the caller's reports; `GetMyReport` for another user's id and a random id raise identical `ReportNotFound`.

**Acceptance criteria:** tests pass against fakes; no framework imports under `application/`.

---

### CHUNK 10 — CASES: OPEN, LINK, TRIAGE, ASSIGN, LIFECYCLE
**[FOR YOU — GEMINI CLI]**

**Files:** `application/services/case_access.py` (complete), `use_cases/list_review_queue.py`, `open_case_from_report.py`, `link_report_to_case.py`, `list_cases.py`, `get_case.py`, `triage_case.py`, `assign_case.py`, `change_case_status.py`.

**`CaseAccess`** (one service so the rule exists once): `require_reviewer(actor, case_id)` — authorizes `SAFETY_CASE_REVIEW`, loads the case, and applies the **conflict-of-interest rule** (actor is the case's `subject_user_id` or a reporter of any linked report → `CaseNotFound`, identical to a missing case); `require_approver(...)` — same with `SAFETY_ENFORCEMENT_APPROVE`.

Implement the use cases exactly as C6: queue ordering via `queue_sort_key` with filters and `similar_report_count`; open-case (creates the case with the report's category/subject user, links the report, report → `LINKED`, history row, one transaction); link (`ReportAlreadyLinked`, closed case refused, history row); triage (priority + reason rule); assign (assignee must hold `SAFETY_CASE_REVIEW`); status changes with every requirement in C6's table (`TransitionRequirementNotMet` for a missing reason/assignee/final decision/open enforcement action); `RESOLVED` → each linked report `CLOSED` and `REPORT_REVIEWED` published to each reporter; reopen increments `cycle` and re-links reports as `LINKED`. **Every change is a conditional update on `version`** (`CaseStateChanged` on a lost race) **and** its history row in the same unit of work. `GetCase` returns the **reviewer** view for reviewers and the **approver** view for approvers (C8) — different assembly paths.

**Tests (fakes unless stated):** each handoff 16.2 item — a report becomes a case; two reports link to one case and **both keep their own reporter, timestamp and evidence**; every illegal transition rejected (parametrized over the full C6 table, asserting the case is unchanged and **no history row was written**); only `SAFETY_CASE_REVIEW` holders act, others `Forbidden`; **`ADMIN` without the review permission cannot triage, assign, or read a case's notes**; an `ESCALATED → IN_REVIEW` and a `CLOSED` reopen need the approver permission; a reviewer who is the case's subject, or a reporter on it, gets `CaseNotFound` for every route (parametrized); assignee without the permission rejected; priority change requires a reason for `HIGH`/`URGENT` and writes a history row each time; resolve without a final decision → `TransitionRequirementNotMet`; close with a `PROPOSED`/`APPROVED`/`REVERSAL_PENDING`/`FAILED`/`REVERSAL_FAILED` action → rejected, with only `REJECTED`/`APPLIED`/`REVERSED`/`EXPIRED` allowing it; `CaseStateChanged` on a stale version with nothing written; every successful transition writes **exactly one** matching history row (assert the fake UoW saw both writes before commit, and neither when commit fails); `REPORT_REVIEWED` published once per reporter on resolve and **not** on any other transition; the approver view contains no notes, no evidence, no reporter ids (assert the DTO type's fields).

**Acceptance criteria:** tests pass; no framework imports under `application/`.

---

### CHUNK 11 — EVIDENCE VIEW, INVESTIGATION NOTES & HISTORY
**[FOR YOU — GEMINI CLI]**

**Files:** `use_cases/view_evidence.py`, `add_note.py`, `get_case_history.py`.

- **`ViewEvidence(actor, case_id, evidence_id)`:** authorize **both** `SAFETY_CASE_REVIEW` and `SAFETY_EVIDENCE_VIEW`; conflict-of-interest; the evidence must belong to a report linked to this case (else `EvidenceNotFound`); returns `EvidenceContentView`; **writes an `EVIDENCE_VIEWED` history row (actor, evidence id, no content) in the same unit of work as the read** — if the audit write fails, the content is not returned. Verify the stored hash against the snapshot and return `integrity_verified`.
- **`AddNote(actor, case_id, kind, content, cited_evidence_ids, corrects_note_id)`:** reviewer; content bounds; every cited evidence id must belong to the case; `CORROBORATED_FACT` requires ≥ 1; `corrects_note_id` must be a note of the same case; a `CLOSED` case refuses notes; history row. **There is no edit and no delete use case.**
- **`GetCaseHistory`:** reviewer; paginated, oldest first; ids and enums only.

**Tests:** evidence view needs both permissions (an `OPERATIONS` account **without** `SAFETY_EVIDENCE_VIEW` is refused — arrange via a custom policy fake; an `ADMIN` is refused); evidence from another case → `EvidenceNotFound`; each view writes one audit row, and a failing audit write returns nothing; the hash is verified and a tampered fake snapshot reports `integrity_verified = False`; **the list/detail responses contain no evidence content** (metadata only); notes: all three kinds; `CORROBORATED_FACT` without citations rejected; citing another case's evidence rejected; a correction note leaves the original unchanged and references it; no update/delete use case or repository method exists (source scan); content never appears in logs; history pagination and ordering.

**Acceptance criteria:** tests pass against fakes.

---

### CHUNK 12 — DECISIONS
**[FOR YOU — GEMINI CLI]**

**Files:** `use_cases/record_decision.py`.

`RecordDecision(actor, case_id, decision_type, rationale, cited_evidence_ids, cited_note_ids)`: reviewer (an `ESCALATED` case requires the **approver** permission instead); conflict-of-interest; case state must be `IN_REVIEW` or `ESCALATED`; rationale bounds; cited evidence/notes belong to the case; **`VIOLATION_ESTABLISHED` requires ≥ 1 cited note and every cited note must be a `CORROBORATED_FACT`** (`InvalidDecision` otherwise); a final decision when one already exists this cycle → `InvalidDecision` (the partial unique index is the backstop, the lost race becomes the same error); history row; one transaction. **Recording a decision does not change the case state** — resolving is a separate, explicit transition (C6).

**Tests (fakes, plus one real-DB test):** each handoff 16.4 item that concerns decisions — an allegation cannot produce a violation finding (a report with any number of reports/priority/category and **no** corroborated-fact notes cannot get `VIOLATION_ESTABLISHED`; assert exhaustively for every category); only authorized actors record; rationale bounds; citations checked; `FURTHER_INVESTIGATION_REQUIRED` is non-final and repeatable; `REFERRED` is final and requires no enforcement; a second final decision in a cycle rejected, **and the real-DB concurrent test: two simultaneous final decisions → exactly one row** (committed data, `asyncio.gather`); after a reopen a new final decision is allowed in the new cycle and the **old one is untouched**; no logs contain the rationale.

**Acceptance criteria:** tests pass.

---

### CHUNK 13 — ENFORCEMENT WORKFLOW, THE WORKER & THE FAILURE SWITCH
**[FOR YOU — GEMINI CLI]**

**Files:** `use_cases/propose_enforcement.py`, `approve_enforcement.py`, `reject_enforcement.py`, `reverse_enforcement.py`, `process_enforcement_queue.py`, `requeue_failed_enforcement.py`; `scripts/run_safety_worker.py`; the debug-flag guard.

Implement C7 exactly: propose (reviewer; every precondition listed; `WARNING` authorized and applied immediately with **no downstream call**, publishing `WARNING_ISSUED`); approve (approver; **approver ≠ proposer and ≠ subject**, else `SeparationOfDutiesViolation`) → `APPROVED` then an **inline apply attempt**; reject (reason); reverse (approver; reason; not for `WARNING`); `ProcessEnforcementQueue(limit)` (apply due `APPROVED`, reverse due `REVERSAL_PENDING`, expire `APPLIED` communication restrictions whose `ends_at` passed — each action in its **own** transaction so one failure cannot affect the rest) and `RequeueFailedEnforcement`. Notifications per C9, best-effort, after commit, **only on a real transition**.

`scripts/run_safety_worker.py`: default = compose real dependencies and run `ProcessEnforcementQueue(safety_worker_batch_size)` **once**, printing counts; `--stats` (counts by status); `--requeue-failed`. No loop, daemon or scheduler (same stance as every earlier script). The script must build its bus through Module 12's `build_event_bus`.

**Debug switch:** `safety_debug_fail_enforcement` is honored **only** when `app_env` is `local` or `test` — an explicit structural check (same stance as Payment's mock controls, Messaging's and Notification's debug flags); ignored otherwise.

**Tests (fakes; one fake enforcer per downstream):**
- the full C7 table — every allowed transition succeeds, every other raises `InvalidEnforcementTransition`;
- **proposal preconditions:** no final `VIOLATION_ESTABLISHED` decision → rejected; target not the case's subject / a listing not among the reports' subjects → rejected; communication restriction without `ends_at`, or beyond the maximum → rejected; `ends_at` on a non-restriction → rejected; a duplicate of a live action → `DuplicateEnforcementAction` (and the real-DB backstop is exercised in Chunk 17);
- **separation of duties:** the proposer approving their own non-warning action → `SeparationOfDutiesViolation`; an approver who is the subject → `CaseNotFound`; a reviewer (without the approve permission) cannot approve, and **`ADMIN` cannot propose** (no review permission);
- **applied means confirmed:** an enforcer that succeeds → `APPLIED` with `applied_at`; an enforcer raising `TransientEnforcementError` → the action stays `APPROVED`, never `APPLIED`, `attempts` incremented, `next_attempt_at` per the backoff, a history row written, and the use case returns normally; `PermanentEnforcementError` → `FAILED` immediately; attempts reaching the max → `FAILED` with an ERROR log; a worker run before `next_attempt_at` skips the row, after it retries;
- **idempotent reference:** every enforcer call receives `reference == action id`, identical on every retry; **a retry after a simulated crash** (the fake enforcer succeeds, then the commit fails) re-sends the same reference and ends with exactly one `APPLIED` and a downstream fake that applied it once;
- reversal mirrors it (`REVERSAL_PENDING` → `REVERSED`/`REVERSAL_FAILED`), including a lift that reports "nothing to lift" treated as success; `WARNING` cannot be reversed; expiry marks `EXPIRED` and publishes `RESTRICTION_LIFTED` once;
- `--requeue-failed` returns `FAILED`/`REVERSAL_FAILED` to `APPROVED`/`REVERSAL_PENDING` with attempts reset, and touches nothing else;
- notifications: each kind published exactly once on its transition, **not** on a failed or retried attempt before success, and a raising bus never changes the result;
- the debug flag is **ignored** when `app_env="staging"`; the worker's own `main()` tested for default, `--stats`, `--requeue-failed`.

**Acceptance criteria:** tests pass against fakes; no framework imports under `application/`; **no use case in this module imports an enforcer's concrete adapter** (only ports).

---

### CHUNK 14 — NOTIFICATION AMENDMENT: THE SAFETY KINDS
**[FOR YOU — GEMINI CLI]**

**Objective:** Notification learns to render `SafetyUpdatePublished`. **Notification's existing behavior and tests must not change.** Read **Part C14** and Module 12's C12 rulebook (Notification's `domain`/`application` still import nothing from any other module; only `adapters/events/` imports T&S's `application/ports/events.py`).

Implement C14: the `SAFETY` category; the six `NotificationType`s with the fixed templates; the two `TargetType`s; the strict parser for the event's payload; the recipient policy (recipient = the event's `recipient_id`; kind → type; target from the reference); the migration altering the three `CHECK`s (**read it**; `downgrade` restores them); subscriber registration (the seventh supported event) through the existing `register_notification_subscribers`; the `event_to_payload` conversion for the new event. Update the Notification module doc's event table only if Chunk 19 asks.

**Tests:** each of the six kinds → one notification for `recipient_id` with the **exact** C14 title/body, correct type, category and target; templates contain no id, name, or event field text; an unknown `kind` or malformed payload → `REJECTED`; a duplicate event creates **no** second notification; `SAFETY` types do **not** collapse; the migration round-trips and the old types still insert; **the full end-to-end:** with the real bus factory, publish each kind from T&S's real use cases (fakes for downstream) and see the notification appear for the right user and **nobody else**; an existing Notification event (e.g. `MessageCreated`) still works; Notification's `domain`/`application` still import nothing from other modules.

**Acceptance criteria:** new tests pass; Notification's **entire** suite, Booking's, Verification's, Messaging's suites unaffected; `lint-imports` clean.

---

### CHUNK 15 — HTTP API: REPORTERS
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/api/schemas.py`, `reporter_router.py`, `dependencies.py`; `app.py` (mount under `/api/v1/safety`).

| Method | Path | Success |
|---|---|---|
| POST | `/safety/reports` | `201` new / `200` replay — body below |
| GET | `/safety/reports/mine` | `200`, paginated |
| GET | `/safety/reports/{report_id}` | `200` — own reports only |

Body: `{"idempotency_key": "…", "category": "…", "description": "…", "subject": {"type": "LISTING", "id": "…"}}`, or `{"type": "BOOKING", "id": "…"}`, or `{"type": "CONVERSATION", "id": "<conversation id>", "message_ids": ["…"]}`. `extra="forbid"` everywhere — a `reporter_id`, `subject_user_id`, `status`, or `priority` field → `422`. `/mine` registered before `/{report_id}`. All routes use the shared `get_current_identity_id`; authorization is in the use cases. Response schemas are built from `ReporterReportView`/`ReportAck` only. **No reviewer functionality on these routes.**

**Tests (real HTTP; Chunk-9 behaviors end to end with real Housing/Booking/Messaging data):** unauthenticated → `401` on every route; a user with no profile → `403`; valid reports on a listing, on a booking, and on selected messages → `201` with the ack and **nothing but** `report_id`, `status`, `created_at`; replay → `200` same id; conflicting body → `409 idempotency_key_conflict`; duplicate open → `409 duplicate_open_report` with the caller's own id; a second reporter on the same listing → `201`; the sixth report in a window → `429` with `Retry-After`; **a request body naming a reporter or subject user → `422`**; invalid category/subject/ids → the standard error shape with the generic `invalid_report_subject`; reporting a conversation you're not in, a booking you're not party to, and a message that is yours → all `422 invalid_report_subject`, **byte-identical** responses; `GET /mine` shows only your reports with the coarse status and **no** case, priority, assignee, or subject-user field (assert the key set); another user's report id → `404` byte-identical to a random id; a **reported user** has no route that shows them anything (route-table assertion); the report appears for a reviewer later (Chunk 16).

**Acceptance criteria:** app starts; tests pass; `lint-imports` clean; other modules' suites unaffected.

---

### CHUNK 16 — HTTP API: REVIEWERS & APPROVERS
**[FOR YOU — GEMINI CLI]**

**Files:** `adapters/api/review_router.py`; schemas; `app.py` (mount under `/api/v1/safety/review`).

| Method | Path | Notes |
|---|---|---|
| GET | `/review/reports` | the unlinked queue; `category`, `status` filters; paginated |
| POST | `/review/reports/{report_id}/open-case` | `201` |
| GET | `/review/cases` | `status`, `priority`, `assigned_to`, `category`; paginated |
| GET | `/review/cases/{case_id}` | reviewer **or** approver view by permission |
| POST | `/review/cases/{case_id}/reports` | body `{report_id}` — link |
| POST | `/review/cases/{case_id}/triage` | `{priority, reason?}` |
| POST | `/review/cases/{case_id}/assign` | `{assignee_id}` |
| POST | `/review/cases/{case_id}/status` | `{to_status, reason?}` — every transition in C6, including resolve, close, reopen |
| GET | `/review/cases/{case_id}/evidence/{evidence_id}` | restricted content; audited |
| POST | `/review/cases/{case_id}/notes` | `{kind, content, cited_evidence_ids, corrects_note_id?}` |
| GET | `/review/cases/{case_id}/history` | paginated |
| POST | `/review/cases/{case_id}/decisions` | `{decision_type, rationale, cited_evidence_ids, cited_note_ids}` |
| POST | `/review/cases/{case_id}/enforcement` | propose |
| POST | `/review/enforcement/{action_id}/approve` | |
| POST | `/review/enforcement/{action_id}/reject` | `{reason}` |
| POST | `/review/enforcement/{action_id}/reverse` | `{reason}` |

`extra="forbid"`; no business logic in routers; list responses carry **metadata only**, never evidence content or note text beyond the documented fields; every route authenticated, authorization inside the use cases. `ConflictOfInterest`-style cases surface as the ordinary `404 case_not_found`.

**Tests (real HTTP, real database; accounts for reporter, subject, reviewer (`OPERATIONS`), approver (`ADMIN`), and an `OPERATIONS` account without the evidence permission):** the whole lifecycle end to end — report → queue → open case → triage → assign → in review → note (corroborated fact) → decision → propose → approve → applied (against the **real** Housing/Messaging/Identity amendments) → resolve → close, checking at each step the state, the history rows, and the notifications; every route returns `401` unauthenticated and `403`/`404` for a user without the right permission, **including an `ADMIN` on every reviewer-only route and an `OPERATIONS` on every approver-only route**; a **reporter**, a **student**, and the **reported user** all get `403` on the whole `/review` namespace; the reviewer who is the subject or a reporter gets `404` everywhere; the approver view has no notes/evidence/reporter ids; evidence content needs both permissions and **each view adds a history row** visible in `/history`; approve-your-own-proposal → `403 separation_of_duties_violation`; illegal transitions → `409 invalid_case_transition`; stale concurrent updates → `409 case_state_changed`; validation errors in the standard shape; pagination on queue, cases, history.

**Acceptance criteria:** app starts; tests pass; **the route table audit**: every route under `/review` appears in a written list in the report and none exists outside the two namespaces.

---

### CHUNK 17 — RELIABILITY & CONCURRENCY
**[FOR YOU — GEMINI CLI]**

**Objective:** prove the guarantees on a real database, with the real Housing, Messaging and Identity amendments where they matter. Mostly tests; fix whatever they reveal. Every test file runs **three times in a row**.

**Tests** (`tests/integration/trust_safety/test_reliability.py`, committed data, `asyncio.gather`):
- **duplicate report submissions:** 10 concurrent identical submissions (same idempotency key) → exactly one report, one set of evidence, one `REPORT_RECEIVED`; 10 concurrent with *different* keys on the same triple → exactly one report, the rest `409 duplicate_open_report`;
- **rate-limit race:** concurrent submissions from one reporter overshoot the limit by **at most the concurrency window** and never leave the system unable to enforce it afterwards (assert the final count and that the next submission is refused) — the documented tolerance;
- **concurrent status changes:** two reviewers move one case at once → exactly one succeeds, the other gets `case_state_changed`, the history shows exactly one transition;
- **concurrent final decisions:** exactly one per cycle (also proven in Chunk 12 — re-assert on the full stack);
- **two workers:** ten `APPROVED` actions, two worker runs at once → each applied exactly once downstream (assert against the real Housing/Messaging state and a recording Identity), none missed, none double-applied;
- **crash between downstream success and local record:** run a real suspension where the commit of `APPLIED` is made to fail once → the listing **is** `SUSPENDED`, the action is still `APPROVED`; the next worker run re-sends the same reference and the action becomes `APPLIED` with the listing unchanged (idempotent) — **exactly the handoff's 16.4.6 case**;
- **downstream unavailable:** with the failure switch on, approving returns normally, the action is `APPROVED` with `attempts ≥ 1`, **nothing is applied downstream**; switch off, worker → applied once; exhausted attempts → `FAILED` after exactly the configured number and `--requeue-failed` recovers it;
- **reversal on the real stack:** reverse an applied listing suspension → listing `UNAVAILABLE`, owner able to republish through normal rules; reverse an applied communication restriction → the user can send again; an expired restriction is marked `EXPIRED` by the worker and Messaging had already stopped enforcing it;
- **duplicate enforcement:** concurrent identical proposals → exactly one live action;
- **audit consistency:** after the full lifecycle, every transition, note, decision, enforcement step and evidence view has exactly one history row, in order, and a forced failure of any history write rolls back its state change (inject a failing history repository once per kind of change);
- **immutability under the application:** attempts to `UPDATE`/`DELETE` evidence, notes, decisions and history through the ORM fail loudly (trigger), and no code path tries;
- **producer isolation:** with Notification's processing failing (its debug switch) and the event bus raising, every T&S operation still succeeds and persists.

**Acceptance criteria:** all pass **three consecutive runs**; any defect is fixed in the responsible layer (never patched in a test) and noted in the report.

---

### CHUNK 18 — SECURITY, PRIVACY & REGRESSION SWEEP
**[FOR YOU — GEMINI CLI]**

**Files:** `tests/api/trust_safety/test_safety_security.py`; `pyproject.toml` import-linter contracts.

- **Authorization matrix:** for every route in both namespaces, a parametrized test over {unauthenticated, student, scout, operations-with-evidence, operations-without-evidence, admin, reported user, reporter-on-the-case, subject-on-the-case} asserting the exact expected status; **an `ADMIN` can never read a note or evidence content**; **an `OPERATIONS` can never approve**.
- **Privacy:** across the whole flow, no response and no log line contains the description, message content, note text, rationale, reporter id (outside reviewer views), or `subject_user_id` (outside reviewer views); a reporter's responses never contain case/priority/assignee/decision/enforcement fields; notifications contain only the fixed templates; the reported user learns of enforcement **only** through the fixed notification text and never of the report or reporter.
- **Existence leaks:** every `404` pair (nonexistent vs unauthorized) is byte-identical across report, case, evidence and action routes.
- **No derived guilt:** an end-to-end test files 20 reports from distinct reporters against one listing and asserts the system **still** has no finding, no enforcement, and no state beyond `RECEIVED` until a reviewer acts.
- **Boundaries:** T&S has no write path to Housing, Messaging, Identity or Payment data other than the three enforcers (source scan of imports and SQL); **Payment's tables are never referenced**; no financial field exists anywhere in the module.
- **Import-linter contracts** (extend the existing list): T&S `domain`/`application` import no other module and no `fastapi`/`sqlalchemy`; only `adapters/` import other modules' `application/ports` (and `ports/events.py`); **no other module imports `camp_match.modules.trust_safety`**; Housing, Messaging and Notification gain no T&S import. **Deliberately violate each once** (e.g. Messaging importing a T&S symbol; T&S's `application` importing Housing), confirm `lint-imports` fails, remove.
- **Full regression:** `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports` across **all thirteen modules**; then re-run Security's, Identity's, Housing's, Search's, Booking's, Messaging's (WebSocket files three times), Notification's, Verification's, and Payment's suites in isolation and confirm they are unchanged apart from the documented amendments.

**Acceptance criteria:** every test passes; no skipped or known-failing test.

---

### CHUNK 19 — DOCUMENTATION, MANUAL GUIDE & AI STATE
**[FOR YOU — GEMINI CLI — Part G at the end of this file is the source for the manual testing document]**

1. Write `docs/modules/trust_safety.md` per `09_DOCUMENTATION_RULES.md`, covering every item in the handoff's Section 18: purpose and exclusions; domain model; categories and submission rules; the case lifecycle table (C6); triage and priority; assignment and permissions; evidence provenance and access; decisions; the enforcement state machine (C7) **and its full recovery table**; integration contracts for Identity, Housing, Messaging, Notification, Security (with the four amendments and why each exists); notification behavior (C9, C14); persistence and transaction boundaries; the append-only guarantees; security and privacy (C8, C1); retention (**an unresolved product decision — no deletion exists**); API; configuration (C10); commands; manual testing; limitations; extension points for appeals and a later shared outbox.
2. **Known limitations, listed plainly and individually:** no appeals; no investigator-attached or file evidence; no user-level or anonymous reports; no retention/purge; `ACCOUNT_SUSPENSION` reversal can re-enable an account an administrator separately disabled (C7); safety notifications are at-most-once across a crash between commit and publish (ADR-161); the reporter has no way to add information after submitting; reviewers use a minimal API, there is no dashboard (Admin & Operations does not exist); report-rate limiting can overshoot by the size of a concurrency window (ADR-158); payment concerns are recorded and referred but **no financial action exists**; the worker is run by hand or cron; the new `SUSPENDED` listing status must be handled by every frontend.
3. Create `docs/modules/trust_safety_manual_testing.md` from Part G, **running every command you document** and correcting any that doesn't work.
4. Update the Housing, Messaging, Notification and Security module docs with a short "Safety integration" section each (what was added, why, which T&S call uses it). Update the frontend API reference location **only with a pointer** — Nsisong maintains the Front End Doc from Part F.
5. Update `AI_state/`: all the standard files; `ARCHITECTURE_STATE.md` (the first module needing four amendments; enforcement as a distributed state machine; append-only triggers); `DATABASE_STATE.md` (eight tables, plus the amendment tables/columns, migrations); `API_STATE.md`; `DECISIONS.md` (append ADR-144–161); `SESSION_HANDOFF.md`; `CURRENT_TASK.md`.

**Acceptance criteria:** every document exists and matches the implementation; every documented command was executed; limitations stated without softening.

---

### CHUNK 20 — FINAL AUDIT & COMPLETION REPORT
**[FOR YOU — GEMINI CLI]**

1. From a clean state (`scripts/db_stop.sh`, `scripts/db_start.sh`, `poetry run alembic upgrade head`) run the full four-command suite; then re-run **every concurrency/reliability file three times** as the last step.
2. Answer each plainly — not "done":
   - Can any code path mark an enforcement action `APPLIED` without the owning module's success? **yes/no, with the evidence.**
   - Can any code path create a finding, a violation, or a substantiated state from reports, counts, categories, or priority alone? yes/no.
   - Can any evidence, note, decision, or history row be changed or deleted — by application code or by SQL? yes/no (the trigger tests).
   - Can any actor touch a case they are the subject or a reporter of? yes/no.
   - Can an `ADMIN` read a note or evidence content; can an `OPERATIONS` account approve? yes/no.
   - Does any state change exist without its history row, or the reverse? yes/no.
   - Does any T&S code write another module's data other than through the three enforcers? yes/no.
   - Does any module import Trust & Safety, or does T&S's `domain`/`application` import another module? yes/no (import-linter).
   - Does any log or non-reviewer response contain description, message content, note text, rationale, reporter or subject-user ids? yes/no.
   - Did Housing's, Messaging's, Notification's or Security's behavior change in any way other than the documented amendments? yes/no, with evidence.
3. **Readiness classification — do not round up:**
   - Reporting, triage, investigation, decisions, audit: implemented? yes/no.
   - Enforcement applied through Identity, Housing, Messaging: implemented? yes/no per owner.
   - Payment/escrow action: **not implemented** (ADR-153).
   - Appeals, investigator-attached evidence, file evidence, user-level and anonymous reports, retention: **not implemented** (ADR-160).
   - Safety notifications: **tier-2** (at-most-once across a crash).
   - Reviewer tooling: **minimal API only**; no dashboard.
4. Report: completed requirements; every command and its real result; known limitations; unresolved decisions (including the retention policy and the role-mapping confirmation); the exact recommended next step. **Do not claim completion for anything unimplemented or unverified.** Set `CURRENT_TASK.md` to "Trust & Safety complete. Awaiting next module specification from Claude."

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

### The handoff's chunk sequence → this document
| Handoff chunk | Here | Note |
|---|---|---|
| 1 Inspection | Chunk 1 | adds checks that Modules 11 and 12 exist as specified |
| 2 Domain and policies | Chunks 2–3 | Chunk 2 is the Security permissions the domain's rules rely on |
| 3 Public contracts and ports | Chunks 4, 8 | ports and DTOs, then the adapters to other modules |
| 4 Persistence and auditability | Chunk 5 | adds database-level immutability triggers |
| 5 Report intake | Chunk 9 | |
| 6 Case creation and association | Chunk 10 | merged with 7 |
| 7 Triage, assignment, lifecycle | Chunk 10 | |
| 8 Evidence and notes | Chunk 11 | |
| 9 Decisions and enforcement | Chunks 12–13 | |
| 10 Integration with other modules | Chunks 6, 7, 8, 14 | **four amendments**: Housing, Messaging, (Security in 2), Notification — see Findings 3–5 |
| 11 Reliability and security hardening | Chunks 17–18 | |
| 12 API completion | Chunks 15–16 | reporter routes, then the review namespace |
| 13 Automated tests and regression | tests live in every chunk; Chunks 17–18 complete them | |
| 14 Documentation and project state | Chunk 19 | |
| 15 Final audit | Chunk 20 | |

### The handoff's Section 16 tests → where each is proven
| Handoff item | Where |
|---|---|
| 16.1 intake (1–10) | Chunk 9 (fakes), Chunk 15 (HTTP); rate limit also Chunk 17 |
| 16.2 lifecycle (1–10) | Chunks 10, 12, 17; item 8's **appeals: not applicable** (deferred, ADR-160); reopening and escalation: Chunk 10 |
| 16.3 evidence and privacy (1–7) | Chunks 11, 16, 18 |
| 16.4 decision and enforcement (1–10) | 1–3 Chunk 12 and 18; 4–7 Chunks 13 and 17; 8 reversal history Chunks 13 and 17 (**appeals not applicable**); 9–10 Chunk 18 (source scan; Payment untouched) |
| 16.5 (1) notification contract fields | Chunks 13–14 |
| 16.5 (2) notification failure leaves the case intact | Chunk 17 |
| 16.5 (3) **duplicate events** | **Not applicable as written — T&S consumes no events** (Finding 9). The equivalent guarantees are the report idempotency key and duplicate-open rule (Chunks 9, 17) and enforcement idempotency (Chunks 13, 17) |
| 16.5 (4) public contracts only | Chunks 8, 18 |
| 16.5 (5–6) downstream failure and crash reconciliation | Chunks 13, 17 |
| 16.5 (7) pagination | Chunks 15–16 |
| 16.5 (8) no production credentials | the whole suite |
| 16.5 (9–10) existing tests pass; ordinary and privileged authorization | Chunks 6, 7, 14, 18 |
| 16.6 regression | Chunk 18 |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**Applies everywhere:** routes are under `/api/v1/safety`, authenticated with `Authorization: Bearer <access_token>`. Errors use `{"error": {"code", "message"}}`. **Two separate areas:** `/safety/reports…` is for ordinary users; **`/safety/review/…` is for Camp Match staff only** — a normal user always gets `403` there, and your normal app should never call it.

### For ordinary users

#### POST /api/v1/safety/reports
**Purpose:** report a listing, a booking, or messages in a conversation. You must be signed in and have a profile (student or scout).
**Body — pick exactly one `subject` shape:**
```json
{ "idempotency_key": "<uuid you generate>", "category": "SCAM_OR_FRAUD",
  "description": "They asked me to pay outside the app.",
  "subject": { "type": "LISTING", "id": "<listing id>" } }
```
`{"type":"BOOKING","id":"<booking id>"}` — a booking you are part of. `{"type":"CONVERSATION","id":"<conversation id>","message_ids":["…"]}` — **1 to 5 messages** from the other person in a conversation you are in.
**Categories:** `SCAM_OR_FRAUD`, `MISLEADING_LISTING`, `HARASSMENT`, `IMPERSONATION`, `PAYMENT_CONCERN`, `THREAT_OR_DANGER`, `OTHER`. `description`: 10–2000 characters.
**You never say who is being reported.** The server works that out from the listing, booking or messages. Sending any extra field (like `reporter_id`) returns `422`.
**Success:** `201` — `{"report_id", "status": "Received", "created_at"}`. Nothing more is shown on purpose. **Reuse the same `idempotency_key` if you retry** after a timeout — you'll get `200` and the same report, never a duplicate.
**Errors:** `403` (no profile) · `409 idempotency_key_conflict` (same key, different content) · `409 duplicate_open_report` (you already have an open report on this same thing in this category — the response includes your existing report's id) · `422 invalid_report_subject` (the one message for **every** problem with the subject — it doesn't say why, deliberately) · `422 invalid_report_description` · `429 rate_limit_exceeded` (default 5 reports per 24 hours; honor `Retry-After`).
**Privacy to tell your users:** the messages you select are copied and shared with Camp Match's safety team so they can review them. Only the messages you select — not the rest of the conversation.

#### GET /api/v1/safety/reports/mine · GET /api/v1/safety/reports/{report_id}
Your own reports only. Each: `{id, category, subject_type, subject_id, description, status, created_at}`. **`status` is one of three words:** `Received`, `Under review`, `Reviewed`. It never says whether anything was found — "Reviewed" just means the team has finished looking. Another person's report id returns `404`, the same as an id that doesn't exist.

#### What users learn, and what they never learn
- The **reporter** gets a notification when the report is received and another when it has been reviewed (both generic text; see below). They never see who was reported, what was decided, or what action was taken.
- The **reported person has no screen and no endpoint for any of this** and is never told a report exists or who made it. If an action affects them they get a short fixed notice (warning, messaging restricted, listing suspended, restriction lifted) and "contact support" — nothing more.

#### Changes elsewhere in the app you must handle
- **Notifications** (the existing `/notifications` endpoints) gain six types, category `SAFETY`: `safety.report_received`, `safety.report_reviewed`, `safety.warning_issued`, `safety.communication_restricted`, `safety.listing_suspended`, `safety.restriction_lifted`. Targets can now be `SAFETY_REPORT` (open "my reports") or `LISTING`.
- **Listings** have a new status, **`SUSPENDED`**. A provider sees it on their own listing; they **cannot** publish, unpublish or archive it, and it is not shown in search or bookable. When the suspension is lifted the listing returns as `UNAVAILABLE` and the provider can publish it again through the normal steps. Show a clear "suspended — contact support" state.
- **Messaging:** `403 communication_restricted` on creating a conversation or sending can now also mean a safety restriction (it can be temporary — it ends on its own). Reading existing conversations still works; show the read-only state. The error text is deliberately generic.

### For Camp Match staff only — `/api/v1/safety/review/…`
*(Build these into an internal staff tool, not the public app. Roles: **reviewer** = `OPERATIONS`; **approver** = `ADMIN`; reading restricted evidence needs a reviewer who also has the evidence permission.)*

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/review/reports` | reviewer | unlinked reports; threats first, then oldest; each shows `similar_report_count` (a hint, never an automatic merge) |
| POST | `/review/reports/{id}/open-case` | reviewer | turn a report into a case |
| GET | `/review/cases` | reviewer | list; filter `status`, `priority`, `assigned_to`, `category` |
| GET | `/review/cases/{id}` | reviewer **or** approver | **different content per role** — reviewers get notes, reporters, evidence *metadata*; approvers get a summary, decisions with rationale, and enforcement actions only |
| POST | `/review/cases/{id}/reports` | reviewer | link another report: `{report_id}` |
| POST | `/review/cases/{id}/triage` | reviewer | `{priority, reason?}` (`reason` required for `HIGH`/`URGENT`) |
| POST | `/review/cases/{id}/assign` | reviewer | `{assignee_id}` (must be a reviewer) |
| POST | `/review/cases/{id}/status` | reviewer / approver | `{to_status, reason?}` — all moves in the lifecycle below |
| GET | `/review/cases/{id}/evidence/{evidence_id}` | reviewer with evidence permission | the restricted content; **every view is recorded** |
| POST | `/review/cases/{id}/notes` | reviewer | `{kind, content, cited_evidence_ids, corrects_note_id?}`; notes can't be edited or deleted — correct with a new note |
| GET | `/review/cases/{id}/history` | reviewer | the permanent audit trail, paginated |
| POST | `/review/cases/{id}/decisions` | reviewer (approver if `ESCALATED`) | `{decision_type, rationale, cited_evidence_ids, cited_note_ids}` |
| POST | `/review/cases/{id}/enforcement` | reviewer | propose `{action_type, …}`; a `WARNING` takes effect at once |
| POST | `/review/enforcement/{id}/approve` · `/reject` · `/reverse` | approver | approve (not your own proposal), reject `{reason}`, reverse `{reason}` |

**Case statuses:** `OPEN` → `TRIAGED` → `IN_REVIEW` ⇄ `AWAITING_INFORMATION`; `ESCALATED` (needs a reason; moving back needs an approver); `RESOLVED` (needs a final decision); `CLOSED` (blocked while any action is waiting or failed); reopening is allowed with a reason. **Decision types:** `NO_VIOLATION_ESTABLISHED`, `INSUFFICIENT_EVIDENCE`, `VIOLATION_ESTABLISHED` (must cite at least one `CORROBORATED_FACT` note), `REFERRED`, `FURTHER_INVESTIGATION_REQUIRED`. **Enforcement statuses:** `PROPOSED`, `APPROVED` (authorized, not yet in effect — may be retrying), `APPLIED` (**the other module confirmed it**), `FAILED`, `REJECTED`, `REVERSAL_PENDING`, `REVERSAL_FAILED`, `REVERSED`, `EXPIRED`. Show `APPROVED` as "pending," never as "done."

**Staff-tool errors to handle:** `404 case_not_found` (also returned if you are the subject or a reporter of that case), `409 invalid_case_transition`, `409 case_state_changed` (someone else changed it — reload), `409 duplicate_enforcement_action`, `403 separation_of_duties_violation`, `422 transition_requirement_not_met`, `422 invalid_decision`.

```js
async function report(listingId, text) {
  const key = crypto.randomUUID();                // keep this if you must retry the same report
  const r = await fetch('/api/v1/safety/reports', { method: 'POST',
    headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ idempotency_key: key, category: 'SCAM_OR_FRAUD', description: text,
                           subject: { type: 'LISTING', id: listingId } }) });
  if (r.status === 409) { const e = (await r.json()).error; /* duplicate_open_report: you already reported this */ }
  if (r.status === 429) { /* too many reports today — read Retry-After */ }
  return r.ok ? (await r.json()).report_id : null;
}
```
**Known limitations (tell your product people):** no appeals; no way for a reporter to add information after reporting; no photo or file evidence; no reporting a person directly (report the listing, booking or messages that show the problem); no anonymous reports; safety notifications can very rarely be missed if the server fails at the wrong instant; no staff dashboard yet.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — and Gemini's source for the manual-testing document in Chunk 19]

**Preconditions:** `scripts/db_start.sh` running; app running; Modules 5, 9, 11, 12 working. Accounts: **Ada** and **Chidi** (Students, reporters), **Bola** (Scout; owns a `PUBLISHED` listing and has a conversation with Ada, so Ada can see messages from Bola), **Rita** (`OPERATIONS` — reviewer), **Ade** (`ADMIN` — approver), **Dual** (both `OPERATIONS` and `ADMIN`, for the four-eyes test). Assign roles with the project's role-assignment script *(Gemini verifies the exact command and writes it down)*. Keep each person's access token. `curl` with `Authorization: Bearer <token>`. Anything marked **(Gemini verifies)** is a table, column, or argument Gemini must confirm in Chunk 19 — the guide may contain only commands that were actually run.

Format: **verifies** · **why** · **steps** · **expect** · **if it fails**.

**S1 — A student reports a suspicious listing.** *Verifies:* a report is accepted and acknowledged, and nothing is concluded. *Why:* reports are allegations. *Steps:* Ada `POST /safety/reports` (category `SCAM_OR_FRAUD`, subject = Bola's listing, a fresh `idempotency_key`); then `GET /safety/reports/mine`; then Ada checks `GET /notifications`. *Expect:* `201` with only `report_id`, `status: "Received"`, `created_at`; the list shows the report as **Received**, with **no** case, priority, or "who was reported"; a "Report received" notification. *If it fails:* `403` → Ada has no profile; `422 invalid_report_subject` → the listing isn't visible to Ada; extra fields in the ack mean information is leaking.

**S2 — A user reports a message.** *Steps:* Bola sends Ada two messages (Module 11); Ada reports with `{"type":"CONVERSATION","id":"<conversation id>","message_ids":[<one of Bola's message ids>]}`. Then try again with **Ada's own** message id, and with a conversation Ada isn't in (use Chidi's token on Ada's conversation). *Expect:* the first → `201`; the other two → `422 invalid_report_subject` with **identical** bodies. *Why:* you can only report what you could see, and only the other person's messages. *If it fails:* any `201` for the last two is a privacy bug.

**S3 — Accepted is not investigated.** *Steps:* `GET /safety/reports/mine` after S1 and S2, without any reviewer action. *Expect:* both still **Received** — no case exists, nothing has happened to Bola (her listing is still `PUBLISHED`, she can still message). Then have Chidi file one report on the same listing from his own account. *Expect:* `201` (independent users are never blocked). *Why:* many reports don't equal guilt. *If it fails:* Bola's listing changing state on its own is blocking.

**S4 — Duplicate and flood protection.** *Steps:* repeat Ada's exact S1 request (same key) → `200`, same id; send a new key for the same listing and category → `409 duplicate_open_report` with Ada's own report id; then file reports until the 6th within a day *(Gemini verifies a quick way to vary subjects, e.g. other listings)*. *Expect:* `200`, `409`, then `429` with `Retry-After`. *If it fails:* a second report row for the same key or the same open triple means the guards are broken — blocking.

**S5 — A reviewer triages.** *Steps:* Rita `GET /safety/review/reports` (queue); `POST …/reports/{id}/open-case`; `POST …/cases/{id}/triage` with `{"priority":"HIGH"}` (expect `422` without a reason), then with a reason; `POST …/assign` to Rita; `POST …/status` `IN_REVIEW`. *Expect:* each step accepted in order; the queue shows threats first and `similar_report_count`; `GET …/history` lists every step. *If it fails:* a transition accepted out of order (e.g. `OPEN → RESOLVED`) → `409 invalid_case_transition` is the **expected** answer — if you get `200`, that's a bug.

**S6 — Unauthorized people can't open a case.** *Steps:* with the case id, try `GET /safety/review/cases/<id>` as Ada, Chidi, Bola, and Ade (`ADMIN`); try Rita's token on `…/enforcement/<id>/approve`. *Expect:* Ada/Chidi/Bola → `403`; **Ade can open the case summary but not notes or evidence**; Rita can't approve (`403`). *Why:* least privilege — an admin is not an investigator. *If it fails:* Ade reading notes or evidence content is blocking.

**S7 — Two reports, one case.** *Steps:* Rita `POST …/cases/<id>/reports` with Chidi's report; `GET` the case as Rita. *Expect:* both reports are listed, **each with its own reporter and timestamp**; linking Ada's report again → `409 report_already_linked`. *If it fails:* a lost reporter or one report replacing the other is blocking.

**S8 — Evidence is restricted and audited.** *Steps:* Rita `GET …/cases/<id>` (evidence shows **metadata only**); Rita `GET …/evidence/<message snapshot id>`; then `GET …/history`. Repeat as Ade. *Expect:* Rita sees the message text and `integrity_verified: true`; the history gains an `EVIDENCE_VIEWED` entry naming Rita and **no content**; Ade → `403`/`404`. *If it fails:* content in the case detail, or a view with no history entry, is blocking.

**S9 — Findings need corroboration; decision with rationale.** *Steps:* Rita tries a `VIOLATION_ESTABLISHED` decision with no notes → `422`; adds a `CORROBORATED_FACT` note citing the snapshot; records the decision citing that note with a rationale. *Expect:* the first fails; the second is accepted; the case is **still `IN_REVIEW`** (resolving is a separate step). *If it fails:* accepting a violation with no corroborated fact means the system treats allegation as proof — blocking.

**S10 — Four-eyes and applied enforcement.** *Steps:* Rita proposes `LISTING_SUSPENSION` for Bola's listing; Rita and Ade check the action (`PROPOSED`); **Dual** proposes another action on the same case and tries to approve it → `403 separation_of_duties_violation`; Ade approves Rita's proposal. Then check Bola's listing, try to publish it as Bola, search for it, try to book it, and check Bola's notifications. *Expect:* `APPLIED`; the listing is **`SUSPENDED`**, Bola cannot publish/unpublish/archive it, it is absent from search and unbookable, and Bola has a "Listing suspended" notice with **no mention of any report**. *If it fails:* Bola able to republish is blocking.

**S11 — Unauthorized enforcement is refused.** Covered by S6 (Rita) and S10 (Dual); also try Ada and Bola on `…/approve` → `403`.

**S12 — The responsible module is unavailable, and a retry doesn't duplicate.** *Verifies:* "applied" means confirmed. *Why:* a request is not a result. *Steps:* set `SAFETY_DEBUG_FAIL_ENFORCEMENT=true` (local only), restart; Rita proposes a `COMMUNICATION_RESTRICTION` on Bola (an `ends_at` a week out), Ade approves; check the action; have Bola send a message. Then unset the flag, restart, run `poetry run python scripts/run_safety_worker.py`; check again; run the worker a second time and `--stats`; query Messaging's restriction table *(Gemini verifies:* `select user_id, status, source_reference from messaging_restrictions`*)*. *Expect:* with the flag on, the action is `APPROVED` (not `APPLIED`), `attempts ≥ 1`, and **Bola can still message**; after the worker: `APPLIED`, Bola's next send is `403 communication_restricted` and she gets "Messaging restricted"; the second run and `--stats` change nothing; **exactly one** restriction row for that action's reference. *If it fails:* `APPLIED` while Bola can still message, or two restriction rows, is blocking.

**S13 — A reporter can't see confidential notes.** *Steps:* Ada `GET /safety/reports/<her report id>`; Ada tries `GET /safety/review/cases/<id>/history`. *Expect:* only the three-word status; `403` on the staff route. *If it fails:* any case, note, decision or enforcement field in Ada's responses is blocking.

**S14 — A notification failure doesn't lose the case.** *Steps:* set `NOTIFICATION_DEBUG_FAIL_PROCESSING=true`, restart; Chidi files a new report on a different listing; list `GET /safety/reports/mine`; unset the flag, restart, run `poetry run python scripts/run_notification_worker.py`. *Expect:* the report exists and is `Received` immediately; the "Report received" notification appears only after the worker runs. *If it fails:* the report missing or the request failing while notifications are broken is blocking.

**S15 — The audit trail is consistent and permanent.** *Steps:* `GET …/cases/<id>/history`; then try to change it directly *(Gemini verifies:* `update safety_case_events set event_type = 'x' where id = '<one id>'` *and a `delete`)*. *Expect:* every step you took appears exactly once, in order, with who did it; the direct `UPDATE`/`DELETE` **fails** with the database's immutability error. *If it fails:* a missing step, a duplicated step, or a successful edit is blocking.

**S16 — Resolve, close, and reverse.** *Steps:* Rita `POST …/status` → `RESOLVED`; Ada and Chidi check notifications; try `CLOSED` while an action is still `PROPOSED`/`FAILED` → `422`; once all are `APPLIED`, close; Ade `POST …/enforcement/<id>/reverse` with a reason; check Bola's listing and notifications; Bola publishes it again. *Expect:* both reporters get "Report reviewed" (and **nothing about the outcome**); close is blocked then allowed; reversal moves the listing to **`UNAVAILABLE`** (not `PUBLISHED`), Bola gets "Restriction lifted", and she must publish through the normal checks. *If it fails:* the listing returning straight to `PUBLISHED` is a bug.

**Intentionally absent:** appeal tests, investigator-attached or file evidence tests, user-level or anonymous report tests, retention tests (not implemented, ADR-160); a payment-action test (none exists, ADR-153).

**Automated tests:** `poetry run pytest tests/unit/trust_safety tests/integration/trust_safety tests/api/trust_safety` · fast, no database: `poetry run pytest tests/unit/trust_safety -v` · reliability, three times: `for i in 1 2 3; do poetry run pytest tests/integration/trust_safety/test_reliability.py; done` · everything: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] An enforcement action is `APPLIED` **only** after Identity, Housing or Messaging confirmed success; downstream failure leaves it `APPROVED` and retrying, never `APPLIED`; a crash between the downstream success and the local record is reconciled by an idempotent retry — proven on a real database.
- [ ] Nothing in the module can create a finding or violation from reports, counts, categories or priority; `VIOLATION_ESTABLISHED` requires cited corroborated facts; 20 reports against one listing change nothing by themselves.
- [ ] Evidence, notes, decisions and case history cannot be changed or deleted — the database triggers refuse it, and no application path tries.
- [ ] Every state change has exactly one history row, in the same transaction; evidence views are audited; a failed history write rolls the change back.
- [ ] `ADMIN` cannot read notes or evidence content; `OPERATIONS` cannot approve; non-warning enforcement needs an `ADMIN` who is not the proposer; nobody can act on a case they are the subject or a reporter of.
- [ ] A reporter sees only their own reports with a three-word status; the reported user can see nothing; every non-authorized access to a case, report, evidence or action is a `404` identical to a missing id.
- [ ] The accountable user is always derived from the resource — no client-supplied accused, no anonymous reports.
- [ ] Reported-message snapshots contain only the reported messages, are hash-verified, restricted, and appear nowhere in lists, logs, notifications or error bodies.
- [ ] Housing's `SUSPENDED` state cannot be undone by the listing's owner, is excluded from search, booking and new conversations, and lifts to `UNAVAILABLE`.
- [ ] Messaging's restriction blocks sending and starting conversations (HTTP and WebSocket, including a restriction applied after connecting), leaves reading intact, and expires on its own.
- [ ] Safety notifications are fixed templates with no case, reporter, note, decision or priority; Notification's `domain`/`application` still import nothing from other modules.
- [ ] No module imports Trust & Safety; T&S's inner layers import no other module — both contracts proven with deliberate-violation checks.
- [ ] Housing, Messaging, Notification and Security changed only as documented; Payment, Booking, Verification, Identity, Profile, Search, Media/File untouched; all thirteen modules' suites pass.
- [ ] `docs/modules/trust_safety.md`, the manual guide and `AI_state/` are written; every documented command was run; limitations are stated without softening — especially: no appeals, no investigator-attached or file evidence, no retention policy, no payment action, at-most-once safety notifications, minimal staff API.
- [ ] The Chunk 20 readiness classification is recorded honestly.
