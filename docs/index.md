# HY Credit Screener — Field Reference

This is the field reference for the high-yield European corporate-bond credit screener, rebuilt on **free data (`yfinance`)** to replace the original Bloomberg dependencies.

Every issuer-level field is documented here: what it is, its exact formula, where each input is pulled from and how it is transformed, the proxies and caveats, a simplified code sketch, and a reconciliation note against the calibration name (**Ball Corp**, `BALL`).

For every field we report the metric **exactly as the Excel defines it**, at two points:

- **`latest`** — the newest available value (TTM rolled to the issuer's reporting cadence, the latest balance-sheet level, or the latest market value).
- **`fy_baseline`** — the same metric as of the **last annual statement**. This is the *guaranteed floor*: it always exists, even for annual-only reporters.

Each carries its exact `as_of` date. Derived fields additionally expose their **components** (the in-between values) at both points, plus a `period_consistent` flag that fires when the components' dates don't line up.

```python
import yfinance as yf
exec(open('screener.py').read())

api = yf.Ticker('BALL')
res = inspect(api)            # prints every field: latest + FY + component breakdown
all_fields = build_all(api)   # dict {field_name: contract}
```

See **[The field contract](concepts/contract.md)** for the output shape and **[The engine](concepts/engine.md)** for date / frequency handling.
