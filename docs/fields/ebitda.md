# EBITDA

`ebitda`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month reported EBITDA. The reported (not adjusted) figure; the adjusted variant is `adj_ebitda`.


## Formula

```text
Tier 1 (primary):  ebitda = TTM rolling of income_stmt['EBITDA']
Tier 2 (fallback): ebitda = TTM(Net Income)
                           + TTM(|Tax Provision|)
                           + TTM(|Interest Expense|)
                           + TTM(|Reconciled Depreciation|)
```

Reported at two points — **latest** (Σ of the last 4Q / 2H of the resolved tier) and **FY-baseline** (the last annual value of the resolved tier), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `EBITDA` | `income_stmt['EBITDA']` | TTM-rolled | Tier 1 (priority 1) |
| `Net Income` | `income_stmt['Net Income']` | TTM-rolled | Tier 2 component |
| `Tax Provision` | `income_stmt['Tax Provision']` | TTM-rolled, absolute value | Tier 2 add-back |
| `Interest Expense` | `income_stmt['Interest Expense']` | TTM-rolled, absolute value | Tier 2 add-back |
| `Reconciled Depreciation` | `income_stmt['Reconciled Depreciation']` | TTM-rolled, absolute value | Tier 2 add-back |


## Tier resolution

Both tiers compute `latest_mm` (TTM) and `fy_mm` (annual). The **picker** chooses the primary by:

```
sort key = (is_stale, priority, is_zero_latest, −recency)
```

1. Non-stale over stale (stale = `as_of` date older than 2 years).
2. Lower priority number first (Tier 1 beats Tier 2).
3. Non-zero latest over zero.
4. More recent `as_of` date.

All tiers are surfaced in `variants` for audit. There is **no sanity-check ratio** between tiers.


## Simplified logic

```python
# Tier 1 — yfinance headline
q1 = quarterly_income_stmt['EBITDA']
a1 = income_stmt['EBITDA']

# Tier 2 — first principles
q2 = NI + |Tax| + |InterestExp| + |D&A|   # all TTM-rolled from quarterly statements
a2 = NI + |Tax| + |InterestExp| + |D&A|   # from annual statements

# Primary = Tier 1 unless stale / zero
```
