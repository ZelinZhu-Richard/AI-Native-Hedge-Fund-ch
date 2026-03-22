# Week 4 Plan

## Summary

Week 4 should not widen scope casually. It should close the structural gaps that still make downstream trust too soft:

- candidate signals still reach portfolio construction without a true eligibility gate
- explicit artifact selection is still weaker than it should be upstream
- issuer identity still stands in for tradable identity
- evaluation and red-team outputs are still more diagnostic than policy-driving
- operator attention states still stop more by convention than by enforced workflow policy

## Priority 1: Reviewed-And-Evaluated Eligibility Gate

- add one explicit downstream eligibility contract between raw candidate signals and portfolio-consumable signals
- require both review state and evaluation state
- keep candidate signals queryable, backtestable, and reviewable, but non-promotable by default
- make portfolio construction reject ineligible signals structurally, not by note text

## Priority 2: Snapshot-Native Artifact Selection

- replace latest-artifact and cutoff-only loading with explicit selected snapshots or artifact references
- thread selected artifact IDs through research, feature, signal, arbitration, portfolio, and evaluation outputs
- add regression tests that prove older artifacts are not silently displaced by newer ones

## Priority 3: Instrument And Security Reference Layer

- introduce a first-class instrument or security contract
- separate issuer identity from tradable identity
- thread instrument identity through:
  - backtests
  - portfolio proposals
  - paper-trade candidates
  - attribution and stress outputs

## Priority 4: Evaluation And Red-Team Enforcement

- make proposal and paper-trade readiness consume evaluation findings explicitly
- extend red-team and evaluation outputs into the main review and eligibility boundary where appropriate
- keep the enforcement structural and honest; do not add fake scoring theater

## Priority 5: Operator Attention Handling

- improve blocked, stale, failed, and review-required workflow states
- make monitoring summaries and review queue state more policy-useful
- preserve human review gates while making stop reasons easier to inspect and act on

## Explicit Non-Goals

- no live trading
- no production scheduler or distributed infra build
- no optimizer binge
- no semantic retrieval overclaim
- no performance-marketing metrics

## Success Criteria

- portfolio construction can no longer consume candidate signals without an explicit eligibility artifact
- explicit selected artifact references are visible across the strongest downstream chain
- tradable identity is no longer approximated by `Company.ticker`
- evaluation and red-team findings materially influence downstream readiness
- operator stop states are clearer and more actionable

## Failure Signs

- eligibility remains note-driven instead of contract-driven
- snapshot selection remains partial and easy to bypass
- instrument identity remains implicit
- evaluation and red-team stay diagnostic-only
- Week 4 work broadens the system without tightening trust
