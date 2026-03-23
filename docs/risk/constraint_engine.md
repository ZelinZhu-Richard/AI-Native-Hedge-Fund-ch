# Constraint Engine

## Purpose

The Day 25 constraint engine is a small deterministic admission-control layer inside portfolio construction.

It is not an optimizer.
It is not a generic policy platform.
It is a visible rule engine that decides whether a candidate can be included and whether its final size was capped.

## Constraints Applied Today

Current active construction constraints are still simple:

- single-name hard limit
- gross exposure hard limit
- net exposure hard limit
- flat-start turnover hard limit

When callers do not provide explicit constraints, the default portfolio workflow uses:

- single-name: `500 bps`
- gross: `1500 bps`
- net: `1000 bps`
- turnover: `1500 bps`

## How Constraint Application Works

Construction now records one `ConstraintSet` plus explicit `ConstraintResult` rows.

Constraint behavior today:

- `single_name`
  - can cap an included candidate downward
  - produces a binding `ConstraintResult` and `PositionSizingRationale` when it changes the final size
- `gross_exposure`
  - evaluated on projected proposal state
  - rejects a candidate when projected gross would breach the hard limit
- `net_exposure`
  - evaluated on projected absolute net exposure
  - rejects a candidate when projected net would breach the hard limit
- `turnover`
  - still uses the flat-start turnover assumption
  - rejects a candidate when projected turnover would breach the hard limit

The engine does not rebalance existing ideas to squeeze a candidate in.
It evaluates candidates in deterministic rank order and either includes or rejects them.

## Binding Versus Blocking

`ConstraintResult.binding = true` means the constraint materially shaped the construction outcome.

That can mean:

- the candidate was capped but still included
- the candidate hit a limit exactly
- the candidate was rejected because inclusion would have breached a hard limit

`ConstraintResult.status` remains explicit:

- `pass`
- `warn`
- `fail`

## Downstream Use

Construction constraint artifacts now flow into:

- risk review
- portfolio attribution
- operator review context
- paper-trade traceability

Risk review now warns when:

- construction context is missing
- one or more construction constraints were already binding

## What Remains Simplified

- no soft-limit scoring or optimizer objective
- no sector, beta, liquidity, or ADV constraint layer yet
- turnover still assumes flat-start holdings
- no dynamic resizing across multiple included names
- no explicit instrument-level concentration model beyond the current company/symbol path
