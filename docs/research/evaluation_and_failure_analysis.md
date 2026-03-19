# Evaluation And Failure Analysis

## Purpose

Day 10 adds a deterministic evaluation layer that records structural quality, explicit failures, and basic robustness checks as typed artifacts.

The goal is not to prove edge.
The goal is to make failure visible, stored, and reviewable.

## Primary Artifacts

The evaluation layer now persists under `artifacts/evaluation/`:

- `reports/`
- `metrics/`
- `failure_cases/`
- `robustness_checks/`
- `comparison_summaries/`
- `coverage_summaries/`

The primary Day 10 artifact is `EvaluationReport`.

Supporting contracts are:

- `MetricValue`
- `EvaluationMetric`
- `FailureCase`
- `RobustnessCheck`
- `ComparisonSummary`
- `CoverageSummary`

## What The System Evaluates Today

The current checks support these dimensions:

- `provenance_completeness`
- `hypothesis_support_quality`
- `feature_lineage_completeness`
- `signal_generation_validity`
- `backtest_artifact_completeness`
- `strategy_comparison_output`
- `risk_review_coverage`

Every material problem should become either:

- a `FailureCase`
- a `RobustnessCheck`
- or an explicit warning metric

It should not be hidden only inside free-form notes.

## Current Workflow Integration

The first integrated target is the Day 9 ablation workflow.

After `AblationResult` is built, the system now evaluates:

- provenance completeness across the shared ablation slice
- Day 5 text feature lineage completeness
- research-signal validity for the text baseline input slice
- variant-signal validity across all strategy families
- child backtest completeness and experiment linkage
- strategy comparison family coverage and output integrity
- first-pass robustness checks over timestamps, source consistency, missing data, extraction completeness, and strategy config validity

The ablation workflow now returns:

- `evaluation_report`
- `evaluation_metrics`
- `failure_cases`
- `robustness_checks`
- `comparison_summary`
- `coverage_summaries`

## Failure Recording Rules

Failure recording is explicit by design.

Current failure categories include:

- `missing_evidence`
- `weak_support`
- `invalid_timestamp`
- `broken_lineage`
- `incomplete_config`
- `empty_output`
- `suspicious_assumption`
- `source_inconsistency`
- `missing_provenance`

Current severity and blocking semantics are structural, not economic:

- `high` or blocking failures mean the artifact should not be treated as structurally trustworthy
- `warn` means the artifact is present but thin, incomplete, or operationally weak
- `pass` means only that the evaluated structural checks passed

## Coverage And Comparison Summaries

`CoverageSummary` is used to expose how much of a slice actually passed a given structural check.

`ComparisonSummary` is used to describe multi-variant output integrity.
Its ordering is explicitly mechanical only.
It does not imply validation, promotion, or a proven winner.

## What This Layer Does Not Do

Day 10 does not add:

- statistical significance tests
- calibration analysis
- economic attribution
- signal promotion logic
- downstream enforcement

It also does not claim that a good backtest row or comparison row means a strategy is trustworthy.

## Current Limitations

- The first integrated target is the Day 9 ablation workflow, not the full repo.
- Portfolio and paper-trade workflows are not yet evaluated automatically.
- The layer is cutoff-aware and snapshot-referential, but not fully snapshot-native upstream.
- Evaluation artifacts are stored locally and are not yet part of a durable review-state system.

## Next Honest Extension

The next step is to connect these evaluation artifacts to a reviewed promotion gate so downstream workflows can distinguish:

- exploratory candidate signals
- evaluated but still unreviewed signals
- reviewed signals that are eligible for stricter downstream use
