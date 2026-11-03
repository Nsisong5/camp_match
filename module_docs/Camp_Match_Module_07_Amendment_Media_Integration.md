# CAMP MATCH — MODULE 07 AMENDMENT: MEDIA/FILE INTEGRATION
**Applies to:** `Camp_Match_Module_07_Verification_Inspection_Specification.md`
**Status:** Verification & Inspection has not been implemented yet. This amendment is not a migration to apply later — it replaces the affected sections of the original spec *before* Gemini starts Chunk 1. Hand Gemini this document alongside the original; where they conflict, this one wins.

---

## HOW TO READ THIS DOCUMENT

This is a patch, not a rewrite. Everything in the original Module 07 specification still applies except what's explicitly changed below. Section headers below match the original document's chunk numbers so you can find exactly what to swap out. **[FOR YOU — GEMINI CLI]** / **[FOR NSISONG]** conventions are unchanged.

---

## WHAT CHANGED AND WHY [FOR NSISONG]

The original Module 07 spec stored evidence as a bare `media_reference` string (its ADR-069), because at the time, Media/File didn't exist — that was the deliberate, honest placeholder Finding 1 flagged. It now exists (Module 06B). This amendment retires that placeholder and wires evidence to real, access-controlled files from the start, so Verification is built once, correctly, not built with a stub and migrated later.

One more thing surfaced while writing this — not a Media/File consequence, a real gap in the original spec's own design, worth being upfront about: **the original `AddEvidence` only authorized the case's owner (the Scout) to submit evidence.** That's wrong on inspection — an inspector clearly needs to submit photographs *they* took, not the property owner. This amendment fixes that too, since it's the same use case being touched anyway.

### NEW DECISIONS (ADR-086 … ADR-088) [FOR NSISONG]

Continuing the log — Media/File (Module 06B) ended at 085.

| ADR | Decision | Why |
|---|---|---|
| 086 | `Evidence.media_reference` (bare string) becomes `Evidence.media_id` (a real `EntityId` referencing Media/File) — retires Module 07's original ADR-069 | The upload endpoint now accepts the file directly; a client never supplies a pre-existing reference string, closing the "attach someone else's upload" risk by the same structural means Media/File's own ADR-079 describes, now with a real caller exercising it. |
| 087 | A genuinely new capability, `GetEvidenceAccess`, is added — not present in the original spec, since there was no real file to protect access to at the time | Verification does its own authorization (case owner, currently-assigned inspector, or `VERIFICATION_REVIEW`), exactly matching the original handoff's Part 26, then asks Media/File in-process for a short-lived grant. |
| 088 | `AddEvidence`'s authorization now also accepts the case's currently-assigned inspector (via `VERIFICATION_INSPECT`, ownership-scoped), not only the case's `submitted_by` | A real gap in the original spec, found while wiring this amendment, not a Media/File-specific change — an inspector could never have submitted their own inspection photographs under the original design. |

---

## PATCH — DOMAIN MODEL (replaces part of the original Chunk 2)
**[FOR YOU — GEMINI CLI]**

In `domain/entities.py`, the `Evidence` entity's field list changes:

**Remove:** `media_reference: str`.
**Add:** `media_id: EntityId` (permanent, same immutability rule as before — set once at construction, never reassigned).

Nothing else about `Evidence` changes — `review_status`/`review_notes` remain the only mutable fields, with the same before-decision-only constraint.

**Tests to update:** `tests/unit/verification/domain/test_evidence.py` — replace any reference to `media_reference` with `media_id`; no new test cases needed here, the existing ones (review-status mutability, immutability after decision) apply unchanged to the renamed field.

---

## PATCH — EVIDENCE & PROVENANCE (replaces the original Chunk 5 in full)
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/add_evidence.py`, `application/use_cases/review_evidence.py`, `application/use_cases/get_evidence_access.py` (new).
**Files to modify:** `application/ports/outbound.py` — add `MediaProvider` (below).

**`MediaProvider`** (this module's own outbound port, mirroring the established in-process-adapter pattern used for every other cross-module dependency in this project): `upload(purpose: str, content: bytes, content_type: str, uploaded_by: EntityId) -> EntityId` (returns the new `media_id`), `get_access(media_id: EntityId) -> AccessGrant`. Implemented in Chunk 9 (below) via `InProcessMediaProvider`, calling Media/File's `UploadMedia`/`GetAuthorizedAccess` use cases directly — never Media/File's `adapters`/`domain`.

**`AddEvidence` — steps, revised:**
1. Look up the case; confirm it's not in a terminal state.
2. **Authorize — either of two paths now, not one (ADR-088):**
   - The caller is the case's `submitted_by`, checked via `VERIFICATION_MANAGE` (ownership-scoped, same as before), **or**
   - The caller is the `inspector_id` on the case's current (non-terminal) `Inspection`, if one exists, checked via `VERIFICATION_INSPECT` (ownership-scoped).
   - Neither matching raises `Forbidden`, same as before.
3. Call `MediaProvider.upload` with `purpose="VERIFICATION_EVIDENCE"`, the uploaded file's bytes/content-type, `uploaded_by=caller's identity_id`. **Content-type and size validation happen inside Media/File** (its own Chunk 5) — this use case does not duplicate that logic, it just handles what Media/File's errors mean in Verification's context: a `MediaTooLarge`/`UnsupportedMediaType` from Media/File propagates as the equivalent Verification-level `InvalidVerificationTransition`-adjacent 422, not a 500.
4. Construct the `Evidence` record with the returned `media_id`; if the caller was the inspector (path 2 above), set `inspection_id` to the current inspection's id — otherwise leave it null.
5. Persist; record history; log INFO (`"evidence_added"`, case id, evidence type, **and now also confirm no `media_id` or any Media/File-internal detail beyond the bare fact of success appears in the log line** — same privacy discipline as the original chunk, extended to cover the new upload step).

