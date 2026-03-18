# Baseline And Ablation Framework

## Purpose

Day 9 adds a comparison layer on top of the existing research, signal, and backtesting stack.

The goal is not to prove that text signals work.
The goal is to make comparisons honest, reproducible, and mechanically inspectable.

## Core Design Choice

The repository now compares strategy variants at the signal boundary, but it does **not** overload the research `Signal` contract for baseline work.

- `Signal`
  - still means a research-derived, evidence-linked candidate signal
- `StrategyVariantSignal`
  - now means a comparable evaluation-layer signal emitted by a baseline or blended strategy variant

This keeps naive and price-only baselines from pretending to have research evidence lineage they do not actually possess.

## Supported Baseline Families

The current framework supports exactly four Day 9 families:

- `naive_baseline`
  - one neutral hold-cash comparable signal
- `price_only_baseline`
  - deterministic 3-bar close-to-close momentum
- `text_only_candidate_baseline`
  - direct adaptation of the existing Day 5 text-only candidate signals
- `combined_baseline`
  - fixed 50/50 blend of the latest eligible text-only signal and the current price-only momentum signal

## Main Contracts

The Day 9 schema layer adds:

- `StrategySpec`
- `StrategyVariant`
- `StrategyVariantSignal`
- `EvaluationSlice`
- `AblationConfig`
- `AblationVariantResult`
- `AblationResult`

These live in `libraries/schemas/research.py` alongside the existing research, signal, backtest, and experiment contracts.

## Execution Flow

The Day 9 workflow is:

1. load shared research signals, features, and the synthetic price fixture
2. build shared input snapshots for the ablation slice
3. materialize comparable signals for each strategy variant
4. persist those variant signals under `artifacts/ablation/variant_signals/`
5. run one child backtest per variant with the existing Day 6 backtest engine
6. record child experiments through the Day 8 experiment registry
7. assemble an `AblationResult`
8. record one parent ablation experiment that links the comparison run to its child backtests

## Artifact Layout

Day 9 persists local artifacts under `artifacts/ablation/`:

- `strategy_specs/`
- `strategy_variants/`
- `evaluation_slices/`
- `source_snapshots/`
- `variant_signals/`
- `ablation_configs/`
- `ablation_results/`

Child backtests still persist under `artifacts/backtesting/ablation_runs/`.

## Experiment Integration

Experiment recording now has two levels for ablations:

- child experiment per variant backtest
- parent experiment for the ablation harness itself

The parent experiment records:

- the ablation config
- the evaluation slice
- shared source snapshots
- the strategy specs and variants
- the final ablation result
- child experiment links

## What The Framework Supports

The current framework supports:

- deterministic baseline definitions
- same-window comparisons across multiple variants
- shared input-slice handling
- experiment-linked variant backtests
- structured comparison results without hard-coded conclusions

## What It Does Not Support

The current framework does **not** support:

- statistical significance testing
- calibrated model comparison
- multi-name portfolio comparisons
- real market data
- promotion of a “best” strategy into truth
- live execution or autonomous strategy selection

## Honest Interpretation Rule

`AblationResult` rows may be mechanically ordered by a declared comparison metric.

That ordering means only:

- the rows were sorted mechanically

It does **not** mean:

- one strategy is validated
- one strategy has a proven edge
- one strategy should be promoted downstream automatically
