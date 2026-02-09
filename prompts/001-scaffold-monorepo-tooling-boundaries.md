Scaffold a production-grade modular monolith monorepo.

Backend:
- FastAPI + Pydantic + SQLAlchemy + Alembic
- Postgres
- Redis + Celery
- Strict module boundaries

Required backend layout:

backend/app/
  main.py
  api/                    # composition only (wires routers)
  platform/               # db, settings, logging, auth/rbac, outbox, projections framework
  modules/
    <module_name>/
      __init__.py         # public API exports only
      models.py
      schemas.py
      service.py
      api.py              # module router
      events.py
      tests/
  workflows/
    engine/
    <workflow_name>/
      definition.yaml
      guards.py
      projections.py
      tests/

Frontend:
- Choose Next.js App Router, client-first. Do not rely on SEO/SSR.
- Feature modules aligned to backend modules:
  frontend/src/modules/<module_name>/*
- API client/types generated from backend OpenAPI:
  frontend/src/api/generated/*

Tooling:
- Python: ruff, mypy/pyright, pytest
- JS/TS: eslint, prettier, typecheck, test runner (vitest/jest)
- pre-commit
- GitHub Actions CI runs: backend lint/type/tests, frontend lint/type/tests, contract generation drift check, boundary enforcement check.
- docker-compose for local Postgres + Redis + MinIO (S3-compatible object storage for documents)

Deliver:
1) Full directory structure
2) All config files
3) Minimal hello endpoint (backend) + minimal UI page calling it (frontend)
4) Boundary enforcement mechanism (import-linter or equivalent) + CI integration
5) Makefile/justfile with common commands
