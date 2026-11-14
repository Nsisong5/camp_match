# CAMP MATCH — MODULE 18: SELF-DESCRIBING API REQUESTS
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Nsisong → Claude: "when a request is wrong, the backend must tell me what it expects — the required fields, the types, the allowed values — on every endpoint that does not already do so. I don't want to open specification files to learn the shape of a request." The failure that triggered it (`POST /api/v1/messaging/conversations`) is reproduced in Part A. Design defaults are recorded in Part B.**

**Prerequisite: Modules 15, 16 and 17 are complete.** This module relies on Module 15's request-model guard (ADR-199, `extra="forbid"` everywhere) and on the routes Module 17 added. Chunk 1 confirms both and **stops if either is missing.**

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** Gemini reads all of it, then works through the chunks **in order, one at a time**. After each chunk Gemini stops and gives a Completion Report; you check it and reply **"Proceed to Chunk N"**. Parts marked **[FOR NSISONG]** are for you (findings, decisions, frontend documentation, manual testing guide).

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

1. **Read the entire file before doing anything.** Part C (Design Specification) is the reference every chunk points back to ("C3", "ADR-236"). Part D is your work. Part G is the source for the manual-testing document you write in Chunk 16.
2. **Your first action is Chunk 1** (inspection and scaffolding, no behavior). Write nothing else first.
3. **One chunk at a time, in order**, only after Nsisong replies "Proceed to Chunk N". Never combine, reorder, skip, or work ahead.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; files created and changed; every command run with its **real** output; each acceptance criterion marked pass or fail; any deviation or open question. Claim nothing you did not verify.
5. **If anything blocks you — a failing acceptance item, the repository contradicting this file, two parts disagreeing, or a decision this file does not make — stop and report.** Do not choose for yourself, weaken a test, or skip a route.
6. **The skip rule (the heart of this module).** An endpoint that **already** describes its own requests properly is **not touched** — not its router function, not its request model class, not its use case, not its tests. "Already" is decided **only** by the automated probe suite built in Chunk 2 (Part C9), never by reading specifications and never by your own judgement. Every module chunk (8–13) begins by listing, from the committed Fix List, which of its routes it is **skipping** and why; Chunk 17 proves the skipped routes are unchanged.
7. The Standing Instructions in `AI_instructions/` apply throughout. Change only what a chunk names plus what the C11 touch map allows. After any chunk that touches an existing module, re-run that module's **full** suite and confirm it is unchanged apart from the documented additions and the entries in the **behavior-change register** (ADR-246).

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

This is not a new business domain. It is one **shared mechanism** (a request-contract describer plus one validation-error handler, both in the platform layer) and a set of **small, targeted fixes** in the modules whose routes fail an objective test. When a request is wrong, the response says **every** problem at once and, for each problem, what was expected:

- a **missing** field → its name, and when it is only required under a condition ("`listing_id` is required when `context_type` is `LISTING`");
- a **wrong type or format** → what type or format was expected;
- a value outside a **closed set** (enum) → **the full list of allowed values**;
- an **unknown field** → the fields that are accepted;
- a **number or length out of range** → the limit;
- and the **whole shape of the request** (every field, its type, whether required, its allowed values, an example body) attached to the error, so one failed attempt in Swagger teaches you the request.

Swagger itself is also fixed on the routes that need it: dropdowns for closed sets, a description on every field, and a valid example body that a test proves is valid.

**One honest note on "skip the endpoints that already do this".** Almost all of the improvement comes from **one** shared handler that every route passes through — that is what makes it consistent, and it is the only place it *can* live. It is global by nature. What stays selective is everything per-endpoint: only routes that the probe suite says are not already self-describing get their request models, rules, examples or error details edited. Routes that already pass keep their own code and tests untouched; they simply also gain the same extra detail in their `422` body, and they keep their existing `code` and a `message` that still contains everything it contained before (ADR-234).

**Explicitly NOT in this module:** any change to business rules, authorization, response bodies (other than validation errors), or status codes (other than the shape-failure moves recorded in the behavior-change register); a "contract explorer" HTTP endpoint (ADR-245 — a generated offline reference is built instead); localization of messages; making deliberately generic errors informative (Finding 3); webhook routes, the media stream route and the pre-authentication WebSocket handshake; response-schema documentation. Each is a clean later addition; none is blocked by what is built here.

**What I could and could not read.** I read the specifications of Modules 05–17 and the University migration. The specifications of **Identity (01), Profile (02), Security (03) and University & Location (04)** were not in the set I worked from, so I could not list their request shapes. That is why the route inventory is **generated from the running application** (Chunk 1 and 2) rather than taken from my tables, and why Chunk 13 is driven by the Fix List rather than by a list I wrote. My tables in Part A are a starting hypothesis, labelled as such.

It has **17 chunks.**

---

## PART A — FINDINGS AND CORRECTIONS [FOR NSISONG]

### The failure that triggered this module

You sent:
```json
{ "context_type": "CONVERSATION", "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6" }
```
to `POST /api/v1/messaging/conversations` and received:
```json
{ "error": { "code": "conversation_context_not_found", "message": "Unknown context type." } }
```
Three things are wrong with that, and each recurs elsewhere:
1. **`context_type` is accepted as free text** and only checked deep inside the use case, so the request is "valid" until it isn't.
2. **The answer lists no options.** The only valid values are `LISTING` and `BOOKING`; the response says neither.
3. **The status and code are wrong.** A bad *value* is a `422` (the request is malformed), not a `404 …_not_found` (a thing you looked up does not exist). `conversation_context_not_found` is meant for "that listing or booking does not exist", and now also means "your `context_type` is wrong" — two different problems under one code.

