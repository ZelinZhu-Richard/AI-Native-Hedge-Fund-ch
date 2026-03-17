# Week 1 Review Plan

## Purpose

Review the Day 1 through Day 7 foundation as a single system before building richer evaluation, promotion gates, and portfolio depth.

## Review Scope

### 1. Schema Consistency

- verify that Days 1 to 7 use one coherent contract vocabulary
- check that review status and validation status remain distinct where required
- confirm that candidate vs approved vs validated artifacts remain unambiguous

### 2. Lineage Completeness

Trace one fixture path end to end:

- source fixture
- normalized document
- exact evidence span
- supporting evidence link
- hypothesis
- evidence assessment
- signal
- backtest run
- position idea
- portfolio proposal
- paper trade candidate

Questions:

- Are IDs preserved cleanly at each handoff?
- Are provenance records complete enough to replay decisions later?
- Are any downstream objects relying on prose instead of typed lineage?

### 3. Temporal Correctness

- confirm that signal, feature, and backtest availability rules are still explicit
- check whether the new downstream proposal layer accidentally assumes information earlier than allowed
- review whether proposal generation is clearly downstream of the current exploratory backtest layer rather than coupled into it

### 4. Candidate Signal Separation

- verify that candidate signals remain visibly provisional in portfolio proposals
- confirm that Day 7 does not blur candidate signals into approved trading instructions
- confirm that the portfolio and paper-trade layers still stop at reviewable artifacts

### 5. Risk And Review Gates

- verify that blocking `RiskCheck` objects cannot be silently bypassed
- confirm that approval cannot be applied to blocking proposals
- review whether trade-level approval remains distinct from proposal-level approval

### 6. Remaining Stubs

Primary gaps to examine before Week 2:

- explicit reviewed-signal promotion gate
- richer temporal ablation and evaluation artifacts
- multi-name portfolio inputs
- sector and liquidity constraints
- trade-level review workflow
- durable audit ledger and operator UI

## Recommended Output Of The Review

- one short architecture note on what should stay unchanged
- one list of schema or lifecycle inconsistencies to tighten
- one prioritized build sequence for Week 2
