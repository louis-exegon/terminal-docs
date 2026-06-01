# Free Cash Flow

`fcf`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `mm` &nbsp;·&nbsp; **Proxy:** ⚠️ yes


Levered free cash flow — cash after capex, working-capital swings, and the cash cost of interest and tax. Computed from components (Excel `Y6 = SUM(S6:X6)`), **not** Yahoo's opaque `Free Cash Flow` line.


## Formula

```text
fcf = ebitda + capex + ch_nwc + cash_interest + cash_taxes   (all cash-signed → straight sum)
```

Reported at two points — **latest** (each component at its **latest** TTM value) and **FY-baseline** (each component at its **FY-start** value), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM | + |
| `capex` | `get_capex` | TTM, negative | − |
| `ch_nwc` | `get_ch_nwc` | TTM, cash-signed | ± |
| `cash_interest` | `get_cash_interest` | TTM, negated (proxy) | − |
| `cash_taxes` | `get_cash_taxes` | TTM current-tax (proxy) | − |


## Caveats & proxies

`cash_interest` and `cash_taxes` are accrual proxies, so `fcf` carries `is_proxy=True`.


## Simplified logic

```python
parts = [get_ebitda, get_capex, get_ch_nwc, get_cash_interest, get_cash_taxes]
latest = sum(p(api)['latest']['value']      for p in parts)
fy     = sum(p(api)['fy_baseline']['value'] for p in parts)
```
