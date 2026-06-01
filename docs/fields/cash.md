# Cash & Equivalents

`cash`

!!! info "At a glance"

    **Basis:** `level` &nbsp;·&nbsp; **Unit:** `mm`


Cash, equivalents and short-term investments — a **balance-sheet level**, taken at the latest snapshot (not summed).


## Formula

```text
cash = balance_sheet['Cash Cash Equivalents And Short Term Investments']   (fallback 'Cash And Cash Equivalents')
```

Reported at two points — **latest** (the newest interim balance-sheet snapshot) and **FY-baseline** (the FY-end snapshot), each with its exact `as_of` date.


## Inputs

| input | source | transform | role / sign |
|---|---|---|---|
| `Cash line` | `balance_sheet['Cash Cash Equivalents And Short Term Investments']` | level (latest snapshot) | + |


## Simplified logic

```python
return resolve_field(api, 'cash')
```

## Reconciliation (Ball)

Ball latest ≈ **730**, FY2025 = **1,212**.

