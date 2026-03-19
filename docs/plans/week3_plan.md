# Week 3 Plan

## Summary

Week 3 should stop treating candidate artifacts as if careful wording alone is enough. The priority is to make reviewed and evaluated state matter operationally, then strengthen replay discipline and instrument identity around that gate.

## Priorities

### 1. Reviewed-And-Evaluated Signal Eligibility Gate

- add an explicit eligibility artifact or status that separates candidate signals from downstream-eligible signals
- require both review and evaluation state before a signal can feed portfolio construction
- keep candidate signals queryable and backtestable, but make them non-promotable by default

### 2. Snapshot-Native Selection

- replace cutoff-only loading with explicit selected snapshot or artifact references across research, feature, signal, and portfolio workflows
- ensure experiment and evaluation records point to the exact slices actually used
- add harder replay tests across multi-generation artifact sets

### 3. Instrument And Reference Data Layer

- add a first-class instrument or security contract instead of relying on `Company.ticker`
- separate company identity from tradable instrument identity
- thread that identity through backtests, proposals, and paper trades

### 4. Broader Evaluation Enforcement

- extend evaluation coverage beyond ablation into proposal readiness, review completeness, and paper-trade eligibility
- make failure cases and robustness findings usable as downstream blockers, not only diagnostics
- keep evaluation structural and honest; do not add performance theater

### 5. Monitoring And Operator Attention Handling

- add clearer attention states for blocked, stale, or failed workflows
- improve service-status usefulness for operators
- keep the monitoring layer summary-oriented, but make it more actionable

## Defaults

- Week 3 should preserve the current local deterministic architecture rather than introducing new infrastructure prematurely.
- Paper trading remains paper-only and human-gated.
- No live execution, alpha claims, or performance-marketing work should enter the plan.