### FINDING 1 — five distinct reasons a route leaves you guessing
(They are different, so they get different fixes; Part C's remedy tree maps each.)
- **(a) A closed set is typed as free text.** The field is `str` in the request model and checked later (your case). Fix: type it at the boundary (enum / `Literal` / discriminated union) so the framework rejects it and the handler lists the options.
- **(b) A "this field decides which other fields are needed" pattern is enforced in the use case or by a database `CHECK`.** `context_type` → `listing_id` or `booking_id`; a safety report's `subject.type`; a safety enforcement's `action_type`. Fix: express it as a discriminated union or a **declared rule** so the contract can describe it.
- **(c) The shared validation handler gives too little.** Module 11's tests only promise "the standard `{error:{code,message}}` shape". Whether today's handler reports **all** problems, names fields, or lists allowed values must be measured, not assumed — Chunk 1 measures it. Fix: one new handler (C3, C4).
- **(d) Swagger is bare.** Only Modules 15, 16 and 17 required descriptions, examples and dropdowns on their request models. Modules 01–14 predate that rule. Fix: descriptions and examples on the routes the probe suite flags.
- **(e) A use case rejects a well-formed value for a policy reason and says nothing about the limit** — a message-length limit that comes from `Settings`, a media type that is not on the allowed list. Fix: those errors carry structured `details` (limit, allowed values) while keeping their code, status and message (C8).

### FINDING 2 — what already supports this (and is skipped)
From the specifications, only **Module 15's payment mock controls** are explicit: strict typed bodies, a nine-value `scenario` enum, descriptions and examples on every field, a `422` whose message "names every allowed value", and a `scenarios` endpoint (ADR-198). **Module 17's new routes** are specified with descriptions and examples but not with allowed-value messages, so they are *probably* partial. Everything else is unknown until probed. **I am deliberately not guessing the rest** — the probe suite (C9) decides, route by route, and its output (the **Fix List**) is committed and reviewed by you before any module is touched.

### FINDING 3 — some errors must never become informative
Earlier modules made certain errors **generic on purpose**, to stop strangers learning what exists: `invalid_or_expired_code` (one message for every email-verification failure), `invalid_google_token`, login failures, `conversation_not_found` (a non-participant sees the same as a missing id), `listing_not_found` on save (hidden looks like missing), `invalid_report_subject` (one message for every problem with a report's subject), `notification_not_found`, `case_not_found`, the media stream's single `403`, the always-the-same `202` on resend. **This module must not weaken any of them.** The rule (ADR-235): **only a *shape* problem — one that can be decided from the request alone, without reading any stored data and without knowing who the caller is — becomes descriptive.** "Is `context_type` one of two words" is a shape problem. "Is this listing visible to you" is not. The protected errors are unchanged, byte for byte, and a guard test proves it.

### FINDING 4 — four decisions about the *same* closed value
A closed value can be wrong in four different ways, and they must not be confused (this is the remedy tree in C7):
1. **Not a member of the field's own set** (`context_type = "CONVERSATION"`, `property_type = "VILLA"`) → boundary rejection, `422 validation_error`, allowed values listed.
2. **A valid member that policy refuses** (`role = ADMIN` on a route that can only grant `OPERATIONS`) → the existing domain error keeps its code, status and message and gains `details` with the permitted values.
3. **A valid member that the current data refuses** (a case in the wrong state) → business; untouched.
4. **A valid member that the caller may not know about** → protected; untouched.

### FINDING 5 — ordering of checks
Pydantic (boundary) validation runs **after** authentication and **before** the use case. Today a request with a bad enum value in a free-text field reaches the use case; after this module it is rejected at the boundary, which means a signed-in caller without the right permission now sees a `422` for a malformed request on a staff route **before** the `403`. That reveals only the *shape* of the request — which the OpenAPI document and your frontend documentation already show — never any data. An **unauthenticated** caller still gets `401` first, with no details. Chunk 1 reports whether OpenAPI is exposed outside local/test; see "Three small things worth a glance".

### FINDING 6 — the user's `404` is a mis-classification that appears elsewhere
I expect (Chunk 1 will confirm or refute, route by route) that other documented domain errors are really shape errors wearing a business code. Candidates, from the specifications: Search's `invalid_search_criteria` (a price bound with no `billing_period`); Messaging's `invalid_client_message_id`; Safety's `invalid_report_description` (10–2000 characters); Admin's "missing/short reason → 422". These are **hypotheses**, listed here only so you can see the kind of thing the Fix List will contain.

### FINDING 7 — "examples" drift unless something proves them
A hand-written example body in Swagger silently goes stale when a field is added. Every example added here is **parsed by a test against its own request model** (ADR-243), so a stale example fails the build.

### CORRECTIONS (things earlier documents said that change)
**Correction 1 — "validation errors use the standard `{"error": {"code", "message"}}` shape" (Modules 11, 12, 14) stays true, but the shape gains optional keys.** `code` and `message` are kept; `details` and `request_contract` are added. Nothing is removed.
**Correction 2 — Module 15 ADR-199 said an unknown field gets a `422`.** After this module that `422` also **names the field and lists the accepted ones**.
**Correction 3 — Module 11's rule "unknown listing → `404 conversation_context_not_found`" is unchanged for an unknown *listing or booking*.** Only an unknown `context_type` (and other pure shape failures) moves to `422 validation_error`. Every such move is recorded in the behavior-change register (ADR-246) and listed in Part F so the frontend knows.

### Preliminary route inventory (hypothesis — Chunk 1 and 2 replace it with the code-derived one) [FOR NSISONG]
Well over a hundred routes exist across the modules. The ones with closed sets or conditional fields — where I expect gaps — are:

| Module | Routes / inputs I expect to need work (to be proven by the probes) |
|---|---|
| Messaging | `POST /conversations` (`context_type` → `listing_id`/`booking_id`); `POST …/messages` (`client_message_id` format, settings-driven content limit); `GET …/messages` (`before`/`after` exclusive); WebSocket command frames |
| Housing | property `property_type`; unit `total_capacity`; listing `price_currency`, `price_period`, `price_amount_kobo`; list filters |
| Search | `billing_period`, `accommodation_type`, `amenities`, `sort_by`, `strategy`; price bound ⇒ `billing_period` |
| Saved Listings | path ids, paging (new module — may already pass) |
| Booking | `idempotency_key`, `cancellation_reason`, handover routes |
| Payment | `idempotency_key`, dispute `reason`, `resolve` resolution values; **mock controls: skip (already supports)**; webhook route: exempt |
| Verification | `target_type` (body and path), `evidence_type`, `item`/`passed`, `reason`, `inspector_id` |
| Notification | `category` (query and `read-all` body), `unread_only`, paging |
| Trust & Safety | report `category`, `subject` shape (LISTING / BOOKING / CONVERSATION + 1–5 `message_ids`); staff `priority`, `to_status`, note `kind`, `decision_type`, enforcement `action_type` |
| Admin & Operations | issue `category`/`priority`/`to_status`; staff `role`; `reason` bounds; Module 15's jobs, role-request and recovery routes |
| Identity / Profile / University / Security | not specified in what I read — the Fix List decides |
| Media | upload routes (avatar, listing photo, evidence): unsupported type and size should state the allowed types and limit |

---

## PART B — DECISIONS [FOR NSISONG]

### DECISIONS (ADR-233 … ADR-246)
Continuing the log from Module 17 (212–232).

| ADR | Decision | Why |
|---|---|---|
| 233 | **One shared mechanism in the platform layer** (describer, rules, translator, handler); per-module work is limited to typing, declared rules, descriptions/examples, and `details` on application errors | well over a hundred routes cannot each hand-write their own wording and stay consistent. The shared piece is the only place the behavior can be uniform |
| 234 | **The error envelope is additive.** `error.code` and `error.message` stay; `error.details[]` and `error.request_contract` are added. The top-level **`message` itself contains every problem** (one readable sentence per problem), so a client or test that only reads `message` still gets the whole story, and an existing assertion that looked for an allowed value in `message` still passes | Nothing that works today breaks, and the message alone is useful in Swagger |
| 235 | **Only shape problems become descriptive.** A shape problem is decidable **from the request alone**: presence, type, format, closed-set membership, length/range, unknown field, co-presence of fields. Anything that needs stored data or the caller's identity is business and is untouched. Deliberately generic errors are **protected** and byte-identical | Finding 3 |
| 236 | **A closed set is typed at the boundary** (enum / `Literal` / discriminated union). A value outside the field's **own** set → `422 validation_error` listing the allowed values. A **valid member refused by policy** keeps its domain code/status/message and gains `details` (Finding 4). Typing a field must **never make a previously accepted input invalid** (e.g. if a use case upper-cased the input, the type must too) | Fixes your case without breaking documented codes |
| 237 | **Rules are declared once; the declaration both enforces and describes.** "Required when", "exactly one of", "at least one of", "mutually exclusive" are small declarative helpers (C6), never opaque validator code | A rule written as plain code cannot appear in the contract, so the contract would lie |
| 238 | **Allowed values, accepted field names and constraints come from the model's schema, never by parsing Pydantic's message text. The translator never copies Pydantic's `msg` or `input`** — it composes its own message from the problem code and schema facts | Version-proof, and structurally incapable of echoing a secret |
| 239 | **`received` (what the client sent) is echoed only for closed-set fields**, at most 64 characters, never for a field on the sensitive-name list (C4). **No request value is ever logged**; logs carry route template, problem counts and problem codes only | Helpful for "you sent CONVERSATION", safe for passwords, tokens, message text |
| 240 | **`ApplicationError` gains optional `details`** (additive, shared kernel). Use cases that reject a well-formed value for a policy reason (settings-driven length, media type) attach structured details; `generic_by_design` classes never render them | Finding 1(e) without touching codes or statuses |
| 241 | **"Already supports it" is decided by one objective, automated, semantic probe suite** run in *report mode* **before** any fix. Routes that pass are on the **Skip List**; their router, request model class, use case and tests are not edited. The Fix List is committed and you review it before any module chunk | Your instruction, made testable instead of a judgement call |
| 242 | **`401` first, and no details on `401`/`403`/`404`.** Unauthenticated callers get `401` before any shape feedback. Exempt routes: payment webhooks (signature-authenticated, must keep acknowledging exactly as today), the media stream, the WebSocket handshake before `auth` | Feedback is for callers allowed to be there; webhooks and the stream are deliberately opaque |
| 243 | **Every example body added to a request model is parsed by a test against that model** | Finding 7 |
| 244 | **WebSocket post-`auth` error frames gain `details`** from the same translator; the `invalid_command` / `unknown_command` frames list the accepted commands and each command's required fields. Pre-`auth` behavior is unchanged | Messaging's frames are an API surface too |
| 245 | **No "contract explorer" endpoint.** Instead: Swagger fixed where needed, the rich `422`, and a **generated offline reference** — `scripts/print_request_contracts.py` writes every route's contract to Markdown/JSON from the same describer, so it cannot drift | The offline reference works in Termux, adds no production surface, and answers "don't make me open spec files" |
| 246 | **Behavior-change register.** Any route whose documented code/status for a *pure shape failure* changes is recorded in `docs/api_contract/behavior_changes.md` (route, input, old, new) and in Part F. Existing tests may be edited **only** on the assertion lines for that exact response, and every such edit is listed in the Completion Report. Business outcomes and success responses never change | The one deliberate exception to "existing tests stay unchanged" |

### Three small things worth a glance (I chose a default; tell me if you disagree)
- **Contract in every `422`.** Every validation error carries `request_contract` (the full shape of that route's request, with an example), capped by `api_validation_contract_max_bytes` (default 16384). It is the feature that stops you opening specs. If you find it noisy it can be turned off by one setting; the `details` stay.
- **Shape feedback on staff routes** (`/admin/…`, `/safety/review/…`) is shown to any **signed-in** caller who sends a malformed request, before the `403` (Finding 5). It reveals only request shape, never data, and your frontend documentation already lists those shapes. Chunk 1 reports whether OpenAPI is hidden outside local/test; if it is, tell me and I will add a staff-only gate for those two namespaces.
- **Code changes are real.** Your own example is one: `conversation_context_not_found` (404) for a bad `context_type` becomes `validation_error` (422). Each such change is listed in Part F; frontends that branch on the old code must be updated.

---

## PART C — DESIGN SPECIFICATION [FOR YOU — GEMINI CLI]

### C1. Rules every chunk obeys

1. **Shape problems only (ADR-235).** A shape problem is decidable from the request alone: presence, type, format, closed-set membership, length/range, unknown field, co-presence of fields. Anything needing stored data or the caller's identity is business and is **not touched**.
2. **One mechanism.** No module writes its own validation-error JSON. Modules supply *typed models, declared rules, descriptions, examples* and (rarely) `details` on their application errors; the platform handler does the rest.
3. **The envelope is additive (ADR-234).** `error.code` and `error.message` are kept. `error.details` and `error.request_contract` are added. A key with no value is **omitted**, not sent as `null`.
4. **Never copy Pydantic's `msg` or `input` (ADR-238).** Allowed values, accepted field names and constraints come from the **schema**. The translator composes every sentence itself.
5. **All problems at once.** A request with four problems gets four `details`, not the first one. Cap: `api_validation_max_details`; beyond it the message ends "and N more problems — see details" and `details` is truncated to the cap.
6. **Closed sets are typed at the boundary (ADR-236)** — enum, `Literal`, or discriminated union. Typing must **never make a previously accepted input invalid**: if a use case upper-cased or trimmed the value before checking it, the type must do the same (a `BeforeValidator`), so `"listing"` that worked before still works.
7. **Rules are declared once (ADR-237).** The declaration enforces *and* describes. No conditional requirement is written as an opaque validator.
8. **Protected errors are byte-identical (Finding 3, C7).** Their code, status, message and body do not change, and they never carry `details`.
9. **`401` first; details only on shape failures (ADR-242).** `401`, `403` and `404` responses are unchanged.
10. **The skip rule (ADR-241).** A route the probe suite marks COMPLIANT is not edited — not its router function, request model class, use case or test.
11. **Success responses and business outcomes never change.** Every existing success-path test passes unchanged.
12. **Examples are proven (ADR-243).** Every example body added is parsed against its own model by a test.
13. **No request value is ever logged (ADR-239).** Logs carry route template, problem count and problem codes only.
14. **Layering.** `ErrorDetail`, `ProblemCode` and `ApplicationError.details` live in the framework-free shared kernel. Everything that knows Pydantic or FastAPI lives in `platform/api_contract/`. A module's `domain` and `application` never import `platform/api_contract/` (import-linter enforces it); a module's `adapters/api` may.
15. **No database change, no migration.**

### C2. Layout (paths confirmed or adjusted by Chunk 1; behavior fixed here)

```
<shared kernel>/errors.py            additive: ErrorDetail, ProblemCode, ApplicationError.details,
                                     ApplicationError.generic_by_design
platform/api_contract/               NEW (framework-aware; name confirmed in Chunk 1)
├── describer.py                     route → RequestContract (C5)
├── rules.py                         declarative rule helpers (C6)
├── translator.py                    RequestValidationError → list[ErrorDetail] (C4)
├── handler.py                       the one FastAPI exception handler (C3)
├── sensitive.py                     the sensitive-name list (C4)
└── ws.py                            WebSocket frame helper (C12)
scripts/print_request_contracts.py   generated offline reference (Chunk 15)
tests/unit/platform/api_contract/    unit tests for each file above
tests/api/contract/                  probe library, its own tests, the strict suite (C9)
tests/architecture/test_request_contract_guards.py
docs/api_contract/                   README.md, baseline_report.{md,json}, fix_list.md, skip_list.md,
                                     behavior_changes.md, schema_snapshot_before.json,
                                     schema_snapshot_after.json, request_reference.md (generated)
```

### C3. The response

`422` for a request that is malformed. Always the same envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid request. context_type: must be one of: LISTING, BOOKING.",
    "details": [ { …one object per problem… } ],
    "request_contract": { …the full shape of this route's request… }
  }
}
```

**`error.message`** = `"Invalid request. "` + each problem as `"<field>: <sentence>"`, joined by one space; a problem on the whole body has no `<field>:` prefix. The `<sentence>` is the detail's own `message` with its leading "`field` " removed, so the two never disagree. At most 1000 characters; if cut, end with `… and N more problems — see details.` This is deliberately the *whole* story so that anything reading only `message` still learns everything (ADR-234).

**Each `details[]` object** (keys with no value are omitted):

| Key | Meaning |
|---|---|
| `location` | `body`, `query`, `path`, or `frame` (WebSocket) |
| `field` | dotted path, list indexes as `[n]`, e.g. `subject.message_ids[0]`. Empty for a whole-body problem |
| `problem` | one code from C4 |
| `message` | one plain sentence, composed by the translator |
| `expected` | human string: `"one of: LISTING, BOOKING"`, `"a UUID"`, `"an integer between 1 and 100"` |
| `allowed_values` | the full list — **closed sets only**; for `unknown_field`, the accepted field names |
| `limit` | the number that was exceeded or not reached (length, size, count, bound) |
| `received` | what the client sent — **closed-set fields only**, ≤ 64 chars, never a sensitive field (ADR-239) |
| `suggestion` | for `unknown_field`: the closest accepted name when one is close (difflib ratio ≥ 0.6) |
| `applies_when` | `{"field": "context_type", "equals": "LISTING"}` — present when the problem only applies under a condition (a variant of a discriminated union, or a rule) |

**Example 1 — your exact request** (`context_type: "CONVERSATION"`):
```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid request. context_type: must be one of: LISTING, BOOKING.",
    "details": [
      {
        "location": "body", "field": "context_type", "problem": "invalid_value",
        "message": "`context_type` must be one of: LISTING, BOOKING.",
        "expected": "one of: LISTING, BOOKING",
        "allowed_values": ["LISTING", "BOOKING"],
        "received": "CONVERSATION"
      }
    ],
    "request_contract": {
      "method": "POST", "path": "/api/v1/messaging/conversations",
      "body": {
        "content_type": "application/json",
        "discriminator": "context_type",
        "variants": [
          { "when": {"field": "context_type", "equals": "LISTING"},
            "fields": [
              {"name": "context_type", "type": "enum", "required": true, "allowed_values": ["LISTING"]},
              {"name": "listing_id", "type": "uuid", "required": true, "description": "The listing the conversation is about."}
            ],
            "example": {"context_type": "LISTING", "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"} },
          { "when": {"field": "context_type", "equals": "BOOKING"},
            "fields": [
              {"name": "context_type", "type": "enum", "required": true, "allowed_values": ["BOOKING"]},
              {"name": "booking_id", "type": "uuid", "required": true, "description": "The booking the conversation is about."}
            ],
            "example": {"context_type": "BOOKING", "booking_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"} }
        ]
      }
    }
  }
}
```

**Example 2 — several problems at once** (`POST /api/v1/properties`, with `property_type: "VILLA"`, `latitude: "abc"`, no `name`):
```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid request. name: is required. property_type: must be one of …. latitude: must be a number.",
    "details": [
      {"location": "body", "field": "name", "problem": "missing", "message": "`name` is required.", "expected": "a string"},
      {"location": "body", "field": "property_type", "problem": "invalid_value", "message": "…", "allowed_values": ["…the real values…"], "received": "VILLA"},
      {"location": "body", "field": "latitude", "problem": "invalid_type", "message": "`latitude` must be a number.", "expected": "a number"}
    ],
    "request_contract": { "…": "…" }
  }
}
```

**Example 3 — an application error that gained `details`** (R4, C8). Code, status and message are exactly what they are today; only `details` is new:
```json
{
  "error": {
    "code": "invalid_message_content",
    "message": "<the existing message, unchanged>",
    "details": [
      {"location": "body", "field": "content", "problem": "too_long", "message": "`content` must be at most 2000 characters.", "limit": 2000}
    ]
  }
}
```
(The limit is read from `Settings` at raise time — the single source of the limit stays where Module 11 put it.)

**`request_contract`** is present on every `validation_error` unless `api_validation_include_contract` is false or the contract exceeds `api_validation_contract_max_bytes`, in which case it is omitted and `"request_contract_omitted": true` is added next to it. Application errors with `details` do **not** carry `request_contract`.

### C4. Problem codes and the translator

**`ProblemCode` (closed set, in the shared kernel):** `missing`, `invalid_type`, `invalid_value`, `invalid_format`, `too_short`, `too_long`, `too_small`, `too_large`, `too_few_items`, `too_many_items`, `unknown_field`, `conditional_required`, `conflicting_fields`, `invalid_json`, `body_required`, `wrong_content_type`.

**Mapping from the framework's error types** (Chunk 1 records the exact strings observed for the installed Pydantic/FastAPI versions and adjusts this table only if they differ; the **meaning** column is binding):

| Framework error | → `problem` | `message` / extras |
|---|---|---|
| `missing` | `missing` | "`f` is required." + `applies_when` if inside a union variant or a rule |
| `extra_forbidden` | `unknown_field` | "`f` is not accepted here. Accepted fields: …" · `allowed_values` = accepted names (from the schema) · `suggestion` |
| `enum`, `literal_error`, `union_tag_invalid` | `invalid_value` | "`f` must be one of: …" · `allowed_values` from the **schema** (for a discriminated union, the discriminator's mapping keys) · `received` |
| `union_tag_not_found` | `missing` | the discriminator field is required; `allowed_values` = its tags |
| `string_type`, `int_type`, `float_type`, `bool_type`, `list_type`, `dict_type`, `model_type`, `int_parsing`, `float_parsing`, `bool_parsing` | `invalid_type` | "`f` must be a/an {string, integer, number, boolean, list, object}." |
| `uuid_parsing`, `uuid_type`, `datetime_parsing`, `date_parsing`, `string_pattern_mismatch`, `url_parsing`, email/format errors | `invalid_format` | "`f` must be a valid {UUID, date-time, date, email, URL}" or, for a pattern, "match `<pattern>`" · `expected` |
| `string_too_short` / `string_too_long` | `too_short` / `too_long` | `limit` |
| `greater_than(_equal)` / `less_than(_equal)` | `too_small` / `too_large` | `limit`; wording distinguishes "at least" from "more than" |
| list `too_short` / `too_long` | `too_few_items` / `too_many_items` | `limit` |
| `json_invalid` | `invalid_json` | "The request body is not valid JSON." — whole-body problem |
| a body is required but absent | `body_required` | "A JSON request body is required." |
| multipart expected but not sent / file part absent | `wrong_content_type` / `missing` | "Expected multipart/form-data with a file part named `file`." |
| a **declared rule** (C6) fails | `conditional_required` / `conflicting_fields` / `missing` | message generated from the rule; `applies_when` where relevant |
| anything else (a custom validator authored in this repo) | `invalid_value` | message authored in the repo; **a test asserts no input value appears in it** |

**Field paths.** Drop the discriminator-tag segment Pydantic inserts into `loc` for union members; render list indexes as `[n]`. The first `loc` element becomes `location`.

**Order of `details`.** `body`, then `query`, then `path`; within a location, in the order the fields are declared on the model; stable between calls.

**Sensitive names (`sensitive.py`).** A path segment equal to or containing (case-insensitive) any of: `password`, `secret`, `token`, `nonce`, `authorization`, `credential`, `otp`, `content`, `description`, or exactly `code`. `received` is never set for these, and — because `received` is already restricted to closed-set fields — this list is a second lock, not the first.

### C5. The describer and `request_contract`

`describer.py` turns a FastAPI route into a **`RequestContract`** (a plain, JSON-serializable tree) from `route.dependant` and `model_json_schema(mode="validation")`. It resolves `$ref`, nullable `anyOf`, `allOf`, `enum`/`const`, arrays, nested objects and discriminated `oneOf` (using `discriminator.mapping`). It is computed once per route and cached; output order is deterministic.

```
request_contract: { method, path,
  body?:  { content_type, fields[] | (discriminator, variants[]), rules[], example? },
  query?: { fields[] },
  path?:  { fields[] } }
