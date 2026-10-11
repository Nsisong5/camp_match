# Profile Module

The Profile module handles user profile management, including personal details, student-specific information (budget, preferences, university association), and scout-specific information (business details, availability).

## Design Overview
- **Modular Monolith**: Follows hexagonal architecture (domain, application, ports, adapters).
- **Core Entities**: `Profile`.
- **Value Objects**: `ProfileType`, `StudentProfileDetails`, `ScoutProfileDetails`.

## API Endpoints
- `POST /api/v1/profiles`: Create a new profile (linked to an Identity ID).
- `GET /api/v1/profiles/me`: Get current user's full profile.
- `GET /api/v1/profiles/{profile_id}`: Get a public profile view (limited data).
- `PATCH /api/v1/profiles/me`: Update core profile info.
- `PATCH /api/v1/profiles/me/student`: Update student-specific details (`university_id`, department, budget, preferences).
- `PATCH /api/v1/profiles/me/scout`: Update scout-specific details.
- `POST /api/v1/profiles/me/avatar`: Upload profile avatar image (multipart file upload via Media/File module).

## University Association & Legacy Compatibility (ADR-089)
- Student profiles support canonical `university_id` referencing the University & Location module.
- `university_name` (free-text string) is **deprecated** as a write input but retained for legacy display compatibility for existing records that have not migrated.
- **Mutual Exclusivity**: Setting `university_id` supersedes and clears any legacy `university_name`.
- **No Automatic Backfill**: Existing `university_name` records are not automatically migrated; users transition when updating their profile.
- **Response Shape (`student_details.university`)**:
  - Canonical: `{"type": "canonical", "value": {"id": "...", "official_name": "..."}}` when `university_id` is set.
  - Legacy: `{"type": "legacy_text", "value": "..."}` when only free-text `university_name` is set.
  - Null: `null` when neither is set.

## Avatar Management & Legacy Compatibility
- Profiles support `avatar_media_id` referencing the Media/File module.
- `avatar_url` is **deprecated** but retained for legacy compatibility.
- To check the count of active profiles still using legacy `avatar_url`:
  ```sql
  SELECT COUNT(*) FROM profiles WHERE avatar_url IS NOT NULL AND avatar_media_id IS NULL;
  ```

## Persistence
- SQLAlchemy-backed repository using three tables: `profiles`, `student_profiles`, `scout_profiles`.
