# Cash Interest

`cash_interest`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm` &nbsp;·&nbsp; **Proxy:** ⚠️ conditional


Cash interest paid — the actual cash outflow for interest, returned as a **positive magnitude**. The `fcf` formula **subtracts** it. Three-tier resolution ladder: the highest-quality cash source available wins; falls back to the accrual proxy only when cash data is absent or implausibly small.


## Formula

```text
Tier 1 (any filer):   cash_interest = |TTM Σ(Interest Paid Cff
                                              + Interest Paid Cfo
                                              + Interest Paid Supplemental Data)|
Tier 2 (US filers):   cash_interest = SEC us-gaap:InterestPaidNet
                       (fallback:     SEC us-gaap:InterestPaid)
Tier 3 (proxy):       cash_interest = |TTM Interest Expense|   ← accrual proxy
```

Returned as a **positive number** (e.g. 120 mm = $120 m of cash interest paid). The `fcf` formula subtracts this value.

Reported at two points — **latest** (TTM for Tiers 1 & 3; annual-only for Tier 2) and **FY-baseline** (last annual value), each with its exact `as_of` date.


## Inputs

| input | source | transform | priority |
|---|---|---|---|
| `Interest Paid Cff` | `quarterly_cash_flow['Interest Paid Cff']` | TTM-rolled, absolute value | Tier 1 |
| `Interest Paid Cfo` | `quarterly_cash_flow['Interest Paid Cfo']` | TTM-rolled, absolute value | Tier 1 |
| `Interest Paid Supplemental Data` | `quarterly_cash_flow['Interest Paid Supplemental Data']` | TTM-rolled, absolute value | Tier 1 |
| `InterestPaidNet` | `SEC EDGAR us-gaap:InterestPaidNet` (annual 10-K) | absolute value, US filers only | Tier 2 |
| `InterestPaid` | `SEC EDGAR us-gaap:InterestPaid` (annual 10-K) | absolute value, US filers only | Tier 2 fallback |
| `Interest Expense` | `income_stmt['Interest Expense']` | TTM-rolled, absolute value | Tier 3 (proxy) |

Tier 1 sums all present cash-flow labels (not just the first one found). Yahoo's `Interest Paid Supplemental Data` typically matches the cash-paid figure directly when it exists.


## Tier resolution

**Picker sort key** (lowest wins):

```
(is_stale, priority, is_zero_latest, −recency)
```

1. Non-stale over stale — a tier is stale if its `as_of` date is > 2 years old.
2. Lower priority number first (Tier 1 beats Tier 2 beats Tier 3).
3. Non-zero `latest` over zero.
4. More recent `as_of` date.

**Sanity check (cash vs. accrual):** after picking the best cash tier (Tier 1 or 2), if its `latest_mm < 0.30 × Tier 3 latest_mm`, the result falls back to Tier 3 with a `note` field:

```
"Cash variant < 30% of accrual → fell back to accrual proxy"
```

**US filer detection:** a ticker **without** a `.` suffix (e.g. `BALL` not `HEIO.AS`) is looked up in SEC's public ticker→CIK map. A found CIK enables Tier 2; otherwise Tier 2 is skipped.


## Caveats & proxies

Tier 3 (accrual) includes non-cash items (OID amortization, issuance-cost amortization, timing differences) and therefore **overstates** true cash interest. Any result sourced from Tier 3 sets `is_proxy=True`, which propagates to `fcf` and `ebitda_less_capex_to_interest`.


## Simplified logic

```python
# Tier 1 — yf cash labels (any filer)
yf_sum = quarterly_cash_flow[['Interest Paid Cff',
                               'Interest Paid Cfo',
                               'Interest Paid Supplemental Data']].sum(axis=1).abs()

# Tier 2 — SEC 10-K (US filers only, ticker has no '.')
sec_val, sec_date = sec_concept(cik, 'InterestPaidNet')   # fallback InterestPaid

# Tier 3 — accrual proxy
accrual = quarterly_income_stmt['Interest Expense'].abs()  # TTM-rolled

# Pick primary by (is_stale, priority, is_zero, -recency)
# Then sanity check: if cash_latest < 30% × accrual_latest → use accrual
```
