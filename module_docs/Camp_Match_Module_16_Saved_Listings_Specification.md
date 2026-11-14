# CAMP MATCH — MODULE 16: SAVED LISTINGS
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Nsisong → Claude, "users can like or save a listing" request. Design defaults were proposed in chat and accepted by "get started"; they are recorded in Part B.**

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** Gemini reads all of it, then works through the chunks **in order, one at a time**. After each chunk Gemini stops and gives a Completion Report; you check it and reply **"Proceed to Chunk N"**. Parts marked **[FOR NSISONG]** are for you (findings, decisions, frontend documentation, manual testing guide).

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

1. **Read the entire file before doing anything.** Part C (Design Specification) is the reference every chunk points back to ("C3", "ADR-206"). Part D is your work. Part G is the source for the manual-testing document you write in Chunk 10.
2. **Your first action is Chunk 1** (inspection and scaffolding, no behavior). Write nothing else first.
3. **One chunk at a time, in order**, only after Nsisong replies "Proceed to Chunk N". Never combine, reorder, skip, or work ahead.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; files created and changed; every command run with its **real** output; each acceptance criterion marked pass or fail; any deviation or open question. Claim nothing you did not verify.
5. **If anything blocks you — a failing acceptance item, the repository contradicting this file, two parts disagreeing, or a decision this file does not make — stop and report.** Do not choose for yourself or weaken a test.
6. The Standing Instructions in `AI_instructions/` apply throughout. Change only what a chunk names plus what the C9 touch map allows. After any chunk that touches an existing module, re-run that module's full suite and confirm it is unchanged apart from the documented additions.

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

This is a small, self-contained feature: a student taps a heart on a listing, and later sees their saved listings in one place. It adds **one new module** (`saved_listings`) and makes **two small, specified additions** to existing modules: Housing gains two in-process lookups, and Search results and listing detail gain an `is_saved` true/false so the app can draw the heart. It has **11 chunks.**

**Explicitly not in this module:** notifications ("someone saved your listing", "a saved listing is available again"), save counts shown to scouts, collections or folders, sharing a saved list, price-drop alerts. Each is a clean later addition; none is blocked by what is built here.

---

## PART A — FINDINGS [FOR NSISONG]

**Finding 1 — Housing's browse list is authenticated.** `GET /listings` (and Search, which sits on top of it) require a signed-in user, so there is always a known viewer. That makes an `is_saved` flag on every result straightforward and means no anonymous case needs designing.

**Finding 2 — a "visible" listing is `PUBLISHED`, nothing else.** Housing's states are `DRAFT`, `PUBLISHED`, `UNAVAILABLE`, `ARCHIVED`, plus `SUSPENDED` from Trust & Safety. Only `PUBLISHED` is shown to the public. A listing can be `PUBLISHED` but currently **full** (no free units); it stays visible, and a student may reasonably want to save it in case a place opens up. So there are three saved-list states, not two: available, fully booked, and no longer available.

**Finding 3 — a save must survive a listing going away and coming back.** If a scout pauses a listing or a safety suspension is applied and later lifted (Module 13, Module 15), a student's save should still be there when the listing returns. Deleting saves when a listing disappears would destroy that. So saves are **never deleted by visibility changes**; the saved list simply shows a no-detail placeholder while the listing is hidden.

**Finding 4 — saves are private by design.** No scout or staff API in this module reveals who saved what. That is a privacy decision (ADR-207), not an omission.

**No corrections** to earlier documents were needed.

---

## PART B — DECISIONS [FOR NSISONG]

