# Epicor Kinetic Reference Export — Agent Prompt (for Nexus)

You are an Epicor Kinetic–specialized agent. Your job is to extract **authoritative reference data + semantics** from an Epicor Kinetic (cloud) tenant so we can finalize Nexus’s foundational schemas:

- **D1 (Chart of Accounts / GL account model)**
- **D2 (Party: customer/vendor master)**
- **Accounting periods + period close behavior** (closed periods + adjusting entries allowed with justification)

## Output format (required)

Deliver a folder of exports **plus** a short written summary (markdown) that answers the questions below.

### Exports (CSV preferred; JSON acceptable)

Create these files (names exactly as listed):

1. `coa_accounts.csv`
2. `fiscal_calendar_periods.csv`
3. `customers.csv`
4. `customer_shipto.csv` (if ship-to is separate)
5. `vendors.csv`
6. `vendor_remitto.csv` (if remit-to is separate)
7. `plants_sites.csv` (plants/sites)
8. `cost_centers_or_segments.csv` (see “Segments/Dimensions” below)
9. `gl_controls_and_defaults.csv` (if Epicor has control accounts/default posting rules)
10. `README_SUMMARY.md` (your narrative summary + answers)

If you can’t produce one of these, still include an empty file and explain why in `README_SUMMARY.md`.

### Data hygiene

- It’s OK to redact sensitive fields (emails, phone numbers, addresses) if needed.
- Do **not** redact account numbers/segment structure—those are essential.
- If you must anonymize names, keep a stable mapping (so repeated entities remain consistent).

## 1) Chart of Accounts (COA) — what to extract

### Goal

We need to design the Nexus `ledger.account` model so it can represent Epicor’s COA **without lossy transformation**.

### Export: `coa_accounts.csv`

Include one row per GL account (or posting account). Provide these columns if available (include even if blank):

- `company`
- `gl_account_id` (Epicor internal ID if exists)
- `account_number_full` (the full human-facing account string)
- `segments_json` (or separate `seg1`, `seg2`, … if JSON is hard)
- `description`
- `account_type` (Asset/Liability/Equity/Revenue/Expense; use Epicor’s classification)
- `normal_balance` (Debit/Credit if Epicor stores it)
- `posting_allowed` (Y/N)
- `active` (Y/N)
- `inactive_date` (if any)
- `parent_account_number` (if there’s a hierarchy) OR `rollup_group` (if grouping is separate)
- `financial_statement_group` (if Epicor defines FS groups)
- `created_at` / `updated_at` (if available)

### COA questions to answer in `README_SUMMARY.md`

- Does Epicor use a **true hierarchy** (parent/child) or just **segment-based rollups/groups**?
- Are there “header/rollup” accounts that are non-posting?
- Are there **account types** on the account master or inferred via mapping tables?
- Are segments (dimensions) part of the GL account string (e.g., `1000-10-200`) or separate posting dimensions?
- Are there constraints like “segment 2 must be a department” or “only certain segment combos valid”?
- Identify any “special” accounts: retained earnings, AP control, AR control, inventory, WIP, COGS, sales, tax.

## 2) Segments / Dimensions — what to extract

### Goal

Nexus will have first-class dimensions (site, cost center, business unit; later department, etc.). We must understand what Epicor stores as:

- plant/site
- GL segments (department/cost center/etc.)
- any cross-validation tables (valid segment combinations)

### Export: `plants_sites.csv`

Include:

- `company`
- `plant_id` / `site_id`
- `name`
- `active`
- `address_present` (Y/N; you can redact addresses)

### Export: `cost_centers_or_segments.csv`

If Epicor uses segments:

- Export the **segment definitions** (segment number, name/label, purpose, length, allowed values).
- Export **segment values** (code, description, active).
- If Epicor has a “valid combinations” table, export it or summarize it.

If Epicor uses cost centers/departments explicitly:

- Export cost centers/departments with ids/codes, descriptions, active, and any hierarchy.

## 3) Accounting periods & period close — what to extract

### Goal

Nexus will support:

- accounting periods (monthly)
- closed periods that reject normal posting
- **adjusting entries** allowed into closed periods only when explicitly marked + justified

We need to understand Epicor’s fiscal calendar and close semantics so Nexus can mirror the real-world operating model.

### Export: `fiscal_calendar_periods.csv`

Include one row per period:

- `company`
- `fiscal_year`
- `period_number`
- `start_date`
- `end_date`
- `status` (open/closed; or separate flags)
- `closed_date`
- `closed_by` (can redact user identity if needed)
- `module_close_flags` (GL/AP/AR/inventory close if those differ)

### Period/close questions to answer in `README_SUMMARY.md`

- How does Epicor represent closed periods? (flags? tables? per-module close?)
- Does Epicor allow “post to closed period” with a permission/override? If yes, what’s the mechanism called?
- Does Epicor distinguish “adjusting” entries vs normal entries? If yes, how is it stored?
- Is the fiscal calendar strictly monthly? Any 4-4-5 patterns?

## 4) Party master: customers & vendors — what to extract

### Goal

Nexus will likely implement a thin `party` module early (customer/vendor/both). We need minimum viable fields + external IDs + relationship to ship-to/remit-to records.

### Export: `customers.csv`

Include:

- `company`
- `customer_id` (Epicor customer key)
- `customer_number` (if distinct)
- `name`
- `active`
- `terms_code`
- `tax_region` / `tax_code` (if relevant)
- `currency` (should be USD; confirm)
- `credit_limit` (optional)
- `external_refs` (any legacy IDs)

### Export: `customer_shipto.csv` (if applicable)

Include:

- `customer_id`
- `shipto_id`
- `name`
- `active`
- `address_present` (Y/N; redact address lines if needed)

### Export: `vendors.csv`

Include:

- `company`
- `vendor_id` (Epicor vendor key)
- `vendor_number` (if distinct)
- `name`
- `active`
- `terms_code`
- `tax_region` / `tax_code` (if relevant)
- `currency` (should be USD; confirm)
- `external_refs`

### Export: `vendor_remitto.csv` (if applicable)

Include:

- `vendor_id`
- `remitto_id`
- `name`
- `active`
- `address_present` (Y/N; redact address lines if needed)

### Party questions to answer in `README_SUMMARY.md`

- Are customers and vendors separate masters or unified “parties”?
- What are the stable identifiers we should store as `external_id` in Nexus?
- Any “inactive but referenced” behavior we must preserve?

## 5) GL controls/defaults (optional but very helpful)

### Export: `gl_controls_and_defaults.csv`

If Epicor has configuration for control accounts / default accounts, export what you can:

- AR control account(s)
- AP control account(s)
- inventory / WIP accounts
- revenue / discounts / tax payable accounts
- any “posting rules” that select accounts based on product/site/etc.

If you can’t export, summarize where/how this is configured.

## 6) What I need from you (acceptance criteria)

In `README_SUMMARY.md`, include:

- A **one-paragraph** recommended Nexus mapping for:
  - `ledger.account` fields (what must exist day-one)
  - “dimensions vs segments” (what should be a first-class dimension table vs embedded in account_number)
  - party master (`party` schema essentials)
- Confirm whether **USD-only** is true in Epicor practice (should be).
- A short list of **gotchas** (weird segment rules, multiple calendars, per-module closing, etc.).

## Notes

- Prefer Epicor REST APIs or BAQs—whatever is fastest and most reliable for Kinetic cloud.
- If you discover that the COA cannot be represented cleanly without a hierarchy/group table, call that out explicitly.

