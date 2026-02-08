# Project Context — Atlas ERP Replacement

This project is a custom, internal ERP system for Atlas Machine and Supply.

Goal:
Replace Epicor first (ERP/MRP/GL/Jobs), then Salesforce later. This is not a SaaS product. It is a single-tenant, internal system optimized for determinism, speed, and correctness.

Key constraints:
- Single database forever
- Big-bang cutover from Epicor
- Internal use only (no regulatory compliance burden)
- Must feel extremely fast to users
- Heavy use of AI coding agents → architecture must be explicit and enforceable

This system is workflow-driven, event-oriented, and modular by design.
