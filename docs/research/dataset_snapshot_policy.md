# Dataset Snapshot Policy

## Purpose

Dataset snapshots exist to preserve what a workflow was allowed to know, not just what files happened to exist later.

Day 8 strengthens the snapshot contract so experiment recording and replay stay temporally honest.

## Snapshot Time Fields

`DataSnapshot` now distinguishes:

- `event_time_start`
  - earliest event time represented by the snapshot
- `watermark_time`
  - latest event time safely included
- `ingestion_cutoff_time`
  - latest ingestion boundary included in the snapshot
- `information_cutoff_time`
  - latest time downstream consumers are allowed to assume is available
- `snapshot_time`
  - when the snapshot was materialized as a workflow-owned artifact

These are not interchangeable.

## Validation Rules

Current schema validation enforces:

- `event_time_start <= watermark_time` when both are present
- `watermark_time <= information_cutoff_time <= snapshot_time` when relevant
- `ingestion_cutoff_time <= snapshot_time`

If a workflow cannot satisfy those semantics honestly, it should leave a field null rather than inventing a convenient timestamp.

## Manifest vs Partition vs Reference

The registry uses three layers of dataset metadata:

- `DatasetManifest`
  - describes one materialized dataset version and its schema
- `DatasetPartition`
  - describes one logical slice inside that dataset version
- `DatasetReference`
  - links an experiment to the specific manifest-backed snapshot it used

`DataSnapshot` remains the workflow-owned point-in-time artifact. The registry references it; the registry does not replace it.

## Current Backtesting Usage

Day 8 backtesting builds two workflow-owned snapshots:

- candidate signal snapshot
- synthetic price snapshot

The experiment registry then builds:

- one source-version record per snapshot
- one partition per snapshot
- one manifest per snapshot
- one dataset reference per snapshot

This means the backtest run can be replayed later without duplicating the snapshot payload itself.

## Local Filesystem Behavior

Current Day 8 behavior is intentionally simple:

- workflow-owned snapshots live under `artifacts/backtesting/snapshots/`
- registry metadata lives under `artifacts/experiments/`
- storage URIs point to local filesystem paths

This is enough for local replay and integration testing. It is not yet a durable production registry.

## Current Limitations

- no object-store or warehouse integration yet
- no snapshot catalog query layer yet
- no explicit late-correction or restatement policy yet
- no cross-workflow snapshot selection service yet

## Next Extension Point

The next step is to apply the same snapshot-reference discipline upstream:

- feature mapping should record the research and parsing snapshots it consumed
- signal generation should record the feature snapshot and research slice it consumed
- later evaluation work should select snapshots explicitly rather than inferring latest artifacts
