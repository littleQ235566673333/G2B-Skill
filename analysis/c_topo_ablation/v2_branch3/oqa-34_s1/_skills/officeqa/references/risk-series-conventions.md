# Derive and verify risk-series conventions before tail metrics

Use this chapter when a task asks for expected shortfall, VaR, or another tail
risk measure but the raw table provides quoted levels rather than an already-defined
return or loss series.

```python
import numpy as np

def compute_tail_metric(levels, series_kind, confidence=0.95):
    if series_kind == "price_return":
        derived = [(cur - prev) / prev * 100 for prev, cur in zip(levels, levels[1:])]
    elif series_kind == "yield_change":
        derived = [cur - prev for prev, cur in zip(levels, levels[1:])]
    elif series_kind == "loss_series":
        derived = [loss_fn(prev, cur) for prev, cur in zip(levels, levels[1:])]
    else:
        raise ValueError("unsupported risk-series convention")
    q = np.percentile(derived, (1 - confidence) * 100)
    return np.mean([x for x in derived if x <= q])
```

## Procedure

1. Restate the exact helper series the prompt requires before computing any percentile:
   returns on prices, changes in yields, spreads, or losses.
2. Record the sign convention explicitly: whether more negative means worse, whether
   losses are positive or negative, and whether the answer should stay in percent units.
3. Build the derived series from adjacent observations only after the convention is locked.
4. Verify the number of derived observations and inspect a few sample transformed values
   to ensure they match the intended convention.
5. Compute the percentile threshold and tail average only on that validated derived series.

## Runtime branches

- **If the prompt frames risk in portfolio-return language**, prefer the return or loss
  definition implied by the priced asset, not a default transformation on quoted yields.
- **If the raw data are quoted yields or rates**, decide explicitly whether the metric is on
  yield changes, price returns derived from those yields, or another loss convention before
  computing the tail statistic.
- **If the task states the answer as a percent with a sign**, keep the helper series and the
  final tail average in that same percent/sign convention rather than flipping to an absolute
  magnitude by default.

```python
derived = build_helper_series(levels, convention)
if len(derived) != max(0, len(levels) - 1):
    raise ValueError("unexpected derived-series length")
threshold = np.percentile(derived, 5)
es95 = np.mean([x for x in derived if x <= threshold])
```

## Verification

Verify three things before writing the answer: the helper series matches the financial
convention named in the prompt, the sign/percent convention of the tail average matches
that helper series, and the result is a tail metric on the derived series rather than on
raw reported levels. If any check fails, stop and return to the convention-selection step;
first choose among price-return, yield-change, and loss-series interpretations explicitly,
then rebuild the helper series before recomputing the percentile and tail mean.
