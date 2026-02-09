Add enforcement gates:
- PR template with required sections: scope, acceptance criteria, tests, migrations, rollback, docs, contract regen
- Required CI checks for merge
- Coverage reporting with a conservative minimum threshold
- ADR system: /docs/adr/0000-template.md and rule: any cross-cutting pattern requires ADR
- Engineering rules file: /docs/standards/ENGINEERING_RULES.md (module boundaries, immutability, projections, contract rules)

Deliver:
- templates + CI config + docs
- boundary violation should fail CI deterministically
