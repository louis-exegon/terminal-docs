# Unlevered Free Cash Flow

`ufcf`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `mm`


Financing-neutral (unlevered) free cash flow. Charges unlevered tax on EBIT, not on the levered interest bill. Feeds the structural model's barrier drift — distinct from levered `fcf`.


## Formula

```text
ufcf = ebitda − (ebit × tax_rate) + capex + ch_nwc
```

Derivation note: `ebitda − ebit × tax` = NOPAT + D&A; subtracting capex (negative) and adding ΔNWC (cash-signed) gives the standard unlevered-FCF build.

| term | value | sign | contribution |
|---|---|---|---|
| `ebitda` | positive | + | cash earnings |
| `ebit × tax_rate` | positive × decimal = positive | − | unlevered tax charge |
| `capex` | **negative** (Yahoo convention) | + (adding a negative) | reduces UFCF |
| `ch_nwc` | cash-signed (negative = outflow) | + | reduces UFCF if NWC grew |

Reported at two points — **latest** (each component at its `latest` value) and **FY-baseline** (each component at its `fy_baseline` value), each with its exact `as_of` date. The `components` sub-dict records each component's value and date at both points. `period_consistent` flags when the components' dates diverge (the dateless `tax_rate` is excluded from that check).


## Inputs

| input | getter | transform | role / sign |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM (multi-tier) | + |
| `ebit` | `get_ebit` | TTM (primary or EBITDA−D&A fallback) | − (multiplied by tax_rate) |
| `tax_rate` | `get_tax_rate` | decimal, clamped [0, 0.40] | scales the tax charge |
| `capex` | `get_capex` | TTM, **negative** | adds as negative |
| `ch_nwc` | `get_ch_nwc` | TTM, cash-signed | adds; negative if NWC grew |


## Simplified logic

```python
v = {k: getter(api)['latest']['value'] for k in parts}
ufcf = v['ebitda'] - v['ebit'] * v['tax'] + v['capex'] + v['ch_nwc']
# same formula applied to fy_baseline values for the FY point
```
