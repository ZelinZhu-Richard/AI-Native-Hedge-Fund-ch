# Day 19 Plan

## Summary

Day 19 adds a deterministic signal-arbitration layer between raw `Signal` artifacts and downstream portfolio consumers.

The goal is not probabilistic truth or a promotion gate.
The goal is to make same-company signals comparable, uncertainty-aware, conflict-preserving, and inspectable before they influence review-facing portfolio proposals.

## What Day 19 Adds

- `SignalCalibration`
- `UncertaintyEstimate`
- `ArbitrationRule`
- `SignalConflict`
- `RankingExplanation`
- `ArbitrationDecision`
- `SignalBundle`

It also adds:

- local signal-arbitration persistence under `artifacts/signal_arbitration/`
- portfolio consumption of arbitrated bundles when present
- non-blocking risk visibility for missing arbitration and detected conflicts
- experiment-registry recording of arbitration context

## Core Rules

Current Day 19 behavior is deterministic:

- clamp signal scores to `[-1, 1]`
- preserve explicit or fallback uncertainty
- detect directional, support, freshness, maturity, and duplicate-support conflicts
- rank signals lexicographically with no hidden weights
- suppress lower-ranked duplicate-support signals when stance agrees
- withhold primary selection when top opposing signals are in blocking disagreement

## Boundaries

Day 19 does not:

- validate signals
- approve signals
- synthesize a new canonical signal artifact
- guarantee downstream eligibility
- replace the Week 3 reviewed-and-evaluated signal gate

## Downstream Effect

Portfolio workflows now:

- prefer the arbitrated primary signal when available
- produce no position ideas when arbitration intentionally withholds a primary signal
- fall back to raw signals only when no arbitration bundle is present, and record that fallback explicitly

## Remaining Weaknesses

- calibration is heuristic and structural, not statistical
- the main real signal family is still narrow
- raw-signal fallback still exists when arbitration is absent
- arbitration does not yet hard-block downstream candidate-signal usage across the whole system

## Best Next Step

The next highest-leverage step remains the Week 3 priority:

- implement the real reviewed-and-evaluated signal eligibility gate, using arbitration output as inspectable context rather than mistaking it for approval
