# Scenario Stress Testing

## Purpose

Day 20 adds a first-pass, deterministic stress layer for `PortfolioProposal`.

The goal is not to fake institutional risk modeling.
The goal is to expose obvious proposal fragility in a structured way before approval.

## Current Stress Artifacts

The current layer persists:

- `ScenarioDefinition`
- `StressTestRun`
- `StressTestResult`
- embedded `ExposureShock` rows

Each `StressTestResult` records:

- the scenario definition used
- affected position IDs
- breached constraint IDs when applicable
- estimated PnL and return impact when the scenario is return-based
- explicit assumptions
- a non-empty structured summary

## Scenario Set In V1

The Day 20 scenario set is deliberately simple and code-owned:

1. `broad_market_drawdown`
   - applies `-10%` return shock to every position

2. `sector_specific_shock`
   - applies `-15%` return shock to the dominant resolved sector
   - if sector metadata is missing, the result says so explicitly instead of guessing

3. `volatility_increase`
   - reduces stressed allowable size to `50%` of `max_weight_bps`

4. `concentration_breach_stress`
   - retests the proposal against a stressed `250 bps` single-name limit

5. `confidence_degradation`
   - reduces confidence by `0.25`
   - increases uncertainty by `0.25`
   - warns when degraded confidence becomes weak, degraded uncertainty becomes high, or confidence metadata is missing

## Stress Math

Return-shock scenarios use only deterministic proposal sizing:

- position notional = `target_nav_usd * proposed_weight_bps / 10000`
- long shocked PnL = `notional * scenario_return`
- short shocked PnL = `-notional * scenario_return`
- portfolio shocked PnL = sum of position shocked PnL values

This is intentionally simple.
There is no factor model, correlation model, volatility surface, liquidity model, or VaR engine here.

## How Status Works

Stress results reuse existing `RiskCheckStatus` and `Severity`.

In v1:

- results are `PASS` or `WARN`
- the portfolio workflow surfaces fragility warnings into risk review
- stress findings do not create a new blocking approval gate by themselves

## What Remains Simplistic

The current stress engine does not model:

- cross-asset contagion
- sector correlations
- factor sensitivities
- realized or implied volatility behavior
- path dependence
- liquidity shocks
- execution slippage changes
- holdings-aware turnover

It is still useful because it makes fragile proposals visible in a structured, inspectable way.

## How Risk Review Should Use It

Reviewers should use these outputs to check:

- whether the proposal is too concentrated
- whether it remains reasonable under tighter sizing assumptions
- whether missing sector or confidence metadata is weakening review quality
- whether a superficially acceptable proposal is actually brittle

These results are advisory and review-facing.
They do not replace the explicit human approval boundary.
