Implement outbox pattern in platform:
- Postgres outbox table with status, attempts, next_attempt_at, payload, event metadata
- A publisher utility for modules/workflows to enqueue outbox events
- Celery worker that processes outbox items (no real external calls yet; just structured logs)
- Retry/backoff policy and poison handling (mark failed after N attempts)

Deliver:
- migrations
- platform/outbox/*
- Celery wiring + worker command
- tests covering enqueue + worker processing + retries
- docs: /docs/architecture/INTEGRATIONS.md (integration boundary principles)
