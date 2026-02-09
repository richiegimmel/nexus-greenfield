Implement platform RBAC/policy with:
- roles mapped to business units
- permission rules expressed as can_trigger_event(workflow_name, event_type, role, current_state, override_flag)
- middleware/dependency for FastAPI enforcing policy on workflow event ingestion
- audit fields: actor_id, actor_role, override_reason captured in workflow_event/transition log

Stub auth is acceptable (dev token), but structure for future SSO.

Deliver:
- platform/auth + platform/rbac
- DB tables for users, roles, assignments, permission_rules
- tests: allowed/denied transitions, override requires specific permission + reason
- docs: /docs/security/RBAC.md
