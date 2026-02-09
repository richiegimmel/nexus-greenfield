Implement workflows/engine with:
- workflow definitions in YAML under backend/app/workflows/<name>/definition.yaml
- compile+validate definitions at startup (fail fast)
- workflow_instance table with version integer for optimistic locking
- workflow_event table with idempotency_key support
- transition log append-only
- API endpoints:
  POST /workflow/instances (create)
  GET /workflow/instances/{id} (state + history)
  POST /workflow/instances/{id}/events (apply event with expected_version + idempotency_key)
- Overrides:
  - explicit event type "OverrideTransition" (or per-transition override flag)
  - requires override_reason string
  - RBAC check hook (stub ok now; integrate later)

Concurrency:
- Reject event if expected_version != current version (409)
- Idempotency: same idempotency_key returns same result without double-applying

Deliver:
- engine implementation + migrations
- unit tests: determinism, optimistic locking, idempotency, override requirement
- docs: /docs/architecture/WORKFLOW_ENGINE.md
