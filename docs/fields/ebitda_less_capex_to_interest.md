# (EBITDA − Capex) / Interest

`ebitda_less_capex_to_interest`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x` &nbsp;·&nbsp; **Proxy:** ⚠️ conditional


Cash-earnings coverage multiple: how many times post-capex EBITDA covers the cash interest bill. Higher is better for creditworthiness.


## Formula

```text
ebitda_less_capex_to_interest = (ebitda + capex) / cash_interest
```

| term | value | sign | effect on numerator / denominator |
|---|---|---|---|
| `ebitda` | positive | + | numerator |
| `capex` | **negative** (Yahoo convention) | + (adding a negative) | reduces numerator |
| `cash_interest` | **positive magnitude** | denominator | larger interest → smaller multiple |

Because `capex` is negative, `ebitda + capex` = EBITDA minus the absolute capex spend.

Reported at two points — **latest** (each component at its `latest` value) and **FY-baseline** (each component at its `fy_baseline` value), each with its exact `as_of` date.


## Inputs

| input | getter | transform | role |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM (multi-tier) | numerator + |
| `capex` | `get_capex` | TTM, **negative** | numerator − |
| `cash_interest` | `get_cash_interest` | TTM, **positive magnitude** (multi-tier: cash → SEC → accrual) | denominator |


## Caveats & proxies

Inherits `cash_interest`'s proxy flag when that field falls back to the accrual estimate (Tier 3). The accrual proxy overstates true cash interest, which understates the multiple. `is_proxy=True` in that case.


## Simplified logic

```python
num   = v['ebitda'] + v['capex']          # capex is negative → reduces num
denom = v['cash_interest']                 # positive magnitude
ratio = num / denom if denom else None
```
