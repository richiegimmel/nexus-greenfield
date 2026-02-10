Implement modules/ledger as the immutable posting subsystem.

Core tables:
- account (minimal chart of accounts)
- accounting_period: id, start_date, end_date, status (open/closed), closed_at, closed_by
- journal_entry (header): id, entry_date, source_type, source_id, status (draft/posted), created_by, posted_at
- journal_line: entry_id, account_id, debit, credit, memo, dimension fields (site_id, cost_center_id, business_unit_id, etc)

Currency constraint:
- All amounts are USD. No currency_code or exchange_rate fields. This is an explicit design decision (see ACCOUNTING_MODEL.md).

Rules:
- Posted entries are immutable: no updates/deletes; only reversals/new entries.
- Period close:
  - Every entry belongs to exactly one `accounting_period` determined by `entry_date`.
  - Normal posting into a closed period is rejected.
  - Adjusting entries are allowed in closed periods only when explicitly marked and justified (see below).
- Provide service function post_entry() that enforces balancing.
- Corrections via create_reversal_entry(original_entry_id) and optional create_correcting_entry().

Adjusting entries (period close model):
- Add fields on `journal_entry`:
  - `is_adjusting` (bool, default false)
  - `adjusting_reason` (nullable string)
- Posting rules:
  - If target `accounting_period.status == closed` then `is_adjusting` must be true and `adjusting_reason` must be non-empty.
  - (Future) Gate adjusting entries in closed periods behind RBAC permission.

APIs:
- create draft entry
- post entry
- reverse entry
- list/create/close accounting periods (v0 can be admin-only; auth may be stubbed)
- query entries by source/date/dimensions

Deliver:
- module code + migrations
- tests: immutability, balancing, reversal correctness, period close enforcement, adjusting entry requirements
- docs: /docs/domain/LEDGER.md and /docs/standards/IMMUTABLE_POSTING.md
