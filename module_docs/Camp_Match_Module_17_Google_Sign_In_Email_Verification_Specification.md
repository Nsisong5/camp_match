# CAMP MATCH — MODULE 17: GOOGLE SIGN-IN & EMAIL VERIFICATION (IDENTITY AMENDMENT)
**Specification prepared by: Claude (Technical Specification Engineer)**
**For: Gemini CLI (Implementation Agent) and Nsisong**
**Source directive: Nsisong → Claude, two requests: "continue with Google" sign-up/sign-in, and email-address verification by OTP for everyone who does not sign in with Google. Design defaults were proposed in chat and accepted by "get started"; they are recorded in Part B.**

**Prerequisite: Module 15 (Platform Reliability) is complete.** Chunk 11 adds a cleanup rule to Module 15's retention sweep, and Module 15 changes how Identity publishes `AccountDisabled`/`AccountReactivated`. Chunk 1 confirms this and **stops if Module 15 is not in the repository.**

---

## HOW THIS FILE IS USED

**Nsisong: give Gemini this whole file, once.** Gemini reads all of it, then works through the chunks **in order, one at a time**. After each chunk Gemini stops and gives a Completion Report; you check it and reply **"Proceed to Chunk N"**. Parts marked **[FOR NSISONG]** are for you (findings, decisions, frontend documentation, manual testing guide).

---

## OPERATING INSTRUCTIONS — GEMINI CLI (READ THIS FIRST)

1. **Read the entire file before doing anything.** Part C (Design Specification) is the reference every chunk points back to ("C6", "ADR-218"). Part D is your work. Part G is the source for the manual-testing document you write in Chunk 15.
2. **Your first action is Chunk 1** (inspection and scaffolding, no behavior). Write nothing else first.
3. **One chunk at a time, in order**, only after Nsisong replies "Proceed to Chunk N". Never combine, reorder, skip, or work ahead.
4. **When a chunk is complete, stop** and give a Completion Report in the standard `CURRENT_TASK.md` status-block format: what you did; files created and changed; every command run with its **real** output; each acceptance criterion marked pass or fail; any deviation or open question. Claim nothing you did not verify.
5. **If anything blocks you — a failing acceptance item, the repository contradicting this file, two parts disagreeing, a dependency that will not install without compiling, or a decision this file does not make — stop and report.** Do not choose for yourself or weaken a test.
6. The Standing Instructions in `AI_instructions/` apply throughout. Change only what a chunk names plus what the C14 touch map allows. **This module amends the Identity module: after every chunk, run Identity's entire suite and confirm it is unchanged apart from the documented additions.** Identity is the front door of the application; a regression here locks everyone out.
7. **Security rules that override everything:** never log, store, or return a raw password, a raw one-time code (except the local/test-only log email adapter, C10), a Google ID token, or an SMTP password.

---

## NOTES ON THIS DOCUMENT [FOR NSISONG]

This module changes how people get into the app, so it is written more defensively than most. Two features share one module because they interact: both change what "this email is proven to belong to this person" means.

- **Email verification (OTP):** a person who signs up with email and password gets a 6-digit code by email and **cannot log in until they enter it.**
- **Continue with Google:** the app sends Google's sign-in result to the server; the server checks it with Google's own library and signs the person in, creating an account on first use. A Google user's email is already proven, so they skip the code. **Both the real Google interface and a mock interface are supported at the same time** (ADR-220), because your frontend needs to be demonstrable and testable without a Google round-trip while still working with the real thing.

It has **16 chunks.** **Explicitly not in this module:** password reset (still deferred — ADR-017; the one-time-code machinery built here is designed so it can reuse it), Apple/Facebook sign-in, changing your email address, phone sign-in, "new sign-in" alert emails, fixing the long-standing login rate-limiting gap (ADR-020 — see Finding 5), and the production email provider (SendGrid, SES and the like) — like payment and media storage, a real provider is a later adapter behind the same port; this module ships a log adapter for testing and a standard SMTP adapter.

---

## PART A — FINDINGS AND CORRECTIONS [FOR NSISONG]

### CORRECTIONS (things I said earlier, or earlier documents said, that change)

**Correction 1 — ADR-018 ("email verification deferred") is reversed for password sign-ups.** Its stated reason was that verification "would force building an email-sending adapter that has no other use yet." That is no longer true: this module builds the email sender, and password reset will reuse it. The letter of ADR-018 is kept: **there is still no `PENDING_VERIFICATION` account status.** "Verified" is a separate fact on the account (a timestamp), so the existing `ACTIVE`/`SUSPENDED`/`DISABLED` state machine, and every module that depends on it, is untouched.

**Correction 2 — my chat proposal's "two-step Google sign-up" is dropped.** I proposed that a new Google user first receives a temporary token and then completes registration with their role and profile fields. Reading the Identity spec shows that Identity's registration collects **only email and password** — role and profile data belong to modules that act after `UserRegistered`. So Google sign-up is a **single step**, and a brand-new Google account publishes the **same `UserRegistered` event** a password sign-up does, so downstream modules behave identically.

**Correction 3 — my chat proposal said "email already has an account → always refuse."** With email verification in place there is a better and safer rule (ADR-218): an account whose email was **never proven** is *claimed* by the Google user; an account whose email **was** proven is refused with a clear "sign in the way you did before, then link Google."

**Correction 4 — `identity_accounts.password_hash` is `NOT NULL` today (Identity Chunk 6).** A Google-only account has no password, so it becomes nullable. `AuthenticateUser` must treat "no password" exactly like "no such account" so a Google-only account cannot be probed.

### FINDINGS

**Finding 1 — "unverified" accounts create a new attack, and "squatting" is it.** Once an email can be registered without being proven, someone can register a victim's email with their own password. Two defences, both built here: the victim signing in with **Google** claims that unverified account and destroys the attacker's password; and a **second registration over an unverified email replaces** the first (an unverified signup never "reserves" an address — whoever proves they hold the inbox wins).

**Finding 2 — Google's email is only trustworthy in two cases.** Google states that its `email` claim is authoritative for `@gmail.com` addresses, and for Google Workspace accounts (the `hd` claim is present) when `email_verified` is true; for any other address it recommends further verification. So this module accepts Google sign-in **only** in those cases and tells everyone else to register with email and password (ADR-214). Most student accounts will be Gmail or a school Workspace domain.

**Finding 3 — the person is identified by Google's `sub`, never by email.** A Google account's email can change; its `sub` never does. The email is used once, to decide whether a new account may be created, and never again.

