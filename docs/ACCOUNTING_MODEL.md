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

## Accounting periods

Nexus uses explicit **accounting periods** (e.g., monthly) to support period close.

- Every posted journal entry belongs to exactly one accounting period.
- The period is determined by `entry_date` (the effective date of the entry).
- Periods are defined by an inclusive date range: `start_date` → `end_date`.

## Period close and adjusting entries

Accounting periods can be **closed**. A closed period is:

- **Closed to normal posting**: you cannot post regular entries into a closed period.
- **Open to explicit adjustments**: you may post **adjusting entries** into a closed period, but only when they are explicitly marked and justified.

Adjusting entries rules:

- Adjusting entries are still fully immutable once posted (no edits/deletes).
- An adjusting entry must set `is_adjusting = true` and include a non-empty `adjusting_reason`.
- Posting into a closed period is permitted **only** for adjusting entries (future: gated by RBAC).

## Currency

**All financial amounts are USD. Multi-currency is not in scope.**

There are no `currency_code` or `exchange_rate` fields on journal lines. If multi-currency is ever needed in the future, it would be introduced as a new schema version — but that is not a current or planned requirement.

## Accounting-Grade Immutability

This is accounting-grade immutability, even if regulatory compliance is not required.
