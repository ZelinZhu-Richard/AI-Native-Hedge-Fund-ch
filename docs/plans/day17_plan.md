# Day 17 Plan

## Goal

Strengthen point-in-time availability rules so the system can reason about when information became usable, not just when it was processed later.

## Delivered Scope

- added a dedicated timing schema layer
- added a reusable timing service with a simple US equities session model
- integrated timing metadata into ingestion, parsing, feature mapping, signal generation, and backtesting
- added structured timing anomalies
- tightened backtests so signals without explicit availability windows are excluded
- added timing tests for schemas, service logic, and end-to-end decision timing

## Deliberate Limits

- US equities only
- no full holiday engine
- no live latency model
- no exchange-grade calendar fidelity
- some upstream compatibility fallbacks still exist when explicit timing metadata is absent

## Immediate Follow-On

Push the same timing-aware rules into:

1. upstream research loading
2. reviewed-and-evaluated eligibility gates
3. snapshot-native replay boundaries
