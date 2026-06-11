# Cash Taxes

`cash_taxes`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Cash taxes paid — the actual cash outflow for income taxes, returned as a **positive magnitude**. The `fcf` formula **subtracts** it. Two-tier resolution: Yahoo cash-flow labels first, SEC 10-K for US filers second. There is **no accrual proxy** — if both tiers fail, the field returns unavailable.


## Formula

```text
Tier 1 (any filer):  cash_taxes = |TTM Σ(Taxes Refund Paid
                                         + Income Tax Paid Supplemental Data)|
Tier 2 (US filers):  cash_taxes = SEC us-gaap:IncomeTaxesPaidNet
                      (fallback:  SEC us-gaap:IncomeTaxesPaid)
```

Returned as a **positive number** (e.g. 80 mm = $80 m of cash taxes paid). The `fcf` formula subtracts this value.

Reported at two points — **latest** (TTM for Tier 1; annual-only for Tier 2) and **FY-baseline** (last annual value), each with its exact `as_of` date.


## Inputs

| input | source | transform | priority |
|---|---|---|---|
| `Taxes Refund Paid` | `quarterly_cash_flow['Taxes Refund Paid']` | TTM-rolled, absolute value | Tier 1 |
| `Income Tax Paid Supplemental Data` | `quarterly_cash_flow['Income Tax Paid Supplemental Data']` | TTM-rolled, absolute value | Tier 1 |
| `IncomeTaxesPaidNet` | `SEC EDGAR us-gaap:IncomeTaxesPaidNet` (annual 10-K) | absolute value, US filers only | Tier 2 |
| `IncomeTaxesPaid` | `SEC EDGAR us-gaap:IncomeTaxesPaid` (annual 10-K) | absolute value, US filers only | Tier 2 fallback |

Tier 1 sums all present cash-flow labels. Yahoo's `Income Tax Paid Supplemental Data` typically matches the cash-paid magnitude directly when present.


## Tier resolution

**Picker sort key** (lowest wins):

```
(is_stale, priority, is_zero_latest, −recency)
```

1. Non-stale over stale — a tier is stale if its `as_of` date is > 2 years old.
2. Lower priority number first (Tier 1 beats Tier 2).
3. Non-zero `latest` over zero. This matters for Tier 2: SEC may have `IncomeTaxesPaidNet=0` (stale) and `IncomeTaxesPaid=15 mm` (stale but non-zero) — the picker selects the non-zero one.
4. More recent `as_of` date.

**US filer detection:** same as `cash_interest` — ticker without `.` suffix → CIK lookup.

**No sanity check** and **no accrual proxy.** The `Tax Provision − Deferred Tax` approach is unreliable and is not used here. If both tiers return nothing, `latest` and `fy_baseline` are `None`.


## Caveats & proxies

Unlike `cash_interest`, there is no fallback to an accrual estimate. A missing result is reported honestly as unavailable rather than substituted.


## Simplified logic

```python
# Tier 1 — yf cash labels (any filer)
yf_sum = quarterly_cash_flow[['Taxes Refund Paid',
                               'Income Tax Paid Supplemental Data']].sum(axis=1).abs()

# Tier 2 — SEC 10-K (US filers only)
sec_val, sec_date = sec_concept(cik, 'IncomeTaxesPaidNet')   # fallback IncomeTaxesPaid

# Pick primary by (is_stale, priority, is_zero, -recency)
# No accrual fallback — returns unavailable if both tiers fail
```
