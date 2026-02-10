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

## Period close and audit adjustments (D13 — unresolved)

We want **hard closes** so financial statements can be trusted as stable snapshots, while still supporting real-world year-end/audit adjustments.

**Current preference (Option A):** closed periods reject *all* posting; audit/year-end adjustments are handled by an explicit **reopen → post adjusting JEs → reclose** flow that produces a new close “version”.

Proposed semantics (pending final decision):

- **Hard close**: if an accounting period is `closed`, posting is rejected.
- **Reopen for adjustments** (privileged): a closed period may be temporarily reopened for audit adjustments; while reopened, only **adjusting entries** are allowed.
- **Adjusting entry requirements**:
  - Still fully immutable once posted (no edits/deletes).
  - Must set `is_adjusting = true`.
  - Must include a non-empty `adjusting_reason` (and ideally an external reference such as an auditor workpaper/ticket ID).
- **Versioned statements**: statements should be referencable by a close event/version (e.g., Close v1 vs Close v2) so “the statements I looked at” remain reproducible even if later audit adjustments occur.

Epicor migration note: we will validate this against Epicor’s data model. Initial inspection of the Atlas Epicor read-only DB (company `160144`) shows the primary fiscal calendar (`FiscalCalendarID = MAIN`) has **12 periods** and `NumClosingPeriods = 0` (i.e., no “Period 13” to map). There are also **no stored `FiscalPeriod = 0` rows** in `Erp.FiscalPer` or `Erp.GLJrnDtl` for `MAIN`; if Epicor screens/reports show “Period 0”, it is likely a **derived beginning-balance/roll-forward bucket**, not an actual fiscal period row that needs schema mapping.

## Currency

**All financial amounts are USD. Multi-currency is not in scope.**

There are no `currency_code` or `exchange_rate` fields on journal lines. If multi-currency is ever needed in the future, it would be introduced as a new schema version — but that is not a current or planned requirement.

## Accounting-Grade Immutability

This is accounting-grade immutability, even if regulatory compliance is not required.
