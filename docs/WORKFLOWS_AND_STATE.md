# Workflows and State Machines

Workflows are explicit state machines that orchestrate domain modules.

They:
- Define states, events, guards, transitions
- Are deterministic
- Persist transition history
- Support overrides with justification

They do NOT:
- Own domain tables
- Embed business rules that belong in modules
- Mutate data directly outside module APIs

Concurrency:
- Workflow instances use optimistic locking
- Clients pass expected_version
- Conflicts return 409

Overrides:
- First-class events
- Require reason and RBAC permission
