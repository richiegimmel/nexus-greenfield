Implement platform core utilities:
- database session management (async or sync, choose one and standardize)
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
