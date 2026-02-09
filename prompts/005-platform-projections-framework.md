Implement a projections/read-model framework in platform:
- A standard way to define projections (handlers) that consume domain/workflow events
- A worker (Celery) that updates read-model tables from outbox events
- A rebuild mechanism for projections (CLI command or management script) for dev

Deliver:
- platform/projections/*
- example projection table: rm_workflow_instance_summary
  fields: instance_id, workflow_name, current_state, updated_at, last_event_type, last_actor, version
- APIs to query this read model efficiently
- tests for projection updates and rebuild behavior
- docs: /docs/architecture/PROJECTIONS.md
