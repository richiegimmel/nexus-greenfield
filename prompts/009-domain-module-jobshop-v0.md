Implement modules/jobshop as the domain module for Machining & Repair job shop work.

Owns tables (thin v0):
- job (customer_id, site_id, cost_center_id, status, description)
- routing (job_id)
- operation (routing_id, sequence, work_center_id, status)
- qa_record (job_id, status, notes)
- shipment_stub (job_id, status)  # keep thin; real shipping module later can own shipping docs

Rules:
- Domain invariants enforced in service layer (e.g., cannot mark QA approved if required ops incomplete)
- No workflow orchestration in this module; expose public service API functions used by workflow module.

Expose (public API from __init__.py):
- create_job()
- update_estimate()
- mark_scheduled()
- start_work()
- complete_operation()
- approve_qa()
- mark_ready_to_ship()

Deliver:
- module code + migrations
- API routes for minimal operations (primarily for testing/driving UI)
- tests for invariants
- docs: /docs/domain/JOBSHOP.md
