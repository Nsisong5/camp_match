# CAMP MATCH — DIAGNOSE-AND-FIX PROMPT
**For: Gemini CLI. From: Nsisong, via Claude (Technical Specification Engineer).**
**This is not a module and not a feature spec.** It is three investigations. For each one you must **find out what is actually wrong, prove it with evidence, fix the root cause, and prove the fix with a test that fails before and passes after.** Do the tasks **in the order A → B → C**: Task B depends on Task A.

---

## GROUND RULES (READ BEFORE TOUCHING ANYTHING)

1. **Diagnose before you change.** For every task your first output is an evidence report (real commands, real output). Do not edit code until the report says where the fault is.
2. **Reproduce first.** If you cannot reproduce a problem, stop and say so; do not "fix" something you cannot see.
3. **Test first.** For every bug, write the failing test **before** the fix, show it failing (real output), then fix, then show it passing. A fix without a failing-then-passing test is not accepted.
4. **Never weaken, delete or skip an existing test to get green.** If an existing test now contradicts correct behavior, stop and report it with the reasoning.
5. **Fix the root cause, not the symptom.** Example: if a value is missing from a response because it is never saved, do not patch the response; fix the save.
6. **Smallest correct change.** No refactors, no renamed modules, no "while I'm here" improvements. If you see another problem, **report it, don't fix it.**
7. **Respect the architecture** (Module 15's rules apply): modules talk **only** through `application/ports`; events are written with `uow.add_event` in the same transaction and carry **ids and enums only**; system use cases take no actor and are never on HTTP; nothing logs secrets, amounts, names or one-time codes (except the one `local`/`test` log email adapter).
8. **Find out why the tests didn't catch it.** For Tasks A and B, finish with one sentence on why the existing suite stayed green while the behavior was broken, and add the missing assertion.
9. **Use the git history.** Both A and B are regressions ("it worked earlier"). Use `git log`, `git blame` and, where practical, `git bisect` with your new failing test to name the **commit** that broke it and say which module's change did it.
10. **If a decision is needed that this prompt does not make, stop and ask.** Do not choose for yourself.
11. **Real outputs only.** Anything you could not run or verify is reported as **not verified**. Redact secrets (API keys, SMTP passwords, tokens) in every report.

**Reports use this shape for each task:** (1) what I ran and what I saw; (2) root cause, stated in one paragraph; (3) the commit that introduced it (if found); (4) files changed; (5) the failing test, then the passing test; (6) why the old tests missed it; (7) anything I found but did not touch.

---

## WHAT THE SYSTEM IS SUPPOSED TO DO (background you need)

- **Booking** (Modules 09 → 10 → 15) owns the handover facts. After a booking is `CONFIRMED` (paid), the **scout offers** the handover (`POST /api/v1/bookings/{id}/handover/offered`) → `handover_offered_at` and `handover_offered_by` are stored, and Booking publishes `HandoverOffered`. The **student accepts** (`POST /api/v1/bookings/{id}/handover/accepted`) → `handover_accepted_at` (and its `_by` field, if Module 10 defined one — confirm against the code) is stored and Booking publishes `HandoverAccepted`. Both facts are **permanent once set**. Every endpoint that returns a booking must show them.
- **Events** (Module 15) go through the shared transactional outbox (written in the same transaction as the change) and are delivered by the **platform worker** (`scripts/run_platform_worker.py`) to subscribers. Notification (Module 12) turns events into in-app notifications; Module 15 added **actions** (`COMPLETE_PAYMENT`, `OFFER_HANDOVER`, `ACCEPT_HANDOVER`) that stay open until done.
- **Which module notifies whom today** (this matters for Task B):
  - Student: "Booking confirmed" (`booking.confirmed.student`, Module 12); "Complete your payment" (action, Module 15); "Confirm you have access" (`ACCEPT_HANDOVER` action, Module 15, after the scout offers).
  - Scout: "Booking confirmed" and "Action needed: arrange handover" (`OFFER_HANDOVER` action, Module 15); a handover-reminder.
  - **Admin: nothing, by design.** Module 12 explicitly excluded Payment events (its Finding 4), Module 14 (Admin) publishes and consumes no events, and Module 15 only added *student* payment notices. **No module in the codebase has ever notified an admin that funds are ready to release.** The "Release Governance" amendment (`Camp_Match_Amendment_Release_Governance_Admin_Tasks_Transaction_Review.md`) is what introduces it (events `PaymentReleaseDue` etc., the `RELEASE_FUNDS` action, six staff notification types).
- **Email one-time codes** (Module 17): a six-digit code is emailed through the `EmailSender` port. `LogEmailSender` (local/test only) prints it in the server log and a dev mailbox; `SmtpEmailSender` (`aiosmtplib`) sends real mail. `EMAIL_BACKEND` chooses which.

---

## TASK A — A BOOKING SHOWS NO HANDOVER DATA AFTER IT WAS OFFERED AND ACCEPTED  *(do this first)*

**The symptom (real output from Nsisong).** A booking returned in a list response (`{"items": [ … ]}`) with `status: "CONFIRMED"`, `confirmed_at` set, and — after the handover was offered and accepted —

```json
"handover_offered_at": null,
"handover_offered_by": null,
"handover_accepted_at": null,
"closure": null
```
(booking id `be77d8ae-7f8c-47bf-9933-916d6cc1ccb8`, created 2026-11-17). It worked in an earlier module; it broke after later modules were added.

### A1 — Reproduce
Using the running API (real HTTP, not unit tests): create a booking on a published listing as a student, pay through the payment mock controls so it is `CONFIRMED`, then as the **scout** call `POST …/handover/offered`, then as the **student** call `POST …/handover/accepted`. **Record every status code and response body.** An error or a `204`/`200` that does nothing is itself the finding.

### A2 — Decide: is it the write path or the read path?
Run a read-only query against the database for that booking (find the real table and column names in the Booking migrations; do not guess):
```sql
SELECT id, status, confirmed_at, handover_offered_at, handover_offered_by,
       handover_accepted_at /* and the accepted_by column if it exists */
FROM <bookings table> WHERE id = '<booking id>';
```
- **Columns exist and contain values, but the API shows null → READ path (A3b).**
- **Columns are null in the database after both calls succeeded → WRITE path (A3a).**
- **A column does not exist → a migration or model regression (A3c).**
Report which, with the query output.

### A3a — Write-path checklist (the database is null)
Check, in this order, and report what you find at each step:
1. The two routes are mounted and reach `ConfirmHandoverOffered` / `ConfirmHandoverAccepted` (not a stub or an older function).
2. The use case actually calls the repository method that writes the columns. Read the repository method: does its `UPDATE` set **all** the handover columns?
3. **The conditional update's row count.** Booking writes are conditional (`UPDATE … WHERE …`) and decide success by affected rows. Find any `WHERE` clause that no longer matches (for example a status or `closure_code`/reminder-claim condition added by Module 15). **A zero-row result that the use case treats as "idempotent repeat → success" would return `200` while writing nothing.** This is the most likely cause — check it explicitly.
4. The unit of work commits (an exception swallowed after the write, or an `add_event` failure that rolls the transaction back while the error is caught and a success returned).
5. The entity/ORM mapper writes the fields back (a field added to the entity but missing from the model's column mapping, or the reverse).
6. Any later code (Module 15's reminder claims, invalidation, reconciliation, the Housing subscriber) that **overwrites** the handover columns with null (for example a full-row `save()` of a stale entity).

### A3b — Read-path checklist (the database has values)
1. Compare **every endpoint that returns a booking**: the detail route, `mine`, the per-property list the scout uses, and any admin-facing read. Note which show the values and which show null.
2. For the failing one(s): the response schema/DTO (are the handover fields declared? are they populated from the entity?), the mapper from ORM model → entity → DTO, and the repository's list query (an explicit column list, `load_only`, a different projection, or a separate "summary" DTO that predates the handover columns).
3. A `from_attributes`/alias mismatch (a field renamed in the model but not in the schema), or `exclude_none`-style serialization that changes shape.
4. Whether Module 15's `closure` object is built from the same entity (the symptom shows `closure: null` on a booking that is simply open — confirm that is correct and not a symptom of the same mapper problem).

### A3c — Missing column / migration regression
Compare the current models with the applied migrations and with what Module 10 Chunk 1 required (`handover_offered_at`, `handover_offered_by`, `handover_accepted_at`, and the accepted-by field if specified). Report any drift. Do **not** run destructive migrations; report first.

### A4 — Find the commit
With the failing test from A5 in place, run `git bisect` (or `git log -p -- <the files you identified>`) to find the commit that broke it. Name the commit, its message, and which module's work it belonged to.

### A5 — Fix and prove
1. Write the failing tests first:
   - **Write path:** after offer then accept via the real API, read the database row (through the repository or a direct query in the integration test) and assert **all** handover columns are populated and `accepted_at ≥ offered_at`.
   - **Read path, one test per endpoint** that returns a booking (detail, mine, per-property list, any other): the response contains `handover_offered_at`, `handover_offered_by`, `handover_accepted_at` (and the accepted-by field if it exists) with the stored values.
   - **Serializer parity:** one test that builds a booking with every field populated and asserts that every endpoint's response contains the **same** set of keys.
   - **Idempotency:** a repeated offer/accept returns success, changes nothing, and publishes **no** second event.
2. Fix the root cause only.
3. Show the previously failing tests passing, and Booking's full suite passing.

**Acceptance for Task A:** the exact reproduction in A1 now returns the handover values in **every** booking-returning endpoint; the report names the root cause and the commit; the new tests are in the repository.

---

## TASK B — ADMINS DO NOT RECEIVE A "RELEASE FUNDS" NOTIFICATION AFTER A STUDENT CONFIRMS  *(after Task A)*

**The symptom.** A student confirmed (accepted the handover) and **no notification arrived for the admin.**

### B0 — First establish which situation this is. Report it before anything else.
1. **Is the Release Governance amendment implemented?** Check for: the events `PaymentReleaseDue` / `PaymentAutoReleaseWarning` / `PaymentFundsReleased` / `PaymentFundsRefunded` / `PaymentDisputeRaised`; the tables `release_schedules`, `release_warnings`, `transaction_reviews`; the `NotificationAction.RELEASE_FUNDS` value; the notification types `payment.release_due.staff` and the five others; Security's `ListIdentitiesHoldingPermission`.
   - **If none of it exists:** this is **expected behavior, not a bug** — no module has ever notified admins (see "Which module notifies whom today"). **Do not invent a quick hack** (for example, a one-off notification subscriber that bypasses the design). Report this finding, list exactly which parts of the amendment are missing, and **stop Task B**. Nsisong will tell you to proceed with the amendment's chunks.
   - **If it is partly or fully implemented:** continue to B1; the symptom is then a real defect.
2. **Which event is meant by "student confirms"?** The admin signal fires when the **student accepts the handover** (`HandoverAccepted`, with the offer recorded first) — **not** when the booking becomes `CONFIRMED` after payment. Check which action was actually performed in the failing test run and say so. (A booking that is only `CONFIRMED` correctly produces **no** admin notification.)

### B1 — Trace the chain, hop by hop, with evidence at every hop
Stop at the **first** hop that fails; that is your root cause. Report the evidence for each hop you passed, too.

| Hop | What must be true | How to check (find real table/command names in the code) |
|---|---|---|
| 1 | The handover facts are valid on the booking: `offered_at` set, `accepted_at` set, `accepted_at ≥ offered_at` | The Task A query. **If this fails, Task A is the cause — fix it first.** |
| 2 | A confirmed `Payment` and a fund disposition exist for the booking (the mock payment completed) | Payment tables; `GET /payments/{id}` as staff |
| 3 | Booking wrote a `HandoverAccepted` row into the **outbox** in the same transaction | The Module 15 outbox table: one row, right type, `status` |
| 4 | The **platform worker is running** and the outbox rows are being claimed (not stuck `PENDING`, not `FAILED`/dead-lettered) | `python scripts/run_platform_worker.py --stats` / `--list`; the worker's log; the outbox's attempt counts and last error |
| 5 | Payment's Booking subscriber is **registered** in `build_event_bus` and its event contract is registered | Read `build_event_bus`; the registry; the subscriber's log line |
| 6 | `SyncBookingFactsForReview` ran and **created/updated the `transaction_reviews` row** (`student_confirmed_at` set, stage `RELEASE_DUE`) and **opened a `release_schedules` row** | The three tables |
| 7 | `PaymentReleaseDue` was written to the outbox (exactly once) | Outbox rows of that type for the payment |
| 8 | Notification's strict parser **accepted** the event (not `REJECTED`/`FAILED`) | Notification's processed-event table for that event id and its status/reason |
| 9 | The recipient list is **not empty**: `StaffRecipientProvider.list_release_approvers()` → Security's `ListIdentitiesHoldingPermission(PAYMENT_AUTHORIZE_RELEASE)` returns the admin's identity id, **and** the account is `ACTIVE`. **Check the test admin really holds the `ADMIN` role** — `PAYMENT_AUTHORIZE_RELEASE` is `ADMIN`-only; an `OPERATIONS`-only account correctly receives nothing | Call the use case in a shell; Security's role table; a WARNING `notification_no_recipient` in the log means exactly this |
| 10 | A `notifications` row exists for that admin: type `payment.release_due.staff`, category `PAYMENT`, action `RELEASE_FUNDS`, target `BOOKING:<booking id>`, `resolved_at` null | SQL on the notifications table |
| 11 | The API returns it **to that admin**: `GET /api/v1/notifications` and `GET /api/v1/notifications?action_required=true` with **that admin's** token (verify the token's identity id equals the recipient id; check category filters and paging) | Real HTTP |

**Common traps to rule in or out explicitly:** the worker is not running (so nothing past the outbox ever happens); the event was processed once as `REJECTED` and replays are skipped as already-processed (a parser or contract that was wrong at the time); the admin used for testing is `OPERATIONS`; the subscriber was added but not registered; the staff-recipient adapter filters out the account (status or role lookup); an exception in a subscriber is logged at DEBUG and swallowed; the notification was created and **already resolved** by a later event (for example `BookingInvalidated` or a dispute event) — check `resolved_at`.

### B2 — Fix and prove
1. Write the failing test at the hop that broke (a unit or integration test), **and** an end-to-end test of the whole path if one does not exist: book → pay (mock controls) → scout offers → student accepts → run the worker once → the admin has **one open** `payment.release_due.staff` notification with action `RELEASE_FUNDS` and target `BOOKING:<id>`; the student and the scout have **no** staff notice; an `OPERATIONS`-only account has none.
2. Fix the root cause only.
3. Show the end-to-end test passing and the Notification, Payment, Booking and Security suites passing.

**Acceptance for Task B:** either (i) a written, evidenced finding that the amendment is not implemented and exactly what is missing, with no code changed; or (ii) the defect fixed with the end-to-end test in the repository and the root-cause hop named in the report.

---

## TASK C — IS THE EMAIL ONE-TIME CODE REALLY SENT TO A REAL ADDRESS?  *(verification first; fix only defects)*

**Background:** Module 17 specified a real SMTP sender, but the **default** backend is `log` (the code appears in the server log and the dev mailbox only). Real delivery needs `EMAIL_BACKEND=smtp` and working SMTP credentials. Module 17's own notes say deployed environments refuse `log`.

### C1 — Inspect (report, with secrets redacted)
1. The effective values of `EMAIL_BACKEND`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_USE_STARTTLS`, `SMTP_FROM_ADDRESS`, `SMTP_TIMEOUT_SECONDS` in the environment actually used for Nsisong's testing (**never print `SMTP_PASSWORD`**; say only whether it is set).
2. Which `EmailSender` adapter is composed at startup (print the class name).
3. Whether `SmtpEmailSender` exists and what it supports: **STARTTLS only, or also implicit TLS (port 465)?** Report what the code does for each.

### C2 — Prove delivery as far as a program can
1. Write a **one-off script** (not committed; delete it afterwards) that builds the real `SmtpEmailSender` from the environment and sends a plain test message to an address Nsisong supplies. Report the real outcome: success, or the exact exception class and message (no secrets).
2. Register a new password account with that real address through the API with `EMAIL_BACKEND=smtp`. Report: the response, whether the server log shows `email_send_failed` (the use case logs this at ERROR and **never fails the request**, by design — so a broken sender is invisible to the client), and whether the SMTP server accepted the message.
3. **You cannot read Nsisong's inbox.** State plainly that receipt must be confirmed by a person, and give Nsisong the exact steps and the address to check (including the spam folder).

### C3 — Fix only genuine defects
Examples that **are** in scope: the adapter never connects because of a wrong default (for example STARTTLS forced when the provider needs implicit TLS on 465 — if so, report it and propose the smallest change, **then ask**); a configuration key that is read but ignored; a startup rule that wrongly blocks `smtp`. Examples that are **not** in scope: choosing an email provider, adding retries or a queue, changing the code format, adding password reset. Report those as recommendations.

### C4 — Answer these in the report
- Do **Google** sign-ups need the code? (They should not — Google's verification counts; only **password** sign-ups need the emailed code. Confirm in the code and with `identity_email_verification_required`.)
- What does a user see when the SMTP send fails? (Expected: nothing — the response is the same `202`; they can press resend.)
- Is anything in the code logging the raw code outside the `local`/`test` log adapter?

**Acceptance for Task C:** a verified statement of which backend is live; the real result of the test send (or the exact error); and a clear list of what only a human can confirm.

---

## FINISH

After all three tasks, give one **Completion Report**:
1. **Verified** (command and real output).
2. **Implemented but not verifiable here** (and why).
3. **Not done / decisions needed** (and why).
4. Anything you noticed but deliberately did not change.

Do not claim a task is done unless its acceptance criterion is met with real evidence.
