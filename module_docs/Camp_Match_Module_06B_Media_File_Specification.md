# CAMP MATCH — MODULE 06B: MEDIA/FILE
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Chief Engineer → Claude, Media/File Module handoff**

---

## HOW TO READ THIS DOCUMENT

Same conventions as every previous module spec. Fourteen chunks, followed exactly, with the usual surrounding sections. Slotted as **"06B"** rather than a new numbered module, because it doesn't belong in the original 13-module product sequence — it's the infrastructure gap three of those modules already hit and punted on (Profile's avatar, Housing's listing photos, and Verification's evidence, flagged explicitly in Verification's own spec, Finding 1/ADR-069).

**On sequencing — this matters more than usual here.** Verification & Inspection (Module 7) has **not** been implemented yet. The Chief Engineer's handoff assumes it has (Part 31 talks about "Search's existing Verification integration" as already live). Rather than build Media/File against a Verification that doesn't exist and migrate it later, this module's Verification integration is delivered as a **companion amendment to Module 7's specification** (a separate document, produced alongside this one) — so Verification gets built once, correctly, using real `media_id` references from the start, never the placeholder string its original spec used as a stand-in. Profile, Housing, and Search & Discovery all already exist, so those three integrations are complete, real chunks below, not stand-ins.

---

## ARCHITECTURAL INTERPRETATION [FOR NSISONG]

Media/File answers one question: "how do we safely store a file and hand back something stable to point at it?" It has no opinion on what a file *means* — that a photo is a listing's primary image, or that a document is identity evidence, is knowledge that belongs entirely to whichever module asked for the upload. This module is a capability, the same category of thing Security is (Security answers "are you allowed"; this answers "here's your file, safely, or here's why not").

### DECISIONS (ADR-078 … ADR-085) [FOR NSISONG]

Continuing the log from Phase 1–3 (001–013) through Verification (069–077).

