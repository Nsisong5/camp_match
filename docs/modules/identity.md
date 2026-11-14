# Identity Module

The Identity module handles user registration, authentication, session management, email verification, third-party identity federation (Google Sign-In), and profile retrieval for Camp Match.

## Overview

- **Purpose**: Manage identities and provide secure access.
- **Scope**: User accounts, credentials, session tokens, OTP verification, federated sign-in.

## Architecture

The module follows hexagonal architecture:

- **Domain**: Pure business logic (entities like `UserAccount`, `ExternalIdentity`, `OneTimeCode`, value objects, domain errors).
- **Application**: Ports and use cases (e.g., `RegisterAccountUseCase`, `AuthenticateUserUseCase`, `VerifyEmailUseCase`, `SignInWithGoogleUseCase`, `LinkGoogleAccountUseCase`, `UnlinkGoogleAccountUseCase`, `SetPasswordUseCase`).
- **Adapters**:
  - **API**: FastAPI routers, request/response schemas with `extra="forbid"`, dependency injection.
  - **Persistence**: SQLAlchemy repositories for `identity_accounts`, `identity_external_identities`, and `identity_one_time_codes`.
  - **Security**: JWT session tokens, Scrypt password hashing, HMAC-SHA256 one-time code hashing.
  - **Google**: Google OAuth2 ID token verifiers (`GoogleIdTokenVerifier`, `FakeGoogleVerifier`, `DisabledGoogleVerifier`, `CompositeGoogleVerifier`), mock minter.
  - **Email**: `LogEmailSender`, `SmtpEmailSender`, in-memory `DevMailbox`.

## Tables & Persistence

1. **`identity_accounts`**: Stores user identity, optional `password_hash` (nullable for Google-only users), `email_verified_at`, and `email_verification_source` (`OTP`, `GOOGLE`, `LEGACY`). Pre-existing accounts were backfilled with `LEGACY`.
2. **`identity_external_identities`**: Stores federated identities keyed by `(provider, subject)` referencing `account_id`.
3. **`identity_one_time_codes`**: Stores cryptographic HMAC-SHA256 hashes of 6-digit OTP codes, purpose, attempt counts, expiration, and consumption/invalidation timestamps.

## Authentication & Verification Model

- **Password Sign-Up**: When `identity_email_verification_required=true`, registration issues a 6-digit OTP code valid for 10 minutes. Login is blocked (`403 email_not_verified`) until verified via `POST /auth/verify-email`.
- **Google Sign-In**: Uses Google ID token exchange (`POST /auth/google`). First-time sign-in provisions an account with `is_new_account: true` and pre-verified email (`source = GOOGLE`).
- **Collision Rules**:
  - Unverified accounts are claimed by Google (attacker's unverified password is wiped).
  - Verified password accounts return `409 account_exists`, requiring the user to authenticate with password and link Google via `POST /auth/google/link`.
- **Account Linking & Unlinking**: Users can link Google to password accounts, set a password on Google-only accounts (`POST /auth/password`), or unlink Google (`POST /auth/google/unlink`) provided at least one sign-in method remains.

## Architectural Notes & Decisions

- **ADR-018 Reversed in Part**: Email verification by OTP is now mandatory for password sign-ups prior to login.
- **ADR-020 Remains Open**: Login brute-force rate limiting remains open for future implementation; however, OTP endpoints carry strict attempt limits (5 tries) and anti-enumeration protections (ADR-222, ADR-223).
- **Admin Operations**: Unaudited admin routes were retired and replaced by audited Admin & Operations account endpoints (`/api/v1/admin/operations/accounts/...`).

## Known Limitations

- No password reset flow (extension point planned using `identity_one_time_codes`).
- No email change functionality.
- No Apple or Microsoft sign-in (planned via `identity_external_identities`).
- No new-sign-in alert emails.
- No production email provider API adapter (only standard SMTP and local log sender exist).
- No login endpoint IP/rate limiting (ADR-020).

## Extension Points

- **Password Reset**: Reuse `identity_one_time_codes` with purpose `PASSWORD_RESET` and the `EmailSender` port.
- **Additional Federated Providers**: Integrate Apple, Microsoft, or SAML providers by adding new records to `identity_external_identities`.

## Testing Strategy

- **Unit**: Domain entities, value objects, use cases with fakes, Google verifiers, settings.
- **Integration**: Database repositories, Alembic migration, retention hook, session adapter.
- **API**: HTTP-level flow and security tests (`test_email_verification_flow.py`, `test_email_verification_security.py`, `test_google_flow.py`, `test_google_security.py`).
