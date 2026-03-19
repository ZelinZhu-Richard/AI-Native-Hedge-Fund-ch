# Day 11 Plan

## Goal

Build the reviewed signal-evaluation and promotion gate on top of the new Day 10 evaluation layer.

## Why This Is Next

The repo can now produce:

- research artifacts
- candidate features and signals
- exploratory backtests
- ablation comparisons
- experiment records
- structured evaluation reports with failures and robustness checks

What it still cannot do well is decide, in a stored and reviewable way:

- which evaluated signals remain exploratory
- which slices have actually been reviewed by a human
- which downstream workflows should be allowed to consume a signal

## Priorities

### 1. Reviewed Evaluation Decisions

- add typed review artifacts for evaluated signals and strategy variants
- record outcome, reviewer, notes, blocking issues, and decision time

### 2. Promotion Gate

- define the first promotion path from:
  - candidate signal
  - exploratory backtest and ablation evidence
  - evaluation report
  - reviewed decision
  - downstream eligibility

### 3. Snapshot-Native Selection

- move evaluation inputs from cutoff-aware loading toward explicit selected snapshot identities
- preserve those selections in the review and promotion records

### 4. Downstream Enforcement

- make portfolio proposal and paper-trade flows reject signals that have not crossed the required gate

### 5. Adversarial Replay And Review Tests

- add tests for stale evaluation usage
- add tests for wrong snapshot selection
- add tests for downstream consumption without review approval

## Non-Goals

- live trading
- portfolio optimization
- statistical significance tooling
- richer factor engineering

## Exact Target

At the end of Day 11, the system should be able to say:

- which signal or variant was evaluated
- on which exact slice
- what failed or passed structurally
- who reviewed the result
- whether the artifact is still exploratory or is eligible for stricter downstream use
