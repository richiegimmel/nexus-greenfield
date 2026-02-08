# Nexus

A custom, internal ERP platform for **Atlas Machine and Supply**.  
Single-tenant. Workflow-driven. Deterministic. Fast.

This system replaces **Epicor first** (ERP / MRP / Jobs / GL) and later **Salesforce**.  
It is not a SaaS product. It is purpose-built for Atlas's operations.

---

## What This Is

An **event-driven, workflow-oriented modular monolith** designed to:

- Model complex manufacturing and service workflows explicitly
- Preserve accounting-grade immutability
- Deliver extremely fast UI performance
- Support heavy AI-assisted development without architectural drift

---

## Core Business Scope

Atlas operates four business units:

### Operational
- **Machining & Repair**
  - Job shop manufacturing
  - Job shop repairs
  - Field machining & welding
  - Metrology
- **Industrial Products**
  - Compressed air equipment sales
  - Field service
  - Spare parts
  - Rentals
  - System installations

### Support
- **Corporate** – HR, IT, Facilities, Marketing, Accounting, Legal
- **Owner** – Owner-specific expenses for financial segmentation

All financials must support **sites, cost centers, and business unit segmentation**.

---

## Architectural Principles (Non-Negotiable)

- **Single database forever**
- **Big-bang cutover** from Epicor
- **Modular monolith**
- **Workflow-driven state machines**
- **Append-only financial records**
- **Read models for speed**
- **OpenAPI is the contract**
- **Boundaries enforced by CI, not convention**

If you violate one of these, the system will rot.

---

## High-Level Architecture

platform → modules → workflows → API composition


### Platform
Cross-cutting infrastructure:
- DB/session management
- Auth & RBAC
- Outbox
- Projections (read models)
- Logging, settings, error handling

### Modules
Own **data + invariants + APIs**.
- No shared domain models
- No cross-module ORM relationships
- Public APIs only via explicit exports

Examples:
- `dimensions`
- `ledger`
- `jobshop`
- `inventory`
- `invoicing`

### Workflows
Explicit state machines that **orchestrate** modules.
- Deterministic
- Concurrency-safe
- Append-only history
- Override support with justification

Workflows **do not own domain tables**.

---

## Accounting Model

- Ledger is **append-only**
- Posted entries are immutable
- Corrections = reversals and/or new entries
- Every financially meaningful workflow event results in ledger postings

This is accounting-grade immutability even though the system is internal.

---

## Performance Model

- Transactional tables are **not** UI query targets
- UI reads from **projections / read models**
- Projections are built from events (outbox + workers)
- Fast dashboards and workflow views are mandatory

---

## Tech Stack

### Backend
- FastAPI
- Pydantic
- SQLAlchemy + Alembic
- PostgreSQL
- Redis + Celery

### Frontend
- React ecosystem
- Next.js (client-first usage)
- Generated TypeScript API client from OpenAPI

### Tooling
- GitHub (issues, PRs, CI)
- Cursor (local + cloud agents)
- Pre-commit + CI enforcement

---

## Repository Layout (Simplified)

```
backend/
  app/
    platform/
    modules/
    workflows/
    api/

frontend/
  src/
    modules/
    api/generated/

docs/
.cursor/
```

---

## Development Model (AI-First)

This repo is designed to be worked on primarily by **AI coding agents** with human oversight.

Key rules:
- One issue → one agent → one PR
- Plan first, then implement
- Small PRs
- CI enforces boundaries, contracts, and invariants

Canonical references for agents live in `/docs/`.

---

## Required Reading (Before Coding)

If you are human or AI, read these first:

- `/docs/PROJECT_CONTEXT.md`
- `/docs/ARCHITECTURE_OVERVIEW.md`
- `/docs/MODULE_CONCEPTS.md`
- `/docs/WORKFLOWS_AND_STATE.md`
- `/docs/ACCOUNTING_MODEL.md`
- `/docs/READ_MODELS_AND_PERFORMANCE.md`
- `/docs/FRONTEND_CONTRACT_MODEL.md`
- `/docs/AI_AGENT_GUIDANCE.md`
- `/docs/DEVELOPMENT_WORKFLOW.md`

---

## Local Development (High Level)

Exact commands are defined in the Makefile, but conceptually:

```bash
make bootstrap
make dev
make lint
make typecheck
make test
make contract
```

Docker Compose provides local Postgres and Redis.

---

## What This Repo Optimizes For

- Correctness over convenience
- Explicit state over implicit behavior
- Structural clarity over speed of first commit
- AI scalability over human heroics

---

## What This Repo Explicitly Does NOT Optimize For

- Multi-tenant SaaS concerns
- SEO
- Generic ERP abstraction layers
- Rapid prototype hacks

---

## Final Note

This system is load-bearing software for Atlas's operations.

If something feels "over-engineered," it's probably because:

- It prevents silent corruption
- It makes AI agents predictable
- It avoids a rewrite later

Treat the constraints as part of the product.
