Implement modules/ledger as the immutable posting subsystem.

Core tables:
- account (minimal chart of accounts)
- journal_entry (header): id, entry_date, source_type, source_id, status (draft/posted), created_by, posted_at
- journal_line: entry_id, account_id, debit, credit, memo, dimension fields (site_id, cost_center_id, business_unit_id, etc)

Currency constraint:
- All amounts are USD. No currency_code or exchange_rate fields. This is an explicit design decision (see ACCOUNTING_MODEL.md).

Rules:
- Posted entries are immutable: no updates/deletes; only reversals/new entries.
- Provide service function post_entry() that enforces balancing.
- Corrections via create_reversal_entry(original_entry_id) and optional create_correcting_entry().

APIs:
- create draft entry
- post entry
- reverse entry
- query entries by source/date/dimensions

Deliver:
- module code + migrations
- tests: immutability, balancing, reversal correctness
- docs: /docs/domain/LEDGER.md and /docs/standards/IMMUTABLE_POSTING.md
