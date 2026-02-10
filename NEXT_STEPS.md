# Nexus ERP — Next Steps

**Date:** 2026-02-10
**Basis:** Full review of ASSESSMENT.md, all docs, Cursor rules, agent playbooks, prompts 000–016, and Epicor COA investigation.

---

## Current State Summary

The project is **documentation-complete, code-zero**. You have:

- 17 build prompts (000–016) in correct dependency order
- 14 docs covering architecture, business context, accounting model, workflows, and more
- 12 Cursor rules (always-apply, glob-attached, and agent-requested playbooks)
- A thorough pre-build assessment with 13 tracked decisions (5 decided, 8 open)
- A completed Epicor COA investigation that directly informs the most critical open decision (D1)

No application code, no backend, no frontend, no migrations, no tests exist yet.

---

## What's Ready to Build (No Blockers)

These milestones can begin immediately:

| Milestone | Prompt | Status |
|-----------|--------|--------|
| **M0 — Scaffold** | `001` | Ready. All decisions resolved (sync SQLAlchemy, MinIO for docs). |
| **M1 — Platform Core** | `003`, `004`, `005` | Ready. DB sessions, settings, logging, errors, outbox, projections framework. |

M0 is the first thing to execute. It produces the monorepo structure, tooling, docker-compose, CI, boundary enforcement, and the hello-world endpoint. Everything else depends on it.

---

## Open Decisions That Must Be Resolved

### D1: Chart of Accounts Schema — EFFECTIVELY RESOLVED

**Status: Ready to decide. The Epicor COA investigation (`docs/investigations/EPICOR_COA_INVESTIGATION.md`) provides all the data needed.**

The investigation extracted the full Epicor COA structure:
- 271 natural accounts (Segment 1) across 26 categories in a parent-child hierarchy
- 5 divisions (Segment 2): CO, IP, MS, OF, YE — maps to `business_unit` dimension
- 8 sub-accounts (Segment 3): work centers — maps to `cost_center` dimension
- 568 GL account combinations (504 active)

Three options were analyzed. **Option B (Normalize)** is recommended:
- `account` table: 271 natural accounts with `account_number`, `name`, `category_id`, `normal_balance`, `active`, `external_id`
- `account_category` table: 26 categories with hierarchy (`parent_category_id`), `statement_type` (B/I), `normal_balance`, `is_net_income`
- Journal lines carry `account_id` + dimension IDs (already designed) + nullable `sub_ledger_type` for future AR/AP
- Option C (combination validation rules) deferred — additive, no schema changes needed later

**Action needed:** Accept or reject Option B. If accepted, update prompt `007` with the specific schema from the investigation. This is a 15-minute decision.

### D2: Party Module — NEEDS DECISION

**Status: Open. HIGH priority. Blocks M2.**

Every downstream module references `customer_id` or `vendor_id` (`jobshop`, `invoicing`, future purchasing/shipping). Without a `party` module, agents will invent incompatible customer representations.

**Recommendation:** Build a thin `party` module alongside dimensions in M2. Minimum schema:

```
party:
  id: UUID (PK)
  party_number: VARCHAR(20) (unique, from Epicor CustNum/VendorNum)
  name: VARCHAR(200)
  type: ENUM (customer, vendor, both)
  active: BOOLEAN
  external_id: VARCHAR(50) (Epicor CustID/VendorID for migration)
  created_at: TIMESTAMPTZ
  updated_at: TIMESTAMPTZ
```

The Epicor reference export agent prompt (`docs/investigations/EPICOR_REFERENCE_EXPORT_AGENT_PROMPT.md`) is already written and ready to run against Kinetic to extract customer/vendor data. This would validate the schema design.

**Action needed:**
1. Decide yes/no on building `party` in M2.
2. If yes, write a thin prompt (insert as `006b` or renumber) and add it to the build sequence.
3. Optionally: run the Epicor export agent to get customer/vendor data for schema validation.

### D8–D12: Lower Priority Open Items

These don't block the first 4 milestones but should be tracked:

