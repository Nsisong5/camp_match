# Module 17 Manual Testing Guide: Google Sign-In & Email Verification

## Start Here
Welcome to the manual testing guide for Module 17 (Google Sign-In & Email Verification). You will test OTP email verification for password accounts, mock/real Google sign-in, account linking/unlinking, and password management.

### Test Accounts & Setup
- In `.env` set:
  ```env
  APP_ENV=local
  EMAIL_BACKEND=log
  GOOGLE_AUTH_BACKEND=both
  GOOGLE_OAUTH_CLIENT_IDS=placeholder.apps.googleusercontent.com
  ```
- **Restart the API server after changing `.env`.**
- Test Persona: **Ada** (a student registering fresh — use new email addresses as specified in each test). Older test accounts (Bola, Ade, Rita) already exist.

### Helpers (Paste once per Termux / bash session)
```bash
BASE=http://localhost:8000/api/v1
post() { curl -s -X POST "$BASE$1" -H 'Content-Type: application/json' ${3:+-H "Authorization: Bearer $3"} -d "$2" | jq .; }
code() { curl -s "$BASE/dev/mailbox?to=$1" | jq -r '.[0].text' | grep -oE '[0-9]{6}' | head -1; }
mock() { curl -s -X POST $BASE/dev/google-mock/token -H 'Content-Type: application/json' -d "{\"email\":\"$1\"}" | jq -r '.id_token'; }
```
- `post PATH 'JSON' [TOKEN]`: sends a JSON POST request to the API with an optional bearer token.
- `code EMAIL`: fetches the newest 6-digit verification code from the local developer mailbox.
- `mock EMAIL`: generates a mock Google ID token for testing without Google Cloud credentials.

---

## Test Scenarios

### V1 — Register and receive the code
*What this proves:* Signing up with email and password automatically sends a verification code to the dev mailbox.
*Do this:*
```bash
post /auth/register '{"email":"ada1@gmail.com","password":"correcthorse123"}'
code ada1@gmail.com
```
*You should see:*
`201` response with `"email_verification_required": true`, and a 6-digit number printed on the terminal (e.g. `123456`).
*If you don't:*
No number means the email wasn't delivered to the dev mailbox; verify `EMAIL_BACKEND=log` and check terminal logs.
*Cleanup:*
None.

---

