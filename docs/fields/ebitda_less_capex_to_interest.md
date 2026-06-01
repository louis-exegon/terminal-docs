# (EBITDA − Capex) / Interest

`ebitda_less_capex_to_interest`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x` &nbsp;·&nbsp; **Proxy:** ⚠️ yes


Coverage multiple: cash earnings after capex relative to the cash cost of interest (Excel `AE6`).


## Formula

```text
ebitda_less_capex_to_interest = (ebitda + capex) / -cash_interest
```

Reported at two points — **latest** (ratio at each component's latest) and **FY-baseline** (ratio at each component's FY value), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM | + |
| `capex` | `get_capex` | TTM, negative (so it reduces the numerator) | + |
| `cash_interest` | `get_cash_interest` | TTM, negated again in the denominator | denominator |


## Caveats & proxies

Inherits the `cash_interest` accrual proxy in the denominator, which amplifies that gap. `is_proxy=True`.


## Simplified logic

```python
m = (v['ebitda'] + v['capex']) / (-v['cash_interest'])
```
