# Free Cash Flow (Levered)

`fcf`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `mm` &nbsp;·&nbsp; **Proxy:** ⚠️ conditional


Levered free cash flow — cash after capex, working-capital swings, and the cash cost of interest and tax. Built from components; two cross-check variants are surfaced alongside.

!!! warning "Sign convention change"
    `cash_interest` and `cash_taxes` are now **positive magnitudes** (cash paid out). The FCF formula **subtracts** them — not adds.


## Formula

```text
fcf = ebitda + capex + ch_nwc − cash_interest − cash_taxes
```

| term | value | sign | contribution |
|---|---|---|---|
| `ebitda` | positive | + | cash earnings |
| `capex` | **negative** (Yahoo convention) | + (adding a negative) | reduces FCF |
| `ch_nwc` | cash-signed (negative = outflow) | + | reduces FCF if NWC grew |
| `cash_interest` | **positive magnitude** (cash paid) | − | reduces FCF |
| `cash_taxes` | **positive magnitude** (cash paid) | − | reduces FCF |

Reported at two points — **latest** (each component at its `latest` value) and **FY-baseline** (each component at its `fy_baseline` value), each with its exact `as_of` date.


## Inputs

| input | getter | transform | role / sign in formula |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM (multi-tier) | + |
| `capex` | `get_capex` | TTM, **negative** | + (already negative) |
| `ch_nwc` | `get_ch_nwc` | TTM, cash-signed | + (negative if NWC grew) |
| `cash_interest` | `get_cash_interest` | TTM, **positive magnitude** (multi-tier: cash → SEC → accrual) | − (subtracted) |
| `cash_taxes` | `get_cash_taxes` | TTM, **positive magnitude** (multi-tier: cash → SEC) | − (subtracted) |


## Variants (in order of preference)

All three are computed and exposed in `variants`:

| # | label | formula |
|---|---|---|
| 1 | components (EBITDA+capex+ΔNWC−int−tax) | `ebitda + capex + ch_nwc − cash_interest − cash_taxes` — **primary** |
| 2 | yfinance Free Cash Flow (direct) | `TTM cash_flow['Free Cash Flow']` |
| 3 | Operating CF − capex | `TTM Operating Cash Flow + capex` (capex negative) |

Variant 1 is the primary (our build). Variants 2 and 3 are cross-checks; they do not drive the output.


## Caveats & proxies

`is_proxy` is inherited from the components. When `cash_interest` falls back to the accrual proxy (Tier 3 of its own ladder) or `cash_taxes` is unavailable, `fcf` inherits `is_proxy=True`.


## Simplified logic

```python
v = {k: getter(api)['latest']['value'] for k in parts}
fcf = v['ebitda'] + v['capex'] + v['ch_nwc'] - v['cash_interest'] - v['cash_taxes']
# same formula applied to fy_baseline values
```
