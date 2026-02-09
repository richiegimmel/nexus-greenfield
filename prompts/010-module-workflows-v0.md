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
