# Change in Net Working Capital

`ch_nwc`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm`


Trailing-twelve-month change in net working capital, **cash-signed** (negative = working capital increased = cash consumed). Two-tier resolution: the cash-flow statement headline is preferred; the balance-sheet proxy is used as fallback.

!!! note "EDGAR removed"
    SEC EDGAR has no us-gaap tag or combination that reproduces Bloomberg's `TRAIL_12M_CHNG_IN_WORK_CAP_OTHER` residual definition. EDGAR is not used for this field.


## Formula

```text
Tier 1 (primary):  ch_nwc = TTM rolling of cash_flow['Change In Working Capital']

Tier 2 (proxy):    NWC_t  = AR_t + Inventory_t − AP_t
                   ch_nwc = −(NWC_t − NWC_{t-1})          per period
                   latest = TTM rolling of the above series
```

Reported at two points — **latest** (Σ of the last 4Q / 2H of the resolved tier) and **FY-baseline** (last annual value of the resolved tier), each with its exact `as_of` date.


## Inputs

| input | source | transform | priority |
|---|---|---|---|
| `Change In Working Capital` | `quarterly_cash_flow['Change In Working Capital']` | TTM-rolled, cash-signed | Tier 1 (primary) |
| `Accounts Receivable` | `quarterly_balance_sheet['Accounts Receivable']` | level; diff'd with adjacent period | Tier 2 |
| `Inventory` | `quarterly_balance_sheet['Inventory']` | level; set to 0 if absent (asset-light businesses) | Tier 2 |
| `Accounts Payable` | `quarterly_balance_sheet['Accounts Payable']` | level (subtracted in NWC formula) | Tier 2 |


## Tier resolution

**Picker sort key** (lowest wins):

```
(is_stale, priority, is_zero_latest, −recency)
```

Tier 1 (priority 1) wins unless stale or zero. Tier 2 (priority 2) is marked `is_proxy=True`.

**Tier 2 mechanics:**
- `NWC_t = AR_t + Inventory_t − AP_t` at each balance-sheet date (quarterly or annual).
- `ch_nwc_t = −(NWC_t − NWC_{t-1})` between adjacent dates.
- The resulting change-series is fed into the same TTM-rolling engine as Tier 1 (sum of last 4 quarterly diffs for `latest`).
- `Inventory` is set to 0 when absent (asset-light or service companies with no inventory line).
- Requires at least `AR` and `AP` to be non-empty; otherwise Tier 2 also returns nothing.


## Caveats & proxies

Tier 2 operates on a **balance-sheet** basis, which can diverge from the cash-flow statement for several reasons (reclassifications, currency translation, non-operating WC items). It may flip sign vs. Tier 1 on some names. `is_proxy=True` when Tier 2 is the primary.


## Simplified logic

```python
# Tier 1 — CFS headline (almost always available)
q1 = quarterly_cash_flow['Change In Working Capital']   # cash-signed
latest = q1.iloc[-ppy:].sum()

# Tier 2 — BS proxy (fallback)
nwc   = AR + Inventory - AP                            # per balance-sheet date
q2    = -(nwc.diff().dropna())                         # change, cash-signed
latest = q2.iloc[-ppy:].sum()
```
