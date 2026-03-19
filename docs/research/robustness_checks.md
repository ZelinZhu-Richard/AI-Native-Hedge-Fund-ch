# Robustness Checks

## Purpose

Day 10 robustness checks are simple, explicit structural checks.

They exist to answer:

- did the workflow encounter brittle inputs
- did timestamps look suspicious
- did source identity drift
- was the upstream slice incomplete
- was the strategy config internally inconsistent

They do not claim statistical robustness or market robustness.

## Current Check Kinds

The current schema supports:

- `missing_data_sensitivity`
- `timestamp_anomaly`
- `source_inconsistency`
- `incomplete_extraction_artifact`
- `invalid_strategy_config`

## Current Semantics

### `missing_data_sensitivity`

- warns when required strategy families emit no signals
- warns when comparison coverage is too thin to treat the slice as a fair comparison

### `timestamp_anomaly`

- fails when signal windows are invalid
- fails when signal timing exceeds source snapshot cutoffs
- fails when snapshot ordering is internally inconsistent

### `source_inconsistency`

- fails when company identity drifts across the shared slice
- fails when source snapshot partitioning disagrees with the requested evaluation slice

### `incomplete_extraction_artifact`

- warns or fails when upstream text artifacts are missing evidence linkage needed for honest reuse

### `invalid_strategy_config`

- fails on duplicate families
- fails on spec and variant family mismatches
- fails on broken shared-config alignment across the evaluation slice and backtest config

## Pass, Warn, And Fail

- `pass` means the specific structural check did not detect an issue
- `warn` means the slice is still usable for inspection, but thin or brittle
- `fail` means the check found a structural problem that should not be ignored

These are not performance grades.

## What Robustness Does Not Mean Here

A passing robustness check does not mean:

- a strategy is profitable
- a comparison is statistically meaningful
- a signal is promoted
- a downstream workflow may bypass review

It only means the evaluated structural problem was not detected by the current deterministic checks.

## Current Integration

The first concrete integration is the Day 9 strategy ablation workflow.

Each completed ablation now records explicit robustness-check artifacts alongside:

- evaluation metrics
- failure cases
- coverage summaries
- one evaluation report

## Next Extension Point

The next honest extension is to connect robustness outcomes to review and promotion decisions so that clearly brittle slices cannot silently flow into stricter downstream workflows.
