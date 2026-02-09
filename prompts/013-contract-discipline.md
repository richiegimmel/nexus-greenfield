Enforce strict API contract workflow:
- Backend OpenAPI is source of truth
- Generate TypeScript types + client into frontend/src/api/generated
- No handwritten API types or clients allowed
- CI fails if generated output differs from repo state

Deliver:
- generation scripts
- CI gate
- docs: /docs/standards/API_CONTRACT.md
- example frontend usage calling workflow endpoints with full type safety
