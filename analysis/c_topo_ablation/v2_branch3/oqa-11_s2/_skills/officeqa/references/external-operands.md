# Separate document facts from external operands

Use this chapter when a task combines values found in the provided document with
an exchange rate, market price, real-price series, CPI-based constant-dollar
conversion, or another operand whose provenance is not already explicit in the
source files.

```python
def choose_operand(candidates, requested_measure, requested_direction):
    matches = []
    for candidate in candidates:
        if candidate["measure"] != requested_measure:
            continue
        if candidate["direction"] != requested_direction:
            continue
        matches.append(candidate)
    if not matches:
        raise ValueError("no candidate matches requested measure and direction")
    return matches[0]
```

## Procedure

1. Enumerate every operand in the planned computation before calculating.
2. Label each operand as either document-provided or externally required.
3. For each external operand, record the exact requested measure type: level vs
   index, annual average vs point-in-time, monthly vs annual frequency, seasonal-
   adjustment status, historical vintage or rebasing, nominal vs real, and directional
   convention such as base-per-quote vs quote-per-base.
4. For outside price operands, also pin down per-unit basis, currency basis, and whether
   the candidate is an actual price level or only a rebased/index presentation.
5. Reject semantically nearby document tables or external series that share topic
   words but express a different measure type, adjustment basis, rebasing, or unit basis.
6. Run a magnitude and direction sanity check on the chosen operand before finalizing
   the arithmetic; if the computation would merely reproduce a statutory/accounting value
   or explode to an implausible scale, treat that as evidence the operand is wrong.

## Runtime branches

- **If the source files already contain the exact requested operand**, use the
  in-document series and keep the provenance label so you do not replace it with
  a nearby outside series.
- **If the source files contain only related indexes, country breakdowns, statutory/accounting
  bases, or a differently rebased presentation**, reject them and continue searching for
  the exact external operand instead of substituting them into the computation.
- **If the task requests constant-dollar conversion with a named CPI variant**, verify the
  exact CPI family, adjustment status, month/year, and historical scale before computing the
  ratio; for target-month dollars, the conversion factor should be `CPI_target / CPI_source`.
- **If the task requests a CPI-based comparison across nearby months**, pin both monthly CPI
  values on one consistent historical scale before any conversion; reject rebased modern CPI
  presentations or nearby month values that change the constant-dollar result.
- **If the task requests an outside commodity or market price**, verify that the selected
  series is the exact requested per-unit price level in compatible units, not a rebased real-price
  index, not a nominal substitute when the prompt asks for real price, and not a fallback to the
  document's statutory valuation basis.

```python
operand = choose_operand(candidates, requested_measure, requested_direction)
value = operand["value"]
if not is_plausible_magnitude(value, requested_direction):
    raise ValueError("operand magnitude inconsistent with requested convention")
result = combine(document_value, value)
```

## Verification

Verify four things before writing the answer: the chosen operand matches the
requested measure type, its direction matches the intended division or
multiplication, its frequency and vintage/adjustment status match the prompt,
and its magnitude is plausible for that convention. If any check fails, stop and
return to candidate selection; first remove indexes, wrong-vintage series,
wrong-adjustment variants, wrong unit-basis candidates, and reversed-direction series
from the candidate list, then re-evaluate provenance before any further computation.
If a CPI conversion still looks wrong after document-side extraction is verified,
re-open the CPI variant/scale choice before touching the Treasury values again.