### V2 — Login is blocked until email verification
*What this proves:* Unverified password accounts are forbidden from logging in until verified.
*Do this:*
```bash
post /auth/login '{"email":"ada1@gmail.com","password":"correcthorse123"}'
post /auth/login '{"email":"ada1@gmail.com","password":"wrongpassword999"}'
```
*You should see:*
The correct password returns `403` with `email_not_verified`. The wrong password returns `401` with `invalid_credentials` (it does not reveal the account's unverified status).
*If you don't:*
If login succeeds before verification, verify `IDENTITY_EMAIL_VERIFICATION_REQUIRED=true` in `.env`.
*Cleanup:*
None.

---

### V3 — Wrong code, then the right code
*What this proves:* An incorrect verification code is rejected without locking the account, and the correct code successfully verifies it.
*Do this:*
```bash
post /auth/verify-email '{"email":"ada1@gmail.com","code":"000000"}'
REAL_CODE=$(code ada1@gmail.com)
post /auth/verify-email "{\"email\":\"ada1@gmail.com\",\"code\":\"$REAL_CODE\"}"
TOKEN=$(post /auth/login '{"email":"ada1@gmail.com","password":"correcthorse123"}' | jq -r '.access_token')
curl -s -H "Authorization: Bearer $TOKEN" $BASE/auth/me | jq .
```
*You should see:*
The wrong code yields `422` with `invalid_or_expired_code`. The correct code yields `{"verified": true}`. Login returns access tokens, and `GET /auth/me` displays `"email_verified": true`.
*If you don't:*
Check if the code was entered correctly or if more than 10 minutes elapsed.
*Cleanup:*
None.

---

### V4 — Verification code expiration
*What this proves:* One-time codes expire after the configured TTL and return the generic invalid/expired code error.
*Do this:*
In `.env` set `IDENTITY_OTP_TTL_SECONDS=10` and **restart the API server.**
```bash
post /auth/register '{"email":"ada2@gmail.com","password":"correcthorse123"}'
sleep 15
EXPIRED_CODE=$(code ada2@gmail.com)
post /auth/verify-email "{\"email\":\"ada2@gmail.com\",\"code\":\"$EXPIRED_CODE\"}"
post /auth/resend-verification '{"email":"ada2@gmail.com"}'
NEW_CODE=$(code ada2@gmail.com)
post /auth/verify-email "{\"email\":\"ada2@gmail.com\",\"code\":\"$NEW_CODE\"}"
```
*You should see:*
The first verification returns `422` with `invalid_or_expired_code` (identical to wrong code error). After resending, the new code succeeds with `{"verified": true}`.
*If you don't:*
Verify that the API server was restarted so the 10-second TTL took effect.
*Cleanup:*
Revert `IDENTITY_OTP_TTL_SECONDS` in `.env` and **restart the API server.**

---

### V5 — Too many incorrect guesses lock the code
*What this proves:* Entering 5 incorrect attempts invalidates the active code to protect against brute-force attacks.
*Do this:*
```bash
post /auth/register '{"email":"ada3@gmail.com","password":"correcthorse123"}'
REAL_CODE=$(code ada3@gmail.com)
for i in {1..5}; do post /auth/verify-email "{\"email\":\"ada3@gmail.com\",\"code\":\"00000$i\"}"; done
post /auth/verify-email "{\"email\":\"ada3@gmail.com\",\"code\":\"$REAL_CODE\"}"
post /auth/resend-verification '{"email":"ada3@gmail.com"}'
NEW_CODE=$(code ada3@gmail.com)
post /auth/verify-email "{\"email\":\"ada3@gmail.com\",\"code\":\"$NEW_CODE\"}"
```
*You should see:*
All 5 wrong attempts return `422`. Even with the real code, verification fails (`422`) because it is locked. After resending, the newly issued code succeeds.
*If you don't:*
Confirm 5 distinct invalid verification requests were executed.
*Cleanup:*
None.

---

### V6 — Resend verification limits and anti-enumeration
*What this proves:* Resending verification codes is throttled by cooldown without leaking account existence to callers.
*Do this:*
```bash
post /auth/register '{"email":"ada4@gmail.com","password":"correcthorse123"}'
post /auth/resend-verification '{"email":"ada4@gmail.com"}'
post /auth/resend-verification '{"email":"ada4@gmail.com"}'
post /auth/resend-verification '{"email":"ada-nonexistent@gmail.com"}'
curl -s "$BASE/dev/mailbox?to=ada4@gmail.com" | jq 'length'
```
*You should see:*
Every resend call returns HTTP `202 Accepted` with the identical message body. The mailbox contains only one email (rapid consecutive calls were silently throttled).
*If you don't:*
Check `identity_otp_resend_cooldown_seconds` in settings.
*Cleanup:*
None.

---

### V7 — Unverified registration squatting protection
*What this proves:* An unverified registration cannot lock out the rightful owner; a new registration with the same email replaces the unverified credentials.
*Do this:*
```bash
post /auth/register '{"email":"victim1@gmail.com","password":"attackerpass123"}'
post /auth/register '{"email":"victim1@gmail.com","password":"realownerpass123"}'
NEW_CODE=$(code victim1@gmail.com)
post /auth/verify-email "{\"email\":\"victim1@gmail.com\",\"code\":\"$NEW_CODE\"}"
post /auth/login '{"email":"victim1@gmail.com","password":"attackerpass123"}'
post /auth/login '{"email":"victim1@gmail.com","password":"realownerpass123"}'
```
*You should see:*
The second registration succeeds (`201`). After verifying, logging in with `attackerpass123` returns `401 Unauthorized`, while `realownerpass123` returns tokens.
*If you don't:*
Confirm the initial registration was not verified before the second registration.
*Cleanup:*
None.

---

### V8 — Legacy accounts bypass verification
*What this proves:* Accounts created prior to Module 17 migration were backfilled as `LEGACY` and do not require verification.
*Do this:*
```bash
post /auth/login '{"email":"bola@example.com","password":"password123"}'
```
*You should see:*
Immediate login success returning access and refresh tokens, without requiring OTP verification.
*If you don't:*
Ensure database migrations were applied (`poetry run alembic upgrade head`).
*Cleanup:*
None.

---

### G1 — Google configuration endpoint
*What this proves:* Clients can query which Google authentication backends and client IDs are available before displaying UI buttons.
*Do this:*
```bash
curl -s $BASE/auth/google/config | jq .
```
*You should see:*
`{"enabled": true, "real_enabled": true, "mock_enabled": true, "client_ids": ["..."]}` when `GOOGLE_AUTH_BACKEND=both`.
*If you don't:*
Check `GOOGLE_AUTH_BACKEND` setting in `.env`.
*Cleanup:*
None.

---

### G2 — Mock Google first-time sign-in creates an account
*What this proves:* Signing in with Google automatically provisions an account with email pre-verified.
*Do this:*
```bash
TOKEN=$(mock newgoogle1@gmail.com)
post /auth/google "{\"id_token\":\"$TOKEN\"}"
```
*You should see:*
Returns `200 OK` with token pair and `"is_new_account": true`.
*If you don't:*
Check that `GOOGLE_AUTH_BACKEND` is set to `both` or `fake`.
*Cleanup:*
None.

---

### G3 — Returning Google user sign-in
*What this proves:* Subsequent sign-ins with the same Google subject reuse the existing account without duplicate creation.
*Do this:*
```bash
TOKEN=$(mock newgoogle1@gmail.com)
post /auth/google "{\"id_token\":\"$TOKEN\"}"
```
*You should see:*
Returns `200 OK` with `"is_new_account": false`.
*If you don't:*
Verify that the same email address was used in the mock token.
*Cleanup:*
None.

---

### G4 — Google sign-in collision with verified password account
*What this proves:* A verified password account prevents automatic Google account takeover; linking requires password authentication.
*Do this:*
```bash
TOKEN=$(mock ada1@gmail.com)
post /auth/google "{\"id_token\":\"$TOKEN\"}"
PW_TOKEN=$(post /auth/login '{"email":"ada1@gmail.com","password":"correcthorse123"}' | jq -r '.access_token')
post /auth/google/link "{\"id_token\":\"$TOKEN\"}" $PW_TOKEN
post /auth/google "{\"id_token\":\"$TOKEN\"}"
```
*You should see:*
The direct sign-in returns `409` with `account_exists`. After linking using the authenticated bearer token, `POST /auth/google` succeeds.
*If you don't:*
Ensure `ada1@gmail.com` was verified in scenario V3.
*Cleanup:*
None.

---

### G5 — Google claims an unverified account
*What this proves:* A Google sign-in claims an unverified squatting account and strips the squatter's password.
*Do this:*
```bash
post /auth/register '{"email":"squat1@gmail.com","password":"attackerpass123"}'
TOKEN=$(mock squat1@gmail.com)
post /auth/google "{\"id_token\":\"$TOKEN\"}"
post /auth/login '{"email":"squat1@gmail.com","password":"attackerpass123"}'
```
*You should see:*
Google sign-in succeeds (`is_new_account: true`). Attempting to log in with `attackerpass123` returns `401 Unauthorized`.
*If you don't:*
Ensure `squat1@gmail.com` was unverified before the Google sign-in.
*Cleanup:*
None.

---

### G6 — Refusal of unsupported Google emails
*What this proves:* Only Gmail and Google Workspace accounts with `email_verified: true` can sign up via Google.
*Do this:*
```bash
YAHOO_TOKEN=$(mock someone@yahoo.com)
post /auth/google "{\"id_token\":\"$YAHOO_TOKEN\"}"
UNVERIFIED_TOKEN=$(curl -s -X POST $BASE/dev/google-mock/token -H 'Content-Type: application/json' -d '{"email":"test@gmail.com","email_verified":false}' | jq -r '.id_token')
post /auth/google "{\"id_token\":\"$UNVERIFIED_TOKEN\"}"
```
*You should see:*
Both requests return `422` with `google_email_not_supported`.
*If you don't:*
Check that the email domain is not gmail.com or lacks hosted domain claim.
*Cleanup:*
None.

---

### G7 — Account credential lifecycle: Set password and unlink Google
*What this proves:* Google-only users can set a password, and accounts cannot unlink their last remaining sign-in method.
*Do this:*
```bash
G_TOKEN=$(mock unlinkuser@gmail.com)
ACCESS_TOKEN=$(post /auth/google "{\"id_token\":\"$G_TOKEN\"}" | jq -r '.access_token')
post /auth/google/unlink "" $ACCESS_TOKEN
post /auth/password '{"password":"newpassword123"}' $ACCESS_TOKEN
post /auth/google/unlink "" $ACCESS_TOKEN
post /auth/login '{"email":"unlinkuser@gmail.com","password":"newpassword123"}'
```
*You should see:*
The first unlink fails (`409 last_sign_in_method`). Setting password returns `204`. The second unlink returns `204`. Logging in with the new password returns tokens.
*If you don't:*
Ensure the access token is passed in the Authorization header.
*Cleanup:*
None.

---

### G8 — Disabled accounts are blocked from Google sign-in
*What this proves:* Administrative account suspensions and disablements prevent Google sign-in.
*Do this:*
```bash
G_TOKEN=$(mock disabled_user@gmail.com)
RESP=$(post /auth/google "{\"id_token\":\"$G_TOKEN\"}")
ACC_ID=$(curl -s -H "Authorization: Bearer $(echo $RESP | jq -r .access_token)" $BASE/auth/me | jq -r .id)
ADMIN_TOKEN=$(post /auth/login '{"email":"admin@campmatch.com","password":"adminpassword"}' | jq -r '.access_token')
post /admin/operations/accounts/$ACC_ID/disable '{"reason":"Fraudulent activity"}' $ADMIN_TOKEN
post /auth/google "{\"id_token\":\"$G_TOKEN\"}"
```
*You should see:*
Google sign-in returns `403` with `account_disabled`.
*If you don't:*
Verify that the operations/admin account has appropriate security roles.
*Cleanup:*
None.

---

### G9 — Real Google sign-in (Run by Nsisong with the real frontend)
*What this proves:* End-to-end integration with Google Identity Services and Google Cloud OAuth credentials.
*One-time Google Cloud setup:*
1. In **Google Cloud Console**, create or select your project.
2. Configure **OAuth consent screen** (User Type: External, Testing mode, add your Gmail under Test users).
3. Under **Credentials**, click **Create Credentials** -> **OAuth client ID** -> **Web application**.
4. In **Authorized JavaScript origins**, add your frontend development URL (e.g. `http://localhost:3000`).
5. Copy the generated **Client ID** (ending in `.apps.googleusercontent.com`).
6. Put this Client ID in `GOOGLE_OAUTH_CLIENT_IDS` in `.env`, set `GOOGLE_AUTH_BACKEND=both`, and **restart the API server.**
*Do this on the frontend:*
Click **Continue with Google**, sign in with your Gmail account.
*You should see:*
Successful sign-in. The terminal log displays `google_sign_in_succeeded` with your account ID and no token text.
*If you don't:*
Verify that the frontend Client ID matches `GOOGLE_OAUTH_CLIENT_IDS` in `.env` and that JavaScript origins match.

---

### G10 — Production and Staging startup guards
*What this proves:* Insecure mock modes and log email senders are strictly prevented from running in production environments.
*Do this:*
```bash
APP_ENV=production GOOGLE_AUTH_BACKEND=both poetry run python -c "from camp_match.config.settings import Settings; Settings()"
APP_ENV=production EMAIL_BACKEND=log poetry run python -c "from camp_match.config.settings import Settings; Settings()"
```
*You should see:*
Both commands raise a validation error and refuse to start, stating that mock Google auth and log email backend are forbidden outside local/test environments.
*If you don't:*
Check `src/camp_match/config/settings.py` environment validator rules.
*Cleanup:*
None.

---

## Stuck?
1. **No code in dev mailbox:** Ensure `EMAIL_BACKEND=log` in `.env`.
2. **404 on `/dev/...` routes:** Ensure `APP_ENV=local` or `test`.
3. **401 `invalid_google_token` on mock token:** Mock tokens must start with `fake:` and backend must be `fake` or `both`.
4. **409 `account_exists` unexpectedly:** The test email already has a verified account; use a fresh email address.
