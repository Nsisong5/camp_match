# CAMP MATCH — PROFILE → UNIVERSITY & LOCATION MIGRATION
**university_name → university_id, and the Discovery feature it unblocks**
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**

---

## HOW TO READ THIS DOCUMENT

Same conventions as every previous document. This isn't a new module — it's a cross-cutting change touching three already-shipped modules. Structured as its own small chunk sequence rather than forced into any one module's existing chunk numbering. **[FOR YOU — GEMINI CLI]** / **[FOR NSISONG]** labels as always.

**Modules checked, for completeness, since "all affected modules" was the ask:** Identity, Security, Housing, Verification, and Media/File were all reviewed against this change and **do not need any modification** — none of them reference Profile's university field directly. Only Profile, University & Location, and Search & Discovery are touched. Stated plainly so nothing is left to guess at.

---

## WHAT THIS CHANGES AND WHY [FOR NSISONG]

Profile's Student `university_name` has been free text since Module 2 — flagged as a gap the moment University & Location existed to fix it (Module 4, ADR-051), and it turned into a real, named limitation once Discovery wanted to use it (Module 6, ADR-062: "near your campus" personalization couldn't be built because there was nothing reliable to resolve a profile to real coordinates). This migration closes that gap and turns Discovery's proximity ranking on for real.

### DECISIONS (ADR-089 … ADR-093) [FOR NSISONG]

Continuing the log — the Module 07 Media amendment ended at 088.

| ADR | Decision | Why |
|---|---|---|
| 089 | `university_id` is the new canonical field. `university_name` stays, **read-only**, for records that predate this change — **no automated backfill from text to ID** | Matching free text against University & Location's directory reliably isn't possible without the exact fuzzy-matching hack this project already rejected once (Module 6, Finding 1). Existing students re-select their university once, through the new field, rather than the backend guessing on their behalf. |
| 090 | University & Location gains one new port method, `get_main_campus(university_id)`, rather than Profile or Search fetching every campus and filtering client-side | Same principle Housing's own candidate port already established: let the module with the index do the narrow lookup, don't make every consumer re-derive it. |
| 091 | Discovery's ranking regains a proximity factor — explicit weights: preference match 0.40, proximity 0.20, verification 0.20, freshness 0.20 | Retires Module 6's ADR-062. Weights are stated plainly, not silently reintroduced at a guessed value — same discipline as every ranking decision in this project. |
| 092 | Proximity is excluded (weights renormalized among the rest) when a student's profile has no resolvable `university_id`, or that university has no campus flagged `is_main_campus` | Same graceful-degradation rule every other optional ranking input in this project already follows — missing context reduces what's scored, never penalizes a candidate for it. |
| 093 | Profile stores **university-level** `university_id`, not `campus_id` — matching the original field's own meaning. Discovery approximates a student's location via their university's *main* campus | A future `campus_id` addition — letting a student at a multi-campus university pick precisely — would sharpen this further without restructuring anything built here. Noted as a clean extension point, not built now, since it wasn't what was asked for. |


---

## CHUNK 1 — INSPECT & CONFIRM
**[FOR YOU — GEMINI CLI]**

**Implementation instructions:**
1. Read `AI_instructions/` in full and `AI_state/CURRENT_STATE.md`, `ARCHITECTURE_STATE.md`, `DATABASE_STATE.md`.
2. Read `docs/modules/profile.md`, `university_location.md`, `search.md`.
3. Inspect Profile's `StudentProfileDetails` value object and `student_profiles` table — confirm `university_name` is exactly as described (a plain nullable text field, no existing `university_id`).
4. Inspect University & Location's `UniversityLocationQueryPort` and `Campus` entity — confirm `is_main_campus` exists exactly as built in Module 4.
5. Inspect Search's `ProfileProvider`/`UniversityLocationProvider` ports and `DiscoveryRankingStrategy` — confirm the current three-factor table (no proximity) matches Module 6 Chunk 5 as documented.
6. Report back confirming all four, or flag exactly what doesn't match before proceeding.

**Acceptance criteria:** written confirmation; no files modified yet.

---

