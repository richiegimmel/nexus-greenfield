# Epicor Chart of Accounts — Investigation Summary

**Date:** 2026-02-10
**Purpose:** Inform decision D1 (Chart of Accounts schema design for Nexus ledger module)
**Data source:** Live queries against Epicor Kinetic read-replica (`SaaS5034_160144`)

---

## 1. Epicor's COA Structure

Atlas uses a single COA (code: `MAIN`) with **3 segments** separated by `|`:

| Seg # | Name | Abbreviation | Length | Numeric Only | Dynamic | Example |
|-------|------|-------------|--------|-------------|---------|---------|
| 1 | Chart | ACCT | 4 | Yes | No | `1200` |
| 2 | Division | DIV | 2 | No (alpha) | No | `MS` |
| 3 | Sub Account | Sub Account | 4 | No (alpha) | Yes (ref: Work Center) | `MILL` |

A fully qualified GL Account in Epicor looks like: **`1200|MS`** or **`5100|MS|TURN`**

- Segment 1 is the **natural account** — the "what" (Accounts Receivable, Payroll, etc.)
- Segment 2 is the **division** — the "who" (which business unit)
- Segment 3 is the **sub account** — a dynamic reference to a Work Center (the "where" within manufacturing)

### Key Properties

- The `CtrlSegList` for this COA is `3`, meaning only Segment 3 is a "controlled" segment (dynamically validated against a reference entity).
- `PerBalFmt` and `TBBalFmt` are `1~2~3` and `1~2` respectively, meaning period balances roll up by all 3 segments, but trial balance rolls up by segments 1 and 2 only.
- The separator character is `-` (though the data stores the pipe `|` internally).

---

## 2. Segment 1 — Natural Accounts (The Chart)

**271 total accounts, 270 active, 1 inactive** (`2370 - Sales Taxes Payable FL`)

### Account Number Ranges by Category

| Range | Category | Description | Count | Type |
|-------|----------|-------------|-------|------|
| 1000 | CASH | Cash | 1 | Balance Sheet |
| 1010–1465 | OTHCURASSE | Other Current Assets | 25 | Balance Sheet |
| 1200 | AR | Accounts Receivable | 1 | Balance Sheet |
| 1235–1450 | CUR_ASSETS | Current Assets (misc) | 3 | Balance Sheet |
| 1400–1445 | INV | Inventory | 8 | Balance Sheet |
| 1500–1630 | PROP_EQUIP | Property and Equipment | 16 | Balance Sheet |
| 1800–1850 | OTH_ASSET | Other Assets | 3 | Balance Sheet |
| 1875–1880 | ASSETS | Assets (top-level) | 2 | Balance Sheet |
| 2000–2590 | CUR_LIABIL | Current Liabilities | 48 | Balance Sheet |
| 2600–2995 | LT_LIABIL | Long Term Liabilities | 17 | Balance Sheet |
| 3000–3500 | EQUITY | Equity | 8 | Balance Sheet |
| 4000–4920 | SALES_REV | Sales/Revenue | 20 | Income Statement |
| 5000–5960 | C_O_S | Cost of Sales | 47 | Income Statement |
| 5101–5940 | MFG_EXP | Manufacturing Expenses | 2 | Income Statement |
| 6100–6550 | EXPENSES | Operating Expenses | 56 | Income Statement |
| 7000–9999 | X_INC_EXP | Other Income/Expenses | 14 | Income Statement |

The numbering follows a standard convention: 1xxx = Assets, 2xxx = Liabilities, 3xxx = Equity, 4xxx = Revenue, 5xxx = COGS/Manufacturing, 6xxx = Expenses, 7xxx–9xxx = Other.

### Key Account Examples

| Code | Name | Category | Normal Bal |
|------|------|----------|-----------|
| 1000 | Stock Yards Checking | CASH | Debit |
| 1200 | Accounts Receivable | AR | Debit |
| 1400 | Inventory - Stocked | INV | Debit |
| 1500 | Machinery & Equipment | PROP_EQUIP | Debit |
| 2000 | Accounts Payable Trade | CUR_LIABIL | Credit |
| 2100 | Accrued Payroll | CUR_LIABIL | Credit |
| 2600 | Line of Credit - Revolving | LT_LIABIL | Credit |
| 3000 | Common Stock | EQUITY | Credit |
| 4000 | Product Sales | SALES_REV | Credit |
| 5000 | Material Cost | C_O_S | Debit |
| 5100 | Production Labor | C_O_S | Debit |
| 6100 | Payroll - Cust Service | EXPENSES | Debit |
| 7000 | Interest Expense | X_INC_EXP | Debit |

