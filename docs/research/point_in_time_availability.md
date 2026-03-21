# Point-In-Time Availability

## Purpose

Day 17 makes the repo explicit about when information became usable, not just when the system happened to ingest or process it later.

The timing layer now distinguishes:

- `event_time`
  - when something happened in the world
- `publication_time`
  - when the source made the information visible
- `internal_available_at`
  - when the platform should treat the information as usable
- `decision_time`
  - when a downstream workflow was allowed to act

This is the minimum structure needed for serious replay and backtesting hygiene.

## Current Timing Artifacts

The repo now uses:

- `PublicationTiming`
- `AvailabilityWindow`
- `MarketSession`
- `DataAvailabilityRule`
- `DecisionCutoff`
- `TimingAnomaly`

These artifacts make timing assumptions inspectable instead of hiding them inside field-name conventions.

## Rules Used Today

### Public Documents

Rule: `public_document_daily_equity`

- if a document is visible before the regular US equities open, it may influence that trading day's close decision
- if it is first visible during regular trading or after-hours, it is delayed until the next regular session
- if it is first visible on a closed market day, it is delayed until the next regular session

### Derived Features

Rule: `derived_feature_from_inputs`

- a feature is available at the maximum upstream document availability across its inputs
- if upstream timing metadata is missing or inconsistent relative to the existing derived artifact timestamp, the repo records a `TimingAnomaly` and uses an explicit compatibility fallback

### Derived Signals

Rule: `derived_signal_from_features`

- a signal is available at the maximum upstream feature availability across its contributing features
- the same compatibility-fallback behavior is explicit and anomaly-backed rather than silent

### Price Bars

Rule: `daily_price_bar_close`

- synthetic daily price bars become usable at the recorded bar close

## How Backtests Use Timing

The exploratory backtest path now:

- builds a `DecisionCutoff` for each decision bar
- evaluates candidate signals against resolved `AvailabilityWindow` objects
- excludes signals that do not carry an explicit availability window
- records `TimingAnomaly` artifacts when timing safety is weak or missing
- writes snapshot `information_cutoff_time` from resolved decision cutoffs

Current daily behavior is conservative:

- pre-market public documents can affect that day's close decision
- regular-session and after-hours public documents are delayed to the next trading day
- no signal is allowed into a decision before its resolved availability time

## Anomalies Recorded Today

The first timing layer records:

- missing publication timestamps
- invalid timezone names
- publication after claimed internal availability
- suspicious event/publication ordering
- retrieval or ingestion before publication
- decision time earlier than claimed availability
- impossible market-session assumptions
- missing upstream availability on derived artifacts
- upstream availability later than an already-materialized derived artifact

Warnings are allowed upstream. Decision and backtest paths are stricter.

## What Remains Simplistic

This is still a conservative first pass:

- only a coarse US equities session model exists
- there is no full holiday engine
- there is no live latency model
- there is no replay of corrections or restatements
- some upstream workflows still rely on explicit compatibility fallbacks when timing metadata is absent

## What This Does Not Prove

This layer improves point-in-time discipline. It does not prove:

- alpha
- execution realism
- exchange-grade timing fidelity
- replay completeness across every workflow boundary
