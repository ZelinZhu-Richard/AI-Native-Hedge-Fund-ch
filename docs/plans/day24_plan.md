# Day 24 Plan

## Goal

Reduce the realism gap between the backtesting layer and the paper-trading workflow without pretending the repo now has execution-grade simulation.

## Implemented Scope

- explicit backtest-side timing, fill, and cost artifacts
- explicit paper-side timing, fill, and cost artifacts
- structured realism warnings
- structured backtest-to-paper reconciliation
- experiment-context attachment for reconciliation artifacts
- operator-review visibility for reconciliation artifacts
- monitoring summaries that surface high-severity mismatches

## Current Defaults

- reconciliation is advisory
- paper trading still requires explicit human approval
- no paper fill simulation is fabricated
- backtests still use synthetic prices and fixed-bps costs
- ambiguous backtest/proposal auto-matching is rejected

## Highest-Value Follow-On

Feed reconciliation results into the Week 4 reviewed-and-evaluated eligibility gate so proposals and paper-trade candidates cannot advance while high-severity backtest-to-paper mismatches remain unresolved.
