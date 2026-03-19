# Day 12 Plan: Downstream Review And Promotion Enforcement

## Summary

Build the first real gate that makes reviewed and evaluated state matter operationally.

The repo now has:

- research review artifacts
- signal artifacts
- evaluation reports
- portfolio proposals
- paper-trade candidates
- operator review queue and actions

What it still lacks is enforcement. Day 12 should stop downstream workflows from relying on convention and instead require explicit reviewed-and-eligible state where the repo says it matters.

## Goals

- define explicit downstream eligibility rules
- gate signal use in portfolio proposal workflows
- gate proposal and paper-trade progression on review state
- connect evaluation and review outputs to those gates
- preserve temporal and audit discipline

## Planned Focus

### 1. Reviewed Signal Eligibility

- define a typed eligibility object or status projection for signals
- require approved or explicitly review-eligible signals for stricter downstream flows
- keep exploratory candidate signals visible, but do not let them silently pass through stricter paths

### 2. Evaluation-Aware Promotion Boundary

- connect Day 10 `EvaluationReport` outputs to explicit promotion decisions
- make major failures and blocking robustness checks matter
- do not equate a decent backtest row with promotion

### 3. Portfolio And Paper-Trade Gates

- prevent portfolio proposal workflows from using ineligible signals when strict mode is requested
- prevent paper-trade approval from bypassing blocked proposal state
- make gate failures explicit and inspectable

### 4. Snapshot-Native Selection

- start replacing cutoff-only loading with explicit selected artifact or snapshot references
- make the selected input slice visible in promotion and downstream artifacts

### 5. Adversarial Tests

- add tests that attempt to bypass review or evaluation gates
- add stale-artifact and future-artifact exclusion tests
- confirm no silent approval path exists

## Non-Goals

- live trading
- broker integrations
- portfolio optimization
- statistical significance claims

## Exact Target

At the end of Day 12, the repo should be able to say:

- which signal was eligible
- why it was eligible
- which review and evaluation artifacts justified that
- why a downstream workflow was allowed or blocked