| # | Decision | Blocking | Recommendation |
|---|----------|----------|----------------|
| D8 | Rental fleet — explicitly deferred? | — | **Defer and document.** Add one line to `BUSINESS_CONTEXT.md`: "Equipment rentals are post-Epicor scope." |
| D9 | Notification platform service | — | **Defer.** It's a pure outbox consumer — additive, no rework. Add to module map as "future." |
| D10 | Reporting / BI strategy | M5 | **Decide by M2.** If period-close snapshots or materialized rollups are needed, the ledger schema should accommodate them. The account_category hierarchy from the COA investigation helps here — it provides the structure for financial statements. Recommendation: PostgreSQL views on read models for V1; evaluate external BI tool later. |
| D11 | Frontend component library | M4 | **Decide by M3.** Recommendation: shadcn/ui (Radix primitives + Tailwind). It's the most common choice for internal apps with forms/tables/workflow UIs, has excellent TypeScript support, and works well with Next.js App Router. |
| D12 | Search strategy | M4 | **Decide by M3.** Recommendation: PostgreSQL `tsvector` on read model tables. Sufficient for V1 (search by job number, customer name, PO number). No external search infrastructure needed. |

---

## Recommended Execution Sequence

### Phase 1: Resolve Remaining Blockers (1-2 hours)

1. **Accept D1 (COA schema).** The investigation has done the work. Accept Option B, update prompt `007` with the specific `account` and `account_category` schema from the investigation report, and add `sub_ledger_type` to `journal_line`.

2. **Decide D2 (party module).** Write a thin prompt for `party` if accepted. Insert into build sequence at M2.

3. **Decide D8 (rental fleet deferral).** One sentence in `BUSINESS_CONTEXT.md`.

4. **Optionally run the Epicor export agent** to extract customer/vendor/period data and validate party + accounting period schemas.

### Phase 2: M0 — Scaffold (Prompt 001)

This is the first code-producing milestone. It creates:

- Full monorepo directory structure (`backend/`, `frontend/`, `docs/`, `.cursor/`)
- `backend/app/main.py` + FastAPI wiring
- `backend/app/platform/` stubs (DB, settings, logging)
- `backend/app/modules/` and `backend/app/workflows/` directories
- `frontend/` with Next.js App Router setup
- `docker-compose.yml` (PostgreSQL + Redis + MinIO)
- `Makefile` with canonical commands (`bootstrap`, `dev`, `lint`, `typecheck`, `test`, `contract`, `boundaries`, `migrate`, `seed`)
- CI workflow (GitHub Actions)
- Boundary enforcement (import-linter or equivalent)
- Pre-commit hooks
- Hello-world endpoint (backend) + minimal UI page calling it (frontend)

**Verification:** `make bootstrap && make lint && make typecheck && make test`

### Phase 3: M1 — Platform Core (Prompts 003, 004, 005)

Three sub-milestones, executed sequentially:

1. **Platform core utilities (003):** DB session management (sync SQLAlchemy), settings (Pydantic), structured logging, error model. This is the foundation everything else imports.

2. **Outbox (004):** Outbox table, publisher utility, Celery worker, retry/backoff, poison handling. This enables the event-driven architecture.

3. **Projections framework (005):** Projection handler registration, worker integration, rebuild CLI, example `rm_workflow_instance_summary` table. This enables the read-model pattern.

**Verification:** `make lint && make typecheck && make test && make migrate`

### Phase 4: M2 — Reference Data + Ledger (Prompts 006, 006b?, 007)

This is the most critical domain milestone. Order matters:

1. **Dimensions (006):** Site, cost_center, business_unit tables + CRUD + validation helpers + seed data. The Epicor investigation provides the seed data (5 divisions, 8 work centers).

2. **Party (006b, if accepted):** Thin customer/vendor table + CRUD + validation. Epicor export provides seed data.

3. **Ledger (007, updated with COA investigation schema):** Account + account_category + accounting_period + journal_entry + journal_line. Immutability enforcement, balanced posting, period close, adjusting entries. Seed the 271 accounts and 26 categories from Epicor data.

**Verification:** `make lint && make typecheck && make test && make migrate && make seed`

### Phase 5: M3 — Workflow Engine (Prompt 008)

YAML-based workflow definitions, compile/validate at startup, `workflow_instance` table with optimistic locking, `workflow_event` table with idempotency, transition log, override support, API endpoints.

**Verification:** `make lint && make typecheck && make test && make migrate`

### Phase 6: M4 — First Workflow E2E (Prompts 009, 010)

1. **Job shop module (009):** Domain tables (job, routing, operation, qa_record, shipment_stub), service layer, public API.

2. **MR Job Shop workflow (010):** Full state machine (DraftScope → ... → Closed), guards, projections, outbox events, minimal frontend screen.

MaterialsAllocated is a manual confirmation event (already decided, D4).

**Verification:** Full gate suite + manual walkthrough of the workflow UI.

### Phase 7+: M5–M7

