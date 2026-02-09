You are working in a clean repo for an internal ERP replacement (Epicor first; Salesforce later). Company has 4 business units: Machining & Repair, Industrial Products, Corporate, Owner. Single database forever. Big-bang cutover planned.

NON-NEGOTIABLE ARCHITECTURE:
1) Modular monolith: platform → modules → workflows → API composition.
2) Each module owns its tables + domain rules + API surface. No shared “common domain”.
3) No cross-module imports of internals. Only import another module’s public API exports (from its __init__.py) or interact via events/read models.
4) No cross-module ORM relationships; reference by IDs.
5) Workflows orchestrate modules. Workflows do not own domain data.
6) Accounting postings are immutable (append-only). Corrections occur via reversals/new entries, never edits.
7) Concurrency is real: workflow transitions must support optimistic locking (expected_version) + idempotency keys.
8) Overrides are first-class: explicit override events require justification and RBAC permission.
9) UI must be extremely fast: read models/projections are first-class. UI reads read-model tables by default.
10) OpenAPI is the source of truth; frontend uses generated types/client only.

Hard requirements:
- Determinism in workflow engine: same event sequence => same final state.
- Append-only audit history (internal use is fine, but must be reliable).
- Tests with every behavior change. CI enforces boundaries + contract + tests.

Deliver outputs as:
- Files to create/modify (paths)
- Rationale (short)
- Commands to run
- Tests to add/run
- PR checklist