| ADR | Decision | Why |
|---|---|---|
| 204 | A **new small module, `saved_listings`**, owns saves. Housing and Search keep no saved state | A student's saves are not a property of a listing; this keeps Housing clean and the data deletable as one unit |
| 205 | **Save is `PUT /saved-listings/{listing_id}`, unsave is `DELETE`**, both idempotent | A double-tap or a retried request must never error or duplicate |
| 206 | **Only a `PUBLISHED` listing can be saved** (anything else → `404`, indistinguishable from "does not exist"); **never your own listing** (`409 cannot_save_own_listing`); a **per-user cap** (`saved_listings_max_per_user`, default 200 → `409 saved_limit_reached`). Re-saving something already saved succeeds even at the cap | A student must not learn that a hidden listing exists; the cap bounds the table and the page cost |
| 207 | **Saves are private.** No endpoint exposes who saved a listing; this module publishes **no** counts | Privacy first; counts can be added deliberately later |
| 208 | The saved list returns, per save, an **`availability`** of `AVAILABLE`, `FULLY_BOOKED`, or `UNAVAILABLE`. For `UNAVAILABLE` the listing details are **withheld entirely** (a placeholder). Rows are **never deleted** because of a visibility change | Finding 3 |
| 209 | **`is_saved` on Search results and on listing detail**, computed by **one batched lookup per page** through an in-process port | The heart must be correct on every card without an N+1 |
| 210 | **No events, notifications, or background jobs** in this module | Nothing consumes them yet; adding them now would be noise |
| 211 | **Concurrency:** primary key `(user_id, listing_id)` with `INSERT … ON CONFLICT DO NOTHING`; the cap is enforced inside the transaction under a **per-user advisory lock** so concurrent saves cannot exceed it | Correct under races, with no shared mutable state |

**Decisions made from my chat proposal (recorded):** the `is_saved` flag is included (not a bare list of ids); there are no new permissions (any signed-in user may save).

---

## PART C — DESIGN SPECIFICATION

### C1. Rules specific to this module
1. `saved_listings` owns exactly one table and imports **no other module's internals**. Cross-module reads go through the other module's `application.ports` via in-process adapters, the established pattern. **No cross-module foreign keys.**
2. A save belongs to **one user**; every read and write is scoped to the **caller's own id** taken from their authenticated identity — **never** from a path or body parameter.
3. A listing that is not `PUBLISHED` must be **invisible** in this module's responses (no title, no photo, no price), exactly as it is invisible in Search.
4. Housing's two new lookups are **system use cases**: no actor, never reachable over HTTP, protected by a structural guard test (the Module 15 ADR-191 pattern).
5. Debug and test switches, if any, work only when `app_env` is `local` or `test`.

### C2. Layout (under `src/camp_match/`)
```
modules/saved_listings/
├── domain/        entities.py (SavedListing), errors-free value objects
├── application/
│   ├── errors.py
│   ├── ports/     inbound.py (SaveListing, UnsaveListing, ListSavedListings, GetSavedState)
│   │              outbound.py (SavedListingRepository, ListingCatalogProvider)
│   └── use_cases/
└── adapters/
    ├── persistence/ (models, repository)
    ├── housing/     (in-process adapter implementing ListingCatalogProvider)
    └── api/         (schemas, router, dependencies)
tests/{unit,integration,api}/saved_listings/
```

### C3. Domain and errors
`SavedListing`: `user_id` (`EntityId`), `listing_id` (`EntityId`), `saved_at` (`datetime`). Immutable; equality by `(user_id, listing_id)`.

| Error | Extends | `code` | Meaning |
|---|---|---|---|
| `ListingNotSavable` | `NotFoundError` | `listing_not_found` | listing absent **or not `PUBLISHED`** — the same error and message either way |
| `CannotSaveOwnListing` | `ConflictError` | `cannot_save_own_listing` | the caller owns the listing |
| `SavedLimitReached` | `ConflictError` | `saved_limit_reached` | the caller already has the maximum number of saves |

### C4. Ports
**Inbound** (`@dataclass` DTOs, `Protocol` with `execute`):
| Port | Request | Response |
|---|---|---|
| `SaveListing` | `user_id`, `listing_id` | `listing_id`, `saved_at`, `already_saved: bool` |
| `UnsaveListing` | `user_id`, `listing_id` | nothing |
| `ListSavedListings` | `user_id`, `PageRequest` | `Page` of `SavedListingItem` (C5) |
| `GetSavedState` | `user_id`, `listing_ids` (at most 100) | `set` of the ids that are saved |

