# Frontend Contract Model

OpenAPI is the single source of truth.

Rules:
- Backend defines schema
- Frontend uses generated types and client
- No handwritten API types
- CI fails on drift

Frontend state:
- Server is authoritative
- Workflow instance state drives UI
- Optimistic UI allowed only where explicitly defined
