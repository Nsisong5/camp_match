# Database State: Admin & Operations
- Tables added: `admin_issues`, `admin_issue_events`, `admin_audit_events`.
- Triggers: `prevent_admin_audit_events_mutation`, `prevent_admin_issue_events_mutation` (enforcing strict append-only immutability).
