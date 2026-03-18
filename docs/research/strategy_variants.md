# Strategy Variants

## Purpose

This document defines the built-in Day 9 comparison variants.

These are not portfolio strategies.
They are deterministic evaluation variants used to compare different input families under the same time window and backtest rules.

## Variant Definitions

### `naive_baseline`

- input family: synthetic daily prices
- comparable signal behavior:
  - emit one neutral `StrategyVariantSignal`
  - `stance = monitor`
  - `primary_score = 0.0`
- intended role:
  - hold-cash anchor for the comparison harness

### `price_only_baseline`

- input family: synthetic daily prices
- rule:
  - 3-bar close-to-close momentum
- score:
  - `clamp((close_t / close_t-3 - 1.0) / 0.05, -1.0, 1.0)`
- stance thresholds:
  - `positive` when score `>= 0.25`
  - `negative` when score `<= -0.25`
  - `monitor` otherwise
- intended role:
  - simple market-only comparator

### `text_only_candidate_baseline`

- input family: persisted Day 5 research `Signal`
- rule:
  - adapt the existing candidate signal 1:1 into `StrategyVariantSignal`
- preserved fields:
  - `effective_at`
  - `primary_score`
  - upstream `source_signal_ids`
- intended role:
  - compare the current text-derived candidate pipeline against simpler baselines

### `combined_baseline`

- input families:
  - persisted Day 5 research `Signal`
  - synthetic daily prices
- rule:
  - latest eligible text-only signal plus current price-only momentum signal
  - fixed blend: `0.5 * text_score + 0.5 * price_score`
- emission rule:
  - no combined signal is emitted until both components exist
- intended role:
  - test whether a simple blended baseline behaves differently from the text-only slice

## Shared Backtest Rule

All Day 9 variants currently share the Day 6 backtest skeleton:

- daily decisions
- latest eligible signal selection
- next-bar-open execution
- explicit transaction cost and slippage placeholders
- flat baseline and buy-and-hold within-run benchmarks

## Temporal Rules

The built-in variants follow these temporal boundaries:

- `text_only_candidate_baseline`
  - uses only persisted research signals already emitted by the current time
- `price_only_baseline`
  - uses only historical closes through the current bar
- `combined_baseline`
  - uses the latest eligible text signal and the current price-only momentum signal
- no variant may use future feature availability through the child backtest path

## Review And Validation Status

All Day 9 comparable signals remain:

- `status = candidate`
- `validation_status = unvalidated`

This is deliberate.
The ablation harness is an evaluation scaffold, not a promotion gate.

## Current Limitations

- one-company comparisons only
- synthetic price fixture only
- no significance testing
- no hyperparameter search
- no conclusions encoded into the framework
