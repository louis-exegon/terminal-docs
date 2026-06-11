# EBITDA / Adjusted EBITDA

`ebitda_to_adj_ebitda`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x`


Earnings-quality ratio: reported EBITDA divided by normalized EBITDA. A value near 1.0 means few add-backs; values substantially above 1.0 signal heavy management adjustments (the reported figure includes one-off charges that inflate the adjusted version vs. the other way around).


## Formula

```text
ebitda_to_adj_ebitda = ebitda / adj_ebitda
```

Reported at two points — **latest** (TTM `ebitda` / TTM `adj_ebitda`) and **FY-baseline** (annual `ebitda` / annual `adj_ebitda`), each with its exact `as_of` date.


## Inputs

| input | getter | transform | role |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM (multi-tier: yf headline → first principles) | numerator |
| `adj_ebitda` | `get_adj_ebitda` | TTM rolling of `income_stmt['Normalized EBITDA']` | denominator |


## Simplified logic

```python
v['ebitda']   = get_ebitda(api)['latest']['value']
v['adj_ebitda'] = get_adj_ebitda(api)['latest']['value']
ratio = v['ebitda'] / v['adj_ebitda']
```
