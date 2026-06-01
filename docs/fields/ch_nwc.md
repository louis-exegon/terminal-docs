# Change in Net Working Capital

`ch_nwc`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month change in net working capital, **cash-signed** (negative = cash consumed by working capital). Resolved through a three-tier ladder, first that yields a value wins.


## Formula

```text
Tier 1: ch_nwc = TTM rolling of cash_flow['Change In Working Capital']
Tier 2: ch_nwc = TTM rolling of Σ(cash-flow working-capital component lines)
Tier 3: ch_nwc = -[(AR+Inventory-AP)_t - (AR+Inventory-AP)_{t-1}]   (balance-sheet proxy)
```

Reported at two points — **latest** (Σ of the last 4Q / 2H of the resolved tier) and **FY-baseline** (the last annual value of the resolved tier), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Change In Working Capital` | `cash_flow['Change In Working Capital']` | TTM-rolled, cash-signed | ± |
| `WC components (Tier 2)` | `cash_flow` Δ receivables/inventory/payables/other | summed, then TTM-rolled | ± |
| `AR / Inventory / AP (Tier 3)` | `balance_sheet` | year-on-year change of (AR+Inv−AP), negated | ± |


## Caveats & proxies

It is a **cash-flow** concept, not a balance-sheet level difference. Tier 3 uses a different (balance-sheet) basis and can flip sign on some names — it carries `is_proxy=True`.


## Simplified logic

```python
# Tier 1 (almost always available):
q = quarterly_cash_flow['Change In Working Capital']
return resolve_flow('ch_nwc', q, annual_equivalent)
```
