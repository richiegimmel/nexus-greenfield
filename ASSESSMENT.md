# Nexus ERP — Pre-Build Assessment

**Date:** 2026-02-09
**Scope:** Full review of docs, Cursor rules, agent playbooks, and build prompts (000–016).
**Status:** Documentation and rules only — zero application code exists.

---

## 1. Project Summary

Nexus is a custom, single-tenant ERP for **Atlas Machine and Supply**, replacing Epicor first and Salesforce later. The system is a **modular monolith** (FastAPI / Next.js / PostgreSQL) with:

- Workflow-driven state machines for orchestration
- Append-only immutable ledger for financials
- Outbox-driven projections for fast UI reads
- OpenAPI as the single contract between backend and frontend
- CI-enforced module boundaries, contract drift checks, and architectural rules

The repo is designed for **AI-agent-first development** with human oversight.

### Business Units

| Unit | Type | Key Activities |
|------|------|----------------|
| Machining & Repair | Operational | Job shop mfg, repairs, field machining, metrology |
| Industrial Products | Operational | Compressed air sales, field service, parts, rentals, installs |
| Corporate | Support | HR, IT, Facilities, Marketing, Accounting, Legal |
| Owner | Support | Owner-specific expenses, GL segmentation |

### Build Sequence (from prompts)

| Milestone | Scope |
|-----------|-------|
| M0 | Scaffold monorepo, tooling, boundary enforcement |
| M1 | Platform core (DB, settings, logging, errors, outbox, projections) |
| M2 | Dimensions + Ledger modules |
| M3 | Workflow engine hardening |
| M4 | First workflow E2E (mr_job_shop) |
| M5 | Invoicing + Ledger integration |
| M6 | RBAC |
| M7 | Hardening, docs, cutover prep |

---

## 2. What Is Well-Designed (No Action Needed)

These areas are sound and do not need rework:

- **Workflow engine model.** Optimistic locking (`expected_version`), idempotency keys, append-only transition history, and first-class overrides with justification. This is a proven pattern and correctly separates orchestration from domain logic.

- **Module boundary enforcement.** Import-linter (or equivalent) with CI enforcement is the right approach, especially for AI-agent development where convention alone will drift.

- **Outbox + projections architecture.** Transactional outbox avoids dual-write problems. Projections are rebuildable, idempotent, and explicitly separate from the write path. This is the correct CQRS-lite approach for a monolith.

- **OpenAPI contract discipline.** Generated TypeScript client with CI drift detection prevents the most common frontend/backend desync failures.

- **Cursor rules structure.** The layered approach (always-apply for invariants, auto-attach by glob for contextual rules, agent-requested for playbooks) is well-organized and keeps agent context tight.

- **Prompt sequencing.** The build order (platform → reference data → ledger → workflow engine → first domain workflow → integration → RBAC → hardening) is correct. Dependencies flow in one direction.

- **Engineering principles.** Determinism, auditability, explicitness, modularity, speed, testability, and AI-first development are clearly stated and consistently reinforced across all docs.

---

## 3. Blockers and Blindspots

These are issues that, if not addressed before building, could require significant rework later.

### 3.1 Chart of Accounts — Under-specified for an Append-Only System

**Severity: HIGH**

The ledger prompt (`007`) describes `account` as "minimal chart of accounts" with no further schema detail. Because the ledger is append-only, the account structure is the **hardest thing to change retroactively** — every posted journal line references an account ID, and those entries cannot be modified.

**What breaks if ignored:**
- If accounts are flat (just `id` + `name`) and you later need a hierarchy (parent/child for rollup reporting, account groups for financial statements), you'll need to build a translation layer on top of immutable data.
- If account type classification (Asset, Liability, Equity, Revenue, Expense) isn't on the account record from the start, trial balance and financial statement generation will require external mapping tables that should have been intrinsic.
- Sub-ledger patterns (AR sub-ledger, AP sub-ledger) are common in ERP systems and affect how you post and reconcile. If not considered now, the posting API surface may need to change.

