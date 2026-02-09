Implement modules/invoicing v0 and integrate it with ledger immutability.

Owns tables:
- invoice (customer_id, job_id, status, totals, issued_at)
- invoice_line (invoice_id, description, qty, unit_price, amount, dimensions)

Rules:
- Issued invoices are immutable; void via reversal/credit note concept (can be simple v0).
- On InvoiceIssued event from workflow, create invoice and then post journal entry via ledger module:
  - debit AR
  - credit revenue
  (accounts can be configured as defaults)

Deliver:
- invoicing module code + migrations
- event consumer that listens to outbox events (or direct call from workflow, but still record an outbox event)
- ledger posting integration
- tests: invoice issuance triggers balanced ledger entry; immutability enforced
- docs: /docs/domain/INVOICING.md
