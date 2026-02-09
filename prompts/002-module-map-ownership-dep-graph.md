Create /docs/architecture/MODULE_MAP.md defining v0 modules, ownership, and allowed dependencies.

Modules to include:
- platform: settings, db, logging, outbox, projections, auth/rbac primitives
- modules: dimensions, ledger, party, catalog, inventory, jobshop, purchasing, shipping, invoicing, gl (gl can be thin if ledger is the posting primitive)
- workflows: engine, mr_job_shop (first)

For each module:
- owns (tables, invariants, APIs)
- does not own
- publishes events
- consumes events
- allowed imports (platform allowed everywhere; module-to-module only via public API)

Include an ASCII dependency diagram.
