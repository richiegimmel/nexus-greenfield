# Modules: First-Class Concept

A module is a packaging and ownership boundary inside the monolith.

A module owns:
- Its database tables
- Its domain invariants
- Its service APIs
- Its tests

A module does NOT:
- Reach into another module’s internals
- Own workflow orchestration
- Share ORM relationships with other modules

Cross-module interaction happens via:
- Workflow events
- Public module APIs
- Read models / projections

Examples:
- modules/jobshop
- modules/ledger
- modules/dimensions
- modules/invoicing
