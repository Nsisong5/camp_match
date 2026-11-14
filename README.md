# Camp Match

Camp Match backend — modular monolith, hexagonal architecture. Under construction.

## Testing
- Run all tests: `poetry run pytest`
- Run one layer: `poetry run pytest -m unit` (also `integration`, `api`, `architecture`)
- Run a single file: `poetry run pytest tests/api/test_health.py`

## Module 17: Email Verification & Google Sign-In Setup
- **Email Verification**: Enabled by default (`IDENTITY_EMAIL_VERIFICATION_REQUIRED=true`). For local/test environments, set `EMAIL_BACKEND=log` to inspect verification codes via `GET /api/v1/dev/mailbox?to=<email>`.
- **Google Sign-In**: Configure `GOOGLE_AUTH_BACKEND` in `.env`:
  - `GOOGLE_AUTH_BACKEND="both"` (enables both real Google ID tokens and local mock tokens).
  - `GOOGLE_AUTH_BACKEND="fake"` (mock only, local/test only).
  - `GOOGLE_AUTH_BACKEND="google"` (real Google only).
  - `GOOGLE_AUTH_BACKEND="disabled"` (default).
  - Set `GOOGLE_OAUTH_CLIENT_IDS="your-client-id.apps.googleusercontent.com"`.
- **Google Cloud Setup**: In Google Cloud Console, configure an OAuth client ID (Web application) with authorized JavaScript origins matching your frontend.

## Code Quality
- Linting: `poetry run ruff check .`
- Formatting: `poetry run ruff format .`
- Type checking: `poetry run mypy src`
- Architectural boundaries: `poetry run lint-imports`

## Database (Termux)
- Run `scripts/db_bootstrap.sh` once after cloning.
- Run `scripts/db_start.sh` at the start of every dev/test session.
- Apply database migrations: `alembic upgrade head` (ensure `DATABASE_URL` is configured in `.env`).
- Run `scripts/db_stop.sh` when done.
The server does not survive a Termux/device restart automatically — you always start it manually. Consider `termux-wake-lock` for long sessions.

## Contributing / Commit Convention
This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Please use one of the following types for your commit messages:
- `feat`: A new feature
- `fix`: A bug fix
- `chore`: Build process or auxiliary tool changes
- `docs`: Documentation changes
- `test`: Adding missing tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `build`: Changes that affect the build system or external dependencies
- `ci`: Changes to our CI configuration files and scripts