**Finding 4 — there is no email sender at all today.** Sending a code needs one. This module adds an `EmailSender` port with a **log adapter** (local/test; the code is readable in the server log and at a local/test-only "dev mailbox" route, because your test accounts use made-up addresses) and a standard **SMTP adapter** (usable with any provider's SMTP gateway). A purpose-built provider adapter is a later swap.

**Finding 5 — a 6-digit code is only safe with guess limits, and Identity has no rate limiter (ADR-020).** The one-time-code endpoints get their **own** protection: the code locks after 5 wrong tries, a new code replaces the old one, resends have a 60-second cooldown and an hourly cap. **ADR-020 itself — no brute-force protection on password login — is not fixed here.** It remains a documented gap.

**Finding 6 — Termux-friendly dependencies.** Identity deliberately avoided libraries that need compiling (ADR-015). The Google check uses Google's official `google-auth` library, which verifies signatures in pure Python when `cryptography` is absent, and the SMTP adapter uses the pure-Python `aiosmtplib`. Chunk 1 verifies both install cleanly on your device and **stops if either demands compiling.**

**Finding 7 — your existing accounts must not be locked out.** Every account that exists when this module is deployed (including your seeded staff and test students) is marked verified by the migration, with source `LEGACY`. A fresh production database starts clean and verifies everyone.

**Finding 9 — your frontend needs the real Google sign-in and a mock one, at the same time.** My first design offered one verifier at a time. It is replaced (ADR-220) by a `both` mode: the real Google check is always the one used for real Google tokens, and a clearly-marked mock token (`fake:…`) is accepted **only** in `local`/`test`. The mock path runs through the **identical** use case as the real one — the only thing that differs is how the token is checked — so a green mock test exercises the same account-creation, linking and collision logic real users will hit. What the mock cannot prove is Google itself (your Google Cloud client ID, the consent screen, a real token); that is covered by one real-Google check in the manual guide (G9).

**Finding 8 — downstream modules.** `UserRegistered` has subscribers somewhere (Profile or Security, and so on). Chunk 1 maps who listens and what they do, because Google sign-ups must trigger exactly what password sign-ups do.

---

## PART B — DECISIONS [FOR NSISONG]

| ADR | Decision | Why |
|---|---|---|
| 212 | Google sign-in is an **ID-token exchange**: the app obtains a Google ID token and sends it to `POST /auth/google`; the server verifies it. No server-side redirect flow, no Google API access, nothing from Google is stored except the stable identifier | The API serves separate frontends; we need to know *who*, not to act on their Google data |
| 213 | A new table **`identity_external_identities`** keyed by `(provider, subject)`; the account is found by Google's **`sub`**, never by email | Stable key; allows a password and Google on one account |
| 214 | Google sign-**up** is accepted only when `email_verified` is true **and** the address is `@gmail.com` or the token carries `hd`; otherwise `422 google_email_not_supported` | Google's own guidance on when its email claim is authoritative |
| 215 | Verification uses `google-auth`'s `verify_oauth2_token` (signature, expiry), then **our own checks** of audience (against the configured list), issuer, subject, and optional nonce; run **off the event loop** with a timeout; **every** failure maps to one `401 invalid_google_token` | The library recommends manual audience checks when several clients are allowed; one error prevents probing |
| 216 | `password_hash` becomes **nullable**. Password login on a passwordless account behaves **exactly like an unknown email** | Google-only accounts exist; anti-enumeration preserved |
| 217 | Google sign-up is **one step**; a new account publishes the same `UserRegistered`; the response adds `is_new_account` | Correction 2 |
| 218 | **Collision rules.** (a) `sub` already linked → sign in. (b) Email matches a **verified** account → `409 account_exists`. (c) Email matches an **unverified** account → Google **claims** it: password cleared, verified, linked, open codes invalidated. (d) No match → create. Also: a **password registration over an unverified** email **replaces** the earlier unverified one | Finding 1 |
| 219 | Authenticated **link** (`POST /auth/google/link`), **unlink** (`DELETE /auth/google`), and **set password** (`POST /auth/password`, only for passwordless accounts). Unlink is refused if it would leave no way to sign in | Lets a password user add Google and a Google user add a password |
| 220 | Setting **`google_auth_backend`**: `disabled` (default) / `google` (real only) / `fake` (mock only) / **`both`** (real **and** mock together). `google` and `both` require the client-id list or startup fails; **`fake` and `both` are refused outside `local`/`test`**. In `both`, a token that starts with `fake:` goes to the mock and **every other token goes to real Google**. When `disabled` the Google routes answer `404 google_sign_in_disabled`. A public **`GET /auth/google/config`** tells the frontend which modes are on, and a `local`/`test`-only **`POST /dev/google-mock/token`** mints mock tokens for the frontend's mock button and for Swagger | Your frontend is already running and needs the authentic Google flow **and** a mock interface at the same time; production can never accept a mock token |
| 221 | **Email verification by OTP replaces ADR-018 for password sign-ups.** New facts on the account: `email_verified_at` and `email_verification_source` (`OTP`/`GOOGLE`/`LEGACY`). **Login is refused until verified.** No new account status | Correction 1 |
| 222 | **The code:** 6 digits from `secrets`, stored only as an **HMAC-SHA256** (keyed by a value derived from `jwt_secret_key`, bound to account and purpose), **10-minute** life, **one active code per account** (a new one replaces the old), **5 wrong attempts** invalidate it, single use, constant-time compare. A `purpose` column exists (only `EMAIL_VERIFICATION` today) so password reset can reuse it | Finding 5 |
| 223 | **Anti-enumeration:** `resend-verification` **always** returns the same `202`; `verify-email` returns **one** generic `422 invalid_or_expired_code` for *every* failure (unknown email, already verified, no code, expired, wrong, locked). Throttling is applied **silently** | A stranger must not learn which emails have accounts |
| 224 | New outbound port **`EmailSender`**; adapters **`LogEmailSender`** (refused outside `local`/`test`) and **`SmtpEmailSender`** (`aiosmtplib`). `email_backend` setting. A **dev mailbox** route (`local`/`test` only, `404` elsewhere) shows recent messages | Finding 4 |
| 225 | The code is emailed **directly after the commit** in the use case, **never through the event outbox** (event payloads must never carry a secret). A send failure **never fails the request**; the person can ask for a resend | Module 15's rule: payloads are ids and enums only |
| 226 | **Login on an unverified account:** after the password **and** the account status check pass, respond `403 email_not_verified` and, best-effort and throttled, send a fresh code if none is active | Only someone who holds the password can learn the account exists and is unverified |
| 227 | Accounts created or claimed through Google are **verified at creation** (`source = GOOGLE`) | Google already proved the email |
| 228 | Response additions only: register gets `email_verification_required`; `/auth/me` gets `email_verified` and `sign_in_methods`; Google sign-in gets `is_new_account` | No existing field changes |
| 229 | A product switch **`identity_email_verification_required`** (default `true`); setting it `false` is **allowed only in `local`/`test`** — startup fails otherwise | Verification must not be silently off in a real environment |
| 230 | Expired and used one-time codes are purged by **Module 15's retention sweep** (a new entry) | Operational data must not grow forever |
| 231 | **No new domain events** (no `EmailVerified`, no `GoogleLinked`); they are logged | Same stance as ADR-022: no events without a subscriber |
| 232 | **ADR-020 remains open for password login**; the new endpoints carry their own protections (ADR-222/223). Stated plainly in the docs | Honest scope |

### Decisions you made or accepted (recorded)
From my chat proposal, accepted by "get started": non-Gmail/non-Workspace Google accounts are **rejected** (ADR-214); **unlink and set-password are included** (ADR-219). Added at your request: the **real and mock Google interfaces run side by side** (ADR-220). *Frontend platforms were not specified, so the frontend notes are platform-neutral — they work for web, Android and iOS clients; the only per-platform difference is which Google client ID(s) you put in `GOOGLE_OAUTH_CLIENT_IDS`.*

### Two small things worth a glance
- **Email wording:** the verification email says *"Your Camp Match verification code is 123456. It expires in 10 minutes. If you didn't create a Camp Match account, you can ignore this email."* Change it in C10 if you want different text.
- **Production switch:** `email_backend=log` is refused in staging/production, so before real users arrive you must configure an SMTP gateway (or later a provider adapter). Until then, deployed environments cannot start with verification on.

---

## PART C — DESIGN SPECIFICATION

### C1. Rules specific to this module
1. **Identity's domain and application layers import no `google`, `requests`, `aiosmtplib`, `fastapi` or `sqlalchemy`.** Google, SMTP and the OTP primitives are adapters behind ports (import-linter extended).
2. **Existing behavior does not change** except where this file says so. In particular `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me` keep every existing field, status code and error code.
3. **Secrets never appear** in logs, events, errors, API responses, or the database in raw form (C8, C9, C10 list the one local/test exception).
4. **Anti-enumeration is a property you test**, not a hope: the failure bodies named in C6 must be **byte-identical** across their causes.
5. **System-only helpers are not routes.** The code-issuing service is internal; no router may call it directly (guard test).
6. Debug and test switches (`google_auth_backend=fake` or `both`, the mock-token minter, `email_backend=log`, `identity_email_verification_required=false`, the dev mailbox) are honored **only** when `app_env` is `local` or `test`; startup fails otherwise.
7. Concurrency safety is by database constraints and conditional updates, never check-then-write.

### C2. Layout (additions to `src/camp_match/modules/identity/`)
```
domain/        value_objects.py  (+ EmailVerificationSource, SignInMethod, OneTimeCodePurpose, ExternalProvider)
               entities.py       (UserAccount amended; + ExternalIdentity, OneTimeCode)
application/   errors.py         (+ ten errors, C4)
               ports/inbound.py  (+ seven ports; two amended responses)
               ports/outbound.py (+ ExternalIdentityRepository, OneTimeCodeRepository, OneTimeCodeService,
                                  EmailSender, GoogleIdentityVerifier)
               use_cases/        (+ verify_email, resend_email_verification, sign_in_with_google,
                                  link_google_account, unlink_google_account, set_password;
                                  email_verification_issuer.py [internal service]; register_account and
                                  authenticate_user amended; get_identity amended)
adapters/      persistence/      (+ external_identity_repository.py, one_time_code_repository.py)
               security/         (+ one_time_code_service.py)
               google/           (google_id_token_verifier.py, fake_google_verifier.py, disabled_google_verifier.py,
                                  composite_google_verifier.py)
               email/            (log_email_sender.py, smtp_email_sender.py, dev_mailbox.py)
               api/              (router additions, dev_mailbox_router.py, google_mock_router.py, schema additions)
tests/{unit,integration,api}/identity/ (additions)
```

### C3. Domain
- **Enums:** `EmailVerificationSource` (`OTP`, `GOOGLE`, `LEGACY`), `SignInMethod` (`PASSWORD`, `GOOGLE`), `OneTimeCodePurpose` (`EMAIL_VERIFICATION`), `ExternalProvider` (`GOOGLE`).
- **`UserAccount` (amended):** `password_hash: str | None`; `email_verified_at: datetime | None`; `email_verification_source: EmailVerificationSource | None` (both set or both null — enforced in the constructor). New behavior: `UserAccount.register_unverified(...)` (ACTIVE, password set, not verified); `UserAccount.register_verified(..., source)` (ACTIVE, password set, verified — for `LEGACY` when the product switch is off); `UserAccount.register_with_google(...)` (ACTIVE, **no password**, verified `GOOGLE`); `is_email_verified`; `has_password`; `mark_email_verified(now, source) -> bool` (**idempotent**: returns `False` and changes nothing if already verified); `replace_unverified_credentials(new_password_hash)` (**only legal while unverified**, else raises); `claim_for_google(now)` (**only legal while unverified**: clears the password hash, verifies with source `GOOGLE`); `set_password(hash)` (**only legal while passwordless**). `can_authenticate` is unchanged (status only).
- **`ExternalIdentity`:** `id`, `account_id`, `provider`, `subject` (str), `email_at_link` (str, display only), `linked_at`, `last_login_at`.
- **`OneTimeCode`:** `id`, `account_id`, `purpose`, `code_hash`, `issued_at`, `expires_at`, `attempts`, `max_attempts`, `consumed_at`, `invalidated_at`. Behavior: `is_active(now)` (not consumed, not invalidated, not expired); `register_failed_attempt()` → increments `attempts` and **invalidates when `attempts >= max_attempts`**, returns the remaining count; `consume(now)`; `invalidate(now)`. No randomness, no hashing in the domain.

### C4. Application errors (all `code`s stable; messages fixed)
| Error | Extends | `code` | Fixed message |
|---|---|---|---|
| `EmailNotVerified` | `ForbiddenError` | `email_not_verified` | "Your email address has not been verified." |
| `InvalidOrExpiredCode` | `ValidationError` | `invalid_or_expired_code` | "That code is invalid or has expired." |
| `InvalidGoogleToken` | `UnauthorizedError` | `invalid_google_token` | "Google sign-in could not be verified." |
| `GoogleEmailNotSupported` | `ValidationError` | `google_email_not_supported` | "This Google account's email can't be used to sign up. Please register with your email and a password." |
| `AccountExistsUseExistingMethod` | `ConflictError` | `account_exists` | "An account with this email already exists. Sign in the way you did before, then link Google from your account settings." |
| `GoogleAlreadyLinked` | `ConflictError` | `google_already_linked` | "A Google account is already linked." |
| `GoogleIdentityInUse` | `ConflictError` | `google_identity_in_use` | "That Google account is linked to a different account." |
| `LastSignInMethod` | `ConflictError` | `last_sign_in_method` | "You need at least one way to sign in. Set a password first." |
| `PasswordAlreadySet` | `ConflictError` | `password_already_set` | "This account already has a password." |
| `GoogleSignInDisabled` | `NotFoundError` | `google_sign_in_disabled` | "Google sign-in is not available." |
Plus `EmailDeliveryError` (an infrastructure error, **not** an `ApplicationError`; never reaches HTTP — C6 catches it).

### C5. Ports
**Inbound (new; `@dataclass` DTOs, `Protocol` with `execute`):**
| Port | Request | Response |
|---|---|---|
| `VerifyEmail` | `email`, `code` | `verified: bool` (always `True` on success) |
| `ResendEmailVerification` | `email` | nothing |
| `SignInWithGoogle` | `id_token`, `nonce: str \| None` | token pair fields + `is_new_account: bool` |
| `LinkGoogleAccount` | `identity_id`, `id_token`, `nonce: str \| None` | nothing |
| `UnlinkGoogleAccount` | `identity_id` | nothing |
| `SetPassword` | `identity_id`, `raw_password` | nothing |
| `GetGoogleSignInConfig` | nothing | `enabled`, `real_enabled`, `mock_enabled`, `client_ids` (only when `real_enabled`, else an empty list) |
**Amended (additive only):** `RegisterAccount`'s response gains `email_verification_required: bool`; `GetIdentityById`'s response gains `email_verified: bool` and `sign_in_methods: list[str]`.
**Outbound (new):**
- `ExternalIdentityRepository`: `get_by_subject(provider, subject)`, `get_by_account(account_id, provider)`, `add(identity)` (translates a unique violation to `GoogleIdentityInUse` or `GoogleAlreadyLinked` as appropriate), `remove(account_id, provider) -> bool`, `touch_last_login(id, now)`, `list_methods(account_id)`.
- `OneTimeCodeRepository`: `get_active(account_id, purpose)`, `add_replacing_active(code)` (invalidates any active code for that account and purpose **in the same transaction**), `update(code)`, `count_issued_since(account_id, purpose, since)`, `latest_issued_at(account_id, purpose)`, `invalidate_all(account_id, purpose, now)`.
- `OneTimeCodeService`: `generate() -> str` (6 digits), `hash(account_id, purpose, code) -> str`, `matches(account_id, purpose, code, code_hash) -> bool` (constant-time).
- `EmailSender`: `send(message: EmailMessage) -> None` (raises `EmailDeliveryError`); `EmailMessage` is `to`, `subject`, `text`.
- `GoogleIdentityVerifier`: `verify(id_token, nonce) -> VerifiedGoogleIdentity` (`subject`, `email`, `email_verified`, `hosted_domain: str | None`) — raises `InvalidGoogleToken` (or `GoogleSignInDisabled` from the disabled implementation).
`IdentityRepository.update` must persist the new `UserAccount` fields.

### C6. Behavior

**Internal service `EmailVerificationIssuer.issue_and_send(account) -> SENT | THROTTLED | SEND_FAILED`** (never raises; not an inbound port; no router may reach it):
1. Skip → `THROTTLED` if `latest_issued_at` is within `identity_otp_resend_cooldown_seconds`, or `count_issued_since(now − 1 hour) >= identity_otp_max_sends_per_hour`.
2. `code = service.generate()`; build a `OneTimeCode` (`expires_at = now + identity_otp_ttl_seconds`, `max_attempts = identity_otp_max_attempts`, `code_hash` from the service); `add_replacing_active` in a unit of work and **commit**.
3. **After the commit,** `EmailSender.send` the fixed message (C10). Any exception → log **ERROR** (`email_send_failed`, account id and error class only — **never the code**) and return `SEND_FAILED`.
4. Log INFO `verification_code_issued` (account id only).

**`RegisterAccount` (amended).** Existing steps 1–3 for a **brand-new** email are unchanged except the account is built with `register_unverified` (or `register_verified(source=LEGACY)` when `identity_email_verification_required` is `false`). New rules: if an account with that email exists and **is verified** → `IdentityAlreadyExists` exactly as today. If it exists and is **unverified** → **replace its credentials** (`replace_unverified_credentials` with the new hash), `invalidate_all` its codes, persist, and continue as below **without** a second `UserRegistered`. After the commit: if the account is unverified, call `issue_and_send` and **ignore its result** (a `SEND_FAILED` still returns `201`). The response's `email_verification_required` is `True` when the account is unverified. `UserRegistered` is published exactly once per account, as today.

**`VerifyEmail(email, code)`:** normalize the email; find the account. **All of these raise the one `InvalidOrExpiredCode`:** no such account; account already verified; no active code; the code expired; wrong code; locked. Steps: `get_active`; if not active or `not matches(...)` → `register_failed_attempt()` (**persist and commit the attempt before raising**), raise. On a match: `consume`, `account.mark_email_verified(now, OTP)`, persist both in **one** unit of work; return `verified = True`. Server log (never returned): WARNING `email_verification_failed` with a `reason` (`no_account`, `already_verified`, `no_active_code`, `expired`, `wrong_code`, `locked`) and the account id when known; INFO `email_verified`.

**`ResendEmailVerification(email)`:** if the account exists, is `ACTIVE`, and is **unverified** → `issue_and_send`; otherwise do nothing. **Always returns nothing**; the route always answers the same `202` (C11). INFO log with the reason.

**`AuthenticateUser` (amended).** After the account is found: **if `password_hash is None`, behave exactly as for "account not found"** (WARNING `login_failed` reason `account_has_no_password`; the identical `InvalidCredentials`). Password verification and the status check are unchanged and run first. **New, after the status check:** if verification is required and the account is not verified → log WARNING `login_blocked_unverified` (account id), call `issue_and_send` (**swallow everything**), and raise `EmailNotVerified`. Only then issue tokens.

**`SignInWithGoogle(id_token, nonce)`:**
1. `verifier.verify` → `InvalidGoogleToken` / `GoogleSignInDisabled` propagate. **The token is never logged or stored.**
2. `get_by_subject(GOOGLE, sub)`: **found** → load the account; if `not can_authenticate` → `AccountSuspended`/`AccountDisabled` (as login does, with a WARNING log); else `touch_last_login`, issue tokens, return `is_new_account = False`. An account found through a Google link is by definition verified; no verification check applies.
3. **Not found:** require `email_verified` **and** (`email` ends with `@gmail.com` **or** `hosted_domain` is not `None`), else `GoogleEmailNotSupported`.
4. `existing = get_by_email(EmailAddress(email))`:
   - **none** → `register_with_google`; persist the account **and** its `ExternalIdentity` in **one** unit of work; publish `UserRegistered` (the same event and fields as `RegisterAccount`); issue tokens; `is_new_account = True`. **Race:** if a unique violation occurs on email or on `(provider, subject)`, **repeat steps 2–4 once**; a second failure is reported, not retried again.
   - **exists and verified** → INFO log, `AccountExistsUseExistingMethod`.
   - **exists and unverified** → if its status is not `ACTIVE`, raise the matching suspended/disabled error and change nothing; otherwise `claim_for_google`, add the `ExternalIdentity`, `invalidate_all` codes, persist in one unit of work, WARNING log `unverified_account_claimed_by_google` (account id), issue tokens, return `is_new_account = True` (this is the person's first real session).
5. INFO log `google_sign_in_succeeded` (account id, `is_new_account`).

**`LinkGoogleAccount`:** verify the token; load the account (`IdentityNotFound`); if it already has a Google link → `GoogleAlreadyLinked`; if the `sub` is linked to any account → `GoogleIdentityInUse`; add the link with `email_at_link`. **No email rules apply** (the link key is `sub`). A unique violation in a race is translated to the same two errors.
**`UnlinkGoogleAccount`:** no link → succeed as a no-op; account has no password → `LastSignInMethod`; else remove.
**`SetPassword`:** account must be passwordless else `PasswordAlreadySet`; hash with the existing `PasswordHasher`; persist. (Length is enforced at the API boundary, 8–128.)
**`GetIdentityById` (amended):** adds `email_verified` and `sign_in_methods` (`PASSWORD` if it has a password, `GOOGLE` if linked).

### C7. Database
**`identity_accounts` (alter):** `password_hash` → **nullable**; add `email_verified_at` (timestamptz, null) and `email_verification_source` (text, null, `CHECK IN ('OTP','GOOGLE','LEGACY')`), plus `CHECK ((email_verified_at IS NULL) = (email_verification_source IS NULL))`. **Backfill every existing row:** `email_verified_at = created_at`, `email_verification_source = 'LEGACY'`. **Read the migration before applying.** `downgrade` drops the two columns and restores `NOT NULL` — **it must refuse (raise a clear error) if any passwordless account exists.**

**`identity_external_identities` (new):** `id` UUID PK; `account_id` UUID not null, **FK → `identity_accounts.id`**, indexed; `provider` text not null `CHECK IN ('GOOGLE')`; `subject` text not null; `email_at_link` text not null; `linked_at` timestamptz not null; `last_login_at` timestamptz null; **unique `(provider, subject)`**; **unique `(account_id, provider)`**.

**`identity_one_time_codes` (new):** `id` UUID PK; `account_id` UUID not null, **FK → `identity_accounts.id`**; `purpose` text not null `CHECK IN ('EMAIL_VERIFICATION')`; `code_hash` text not null; `issued_at`, `expires_at` timestamptz not null; `attempts` int not null default 0; `max_attempts` int not null; `consumed_at`, `invalidated_at` timestamptz null; **partial unique index on `(account_id, purpose) WHERE consumed_at IS NULL AND invalidated_at IS NULL`** (at most one active code); index `(account_id, purpose, issued_at)`.

### C8. The one-time code (`adapters/security/one_time_code_service.py`)
`generate()`: `f"{secrets.randbelow(1_000_000):06d}"`. `hash`: **HMAC-SHA256** over `f"{account_id}:{purpose}:{code}"` with a key derived as `HMAC-SHA256(jwt_secret_key, b"camp_match.identity.one_time_code.v1")` (no new secret to manage; domain-separated from JWT signing); return hex. `matches`: recompute and compare with `hmac.compare_digest`. The raw code exists only in memory between `generate` and the email send.

### C9. Google verification (`adapters/google/`)
`GoogleIdTokenVerifier` calls `google.oauth2.id_token.verify_oauth2_token(token, google.auth.transport.requests.Request())` **without** the library's audience argument, inside `asyncio.to_thread` under `asyncio.wait_for(google_verify_timeout_seconds)`; then **checks itself**: `aud` is in `google_oauth_client_ids`; `iss` is `accounts.google.com` or `https://accounts.google.com`; `sub` is a non-empty string; `email` is a string; and, if a `nonce` was supplied (or `google_require_nonce` is true and none was), the token's `nonce` equals it. Any exception of any kind (bad signature, expiry, network, timeout, parsing, a failed check above) → log WARNING (`google_token_rejected`, **exception class only**) and raise `InvalidGoogleToken`. `FakeGoogleVerifier` (local/test only) accepts `fake:<sub>:<email>` with optional `:unverified` and `:hd=<domain>` segments (for example `fake:sub-ada:ada.test@gmail.com`, `fake:sub-x:x@school.edu:hd=school.edu`, `fake:sub-y:y@yahoo.com:unverified`); anything else → `InvalidGoogleToken`. `DisabledGoogleVerifier` always raises `GoogleSignInDisabled`. **`CompositeGoogleVerifier(real, fake)`** (used for `both`): a token that starts with `fake:` is verified by the fake, **any other token by the real verifier** (a real Google ID token is a JWT and always starts with `eyJ`, so the two can never be confused). Composition picks the verifier from `google_auth_backend`: `disabled` → Disabled, `google` → Real, `fake` → Fake, `both` → Composite.

**`GetGoogleSignInConfig`** reports `real_enabled` (backend is `google` or `both`), `mock_enabled` (backend is `fake` or `both`), `enabled` (either), and `client_ids` (the configured list, **only** when `real_enabled`). Client IDs are public values, not secrets; no other setting is ever exposed.

**The mock-token minter** (`POST /api/v1/dev/google-mock/token`, mounted **only** when `app_env` is `local`/`test` **and** `mock_enabled`; absent — `404` — otherwise): body `{email, email_verified?: bool (default true), hosted_domain?: str | null}`; returns `{"id_token": "fake:<sub>:<email>[:unverified][:hd=<domain>]"}`, where `sub` is deterministic from the email (`mock-` followed by the first 20 hex characters of the SHA-256 of the lowercased email) so the same mock user always gets the same account. It exists so the frontend's mock button, Swagger, and the manual guide can produce mock tokens without hand-typing them. It mints nothing the fake verifier would not already accept.

### C10. Email (`adapters/email/`)
**The fixed message:** subject `Your Camp Match verification code`; body `Your Camp Match verification code is {code}.` blank line `It expires in {minutes} minutes. If you didn't create a Camp Match account, you can ignore this email.`
- `LogEmailSender` (**refused outside `local`/`test`**): logs INFO `dev_email_sent` with `to`, `subject` and the body — **this is the single place a raw code may be logged** — and appends the message to the in-memory `DevMailbox` ring buffer (last 50 messages overall).
- `GET /api/v1/dev/mailbox?to=<email>` (mounted **only** when `app_env` is `local`/`test`; absent — `404` — otherwise): returns that address's last 10 messages, newest first (`to`, `subject`, `text`, `sent_at`).
- `SmtpEmailSender` (`aiosmtplib`): builds a standard `email.message.EmailMessage`; connects to `smtp_host:smtp_port`, STARTTLS when `smtp_use_starttls` is true, logs in with `smtp_username`/`smtp_password` when set, honors `smtp_timeout_seconds`; any failure → `EmailDeliveryError`. **Never logs the body, the password, or the recipient's code.**

### C11. API
| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| POST | `/api/v1/auth/register` | none | `201` | body unchanged; response gains `email_verification_required` |
| POST | `/api/v1/auth/login` | none | `200` | unchanged; new `403 email_not_verified` |
| POST | `/api/v1/auth/verify-email` | none | `200` `{"verified": true}` | `{email, code}`; `code` must match `^\d{6}$` (else `422 validation_error`); every failure `422 invalid_or_expired_code` |
| POST | `/api/v1/auth/resend-verification` | none | `202` | `{email}`; **always** `{"message": "If this email needs verification, a new code has been sent."}` |
| POST | `/api/v1/auth/google` | none | `200` | `{id_token, nonce?}` → tokens plus `is_new_account` |
| POST | `/api/v1/auth/google/link` | Bearer | `200` `{"linked": true}` | `{id_token, nonce?}` |
| DELETE | `/api/v1/auth/google` | Bearer | `204` | |
| POST | `/api/v1/auth/password` | Bearer | `204` | `{new_password}` (8–128) |
| GET | `/api/v1/auth/me` | Bearer | `200` | gains `email_verified`, `sign_in_methods` |
| GET | `/api/v1/auth/google/config` | none | `200` | `{enabled, real_enabled, mock_enabled, client_ids}` — the frontend uses it to decide which buttons to show |
| POST | `/api/v1/dev/google-mock/token` | none | `200` | `local`/`test` **and** mock mode only; mints a mock token (C9) |
| GET | `/api/v1/dev/mailbox` | none | `200` | `local`/`test` only |
All request models `extra="forbid"`; `id_token` 20–4096 characters; `nonce` ≤ 256. Errors use the existing `{"error": {"code", "message"}}` shape with the C4 codes.

### C12. Settings (`config/settings.py`, `.env.example`; invalid values fail startup)
| Setting | Default | Rules |
|---|---|---|
| `identity_email_verification_required` | `true` | `false` only when `app_env` is `local`/`test` |
| `identity_otp_ttl_seconds` | 600 | ≥ 30 |
| `identity_otp_max_attempts` | 5 | ≥ 1 |
| `identity_otp_resend_cooldown_seconds` | 60 | ≥ 0 |
| `identity_otp_max_sends_per_hour` | 5 | ≥ 1 |
| `google_auth_backend` | `disabled` | `Literal["disabled","google","fake","both"]`; `fake` and `both` only in `local`/`test` |
| `google_oauth_client_ids` | empty | comma-separated; **required (non-empty) when backend is `google` or `both`** |
| `google_require_nonce` | `false` | |
| `google_verify_timeout_seconds` | 5 | ≥ 1 |
| `email_backend` | `log` | `Literal["log","smtp"]`; `log` only in `local`/`test`; `smtp` requires host and from-address |
| `smtp_host`, `smtp_port` (587), `smtp_username`, `smtp_password`, `smtp_use_starttls` (true), `smtp_from_address`, `smtp_timeout_seconds` (10) | | `smtp_password` is a secret: never logged, never echoed |
| `retention_identity_codes_days` | 7 | used by Module 15's sweep |
`.env.example` gets matching, commented entries.

### C13. Dependencies (added once, in Chunk 1 after verification)
`google-auth` and `requests` (runtime); `aiosmtplib` (runtime); `aiosmtpd` (**dev only**, for the SMTP adapter test). **All must install without compiling on Termux; stop and report if any does not.** No other new libraries.

### C14. Touch map — the only files outside Identity's own folders this module changes
`config/settings.py`; `.env.example`; `pyproject.toml`/lockfile; `app.py` (mount the dev mailbox and Google-mock routers, local/test only); Alembic migrations; import-linter contracts; **Module 15's** `RunRetentionSweep` and purge wiring (one entry, Chunk 11). **Not touched:** every other business module. Downstream modules that subscribe to `UserRegistered` are **not changed**; Chunk 1 proves they receive Google sign-ups identically.

---

## PART D — CHUNKED IMPLEMENTATION

Every chunk ends the same way: run **Identity's entire suite** and the full suite of every other module the chunk touched, `poetry run ruff check .`, `poetry run ruff format --check .`, `poetry run mypy src`, and `poetry run lint-imports`, and report the real results. Identity paths are under `src/camp_match/modules/identity/`.

---

### CHUNK 1 — INSPECTION, DEPENDENCY CHECK & SCAFFOLDING
**[FOR YOU — GEMINI CLI]**

**Objective:** verify every assumption in this file against the repository, and prove the new dependencies install on this device. **Write no behavior.**

**Do:**
1. **Prerequisite:** confirm Module 15 exists (`modules/platform_runtime/`, `RunRetentionSweep`, the shared outbox). **If it does not, stop and report.**
2. **Dependency check (C13):** run `poetry add google-auth requests aiosmtplib` and `poetry add --group dev aiosmtpd`. Report whether **each** installed without compiling anything (watch for `cryptography`, `cffi`, `rust` or `gcc` in the output). **If any needs compilation, revert the change and stop.** Also run a one-line import of `google.oauth2.id_token` and `aiosmtplib`.
3. Create the empty scaffolding for the new files in C2 (each with a one-line docstring) and the three test folders' new subfolders.

**Inspect and report, with paths and exact signatures:**
- Identity as it is **now**: `UserAccount`, the seven existing use cases and ports, `IdentityRepository`, `ScryptPasswordHasher`, `JwtAuthenticationSessionAdapter`, the five routes and their schemas, the migrations applied, and any change made to Identity since its original spec (Module 13/15 touched it for `AccountDisabled`/`AccountReactivated` publishing).
- **Who subscribes to `UserRegistered`** and what each subscriber does (Profile? Security? Notification?). Confirm a second `UserRegistered` for the same account would be harmless or say it is not — this matters for C6's "no second event when replacing an unverified registration."
- **Who calls `GetIdentityById`, `RegisterAccount`, `AuthenticateUser`** from other modules (their request/response shapes must stay valid).
- How `get_current_identity_id` (or the Security-module equivalent) protects routes; how `/auth/me` is built.
- **The frontend's current integration:** the CORS configuration (`allow_origins`), and how the running frontend calls `/auth/login` today — the new `403 email_not_verified` must not break it silently; report any assumption the frontend makes.
- Where debug-only routes (the mock payment controls) are mounted and guarded by `app_env`; copy that pattern for the dev mailbox and Google-mock routers.
- The structlog configuration (so Chunk 6 and 7 never leak a secret) and how test log capture works (Identity's existing security test).

**Output:** a **mapping table** (assumption → what the repository has) and **every difference**.

**Acceptance criteria:** dependencies installed and importable (or you stopped); skeleton imports; Identity's and the full suite unchanged; `lint-imports` clean. **Stop after this chunk.**

---

### CHUNK 2 — SETTINGS & STARTUP RULES
**[FOR YOU — GEMINI CLI]**

Implement every setting in **C12** (typed, defaulted, validated, in `.env.example` with comments) and the startup-time rules: `identity_email_verification_required=false` only in `local`/`test`; `email_backend=log` only in `local`/`test`; `email_backend=smtp` requires host and from-address; `google_auth_backend` `fake`/`both` only in `local`/`test`; `google`/`both` require a non-empty `google_oauth_client_ids` (parsed from a comma-separated string into a cleaned list: trimmed, empties dropped, duplicates removed); `smtp_password` is a secret that never appears in `repr`, logs, or errors.

**Tests:** every default; every rule above fails startup with a clear message in the wrong environment and passes in the right one (parametrize over `app_env` in `local`, `test`, `staging`, `production`); the client-id parser; the secret does not appear in `repr(settings)` or in a startup error.

**Acceptance criteria:** new tests pass; the existing suite is unchanged.

---

### CHUNK 3 — DOMAIN
**[FOR YOU — GEMINI CLI]**

Implement **C3**: the four enums; the amended `UserAccount` (nullable password, verification facts, the constructors and transition methods exactly as listed, the both-or-neither invariant); `ExternalIdentity`; `OneTimeCode`. Pure Python: no hashing, no randomness, no framework. **Every existing domain test must pass unmodified.**

**Tests:** `register_unverified` / `register_verified` / `register_with_google` produce the right state and each invariant; `mark_email_verified` is idempotent and returns `False` the second time without changing the original timestamp or source; `replace_unverified_credentials` and `claim_for_google` raise on a verified account and work on an unverified one (`claim_for_google` clears the password hash and sets source `GOOGLE`); `set_password` raises when a password exists; verification facts set one without the other raise; `OneTimeCode.is_active` across active, consumed, invalidated, and expired (use a `FixedClock` and the exact boundary instant); `register_failed_attempt` counts, invalidates at `max_attempts`, and returns the right remaining count; `consume` and `invalidate` behave and are idempotent.

**Acceptance criteria:** new and existing domain tests pass; the domain imports only the shared kernel and the standard library.

---

### CHUNK 4 — APPLICATION ERRORS & PORTS
**[FOR YOU — GEMINI CLI]**

Implement **C4** (ten errors with the exact `code`s, parents and fixed messages; `EmailDeliveryError` as a plain infrastructure error) and **C5** (all new inbound and outbound ports, the two additive response changes, `EmailMessage`, `VerifiedGoogleIdentity`). Port methods are `...`. **No existing field of any existing port changes.**

**Tests:** each error is an instance of its stated parent and carries its exact `code` and message; `EmailDeliveryError` is **not** an `ApplicationError`; `mypy` is clean on the ports; the amended response dataclasses still construct with the old arguments (the new fields have defaults or are supplied by every caller — report which).

**Acceptance criteria:** new tests pass; Identity's and the full suite unchanged.

---

### CHUNK 5 — PERSISTENCE & MIGRATION
**[FOR YOU — GEMINI CLI]**

Implement **C7**: the three schema changes in **one** migration (**read the generated file before applying; autogenerate is a draft**), including the backfill and the guarded `downgrade`; the ORM changes; `SqlAlchemyExternalIdentityRepository` and `SqlAlchemyOneTimeCodeRepository`; extend `SqlAlchemyIdentityRepository` to persist the new account fields (unique-violation translation unchanged).

**Tests (integration, real DB):** the backfill marks every pre-existing row verified with source `LEGACY` and `email_verified_at = created_at` (seed rows, run the migration step, assert); a passwordless account round-trips; the both-or-neither `CHECK` rejects a row with one set; the `(provider, subject)` and `(account_id, provider)` unique constraints each reject a duplicate and are **translated** (`GoogleIdentityInUse`, `GoogleAlreadyLinked`), never a raw database error; **only one active code per `(account_id, purpose)`**: `add_replacing_active` invalidates the previous one and the partial unique index rejects a direct second insert; `count_issued_since` and `latest_issued_at` correct; `downgrade` **refuses** while a passwordless account exists and succeeds otherwise; `upgrade → downgrade → upgrade` is clean on an empty database.

**Acceptance criteria:** tests pass; the migration applies cleanly; nothing outside `adapters/persistence/` imports SQLAlchemy.

---

### CHUNK 6 — ONE-TIME-CODE SERVICE & EMAIL ADAPTERS
**[FOR YOU — GEMINI CLI]**

Implement **C8** (`one_time_code_service.py`) and **C10**: `LogEmailSender`, `DevMailbox`, the dev-mailbox router (mounted by the same `app_env` guard pattern as the mock payment controls), `SmtpEmailSender`, and composition choosing by `email_backend`.

**Tests:** codes are always exactly six digits and include leading zeros (force `randbelow` to return 7 and assert `"000007"`); 10,000 generated codes are not all equal (sanity, not statistics); `hash` differs across account, purpose and code, and equals itself for the same inputs; `matches` is true only for the right triple; the raw code is never in the hash; `LogEmailSender` records to the mailbox (ring buffer keeps the last 50 and the per-address query returns at most 10, newest first) and **refuses to construct** outside `local`/`test`; the dev-mailbox route returns `404` when `app_env` is `staging`/`production`; **`SmtpEmailSender` is tested against an in-process `aiosmtpd` server:** it delivers the exact subject and body, uses STARTTLS when configured (assert the negotiation), authenticates when credentials are set, times out cleanly (a server that never answers → `EmailDeliveryError` within the timeout), raises `EmailDeliveryError` for a refused connection and a rejected recipient, and **never** logs the body, the password, or the code (capture logs and assert).

**Acceptance criteria:** new tests pass; no new import leaks into Identity's domain or application layers.

---

### CHUNK 7 — GOOGLE VERIFIER ADAPTERS, CONFIG & MOCK MINTER
**[FOR YOU — GEMINI CLI]**

Implement **C9**: `GoogleIdTokenVerifier` (real), `FakeGoogleVerifier`, `DisabledGoogleVerifier`, `CompositeGoogleVerifier`, composition by `google_auth_backend`, the `GetGoogleSignInConfig` use case, and the mock-token minter router (guarded by `app_env` **and** mock mode).

**Tests — the real verifier.** Do **not** call Google. Generate a throwaway RSA key pair in the test, sign tokens with it, and make `verify_oauth2_token` trust that key by patching the certificate fetch for the test (`google.oauth2.id_token`'s certificate retrieval; report exactly what you patched). Cases, **each its own test:** a valid token → the right `subject`, `email`, `email_verified`, `hosted_domain`; **wrong audience** (not in the list) → `InvalidGoogleToken`; a token for a *different* configured client ID → accepted; wrong issuer; expired; signed by a different key; missing `sub`; missing `email`; malformed string; nonce supplied and matching → ok; nonce supplied and not matching → rejected; `google_require_nonce` true and none supplied → rejected; the certificate fetch raising a network error → `InvalidGoogleToken`; the verification exceeding `google_verify_timeout_seconds` → `InvalidGoogleToken` and the event loop is **not blocked** (assert another task makes progress during the call); **the token string never appears in any log line** and the logged exception is a class name only.
**Fake verifier:** every documented format, `:unverified`, `:hd=…`, and a malformed string → `InvalidGoogleToken`. **Composite:** a `fake:` token never reaches the real verifier (spy), a non-`fake:` token never reaches the fake (spy), and a real-shaped token starting `eyJ` is routed to the real one. **Disabled:** raises `GoogleSignInDisabled`. **Config:** correct flags and `client_ids` for each of the four backends (empty list unless real is enabled). **Minter:** returns a token the fake verifier accepts; `sub` is deterministic and case-insensitive on the email; `email_verified=false` and `hosted_domain` produce the right suffixes; `404` outside `local`/`test` and when mock mode is off; it **cannot** mint anything the fake would reject.

**Acceptance criteria:** new tests pass; the real verifier's tests make **zero** network calls (assert by blocking sockets in the test).

---

### CHUNK 8 — USE CASES A: EMAIL VERIFICATION
**[FOR YOU — GEMINI CLI]**

Implement **C6** for email verification: `EmailVerificationIssuer`, the amended `RegisterAccount` and `AuthenticateUser`, `VerifyEmail`, `ResendEmailVerification`. Built only against ports; shared fakes extended in `tests/support/identity_fakes.py` (an in-memory one-time-code repository honoring the one-active-code rule, a recording `EmailSender` fake with a switchable failure, a fake `OneTimeCodeService`).

**Tests (fakes only, `FixedClock`):**
*Register:* a new email → account unverified, code issued, email sent once, `UserRegistered` published once, `email_verification_required = True`; with the product switch off → account verified `LEGACY`, **no** email, `email_verification_required = False`; an existing **verified** email → `IdentityAlreadyExists`; an existing **unverified** email → password replaced (the old password no longer works, the new one does), old codes invalidated, a new code sent, **no second `UserRegistered`**; **email sending fails → still returns the registration response**, the failure is logged at ERROR with no code in the log; the response and the log never contain the code.
*Issuer:* cooldown (a second call within 60 s → `THROTTLED`, no email); hourly cap (the sixth in an hour → `THROTTLED`); after the cooldown a new code replaces the old (the old no longer verifies); `SEND_FAILED` on a sender error, the code row still stored.
*Verify:* the right code → account verified (source `OTP`), code consumed, **both in one unit of work** (assert a failure in persisting the account leaves the code unconsumed); a wrong code → attempts+1 and `InvalidOrExpiredCode`; **the attempt is persisted even though the call raises**; five wrong codes → locked, and the *correct* code afterwards still fails; an expired code; no active code; unknown email; already-verified account — **all raise the identical `InvalidOrExpiredCode` (same type, same message)**; a used code cannot be reused.
*Resend:* an unverified active account gets a code; an unknown email, a verified account, and a suspended/disabled account get **nothing** and the call returns normally for all of them (the use case cannot distinguish them to its caller).
*Authenticate:* a verified account logs in as before; an unverified account with the **correct** password → `EmailNotVerified` and a code is sent (throttled on repeat); an unverified account with a **wrong** password → the ordinary `InvalidCredentials` (the unverified status is **not** revealed); a **passwordless** account with any password → `InvalidCredentials` identical to the unknown-email case; a suspended-and-unverified account → `AccountSuspended` (status is checked first); an email-send failure during that login still raises `EmailNotVerified`, not a server error.

**Acceptance criteria:** new tests pass using fakes only; Identity's existing use-case tests pass unmodified.

---

### CHUNK 9 — USE CASES B: GOOGLE
**[FOR YOU — GEMINI CLI]**

Implement **C6** for Google: `SignInWithGoogle`, `LinkGoogleAccount`, `UnlinkGoogleAccount`, `SetPassword`, and the amended `GetIdentityById`. Fakes extended (an in-memory `ExternalIdentityRepository`, a scriptable fake `GoogleIdentityVerifier`).

**Tests (fakes only):**
*Sign-in, found by `sub`:* returns tokens, `is_new_account = False`, `last_login_at` touched; **the same `sub` with a different email at Google still signs into the same account**; a suspended or disabled account → the specific `AccountSuspended`/`AccountDisabled` and no tokens.
*New account:* `register_with_google` account (ACTIVE, no password, verified `GOOGLE`), the link stored, **both in one unit of work**, **`UserRegistered` published once with the same fields a password sign-up publishes** (compare the two events field for field), `is_new_account = True`; `@gmail.com` accepted; a Workspace address with `hosted_domain` accepted; `email_verified = false` → `GoogleEmailNotSupported`; a non-Gmail address with no `hosted_domain` → `GoogleEmailNotSupported`; `gmail.com` match is on the domain exactly (`x@notgmail.com` and `x@gmail.com.evil.test` are rejected).
*Collisions:* an existing **verified** account with that email → `AccountExistsUseExistingMethod` and **nothing** changes (no link, password intact); an existing **unverified** account → **claimed**: password cleared (the old password no longer logs in), verified `GOOGLE`, link stored, open codes invalidated, tokens issued, `is_new_account = True`, WARNING log; an unverified account that is `SUSPENDED` → `AccountSuspended` and **not** claimed.
*Races (fakes simulating the unique-violation):* a violation on `(provider, subject)` or email during creation → the lookup is repeated **once** and resolves (sign in, or `AccountExists`); a second consecutive failure is surfaced, not looped.
*Link/unlink/password:* link succeeds; a second link on the same account → `GoogleAlreadyLinked`; a `sub` already on another account → `GoogleIdentityInUse`; linking needs no email match; unlink with a password present succeeds; unlink with no password → `LastSignInMethod`; unlink with no link → success no-op; `SetPassword` on a passwordless account → hashes and persists; on an account with a password → `PasswordAlreadySet`; after `SetPassword` the account can log in with email+password **and** unlink Google.
*Identity read:* `sign_in_methods` and `email_verified` correct for password-only, Google-only, both, and legacy accounts.
*Safety:* the token string is never logged and never stored (capture logs).

**Acceptance criteria:** new tests pass using fakes only; existing tests unmodified.

---

### CHUNK 10 — API ADAPTER
**[FOR YOU — GEMINI CLI]**

Implement **C11**: schemas (`extra="forbid"`; descriptions and examples on every field so Swagger shows a useful body, never `additionalProp1`), the new routes, the additive changes to register/`me`, composition for every new use case and adapter, and mounting of the dev routers by the `app_env` guard. No business logic in routers. Error mapping uses the existing platform handlers (the C4 categories already map).

**Tests (API):** every route's success shape and status; `verify-email` with a malformed code (`12345`, `1234567`, `abcdef`) → `422 validation_error`; `resend-verification` returns the **same status and byte-identical body** for an unknown email, a verified account, and an unverified account; `verify-email` returns a **byte-identical** `422 invalid_or_expired_code` body for every cause in C6; `login` with an unverified account → `403 email_not_verified`; `/auth/google` with each backend (`disabled` → `404 google_sign_in_disabled`; `fake` and `both` accept mock tokens; `both` routes a non-`fake:` token to the real verifier and rejects garbage with `401 invalid_google_token`); `/auth/google/config` for each of the four backends; the minter route exists only in `local`/`test` with mock mode on; link/unlink/password need a Bearer token (`401` without one); unknown request fields → `422`; **every existing Identity API test passes unmodified**.

**Acceptance criteria:** new tests pass; the full suite unchanged; `uvicorn` starts and Swagger shows the new routes with example bodies.

---

### CHUNK 11 — RETENTION HOOK (MODULE 15)
**[FOR YOU — GEMINI CLI]**

Add one entry to Module 15's retention sweep (its C13 table): purge `identity_one_time_codes` rows that are consumed, invalidated or expired **and** older than `retention_identity_codes_days`, in batches, **never** touching an active code. Implement it as a purge use case in Identity that the sweep calls (Module 15's pattern — each module owns its purge). Update Module 15's purge-target guard test so the list is asserted **exactly** with the new entry.

**Tests:** old consumed/invalidated/expired rows are purged; an active (unexpired, unconsumed) code is never purged at any age of the row; younger rows are kept; batching; a second run is a no-op; the guard test lists exactly the Module 15 targets plus this one and still contains no audit, booking, payment or account table.

**Acceptance criteria:** Module 15's retention tests and Identity's suites pass.

---

### CHUNK 12 — FULL TESTING A: EMAIL VERIFICATION END TO END
**[FOR YOU — GEMINI CLI]**

Write `tests/api/identity/test_email_verification_flow.py` and `test_email_verification_security.py` (real HTTP, real database, `email_backend=log`, the dev mailbox to read codes).

**Flow:** register → login is `403 email_not_verified` → read the code from the dev mailbox → `verify-email` → login succeeds → `/auth/me` shows `email_verified: true`. **Wrong code then right code** works. **Expiry** (a short TTL setting and a `FixedClock`). **Lockout:** five wrong codes, then the right one fails, then resend, then the new code works. **Resend:** cooldown and hourly cap return the **same `202` body** every time and send nothing extra. **Squatting:** register `victim@x.test` with password A (never verified); register the same email with password B → login with A fails, B is accepted after verification, and A's earlier code is dead. **Legacy:** an account created before the migration (seed it) logs in without verification.

**Security:** `verify-email` and `resend-verification` bodies are **byte-identical** across unknown/verified/unverified emails; the raw code never appears in any HTTP response, any error body, or — with `email_backend=smtp` against the in-process server — any log line; the database holds only a hash (assert the stored value is not the code); a code issued for one account cannot verify another (same code value, different account); concurrency, **three consecutive runs each:** two `verify-email` calls with the same correct code at the same time → exactly one succeeds and the account is verified once; ten simultaneous wrong guesses → the attempt counter never exceeds `max_attempts` and the code is locked; two simultaneous resends → exactly one new active code.

**Acceptance criteria:** all pass three consecutive times; Identity's entire suite and the full suite pass.

---

### CHUNK 13 — FULL TESTING B: GOOGLE END TO END
**[FOR YOU — GEMINI CLI]**

Write `tests/api/identity/test_google_flow.py` and `test_google_security.py` (real HTTP, real database, `google_auth_backend=both` with a stubbed real-verifier certificate source as in Chunk 7).

**Flow (mock path, through the minter):** mint a token → `POST /auth/google` → `201`-equivalent `200` with `is_new_account: true` → `/auth/me` shows `email_verified: true` and `sign_in_methods: ["GOOGLE"]` → refresh works → logout works → sign in again → `is_new_account: false`, **one** account in the table. **Real-path flow with a locally signed token** (the Chunk 7 technique): the identical journey succeeds, proving the real verifier plugs into the same use case. **Collision:** a password account (verified) then Google with the same email → `409 account_exists`; the user logs in with the password, `POST /auth/google/link`, then signs in with Google and gets the **same** account id. **Claim:** an unverified squatter then Google → claimed; the squatter's password no longer works. **Set password and unlink.** **Disabled:** disable the account (Admin's audited route or the use case) → Google sign-in `403 account_disabled`; reactivate → works. **Unsupported email:** a Yahoo-style address and an `unverified` token → `422 google_email_not_supported`. **Downstream:** the same subscribers receive `UserRegistered` for a Google sign-up as for a password sign-up (use what Chunk 1 mapped).

**Security:** every invalid-token cause (garbage, wrong audience, wrong issuer, expired, bad signature, missing claims) returns a **byte-identical** `401 invalid_google_token`; a `fake:` token is **rejected** when `google_auth_backend=google`, and **no mock route or fake acceptance exists** when `app_env=production` (parametrize `app_env`); the token string never appears in responses or logs; a Google-only account cannot log in with email+password (identical to the unknown-email response); the mock minter cannot produce a token that would sign in an account the minter's email did not name; **concurrency, three consecutive runs:** ten simultaneous first-time sign-ins with one `sub` → exactly one account and ten successful responses; a password registration and a Google sign-in for the same email at the same instant → one account, with both responses consistent with the collision rules.

**Acceptance criteria:** all pass three consecutive times; the full suite passes.

---

### CHUNK 14 — ARCHITECTURE & REGRESSION SWEEP
**[FOR YOU — GEMINI CLI]**

Extend the import-linter contracts: Identity's `domain` and `application` import none of `google`, `requests`, `aiosmtplib`, `fastapi`, `sqlalchemy`; only `adapters/google/` may import `google`/`requests`; only `adapters/email/` may import `aiosmtplib`. Add the guard that no router imports `EmailVerificationIssuer`. Write the regression test that **every field, status code and error code of the five original endpoints is unchanged** (snapshot their OpenAPI schemas from before this module and assert only additive differences). Confirm Module 15's request-model guard (`extra="forbid"`) passes for every new model. Run the entire project suite three times.

**Acceptance criteria:** all pass; import-linter clean; the OpenAPI diff for the original endpoints is additive only (attach it).

---

### CHUNK 15 — DOCUMENTATION, MANUAL GUIDE & AI STATE
**[FOR YOU — GEMINI CLI]**

Update `docs/modules/identity.md`: the new sign-in methods, the verification model, the three tables, the OTP and Google designs, the corrected sentences from Part A (ADR-018 reversed in part; ADR-020 still open, **stated plainly**), the known limitations (no password reset, no email change, no Apple sign-in, no new-sign-in alerts, no production email provider adapter, no login rate limiting), and the extension points (password reset reusing `identity_one_time_codes` and `EmailSender`; an Apple or Microsoft provider reusing `identity_external_identities`). Update the project-wide frontend API document from **Part F**; update every `AI_state/` file the Standing Instructions require; append ADR-212 … ADR-232 to `DECISIONS.md`; update `.env.example` and the README (how to turn on verification, mock Google, and real Google, and the Google Cloud setup from Part G, G9).

**The manual testing guide** is `docs/manual_testing/module_17.md`, written from **Part G** under these rules (the reader is not a backend specialist): (1) a short "Start here" with the test accounts and the two copy-paste helper functions, each explained in one line; (2) every test uses the same five headings — *What this proves (one plain sentence)* · *Do this* · *You should see* · *If you don't* · *Cleanup*; (3) every step is a **runnable command** with a short example of real output; (4) no jargon without a one-line explanation; (5) commands that need a restart say so in bold; (6) a "Stuck?" section; (7) **only commands you actually ran** — anything in Part G marked *(Gemini verifies)* must be confirmed or corrected. G9 (real Google) is the one test you cannot run yourself in this environment: write it as exact instructions for Nsisong and mark it clearly **"run by Nsisong with the real frontend."**

**Acceptance criteria:** every document exists and is accurate; no document claims a guarantee the tests do not prove; every command in the guide (except G9) was run and the real outputs are in the report.

---

### CHUNK 16 — FINAL AUDIT & COMPLETION REPORT
**[FOR YOU — GEMINI CLI]**

Run the entire suite three times; `lint-imports`; apply the migration to a fresh database and downgrade/re-upgrade it; apply it to a database seeded with old-style accounts and confirm they all log in; verify the C14 touch map; fill the Completion Checklist; and classify readiness in **three honest lists: ready for production use / ready for testing only / not built.** The last list must include at least: password reset, email change, Apple/Microsoft sign-in, new-sign-in alert emails, a production email-provider adapter (only SMTP and the log adapter exist), login brute-force protection (ADR-020), cancelling a disabled student's unpaid holds (not part of this module), and **a real-Google end-to-end run, which only Nsisong can perform with the Google Cloud client ID and the running frontend (G9)**.

---

## PART E — COVERAGE MATRIX [FOR NSISONG]

| Your request | Built in | Proven in |
|---|---|---|
| Sign up and sign in with Google (**real**) | Chunks 7, 9, 10 | Chunks 7, 9, 13; **G9 (you, with the real frontend)** |
| A **mock** Google interface alongside the real one | Chunks 7, 10 | Chunks 7, 10, 13 |
| The frontend can tell which Google modes are on | Chunks 7, 10 | Chunks 7, 10 |
| Email verification by OTP for everyone who doesn't use Google | Chunks 6, 8, 10 | Chunks 8, 10, 12 |
| Google users skip the code (their email is already proven) | Chunk 9 | Chunks 9, 13 |
| Existing accounts keep working | Chunk 5 | Chunks 5, 12, 16 |
| Safe account-takeover behavior (squatting, linking) | Chunks 8, 9 | Chunks 8, 9, 12, 13 |
| No mock can ever be accepted in a real environment | Chunks 2, 7, 10 | Chunks 2, 13 |

---

## PART F — FRONTEND DOCUMENTATION [FOR NSISONG — copy into your Front End Doc]

All paths are under `/api/v1`. Errors always look like `{ "error": { "code": "...", "message": "..." } }`; branch on `code`, show `message`.

### A. Email and password sign-up (now with a verification code)
1. **`POST /auth/register`** (unchanged request) → `201` with the old fields **plus `email_verification_required`** (`true` for a normal sign-up). If `true`, go to a "Enter your 6-digit code" screen. The server has already emailed the code.
2. **`POST /auth/verify-email`** `{ "email", "code" }` → `200 { "verified": true }`. **No tokens are returned — call `/auth/login` next.** Any failure is `422 invalid_or_expired_code` — the same message for a wrong code, an expired code, too many tries, or an unknown email; **do not try to tell them apart.** A code that isn't exactly 6 digits is `422 validation_error`.
3. **`POST /auth/resend-verification`** `{ "email" }` → **always** `202`, always the same message, whether or not the email has an account. Show "If this email needs verification, a new code has been sent." and **disable the button for 60 seconds** on the client (the server also limits it, silently).
4. **`POST /auth/login`** on an account that isn't verified yet → **`403 email_not_verified`** (only returned when the password was right). The server has already sent a fresh code, so send the user straight to the code screen.
Code facts: 6 digits, valid **10 minutes**, locked after **5 wrong tries** (request a new code), a new code replaces the old one.
**Existing accounts are already marked verified** and are unaffected.

### B. Continue with Google
**At app start, call `GET /auth/google/config`** (no sign-in needed) → `{ "enabled", "real_enabled", "mock_enabled", "client_ids" }`.
- `real_enabled: true` → show Google's **official** sign-in button/flow, configured with one of the returned `client_ids`. Take the **ID token** Google gives you and send it as `id_token`:
  - **Web** (Google Identity Services): the button's callback returns a `credential` — that string is the `id_token`.
  - **Android** (Credential Manager "Sign in with Google"): use the **web** client ID as the server client ID so the token's audience matches; send `GoogleIdTokenCredential.idToken`.
  - **iOS** (Google Sign-In SDK): send the `idToken` from the sign-in result.
  Optionally generate a random `nonce`, give it to Google when starting sign-in, and send the same value as `nonce`.
- `mock_enabled: true` (**only ever in local/test**) → also show a clearly labelled **"Mock Google (dev only)"** control. It asks for an email, calls `POST /dev/google-mock/token` `{ "email", "email_verified"?: true, "hosted_domain"?: null }` → `{ "id_token": "fake:…" }`, and then sends that string to `/auth/google` exactly as the real flow would.
- Both `false` → hide Google sign-in. In production `mock_enabled` is always `false`.

**`POST /auth/google`** `{ "id_token", "nonce"? }` → `200 { access_token, refresh_token, token_type, expires_in, is_new_account }` (same tokens as `/auth/login`).
- `is_new_account: true` → this is the person's first session: send them through the **same profile/role setup** a password registrant gets after registering.
| Status | `error.code` | What to show |
|---|---|---|
| 401 | `invalid_google_token` | "Google sign-in couldn't be verified. Please try again." (never more detail) |
| 422 | `google_email_not_supported` | "That Google account can't be used to sign up. Please register with your email and a password." |
| 409 | `account_exists` | "You already have an account with this email. Sign in the way you did before, then link Google in settings." |
| 403 | `account_suspended` / `account_disabled` | same messages as login |
| 404 | `google_sign_in_disabled` | hide the Google button |
Only **Gmail** addresses and **Google Workspace (school/work)** accounts can sign up with Google.

### C. Account settings (all need `Authorization: Bearer <access_token>`)
- **`GET /auth/me`** now also returns **`email_verified`** (bool) and **`sign_in_methods`** (`["PASSWORD"]`, `["GOOGLE"]`, or both). Use it to decide what to show.
- **`POST /auth/google/link`** `{ "id_token", "nonce"? }` → `200 { "linked": true }`. Errors: `409 google_already_linked`, `409 google_identity_in_use`, `401 invalid_google_token`.
- **`DELETE /auth/google`** → `204`. `409 last_sign_in_method` if they have no password — prompt them to set one first.
- **`POST /auth/password`** `{ "new_password" }` (8–128 characters) → `204`. Only for accounts **without** a password (Google-only); otherwise `409 password_already_set`.

### D. Login screen hints
- A Google-only account that tries email+password gets the ordinary `401 invalid_credentials` (the server deliberately doesn't say why). Add a static hint under the login form: **"Signed up with Google? Use Continue with Google."**

### E. Development helpers (local/test only; `404` anywhere else)
- **`GET /dev/mailbox?to=<email>`** — the last emails "sent" to that address (so you can read the verification code without a real inbox).
- **`POST /dev/google-mock/token`** — mint a mock Google token (see B).

---

## PART G — MANUAL TESTING GUIDE [FOR NSISONG — and Gemini's source for `docs/manual_testing/module_17.md`]

**Read this first.** You'll sign up, get a code, break the rules on purpose, and sign in with Google two ways: a **mock** one (no Google needed) and the **real** one (needs your Google Cloud setup). Each test says what to do and what you should see.

**Setup for the local tests:** in `.env` set `APP_ENV=local`, `EMAIL_BACKEND=log`, `GOOGLE_AUTH_BACKEND=both`, and `GOOGLE_OAUTH_CLIENT_IDS=<your client id>` (for tests V1–G8 any placeholder like `placeholder.apps.googleusercontent.com` works, because the mock path doesn't contact Google; G9 needs your real one). **Restart the API.**

**The cast:** **Ada** (a student who will register fresh in these tests — use new emails each time). Your older test accounts (Bola, Ade, Rita) already exist.

**Helpers** — paste once per Termux session. *(Gemini verifies the paths and the mailbox response shape.)*
```
BASE=http://localhost:8000/api/v1
post() { curl -s -X POST "$BASE$1" -H 'Content-Type: application/json' ${3:+-H "Authorization: Bearer $3"} -d "$2" | jq .; }
code() { curl -s "$BASE/dev/mailbox?to=$1" | jq -r '.[0].text' | grep -oE '[0-9]{6}' | head -1; }
mock() { curl -s -X POST $BASE/dev/google-mock/token -H 'Content-Type: application/json' -d "{\"email\":\"$1\"}" | jq -r '.id_token'; }
```
`post PATH 'JSON' [TOKEN]` sends a request. `code EMAIL` reads the newest verification code from the dev mailbox. `mock EMAIL` makes a mock Google token.

---

**V1 — Register and receive the code.**
*What this proves:* signing up sends a code.
*Do this:* `post /auth/register '{"email":"ada1@gmail.com","password":"correcthorse123"}'`, then `code ada1@gmail.com`.
*You should see:* `201` with `email_verification_required: true`, and a 6-digit number printed by `code`.
*If you don't:* no number means the email wasn't "sent" — check `EMAIL_BACKEND=log` and the API's log.

**V2 — You can't log in until you verify.**
*Do this:* `post /auth/login '{"email":"ada1@gmail.com","password":"correcthorse123"}'`.
*You should see:* `403` with `email_not_verified`. Also try a **wrong** password: you should get the ordinary `401 invalid_credentials` (it must **not** say the account is unverified).

**V3 — Wrong code, then the right one.**
*Do this:* `post /auth/verify-email '{"email":"ada1@gmail.com","code":"000000"}'`, then with the real code from `code ada1@gmail.com`, then log in again.
*You should see:* the first gives `422 invalid_or_expired_code`; the second gives `{"verified": true}`; login now returns tokens; `GET /auth/me` shows `email_verified: true`.

**V4 — The code expires.**
*Do this:* set `IDENTITY_OTP_TTL_SECONDS=30` **and restart the API.** Register `ada2@gmail.com`, wait 40 seconds, then verify with the code.
*You should see:* `422 invalid_or_expired_code` — **exactly the same message** as a wrong code. Then `post /auth/resend-verification` and verify with the new code: it works.
*Cleanup:* remove the setting and restart.

**V5 — Too many guesses lock the code.**
*Do this:* register `ada3@gmail.com`. Send five wrong codes (`000001` … `000005`). Then send the **correct** code.
*You should see:* the correct code **also fails** — it's locked. Resend and verify with the new code: it works.

**V6 — Resend limits.**
*Do this:* register `ada4@gmail.com`. Immediately call `post /auth/resend-verification '{"email":"ada4@gmail.com"}'` three times. Look at `GET /dev/mailbox?to=ada4@gmail.com`.
*You should see:* every call returns the same `202` message; the mailbox shows **only one or two** emails, not four (the 60-second cooldown holds the rest back silently). Try `ada-nobody@gmail.com` too: **identical** `202` — it never reveals whether an account exists.

**V7 — Someone else registers your email.**
*What this proves:* an unproven signup can't lock the real owner out.
*Do this:* register `victim1@gmail.com` with password `attackerpass123` and **don't verify it**. Then register the same email with `realownerpass123` and verify with the newest code. Try logging in with each password.
*You should see:* only `realownerpass123` works; `attackerpass123` gives `401`.

**V8 — Your existing accounts still work.**
*Do this:* log in as Bola (or any account that existed before this module).
*You should see:* a normal login, no code needed.

**G1 — Which Google buttons should show.**
*Do this:* `curl -s $BASE/auth/google/config | jq .`
*You should see:* `{"enabled": true, "real_enabled": true, "mock_enabled": true, "client_ids": ["…"]}` in `both` mode. Change the backend to `fake` and restart: `real_enabled: false`, empty `client_ids`. Change to `disabled`: everything `false`, and `post /auth/google '{"id_token":"fake:a:b@gmail.com"}'` gives `404 google_sign_in_disabled`. Set it back to `both` and restart.

**G2 — Mock Google: first sign-in creates an account.**
*Do this:* `T=$(mock newgoogle1@gmail.com)` then `post /auth/google "{\"id_token\":\"$T\"}"`.
*You should see:* tokens and `is_new_account: true`. Use the access token on `GET /auth/me`: `email_verified: true`, `sign_in_methods: ["GOOGLE"]`. **No code was needed.**

**G3 — Same Google user again.**
*Do this:* repeat the `post /auth/google` with the same token.
*You should see:* tokens again, `is_new_account: false`, and the **same account id** in `/auth/me`.

**G4 — Google when a verified password account already has that email.**
*Do this:* use `ada1@gmail.com` (verified in V3). `T=$(mock ada1@gmail.com)` then `post /auth/google …`.
*You should see:* `409 account_exists` and nothing changed (log in with the password still works). Now log in with the password, then `post /auth/google/link "{\"id_token\":\"$T\"}" <access_token>` → `{"linked": true}`. Sign in with Google again: you get Ada's **same** account.

**G5 — Google claims an unverified account.**
*Do this:* register `squat1@gmail.com` with `attackerpass123` (don't verify). Then `T=$(mock squat1@gmail.com)` and `post /auth/google …`.
*You should see:* success, `is_new_account: true`. Then try `post /auth/login` with `attackerpass123`: **`401`** — the attacker's password is gone.

**G6 — Emails Google can't vouch for.**
*Do this:* `T=$(mock someone@yahoo.com)` and sign in. Then mint a token for `x@gmail.com` with `email_verified` false: `curl -s -X POST $BASE/dev/google-mock/token -H 'Content-Type: application/json' -d '{"email":"x@gmail.com","email_verified":false}' | jq -r .id_token`.
*You should see:* both give `422 google_email_not_supported`. A token for `x@school.edu` with `"hosted_domain":"school.edu"` **works** (a Google Workspace account).

**G7 — Link, unlink, set a password.**
*Do this:* with the Google-only account from G2: try `DELETE /auth/google` (use `curl -X DELETE`); then `post /auth/password '{"new_password":"newpassword123"}' <token>`; then `DELETE /auth/google` again; then log in with the new password.
*You should see:* the first `DELETE` → `409 last_sign_in_method`; setting the password → `204`; the second `DELETE` → `204`; password login works. Calling `post /auth/password` again → `409 password_already_set`.

**G8 — A disabled account can't use Google.**
*Do this:* as Ade, disable the G2 account through the audited admin route *(Gemini verifies)*, then `post /auth/google` with its token.
*You should see:* `403 account_disabled`. Reactivate and it works again.

**G9 — The real Google sign-in. Run by Nsisong with the real frontend.** *(Gemini writes this out in full in `docs/manual_testing/module_17.md`; the commands cannot be run by the coding agent.)*
*One-time Google setup (menu names change; follow Google's current instructions if they differ):* in **Google Cloud Console**, pick or create a project; configure the **OAuth consent screen** (app name, support email; while it is in "Testing" mode, add yourself as a test user); then **APIs & Services → Credentials → Create credentials → OAuth client ID → Web application**; under **Authorized JavaScript origins** add your frontend's address (for local development, for example `http://localhost:3000`); copy the **Client ID** (it ends in `.apps.googleusercontent.com`). Put that same Client ID in the frontend's Google configuration **and** in `GOOGLE_OAUTH_CLIENT_IDS` in `.env`, set `GOOGLE_AUTH_BACKEND=both`, and **restart the API.**
*Do this:* open the frontend, click **Continue with Google**, and choose a real Gmail account.
*You should see:* you're signed in; the frontend shows a new-account flow the first time (`is_new_account: true`) and straight in the second time; in the API log you see `google_sign_in_succeeded` with an account id (and **no** token text). A school/work (Workspace) account also works; a non-Gmail, non-Workspace Google account is refused with the friendly message.
*If you don't:* `invalid_google_token` almost always means the Client ID in the frontend and in `.env` don't match (the token's audience), or the origin isn't authorized in Google Cloud. A browser popup error before the API is even called is a Google Cloud setup problem, not an API problem.

**G10 — Real and mock side by side.**
*Do this:* in `both` mode, sign in with **real** Google (G9) and with **mock** Google (G2) on the same frontend, one after the other.
*You should see:* both work, and they create **separate** accounts unless the emails match (then the collision rules from G4 apply).

**G11 — The mock cannot exist in a real environment.**
*Do this:* run `APP_ENV=staging GOOGLE_AUTH_BACKEND=both GOOGLE_OAUTH_CLIENT_IDS=x.apps.googleusercontent.com poetry run python -c "from camp_match.config.settings import Settings; Settings()"`, and again with `EMAIL_BACKEND=log` and `GOOGLE_AUTH_BACKEND=google`.
*You should see:* both **refuse to start**, with a message naming the setting that isn't allowed there. (A staging/production environment must use `GOOGLE_AUTH_BACKEND=google` and `EMAIL_BACKEND=smtp`.)

**Stuck?** (1) No code in the mailbox → `EMAIL_BACKEND` isn't `log`, or you restarted and the in-memory mailbox emptied — register or resend again. (2) `404` on `/dev/...` → `APP_ENV` isn't `local`/`test`, or `GOOGLE_AUTH_BACKEND` doesn't include the mock. (3) `401 invalid_google_token` on a mock token → the token must start with `fake:` and the backend must be `fake` or `both`. (4) A test needing a short expiry still passes the long way → you forgot to **restart** after changing `.env`. (5) `409 account_exists` where you expected a new account → that email already exists; use a fresh one.

---

## COMPLETION CHECKLIST [FOR NSISONG]

- [ ] Module 15 present; `google-auth`, `requests`, `aiosmtplib` (and dev `aiosmtpd`) installed on this device **without compiling** (Chunk 1 report).
- [ ] Migration: `password_hash` nullable; verification columns with the both-or-neither check; **every pre-existing account backfilled verified `LEGACY`**; two new tables; `downgrade` refuses while a passwordless account exists; the round trip is clean.
- [ ] **Email verification:** a password sign-up cannot log in until the code is entered; the code is 6 digits, hashed (never stored raw), 10 minutes, five tries, single-use, one active per account; cooldown and hourly cap hold; `verify-email` and `resend-verification` bodies are **byte-identical** across unknown/verified/unverified emails; a wrong password on an unverified account does **not** reveal that it's unverified.
- [ ] **Squatting defences:** a second registration over an unverified email replaces it; a verified email is refused; Google claims an unverified account and destroys the squatter's password.
- [ ] **Google (real):** the real verifier checks signature, expiry, audience (against the configured list), issuer, subject and nonce; every failure is one `401 invalid_google_token`; verification never blocks the event loop; the token is never logged or stored; the real path was proven with locally signed tokens and **zero network calls in tests**.
- [ ] **Google (mock):** the mock runs through the **same** use case; `both` routes `fake:` tokens to the mock and everything else to real Google; `GET /auth/google/config` and the mock-token minter behave as specified; **no mock route, mock acceptance, or log email backend can start or run in `staging`/`production`**.
- [ ] A new Google sign-up publishes the **same** `UserRegistered` as a password sign-up; downstream subscribers confirmed (Chunk 1).
- [ ] Only Gmail and Google Workspace (`hd`) emails with `email_verified = true` can sign up with Google; the account is found by `sub`, never by email.
- [ ] Link, unlink (refused when it would leave no sign-in method) and set-password work; a Google-only account cannot be probed through password login.
- [ ] The five original endpoints keep every existing field, status and error code (OpenAPI diff is additive only); Identity's entire original suite passes unmodified; the running frontend's existing login still works for verified accounts.
- [ ] Module 15's retention sweep purges expired/used codes and never an active one; its guard test lists the target exactly.
- [ ] No raw password, code (outside the local/test log email adapter), Google token, or SMTP password in any log, response, event, or database column.
- [ ] Docs written; frontend API doc updated from Part F; AI state updated; **the manual guide follows the plain-language rules and every command in it (except G9) was run.**
- [ ] **G9 (the real Google run with your Client ID and the running frontend) has been performed by Nsisong and passed.**
- [ ] The final report classifies readiness in three honest lists (production-ready / testing-only / not built).
