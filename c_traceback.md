127.0.0.1:39858 - "OPTIONS /api/v1/auth/google HTTP/1.1" 200 OK
{"event": "google_verification_started", "request_id": "024f358b-5a06-4af8-b075-e78f8c04e312", "level": "info", "timestamp": "2026-11-14T15:18:09.746045Z"}
{"event": "google_token_input_validated", "request_id": "024f358b-5a06-4af8-b075-e78f8c04e312", "level": "info", "timestamp": "2026-11-14T15:18:09.746626Z"}
{"event": "google_verification_library_started", "request_id": "024f358b-5a06-4af8-b075-e78f8c04e312", "level": "info", "timestamp": "2026-11-14T15:18:09.747093Z"}
{"stage": "verification_library", "error_type": "InvalidValue", "event": "google_verification_failed", "request_id": "024f358b-5a06-4af8-b075-e78f8c04e312", "level": "error", "timestamp": "2026-11-14T15:18:10.723626Z"}
{"code": "invalid_google_token", "path": "http://localhost:8000/api/v1/auth/google", "event": "application_error", "request_id": "024f358b-5a06-4af8-b075-e78f8c04e312", "level": "warning", "timestamp": "2026-11-14T15:18:10.727869Z"}
INFO:     127.0.0.1:39862 - "POST /api/v1/auth/google HTTP/1.1" 401 Unauthorized


Also I need you to enforce the format the information is required from the backend. if the information is not in the required format returned a message pointing that the information is not in the required format 
and then diagnosed the problem above