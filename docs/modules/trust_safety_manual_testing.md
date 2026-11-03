# CAMP MATCH — MODULE 13: TRUST & SAFETY MANUAL TESTING GUIDE

## Preconditions
- Database running (`scripts/db_start.sh`).
- Application running.
- Test accounts: Ada & Chidi (Students / Reporters), Bola (Scout / Listing owner), Rita (Operations / Reviewer), Ade (Admin / Approver), Dual (Operations + Admin).

## Test Scenarios
- **S1:** A student reports a suspicious listing (`POST /safety/reports`). Expected: `201` with `report_id`, `status: "RECEIVED"`.
- **S2:** A user reports a message (`POST /safety/reports` with conversation and message ID). Expected: `201` for valid message; `422` for own message or unjoined conversation.
- **S3:** Accepted is not investigated. Expected: Report stays `RECEIVED`, listing remains published.
- **S4:** Duplicate and flood protection. Expected: `200` on idempotency replay; `409` on duplicate open; `429` on rate limit.
- **S5:** Reviewer triages case (`/review/reports/{id}/open-case`, `/triage`, `/status`). Expected: Successful transitions following C6.
- **S6:** Unauthorized people cannot open/review cases. Expected: `403` or `404`.
- **S7:** Two reports, one case (`/cases/{id}/reports`). Expected: Both reports linked, independent timestamps.
- **S8:** Evidence restricted and audited. Expected: Evidence metadata shown in case view; full content view logged in case history.
- **S9:** Findings need corroboration (`CORROBORATED_FACT` note required before decision). Expected: `422` if decision recorded without notes.
- **S10:** Four-eyes enforcement approval and application (`/enforcement/{id}/approve`). Expected: Listing suspended, unbookable, unpublished.
- **S12:** Worker queue execution (`scripts/run_safety_worker.py`). Expected: Idempotent execution and recovery of approved/reversal actions.
- **S15:** Audit trail immutability. Expected: Database triggers reject `UPDATE` and `DELETE` on audit tables (`safety_notes`, `safety_decisions`, `safety_evidence`, `safety_case_events`).
- **S16:** Case resolution, closure, and enforcement reversal. Expected: Case resolves/closes, enforcements can be reversed moving listing to `UNAVAILABLE`.