## CHUNK 2 — UNIVERSITY & LOCATION: ADD `get_main_campus`
**[FOR YOU — GEMINI CLI]**

**Files to modify (module: University & Location):** `application/ports/inbound.py` (add the method to the existing `UniversityLocationQueryPort`), `application/use_cases/` (a small new use case, or extend the existing campus-listing logic internally — your call, document which in the Completion Report), `adapters/api/` — **no new HTTP route**, this is for in-process consumption only, same as every other port addition in this project.

**`get_main_campus(university_id: EntityId) -> CampusSummary | None`** — returns the campus with `is_main_campus = True` for the given university, or `None` if the university doesn't exist or has no campus flagged as main. `CampusSummary` is the same shape `UniversityLocationQueryPort` already returns elsewhere (id, name, coordinates) — nothing new to define.

**Prohibition:** this is the only change to University & Location in this document — nothing else in that module's files changes.

**Tests you must write:** `tests/unit/university_location/application/test_get_main_campus.py` — returns the correctly-flagged campus; returns `None` for a university with campuses but none flagged main; returns `None` for a nonexistent university id.

**Acceptance criteria:** new test passes; `poetry run pytest tests/unit/university_location tests/integration/university_location tests/api/university_location` shows the same results as before this chunk, plus the one new test.


---

## CHUNK 3 — PROFILE: DOMAIN & DATABASE
**[FOR YOU — GEMINI CLI]**

**Files to modify (module: Profile):** `domain/value_objects.py` (`StudentProfileDetails`), `adapters/persistence/models.py`, `application/ports/outbound.py`.

**`StudentProfileDetails` changes:** add `university_id: EntityId | None` (permanent once set — a method on the entity replaces it wholesale, same immutable-value-object discipline as every other field here; no partial mutation). **Keep `university_name: str | None`** exactly as it is — field stays, but nothing in Chunk 4's application layer will accept it as new input going forward (it becomes read-only legacy data, not a dead field — existing values must keep rendering correctly).

**New outbound port, `UniversityProvider`:** one method, `get_university(university_id: EntityId) -> UniversitySummary | None` (`UniversitySummary`: id, official_name, status).

**Database:** `student_profiles` gains `university_id UUID NULL` (no foreign key — cross-module, same discipline as every other cross-module reference in this project), indexed. `university_name` column is untouched. Migration: `poetry run alembic revision --autogenerate -m "add university_id to student_profiles"`, read before applying.

**Tests you must write:** `tests/unit/profile/domain/test_student_profile_details.py` — extend with: `university_id` can be set independently of `university_name`; both can coexist on an existing (pre-migration-pattern) record without either being silently cleared by unrelated field updates.

**Acceptance criteria:** new/updated tests pass; migration applies cleanly; Profile's pre-existing suite otherwise unaffected.

---

## CHUNK 4 — PROFILE: APPLICATION LAYER & API
**[FOR YOU — GEMINI CLI]**

**Files to create:** `adapters/university/university_provider.py` — `InProcessUniversityProvider` implementing `UniversityProvider`, calling University & Location's `GetUniversity` use case directly (its `application.ports` only, never `adapters`/`domain` — same discipline as every in-process adapter in this project).

**Files to modify:** `application/use_cases/update_student_profile.py`, `adapters/api/schemas.py`, `adapters/api/router.py` (wiring the new adapter into composition only — no route changes).