FieldContract: { name, type, required, required_when?, nullable?, allowed_values?, items?,
                 constraints?{min_length,max_length,minimum,maximum,exclusive_*,pattern,min_items,max_items},
                 default?, description?, example?, fields? }
type ∈ { string, integer, number, boolean, uuid, date, datetime, email, url, enum, array, object, file }
```

Rules (`rules[]`) come from the declarations in C6. An `example` is the model's declared example; if the model has none, the describer synthesizes a minimal valid body from the required fields and marks it `"example_is_generated": true`. The describer never reads defaults that look like secrets and never executes request-time code.

### C6. Declared rules (`rules.py`)

A small closed set of rule kinds, each a frozen dataclass; a class decorator **`@contract_rules(*rules)`** both (a) writes them into the model's `json_schema_extra["x-contract-rules"]` so the describer can publish them and (b) installs one `model_validator(mode="after")` that raises a structured error the translator recognizes.

| Rule | Meaning | Problem |
|---|---|---|
| `RequiredWhen(field, equals=("other", value))` | `field` is required when `other == value` | `conditional_required` |
| `RequiredWhen(field, any_present=("a","b"))` | `field` is required when any of `a`, `b` is present | `conditional_required` |
| `ExactlyOneOf(*fields)` | one and only one is present | `missing` (none) / `conflicting_fields` (several) |
| `AtLeastOneOf(*fields)` | one or more present (PATCH bodies that must change something) | `missing` |
| `MutuallyExclusive(*fields)` | not more than one present | `conflicting_fields` |

Wording is **generated from the rule**, never hand-written, so it is uniform ("`billing_period` is required when `min_price_kobo` or `max_price_kobo` is set."). **Which tool for which pattern:** if a field's value decides which *other fields exist* (`context_type`, `subject.type`, `action_type`), use a **discriminated union** (the contract shows each variant). If it only decides whether one field is needed, use `RequiredWhen`. For routes whose query parameters are individual function arguments, Chunk 5 provides a tiny dependency that builds a query model so the same rules apply to `query`.

### C7. The remedy tree, protected errors and exemptions

**Remedy tree** (applied by every module chunk to every route on the Fix List):

| Case | Remedy |
|---|---|
| **R1** — the input is missing, the wrong type or format, out of declared bounds, an unknown field, or **not a member of its own closed set** | Type it at the boundary; the shared handler describes it. Record any changed code/status in the register (ADR-246) |
| **R2** — a co-presence rule among request fields, with **no documented domain code** | Declare it with `@contract_rules` or a discriminated union |
| **R3** — Swagger is bare (no description, no dropdown, no valid example) | Add `description`, enum/`Literal`, and an `examples` entry on the fields/models of the Fix List route |
| **R4** — a **documented domain code** rejects a well-formed value for a policy or settings reason | **Keep** code, status and message; attach `details` (C8) |
| **R5** — the rejection depends on stored data or on who the caller is | Business — **do not touch** |
| **Protected** | **Do not touch** — see below |

**Protected errors (starting list; Chunk 1 maps each to its real class and confirms its byte-identical test exists).** Each is marked `generic_by_design = True` and a guard test (Chunk 15) fails if any ever carries `details`:
`InvalidOrExpiredCode` (`invalid_or_expired_code`) · `InvalidGoogleToken` · the login credential failure · `ConversationNotFound` (`conversation_not_found`) · the saved-listing `listing_not_found` · `InvalidReportSubject` (`invalid_report_subject`) · `NotificationNotFound` · `CaseNotFound` (`case_not_found`) · the media stream's single `403` · the resend-verification `202`. A **pure shape failure on the same route** (a missing `code` field, an unknown report `subject.type`) is **not** protected — it is decided before any lookup and does not reveal what exists.

**Exempt routes (no probe, no change):** `POST /api/v1/payments/webhooks/{provider_name}` (provider-signature-authenticated; must keep acknowledging exactly as today), `GET /api/v1/media/{id}/stream`, the WebSocket handshake before `auth`. Chunk 2 may add to this list **only** with a one-line reason per route; routes with no inputs at all are **N/A**, not exempt.

### C8. `details` on application errors (ADR-240)

Shared kernel, additive:
- `ErrorDetail` — frozen dataclass with the keys of C3 (framework-free).
- `ApplicationError.details: tuple[ErrorDetail, ...] = ()` — existing constructors keep working unchanged.
- `ApplicationError.generic_by_design: ClassVar[bool] = False`.

The platform's existing application-error handler renders `error.details` when `details` is non-empty **and** `generic_by_design` is false; status, `code` and `message` are exactly as before. A use case attaches `details` only for **R4** cases: a settings-driven limit (`limit`), an allowed set the policy narrows (`allowed_values`), an allowed media type list and size ceiling. It never attaches stored data.

### C9. The probe suite, the baseline, the Fix List (ADR-241)

**Location:** `tests/api/contract/`. **Library:** `probe.py` (generates probes from `app.openapi()` and the describer), `closed_sets.py` (the reviewed register of fields that **must** be enums — see P3), `exempt.py`, `report.py`. **App under test:** `app_env="test"` so the conditionally mounted routes (mock controls, dev routes) are included.

**Credentials.** A fixture issues real tokens for a student, a scout, an `OPERATIONS` account, an `ADMIN` account and a dual-role account (reuse the existing API-test fixtures). For each route the harness uses the **lowest-privilege account that gets past any route-level permission dependency**; Chunk 1 records, per route, whether permission is a route dependency (reached before validation) or inside the use case (reached after).

**Probes** (path ids are random UUIDs — validation happens before any lookup, so no data is needed):

| Probe | Request | Pass means |
|---|---|---|
| **P1 missing** | `{}` or no body, for a body with required fields | `422`, and the serialized response **contains every required top-level field name** |
| **P2 unknown field** | a valid body plus `"__not_a_field__": 1` | `422`; response contains `__not_a_field__` **and** the accepted field names |
| **P3 closed set** | for every property that is an enum/`const` in OpenAPI **and** every entry of `closed_sets.py`: an invalid value | the **schema** shows an `enum` for the register entries (a free-text field **fails**); `422` and the response **contains every allowed value** |
| **P4 wrong type** | for every typed property, a value of the wrong JSON type | `422`; response contains the field name **and** a type word (`string`, `integer`, `number`, `boolean`, `list`, `object`, `UUID`, …) |
| **P5 query/path** | invalid enum / out-of-range / non-UUID for each query and path parameter | `422`; response contains the parameter name and the allowed values or the bound |
| **P6 rules** | for each declared rule, a violating request | `422`; response contains the field names in the rule |
| **P7 auth first** | no token plus an invalid body | `401`, and the response contains **no** `details` |
| **P8 documented** | inspect `app.openapi()` | every body property has a `description`; every request model has ≥ 1 example; closed sets render as `enum`; no free-form `additionalProperties: true` body (allow-listed with a reason) |
| **U1 upload, no file** | multipart request with no `file` part | `422`; response contains `file` |
| **U2 upload, wrong type** | handled in the module chunk's own test (it needs a real owner/listing) | — |

"Contains" means the string appears in the JSON-serialized response body, case-sensitive. The probes are **semantic on purpose** (ADR-241): a route with its own bespoke wording passes if the information is in the response.

**Verdicts per route:** **COMPLIANT** (every applicable probe passes) · **PARTIAL** · **NON-COMPLIANT** · **N/A** (no inputs) · **EXEMPT** (with its reason).

**Modes.** `REPORT` (default; never fails; writes `baseline_report.md`/`.json` — a route × probe matrix with PASS/FAIL/NA). `STRICT` (CI; fails on any FAIL for a non-exempt route). The harness is itself tested **both ways** (Chunk 2): a tiny FastAPI app with one compliant route and several deliberately bad ones must produce exactly the expected PASS and FAIL cells.

**The Fix List and Skip List.** After the shared mechanism exists (Chunk 7) the suite is run again in REPORT mode. Output: `docs/api_contract/fix_list.md` — one row per route with ≥ 1 FAIL: module · method + path · failing probes · remedy letters (R1–R4) · the registered behavior change, if any — and `skip_list.md` — every COMPLIANT route. **The Fix List is the work order for Chunks 8–13.** A module chunk edits only the routes on it.

**Schema snapshots (the proof of "skipped").** Chunk 2 writes `schema_snapshot_before.json` (the `model_json_schema` of **every** request model, keyed by route). Chunk 17 writes `schema_snapshot_after.json` and diffs the two: every model that changed must belong to a Fix List route; every Skip List route's models must be **identical**.

### C10. Settings (`config/settings.py`, `.env.example`; invalid values fail startup)

| Setting | Default | Rule |
|---|---|---|
| `api_validation_include_contract` | `true` | bool |
| `api_validation_max_details` | `20` | integer ≥ 1 |
| `api_validation_contract_max_bytes` | `16384` | integer ≥ 1024 |
| `api_validation_echo_received` | `true` | bool; `false` suppresses `received` everywhere |

### C11. Touch map

**Allowed to change:** the shared kernel's error module (additive only); `platform/api_contract/` (new); `app.py` (register the one handler, replacing the existing request-validation handler — its location from Chunk 1); `config/settings.py`; `.env.example`; each module's `adapters/api/schemas.py`, `router.py`, `dependencies.py` **for Fix List routes only**; each module's `application/errors.py` and the use cases that raise R4 errors (to attach `details`); Messaging's WebSocket protocol file (Chunk 14); the import-linter configuration; tests; `scripts/`; `docs/`; the frontend and manual-testing documents; AI-state files.
**Must not change:** any `domain/` entity or repository; any migration (there are none); Security's policy or permission tables; any response schema other than the validation-error envelope and R4 `details`; any protected error; any Skip List route's code or tests; any success-path behavior.

### C12. WebSocket (ADR-244)

After a successful `auth`, error frames for bad frames carry `details` using the same translator over the frame's Pydantic model, with `location: "frame"`:
```json
{"type": "error", "request_id": "r1", "code": "invalid_command",
 "message": "Invalid request. conversation_id: is required.",
 "details": [{"location": "frame", "field": "conversation_id", "problem": "missing", "message": "`conversation_id` is required.", "expected": "a UUID"}]}
