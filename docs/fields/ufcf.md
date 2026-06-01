# Unlevered Free Cash Flow

`ufcf`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `mm`


Unlevered free cash flow — financing-neutral cash generation. Feeds the structural model's barrier drift. **Not** levered FCF: there is no interest term and tax is charged on EBIT.


## Formula

```text
ufcf = ebitda - (ebit × tax_rate) + capex + ch_nwc
     [ = NOPAT + D&A - CapEx - ΔNWC ; D&A cancels, so reuse EBITDA ]
```

Reported at two points — **latest** (each component at its **latest** value) and **FY-baseline** (each component at its **FY-start** value), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM | + |
| `ebit` | `get_ebit` | TTM; × tax_rate gives unlevered tax | − tax |
| `tax_rate` | `get_tax_rate` | decimal | — |
| `capex` | `get_capex` | TTM, negative | + (already −) |
| `ch_nwc` | `get_ch_nwc` | TTM, cash-signed | + |


## Caveats & proxies

Computed at both points; `period_consistent` flags if the components' dates diverge (dateless `tax_rate` is excluded from that check).


## Simplified logic

```python
v = {k: get(k)['latest']['value'] for k in parts}
ufcf = v['ebitda'] - v['ebit']*v['tax'] + v['capex'] + v['ch_nwc']
```