**Decision needed:**
- [ ] Obtain Epicor's current chart of accounts export (account number, description, type, group/parent, active flag).
- [ ] Decide: hierarchical accounts (parent/child) or flat with grouping via a separate `account_group` table?
- [ ] Decide: is account type (A/L/E/R/X) a field on the account record? (Recommendation: **yes**, always.)
- [ ] Decide: are sub-ledgers in scope? (Even if deferred, the posting API should accommodate a `sub_ledger_type` field from day one.)

**Recommendation:** Add `account_type` (enum: Asset, Liability, Equity, Revenue, Expense), `parent_account_id` (nullable self-reference), and `account_number` (string, from Epicor's COA) to the account table in prompt `007`. This is low cost now and extremely high cost to add later.

---

### 3.2 Party / Customer / Vendor — Referenced Everywhere, Defined Nowhere

**Severity: HIGH**

The module map prompt (`002`) lists `party` as a planned module, but no implementation prompt exists for it. Meanwhile:
- `jobshop` (`009`) has `customer_id` on the `job` table
- `invoicing` (`011`) has `customer_id` on the `invoice` table
- Industrial Products (future) will need customer and vendor references
- The ledger will need party references for AR/AP postings

**What breaks if ignored:**
- Agents building `jobshop` and `invoicing` will invent their own `customer_id` handling — bare UUIDs with no validation, no name resolution for read models, and incompatible seed data.
- When `party` is eventually built, every module that assumed its own customer representation will need to be retrofitted.
- Read models / projections that need to display customer names will have nowhere to look them up.

**Decision needed:**
- [ ] Should `party` be built as a thin stub in M2 (alongside dimensions)?
- [ ] Minimum viable `party` schema: `id`, `name`, `type` (customer/vendor/both), `active`, `external_id` (for Epicor migration)?

**Recommendation:** Add a prompt between `006` and `007` for a thin `party` module. It doesn't need to be CRM-complete — just enough to be the single source of "who is this entity" that other modules reference by ID. This follows the same pattern as `dimensions`: reference data that must exist before domain modules can be built correctly.

---

### 3.3 Sync vs Async SQLAlchemy — Undecided Fork-in-the-Road

**Severity: HIGH**

Prompt `003` explicitly says "async or sync, choose one and standardize." This decision touches **every file in the backend**: session management, service function signatures, test fixtures, Celery worker session handling, and dependency injection patterns.

**What breaks if ignored:**
- If the scaffold (prompt `001`) picks one and it's wrong, every subsequent module/workflow/test will need rewriting.
- Mixing sync and async SQLAlchemy sessions is a well-known source of bugs (event loop conflicts, session lifecycle mismatches between FastAPI request handlers and Celery workers).

**Decision needed:**
- [ ] Sync or async SQLAlchemy sessions?

**Recommendation:** Use **sync SQLAlchemy**. Rationale:
- This is a single-tenant internal system, not a high-concurrency SaaS product. The concurrency benefits of async are minimal.
- Celery workers (which handle outbox processing and projection updates) run synchronously. Mixing sync workers with async request handlers adds complexity for no benefit.
- Sync is simpler to debug, test, and reason about — important when AI agents are writing the code.
- FastAPI supports sync endpoints without issue; the performance difference at Atlas's scale is negligible.

---

### 3.4 Materials / Inventory Dependency for First Workflow E2E

**Severity: MEDIUM**

The `mr_job_shop` workflow (`010`) includes:
- A `MaterialSourcing` state
- A `MaterialsAllocated` event
- A guard: "cannot Scheduled unless MaterialsAllocated OR override"

But `inventory`, `purchasing`, and `catalog` have no implementation prompts. They appear in the module map (`002`) as planned modules only.

**What breaks if ignored:**
- M4 ("First Workflow E2E") cannot run a meaningful happy path without something to satisfy the `MaterialsAllocated` guard.
- If the guard is always-pass, it's not testing real behavior. If it requires a real inventory module, M4 is blocked on unplanned work.

**Decision needed:**
- [ ] For M4: stub material allocation as a manual flag / override, or build a thin `inventory` module?

**Recommendation:** Stub it. The `MaterialsAllocated` event should be manually triggerable (an explicit event the user fires, like "I confirm materials are ready"), with the guard checking whether that event has been recorded — not checking actual inventory levels. This keeps M4 achievable without building inventory, and the real integration can replace the manual trigger later. Document this explicitly in the `010` prompt so agents don't invent their own solution.

---

### 3.5 Multi-Currency — Not Mentioned, Could Be Structural

**Severity: MEDIUM**

The ledger has `debit` and `credit` on journal lines, but there is no mention of currency anywhere in the documentation. The dimensions doc mentions site, cost center, and business unit — but not currency.

**What breaks if ignored:**
- If Atlas ever transacts in non-USD (international vendors, foreign customer invoicing), adding currency to an append-only ledger is painful: every historical line would lack currency, and the posting API would need to change.
- Even if everything is USD today, a `currency` field with a default of `USD` is cheap insurance.

**Decision needed:**
- [ ] Is everything always USD? If yes, document this as an explicit constraint.
- [ ] If there's any possibility of multi-currency, add `currency_code` (default `USD`) and `exchange_rate` (default `1.0`) to `journal_line` in prompt `007`.

**Recommendation:** If USD-only, add a single line to `ACCOUNTING_MODEL.md`: "All financial amounts are USD. Multi-currency is not in scope." If there's any doubt, add the two fields now — they cost nothing on an empty system.

---

### 3.6 Document / File Storage — Not Addressed

**Severity: MEDIUM**

Job shop operations typically involve: engineering drawings, customer POs, shipping documents, packing slips, inspection/CMM reports, photos, certifications, and quotes (PDFs). There is no module, prompt, or even mention of file/document storage.

**What breaks if ignored:**
- Each module that needs documents (jobshop, invoicing, purchasing) will invent its own blob-reference pattern.
- Without a shared `documents` platform service, there's no consistent way to attach files to entities, manage storage lifecycle, or build file-aware read models.

**Decision needed:**
- [ ] Does Nexus need to store/manage documents?
- [ ] If yes: S3-compatible object storage with a thin `documents` platform service (upload, download, reference-by-ID)?
- [ ] If no: how are documents handled? (External system? Manual process?)

**Recommendation:** If documents are in scope, add a platform-level `documents` service to the module map (not a full module — just a utility like outbox or projections). Define it before M4, since the first workflow (job shop) will almost certainly need to reference customer POs and drawings.

---

### 3.7 Epicor Data Migration — Schema Design Should Be Migration-Aware

**Severity: MEDIUM (not blocking M0–M3, but blocking M7)**

The documentation mentions "big-bang cutover" and the development workflow doc (section 9) describes cutover artifacts, but there is no prompt for building the actual data migration pipeline. More importantly, the **schema design of ledger, dimensions, and party should be informed by what exists in Epicor** to avoid a painful mapping layer at cutover time.

**What breaks if ignored:**
- If the new COA structure is incompatible with Epicor's, the cutover migration becomes a data transformation project on top of a data migration project.
- If Epicor's site/cost center/department codes don't map cleanly to the dimensions module, reference data will need a translation layer.
- Historical financial data import (opening balances at minimum) requires the ledger schema to accommodate Epicor's structure.

**Decision needed:**
- [ ] Which Epicor version is in production? (Epicor 10 / Kinetic / Prophet 21 / other)
- [ ] Can you export the chart of accounts, site list, cost center list, and customer/vendor master now?
- [ ] What is the cutover boundary? (Opening balances only, or historical transaction import?)

**Recommendation:** Export Epicor reference data (COA, sites, cost centers, customers, vendors) early and use it to validate schema design in M2. This doesn't require building a migration pipeline — just ensuring the new schema can represent the existing data without lossy transformation.

---

## 4. Minor Items (Not Blockers, But Worth Noting)

These are lower-risk items that should be tracked but won't cause a rebuild.

### 4.1 Rental Fleet Not Addressed

Industrial Products includes "equipment rentals" in the business context. Rentals have unique lifecycle and financial patterns (recurring invoicing, depreciation, maintenance scheduling). No module or workflow prompt exists for this. This is fine if rentals are post-Epicor-replacement scope, but should be documented as an explicit deferral.

### 4.2 No Notification / Alert System

Workflow transitions (e.g., QA hold, override events, invoice issued) will likely need notifications (email, in-app). There's no mention of a notification platform service. This can be added later without rework (it's a pure outbox consumer), but should be on the module map as a future platform service.

