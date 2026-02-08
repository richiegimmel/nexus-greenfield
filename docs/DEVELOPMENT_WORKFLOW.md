# Development Workflow — GitHub + Cursor AI for a Modular Monolith ERP

This document defines the development workflow for building the Atlas ERP replacement using GitHub + Cursor with local and cloud AI agents. It assumes:
- Modular monolith architecture
- Workflow/state-machine core
- Append-only ledger postings
- Projections/read models for speed
- OpenAPI as source of truth
- CI-enforced boundaries and drift gates

---

## 1) Canonical Sources of Truth

### Architecture and constraints
- `/docs/PROJECT_CONTEXT.md`
- `/docs/ARCHITECTURE_OVERVIEW.md`
- `/docs/MODULE_CONCEPTS.md`
- `/docs/WORKFLOWS_AND_STATE.md`
- `/docs/ACCOUNTING_MODEL.md`
- `/docs/READ_MODELS_AND_PERFORMANCE.md`
- `/docs/FRONTEND_CONTRACT_MODEL.md`

### Code truth
- Backend OpenAPI is the API contract truth
- Ledger module is the financial truth
- Workflow engine transition log is the state-history truth
- Read models are the UI query truth (default UI reads)

No agent is permitted to “imply” rules not present in these documents or code.

---

## 2) Repo Operating Model

### Branch model
- `main`: always releasable
- `feature/<issue-number>-<short-name>`: all work happens here
- `hotfix/<issue-number>-<short-name>`: production fixes only (if/when you get there)

### PR size rule
- Prefer small PRs. One concept per PR.
- If a PR touches multiple modules, it must be justified and documented.

### Definition of Done (DoD)
A PR is “done” only if:
- Tests added/updated for the change
- CI passes (lint/type/tests/contract/boundaries)
- Docs updated if patterns changed
- Migrations included (if schema changes)
- Rollback notes included (how to revert safely)

---

## 3) GitHub Project Management Workflow

### Labels (recommended)
- `type/feature`, `type/bug`, `type/chore`, `type/docs`
- `module/<name>` (e.g., `module/ledger`, `module/dimensions`, `module/jobshop`)
- `workflow/<name>` (e.g., `workflow/mr_job_shop`)
- `platform/<area>` (e.g., `platform/outbox`, `platform/projections`)
- `priority/p0`, `priority/p1`, `priority/p2`
- `risk/high`, `risk/med`, `risk/low`

### Issue template (mandatory content)
Each issue must contain:
- Context (what/why)
- Acceptance criteria (testable)
- Constraints (module boundaries, immutability, determinism, etc.)
- Tests required
- “Agent Execution Prompt” (copy/paste prompt tailored to the repo)
- Closure gates (commands to run, checks that must pass)

### Milestones (suggested)
- M0 Scaffold & Enforcement
- M1 Platform Core (outbox/projections)
- M2 Dimensions + Ledger
- M3 Workflow Engine Hardening
- M4 First Workflow E2E
- M5 Invoicing + Ledger Integration
- M6 RBAC
- M7 Cutover prep + Hardening

---

## 4) Cursor Configuration Workflow

### Project rules: make the repo self-explaining
Create and maintain:
- `/docs/*` as canonical context
- A small, strict rule file for agents (Cursor rules)
- A “how we do things” doc that agents must follow:
  - `/docs/standards/ENGINEERING_RULES.md`
  - `/docs/architecture/MODULE_MAP.md`

### Cursor best-practice setup
- Keep rules short and enforceable (CI does the heavy lifting).
- Always link agents to:
  - module boundaries
  - contract generation
  - projections-first read strategy
  - immutability rules
  - workflow determinism and concurrency rules

### Agent scope discipline
- One agent per issue.
- One PR per issue.
- Agents imply changes via a plan first, then execute.

---

## 5) The Standard “AI-Driven Implementation Loop”

### Step 1 — Create/Select a GitHub issue
Issue must be fully specified (acceptance criteria + tests + closure gates).

### Step 2 — Agent creates an implementation plan (no code yet)
Plan must include:
- files to change
- migrations (if any)
- tests to add
- API changes and whether OpenAPI impacts generated client
- module boundary considerations
- projection/read-model implications
- rollback strategy

