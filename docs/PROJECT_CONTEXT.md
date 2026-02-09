# Project Context — Atlas ERP Replacement

This project is a custom, internal ERP system for Atlas Machine and Supply.

Goal:
Replace Epicor first (ERP/MRP/GL/Jobs), then Salesforce later. This is not a SaaS product. It is a single-tenant, internal system optimized for determinism, speed, and correctness.

## Source system

Atlas currently runs **Epicor Kinetic ERP (cloud, latest version)**. This is the system being replaced. Key implications:
- Epicor Kinetic exposes REST APIs and BAQs (Business Activity Queries) for data export — useful for migration and schema validation.
- The chart of accounts, site list, cost centers, customer/vendor master, and job history all live in Kinetic and will need to be exported for cutover.
- Schema design for Nexus reference data (accounts, dimensions, party) should be validated against Epicor Kinetic exports to avoid lossy transformation at cutover time.

## Key constraints

- Single database forever
- Big-bang cutover from Epicor Kinetic
- All financial amounts are USD (no multi-currency)
- Internal use only (no regulatory compliance burden)
- Must feel extremely fast to users
- Heavy use of AI coding agents → architecture must be explicit and enforceable

This system is workflow-driven, event-oriented, and modular by design.
