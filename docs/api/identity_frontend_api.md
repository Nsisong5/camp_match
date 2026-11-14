# Frontend API Documentation — Identity, Google Sign-In & Email Verification

All paths are under `/api/v1`. Errors always look like `{ "error": { "code": "...", "message": "..." } }` or `{ "detail": { "code": "...", "message": "..." } }`; branch on `code`, show `message`.

### A. Email and password sign-up (now with a verification code)
1. **`POST /auth/register`** (unchanged request) -> `201` with the old fields **plus `email_verification_required`** (`true` for a normal sign-up). If `true`, go to a "Enter your 6-digit code" screen. The server has already emailed the code.
2. **`POST /auth/verify-email`** `{ "email", "code" }` -> `200 { "verified": true }`. **No tokens are returned — call `/auth/login` next.** Any failure is `422 invalid_or_expired_code` — the same message for a wrong code, an expired code, too many tries, or an unknown email; **do not try to tell them apart.** A code that isn't exactly 6 digits is `422 validation_error`.
3. **`POST /auth/resend-verification`** `{ "email" }` -> **always** `202`, always the same message, whether or not the email has an account. Show "If this email needs verification, a new code has been sent." and **disable the button for 60 seconds** on the client (the server also limits it, silently).
4. **`POST /auth/login`** on an account that isn't verified yet -> **`403 email_not_verified`** (only returned when the password was right). The server has already sent a fresh code, so send the user straight to the code screen.
- Code facts: 6 digits, valid **10 minutes**, locked after **5 wrong tries** (request a new code), a new code replaces the old one.
- **Existing accounts are already marked verified** and are unaffected.

### B. Continue with Google
**At app start, call `GET /auth/google/config`** (no sign-in needed) -> `{ "enabled", "real_enabled", "mock_enabled", "client_ids" }`.
- `real_enabled: true` -> show Google's **official** sign-in button/flow, configured with one of the returned `client_ids`. Take the **ID token** Google gives you and send it as `id_token`:
  - **Web** (Google Identity Services): the button's callback returns a `credential` — that string is the `id_token`.
- `mock_enabled: true` (only true in `local` / `test` mode): show a developer "Mock Google" button beside the real one. It calls `POST /dev/google-mock/token {"email": "..."}` to get a mock ID token.
- Send the ID token: **`POST /auth/google`** `{ "id_token", "nonce"? }` -> `200` with the standard token pair **plus `is_new_account`** (`true` on first sign-up, `false` on returning sign-in). If `true`, take them to the student/scout profile-creation step (Module 4).
- Errors from `POST /auth/google`:
  - `401 invalid_google_token`: bad signature, expired, or wrong client ID.
  - `409 account_exists`: an account with that email was registered with email+password and verified. Show: *"An account with this email already exists. Please sign in with your email and password, then link Google from Settings."*
  - `422 google_email_not_supported`: the Google account's email is not a Gmail or Google Workspace address, or Google hasn't verified it. Show: *"Please register with an email and password."*

### C. Account settings (all need `Authorization: Bearer <access_token>`)
- **`GET /auth/me`** now also returns **`email_verified`** (bool) and **`sign_in_methods`** (`["PASSWORD"]`, `["GOOGLE"]`, or both). Use it to decide what to show.
- **`POST /auth/google/link`** `{ "id_token", "nonce"? }` -> `204`. Errors: `409 google_already_linked`, `409 google_identity_in_use`, `401 invalid_google_token`.
- **`POST /auth/google/unlink`** -> `204`. `409 last_sign_in_method` if they have no password — prompt them to set one first.
- **`POST /auth/password`** `{ "password" }` (8–128 characters) -> `204`. Only for accounts **without** a password (Google-only); otherwise `409 password_already_set`.

### D. Login screen hints
- A Google-only account that tries email+password gets the ordinary `401 invalid_credentials` (the server deliberately doesn't say why). Add a static hint under the login form: **"Signed up with Google? Use Continue with Google."**

### E. Development helpers (local/test only; `404` anywhere else)
- **`GET /dev/mailbox?to=<email>`** — the last emails "sent" to that address (so you can read the verification code without a real inbox).
- **`POST /dev/google-mock/token`** — mint a mock Google token (see B).
