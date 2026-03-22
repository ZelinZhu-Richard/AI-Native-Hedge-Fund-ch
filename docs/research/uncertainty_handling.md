# Uncertainty Handling

## Purpose

The system should never imply that a signal is precise when the supporting structure is weak.

Day 19 strengthens this by making uncertainty explicit in the signal-arbitration layer.

## What Uncertainty Means In This Repository

Current uncertainty is structural, not statistical.

It reflects visible properties such as:

- whether signal confidence was explicitly recorded
- whether lineage is complete
- whether evidence support is strong or weak
- whether the signal is fresh or stale relative to an `as_of_time`
- whether the signal is time-eligible at the arbitration cutoff
- whether the signal is validated or still provisional

It does not mean:

- probability of profit
- expected forecast error
- confidence interval around returns
- model calibration quality

## Two Different Layers

### Raw signal confidence

`Signal.confidence` remains part of the base signal contract.

That object records whatever explicit confidence and uncertainty the signal-generation workflow emitted.

### Arbitration-layer uncertainty

`UncertaintyEstimate` is a Day 19 interpretation layer over the visible signal state.

It records:

- `uncertainty_score`
- whether uncertainty came from `signal_confidence` or a fallback
- whether lineage is complete
- current validation status
- optional evidence grade
- freshness state
- explicit contributing factors

This keeps the raw signal unchanged while still giving downstream workflows something inspectable.

## Current Uncertainty Rules

The current rules are intentionally simple:

- if `Signal.confidence.uncertainty` exists, use it
- otherwise use `1.0` and record `missing_confidence_fallback`
- derive freshness from `effective_at` relative to `as_of_time`
- exclude future-effective signals before freshness ranking instead of treating them as stale
- derive lineage completeness from required feature and evidence lineage fields
- carry evidence grade forward when an `EvidenceAssessment` is available

Freshness states are:

- `fresh`
- `aging`
- `stale`
- `unknown`

These states are operational context, not predictions.

## Why This Matters

Signals in this repo can look structurally similar while being very different in maturity.

Examples:

- a strong-looking score with weak evidence support
- an approved-looking signal with incomplete lineage
- a candidate signal that is already stale at review time
- overlapping signals that appear independent but reuse the same support

Without explicit uncertainty handling, those cases are easy to overread.

## How Downstream Workflows Use Uncertainty Today

Portfolio construction:

- prefers the arbitration-selected primary signal when available
- produces no position ideas when arbitration withholds a primary signal
- still warns when arbitration is missing entirely

Risk review:

- keeps missing arbitration visible
- keeps signal conflicts visible
- still separately warns on candidate or unvalidated signals

Experiment tracking:

- can record `SignalCalibration` and `SignalConflict` artifacts as experiment diagnostics

## What Remains Simple

- no statistical calibration
- no learned uncertainty model
- no cross-run uncertainty tracking
- no posterior-style combination of multiple signal families
- no hard downstream gate based on uncertainty alone

The system is still using deterministic heuristics so uncertainty remains explainable and auditable.

## Safe Interpretation

Treat the current uncertainty layer as a warning and comparison system.

It can tell you:

- where the structure is weak
- where timing is stale
- where timing is not yet eligible
- where support is thin
- where confidence is missing

It cannot tell you whether the market outcome will validate the signal.
