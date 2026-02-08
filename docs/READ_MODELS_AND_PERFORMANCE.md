# Read Models and Performance Strategy

Transactional tables are NOT optimized for UI queries.

Pattern:
- Write path: domain modules + workflows
- Read path: projections/read models

Characteristics:
- Read models are rebuilt from events
- Optimized for specific screens
- Safe to denormalize
- Fast to query

UI rules:
- Default to read models
- Only hit transactional APIs for commands or drill-downs