**`ReviewEvidence`** — unchanged from the original spec.

**`GetEvidenceAccess`** (new, ADR-087) **— steps:** look up the evidence and its case; authorize: `ALLOWED` if the caller is the case's `submitted_by`, **or** the case's currently-assigned inspector, **or** holds `VERIFICATION_REVIEW` (role-scoped) — anything else, `Forbidden`; call `MediaProvider.get_access(evidence.media_id)`; return the grant. Log at INFO who accessed which evidence record (case id, evidence id, accessing identity) — this is a genuinely sensitive action worth its own audit trail line, distinct from the general privacy discipline that forbids logging the file's *content*.

**Tests you must write:** revise `tests/unit/verification/application/test_add_evidence.py` to cover both authorization paths (case owner succeeds; assigned inspector succeeds; an unrelated `OPERATIONS` account without the case's specific inspection assignment fails; a Student with neither role fails) and the Media/File error-translation case (a fake `MediaProvider` configured to reject an oversized/wrong-type file surfaces as a 422-appropriate error, not a 500). Add `tests/unit/verification/application/test_get_evidence_access.py` covering all three allowed-caller cases and the disallowed case, against a fake `MediaProvider`.

**Acceptance criteria:** new/revised tests pass, all against fakes — no real Media/File code executed at this layer.

---

## PATCH — PORTS (extends the original Chunk 9)
**[FOR YOU — GEMINI CLI]**

Add `MediaProvider` (defined above) to the outbound port list. Add `GetEvidenceAccess` to the inbound port list, same `Protocol`-with-`execute` convention as every other use case in this module.

---

## PATCH — PERSISTENCE (replaces one column in the original Chunk 10)
**[FOR YOU — GEMINI CLI]**

In the `verification_evidence` table: **`media_reference text not null` becomes `media_id UUID not null`** — no foreign key into Media/File's `media_files` table, same cross-module reference discipline as every other cross-module id in this project (`target_id`, `submitted_by`, etc.).

**Files to create:** `adapters/media/media_provider.py` — `InProcessMediaProvider` implementing `MediaProvider`, constructed with references to Media/File's `UploadMedia` and `GetAuthorizedAccess` use case instances. Imports only Media/File's `application.ports`, never its `adapters`/`domain`.

**Tests you must write:** `tests/unit/verification/adapters/test_media_provider.py` — mirrors every other in-process adapter test in this project (fake underlying use case, confirm correct mapping and error propagation).

---

## PATCH — API (extends the original Chunk 11)
**[FOR YOU — GEMINI CLI]**

**`POST /api/v1/verification/cases/{id}/evidence` changes shape:** was JSON (`{evidence_type, media_reference, source_description, captured_at}`); **now multipart** — the file itself, plus `evidence_type`, `source_description` (optional), `captured_at` (optional) as form fields. Authorization is now checked as described in the patched `AddEvidence` above (case owner **or** assigned inspector), not owner-only.

**New endpoint:** `GET /api/v1/verification/evidence/{evidence_id}/access` — authenticated, authorization per `GetEvidenceAccess` above (not a fixed permission — the three-way check happens inside the use case). Response: `{ "stream_path": "..." }` (Media/File's signed streaming path).

---

## PATCH — FRONTEND DOCUMENTATION [FOR NSISONG — replaces the original evidence-endpoint entry]

### POST /api/v1/verification/cases/{id}/evidence
**Authorization:** the case's owner, **or** the inspector currently assigned to it.
**Request:** multipart — file (image or PDF, per Media/File's `VERIFICATION_EVIDENCE` rules: 10 MB max), `evidence_type`, `source_description` (optional), `captured_at` (optional).
**Success — 201.** **Errors:** 403 (neither owner nor assigned inspector); 422 `unsupported_media_type`/`media_too_large` (from Media/File, surfaced here).

### GET /api/v1/verification/evidence/{evidence_id}/access
**Authorization:** case owner, currently-assigned inspector, or a reviewer (`VERIFICATION_REVIEW`) — nobody else, regardless of what other Verification permissions they hold.
**Success — 200:** `{ "stream_path": "..." }` — follow it directly (short-lived, ~5 minutes) to retrieve the actual file.
**Frontend notes:** don't cache this path — re-request it each time evidence needs to be displayed.

---

## PATCH — MANUAL TESTING [FOR NSISONG — additional steps, insert after the original guide's step 4]

**4a. Inspector submits evidence:** as Account B (the assigned inspector from step 4 of the original guide), `POST /verification/cases/{id}/evidence` with an inspection photo, while the inspection is in progress. Expect `201` — this specifically proves ADR-088's fix; under the original spec's design this would have incorrectly returned `403`.

**4b. Evidence access boundary:** as the Scout (case owner), `GET /verification/evidence/{that evidence id}/access` — expect `200`. As a *different*, unrelated Scout, attempt the same call — expect `403`. As Account A (the reviewer, not the inspector) — expect `200`.

---

## PATCH — COMPLETION CHECKLIST [FOR NSISONG — additional items]

- [ ] Evidence is stored as a real `media_id`, resolvable through Media/File's access mechanism — not a bare string.
- [ ] An assigned inspector can submit evidence for their own inspection (the ADR-088 fix, proven by manual step 4a and its corresponding automated test).
- [ ] Evidence access is limited to exactly three caller types — case owner, assigned inspector, reviewer — verified by the specific negative test (an unrelated Scout denied).
- [ ] Media/File's own content-type and size rejections surface through Verification's evidence endpoint as clean 422s, not 500s.
