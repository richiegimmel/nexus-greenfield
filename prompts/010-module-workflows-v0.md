Implement workflows/mr_job_shop as an orchestration workflow for job shop manufacturing.

States (v0):
- DraftScope
- Estimating
- Quoted
- CustomerPOReceived
- MaterialSourcing
- Scheduled
- InProcess
- QAComplete
- Shipped
- Invoiced
- Closed
Terminal: Cancelled, OnHold

Events:
- ScopeDefined
- EstimateUpdated
- QuoteIssued
- CustomerPOAttached
- MaterialsAllocated
- Scheduled
- WorkStarted
- OperationCompleted
- QAApproved
- ShipmentCreated
- InvoiceIssued
- Closed
- HoldPlaced
- HoldReleased
- Cancelled
- OverrideTransition (requires reason, permission)

Guards:
- cannot Scheduled unless MaterialsAllocated OR override
- cannot Shipped unless QAApproved OR override
- cannot Invoiced unless ShipmentCreated OR override

MaterialsAllocated stub strategy (M4):
- There is no inventory or purchasing module yet. For M4, MaterialsAllocated is a **manual confirmation event** — the user explicitly fires it to indicate "materials are ready."
- The guard checks whether a MaterialsAllocated event exists in the workflow transition history, NOT actual inventory levels.
- This keeps M4 achievable without building inventory infrastructure.
- When a real inventory module is built later, MaterialsAllocated will be replaced by (or supplemented with) an automated event from inventory allocation. The guard signature does not need to change — only the event source changes.
- Do NOT invent a temporary inventory table or mock allocation service. The manual event IS the intended V0 design.

Implementation requirements:
- workflow transitions call jobshop public APIs only (no direct table writes)
- emit outbox events for downstream modules (invoicing/ledger integration later)
- projection updates: ensure rm_workflow_instance_summary updates

Deliver:
- definition.yaml
- guards.py
- projections.py
- tests: happy path + 3 failure/hold/override paths
- minimal frontend screen to create instance, apply events, show state/history
