# Architecture Overview

This system is a **modular monolith**.

## High-level structure

platform → modules → workflows → API composition

- Platform: cross-cutting infrastructure (DB, auth, RBAC, outbox, projections, documents)
- Modules: domain ownership (tables + invariants + APIs)
- Workflows: orchestration/state machines
- API layer: wiring only, no business logic

## Backend stack
- FastAPI (sync endpoints)
- Pydantic
- SQLAlchemy (synchronous sessions only — no async) + Alembic
- PostgreSQL
- Redis + Celery

### Why sync SQLAlchemy
This is a single-tenant internal system, not a high-concurrency SaaS product. Sync is the standard because:
- Celery workers (outbox processing, projection updates) run synchronously. Mixing sync workers with async request handlers adds complexity for no benefit.
- Sync is simpler to debug, test, and reason about — critical when AI agents write the code.
- FastAPI supports sync endpoints without issue; the performance difference at Atlas's scale is negligible.
- No async/sync session lifecycle mismatches to manage.

## Frontend stack
- React ecosystem
- Next.js App Router (client-first usage)
- Generated API client from OpenAPI
- Feature modules aligned to backend modules

## Key architectural pillars
- Explicit boundaries
- Deterministic workflows
- Append-only financial records
- Read models for speed
- Enforced contracts
