# Cash Interest

`cash_interest`

!!! info "At a glance"

    **Basis:** `ttm` &nbsp;·&nbsp; **Unit:** `mm` &nbsp;·&nbsp; **Proxy:** ⚠️ yes


Trailing-twelve-month cash interest paid. Stored **negative**. Yahoo exposes no cash-paid-for-interest line, so the accrual interest expense is used as a proxy.


## Formula

```text
cash_interest = -(TTM rolling of income_stmt['Interest Expense'])
```

Reported at two points — **latest** (−Σ of the last 4Q / 2H of `Interest Expense`) and **FY-baseline** (−(last annual `Interest Expense`)), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Interest Expense` | `income_stmt['Interest Expense']` | TTM-rolled, **negated** | − (outflow) |


## Caveats & proxies

**Proxy.** Accrual interest runs above true cash interest (it includes non-cash OID / issuance-cost amortization and timing). Flagged `is_proxy=True`; any field built on it inherits the flag.


## Simplified logic

```python
return resolve_field(api, 'cash_interest')   # sign=-1 applied in the registry
```
