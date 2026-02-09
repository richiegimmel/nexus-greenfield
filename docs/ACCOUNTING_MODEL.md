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

## Currency

**All financial amounts are USD. Multi-currency is not in scope.**

There are no `currency_code` or `exchange_rate` fields on journal lines. If multi-currency is ever needed in the future, it would be introduced as a new schema version — but that is not a current or planned requirement.

## Accounting-Grade Immutability

This is accounting-grade immutability, even if regulatory compliance is not required.
