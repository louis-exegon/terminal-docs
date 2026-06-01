# Cash Taxes

`cash_taxes`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm` &nbsp;·&nbsp; **Proxy:** ⚠️ yes


Trailing-twelve-month cash taxes paid. Stored **negative**. Approximated by the *current* tax expense (total provision less the non-cash deferred piece).


## Formula

```text
cash_taxes = -(TTM Tax Provision - TTM Deferred Tax)     (fallback: -(TTM Tax Provision))
```

Reported at two points — **latest** (−(TTM `Tax Provision` − TTM `Deferred Tax`)) and **FY-baseline** (−(annual `Tax Provision` − annual `Deferred Tax`)), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Tax Provision` | `income_stmt['Tax Provision']` | TTM-rolled (total tax) | + before negation |
| `Deferred Tax` | `cash_flow['Deferred Tax']` (fallback `Deferred Income Tax`) | TTM-rolled, subtracted to leave current tax | − |


## Caveats & proxies

**Proxy.** Still omits the change in taxes-payable that only the 10-K 'cash paid for income taxes' line captures (Yahoo lacks it). If no deferred line exists, falls back to total provision.


## Simplified logic

```python
prov = TTM('Tax Provision');  deferred = TTM('Deferred Tax')
return -(prov - deferred)   # negated; current-tax proxy
```

## Reconciliation (Ball)

Ball LTM ≈ **−161**, FY2025 ≈ **−180**.

