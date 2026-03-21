# Market Calendar And Timing

## Scope

Day 17 adds a simple market-timing model for `US Equities` only.

It is designed for deterministic research replay and conservative backtest eligibility. It is not an exchange-grade schedule engine.

## Current Session Model

Timezone:

- `America/New_York`

Default weekday sessions:

- `pre_market`: `04:00` to `09:30`
- `regular`: `09:30` to `16:00`
- `after_hours`: `16:00` to `20:00`
- `closed`: outside those windows and on weekends

Weekdays are assumed open unless an explicit manual override is supplied.

## Supported Overrides

`MarketCalendarEvent` currently supports:

- `holiday`
- `early_close`
- `late_open`
- `session_override`

These are explicit local overrides. The repo does not currently persist or distribute a full calendar dataset.

## Decision-Cutoff Semantics

Backtesting now builds one `DecisionCutoff` per daily decision bar.

For the current exploratory simulator:

- `decision_time` is the price-bar close
- `eligible_information_time` is the same timestamp
- the cutoff records the session kind and timing rule used for that decision

This makes snapshot timing more defensible:

- `DataSnapshot.information_cutoff_time` now comes from resolved decision cutoffs
- `BacktestRun.decision_cutoff_time` now reflects the actual decision schedule

## Publication-Time Rule

The current public-document rule is intentionally conservative:

- before the regular open: same-day close eligibility
- during regular trading: next-session eligibility
- during after-hours: next-session eligibility
- on closed-market days: next-session eligibility

This avoids the common shortcut of treating all same-date documents as usable on the same trading day.

## Timezone Handling

At rest, timestamps remain UTC.

The timing layer still preserves timezone assumptions explicitly:

- `source_timezone`
- `normalized_timezone`
- `MarketSession.timezone`
- `DecisionCutoff.timezone`

Invalid timezone names are recorded as `TimingAnomaly`, not silently normalized away.

## Known Limits

Current limits are explicit:

- no holiday catalog
- no half-day library beyond manual overrides
- no halt or auction handling
- no market scopes beyond US equities
- no distinction yet between source publication and downstream human-review eligibility

The next structural improvement should push the same timing rules deeper into research loading and downstream eligibility gates.
