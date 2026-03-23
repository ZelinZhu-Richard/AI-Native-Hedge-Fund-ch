# Backtest Realism V2

## Scope

Day 24 improves realism in a narrow, explicit way.

It does not add a market microstructure engine. It does not make the synthetic backtest market-realistic. It does make the current assumptions more explicit and less misleading.

## What Improved

The backtest layer now records explicit read models for:

- execution timing
- fill basis
- transaction-cost and slippage assumptions
- realism warnings

The most important mechanical change is that fill events no longer reuse the next bar's close timestamp. Day 24 records fills at the next session open timestamp while still using the same simple next-bar-open execution model.

## Backtest Side Today

The current backtest path remains:

- daily close decisioning
- next-session open execution
- fixed-basis-point transaction costs and slippage
- unit-position sizing
- synthetic daily price fixtures

That is still exploratory. It is now more explicit and internally coherent.

## Paper Side Today

The paper workflow now records its own assumptions explicitly:

- proposal `as_of_time` is the research decision anchor
- paper-trade `submitted_at` is the candidate-generation anchor
- human approval is required before execution
- no automatic fill time is fabricated
- quantity is only materialized when a caller provides a reference price
- slippage is estimate-only

## Why This Matters

Without this explicit modeling, the repo would encourage a common failure mode:

- a backtest appears more executable than it really is
- a paper workflow appears more comparable to the backtest than it really is
- reviewers get false comfort from similarity that was never encoded

Day 24 reduces that gap by preserving the assumptions instead of hiding them.

## Known Simplifications

- synthetic prices remain synthetic
- costs remain fixed basis points
- no partial fills
- no queue position
- no market impact
- no holdings engine
- approval delay is only recorded as a warning, not simulated in the backtest path

## Safe Interpretation

Use the Day 24 outputs as realism metadata and internal-consistency diagnostics.

Do not interpret them as proof that the backtest and paper-trading layers are execution-equivalent.
