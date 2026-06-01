# EBITDA / Adjusted EBITDA

`ebitda_to_adj_ebitda`

!!! info "At a glance"

    **Basis:** `derived` &nbsp;·&nbsp; **Unit:** `x`


Ratio of reported to adjusted EBITDA — how much 'adjustment' is in the headline number. Near 1.0 means few add-backs.


## Formula

```text
ebitda_to_adj_ebitda = ebitda / adj_ebitda
```

Reported at two points — **latest** (ratio of each component's latest) and **FY-baseline** (ratio of each component's FY value), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `ebitda` | `get_ebitda` | TTM | numerator |
| `adj_ebitda` | `get_adj_ebitda` | TTM | denominator |
