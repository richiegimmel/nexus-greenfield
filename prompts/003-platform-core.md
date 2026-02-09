Implement platform core utilities:
- database session management (synchronous SQLAlchemy only — this is decided and non-negotiable; see rationale below)
- settings management (pydantic settings)
- structured logging with correlation/request IDs
- standardized error model:
  - validation errors (422)
  - domain rule violations (409 or 422; pick and standardize)
  - not found (404)
  - authz (401/403)
  - unexpected (500) with safe error response

Deliver:
- backend/app/platform/* with clear interfaces
- tests for error handlers and db wiring
- docs: /docs/standards/ERRORS.md and /docs/standards/LOGGING.md

Rationale for sync SQLAlchemy:
- Single-tenant internal system; no concurrency pressure requiring async.
- Celery workers (outbox, projections) are sync; mixing async request handlers with sync workers causes lifecycle mismatches.
- Sync is simpler for AI agents to write, test, and debug correctly.
- FastAPI handles sync endpoints fine; performance difference at Atlas's scale is negligible.