Each account carries:
- `SegmentCode` (the 4-digit number)
- `SegmentName` (short name)
- `SegmentDesc` (longer description, sometimes with usage notes)
- `Category` (FK to account category)
- `NormalBalance` ("D" or "C")
- `ActiveFlag` (boolean)

---

## 3. Segment 2 — Divisions

**5 divisions:**

| Code | Name | Description | Maps to Nexus |
|------|------|-------------|---------------|
| CO | Corp | Corporate | `business_unit` dimension |
| IP | Industrial Products | Industrial Products — Compressed Air | `business_unit` dimension |
| MS | Machine Shop | Machine Shop | `business_unit` dimension |
| OF | Officer | Officer (Owner) | `business_unit` dimension |
| YE | Year End Adjustments | GAAP adjustments not shown operationally | Special handling needed |

The `YE` division is noteworthy — it's used for year-end GAAP adjustments that management doesn't want in operational reports. This is a common ERP pattern and will need to be represented in Nexus, likely as a special business unit or a flag on journal entries.

---

## 4. Segment 3 — Sub Accounts (Work Centers)

**8 sub accounts, all active:**

| Code | Name |
|------|------|
| ALLO | Unallocated |
| FDSV | Field Service Breck |
| FSTX | Field Service Texas |
| GRIN | Grind |
| MILL | Mill |
| RAIG | Steel Services |
| TURN | Turn |
| WELD | Weld |

This segment is dynamic and references `GLCOARefType = "WkCenter"` (Work Center). It provides cost center–level detail within the Machining & Supply division. In Nexus, this maps to the `cost_center` dimension that already exists in the dimensions module design.

---

## 5. Account Categories (Hierarchy)

**26 categories** organized in a parent-child tree. Each has a `Type` field: `B` = Balance Sheet, `I` = Income Statement.

```
ASSETS (B, Debit)                          ← Top-level
├── CUR_ASSETS (B, Debit)                  ← Current Assets
│   ├── CASH (B, Debit)
│   ├── AR (B, Debit)
│   ├── OTHCURASSE (B, Debit)
│   └── INV (B, Debit)
├── PROP_EQUIP (B, Debit)                  ← Fixed Assets
├── OTH_ASSET (B, Debit)
└── LT Assets (B, Debit)                   ← Long Term Receivables

LIAB_EQUIT (B, Credit)                     ← Top-level
├── LIABILITIE (B, Credit)
│   ├── CUR_LIABIL (B, Credit)
│   └── LT_LIABIL (B, Credit)
└── EQUITY (B, Credit)
    └── PROFIT (B, Credit, NetIncome=true)  ← Retained earnings target

NET_INCOME (I, Credit)                     ← Top-level (Income Statement)
├── NET_INC_BT (I, Credit)                 ← Net Income Before Taxes
│   ├── OPR_INCOME (I, Credit)
│   │   ├── GROS_PROFI (I, Credit)
│   │   │   ├── SALES_REV (I, Credit)
│   │   │   ├── C_O_S (I, Debit)
│   │   │   │   └── INFREIGHT (I, Debit)
│   │   │   └── MFG_EXP (I, Debit)
│   │   └── EXPENSES (I, Debit)
│   └── X_INC_EXP (I, Debit)
└── TAX_PROVIS (I, Debit)
```

The `PROFIT` category has `NetIncome = true`, which is how Epicor knows where to roll net income into the balance sheet (retained earnings). This is a critical detail for period-close.

---

## 6. GL Accounts (The Combinations)

**568 total GL accounts, 504 active.**

A GL Account is a combination of Segment 1 (Account) + Segment 2 (Division) + optionally Segment 3 (Sub Account). Examples:

| GLAccount | Description | Seg1 | Seg2 | Seg3 |
|-----------|-------------|------|------|------|
| `1000\|CO` | Stock Yards Checking - CO | 1000 | CO | |
| `1200\|IP` | Accounts Receivable - IP | 1200 | IP | |
| `1200\|MS` | Accounts Receivable - MS | 1200 | MS | |
| `5100\|MS\|TURN` | Production Labor - MS - Turn | 5100 | MS | TURN |

