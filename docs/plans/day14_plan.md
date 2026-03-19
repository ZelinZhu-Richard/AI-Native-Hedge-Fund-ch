# Day 14 Plan: Eligibility Gates And Red-Team-Aware Enforcement

## Summary

Build the first hard downstream eligibility gate that uses reviewed state, evaluation state, and red-team-sensitive rules together.

The repo now has:

- review workflows
- evaluation artifacts
- monitoring summaries
- red-team cases and guardrail violations

What it still lacks is enforcement that makes these signals matter when downstream workflows decide whether an artifact may progress.

## Planned Focus

### 1. Signal Eligibility Gate

- define a typed eligible-signal view
- require approved or explicitly review-eligible signals for stricter downstream portfolio use
- surface the exact review and evaluation artifacts behind eligibility

### 2. Evaluation And Guardrail Sensitivity

- make blocking evaluation failures matter
- make known red-team-exposed weaknesses visible in downstream gate decisions
- avoid equating a clean backtest row with promotion

### 3. Proposal And Paper-Trade Enforcement

- prevent proposal workflows from using ineligible signals in strict mode
- prevent paper-trade approval when parent proposal or review state is incomplete
- make gate failures explicit artifacts rather than silent skips

### 4. Stale And Failed Attention Queues

- turn failed or attention-required monitoring states into operator-facing attention targets
- make stale or broken workflow slices easier to inspect before downstream use

### 5. Adversarial Gate Tests

- add cases that try to bypass review, evaluation, or red-team-sensitive gates
- add stale-slice and future-slice tests around the stricter downstream boundary

## Non-Goals

- live trading
- portfolio optimization
- statistical significance claims
- broad UI work

## Exact Target

At the end of Day 14, the repo should be able to say:

- which artifact was eligible
- why it was eligible
- which review, evaluation, and guardrail-sensitive states justified that
- why a downstream workflow was allowed or blocked