### Step 3 — Agent implements in small commits
Commit strategy:
- Commit 1: scaffolding/structure (no behavior)
- Commit 2: schema/migrations
- Commit 3: core behavior + unit tests
- Commit 4: API wiring + contract regen checks
- Commit 5: projections + performance read path
- Commit 6: docs update

### Step 4 — Local verification gates (before PR)
Run the repo’s canonical checks (examples; adapt to your tooling):
- `make lint`
- `make typecheck`
- `make test`
- `make contract` (OpenAPI → TS generation)
- `make boundaries` (import rules)
- `make migrate` (if schema changed)

### Step 5 — Open PR with strict template
PR must contain:
- scope summary
- acceptance criteria checklist
- tests added and how to run
- migrations and safety notes
- rollback plan
- docs updated

### Step 6 — Automated review gates
CI must enforce:
- formatting + lint
- type checks
- tests
- contract drift (generated client up to date)
- module boundary enforcement
- migration sanity (at least applies cleanly)

### Step 7 — Human review (you)
You are not reviewing “style.” You are reviewing invariants:
- module ownership respected
- ledger immutability preserved
- workflow engine determinism preserved
- optimistic locking present where required
- projections used for UI read paths
- API contract discipline enforced

### Step 8 — Merge
Squash merge preferred if it keeps history clean; otherwise retain commits if they map to logical steps.

---

## 6) Patterns That Must Be Enforced (Operational Rules)

### Module boundary rule
- Only import other modules via their public exports.
- No shared ORM relationships across modules.
- Cross-module is events/read models, not direct writes.

### Workflow rule
- Workflows orchestrate, modules own domain rules.
- Workflows never reach into module tables directly.
- Transition history append-only.

### Ledger rule
- Posted entries immutable.
- Corrections are reversals/new entries.
- Every financially impactful workflow event must produce ledger postings (directly or via outbox consumer).

### Performance rule
- Default UI reads from read models (projections).
- Transactional reads only for drilldown or command validation.

### Contract rule
- OpenAPI is the source of truth.
- TS client/types are generated; no handwritten API typing.

---

## 7) Handling Concurrency and Fast UX

### Concurrency (write path)
- Every workflow event ingestion uses:
  - `expected_version`
  - `idempotency_key`
- Conflicts return 409 with the current state/version.

### Fast UX (read path)
- UI consumes read model endpoints:
  - lists, dashboards, status pages
- After a command:
  - return updated instance summary
  - update projection quickly (sync or near-sync)
- Never “poll transactional tables” as a primary UI mechanism.

---

## 8) Managing Multiple Agents Without Chaos

### Parallelism policy
Parallel work is allowed only if issues do not overlap on:
- the same module internals
- the same migrations
- the same contract surface

If overlap is unavoidable:
- serialize work by milestone (one foundational PR first)
- then branch off the stabilized base

### Conflict avoidance
- Reserve migrations to one active PR at a time when possible.
- If unavoidable, enforce a migration rebase workflow:
  - rebase feature branch
  - regenerate migrations if needed
  - rerun full gate suite

### Review load shedding
Push complexity into:
- deterministic gates (CI)
- enforceable rules (boundary checks)
- small PRs

---

## 9) Cutover Preparation Workflow (Big-Bang)

### Cutover is a milestone, not an afterthought
Create a dedicated “Cutover” milestone with:
- data migration plan
- reconciliation checks
- freeze window runbook
- rollback plan

### Required cutover artifacts
- Migration scripts (repeatable, idempotent)
- Validation reports:
  - counts, totals, balances by dimension
  - ledger trial balance comparisons
- A dry-run procedure you can execute end-to-end

---

## 10) Practical “Daily Operating Loop”

1. Pick the next issue from the milestone board.
2. Ensure the issue has acceptance criteria + agent prompt + closure gates.
3. Run an agent for plan-only first.
4. Approve plan; agent implements.
5. Run local gates.
6. Open PR.
7. Merge only if CI + invariant review passes.

---

## Appendix: Minimal PR Checklist (copy into PR template)

- [ ] Scope limited to one issue
- [ ] Module ownership respected (no cross-module internals)
- [ ] Tests added/updated
- [ ] Migrations included and safe
- [ ] Contract regen run; no drift
- [ ] Projections/read models used for UI reads
- [ ] Workflow determinism + optimistic locking preserved
- [ ] Ledger immutability preserved
- [ ] Docs updated (if pattern changed)
- [ ] Rollback plan included