### 4.3 Reporting / BI Strategy Not Defined

Read models serve the transactional UI, but ERP systems also need period-end financial reports, management dashboards, and potentially data warehouse exports. Whether this is handled by projections, direct SQL views, or an external BI tool should be decided before the ledger schema is finalized (it affects whether you need period-close snapshots or materialized rollups).

### 4.4 Frontend Component Library / Design System

The frontend rules mention Tailwind CSS or CSS Modules but don't specify a component library. For an internal ERP with dozens of forms, tables, and workflow UIs, a component library decision (shadcn/ui, Radix, Mantine, etc.) should be made before M4 to prevent inconsistent UI patterns across modules.

### 4.5 Search

ERP users search constantly — by job number, customer name, PO number, part number. There's no mention of search infrastructure. For V1, full-text search on read model tables (PostgreSQL `tsvector`) is probably sufficient, but it should be a conscious choice.

---

## 5. Decision Register

Summary of all decisions needed before coding begins. Mark each when decided.

| # | Decision | Severity | Blocking | Status |
|---|----------|----------|----------|--------|
| D1 | Chart of accounts schema (hierarchy, type, account_number) | HIGH | M2 | `OPEN` |
| D2 | Build thin `party` module in M2? | HIGH | M2 | `OPEN` |
| D3 | Sync vs async SQLAlchemy | HIGH | M0 | `OPEN` |
| D4 | Material allocation stub strategy for M4 | MEDIUM | M4 | `OPEN` |
| D5 | Multi-currency: USD-only or add currency fields? | MEDIUM | M2 | `OPEN` |
| D6 | Document/file storage in scope? | MEDIUM | M4 | `OPEN` |
| D7 | Epicor version and reference data export | MEDIUM | M2 | `OPEN` |
| D8 | Rental fleet — explicitly deferred? | LOW | — | `OPEN` |
| D9 | Notification platform service — future scope? | LOW | — | `OPEN` |
| D10 | Reporting / BI strategy | LOW | M5 | `OPEN` |
| D11 | Frontend component library choice | LOW | M4 | `OPEN` |
| D12 | Search strategy (pg full-text on read models?) | LOW | M4 | `OPEN` |

