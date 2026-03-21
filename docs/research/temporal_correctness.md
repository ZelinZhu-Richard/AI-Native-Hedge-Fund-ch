# Temporal Correctness

## Purpose

Financial research systems fail quietly when they leak future information.

Day 6 makes the backtesting boundary explicit so future evaluation work can stay honest.

## Timestamp Roles

The repository now distinguishes:

- `published_at`
  - when a source became public
- `publication_time`
  - normalized source visibility time used by the timing layer
- `internal_available_at`
  - normalized platform-usable time derived from a timing rule
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

## Upstream Workflow Cutoffs

Week 1 hardening added explicit `as_of_time` cutoffs to the upstream local workflows that sit before backtesting:

- feature mapping may now filter research and parsing artifacts by `created_at <= as_of_time`
- signal generation may now filter features by `FeatureValue.available_at <= as_of_time`
- portfolio proposal workflows may now filter signals by `effective_at <= as_of_time` and `created_at <= as_of_time`

When `as_of_time` is omitted, the current repo still allows latest-artifact loading for local development convenience. That behavior is intentionally called out in workflow notes as not replay-safe.

## Day 9 Ablation Rules

Day 9 extends honest temporal handling into the baseline comparison layer.

The ablation harness now enforces these additional rules:

1. `text_only_candidate_baseline` reuses only research signals already available by the current bar.
2. `price_only_baseline` uses only trailing closes through the current bar close.
3. `combined_baseline` uses:
   - the latest eligible text-only signal with `effective_at <= current_bar_time`
   - the current price-only momentum signal computed from historical closes only
4. Child backtests still revalidate future feature availability whenever a comparable signal resolves back to research-signal lineage.
5. Shared input snapshots are persisted for the ablation slice so variant signals can point to explicit source snapshot IDs.

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

## Day 17 Timing Layer

Day 17 adds a first-class timing layer instead of relying only on ad hoc timestamp comparisons.

The repo now carries:

- `PublicationTiming`
- `AvailabilityWindow`
- `MarketSession`
- `DataAvailabilityRule`
- `DecisionCutoff`
- `TimingAnomaly`

Current timing policy for public documents is intentionally conservative:

1. documents available before regular market open may influence that trading day's close decision
2. documents first available during regular trading or after-hours are delayed until the next regular session
3. price bars become usable at the recorded bar close
4. signals without resolved availability windows are excluded from backtest eligibility

Derived feature and signal availability is now tied to upstream availability windows where available. When upstream timing metadata is incomplete, the workflow records a `TimingAnomaly` instead of hiding the fallback.

## Known Remaining Risks

Day 6 is honest, but still simple.

Current risks still to improve:

- no stale-signal expiry policy yet
- no corporate-action handling
- no split-adjustment logic
- no intraday timestamp granularity
- no full holiday calendar engine
- some upstream workflows still depend on compatibility fallbacks when explicit timing metadata is absent
- no replay of late corrections or vendor restatements
- synthetic prices only, not real point-in-time market data

## Next Structural Priority

The next step is explicit artifact and snapshot selection across the full chain, not more downstream sophistication.

Week 2 should tighten:

- snapshot-aware artifact selection before and after backtesting
- promotion gates from exploratory candidate signals into reviewed validation work
- adversarial replay checks over multi-generation artifact sets
