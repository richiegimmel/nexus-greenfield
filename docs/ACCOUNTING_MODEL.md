# Accounting and Financial Model

Accounting is append-only and immutable.

Key rules:
- Journal entries cannot be edited or deleted once posted
- Corrections are reversals and/or new entries
- All financial impact flows through the ledger module

Ledger characteristics:
- Balanced entries only
- Dimensions attached to every line:
  - site
  - cost_center
  - business_unit
  - (future: department, project)

This is accounting-grade immutability, even if regulatory compliance is not required.
