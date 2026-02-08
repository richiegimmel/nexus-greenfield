# Engineering Principles (Non-Negotiable)

1. **Determinism**
   Same inputs and events must always produce the same result.

2. **Auditability**
   History must be append-only. Corrections are new facts, not edits.

3. **Explicitness**
   No hidden coupling. No magic behavior. No implicit state transitions.

4. **Modularity**
   Each module owns its data and rules. No cross-module leakage.

5. **Speed**
   UI reads from projections/read models, not transactional tables.

6. **Testability**
   Every behavior change must be covered by tests.

7. **AI-first development**
   Patterns must be codified so agents can replicate them consistently.