```
`unknown_command` and `invalid_command` additionally carry `allowed_values` (every accepted client command `type`) and, for `invalid_command`, the required fields of that command. **Before `auth` completes nothing changes** (`auth_required` stays exactly as it is). Frontends that ignore unknown keys are unaffected.

---

## PART D — CHUNK INSTRUCTIONS [FOR YOU — GEMINI CLI]

**Every chunk ends the same way:** run the linter, the type checker, `poetry run lint-imports`, and the **full test suite of every module the chunk touched** (Chunks 1, 2 and 7 run the entire suite). Report the real output.

---

### CHUNK 1 — INSPECTION & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** learn what is really in the repository, measure what today's errors actually look like, and lay empty scaffolding. **No behavior change.** Nothing in this chunk may alter a response.

**Part one — inspect and report** (a written report, with real command output, before any file is created):

1. **Prerequisites.** Confirm Modules 15, 16 and 17 are in place: the Module 15 request-model guard test exists and passes; Module 17's routes are mounted. **If either is missing, stop and report.**
2. **Error machinery.** Locate the shared-kernel `ApplicationError` and its categories; where `code` and `message` are defined; the platform file that registers exception handlers; how `RequestValidationError`, `HTTPException`, application errors and unexpected exceptions are each converted today.
3. **Measure today's validation responses.** Start the app and send, to one representative route that has a body, a query and a path parameter: a missing required field · a wrong type · a value outside a closed set · an unknown field · invalid JSON · a non-UUID path id · an out-of-range `page_size`. **Paste the real response body for each.** State whether today's handler reports **all** problems or only the first, whether it names the field, whether it lists allowed values, and whether `details` exists anywhere today.
4. **Versions.** FastAPI, Pydantic (confirm v2) and Starlette versions; the exact framework `type` strings observed in step 3 (to confirm or adjust C4's table).
5. **Route inventory, generated from the running app** (`app.openapi()` plus the router modules), one row per route: module · method · path · request body model(s) · query and path parameters with types · for **every** field that looks like a closed set, whether it is an enum/`Literal`/discriminated union or plain `str` · whether the model has `extra="forbid"`, descriptions, examples · the auth dependency · **whether permission is enforced by a route dependency (before validation) or inside the use case (after)** — prove this by experiment on at least three routes (one student-only, one staff-only, one ownership-scoped).
6. **Shape errors raised after the boundary.** Every application `ValidationError` subclass and every error whose message reads like "unknown/invalid <option>". Classify each as a shape problem (C1.1) or business. **List every one raised for a closed-set input — your user's `conversation_context_not_found` for an unknown `context_type` is the first.** Also list every use case that **normalizes** a closed-set input (upper-case, trim) before checking it (C1.6).
7. **Protected errors.** Map each C7 candidate to its real class and code, and the existing test that proves its body is byte-identical.
8. **WebSocket.** Messaging's `ws_protocol.py`: every place an `invalid_json`, `invalid_command`, `unknown_command` or `auth_required` frame is built.
9. **Uploads.** The avatar, listing-media and verification-evidence upload routes; where `UnsupportedMediaType` and `MediaTooLarge` are raised and with what message.
10. **Conventions.** How request models are declared; the base class if any; where API tests get tokens for each role; the import-linter configuration; the frontend-documentation file; the AI-state files; **whether the OpenAPI document and Swagger are exposed outside `local`/`test`** (state the exact setting).
11. **Where each C2 path lands** in this repository. Report any difference between this file and what you found; do not "fix" the file.

**Part two — scaffolding.** Create the empty packages and folders in C2 (with `__init__.py` and a docstring each), `docs/api_contract/README.md` (two lines saying what the folder is for), and add the import-linter contracts of C1.14 (shared kernel free of FastAPI/Pydantic; `platform/api_contract` imports only the shared kernel, FastAPI and Pydantic; no module's `domain`/`application` imports it). They must pass on the empty packages.

**Prohibition:** no handler, settings, model or route changes.

**Tests you must write:** none beyond the import-linter contracts passing.

**Acceptance criteria:** the full existing suite passes unchanged; `lint-imports` passes with the new contracts; the report answers all eleven items with real output.

---

### CHUNK 2 — THE PROBE SUITE (REPORT MODE) AND THE BASELINE
**[FOR YOU — GEMINI CLI]**

**Objective:** build the objective arbiter of "already supports it" **before changing any behavior**, and record the true starting point. Read **C9**.

**Build** `tests/api/contract/`: `probe.py`, `closed_sets.py`, `exempt.py`, `report.py` and the credentials fixture, exactly per C9 — probes P1–P8 and U1, REPORT and STRICT modes, verdicts, the route × probe matrix.
- `closed_sets.py` is the **reviewed register** of fields that must be enums. Seed it from Chunk 1 step 5 (every closed-set field that is plain `str`) and from Part A's table; **every entry carries a comment naming its source**.
- `exempt.py` contains the three C7 exemptions, each with its reason.
- Write `docs/api_contract/schema_snapshot_before.json` (C9).
- Run the suite in **REPORT mode against the untouched app** and commit `baseline_report.md` and `.json`. In the Completion Report, include the summary counts (COMPLIANT / PARTIAL / NON-COMPLIANT / N/A / EXEMPT) and the list of COMPLIANT routes.

**Prohibition:** no application code changes. Only tests, docs and the snapshot.

**Tests you must write (the harness is itself tested, both ways):** a tiny throwaway FastAPI app inside the test with (a) a fully compliant route, (b) a route whose closed set is plain `str`, (c) a route that returns only the first problem, (d) a route with a bare model (no descriptions/examples), (e) a route that echoes nothing useful for an unknown field. Assert the report marks exactly the right probe cells PASS and FAIL for each, that `STRICT` mode fails on (b)–(e) and passes on (a), and that an exempt route is reported EXEMPT, not skipped silently.

**Acceptance criteria:** the harness tests pass; the baseline report exists and covers **every** route in the inventory (a count assertion: report rows == non-exempt routes in the OpenAPI document); the existing suite is unaffected.

---

### CHUNK 3 — SETTINGS, SHARED TYPES AND `details` ON APPLICATION ERRORS
**[FOR YOU — GEMINI CLI]**

**Objective:** the framework-free foundations. Read **C8, C10**, ADR-240.

**Build:**
1. The four settings of **C10** in `config/settings.py` and `.env.example`; invalid values fail startup.
2. In the shared kernel: `ProblemCode` (closed set, **C4**), the frozen `ErrorDetail` dataclass (the keys of C3), `ApplicationError.details` (default empty tuple; every existing construction unchanged) and `ApplicationError.generic_by_design` (default `False`).
3. Extend the platform's **existing** application-error handler so it renders `error.details` when non-empty and `generic_by_design` is false; status, `code` and `message` untouched. Keys with no value are omitted.
4. Mark the protected error classes `generic_by_design = True` (the classes confirmed in Chunk 1 step 7) — a one-line change each, nothing else in those classes.

**Prohibition:** do not attach `details` to any real error yet; do not touch the validation handler yet.

**Tests you must write (`tests/unit/`):** settings defaults and invalid values (`api_validation_max_details = 0`, `api_validation_contract_max_bytes = 100`) fail startup; an `ApplicationError` with no `details` serializes **byte-identically to before** (compare against a fixture captured from the old handler); with `details`, `details` is rendered and the other three keys are unchanged; a `generic_by_design` error with `details` renders **no** `details`; every `ProblemCode` round-trips to its string; `ErrorDetail` omits empty keys.

**Acceptance criteria:** tests pass; the full suite passes unchanged; import-linter clean (the shared kernel imports no FastAPI/Pydantic).

---

### CHUNK 4 — THE REQUEST-CONTRACT DESCRIBER
**[FOR YOU — GEMINI CLI]**

**Objective:** a route in, a complete `RequestContract` out. Read **C5**.

**Build** `platform/api_contract/describer.py` exactly per C5: body fields, discriminated-union variants, nested objects, arrays, nullable fields, `enum`/`const`, `format` → `type`, constraints, descriptions, declared examples (else a generated one marked `example_is_generated`), query and path parameters, the multipart `file` part. Cached per route; deterministic order. A JSON serializer that **omits empty keys**.

**Prohibition:** the describer never imports `app.py`, never executes a request, and never reads settings other than to be told about them by the caller.

**Tests you must write (`tests/unit/platform/api_contract/test_describer.py`, using small throwaway models and a throwaway FastAPI app):** one test per feature in the build list; a discriminated union (`LISTING`/`BOOKING`) yields two variants with the right required fields and `when`; an enum yields `allowed_values` equal to the enum members **in declaration order**; constraints (`min_length`, `max_length`, `ge`, `le`, pattern, `min_length` on a list) map to the right keys; a model with no declared example gets a generated one that **validates against the model**; output is identical across two calls and across process restarts (determinism); a route with no body and no parameters yields an empty contract; a multipart route shows a `file` field of type `file`.

**Acceptance criteria:** tests pass; the full suite passes unchanged.

---

### CHUNK 5 — DECLARED RULES AND THE QUERY-MODEL DEPENDENCY
**[FOR YOU — GEMINI CLI]**

**Objective:** conditional requirements that enforce **and** describe. Read **C6**, ADR-237.

**Build** `platform/api_contract/rules.py`: `RequiredWhen` (both forms), `ExactlyOneOf`, `AtLeastOneOf`, `MutuallyExclusive`, and the `@contract_rules(*rules)` decorator that writes `x-contract-rules` into `json_schema_extra` and installs the single after-validator raising a structured error the translator recognizes. Rule wording is generated from the rule. Teach the **describer** (Chunk 4) to publish `rules[]` and `required_when` from `x-contract-rules`. Add the small **query-model dependency** that lets a route whose query parameters are separate arguments validate them through one model so rules apply to `query` (use the framework's own query-parameter-model support if the installed FastAPI version has it; otherwise a dependency that builds the model and converts its error into the same error shape).

**Prohibition:** apply the decorator to **no** real route yet.

**Tests you must write:** each rule kind passes when satisfied and fails when violated, for each violated shape (none present, several present); a decorated model's schema contains `x-contract-rules`; the describer publishes it; generated wording matches the C6 example exactly; a rule referencing a field the model does not have fails at **import time**, not at request time; the query-model dependency applies a rule to query parameters.

**Acceptance criteria:** tests pass; the full suite passes unchanged.

---

### CHUNK 6 — THE TRANSLATOR AND THE ONE HANDLER
**[FOR YOU — GEMINI CLI]**

**Objective:** the visible change. Read **C3, C4**, ADR-234, 238, 239, 242.

**Build:**
1. `translator.py`: framework errors → `list[ErrorDetail]` per the C4 table. Allowed values, accepted field names and constraints come **from the describer/schema**, never from the framework's message text (ADR-238). The translator **never reads `msg` or `input`** except to classify; custom-validator messages are the only authored text it passes through.
2. `sensitive.py` and the `received` rule: set only for closed-set fields, ≤ 64 characters, never for a sensitive name, and not at all when `api_validation_echo_received` is false.
3. `handler.py`: the single handler for the framework's request-validation error. It builds `code: "validation_error"`, the composed `message` (C3), `details` (capped by `api_validation_max_details`), and `request_contract` (C3 rules and the size cap). Invalid JSON and an absent required body become `invalid_json` / `body_required`.
4. In `app.py`, register it **in place of** the existing request-validation handler (location from Chunk 1). The old handler's `code` is kept exactly (`validation_error` per Module 17's usage); confirm in your report what it was.
5. Logging: one structured line per failure — method, route template, problem count, problem codes. **No field values, no `received`, no body.**

**Prohibition:** no route, model or use-case changes. No `401`/`403`/`404` behavior change.

**Tests you must write (`tests/unit/` and `tests/api/contract/test_handler.py`, against a throwaway app plus two real routes):** each C4 row produces the right `problem`, message sentence and extras; **all** problems are reported together; the cap truncates and the message ends with "and N more problems"; `request_contract` is present, omitted when the setting is off, omitted with `request_contract_omitted: true` when over the byte cap; your exact Part-C Example 1 request body, sent to a throwaway discriminated-union route, returns the Example 1 response **verbatim** (modulo the route's own path); `received` is never present for a field named `password`/`token`/`content`/`code`; **a request whose body contains a secret in the wrong field never appears in the response, the logs, or the contract** (assert on the captured log output); invalid JSON, a missing body, a non-UUID path id, an out-of-range `page_size` and a bad enum in the query each produce the right detail; **no input value appears in any custom-rule message**; an unauthenticated request with an invalid body → `401` with no `details`; a `404`, a `403` and a protected error are byte-identical to before; a real existing route's old assertion on `error.code == "validation_error"` still passes.

**Acceptance criteria:** the new tests pass; the **full existing suite** passes — and if any existing test fails **only because it pinned the old exact validation message text**, list each, update only that assertion line (ADR-246), and report it; any other failure → stop and report.

---

### CHUNK 7 — THE CENTRAL RESULT AND THE FIX LIST
**[FOR YOU — GEMINI CLI]**

**Objective:** measure what the shared handler alone achieved, and produce the work order. Read **C9**.

1. Run the probe suite in **REPORT mode** against the app now carrying the shared handler.
2. Write `docs/api_contract/fix_list.md` and `docs/api_contract/skip_list.md` in the C9 format: **one row per route** with ≥ 1 FAIL (module, method + path, failing probes, remedy letters R1–R4 per the C7 tree, and the register entry if the fix will change a documented code/status), and every COMPLIANT route in the skip list.
3. Write `docs/api_contract/behavior_changes.md` with the entries **known so far** (at minimum the Messaging `context_type` case) — the register is completed by the module chunks.
4. In the Completion Report: the before/after counts against the baseline; the routes the shared handler alone moved from FAIL to PASS; the Fix List grouped by module so Nsisong can see what Chunks 8–13 will touch; and the Skip List with, for each route, which probes it passes and why that counts as "already supports it".

**Prohibition:** no module is edited in this chunk.

**Tests you must write:** none new; the report files are the artifact. Re-run the full suite.

**Acceptance criteria:** the full suite passes; both lists cover every non-exempt route exactly once (count assertion); **stop and wait — Nsisong reviews the Fix List before Chunk 8.**

---

### THE MODULE-CHUNK PROCEDURE (applies to Chunks 8 through 13)
**[FOR YOU — GEMINI CLI]**

Each of Chunks 8–13 repeats this procedure for its modules. The chunk text below names the routes and the **hypotheses** from Part A; **the Fix List decides, not the hypotheses.**

1. **Open `docs/api_contract/fix_list.md` and `skip_list.md`.** Start your report with two tables for this chunk's modules: the routes you **will edit** (with their failing probes and remedy letters) and the routes you **will skip** (COMPLIANT, EXEMPT or N/A, with the reason). **If no route in scope is on the Fix List, say so, change nothing, run the module's suite, and stop.**
2. **Apply the remedy tree (C7) to each Fix List route — exactly the letters the Fix List gives, nothing more.** R1: type the closed set at the boundary, with the C1.6 compatibility rule. R2: `@contract_rules` or a discriminated union. R3: descriptions, enum/`Literal`, and an `examples` entry on that route's models and parameters. R4: attach `details` to the existing application error, keeping its code, status and message. **Never** touch an R5 case or a protected error.
3. **The router passes the use case exactly what it accepted before** (the enum's `.value` or the domain enum the use case already took). **No use-case signature changes** other than raising an R4 error with `details`.
4. **The register (ADR-246).** For every route where a documented code/status for a pure shape failure changes, add an entry to `docs/api_contract/behavior_changes.md` (route · input · old status/code/message · new). Edit an existing test **only** on the assertion lines for that exact response and list each edit in your report.
5. **Tests (`tests/api/<module>/test_request_feedback.py`, real HTTP):** for every edited route, assert the **exact** detail(s) returned — the missing field names, the **exact** allowed-value list, the rule's fields, the limit — for at least: one missing field, one wrong type, one out-of-set value (where the route has a closed set), one unknown field, and every declared rule violated. Add a test that **every declared example parses against its own model** (ADR-243). Add one byte-identical assertion for each protected error in the module that did not already have one. Existing success-path tests are untouched and pass.
6. **Module-scoped STRICT run:** run the probe suite in STRICT mode restricted to this chunk's routes; every non-exempt route passes.
7. **Docs:** add a short "Request feedback" section to each amended module's documentation: routes changed, routes skipped, register entries.
8. **Acceptance criteria (every module chunk):** the module's full suite passes; the STRICT run for its routes passes; **a diff of the routers, request models, use cases and tests of the skipped routes shows no change**; no migration exists; `lint-imports` clean.

---

### CHUNK 8 — MESSAGING (REST)
**[FOR YOU — GEMINI CLI]**

Follow the **module-chunk procedure**. Hypotheses (Part A; the Fix List decides):

- **`POST /api/v1/messaging/conversations`** — **the route that started this module.** `context_type` becomes a **discriminated union**: `LISTING` requires `listing_id` and forbids `booking_id`; `BOOKING` requires `booking_id` and forbids `listing_id`. An unknown `context_type` is now `422 validation_error` listing `LISTING, BOOKING` (R1), **replacing `404 conversation_context_not_found` for that case only** — register entry. `404 conversation_context_not_found` still means "that listing/booking does not exist", and `422 conversation_context_unavailable` is unchanged. Honor C1.6: if the use case normalized case, `"listing"` must still work.
  **The two acceptance tests are your user's:** (1) the exact body `{"context_type": "CONVERSATION", "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}` returns `422` whose `details` has one `invalid_value` for `context_type` with `allowed_values == ["LISTING", "BOOKING"]` and `received == "CONVERSATION"`, and whose `request_contract` shows both variants; (2) `{"context_type": "LISTING"}` returns `422` with `listing_id` `missing` and `applies_when` `{"field": "context_type", "equals": "LISTING"}`. Also: `{"context_type": "LISTING", "booking_id": "…"}` → `booking_id` `unknown_field` and `listing_id` `missing`.
- **`POST …/messages`** — `client_message_id` format (currently an `InvalidClientMessageId` use-case error): if the rule is decidable from the value alone, move it to the schema (R1) and register it; otherwise R4. The **settings-driven content limit stays in the use case** (Module 11's single-source rule): `InvalidMessageContent` gains `details` with `limit` read from `Settings` (R4) — **no `max_length` in the schema**, **message text unchanged**. `media_ids` and other extras: `unknown_field` with the accepted fields.
- **`GET …/messages`** — `limit` bounds; `before` and `after` together become a declared `MutuallyExclusive` rule at `query` (R2). A cursor that cannot be decoded **stays** `422 invalid_history_cursor` — its response gains `expected: "an opaque cursor copied from older_cursor, newer_cursor or an item's cursor"` via R4.
- **`POST …/read`**, **`GET /conversations`**, path UUIDs — descriptions and examples (R3) where flagged.
- **Protected, untouched:** `conversation_not_found` (byte-identical for non-participants and unknown ids), `communication_restricted`, `self_conversation_not_allowed`.

**Additional acceptance criteria:** the full Messaging suite passes unchanged apart from the register entries; the rate-limit and byte-identical `404` tests still pass.

---

### CHUNK 9 — HOUSING, SEARCH AND SAVED LISTINGS
**[FOR YOU — GEMINI CLI]**

Follow the **module-chunk procedure.** Hypotheses:

- **Housing:** property `property_type`; unit `total_capacity` bounds; listing `price_currency`, `price_period`, `price_amount_kobo` (the description must say **"in kobo, not naira"**); `PATCH` bodies (an `AtLeastOneOf` rule if an empty `PATCH` is currently refused downstream with no explanation); list filters (`campus_id`, `property_type`); state-transition routes carry no body and are N/A.
- **Search:** `billing_period` (`YEAR`/`SEMESTER`/`MONTH`), `accommodation_type`, `amenities` (repeatable — if the amenity names are a code-defined set, type them; if they are open text, say so in the description), `sort_by` (`RELEVANCE`, `PRICE_ASC`, `PRICE_DESC`, `DISTANCE`, `NEWEST`), `strategy` (`RECOMMENDED_FOR_YOU`, `RECENTLY_ADDED`), paging. **The price/period pairing rule (ADR-066) becomes a declared `RequiredWhen("billing_period", any_present=("min_price_kobo","max_price_kobo"))`** so the contract states it; the existing `invalid_search_criteria` code is a **documented domain code** — if the probe finds its message already names `billing_period`, this part is COMPLIANT and is skipped. `max_distance_km` "only meaningful with `campus_id`" is a description, not a rule.
- **Saved Listings (new in Module 16):** path ids, `page`, `page_size` — expected to be largely compliant; skip what passes.
- **Protected, untouched:** the saved-listing `listing_not_found` (hidden looks like missing).

---

### CHUNK 10 — BOOKING, PAYMENT AND VERIFICATION
**[FOR YOU — GEMINI CLI]**

Follow the **module-chunk procedure.** Hypotheses:

- **Booking:** `POST /bookings` (`listing_id`, `idempotency_key` — state the bounds); `…/cancel` (`cancellation_reason` required — state its bounds); the two handover routes.
- **Payment:** `POST /payments` (`booking_id`, `idempotency_key`); `…/disputes` (`reason`); `…/disputes/{id}/resolve` (a closed-set resolution — type it); release and refund bodies.
  **Payment mock controls: expected on the Skip List (Module 15, ADR-198) — verify with the probe, do not edit them.** **The webhook route is exempt** (C7).
- **Verification:** `target_type` (`PROVIDER`/`PROPERTY`) in the body of `POST /cases` **and in the path of `GET /verification-status/{target_type}/{target_id}`** (a typed path enum, so an invalid value names the allowed ones); `evidence_type`; observation `item`, `passed`, `notes`; `reason` (non-empty) on approve/reject/revoke; `inspector_id`. Evidence upload is covered by Chunk 13.
- **Protected, untouched:** verification-owner `404`s and everything in Payment/Booking that depends on stored state (`booking_not_eligible_for_payment`, `409`s).

---

### CHUNK 11 — NOTIFICATION AND TRUST & SAFETY
**[FOR YOU — GEMINI CLI]**

Follow the **module-chunk procedure.** Hypotheses:

- **Notification:** `category` as a typed enum in the query of `GET /notifications` and in the optional `read-all` body; `unread_only`; paging; path UUID.
- **Trust & Safety — user routes:** report `category` (`SCAM_OR_FRAUD`, `MISLEADING_LISTING`, `HARASSMENT`, `IMPERSONATION`, `PAYMENT_CONCERN`, `THREAT_OR_DANGER`, `OTHER`); `idempotency_key`; `description` (10–2000); **`subject` as a discriminated union on `type`**: `LISTING {id}`, `BOOKING {id}`, `CONVERSATION {id, message_ids}` with **1 to 5** `message_ids` (a count bound — shape). A subject whose `type` is not one of the three, or a `CONVERSATION` with no `message_ids`, becomes a `validation_error` (R1) — **register entries.** The semantic failures (not yours, not visible, not found) **remain the single generic `invalid_report_subject`** (protected). `invalid_report_description` stays (documented code) and gains `details` with the 10–2000 `limit` if its message does not already state it (R4).
- **Trust & Safety — staff routes:** `priority`, `to_status` (the seven case statuses), note `kind`, `decision_type` (the five), enforcement `action_type` with its per-type fields as a discriminated union, review-list filters (`status`, `priority`, `assigned_to`, `category`); "`reason` required for `HIGH`/`URGENT`" as a `RequiredWhen` **only if** no documented domain code covers it — otherwise R4 on the existing error.
- **Protected, untouched:** `notification_not_found`, `case_not_found`, `invalid_report_subject` (semantic), `409 duplicate_open_report`, `403 separation_of_duties_violation`.

---

### CHUNK 12 — ADMIN & OPERATIONS (INCLUDING MODULE 15's ADDITIONS)
**[FOR YOU — GEMINI CLI]**

Follow the **module-chunk procedure.** Hypotheses:

- **Issues:** create (`category`, `priority`, `idempotency_key`, `title`, any related-resource pointer typed with its closed set); `assign {assignee_id}`; `resolve {resolution_summary}` (required — state the bound); `status {to_status, reason?}` (typed enum); list filters.
- **Accounts:** `disable`/`reactivate {reason}` — the "missing/short reason → 422" bound becomes a schema constraint (R1) **only if** it currently surfaces as a generic validation failure; if a documented code carries it, R4.
- **Staff:** grant `{role, reason}`. **`role` is typed as the full role enum at the boundary** (R1); granting a **valid but non-manageable** role (`ADMIN`) **keeps `422 role_not_manageable`** and gains `details` with `allowed_values: ["OPERATIONS"]` (R4) — Finding 4, case 2. `…/roles/{role}/revoke`: `{role}` typed in the path.
- **Recovery** (`{reason}`), **audit-events** filters, **Module 15's** `GET /admin/jobs`, role-request list / approve / reject, and `POST /admin/recovery/platform-events/requeue-dead` — whatever the Fix List flags.
- **Protected, untouched:** `403 self_action_not_allowed`, `403 admin_account_protected`, and every permission outcome.

---

### CHUNK 13 — IDENTITY, PROFILE, UNIVERSITY & LOCATION, SECURITY AND MEDIA
**[FOR YOU — GEMINI CLI]**

Follow the **module-chunk procedure.** I did not have the specifications of Modules 01–04, so **this chunk is driven entirely by the Fix List and Chunk 1's inventory.** Hypotheses where the later specs gave hints:

- **Identity (and Module 17's routes):** register, login, refresh, logout, `verify-email {email, code}` (`code` is `^\d{6}$` — Module 17 already returns `422 validation_error` for it; the probe will say whether the rest is compliant), `resend-verification`, `google`, `google/link`, `DELETE google`, `password {new_password}` (8–128), `google/config`, and the `local`/`test` dev routes (`google-mock/token`, `mailbox`). **Protected, untouched:** the login credential failure, `invalid_or_expired_code`, `invalid_google_token`, the `202` resend body. Shape-only feedback on these routes (a missing or malformed field) is allowed and is not a leak.
- **Profile:** student/scout create and update, with their closed sets (profile type, accommodation preference, and any others Chunk 1 finds); after the University migration `university_name` is **no longer accepted** — a client still sending it should get `unknown_field` plus the accepted fields (and a `suggestion` only if the names are close; do not invent a mapping).
- **University & Location:** the directory and admin routes the Fix List flags.
- **Security:** any HTTP routes it owns — probably none; say so.
- **Media and uploads** (`POST /profiles/me/avatar`, `POST /listings/{id}/media`, `POST /verification/cases/{id}/evidence`, `GET /media/{id}`): the probe's **U1** (no file part → `422` naming `file`) for each upload route; and, for **R4**, `UnsupportedMediaType` and `MediaTooLarge` gain `details` — `allowed_values` = the accepted content types for that purpose (`image/jpeg`, `image/png`, `image/webp` for avatar and listing photos; whatever evidence accepts), `limit` = the maximum size in bytes — **codes, statuses and messages unchanged.** Write the **U2** test per upload route here, with a real owner and a real listing/case, uploading a `.txt` file and an oversize file. **`GET /media/{id}/stream` is exempt** and its single `403` is protected.

---

### CHUNK 14 — WEBSOCKET FRAME FEEDBACK
**[FOR YOU — GEMINI CLI]**

**Objective:** Messaging's socket is an API surface; give its bad-frame errors the same help. Read **C12**, ADR-244.

**Build** `platform/api_contract/ws.py` (a helper that turns a Pydantic error from a frame model into `ErrorDetail`s with `location: "frame"`, reusing the translator) and use it in Messaging's `ws_protocol.py` at the sites Chunk 1 step 8 listed: after `auth`, `invalid_command` carries `details` and the **required fields of that command**; `unknown_command` carries `allowed_values` = every accepted client command `type`; `invalid_json` is unchanged in code and gains `message` text naming the expected shape. **Before `auth` completes, behavior is unchanged** (`auth_required` exactly as today). The error frame keeps `type`, `request_id`, `code`, `message`; `details` is additive.

**Prohibition:** no change to any success frame, the auth flow, limits, close codes, or the REST routes.

**Tests you must write (real WebSocket against the app):** after `auth`, `{"type": "conversation.subscribe"}` → an `invalid_command` frame whose `details` names `conversation_id` as `missing`; `{"type": "nope"}` → `unknown_command` with `allowed_values` containing **every** command in `ws_protocol.py` (assert against the module's own list so it cannot drift); before `auth`, a non-`auth` frame still yields exactly the old `auth_required` frame (byte-compare against a captured fixture); all of Module 11's WebSocket tests unchanged and passing.

**Acceptance criteria:** tests pass; the full Messaging suite passes.

---

### CHUNK 15 — THE STRICT SUITE, THE GUARDS AND THE GENERATED REFERENCE
**[FOR YOU — GEMINI CLI]**

**Objective:** make the guarantee permanent and give Nsisong the offline reference. Read **C9**, ADR-243, 245.

1. **STRICT mode in the normal test run:** a test that runs the whole probe suite in STRICT mode over every non-exempt route. It **must pass** — if a route still fails, do not weaken the probe; stop and report (it means a chunk missed a route).
2. **`tests/architecture/test_request_contract_guards.py`:**
   - every request model's declared `examples` parse against that model (ADR-243), project-wide;
   - every error class marked `generic_by_design` never renders `details` (instantiate each with a `details` tuple and assert the rendered body has none), and the marked set equals the C7 list plus whatever Chunk 1 added — a new protected error must be added deliberately;
   - **no code outside `platform/api_contract/` builds a `validation_error` response** (a source scan);
   - the exempt list contains only the three C7 routes plus entries each carrying a reason.
3. **`scripts/print_request_contracts.py`** — `python scripts/print_request_contracts.py [--route "POST /api/v1/messaging/conversations"] [--module messaging] [--format md|json]` — prints every route's contract from the **same describer** (fields, types, required, allowed values, constraints, rules, example). With no arguments it writes `docs/api_contract/request_reference.md`. It must work on Termux (no extra system packages).
4. A **drift test**: the committed `request_reference.md` equals what the script regenerates; the script builds a contract for **every** non-exempt route without error.

**Prohibition:** no new HTTP route; the script is the only "explorer" (ADR-245).

**Acceptance criteria:** all of the above pass; the guard fails when a deliberately violating fixture is introduced (prove it works, like Module 15's Chunk 17).

---

### CHUNK 16 — DOCUMENTATION AND AI STATE
**[FOR YOU — GEMINI CLI]**

**Write:**
1. **`docs/modules/api_contract.md`** — what the module is; the C3 envelope; the problem-code table (C4); and **"How to add a new endpoint so it is self-describing"** — a five-step recipe: (1) type every closed set as an enum/`Literal`/discriminated union; (2) a `description` and an `examples` entry on every field/model; (3) declare conditional requirements with `@contract_rules`; (4) for a policy rejection with a documented code, attach `details`; (5) run the STRICT suite. Include the remedy tree (C7), the protected-error rule, and the skip rule.
2. **The frontend documentation:** add **Part F** of this file to the frontend document, completing the **breaking-changes table** from `behavior_changes.md` with the real entries.
3. **The manual-testing guide** from **Part G**, **running every scenario yourself** and replacing each expected output with the real response; if a scenario cannot be run, mark it **not verified** — never invent an output. Plain-language rules apply: Swagger steps first, no jargon.
4. Add the ADR rows **233–246** to the project's decision log.
5. **AI state:** update the current-state files — module complete, route counts by verdict, the Fix List size at the start and zero at the end, the register, the ADR range, and the Known Limitations list (Part F).

**Acceptance criteria:** every document exists; the manual guide shows only real outputs or an explicit "not verified"; the full suite passes.

---

### CHUNK 17 — FINAL AUDIT
**[FOR YOU — GEMINI CLI]**

1. Run the **entire** test suite, the linters, the type checker and `lint-imports`.
2. Run the probe suite in **STRICT** mode over all routes and paste the summary.
3. Write `docs/api_contract/schema_snapshot_after.json` and **diff it against `schema_snapshot_before.json`** (C9). Report: every changed request model and the Fix List row that justifies it; and, for **every Skip List route, that its request models are identical**. A changed model that is on no Fix List row, or a changed Skip List route, is a **failure — stop and report.**
4. Run `git diff --stat` between the commit before Chunk 8 and now, restricted to the routers, request models, use cases and tests of the Skip List routes: it must be empty.
5. Re-run Module 15's request-model guard and the Module 11 byte-identical-`404` test.
6. Confirm: no migration was added; no response other than `validation_error` and R4 `details` changed; every register entry is in Part F.
7. Produce the **route table**: every route · module · final verdict · whether it was edited or skipped.

**Completion Report — three lists:** (a) **Verified** (with the command and its output); (b) **Implemented but not verifiable in this environment** (and why); (c) **Not done** (and why). Do not blur them.

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

| What you asked for | Where it is built |
|---|---|
| A wrong request lists **what is required, the types, and the allowed values** | C3, C4 · Chunks 3–6 (shared mechanism) |
| **Every endpoint** gets it | One shared handler (Chunk 6) covers every route's types, required fields, unknown fields, bounds and bad ids; Chunks 8–13 add closed-set typing, rules, examples and `details` where the probes say it is still missing |
| Endpoints that **already do it are skipped** | ADR-241 · Chunk 2 (the probe suite decides) · Chunk 7 (Skip List) · Chunks 8–13 (skip rule) · Chunk 17 (schema-snapshot proof) |
| **Chunks, like before** | Part D, 17 chunks, one at a time, each with tests and acceptance criteria |
| **No poking into specification files** | `request_contract` on every `422`; fixed Swagger (dropdowns, descriptions, proven examples); `scripts/print_request_contracts.py` offline reference (Chunk 15) |
| Your **exact failing request** | Part A · Chunk 8 (its two acceptance tests are your request body) · Part G, G1 |
| Don't weaken what is **deliberately generic** | Finding 3 · C7 protected list · Chunk 3 (`generic_by_design`) · Chunk 15 (guard) |
| The **WebSocket** too | C12 · Chunk 14 |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

**What changed:** when a request is malformed, the API now tells you **everything that is wrong, at once, and what it expected**. Nothing about successful responses changed. `401`, `403` and `404` are unchanged.

### The validation error
Status `422`, always this shape (keys with nothing to say are left out):

```json
{ "error": { "code": "validation_error",
             "message": "Invalid request. context_type: must be one of: LISTING, BOOKING.",
             "details": [ { "location": "body", "field": "context_type", "problem": "invalid_value",
                            "message": "`context_type` must be one of: LISTING, BOOKING.",
                            "expected": "one of: LISTING, BOOKING",
                            "allowed_values": ["LISTING", "BOOKING"], "received": "CONVERSATION" } ],
             "request_contract": { "…": "the full shape of this request, with an example" } } }
```

- **`message`** already contains every problem in plain English — you can show it as-is.
- **`details`** is one entry per problem. `field` is a dotted path (`subject.message_ids[0]`); an empty `field` means the whole body. `location` is `body`, `query` or `path`.
- **`allowed_values`** is the complete list for a closed set — **build your dropdown from it.** For an `unknown_field` it is the list of accepted field names, and `suggestion` is the closest one.
- **`request_contract`** describes the whole request: each field's `type`, whether it is `required` (or `required_when` something), its constraints, and an `example` you can copy. For requests where one field decides which others are needed (a conversation about a **listing** or a **booking**; a report on a **listing**, **booking** or **messages**), it has one **`variants`** entry per choice, each with its own example.

### What each `problem` means

| `problem` | Meaning | What to do |
|---|---|---|
| `missing` | A required field is absent | Show it on that field; `applies_when` says if it is only required under a condition |
| `invalid_type` | Wrong kind of value (text where a number was expected) | Show `expected` |
| `invalid_value` | Not one of the allowed values | Offer `allowed_values` |
| `invalid_format` | Right kind but not valid (not a UUID, not a date) | Show `expected` |
| `too_short` / `too_long` / `too_small` / `too_large` / `too_few_items` / `too_many_items` | Out of range | Show `limit` |
| `unknown_field` | You sent a field this route does not take | Remove it; see `allowed_values` / `suggestion` |
| `conditional_required` | A field is required because of another one | See `applies_when` |
| `conflicting_fields` | Two fields that cannot be sent together | Send only one |
| `invalid_json` / `body_required` | The body is not JSON / is missing | Send a JSON object |
| `wrong_content_type` | A file upload was expected | Send `multipart/form-data` with a `file` part |

**Some existing errors also gained a `details` list** without changing their code, status or message — for example a message that is too long now states the limit (`limit`), and an unsupported upload now lists the accepted file types and the maximum size.

### Mapping errors to form fields (condensed JavaScript)
```js
async function send(url, options) {
  const r = await fetch(url, options);
  if (r.ok) return { ok: true, data: await r.json() };
  const err = (await r.json()).error;
  if (err.code === 'validation_error') {
    const byField = {};
    for (const d of err.details ?? []) (byField[d.field || '_form'] ??= []).push(d.message);
    return { ok: false, byField, contract: err.request_contract };   // dropdown options: d.allowed_values
  }
  return { ok: false, code: err.code, message: err.message, details: err.details };
}
```

### Breaking changes — check these
Some failures that used to come back under a business code are really "your request is malformed" and now come back as `422 validation_error`. **If your client branches on the old code, update it.**

| Route | Input | Before | Now |
|---|---|---|---|
| `POST /api/v1/messaging/conversations` | an unknown `context_type` | `404 conversation_context_not_found` ("Unknown context type.") | `422 validation_error`, `allowed_values: ["LISTING", "BOOKING"]` |
| *(Chunk 16 completes this table from `behavior_changes.md`; every row is a real change.)* | | | |

**Unchanged on purpose:** `conversation_context_not_found` still means a listing or booking that does not exist; `invalid_or_expired_code`, `invalid_report_subject`, `conversation_not_found`, `case_not_found`, `notification_not_found`, login failures and the media stream's `403` stay deliberately vague so no one can learn what exists.

**Known limitations (tell your product people):** `request_contract` can be large on routes with big bodies (it is cut at a size limit and flagged `request_contract_omitted`); the allowed-value lists describe what the route accepts, not what *you* are allowed to do — permission and state errors are still reported separately; the WebSocket gives the same help only **after** `auth`; error text is English only; webhook and media-stream routes are unchanged.

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — Gemini turns this into the testing document in Chunk 16, running every step]

**Before you start:** run the API, open Swagger, and click **Authorize** with a token for a **student** account (for the staff scenario use an `OPERATIONS` account). In every scenario you are looking at the **response body** — it should always say what was wrong **and** what it expected, without you opening any specification file.

**G1 — Your original failure.** `POST /api/v1/messaging/conversations` with `{"context_type": "CONVERSATION", "listing_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}`.
*You should see:* `422` (not `404`); `code: "validation_error"`; one entry for `context_type` listing `LISTING` and `BOOKING`, and `received: "CONVERSATION"`; a `request_contract` with two variants, each with an example you can copy.

**G2 — Right type, missing id.** Same route, body `{"context_type": "LISTING"}`.
*You should see:* `422`; `listing_id` is `missing`, with `applies_when` saying it is required when `context_type` is `LISTING`.

**G3 — The wrong id for the type.** Same route, body `{"context_type": "LISTING", "booking_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7"}`.
*You should see:* `422` with **two** entries — `booking_id` is not accepted here, and `listing_id` is required — in one response.

**G4 — Several mistakes at once.** `POST /api/v1/properties` with a nonsense `property_type`, a text `latitude`, and no `name`.
*You should see:* one `422` with **three** entries; the `property_type` entry lists every allowed value; nothing needs a second attempt to discover the next mistake.

**G5 — Search with a missing pair.** `GET /api/v1/search?min_price_kobo=500000&sort_by=CHEAPEST`.
*You should see:* `422` naming both problems — `sort_by` with its allowed values, and `billing_period` required because a price was given.

**G6 — A bad value in the path.** `GET /api/v1/verification-status/BUILDING/<any uuid>`.
*You should see:* `422` with `location: "path"`, `field: "target_type"`, and the allowed values (`PROVIDER`, `PROPERTY`).

**G7 — A safety report with two mistakes.** `POST /api/v1/safety/reports` with an unknown `category` and no `subject`.
*You should see:* the full category list, and a `subject` entry whose contract shows the three choices (listing, booking, conversation + 1–5 messages).

**G8 — An upload of the wrong kind.** `POST /api/v1/profiles/me/avatar` with a `.txt` file; then with a very large image.
*You should see:* the same error code and message as before, plus a `details` entry listing the accepted file types, and — for the large file — the maximum size.

**G9 — Deliberately vague errors stay vague.** Send `POST /api/v1/auth/verify-email` with a well-formed but wrong code; open a conversation id that is not yours; log in with a wrong password.
*You should see:* exactly the same responses as before this module — **no `details`** on any of them.

**G10 — A route that already did this.** `POST /api/v1/payment-mock-controls/<attempt id>/simulate-webhook` with an unknown `scenario`.
*You should see:* the same behavior as before (the message names all nine scenarios), now with the same extra `details`; it was not edited.

**G11 — Not signed in.** Clear Authorize and send an invalid body to any protected route.
*You should see:* `401`, and **no** `details` or `request_contract`.

**G12 — The socket.** Connect, `auth`, then send `{"type": "nope"}`.
*You should see:* an `unknown_command` error frame whose `details`/`allowed_values` lists every command the socket accepts.

**G13 — The offline reference.** In a terminal: `python scripts/print_request_contracts.py --route "POST /api/v1/messaging/conversations"`.
*You should see:* the same contract the `422` returned, readable as Markdown, with no server running.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] **The probe suite exists, was tested both ways, and its baseline report covers every non-exempt route** (Chunk 2)
- [ ] **The shared handler returns every problem at once**, with `details`, `allowed_values`, `limit`, `suggestion`, and the full `request_contract`, and never echoes a secret (Chunk 6)
- [ ] **Your exact request** returns `422` listing `LISTING` and `BOOKING`, and the missing-id and wrong-id variants behave as in G1–G3 (Chunk 8)
- [ ] **The Fix List was reviewed by you before any module was touched** (Chunk 7), and **every module chunk began with an edit list and a skip list** (Chunks 8–13)
- [ ] **Skipped routes are provably unchanged** — schema snapshot diff and `git diff --stat` both clean (Chunk 17)
- [ ] **Protected errors are byte-identical** and a guard fails if one ever carries `details` (Chunks 3, 15)
- [ ] **Every code/status change is in the behavior-change register and in Part F** (Chunks 8–13, 16)
- [ ] **Every example body is proven valid by a test**, and the **STRICT suite passes over every route** (Chunk 15)
- [ ] **The WebSocket gives the same help after `auth`**, and pre-`auth` behavior is unchanged (Chunk 14)
- [ ] **The offline reference script works and its committed output cannot drift** (Chunk 15)
- [ ] **No migration, no response change other than `validation_error` and R4 `details`, no success-path change** (Chunk 17)
- [ ] **The manual testing guide contains only real outputs or an explicit "not verified"** (Chunk 16)

---

*End of Module 18 specification.*
