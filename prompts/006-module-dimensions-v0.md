Implement modules/dimensions as a first-class reference model.

Tables:
- site
- cost_center
- business_unit (at minimum: MachiningRepair, IndustrialProducts, Corporate, Owner)
Optional stubs (create but can keep unused): department, work_center

Requirements:
- CRUD APIs for reference data (can be admin-only; auth can be stubbed for now)
- Validation helpers used by other modules (e.g., validate_cost_center_id)
- Seed mechanism for dev (fixtures)

Deliver:
- models, schemas, services, api routes, migrations
- tests for validation and CRUD
- docs: /docs/domain/DIMENSIONS.md
