# Day 9 Plan

Status: `Planned`

## Goal

Extend reproducibility and snapshot discipline upstream so experiment recording is no longer backtest-only.

## Priority

Day 9 should not add more downstream complexity first.

The best next step is to make feature mapping and signal generation snapshot-aware and experiment-recorded, so the full research-to-signal chain can be replayed without relying on implicit latest-artifact selection.

## Planned Work

- integrate experiment recording into the Day 5 feature-mapping workflow
- integrate experiment recording into the Day 5 signal-generation workflow
- add explicit snapshot or artifact selection for those workflows instead of cutoff-only loading
- record produced feature and signal artifacts as experiment outputs
- record candidate-signal metrics that are structural and honest, not performance claims
- expand adversarial tests for multi-generation artifact replay

## What Day 9 Should Not Do

- portfolio optimization
- live execution
- fake evaluation metrics
- broad ML platform abstraction
- opaque experiment dashboards

## Carry-Forward

Once feature and signal generation are experiment-recorded and snapshot-aware, the next layer can focus on reviewed promotion gates rather than adding more untracked outputs.
