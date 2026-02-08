# Cursor Setup for Atlas ERP Project (Modular Monolith + AI Agents)

This document defines a Cursor configuration that makes agent output consistent on a complex modular monolith: enforced module boundaries, deterministic workflows, immutable ledger postings, projections-first UI, and OpenAPI-driven contracts.

It uses **project rules** stored in `.cursor/rules/*.mdc`, organized so the right constraints attach automatically by directory and task type. Cursor rule types and their `.mdc` metadata fields (`alwaysApply`, `globs`, `description`) are used explicitly. Cursor's rules system can be created via Cursor Settings → Rules / "New Cursor Rule", which writes into `.cursor/rules/`.

---

## 1) Target outcomes

1. Agents cannot "accidentally" break architecture (boundaries enforced by rules + CI).
2. Agents consistently apply the same patterns (module layout, migrations, projections, OpenAPI generation).
3. Every issue is executable by a cloud agent with minimal human interpretation.
4. Cursor context stays tight: rules auto-attach by glob; only relevant guidance is injected.

---

## 2) Project Rules Architecture

### Rule types (how you should use them)

Cursor rules support four practical modes via metadata in `.mdc` headers:

- **Always** (`alwaysApply: true`): universal invariants (modular monolith, immutability, projections-first, OpenAPI truth).
- **Auto Attached** (`globs`): attach when files in a directory are referenced (backend vs frontend vs workflows).
- **Agent Requested** (`description` + not always): task-specific playbooks (creating a new module, adding a workflow, building a projection).
- **Manual** (not always + no description): rarely used; avoid unless you want explicit opt-in.

### Recommended `.cursor/rules` layout

```text
.cursor/rules/
├── 00-prime-directive.mdc
├── 10-architecture-modules.mdc
├── 20-backend-standards.mdc
├── 21-backend-sqlalchemy-alembic.mdc
├── 22-workflow-engine.mdc
├── 23-ledger-immutability.mdc
├── 24-projections-read-models.mdc
├── 30-frontend-nextjs.mdc
├── 31-frontend-api-contract.mdc
├── 40-github-issues-and-prs.mdc
├── 50-commands-and-checks.mdc
└── agent-playbooks/
    ├── new-module.mdc
    ├── new-workflow.mdc
    ├── new-projection.mdc
    └── integration-outbox.mdc
```

This mirrors how larger projects split topic-based rule subdirectories for maintainability.

---

## 3) Rules content to create (copy/paste templates)

### 3.1 `00-prime-directive.mdc` (Always)

```md
---
alwaysApply: true
---

# Prime Directive (Atlas ERP)

- This is a modular monolith: platform → modules → workflows → API composition.
- Modules own tables + invariants + APIs. No shared "common domain".
- No cross-module internal imports; only public exports from other modules or events/read models.
- No cross-module ORM relationships; reference by ID.
- Workflows orchestrate; never own domain tables.
- Ledger postings are immutable once posted (append-only; corrections via reversal/new entry).
- Workflow transitions must be concurrency-safe (expected_version) and idempotent (idempotency_key).
- Overrides are explicit events requiring justification and RBAC permission.
- UI must be fast: default reads come from read models/projections, not transactional tables.
- OpenAPI is the source of truth; frontend uses generated TS client/types only.

Output requirements for every agent action:
- List files changed, commands to run, tests added, and verification steps.
```

### 3.2 `10-architecture-modules.mdc` (Auto Attached to backend)

```md
---
alwaysApply: false
globs:
  - "backend/**"
---

# Backend Architecture Boundaries

## Module rules
- Each module lives at `backend/app/modules/<module>/`.
- Tables are owned by a single module.
- Disallow imports into `backend/app/modules/*` from other module internals (models/schemas/service).
- Allowed: import `backend/app/modules/<module>/__init__.py` exports only.
- Workflows call module public APIs; workflows do not directly mutate module tables.

## Review gates
- Any cross-cutting pattern change requires:
  - docs update under /docs
  - ADR if it affects multiple modules
  - CI must enforce boundaries
```

### 3.3 `22-workflow-engine.mdc` (Auto Attached to workflows)

```md
---
alwaysApply: false
globs:
  - "backend/app/workflows/**"
---

# Workflow Engine Rules

- Workflow definitions live in YAML under their workflow directory.
- Engine must validate definitions at startup (fail fast).
- Workflow instance supports optimistic locking via `expected_version`.
- Event ingestion supports `idempotency_key` and returns same result if repeated.
- Transition history is append-only.
- Override transitions must:
  - be explicit events
  - include `override_reason`
  - require RBAC permission
```

### 3.4 `23-ledger-immutability.mdc` (Auto Attached to ledger module)

```md
---
alwaysApply: false
globs:
  - "backend/app/modules/ledger/**"
  - "backend/app/modules/gl/**"
---

# Ledger Immutability Rules

- Posted journal entries cannot be updated or deleted.
- Corrections occur via reversals and/or new correcting entries.
- Services must enforce balanced entries.
- Every ledger mutation must be tested:
  - posting immutability
  - reversal correctness
  - balancing invariant
```

### 3.5 `24-projections-read-models.mdc` (Auto Attached to projections + frontend consumers)

```md
---
alwaysApply: false
globs:
  - "backend/app/platform/projections/**"
  - "backend/app/**/projections.py"
  - "frontend/src/**"
---

# Projections / Read Models

- Read models are first-class and are the default UI read source.
- Projections are updated from outbox events (worker-driven).
- Read models may denormalize and are rebuildable.
- After command endpoints, return enough summary state for UI to update immediately.
```

### 3.6 `31-frontend-api-contract.mdc` (Auto Attached to generated client usage)

```md
---
alwaysApply: false
globs:
  - "frontend/src/**"