**Outbound** (this module's own copies):
- `SavedListingRepository`: `add(saved, max_per_user) -> bool` (**True if newly saved, False if it already existed**; raises `SavedLimitReached` only when it is genuinely new and the cap is reached), `remove(user_id, listing_id) -> bool`, `list_page(user_id, page) -> Page[SavedListing]` (newest `saved_at` first, ties broken by `listing_id`), `saved_among(user_id, listing_ids) -> set[EntityId]`.
- `ListingCatalogProvider`: `get_for_saving(listing_id) -> ListingSavingInfo | None` (`owner_id`, `is_public`; `None` if the listing does not exist); `get_cards(listing_ids) -> dict[EntityId, ListingCard]` where `ListingCard` is `state` (`AVAILABLE`/`FULLY_BOOKED`/`UNAVAILABLE`) plus, **only when `state` is not `UNAVAILABLE`**, the card fields (C5).

### C5. Behavior
**`SaveListing`:** 1) `get_for_saving`; absent **or** `is_public` false → `ListingNotSavable`. 2) caller is the owner → `CannotSaveOwnListing`. 3) `repository.add(..., max_per_user)` in a unit of work. 4) Return `already_saved = not newly_added`. Nothing is published, nothing is notified (ADR-210).
**`UnsaveListing`:** `repository.remove`; succeeds whether or not a row existed; **never** checks the listing (it may no longer be visible — the user must still be able to remove the save).
**`ListSavedListings`:** page the user's saves, then **one** `get_cards` call for the page's ids. Each `SavedListingItem` is `listing_id`, `saved_at`, `availability`, and `listing` — the card for `AVAILABLE`/`FULLY_BOOKED`, **`null` for `UNAVAILABLE`**. A save whose listing is missing from the catalog response is treated as `UNAVAILABLE`. The card has exactly the fields of Search's `SearchResultItem` (Chunk 1 confirms them) so the app renders both with one component.
**`GetSavedState`:** `saved_among`; an empty input returns an empty set with no query.

### C6. Database — table `saved_listings`
| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID | not null — **no foreign key** (cross-module) |
| `listing_id` | UUID | not null — **no foreign key** |
| `saved_at` | timestamptz | not null, server default now |
| | | **primary key `(user_id, listing_id)`** |
Index `(user_id, saved_at DESC, listing_id)`. Read the generated migration before applying it; `downgrade` must work.
**Cap enforcement in `add`:** inside the transaction take `pg_advisory_xact_lock(<64-bit hash of user_id>)`, then `INSERT … ON CONFLICT DO NOTHING RETURNING`; if nothing was inserted it already existed (return `False`); otherwise, if the user's count now exceeds the cap, the insert is rolled back and `SavedLimitReached` is raised. Re-saving at the cap never fails.

### C7. API (all require a signed-in user; **no new permission** — Chunk 1 confirms which dependency "authenticated" routes already use)
| Method | Path | Success |
|---|---|---|
| PUT | `/api/v1/saved-listings/{listing_id}` | `200` `{listing_id, saved: true, saved_at}` |
| DELETE | `/api/v1/saved-listings/{listing_id}` | `204` |
| GET | `/api/v1/saved-listings?page=&page_size=` | `200` paginated `SavedListingItem` (same page shape as every other list) |
Request models use `extra="forbid"`. The user id always comes from the token.