| ADR | Decision | Why |
|---|---|---|
| 078 | MVP storage adapter is the **local filesystem**, under a configurable path — not a cloud provider | No cloud storage has been selected anywhere in this project. Inventing one now would be the exact premature-infrastructure choice this project has consistently avoided (Docker, PostGIS, a message broker — all declined for the same reason at the point they'd have been premature). A real deployment needs a real object-storage adapter before going live; the storage port is shaped so that's a one-adapter swap, not a rewrite. |
| 079 | Upload happens **only** through the owning module's own endpoint — Profile's avatar update, Housing's listing-photo add, Verification's evidence submission (once that module exists) — never a standalone "upload, then attach to something later" flow | Makes the "attach my file to someone else's object" risk (Part 20) structurally impossible, not just checked for — there's no window where an unassociated file exists for anyone to misattach. |
| 080 | Private media access likewise never goes through Media/File's own generic endpoint — only through the owning module's own access endpoint, which does its own business-level authorization first, then asks Media/File in-process for a grant. Media/File's own public endpoint serves **public** media only; a private request through it is rejected outright, regardless of who's asking | Same structural-over-checked discipline as everything else in this project (Profile's self-scoped `/me`, Housing's derived bookability). Media/File genuinely cannot know Verification's access rules — the boundary has to be enforced by *not answering* for private media through the generic door, not by trying to import Verification's policy. |
| 081 | Short-lived access is an **HMAC-signed, time-limited token**, validated by this module's own streaming endpoint — not a native cloud-provider presigned URL, since there's no cloud provider yet | Built to the same contract shape (`store → key`, `access → time-limited URL`) a real presigned-URL adapter would have, so swapping one in later changes one adapter file, nothing upstream. |
| 082 | Upload **purpose** (`PROFILE_AVATAR`, `LISTING_PHOTO`, `VERIFICATION_EVIDENCE`) is a small, static, code-defined set that determines both the allowed content-type category and the access policy — never a client-supplied field | The fourth confirmed instance of this project's recurring "static policy mapping" idiom, after Security's roles (Module 3), Verification's per-target requirements (Module 7), and now this. A client should never be able to mark their own upload `PUBLIC` by mistake or malice — the purpose decides that, not the request. |
| 083 | Content type is validated against the file's **actual bytes** (its signature/magic number), never trusted from the filename or the client-supplied header alone | Direct requirement (Part 41). Extension and header are both attacker-controlled; the bytes aren't. |
| 084 | Deletion is **logical only** — the database row never disappears, only its status becomes `DELETED`; the underlying local file is physically removed at that point. **No HTTP endpoint exposes it yet** | No consuming module has a real trigger for deletion today (Profile has no "remove avatar" use case, Housing no "remove photo," and Verification's evidence is explicitly immutable). Same discipline as Identity's original `DisableAccount` — build the capability, wait for a legitimate caller before exposing it. |
| 085 | Verification's integration is a **companion amendment**, not a chunk in this document | Explained above. |


---

## CHUNK 1 — CODEBASE INSPECTION & ARCHITECTURAL ALIGNMENT
**[FOR YOU — GEMINI CLI]**

**Implementation instructions:**
1. Read `AI_instructions/` in full and `AI_state/CURRENT_STATE.md`, `ARCHITECTURE_STATE.md`, `DATABASE_STATE.md`, `API_STATE.md`.
2. Read `docs/modules/identity.md`, `profile.md`, `security.md`, `university_location.md`, `housing.md`, `search.md`.
3. Inspect Profile's `avatar_url` field (`domain/entities.py`, `adapters/persistence/models.py`) — this is the exact legacy field Chunk 9 migrates.
4. Inspect Housing's `listing_media` table and its adapter — this is what Chunk 10 migrates.
5. Inspect Search's `SearchResultItem` DTO (`media` field) — confirm its current shape before Chunk 12 changes what populates it.
6. Confirm no storage configuration, upload utility, or file-handling code exists anywhere in the project already (expected — report if anything does, since that would change this module's approach).
7. Produce a short gap analysis in your Completion Report: exactly which fields/tables in Profile and Housing this module will touch, confirming they match what Chunks 9–10 below assume.
8. Create the module's empty structure:
```
src/camp_match/modules/media/__init__.py
src/camp_match/modules/media/domain/__init__.py
src/camp_match/modules/media/domain/value_objects.py
src/camp_match/modules/media/domain/entities.py
src/camp_match/modules/media/domain/policy.py
src/camp_match/modules/media/application/__init__.py
src/camp_match/modules/media/application/errors.py
src/camp_match/modules/media/application/ports/__init__.py
src/camp_match/modules/media/application/ports/inbound.py
src/camp_match/modules/media/application/ports/outbound.py
src/camp_match/modules/media/application/use_cases/__init__.py
src/camp_match/modules/media/adapters/__init__.py
src/camp_match/modules/media/adapters/persistence/__init__.py
src/camp_match/modules/media/adapters/storage/__init__.py
src/camp_match/modules/media/adapters/api/__init__.py
tests/unit/media/__init__.py
tests/unit/media/domain/__init__.py
tests/unit/media/application/__init__.py
tests/integration/media/__init__.py
tests/api/media/__init__.py
```
`domain/policy.py` — the purpose → category/access-policy mapping (ADR-082), same naming convention as Security's/Verification's equivalent files.

**Acceptance criteria:** the gap analysis is written and accurate; all files from step 8 importable; **do not proceed past this chunk if step 6 finds something unexpected** — report it instead.

---

## CHUNK 2 — MEDIA/FILE DOMAIN MODEL
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `domain/value_objects.py`, `domain/entities.py`, `domain/policy.py`.

**`value_objects.py`:**
- **`MediaPurpose`** (enum) — `PROFILE_AVATAR`, `LISTING_PHOTO`, `VERIFICATION_EVIDENCE`.
- **`MediaCategory`** (enum) — `IMAGE`, `DOCUMENT`.
- **`MediaStatus`** (enum) — `UPLOADING`, `AVAILABLE`, `FAILED`, `DELETED`. No separate `PENDING` — upload is a single synchronous request/response cycle for MVP (backend-mediated, Part 5), so there's no meaningful gap between "requested" and "in progress" worth its own state.
- **`AccessPolicy`** (enum) — `PUBLIC`, `PRIVATE`.

**`policy.py`** (ADR-082) — the static mapping, one function: `rules_for(purpose: MediaPurpose) -> MediaPurposeRules` where `MediaPurposeRules` carries `category`, `access_policy`, `allowed_content_types` (a frozenset), `max_size_bytes`:

| Purpose | Category | Access | Allowed types | Max size |
|---|---|---|---|---|
| `PROFILE_AVATAR` | `IMAGE` | `PUBLIC` | `image/jpeg`, `image/png`, `image/webp` | 5 MB |
| `LISTING_PHOTO` | `IMAGE` | `PUBLIC` | `image/jpeg`, `image/png`, `image/webp` | 5 MB |
| `VERIFICATION_EVIDENCE` | `IMAGE` or `DOCUMENT` | `PRIVATE` | the three image types above, plus `application/pdf` | 10 MB |

These exact numbers live in `Settings` (Chunk 3), not hard-coded — the table above is the *default* configuration, not a permanent constant.

**`entities.py` — one entity, `MediaFile`:** `id` (`EntityId`, permanent), `purpose` (permanent), `storage_reference` (str, set only when status becomes `AVAILABLE`), `content_type`, `size_bytes`, `original_filename` (str, metadata only — never used to derive the storage key), `status`, `uploaded_by` (`EntityId`, permanent), `created_at`/`updated_at`. Read-only derived properties: `category`/`access_policy` (from `policy.rules_for(purpose)` — never stored redundantly, always derived from `purpose`, so there's no way for them to drift out of sync with it).

**Invariants enforced here:** `storage_reference` can only be set when transitioning to `AVAILABLE`, never before; a `DELETED`/`FAILED` file has no valid `storage_reference` a caller should trust; `purpose`/`uploaded_by`/`id` never change after construction.

**Tests you must write:** `tests/unit/media/domain/test_policy.py` (each purpose resolves to the exact rules in the table above) and `tests/unit/media/domain/test_media_file.py` (a file starts `UPLOADING` with no `storage_reference`; transitioning to `AVAILABLE` requires supplying one; transitioning to `FAILED` clears any partial reference; `category`/`access_policy` are always derived, never independently settable).

**Acceptance criteria:** new tests pass; no import beyond stdlib + shared-kernel `EntityId`.


---

## CHUNK 3 — STORAGE PORT & ADAPTER
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `application/ports/outbound.py`, `config/settings.py`, `.env.example`.
**Files to create:** `adapters/storage/local_storage_adapter.py`, `adapters/storage/access_token.py`.

**New settings:** `media_storage_path: str` (default `"./var/media"`, resolved relative to the project root — under Termux this lands inside the repo checkout, not `$PREFIX`, since it's application data, not a system service), `media_access_token_secret: str` (same treatment as `jwt_secret_key` — a placeholder in `.env.example`, a real random value required anywhere that matters), `media_access_token_ttl_seconds: int = 300` (five minutes).

**`StoragePort`** (outbound): `store(key: str, data: bytes, content_type: str) -> None`, `delete(key: str) -> None`, `exists(key: str) -> bool`, `issue_access_token(key: str) -> AccessGrant` where `AccessGrant` carries `token: str`, `expires_at: datetime`.

**`LocalFileSystemStorageAdapter`:** `store` writes `data` to `{media_storage_path}/{key}`, creating parent directories as needed; the **key is always exactly `media/{media_id}`** — derived server-side from the entity's own id, never from `original_filename` or anything client-supplied (Part 42/43). `delete` removes the file if present, silently succeeds if it's already gone (idempotent, same discipline as every other deletion-adjacent operation in this project). `exists` a plain filesystem check.

**`access_token.py` — the signed-token mechanism (ADR-081), stated precisely:** generate a token as `base64url(key) + "." + base64url(expires_at_unix_timestamp) + "." + hex(HMAC-SHA256(media_access_token_secret, key + ":" + expires_at_unix_timestamp))`. Validation: recompute the HMAC from the token's own key and timestamp, compare with `hmac.compare_digest` (never `==`), and reject if `expires_at` has passed. This is deliberately the same constant-time-comparison discipline Identity used for its refresh tokens (Module 1) — a forged or tampered token must fail exactly like an expired one, not in a way that leaks which part was wrong.

**Tests you must write:** `tests/unit/media/adapters/test_local_storage_adapter.py` (store then retrieve the same bytes back; delete then confirm `exists` is false; deleting twice doesn't raise) and `tests/unit/media/adapters/test_access_token.py` (a freshly issued token validates; a tampered token — flip one character — fails; an expired token fails even with a correct signature; two tokens issued for the same key at different times are different strings).

**Acceptance criteria:** new tests pass.

---

## CHUNK 4 — REPOSITORY & PERSISTENCE
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/persistence/models.py`, `adapters/persistence/repository.py`.

**`media_files`**

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | primary key |
| `purpose` | text | not null, `CHECK` restricted |
| `storage_reference` | text | nullable — only set once `AVAILABLE` |
| `content_type` | text | not null |
| `size_bytes` | bigint | not null, `CHECK (size_bytes > 0)` |
| `original_filename` | text | not null |
| `status` | text | not null, `CHECK` restricted, default `UPLOADING` — indexed (needed to find stuck/orphaned uploads, Part 14) |
| `uploaded_by` | UUID | not null, no foreign key — indexed |
| `created_at`/`updated_at` | timestamptz | server defaults |

No foreign keys to Profile, Housing, or Verification tables (Part 39) — this module doesn't know or care who references a `media_id`.

**`SqlAlchemyMediaRepository`:** `add` (called with `status=UPLOADING`, before storage is attempted — Part 13's ordering, so a row always exists even if storage subsequently fails), `get_by_id`, `update` (used for both the success path — `AVAILABLE` + `storage_reference` — and the failure path — `FAILED`), `find_stuck_uploads(older_than: timedelta) -> list[MediaFile]` (a diagnostic query, not wired to any automated cleanup per Part 14 — just callable manually or from a future admin tool).

**Migration:** `poetry run alembic revision --autogenerate -m "add media_files table"`, read before applying.

**Tests you must write:** `tests/integration/media/test_repository.py` (marked `integration`) — add-then-retrieve; the `UPLOADING` → `AVAILABLE`/`FAILED` update paths; `find_stuck_uploads` correctly filters by age.

**Acceptance criteria:** new tests pass against local Termux Postgres; migration applies cleanly.


---

## CHUNK 5 — UPLOAD APPLICATION WORKFLOW
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/upload_media.py`.

**`UploadMedia` — steps, in order, matching the transaction-boundary strategy from ADR/Part 13 exactly:**
1. Resolve `rules_for(purpose)` (Chunk 2).
2. Validate the **actual content type from the file's own bytes**, not the client-supplied header (ADR-083 — check the file's signature: JPEG starts `FF D8 FF`, PNG starts the 8-byte PNG signature, PDF starts `%PDF`, WebP has the `RIFF....WEBP` structure; reject with `UnsupportedMediaType` if the sniffed type doesn't match one of `rules.allowed_content_types`, regardless of what the client claimed).
3. Validate `size_bytes <= rules.max_size_bytes` — reject with `MediaTooLarge` otherwise, **before** attempting to store anything.
4. Construct a new `MediaFile`, `status=UPLOADING`, and persist it **first** — this row existing is the guarantee against a silently-lost upload.
5. Call `StoragePort.store(key=f"media/{media_id}", data, content_type)`.
6. **On success:** update the record to `status=AVAILABLE` with the `storage_reference` set; log INFO (`"media_uploaded"`, media id, purpose, size — never the filename or content in a way that could be sensitive, and never anything for `VERIFICATION_EVIDENCE` beyond the bare fact it happened).
7. **On storage failure:** update the record to `status=FAILED`; log at WARNING (not INFO — a failed upload is worth noticing); re-raise as `MediaUploadFailed` so the caller's HTTP response reflects it honestly rather than claiming success.
8. Return the response — `media_id`, `status`.

**Tests you must write:** `tests/unit/media/application/test_upload_media.py`, against a fake `StoragePort` — the happy path; content-type mismatch (a `.jpg`-named, PDF-content-type-claimed file that's actually a PNG by its bytes is rejected, proving the sniff, not the claim, decides); oversized file rejected before the fake storage adapter is ever called (assert the fake wasn't invoked); a fake storage adapter configured to fail leaves the record `FAILED`, not silently `AVAILABLE` or deleted.

**Acceptance criteria:** new tests pass, all against fakes.

---

## CHUNK 6 — AUTHORIZED ACCESS
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/get_media_metadata.py`, `application/use_cases/get_authorized_access.py`.

**`GetMediaMetadata` — steps:** look up by id; `MediaNotFound` if absent or `status == DELETED`; return safe fields only (`media_id`, `content_type`, `size_bytes`, `status`, `access_policy`) — **never** `storage_reference`, **never** `original_filename` beyond what the caller already knows it uploaded.

**`GetAuthorizedAccess` — steps:** look up by id; reject (`MediaNotAvailable`) unless `status == AVAILABLE`; call `StoragePort.issue_access_token`; return the grant. **This use case does not check `access_policy` itself** — per ADR-080, that boundary is enforced by *who calls this port*, not by logic inside it: Media/File's own HTTP layer (Chunk 12) only ever calls this for `PUBLIC` media; a consuming module's own endpoint (Verification's evidence-access route, once that module exists) calls it in-process only after doing its own business-level authorization first. State this explicitly in the docstring, since "the use case doesn't check access_policy" reads like an oversight if you don't know it's deliberate.

**Tests you must write:** `tests/unit/media/application/test_get_authorized_access.py` — a grant is issued for `AVAILABLE` media of either policy (proving the port itself is policy-agnostic, by design); `DELETED`/`FAILED`/`UPLOADING` media all correctly raise `MediaNotAvailable`.

**Acceptance criteria:** new tests pass.

---

## CHUNK 7 — DELETION & LIFECYCLE
**[FOR YOU — GEMINI CLI]**

**Files to create:** `application/use_cases/delete_media.py`.

**`DeleteMedia` — steps (built now, exposed over HTTP by nobody yet — ADR-084):** look up by id; if already `DELETED`, succeed with no further action (idempotent); otherwise call `StoragePort.delete`, then set `status=DELETED` (keep every other field — `original_filename`, `uploaded_by`, etc. — for audit purposes; only `storage_reference` is cleared); log INFO.

**Tests you must write:** `tests/unit/media/application/test_delete_media.py` — deletes the underlying storage object (assert the fake `StoragePort.delete` was called with the right key); calling twice doesn't raise or double-delete; a subsequent `GetMediaMetadata`/`GetAuthorizedAccess` call against a deleted id behaves exactly like a nonexistent one from the caller's point of view.

**Acceptance criteria:** new tests pass.


---

## CHUNK 8 — PORTS, ERRORS & API SURFACE
**[FOR YOU — GEMINI CLI]**

**Objective:** the Chief Engineer's suggested Chunks 12 ("FastAPI") content, brought forward and merged with the port definitions — Media/File's own HTTP surface is small enough (three routes) that defining it separately from its ports would be artificial splitting for a module this size.

**Files to modify:** `application/ports/inbound.py`, `application/errors.py`.
**Files to create:** `adapters/api/schemas.py`, `adapters/api/router.py`, `adapters/api/dependencies.py`, `adapters/api/streaming.py`.
**Files to modify:** `app.py`.

**Inbound ports (consumed in-process by other modules — this is the module's real public contract, not its HTTP surface):** `UploadMedia`, `GetMediaMetadata`, `GetAuthorizedAccess`, `DeleteMedia` — `Protocol`-with-`execute`, dataclass request/response, same convention as every previous module.

**Errors:** `MediaNotFound` (`NotFoundError`), `UnsupportedMediaType` (`ValidationError`), `MediaTooLarge` (`ValidationError`), `MediaUploadFailed` (reserved as a distinct category — since it represents an infrastructure failure rather than a bad request, let it propagate as an unexpected exception to the generic 500 handler rather than inventing a new HTTP-status category nothing else in the project uses yet, same reasoning Search applied to its own dependency-failure case, Module 6), `MediaNotAvailable` (`ValidationError`).

**HTTP surface — deliberately minimal, three routes, all under `/api/v1/media`, and this is the *only* module-owning-its-own-HTTP-surface part of this module (uploads happen through owning modules, not here — ADR-079):**

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/{media_id}` | authenticated | metadata only, any `AVAILABLE` **public** media; `403` for private, regardless of asker |
| GET | `/{media_id}/stream` | token query param, no `Authorization` header needed | validates the signed token (Chunk 3), streams the bytes; used by both public and (when a consuming module has legitimately issued one) private grants |
| — | — | — | no upload route, no delete route, here |

**`streaming.py`:** validates the `token` query parameter against `access_token.py`'s validation function (Chunk 3); on success, streams the file from local storage with the correct `Content-Type`; on failure (expired/tampered/missing token), `403` — no distinction in the response between "expired" and "tampered," to avoid giving an attacker a signal about which part of their forgery attempt was closer to working.

**Tests you must write:** `tests/api/media/test_metadata_endpoint.py` (public media resolves; private media is rejected regardless of caller) and `tests/api/media/test_streaming.py` (a valid token streams the correct bytes; an expired one is rejected; a tampered one is rejected; a token for a different media id than the one in the URL path is rejected — confirm the key is actually bound into the signature, not just checked separately).

**Acceptance criteria:** new tests pass.

---

## CHUNK 9 — PROFILE INTEGRATION
**[FOR YOU — GEMINI CLI]**

**Objective:** migrate Profile's `avatar_url` (a bare string) to a real `avatar_media_id`, with temporary compatibility for whatever's already in the database.

**Files to modify (Profile, Module 2):** `domain/entities.py` (add `avatar_media_id: EntityId | None`, **keep** `avatar_url: str | None` — do not remove it yet, per Part 45/46), `adapters/persistence/models.py` (add the new nullable column, migration), `adapters/api/schemas.py` (response includes both fields during the transition — `avatar_media_id` when present, `avatar_url` as a fallback for legacy records that predate this chunk), `application/use_cases/update_profile.py` (accepting an already-uploaded `avatar_media_id` is not what changes here — see below).

**The actual upload path — a new endpoint, not a field update:** `POST /api/v1/profiles/me/avatar` (multipart file upload), a new small Profile-owned endpoint: confirms the caller has a profile; calls Media/File's `UploadMedia` in-process with `purpose=PROFILE_AVATAR`, `uploaded_by=caller's identity_id`; on success, sets `avatar_media_id` on the profile (clearing `avatar_url`, since the two are mutually exclusive going forward — a profile has one or the other, never both, once this endpoint has been used once); returns the updated profile.

**Legacy compatibility rule, stated precisely:** a profile response includes an `avatar` object shaped `{ "type": "media" | "legacy_url", "value": "<media access path>" | "<the raw URL>" }` — the frontend can tell the two apart and render either, and nothing pretends a legacy URL is a Media/File reference it isn't (Part 27's explicit warning). Document in `docs/modules/profile.md` (updated as part of this chunk) that `avatar_url` is deprecated but not removed, and will be dropped in a future migration once no active profile still uses it — a query to check that count is worth including in the documentation, not just the intent.

**Tests you must write:** `tests/api/profile/test_avatar_upload.py` (in Profile's own test folder) — upload succeeds, `avatar_media_id` is set, `avatar_url` is cleared; a profile created before this chunk (simulate by inserting a row with only `avatar_url` set) still resolves correctly through the response shape above; confirm Profile's full pre-existing suite is unaffected.

**Acceptance criteria:** new tests pass; `poetry run pytest tests/unit/profile tests/integration/profile tests/api/profile` shows the same results as before this chunk, plus the new ones.


---

## CHUNK 10 — HOUSING INTEGRATION
**[FOR YOU — GEMINI CLI]**

**Objective:** migrate `listing_media.media_url` to a real `media_id`, same pattern as Chunk 9, adapted for Housing keeping ownership of ordering and primary-image selection (Part 28 — Housing decides which photo is first and whether an image belongs on a listing at all; Media/File only stores it).

**Files to modify (Housing, Module 5):** `adapters/persistence/models.py` (`listing_media` gains `media_id: UUID | None`, keeps `media_url: text | None` — same both-fields-during-transition approach as Profile), `domain/entities.py` (the media reference on a `Listing`'s media list becomes a small union-shaped value, same `{type, value}` idea as Chunk 9).

**New endpoint:** `POST /api/v1/listings/{id}/media` (multipart, `HOUSING_MANAGE` + ownership, same authorization as every other Housing mutation) — calls `UploadMedia` with `purpose=LISTING_PHOTO`; on success, appends a new `listing_media` row with `media_id` set (not `media_url`); Housing's existing `display_order`/primary-image logic is untouched, it just now has a mix of `media_id`-backed and legacy `media_url`-backed rows to order, which its existing ordering logic already handles since it only ever cared about `display_order`, not which field holds the reference.

**Tests you must write:** `tests/api/housing/test_listing_media_upload.py` — upload succeeds and appends correctly; ownership enforced (a different Scout can't add photos to someone else's listing); a listing with a mix of legacy `media_url` and new `media_id` rows serializes correctly in `GET /listings/{id}`; Housing's full pre-existing suite unaffected.

**Acceptance criteria:** new tests pass; `poetry run pytest tests/unit/housing tests/integration/housing tests/api/housing` shows the same results as before this chunk, plus the new ones.

---

## CHUNK 11 — SEARCH & DISCOVERY INTEGRATION
**[FOR YOU — GEMINI CLI]**

**Objective:** populate `SearchResultItem.media` with real, accessible references — and do it without Search ever touching Media/File's database or reimplementing access logic (Part 30/32).

**Files to modify (Search, Module 6):** `adapters/housing/housing_provider.py` (Search's existing `InProcessHousingProvider` — its `CandidateListing` mapping now carries through whatever media reference shape Housing's `ListEligibleCandidates` port returns, unchanged in kind from Chunk 10's work — Search does not resolve media access itself, it passes through what Housing already resolved), `adapters/api/schemas.py` (the `media` field in `SearchResultItem` becomes a list of resolvable references, each either a public streaming path — for `media_id`-backed entries, this is safe to include directly since listing photos are always `PUBLIC` — or the legacy raw URL).

**Prohibition, explicit per Part 31/32:** do not add a new outbound port from Search to Media/File. Search already gets everything it needs through Housing's existing port (extended, not replaced, by Chunk 10 above) — adding a second path to the same information would be exactly the "duplicate Media metadata into Search" the handoff warns against. Do not touch Search's ranking, filtering, or its (now-real, Module 7) verification integration — this chunk only changes what populates one field.

**Tests you must write:** extend `tests/api/search/test_search_flow.py` (Search's own existing test file) with one new assertion: a listing with an uploaded photo (via Chunk 10's new endpoint) shows a resolvable media reference in its search result; confirm every other existing Search assertion still passes unchanged.

**Acceptance criteria:** the extended test passes; `poetry run pytest tests/unit/search tests/integration/search tests/api/search` shows the same results as before this chunk, plus the one new assertion.

---

## CHUNK 12 — VERIFICATION INTEGRATION (DEFERRED — SEE COMPANION DOCUMENT)
**[FOR YOU — GEMINI CLI]**

Verification & Inspection has not been implemented yet (ADR-085). There is nothing to integrate with in this chunk. When Module 7 is implemented, it will consume this module's `UploadMedia`/`GetAuthorizedAccess` ports directly, with `purpose=VERIFICATION_EVIDENCE`, exactly as described in the companion document **"Verification & Inspection — Media/File Amendment."** Do not implement anything in this chunk — confirm the amendment document exists and is consistent with what Chunks 1–11 actually built (in particular, that `VERIFICATION_EVIDENCE`'s rules in `domain/policy.py`, Chunk 2, match what that document assumes), and report any mismatch rather than silently reconciling one side to the other.

**Acceptance criteria:** written confirmation that the amendment document's assumptions match this module's actual `domain/policy.py` and port signatures.


---

## CHUNK 13 — SECURITY, TESTING, DOCUMENTATION & AI STATE
**[FOR YOU — GEMINI CLI]**

**Files to create:** `tests/api/media/test_upload_flow.py`, `tests/api/media/test_security.py`; extend the import-linter contract list.

**`test_upload_flow.py`, through real HTTP, using the three owning-module endpoints (not a direct `/media` upload — that route doesn't exist, ADR-079):** upload a Profile avatar, confirm it's retrievable at its streaming path; upload a Housing listing photo the same way; confirm both are correctly marked `PUBLIC` and reachable without any special permission beyond authentication.

**`test_security.py`:** oversized file rejected before storage is touched; a file whose extension claims `.jpg` but whose actual bytes are something else (or garbage) is rejected by content-sniffing, not accepted on the strength of its name; a tampered access token is rejected; requesting private-media semantics through Media/File's own generic endpoint is rejected outright (there's no private media to actually test end-to-end yet without Verification, so this test constructs a `PRIVATE`-purpose record directly via the repository to prove the endpoint's own rejection logic, independent of any real consumer).

**Extend import-linter:** `camp_match.modules.media.domain` and `.application` must not import `fastapi` or `sqlalchemy`; nothing outside `camp_match.modules.media` may import its `adapters.*` directly.

**Documentation:** write `docs/modules/media.md` per the Module Documentation Requirements below. Update `AI_state/` per the AI State Requirements below, using the standard `CURRENT_TASK.md` status-block format. Update `docs/modules/profile.md` and `docs/modules/housing.md`'s existing "known limitations" sections to remove the now-resolved "no media upload, just URL storage" entries each one carried.

**Run everything:** `poetry run pytest`, `poetry run ruff check .`, `poetry run mypy src`, `poetry run lint-imports` — the whole project, all modules touched so far, green.

**Acceptance criteria:** every scenario above passes; both updated "known limitations" sections in Profile's and Housing's docs are actually edited, not just noted as needing it.

---

## CHUNK 14 — FINAL ARCHITECTURE AUDIT
**[FOR YOU — GEMINI CLI]**

Confirm every item in the Completion Checklist below. Run the full suite one final time from a clean state. Confirm Profile's, Housing's, and Search's suites specifically are unaffected apart from the documented, intentional additions in Chunks 9–11.


---

## FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**General note, applies everywhere media appears in any response:** a media reference is one of two shapes — `{ "type": "media", "media_id": "...", "stream_path": "/api/v1/media/{id}/stream?token=..." }` for anything uploaded through this module, or `{ "type": "legacy_url", "url": "..." }` for anything predating it. Always check `type` before deciding how to render it.

### POST /api/v1/profiles/me/avatar
**Authentication:** required. **Request:** multipart file upload, `image/jpeg`/`png`/`webp`, max 5 MB.
**Success — 200:** the updated profile, with the new avatar reference.
**Errors:** 422 `unsupported_media_type` / `media_too_large`.

### POST /api/v1/listings/{id}/media
**Authorization:** `housing.manage` + ownership.
**Request:** multipart, same image constraints as above.
**Success — 201:** the new media entry, appended to the listing's photo list.

### GET /api/v1/media/{id}
**Authentication:** required. **Success — 200:** metadata only (content type, size, status). **Errors:** 403 if the media is private (nothing in the current product surfaces a private reference to the frontend yet — this only becomes reachable once Verification exists).

### GET /api/v1/media/{id}/stream
**Authentication:** none — a valid `token` query parameter (obtained from the object that referenced this media, e.g. a profile or listing response) is the credential.
**Frontend notes:** the token expires after 5 minutes — don't cache a stream URL long-term; re-fetch the owning resource (the profile, the listing) to get a fresh one if a lot of time has passed.

---

## MANUAL TESTING GUIDE [FOR NSISONG]

**Preconditions:** `scripts/db_start.sh` running; the app running; a Scout account with a listing.

1. **Avatar upload:** `POST /profiles/me/avatar` with a real small JPEG. Expect `200`, a `type: "media"` avatar reference.
2. **Stream it:** follow the returned `stream_path`. Expect the actual image bytes back, correct `Content-Type`.
3. **Tampered token:** alter one character of the token in the URL from step 2. Expect `403`.
4. **Reject bad content:** rename a small text file to `photo.jpg` and upload it as a listing photo. Expect `422` — the sniff catches it even though the filename and claimed type both say image.
5. **Oversized file:** attempt an upload larger than 5 MB. Expect `422`, and confirm (via logs or a `find_stuck_uploads`-style check) that no partial file was written to `media_storage_path` — the size check happens before storage is touched.
6. **Legacy compatibility:** if any profile in your test data predates this module (has only `avatar_url` set), confirm `GET /profiles/me` still renders it correctly, now shaped as `type: "legacy_url"`.

**Failure interpretation:** if step 4 succeeds, content-type validation is trusting the filename/header instead of the bytes — a real security gap for a platform that will eventually accept identity documents, not just a cosmetic bug. Treat it as blocking.

---

## AUTOMATED TESTING GUIDE [FOR NSISONG]

- Just Media/File: `poetry run pytest tests/unit/media tests/integration/media tests/api/media`
- Domain/adapter only (fast, no database): `poetry run pytest tests/unit/media -v`
- Security-specific: `poetry run pytest tests/api/media/test_security.py -v`
- Full verification: `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports`
- After this module, re-run Profile's, Housing's, and Search's suites in isolation to confirm each is unaffected apart from its documented, intentional addition.


---

## MODULE DOCUMENTATION REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 13]

Write `docs/modules/media.md`. Cover: purpose/ownership/non-ownership (this document's Architectural Interpretation, condensed — "how," never "what it means"); the domain model and the purpose→policy table in full; the upload transaction-boundary strategy (Chunk 5) explained clearly enough that a future reader understands why the DB row is created *before* storage is attempted, not after; the signed-token access mechanism (Chunk 3) in enough detail to actually implement a cloud-storage replacement later without re-deriving the contract from scratch; the structural public/private boundary (ADR-080) — stated plainly, since it's the one thing in this module most likely to be "simplified" by a future engineer who doesn't understand why it's split this way; the Profile and Housing migration strategy, including the legacy-compatibility shape and exactly how to check whether any legacy `avatar_url`/`media_url` records remain; known limitations (local filesystem storage, not production-ready — ADR-078, stated as a real gap, not a footnote; no delete endpoint yet; no malware/virus scanning); the companion Verification amendment, referenced by name, not duplicated.

## AI STATE REQUIREMENTS [FOR YOU — GEMINI CLI, part of Chunk 13]

Update `CURRENT_STATE.md`, `PROGRESS.md`, `COMPLETED_WORK.md`, `ARCHITECTURE_STATE.md` (note this is the first module three other modules had to be reopened for, and why that's different from an unplanned break), `DATABASE_STATE.md`, `API_STATE.md`, `TEST_STATE.md`, `DECISIONS.md` (append ADR-078–085), `SESSION_HANDOFF.md` — set the next task to Module 7 (Verification & Inspection), noting its amendment document is the authoritative version of its evidence/media handling, superseding the original spec's placeholder design. Profile's and Housing's own `AI_state` entries should note their media migrations. Use the standard `CURRENT_TASK.md` status-block format throughout.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] Upload works through all three owning-module endpoints (Profile, Housing, and — once built — Verification), never through a standalone generic upload route.
- [ ] Content-type validation genuinely inspects file bytes, not filename or client-claimed header — proven by the mismatched-extension test.
- [ ] Oversized files are rejected before any bytes are written to storage.
- [ ] A failed storage write leaves a `FAILED` record, never a phantom `AVAILABLE` one with no real file behind it.
- [ ] Access tokens are time-limited, tamper-evident, and bound to a specific media id — all three properties individually tested.
- [ ] Private-media requests through Media/File's own generic endpoint are rejected outright, regardless of caller — the structural boundary from ADR-080, not just a policy note.
- [ ] Profile's and Housing's legacy URL fields still work, unmigrated records still render correctly, and neither module's pre-existing test suite regressed.
- [ ] Search surfaces real, resolvable media references without adding any new outbound port or touching ranking/filtering.
- [ ] No cross-module database access in any direction; no foreign keys from `media_files` into any other module's tables.
- [ ] Unit, integration, API, and architecture tests all pass — every module touched, together.
- [ ] `docs/modules/media.md` exists and covers everything above; Profile's and Housing's docs have their now-resolved "known limitations" entries actually removed, not just superseded silently.
- [ ] All `AI_state/` files updated, including Profile's and Housing's.
- [ ] The companion Verification amendment document exists, is consistent with this module's actual `domain/policy.py`, and is ready to hand to Gemini alongside (or instead of) Module 7's original chunks.