Not every account × division combination exists — only the ones that are valid for that business unit. The `ParentGLAccount` field is empty for all sampled records, suggesting Epicor's GL account hierarchy is driven entirely through the category tree, not through parent-child GL accounts.

---

## 7. Options for Nexus D1 Schema Design

### Option A: Replicate Epicor's Segmented GL Account Model

Store the full segment combination as the account identifier, similar to how Epicor does it.

**Schema:**
- `gl_account` table: `id`, `account_code` ("1200|MS"), `description`, `segment_1` (natural account), `segment_2` (division), `segment_3` (sub account), `category_id`, `normal_balance`, `active`
- `account_category` table: hierarchy as above
- Journal lines reference `gl_account_id` directly

**Pros:**
- 1:1 mapping from Epicor — migration is trivial
- Familiar to Atlas accounting staff
- Single FK on journal lines (simple)

**Cons:**
- 568 GL account records that embed dimension data (division, work center) in the account itself
- Adding a new division or work center means creating new GL account combinations — combinatorial explosion
- Duplicates the purpose of Nexus's dimensions module (business_unit, cost_center are already on journal lines)
- Reporting queries must parse segments out of the account code to roll up by division
- Violates the Nexus architecture principle that dimensions are first-class, separate from the account

### Option B: Normalize — Natural Account + Dimensions (Recommended)

Separate the natural account (Segment 1) from the dimensional segments (Segments 2 and 3), which are already represented by Nexus's dimensions module.

**Schema:**
- `account` table: `id`, `account_number` ("1200"), `name`, `description`, `category_id`, `normal_balance`, `active`, `external_id` (for Epicor migration)
- `account_category` table: `id`, `name`, `statement_type` (B/I), `normal_balance`, `parent_category_id`, `sequence`, `is_net_income`
- Journal lines: `account_id` + `business_unit_id` (from dimensions) + `cost_center_id` (from dimensions)

**Pros:**
- Only 271 account records (not 568 combinations)
- Clean separation of "what" (account) from "where" (dimensions)
- Adding a new division or cost center doesn't require new account records
- Reporting rolls up naturally by any dimension without parsing
- Consistent with Nexus architecture (dimensions are first-class on every journal line)
- Categories provide the type classification (B/I) and hierarchy needed for financial statements

**Cons:**
- Not a 1:1 map from Epicor — migration requires splitting `1200|MS` into `account_id=1200` + `business_unit_id=MS`
- Epicor staff familiar with "account 1200-MS" will see "account 1200, division MS" instead — minor UX adjustment
- Some Epicor GL accounts may have segment-combination-specific descriptions (e.g., "Stock Yards Checking-CO") that won't have a natural home

### Option C: Hybrid — Natural Account Table + Mapping Table

Keep the normalized natural account table but also maintain a mapping/validation table of allowed account × dimension combinations.

**Schema:**
- `account` table: same as Option B
- `account_category` table: same as Option B
- `account_dimension_rule` table: `account_id`, `business_unit_id`, `cost_center_id`, `active` — defines which combinations are valid
- Journal lines: same as Option B, but posting validates against the rules table

