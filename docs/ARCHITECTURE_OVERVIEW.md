# Architecture Overview

This system is a **modular monolith**.

## High-level structure

platform → modules → workflows → API composition

- Platform: cross-cutting infrastructure (DB, auth, RBAC, outbox, projections)
- Modules: domain ownership (tables + invariants + APIs)
- Workflows: orchestration/state machines
- API layer: wiring only, no business logic

## Backend stack
- FastAPI
- Pydantic
- SQLAlchemy + Alembic
- PostgreSQL
- Redis + Celery

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