### C8. The two amendments to existing modules
**Housing (in-process, system use cases; no actor; not on any router):**
- `GetListingForSaving(listing_id) -> {owner_id, is_public} | None` — `owner_id` is the property's `provider_id` (the property owner); `is_public` is `status == PUBLISHED`.
- `GetListingCards(listing_ids)` — at most 100 ids; one query; for each id returns `state` (`AVAILABLE` when `PUBLISHED` and a unit has free capacity; `FULLY_BOOKED` when `PUBLISHED` with none; `UNAVAILABLE` for **every other status or a missing id**) and, for the first two states only, the same card fields Search returns. **A non-`PUBLISHED` listing never contributes any detail.**
- Listing detail (`GET /listings/{id}`) gains `is_saved` (bool) through a Housing outbound `SavedStateProvider` port implemented by an in-process adapter calling `GetSavedState`.
**Search:** `SearchListings` and `GetDiscoveryFeed` take the viewer's id, make **one** `SavedStateProvider.saved_among` call per page, and set `is_saved` on every `SearchResultItem`. Ranking, filtering, pagination and visibility are **unchanged**.
**Adapters live in the consuming module** (`modules/search/adapters/saved/`, `modules/housing/adapters/saved/`, `modules/saved_listings/adapters/housing/`) and import only the other module's `application.ports`. Import-linter contracts are extended to match.