**Pros:**
- All benefits of Option B
- Preserves Epicor's validation rules (not every account is valid for every division)
- Migration can populate rules from existing GL account combinations
- Prevents invalid postings (e.g., can't post Field Service expenses to Corporate division)

**Cons:**
- Additional table to maintain
- Adds complexity to the posting API (must validate account + dimensions against rules)
- Rules may be overly restrictive if Atlas wants more flexibility in Nexus than Epicor allowed
- Can be added later as an enhancement without schema changes to core tables

---

## 8. Recommendation

**Option B (Normalize) with a deferred path to Option C.**

### Reasoning

1. **Architecture alignment.** Nexus is designed around first-class dimensions on journal lines. Embedding dimensions into the account code contradicts this and creates two parallel systems for the same data.

2. **The data supports it.** Epicor's Segment 2 (Division) maps exactly to Nexus's `business_unit` dimension. Segment 3 (Sub Account / Work Center) maps exactly to `cost_center`. These dimensions already exist in the module design. There is no information in the segment combination that isn't captured by the existing dimensional model.

3. **Scale is small.** 271 natural accounts and 26 categories is a very manageable reference data set. Migration is straightforward: split the GL account code on `|`, map Segment 1 to `account_id`, Segment 2 to `business_unit_id`, Segment 3 to `cost_center_id`.

4. **Categories provide the type system.** The 26-category hierarchy with `Type` (B/I), `NormalBalance`, `ParentCategory`, and `NetIncome` flag gives Nexus everything it needs for trial balance, balance sheet, income statement, and period-close (retained earnings rollup) without inventing a new classification scheme.

5. **The combination validation (Option C) can come later.** The `account_dimension_rule` table is purely additive — it doesn't change the account or journal_line schema. If Atlas wants to restrict which account/division combinations are valid, this can be added as an enhancement after the core ledger is working.

6. **Sub-ledger readiness.** Adding a nullable `sub_ledger_type` field to `journal_line` now (even if unused initially) keeps the posting API stable when AR/AP sub-ledgers are eventually needed. This is cheap insurance.

### Specific Schema Recommendations for Prompt 007

**`account` table:**
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | PK |
| `account_number` | VARCHAR(20) | Epicor Segment 1 code, e.g. "1200". Unique. |
| `name` | VARCHAR(200) | Short name, e.g. "Accounts Receivable" |
| `description` | TEXT | Optional longer description |
| `category_id` | VARCHAR(20) | FK → account_category. E.g. "AR" |
| `normal_balance` | VARCHAR(1) | "D" or "C" |
| `active` | BOOLEAN | Default true |
| `external_id` | VARCHAR(50) | Epicor SegmentCode for migration traceability |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**`account_category` table:**
| Column | Type | Notes |
|--------|------|-------|
| `id` | VARCHAR(20) | PK. Natural key from Epicor, e.g. "AR", "CASH" |
| `name` | VARCHAR(200) | Display name, e.g. "ACCOUNTS RECEIVABLE" |
| `statement_type` | VARCHAR(1) | "B" (Balance Sheet) or "I" (Income Statement) |
| `normal_balance` | VARCHAR(1) | "D" or "C" |
| `parent_category_id` | VARCHAR(20) | Nullable self-reference for hierarchy |
| `sequence` | INTEGER | Display/report ordering |
| `is_net_income` | BOOLEAN | True only for PROFIT — retained earnings target |

**`journal_line` additions:**
| Column | Type | Notes |
|--------|------|-------|
| `sub_ledger_type` | VARCHAR(20) | Nullable. Future: "AR", "AP", etc. |

### Seed Data

The 26 account categories and 271 natural accounts should be seeded as reference data during M2. The Epicor data extracted in this investigation can be used directly as the seed source.

### YE Division

The `YE` (Year End Adjustments) division should be represented as a business unit in the dimensions module with a special flag (`is_adjustment = true` or similar) so that operational reports can exclude year-end GAAP adjustments while financial statements include them.

---

## 9. Open Items

| Item | Priority | Notes |
|------|----------|-------|
| Validate seed data with Atlas accounting team | HIGH | Confirm the 271 accounts and 26 categories are current and complete |
| Decide on combination validation rules | MEDIUM | Option C — can be deferred to post-M2 |
| Map `YE` division handling | MEDIUM | Need business rule for when adjustments are visible |
| Historical balance migration | MEDIUM | Opening balances at cutover — what format, what period? |
| Sub-ledger scope | LOW | When do AR/AP sub-ledgers come into play? |

---

## Appendix: Data Extraction Queries

All data was extracted on 2026-02-10 from `erpus-read08.epicorsaas.com` (Epicor Kinetic read replica), database `SaaS5034_160144`, company `160144`, COA code `MAIN`.

Key tables queried:
- `Erp.COA` — COA header (separator, segment format)
- `Erp.COASegment` — Segment definitions (3 segments)
- `Erp.COASegValues` — Segment values (accounts, divisions, sub-accounts)
- `Erp.COAActCat` — Account categories (26-row hierarchy)
- `Erp.GLAccount` — GL account combinations (568 rows)
- `Erp.GLCOARefType` — Reference type for dynamic segment 3 (Work Center)