---

# Frontend API Contract

- OpenAPI is the source of truth.
- Frontend uses generated TS types + client only.
- No handwritten API typing.
- Any backend contract change must:
  - update generation artifacts
  - update usages
  - pass CI drift gate
```

### 3.7 Agent playbooks (Agent Requested rules)

Use Agent Requested for "how to do a task" rules; include a description so Cursor decides when to apply it.

#### `.cursor/rules/agent-playbooks/new-module.mdc`

```md
---
alwaysApply: false
description: "Follow these rules when creating a new backend domain module under backend/app/modules/*"
---

# New Module Playbook

When asked to create a new module:
1) Create folder structure: models.py, schemas.py, service.py, api.py, events.py, tests/
2) Add Alembic migration(s) owned by the module's tables.
3) Expose public API from __init__.py only.
4) Add module router and wire it in api composition layer.
5) Add tests for invariants and API behavior.
6) Update /docs/architecture/MODULE_MAP.md with ownership and events.
7) Run: lint, typecheck, tests, migration apply.
```

#### `.cursor/rules/agent-playbooks/new-workflow.mdc`

```md
---
alwaysApply: false
description: "Follow these rules when adding a new workflow under backend/app/workflows/*"
---

# New Workflow Playbook

1) Create definition.yaml with states, events, guards, transitions.
2) Implement guards in code (config + code guards).
3) Ensure engine validation covers this workflow.
4) Ensure optimistic locking and idempotency are honored.
5) Add tests: happy path + failure paths + override path.
6) Add projection updates for rm_* summary tables.
```

---

## 4) Cursor Context Strategy (Docs + @Docs indexing)

### Why

Complex projects fail when agents don't have stable canonical context. Cursor can auto-include project context and you can also add external docs through its Docs indexing features.

### What to index as Cursor Docs

Add these as indexed docs (so you can reference with `@Docs`):

- `/docs/PROJECT_CONTEXT.md`
- `/docs/ARCHITECTURE_OVERVIEW.md`
- `/docs/architecture/MODULE_MAP.md`
- `/docs/WORKFLOWS_AND_STATE.md`
- `/docs/ACCOUNTING_MODEL.md`
- `/docs/READ_MODELS_AND_PERFORMANCE.md`
- `/docs/FRONTEND_CONTRACT_MODEL.md`

If you have external PDFs/specs, convert them to markdown and add them as docs (common approach is converting and indexing).

---

## 5) Cursor "Hooks" (practical equivalents you can enforce)

Cursor does not need special proprietary hooks if you make the repo itself enforce correctness. Treat these as "hooks":

### A) Pre-commit hooks (local)

- `ruff` / format
- `mypy` / `pyright`
- Frontend lint / typecheck
- Import boundary checks
- OpenAPI generation drift check

### B) CI required checks (server-side hook)

- Lint / type / test (backend + frontend)
- Boundary enforcement
- Contract drift enforcement
- Migration sanity

These are the real guardrails that keep cloud agents honest.

---

## 6) Commands: define a single canonical interface for agents

Create a Makefile (or justfile) and document these commands in a rule so agents always use the same verbs.

#### `.cursor/rules/50-commands-and-checks.mdc` (Always or Auto Attached)

```md
---
alwaysApply: true
---

# Canonical Commands

Always use these commands (no ad-hoc scripts):

- make bootstrap
- make dev
- make lint
- make typecheck
- make test
- make contract   # OpenAPI -> generated TS
- make boundaries # import-linter/boundary enforcement
- make migrate    # apply migrations
- make seed       # seed reference data for local
```

---

## 7) Subagents: how to operationalize in Cursor

Use "subagents" as role-constrained execution patterns.

### Recommended role split (one agent per PR)

- **Architect / Planner Agent** — produces plan only (files, tests, gates, migration impact).
- **Implementer Agent** — executes plan, writes code + tests.
- **Refactor / Hardening Agent** — improves structure, docs, naming, boundary compliance.
- **Verification Agent** — runs commands, checks drift, reviews invariants.

Enforce this operationally by writing issues that contain:

1. A "Plan required" section
2. An "Execution prompt" section
3. A "Verification gates" section

(Your GitHub issue template becomes the subagent coordinator.)

---

## 8) Cursor usage patterns that work on complex repos

### Plan-first discipline

In Cursor, ask the agent to output a plan with:

- File list
- Invariants touched
- Tests to add
- Commands to run

Only then allow implementation.

### Force correct context attachment

When starting work on an issue, open:

- The relevant module directory
- The relevant docs file(s)
- The relevant workflow definition (if applicable)

This increases Cursor's automatic context quality.

### Prevent "pattern drift"

When you accept a new pattern, update:

- A `/docs/standards/*` file
- The relevant `.cursor/rules/*.mdc` file
- The Makefile gates (if enforceable)

---

## 9) Minimal "Cursor Setup Checklist" (do this once)

1. Create `.cursor/rules/` and add the rules files above.
2. Add the `/docs/*` reference docs to Cursor Docs indexing (so you can `@Docs` them).
3. Implement Makefile canonical commands and ensure they pass on a clean repo.
4. Make CI required checks match Makefile commands exactly.
5. Create a GitHub issue template that includes an "Agent Execution Prompt" and "Closure Gates".

---

## 10) What this setup prevents

- Cross-module entanglement (rules + boundary checks)
- Workflow engine becoming a domain dumping ground
- Ledger postings being mutated after posting
- UI slowness from querying transactional tables
- Contract drift between backend and frontend
- Agents inventing their own command vocabulary and skipping gates