**`UpdateStudentProfile`, revised steps for the `university_id` field specifically (every other field's handling is unchanged):**
1. If `university_id` is supplied in the request, call `UniversityProvider.get_university` — `None` result raises `InvalidProfileData` (Profile's existing error type, reused, message naming the university id that didn't resolve).
2. If it resolves, set `university_id` on the entity **and clear `university_name`** — the two are mutually exclusive going forward, same pattern as Profile's own earlier avatar migration (Module 06B, Chunk 9): once the canonical field is set, the legacy one is superseded, not left to drift alongside it.
3. `university_name` is **no longer an accepted field on this request at all** — remove it from the Pydantic schema entirely, with `model_config` set to reject unknown fields (`extra="forbid"`) so a client still sending the old field gets an immediate, clear `422`, not silent ignoring.

**Response shape, `GET /profiles/me` and `GET /profiles/{id}`'s `student_details`:** `university_name` (flat string) becomes `university: {"type": "canonical", "value": {"id": "...", "official_name": "..."}} | {"type": "legacy_text", "value": "..."} | null` — canonical when `university_id` is set (resolve the name via `UniversityProvider` at read time, same as every other read-time resolution in this project), legacy when only the old free-text field has a value, `null` when neither does.

**Tests you must write:** `tests/unit/profile/application/test_update_student_profile.py` — extend with: setting `university_id` to a valid id succeeds and clears any existing `university_name`; setting it to a nonexistent id raises `InvalidProfileData` without changing anything; the old field is rejected with `422` if a client sends it. `tests/api/profile/test_profile_flow.py` — extend with: the response shape test for all three states (canonical / legacy / null).

**Acceptance criteria:** new/updated tests pass; `poetry run pytest tests/unit/profile tests/integration/profile tests/api/profile` shows the same results as before this chunk, plus the new ones.


---

## CHUNK 5 — SEARCH: PROVIDER UPDATES
**[FOR YOU — GEMINI CLI]**

**Files to modify (module: Search & Discovery):** `application/ports/outbound.py` (`StudentPreferences`, `UniversityLocationProvider`), `adapters/profile/profile_provider.py`, `adapters/university_location/university_location_provider.py`.

**`StudentPreferences` gains `university_id: EntityId | None`** — Search's `InProcessProfileProvider` now maps this straight through from Profile's `GetCurrentUserProfile` response (which, after Chunk 4, carries the resolved `university_id` directly on the student details — Search does **not** need to know anything about the canonical/legacy response-shaping Profile does for its own HTTP layer; the in-process use case response is the plain underlying field).

**`UniversityLocationProvider` (Search's own outbound port, from Module 6) gains `get_main_campus_coordinates(university_id: EntityId) -> Coordinates | None`** — `InProcessUniversityLocationProvider` implements it by calling University & Location's new `get_main_campus` (Chunk 2), mapping `None` through unchanged, and pulling just the coordinates out of the result otherwise (same field-mapping discipline as every other adapter in this project — translate into Search's own `Coordinates` type, don't import University & Location's).

**Tests you must write:** extend `tests/unit/search/adapters/test_profile_provider.py` and `test_university_location_provider.py` with the new field/method, same fake-backed pattern as every existing test in those files.

**Acceptance criteria:** new tests pass.

---

## CHUNK 6 — SEARCH: DISCOVERY RANKING REBALANCE
**[FOR YOU — GEMINI CLI]**

**Files to modify:** `application/strategies/recommended_for_you.py` (the `DiscoveryRankingStrategy`'s factor table from Module 6, Chunk 5).

**New table, replacing the old three-factor one exactly (ADR-091):**

| Factor | Weight | Formula | When excluded |
|---|---|---|---|
| Preference match | 0.40 | unchanged from Module 6 | student has no preferences set at all |
| Proximity | 0.20 | same formula as Search's own ranking (Module 6, Chunk 4): `max(0, 1 - distance_km / 10)` | student's `university_id` is unset, **or** `get_main_campus_coordinates` returns `None` for it (ADR-092) |
| Verification | 0.20 | unchanged | never excluded |
| Freshness | 0.20 | unchanged | never excluded |

**Steps added to `RecommendedForYou`:** after resolving the student's preferences (already happens today), if `university_id` is set, call `UniversityLocationProvider.get_main_campus_coordinates` **once per request**, same N+1 discipline as every batched/single lookup in this project — not once per candidate. Compute each candidate's distance using the same Haversine function already built in Module 6, Chunk 4 — reused directly, not reimplemented.

**The no-profile fallback (Module 6, ADR-067) is unchanged** — a caller with no profile at all still degrades to `RecentlyAdded`'s behavior exactly as before; this chunk only changes what happens once personalization *does* apply.

**Tests you must write:** extend `tests/unit/search/application/test_recommended_for_you.py` — a student with `university_id` set scores a nearby candidate higher than a distant one, all else equal; a student with `university_id` unset gets the renormalized three-factor score exactly as Module 6 originally specified (proving the fallback still works, not just the new path); a student whose university has no main campus flagged behaves identically to having no `university_id` at all.

**Acceptance criteria:** new tests pass; `poetry run pytest tests/unit/search tests/integration/search tests/api/search` shows the same results as before this chunk, plus the new ones.


---

## CHUNK 7 — END-TO-END TESTING
**[FOR YOU — GEMINI CLI]**

**Files to create:** `tests/api/profile/test_university_migration.py`, `tests/api/search/test_discovery_proximity.py`.

**`test_university_migration.py`:** a Student sets `university_id` via `PATCH /profiles/me/student` with a real, seeded university id — confirm `GET /profiles/me` now shows the `canonical` shape with the correct resolved name; attempt the same with a nonexistent id — expect `422`; attempt sending the old `university_name` field — expect `422` naming it as an unrecognized field, not silently ignored.

**`test_discovery_proximity.py`, the real end-to-end proof:** seed a university with a main campus at known coordinates; create two listings at different distances from it; a Student sets `university_id` to that university; call `GET /discovery` and confirm the nearer listing ranks above the farther one, all else equal — this is the actual retirement of Module 6's ADR-062, proven through real HTTP, not just unit-level fakes.

**Acceptance criteria:** both tests pass; `poetry run pytest && poetry run ruff check . && poetry run mypy src && poetry run lint-imports` — the whole project green, every module.

---

## CHUNK 8 — DOCUMENTATION & AI STATE
**[FOR YOU — GEMINI CLI]**

**Update `docs/modules/profile.md`:** the `university_id`/`university_name` field description, the mutual-exclusivity rule, the response shape, and — explicitly — that existing `university_name` records are not automatically migrated (ADR-089), so a reader doesn't assume a backfill job ran somewhere.

**Update `docs/modules/university_location.md`:** document `get_main_campus` alongside the rest of `UniversityLocationQueryPort`.

**Update `docs/modules/search.md`:** replace the "no campus-proximity discovery" known limitation (which pointed at this exact migration as its unblock condition) with the new factor table from Chunk 6, and a note that it's now live.

**Update `AI_state/`** across all three modules using the standard `CURRENT_TASK.md` status-block format: `DECISIONS.md` (append ADR-089–093, filed once, referenced from whichever module's state a reader opens first — your call where the canonical copy lives, cross-reference from the others), `ARCHITECTURE_STATE.md` for each of the three modules, `API_STATE.md` for Profile (the changed request/response shape).

**Acceptance criteria:** all three modules' documentation and AI state reflect this change; the retired limitation in `search.md` is actually removed, not left alongside the new capability as a contradiction.

---

## CHUNK 9 — FINAL VERIFICATION
**[FOR YOU — GEMINI CLI]**

Run the full project suite from a clean state. Confirm every item below, then report completion.

### COMPLETION CHECKLIST [FOR NSISONG]

- [ ] A Student can set `university_id` and see it resolved correctly in their profile response.
- [ ] The old `university_name` field is rejected on write, with a clear `422`, not silently accepted or ignored.
- [ ] Existing `university_name` data still renders correctly (as `legacy_text`) for profiles that haven't migrated — nothing destructive happened to it.
- [ ] `university_location`'s `get_main_campus` correctly resolves the flagged campus, and correctly returns nothing when there isn't one.
- [ ] Discovery's proximity ranking is live and proven end-to-end — a real nearer listing outranks a real farther one for a migrated student.
- [ ] The no-profile and no-university fallbacks both still work exactly as Module 6 originally specified — this migration added a capability, it didn't remove graceful degradation.
- [ ] No cross-module database access introduced anywhere in this change.
- [ ] Unit, integration, API, and architecture tests pass — every module, together.
- [ ] Documentation updated in all three affected modules, with the retired Search limitation actually removed.
- [ ] Identity, Security, Housing, Verification, and Media/File are all confirmed untouched and their suites pass unchanged.