---

## 6. Recommended Pre-Build Actions

These should be completed before executing prompt `001`:

1. **Decide D3 (sync vs async).** This affects the scaffold structure. Recommendation: sync.
2. **Decide D1 (COA schema).** Export Epicor COA if available. At minimum, add `account_type` and `account_number` to prompt `007`.
3. **Decide D5 (currency).** Add a one-line constraint to `ACCOUNTING_MODEL.md`, or add the fields to prompt `007`.
4. **Decide D2 (party module).** If yes, write a thin prompt and insert it into the build sequence before or alongside `007`.
5. **Decide D4 (materials stub).** Add a note to prompt `010` documenting the stub strategy.
6. **Decide D6 (documents).** If in scope, add to module map. If not, document the deferral.

Items D7–D12 can be decided during the build but should be tracked.

---

## 7. Overall Assessment

**The project is in strong shape for pre-code.** The documentation quality, Cursor rules, and prompt sequencing are significantly above average. The architecture is well-reasoned, the constraints are clearly stated, and the AI-agent development model is well-supported by the tooling design.

The primary risk is not architectural — it's **under-specification of financial reference data** (chart of accounts, party, currency). These are the hardest things to change in an append-only system, and they interact with every other module. Spending a few hours on decisions D1, D2, and D5 before writing code will save weeks of rework later.

The secondary risk is the **Epicor data migration** not informing schema design early enough. The schema should be designed to receive Epicor data, not the other way around.

Everything else — the workflow engine, module boundaries, outbox/projections, contract discipline, CI enforcement — is well-designed and ready to build.