- **M5:** Invoicing + ledger integration (prompt 011)
- **M6:** RBAC (prompt 012)
- **M7:** Contract discipline hardening (013), tech debt gates (014), project management (015), open questions capture (016)

---

## GitHub Issues: Suggested First Batch

Once D1 and D2 are decided, create these issues for M0 and M1:

### M0 — Scaffold

| # | Title | Prompt | Labels |
|---|-------|--------|--------|
| 1 | Scaffold monorepo: backend + frontend directory structure | 001 | `type/chore`, `platform/scaffold`, `priority/p0` |
| 2 | Docker Compose: PostgreSQL + Redis + MinIO | 001 | `type/chore`, `platform/infra`, `priority/p0` |
| 3 | Makefile with canonical commands | 001 | `type/chore`, `platform/scaffold`, `priority/p0` |
| 4 | CI: GitHub Actions for lint/type/test/contract/boundaries | 001 | `type/chore`, `platform/ci`, `priority/p0` |
| 5 | Boundary enforcement: import-linter setup | 001 | `type/chore`, `platform/boundaries`, `priority/p0` |
| 6 | Hello-world endpoint + frontend page | 001 | `type/feature`, `priority/p1` |

### M1 — Platform Core

| # | Title | Prompt | Labels |
|---|-------|--------|--------|
| 7 | Platform: sync DB session management + get_db dependency | 003 | `platform/db`, `priority/p0` |
| 8 | Platform: Pydantic settings + structured logging | 003 | `platform/settings`, `priority/p0` |
| 9 | Platform: standardized error model + handlers | 003 | `platform/errors`, `priority/p0` |
| 10 | Platform: outbox table + publisher + Celery worker | 004 | `platform/outbox`, `priority/p0` |
| 11 | Platform: projections framework + rebuild CLI | 005 | `platform/projections`, `priority/p0` |

---

## Prompt Updates Needed

Based on the Epicor COA investigation, these prompts should be updated before execution:

### Prompt 007 (Ledger) — Update account schema

Replace the minimal `account` table with the specific schema from the investigation:

- `account`: `id`, `account_number` (VARCHAR(20), unique), `name`, `description`, `category_id` (FK), `normal_balance` (D/C), `active`, `external_id`, `created_at`, `updated_at`
- Add `account_category` table: `id` (VARCHAR(20), natural key), `name`, `statement_type` (B/I), `normal_balance`, `parent_category_id`, `sequence`, `is_net_income`
- Add `sub_ledger_type` (nullable VARCHAR(20)) to `journal_line`
- Add seed data instructions: 271 accounts from Epicor Segment 1, 26 categories from Epicor account categories

### Prompt 006 (Dimensions) — Update seed data

Add specific seed values from the Epicor investigation:
- Business units: CO (Corporate), IP (Industrial Products), MS (Machine Shop), OF (Officer/Owner), YE (Year End Adjustments — flag as `is_adjustment`)
- Cost centers / sub-accounts: ALLO, FDSV, FSTX, GRIN, MILL, RAIG, TURN, WELD

### New Prompt 006b (Party) — Write if D2 accepted

Thin party module with customer/vendor CRUD, validation helpers, and Epicor migration fields.

### Prompt 002 (Module Map) — Add party module

If D2 is accepted, add `party` to the module map with ownership, events, and dependency relationships.

---

## Risk Summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| COA schema wrong for Epicor data | HIGH | **Mitigated.** Investigation complete, schema validated against real data. |
| Party module missing → ad-hoc customer handling | HIGH | Decide D2 now. 15-minute decision. |
| Epicor reference data not exported (customers, vendors, periods) | MEDIUM | Run the export agent prompt (already written). Validates party + period schemas. |
| Frontend component library not chosen → inconsistent UI in M4 | LOW | Decide by M3. Recommend shadcn/ui. |
| Reporting needs not defined → missing period-close snapshots | LOW | Decide by M2. Category hierarchy from COA investigation covers financial statement structure. |

---

## TL;DR — The Critical Path

```
1. Accept D1 (COA schema — Option B from investigation)     ← 15 min decision
2. Decide D2 (party module — recommend yes)                  ← 15 min decision
3. Update prompts 006, 007 with Epicor data                  ← 30 min
4. Execute M0 (scaffold)                                     ← first code
5. Execute M1 (platform core)
6. Execute M2 (dimensions + party? + ledger)
7. Execute M3 (workflow engine)
8. Execute M4 (first workflow E2E)                            ← first real user value
```

Steps 1–3 are pre-code. Steps 4–8 are the build. Each milestone is one or more GitHub issues, each issue is one agent, each agent produces one PR.
