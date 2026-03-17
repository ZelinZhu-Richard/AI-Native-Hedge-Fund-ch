# Temporal Correctness

## Purpose

Financial research systems fail quietly when they leak future information.

Day 6 makes the backtesting boundary explicit so future evaluation work can stay honest.

## Timestamp Roles

The repository now distinguishes:

- `published_at`
  - when a source became public
- `retrieved_at`
  - when the platform pulled the source
- `effective_at`
  - when a derived research artifact or signal is eligible for downstream use
- `available_at`
  - when a feature value may be used by a downstream workflow
- `snapshot_time`
  - when a dataset snapshot was materialized for access
- `watermark_time`
  - latest event time safely included in the snapshot
- `information_cutoff_time`
  - latest time the consumer is allowed to assume is available
- `decision_time`
  - time when the backtest strategy is allowed to decide
- `event_time`
  - time when a simulated fill, mark, or benchmark mark is recorded

## Day 6 Backtest Rules

The Day 6 backtesting engine enforces these rules in code:

1. A signal may only be considered when `effective_at <= decision_time`.
2. If a signal-availability buffer is configured, the effective boundary becomes:
   `effective_at + buffer <= decision_time`
3. Every feature referenced by the candidate signal must satisfy:
   `FeatureValue.available_at <= decision_time`
4. Signals not in `BacktestConfig.signal_status_allowlist` are ignored.
5. Execution happens at next-bar open, never same-bar.
6. Price and signal snapshots must carry `information_cutoff_time`.

If a rule fails, the signal is rejected for that decision point and the run records the relevant leakage or integrity check.

## What Day 6 Explicitly Avoids

The Day 6 engine does not:

- use raw `published_at` directly as a backtest decision boundary
- use raw source event timestamps directly in the simulator
- pull forward features whose `available_at` is in the future
- execute on the same bar as the decision
- silently fill missing lineage with assumptions

## Snapshot Semantics

`DataSnapshot.snapshot_time` is not the decision boundary.

It answers:

- when was this snapshot materialized?

`DataSnapshot.information_cutoff_time` answers:

- what is the latest time downstream logic is allowed to assume is in the snapshot?

This separation matters because a file can be written later than the latest information it legitimately contains.

## Leakage Checks Recorded Today

Day 6 records checks for:

- missing snapshot cutoffs
- requested price window outside available bars
- missing signal lineage
- missing referenced features
- future feature availability relative to decision time

These checks are attached to `BacktestRun.leakage_checks`.

## Known Remaining Risks

Day 6 is honest, but still simple.

Current risks still to improve:

- no stale-signal expiry policy yet
- no corporate-action handling
- no split-adjustment logic
- no intraday timestamp granularity
- no replay of late corrections or vendor restatements
- synthetic prices only, not real point-in-time market data

## Day 7 Direction

The next step is not portfolio logic.

The next step is richer signal-evaluation infrastructure:

- ablation-aware replay
- snapshot-aware validation artifacts
- promotion gates from exploratory candidate signals into reviewed validation work
