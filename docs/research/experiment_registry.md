# Experiment Registry

## Purpose

Research workflows are not reproducible unless the system records:

- what configuration was used
- which dataset snapshots were in scope
- which workflow run produced the result
- which artifacts were emitted
- which metrics were recorded

Day 8 adds that metadata spine without pretending to be a full ML platform.

## Current Day 8 Capability

The local experiment registry now persists typed records under `artifacts/experiments/`:

- `experiment_configs/`
- `run_contexts/`
- `dataset_manifests/`
- `dataset_partitions/`
- `source_versions/`
- `dataset_references/`
- `experiments/`
- `experiment_artifacts/`
- `experiment_metrics/`

The core contracts are:

- `Experiment`
- `ExperimentConfig`
- `ExperimentParameter`
- `RunContext`
- `DatasetManifest`
- `DatasetPartition`
- `DatasetReference`
- `SourceVersion`
- `ExperimentArtifact`
- `ExperimentMetric`

## Why Dataset References Matter

Artifacts alone are not enough. A backtest result without explicit dataset references cannot be replayed honestly.

The registry therefore records dataset references separately from output artifacts:

- `DataSnapshot` remains owned by the workflow that created it
- `DatasetManifest` describes the materialized dataset slice
- `DatasetReference` links the experiment to the manifest-backed snapshot actually used
- `SourceVersion` captures minimal replay watermarks for the source family

This keeps snapshot ownership with the producing workflow while still giving the experiment record enough metadata to explain the run.

## First Integrated Workflow

Backtesting is the first workflow integrated with the registry.

For each recorded backtest run, the system now:

1. records a stable `ExperimentConfig` derived from `BacktestConfig` and `ExecutionAssumption`
2. records a `RunContext` with workflow run ID, requester, environment, artifact root, and `as_of_time`
3. builds signal and price dataset manifests plus dataset references from the backtest snapshots
4. creates an `Experiment` in `running`
5. finalizes the experiment with:
   - `BacktestRun`
   - `PerformanceSummary`
   - both `DataSnapshot` records
   - `BenchmarkReference` artifacts
   - numeric metrics such as `gross_pnl`, `net_pnl`, `trade_count`, and benchmark simple returns

## Reproducibility Contract

The current registry is metadata-first. It does not duplicate payloads that are already owned by another workflow.

Replaying a Day 8-recorded backtest depends on:

- the persisted `ExperimentConfig`
- the persisted `RunContext`
- the referenced `DataSnapshot` records
- the manifest and source-version metadata attached to those snapshots
- the persisted workflow outputs referenced by `ExperimentArtifact`

## Current Limitations

- only backtesting is integrated today
- registry storage is local filesystem only
- there is no cross-run query service yet
- there is no promotion gate from exploratory experiments to validated experiments yet
- model references exist in the schema but are not used by the current backtest flow

## Next Extension Point

The next honest extension is upstream, not downstream:

- integrate experiment recording into feature mapping
- integrate experiment recording into signal generation
- move from cutoff-aware loading to explicit snapshot selection