### C9. Settings and touch map
Setting: `saved_listings_max_per_user` (int, default `200`, must be ≥ 1), in `.env.example`.
**Touch map — the only files outside `modules/saved_listings/`:** Housing (`application/ports/{inbound,outbound}.py`, two use cases, listing-detail schema/route, a small adapter), Search (`application/ports/outbound.py`, the two use cases' request DTOs, `SearchResultItem` schema, a small adapter), `app.py` (mount the router), `config/settings.py`, `.env.example`, migrations, import-linter contracts. **Not touched:** Identity, Security, Booking, Notification, Messaging, Admin, Trust & Safety, Payment, Media.

---

## PART D — CHUNKED IMPLEMENTATION

Every chunk ends the same way: run the full suite of every module the chunk touched, `poetry run ruff check .`, `poetry run mypy src`, and `poetry run lint-imports`, and report the real results.

---

### CHUNK 1 — INSPECTION & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** verify every assumption in this file against the repository. **Write no behavior.** Create only the empty `modules/saved_listings/` skeleton (C2), each file with a one-line docstring, plus the three test folders.

**Inspect and report, with file paths and exact signatures:**
1. **Housing:** `ListingStatus` members now (is there a `SUSPENDED` member?); the exact `GetListing` use case and `GET /listings/{id}` response schema; how a listing's owner is determined (listing → property → `provider_id`); how `ListActiveListings` computes availability.
2. **Search:** `SearchListings`/`GetDiscoveryFeed` request DTOs; the exact `SearchResultItem` fields; how the routes obtain the caller's identity; whether results are ever served to an unauthenticated caller.
3. **Authentication on routes:** which dependency the "authenticated" routes use today (Identity's `get_current_identity_id`, or a Security-module dependency), so Chunk 6 uses the same one.
4. **Conventions:** `Page`/`PageRequest`, how `UnitOfWork` is used by recent modules, how request models are declared (`extra="forbid"`?), how modules register routers in `app.py`, how existing in-process adapters are structured (copy one), the frontend API doc location.
5. **Any existing "favorite", "like" or "saved" code or table** anywhere in the repository (there should be none; report if there is).

**Output:** a **mapping table** (assumption → what the repository actually has) and every difference. A difference that changes a later chunk is reported now.

**Acceptance criteria:** the skeleton imports; the existing suite is unchanged; `lint-imports` is clean; the mapping table is complete. **Stop after this chunk.**

---

### CHUNK 2 — DOMAIN, ERRORS & SETTINGS
**[FOR YOU — GEMINI CLI]**

Implement C3 (`SavedListing`, the three errors with the exact `code`s, each extending the shared-kernel category shown) and the `saved_listings_max_per_user` setting (typed, validated ≥ 1, in `.env.example`).

**Tests:** `SavedListing` equality by `(user_id, listing_id)` regardless of `saved_at`; immutability; each error is an instance of its parent with the exact `code`; the setting defaults to 200 and a value below 1 fails startup.

**Acceptance criteria:** new tests pass; domain imports only the shared kernel and the standard library.

---

### CHUNK 3 — PORTS & USE CASES
**[FOR YOU — GEMINI CLI]**

Implement C4 and C5: the inbound and outbound ports, and the four use cases built **only** against ports (no database, no FastAPI). Put shared fakes in `tests/support/saved_listings_fakes.py` (an in-memory repository that honors the same add/cap/idempotency contract, and a fake `ListingCatalogProvider`).

**Tests (fakes only):** saving a published listing succeeds and a repeat returns `already_saved = true` without a second row; a non-existent listing and a non-published listing both raise the **identical** `ListingNotSavable` (same message); saving your own listing → `CannotSaveOwnListing`; the cap: the 200th save succeeds, the 201st raises `SavedLimitReached`, and re-saving an existing one at the cap succeeds; unsave of a saved listing, of an unsaved listing, and of a listing that is no longer visible all succeed; the saved list is newest-first with deterministic tie-breaking and exactly **one** `get_cards` call per page; an `UNAVAILABLE` card yields `listing: null`; a save missing from the catalog response is `UNAVAILABLE`; `GetSavedState` returns only the caller's saved ids and makes no query for an empty input.

**Acceptance criteria:** tests pass using fakes only.

---

### CHUNK 4 — HOUSING: THE TWO SYSTEM LOOKUPS & THE ADAPTER
**[FOR YOU — GEMINI CLI]**

Implement **C8, Housing part (lookups only)**: `GetListingForSaving` and `GetListingCards` as Housing inbound ports and use cases, then the in-process adapter in `modules/saved_listings/adapters/housing/` implementing `ListingCatalogProvider`. **Housing's existing behavior, return values and tests must not change.** Add the structural guard: no router module imports either use case.

**Tests:** `is_public` is true only for `PUBLISHED`; the owner id is the property's provider; `GetListingCards` returns `AVAILABLE` for a published listing with free capacity, `FULLY_BOOKED` for a published one with none, and `UNAVAILABLE` — **with no detail fields at all** — for `DRAFT`, `UNAVAILABLE`, `ARCHIVED`, `SUSPENDED` and a missing id; one query for a 100-id batch (assert the query count); more than 100 ids is rejected; card fields equal what Search returns for the same listing; the guard test fails when a router imports the use case (prove with a fixture); the adapter maps correctly.

**Acceptance criteria:** Housing's and Search's entire suites unchanged apart from the additions.

---

### CHUNK 5 — PERSISTENCE & MIGRATION
**[FOR YOU — GEMINI CLI]**

Implement C6: the `saved_listings` table and migration (**read it before applying; `downgrade` must work**), and `SqlAlchemySavedListingRepository` with the advisory-lock cap logic.

**Tests (integration, real DB):** add then list; re-adding returns `False` and leaves one row; ordering newest-first; `saved_among` returns the right subset; remove is idempotent; **concurrency (three consecutive runs):** 20 simultaneous saves of distinct listings by one user with a cap of 10 → exactly 10 succeed and 10 raise `SavedLimitReached`; 20 simultaneous saves of the **same** listing → exactly one row and every call succeeds; two different users saving the same listing never interfere; the table has no foreign keys.

**Acceptance criteria:** tests pass; migration round-trips; `lint-imports` clean (nothing outside `adapters/persistence/` imports SQLAlchemy).

---

### CHUNK 6 — API ADAPTER
**[FOR YOU — GEMINI CLI]**

Implement C7: schemas (`extra="forbid"`, descriptions and examples on every field), dependencies (composition with the real repository, the Housing adapter and the settings; the authentication dependency Chunk 1 identified), the three routes, and mount the router in `app.py`. No business logic in the router.

**Tests (API):** `PUT` a published listing → `200` with `saved: true`; repeating it → `200` again; `PUT` an unknown id and a hidden one → `404` with **byte-identical** bodies; `PUT` your own listing → `409 cannot_save_own_listing`; `PUT` beyond the cap → `409 saved_limit_reached`; `DELETE` → `204` whether saved or not; `GET` returns newest first, paginated; every route without a token → `401`; the user id cannot be overridden through any parameter (try a body field and a query parameter → ignored or `422`); an unknown request field → `422`.

**Acceptance criteria:** new tests pass; the full suite is unchanged.

---

### CHUNK 7 — SEARCH: `is_saved` ON RESULTS
**[FOR YOU — GEMINI CLI]**

Implement **C8, Search part**: the outbound `SavedStateProvider` port, the in-process adapter in `modules/search/adapters/saved/`, the viewer id passed into `SearchListings` and `GetDiscoveryFeed`, and `is_saved` on `SearchResultItem` and its schema. **Ranking, filters, pagination and visibility must not change.**

**Tests:** a viewer who saved two listings sees `is_saved: true` on exactly those and `false` on the rest, on both the search and discovery routes; exactly **one** `saved_among` call per page (assert with a spy); another user's saves never affect the flag; a page with no results makes no call; with the same data, ordering and pagination are **identical** to before the change (regression); **every existing Search test passes unmodified**.

**Acceptance criteria:** Search's entire suite passes unchanged apart from the additions.

---

### CHUNK 8 — HOUSING: `is_saved` ON LISTING DETAIL
**[FOR YOU — GEMINI CLI]**

Implement **C8, Housing detail part**: the outbound `SavedStateProvider` port, the in-process adapter in `modules/housing/adapters/saved/`, the viewer id through `GetListing`, and `is_saved` on the detail schema. Housing's other responses are unchanged.

**Tests:** detail shows `true` after a save and `false` after an unsave; another user sees `false`; **the Housing detail response for a viewer who saved nothing differs from before only by the new field**; Housing's entire suite passes.

**Acceptance criteria:** Housing's suite unchanged apart from the additions.

---

### CHUNK 9 — FULL TESTING & SECURITY VERIFICATION
**[FOR YOU — GEMINI CLI]**

Write `tests/api/saved_listings/test_saved_flow.py` and `test_saved_security.py`, plus extend the import-linter contracts (`saved_listings.domain`/`application` import no `fastapi`/`sqlalchemy`; nothing outside `saved_listings` imports its `adapters`).

**Flow test (one journey through real HTTP):** a student searches, saves a listing, sees `is_saved: true` in search and detail, lists saves, unsaves, sees `false`. **Visibility journey:** save a listing; the scout pauses it (`UNAVAILABLE`) → the saved list shows it as `UNAVAILABLE` with `listing: null`; the scout republishes → the card returns **with the save intact**; Trust & Safety suspends it (through the real use case) → placeholder again; lifting restores it; archiving it → placeholder permanently; unsave still works throughout. **Full-listing journey:** a published listing whose units are all booked is saved and shown `FULLY_BOOKED` with its card; when a unit frees, `AVAILABLE`.

**Security test:** a user cannot read, add or remove another user's saves by any route or parameter; the placeholder response contains **no** title, photo, price, location or any listing field; a hidden listing's `PUT` and an unknown id's `PUT` are indistinguishable (bodies and timing-independent status); no response or log line contains another user's id; the saved list is bounded by `page_size` and cannot be used to enumerate unlimited rows.

**Acceptance criteria:** all pass; the **entire** project suite passes; ruff, mypy and import-linter are clean.

---

### CHUNK 10 — DOCUMENTATION, MANUAL GUIDE & AI STATE
**[FOR YOU — GEMINI CLI]**

Write `docs/modules/saved_listings.md` (purpose, the three availability states, privacy rule, concurrency approach, the two amendments, known limitations including "no notifications and no counts"); add the amendment paragraphs to the Housing and Search module docs; update the project-wide frontend API document from **Part F**; update every `AI_state/` file the Standing Instructions require.

**The manual testing guide** is `docs/manual_testing/module_16.md`, written from **Part G** under these rules (the reader is not a backend specialist): (1) a short "Start here" with the test accounts and the two copy-paste helper functions, each explained in one line; (2) every test uses the same five headings — *What this proves (one plain sentence)* · *Do this* · *You should see* · *If you don't* · *Cleanup*; (3) every step is a **runnable command** with a short example of real output; (4) no jargon without a one-line explanation; (5) **only commands you actually ran**; anything in Part G marked *(Gemini verifies)* must be confirmed or corrected.

**Acceptance criteria:** every doc exists and is accurate; the guide's commands were each run and the real outputs are in the report.

---

### CHUNK 11 — FINAL AUDIT & COMPLETION REPORT
**[FOR YOU — GEMINI CLI]**

Run the entire suite three times; `lint-imports`; apply and downgrade/re-upgrade this module's migration on a fresh database; verify the C9 touch map (every changed file outside `modules/saved_listings/` is listed and justified); fill the Completion Checklist; classify readiness in three honest lists: **ready for production use / ready for testing only / not built** (the last must include notifications, scout-facing counts, collections, and price/availability alerts).

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

| Your request | Built in | Proven in |
|---|---|---|
| Users can like/save a listing and unsave it | Chunks 3, 5, 6 | Chunks 3, 5, 6, 9 |
| See all saved listings in one place | Chunks 3, 4, 6 | Chunks 3, 4, 6, 9 |
| Heart shows correctly on search results and detail | Chunks 7, 8 | Chunks 7, 8, 9 |
| Saved listing disappears when suspended/paused and returns when restored | Chunks 3, 4 | Chunk 9 |
| Privacy and abuse limits (own listing, cap, other users) | Chunks 3, 5, 6 | Chunks 5, 6, 9 |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**`PUT /api/v1/saved-listings/{listing_id}`** — save a listing. Requires sign-in. `200` → `{ "listing_id": "uuid", "saved": true, "saved_at": "ISO 8601" }`. Safe to call again (it just returns `200`). Errors: `404 listing_not_found` (the listing doesn't exist **or is not visible** — treat both the same); `409 cannot_save_own_listing`; `409 saved_limit_reached` (default 200 saves).

**`DELETE /api/v1/saved-listings/{listing_id}`** — unsave. `204`, always, even if it wasn't saved or the listing is now hidden.

**`GET /api/v1/saved-listings?page=1&page_size=20`** — the user's saves, **newest saved first**. Each item: `listing_id`, `saved_at`, `availability`, and `listing`.
- `availability: "AVAILABLE"` → `listing` is the full card (same shape as a search result).
- `"FULLY_BOOKED"` → `listing` is the card; show a "fully booked" badge.
- `"UNAVAILABLE"` → **`listing` is `null`**. The listing is hidden right now (paused, suspended, archived). Show a plain "No longer available" row with a **remove** button; do not show any details. If it comes back, it reappears on its own.

**The heart icon:** every search result, discovery result and listing-detail response now includes **`is_saved`** (true/false) — draw the heart from it. After a `PUT` or `DELETE`, flip the heart locally; no refetch needed.

**Rules to remember:** a user cannot save their own listing; saves are private; there is no count of how many people saved a listing.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — and Gemini's source for `docs/manual_testing/module_16.md`]

**Read this first.** You'll use the app like a student would: save a listing, see it in a list, and watch it behave when a listing is paused or suspended. You don't need to read code. Each test says what to do and what you should see.

**The cast:** **Ada** (a student), **Bola** (a scout with at least two published listings, A and B), **Rita** (`OPERATIONS`), **Ade** (`ADMIN`). *(Gemini verifies the real emails.)*

**Two helpers** — paste once per Termux session. *(Gemini verifies the login path and field names.)*
```
BASE=http://localhost:8000/api/v1
login() { curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' -d "{\"email\":\"$1\",\"password\":\"$2\"}" | jq -r '.access_token'; }
api() { curl -s -X "$1" "$BASE$2" -H "Authorization: Bearer $3" -H 'Content-Type: application/json' ${4:+-d "$4"} | jq .; }
```
Then `ADA=$(login ada@example.com password)` and likewise `BOLA`, `RITA`, `ADE`. Note the ids of listings A and B (`LA`, `LB`).

**S1 — Save and unsave.**
*What this proves:* tapping the heart works and can be repeated safely.
*Do this:* `api PUT /saved-listings/$LA $ADA`, twice. Then `api GET /saved-listings $ADA`. Then `api DELETE /saved-listings/$LA $ADA` and list again.
*You should see:* both `PUT`s succeed with `saved: true`; the list has one item; after the `DELETE` the list is empty.
*If you don't:* a duplicate row, or an error on the second `PUT`, is a real bug.

**S2 — The heart on search.**
*Do this:* save listing A. Search or browse as Ada *(Gemini verifies the search route)* and find A and B.
*You should see:* `is_saved: true` on A and `false` on B. Open A's detail: `is_saved: true`.

**S3 — Saves are yours alone.**
*Do this:* as Bola, `api GET /saved-listings $BOLA`.
*You should see:* an empty list — Ada's saves are invisible to everyone else.

**S4 — You can't save your own listing.**
*Do this:* as Bola, `api PUT /saved-listings/$LA $BOLA`.
*You should see:* `409` with `cannot_save_own_listing`.

**S5 — Hidden listings look like they don't exist.**
*Do this:* have Bola pause listing B (set it `UNAVAILABLE`). As Ada, `PUT` B. Also `PUT` a made-up id (`00000000-0000-0000-0000-000000000000`).
*You should see:* the same `404 listing_not_found` for both, with identical bodies.

**S6 — A save survives the listing disappearing and returning.**
*Do this:* Ada saves A. Bola pauses A. As Ada, list saves. Bola republishes A. List again.
*You should see:* while paused, A's row shows `availability: "UNAVAILABLE"` and `listing: null` (no title, no price, nothing); after republishing, the full card is back **and nothing was lost**. Ada can remove the row either way.

**S7 — Suspension does the same.**
*Do this:* with A saved by Ada, suspend A through Module 13's flow (Rita proposes, **Ade** approves — Gemini writes every command out in full). List Ada's saves. Then lift the suspension and list again.
*You should see:* a placeholder while suspended; the card is back after the lift.

**S8 — Fully booked still shows.**
*Do this:* fill every unit of listing A through bookings (or set capacity so none is free) *(Gemini verifies the quickest way)*. List Ada's saves.
*You should see:* `availability: "FULLY_BOOKED"` and a full card. Free a unit and it becomes `AVAILABLE`.

**S9 — The cap.**
*Do this:* set `SAVED_LISTINGS_MAX_PER_USER=2` **and restart the API.** Ada saves A, then B, then a third listing C.
*You should see:* the third `PUT` returns `409 saved_limit_reached`; saving A again still succeeds.
*Cleanup:* remove the setting and restart.

**Stuck?** (1) `401` → your token expired; run `login` again. (2) Nothing in the list after a save → check you used Ada's token. (3) A test needing a paused/suspended listing fails → check the listing really changed status first. (4) Connection errors → the database isn't up; run `scripts/db_start.sh`.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] Chunk 1 mapping table complete; every difference reported before Chunk 2.
- [ ] `saved_listings` table has **no foreign keys**; primary key `(user_id, listing_id)`; migration round-trips.
- [ ] Save and unsave are idempotent; the cap holds under concurrency (three consecutive runs); re-saving at the cap succeeds.
- [ ] A non-`PUBLISHED` listing and a missing id produce **identical** `404` bodies; your own listing is refused; unsave always works.
- [ ] The saved list is newest-first, paginated, uses **one** catalog lookup per page, and shows **no listing detail** for `UNAVAILABLE` rows.
- [ ] Visibility journeys pass: paused → placeholder → restored; suspended → placeholder → lifted; archived → placeholder permanently; saves are never deleted by a visibility change.
- [ ] `is_saved` is correct on search, discovery and detail with **one** batched lookup per page; ranking, filters and pagination are unchanged; every existing Search and Housing test passes.
- [ ] The two Housing lookups are not reachable over HTTP (guard test).
- [ ] No user can read or change another user's saves; no response or log leaks another user's id.
- [ ] Docs written; frontend API doc updated from Part F; AI state updated; the manual guide follows the plain-language rules and every command in it was run.
- [ ] The final report classifies readiness in three honest lists.
