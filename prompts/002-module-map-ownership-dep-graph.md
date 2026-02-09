Create /docs/architecture/MODULE_MAP.md defining v0 modules, ownership, and allowed dependencies.

Modules to include:
- platform: settings, db, logging, outbox, projections, auth/rbac primitives, documents (S3-backed file storage service)
- modules: dimensions, ledger, party, catalog, inventory, jobshop, purchasing, shipping, invoicing, gl (gl can be thin if ledger is the posting primitive)
- workflows: engine, mr_job_shop (first)

Platform service — documents:
- S3-compatible object storage (MinIO for local dev, S3 for production)
- Thin service: upload, download, delete, reference-by-ID
- Table: document (id, filename, content_type, s3_key, uploaded_by, uploaded_at, entity_type, entity_id)
- Any module can attach documents to its entities via entity_type + entity_id reference
- Not a full document management system — just structured file attachment and retrieval
- Must be defined before M4 (job shop workflow needs customer POs, drawings, inspection reports)

For each module:
- owns (tables, invariants, APIs)
- does not own
- publishes events
- consumes events
- allowed imports (platform allowed everywhere; module-to-module only via public API)

Include an ASCII dependency diagram.
