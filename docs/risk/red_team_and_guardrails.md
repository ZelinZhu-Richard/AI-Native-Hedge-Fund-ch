# Red-Team And Guardrails

## Purpose

Day 13 adds the first explicit red-team layer.

This is not a generic safety platform.
It is a deterministic adversarial test harness that clones persisted artifacts, injects known bad states, and records which guardrails fail.

The goal is to make weak behavior visible and inspectable before the system grows more capable or more trusted.

## Primary Artifacts

The red-team layer persists under `artifacts/red_team/`:

- `cases/`
- `guardrail_violations/`
- `safety_findings/`

The key contracts are:

- `RedTeamCase`
- `AdversarialInput`
- `GuardrailViolation`
- `SafetyFinding`
- `RecommendedMitigation`

`Severity` is reused directly as the red-team failure-severity scale so risk, evaluation, monitoring, and red-team findings remain comparable.

## Current Guardrails

The first pass implements these explicit guardrails:

- `required_provenance_present`
- `required_evidence_present`
- `claim_strength_matches_support`
- `review_bypass_detected`
- `paper_trade_approval_state_complete`
- `evaluation_references_complete`
- `non_empty_extraction_required_for_downstream`
- `timestamp_ordering_valid`

These checks are narrow and deterministic.
They are meant to fail for concrete reasons, not to perform general-purpose “AI safety” judgment.

## Current Adversarial Scenarios

The Day 13 suite covers:

- missing provenance on downstream artifacts
- contradictory evidence ignored by stronger thesis wording
- corrupted timestamp windows
- incomplete review state on proposals
- unsupported causal or recommendation language
- malformed portfolio proposal payloads
- weak or missing signal lineage
- empty extraction artifacts that still appear downstream
- paper-trade approval-state gaps
- experiment records missing config or dataset references

Each scenario runs against cloned in-memory artifacts only.
The persisted upstream research, signal, portfolio, review, and experiment artifacts are not rewritten by the suite.

## Monitoring And Audit

The red-team suite is integrated with existing monitoring and audit layers.

Each suite run now records:

- one monitoring `RunSummary`
- pipeline events for suite start and completion
- monitoring alerts when failed or attention-required outcomes exist
- one audit log for suite completion

Blocking or critical violations surface operationally through the same monitoring layer used elsewhere in the repo.

## What This Layer Does Not Do

Day 13 does not:

- prove production correctness
- replace evaluation, review, or promotion gates
- block normal runtime workflows automatically
- claim full coverage of failure modes

The current enforcement path is:

- structured red-team artifacts
- failing tests
- monitoring alerts
- audit visibility

## Main Remaining Exposures

- downstream services still do not universally hard-block on red-team findings
- recommendation-language checks are intentionally narrow and phrase-based
- adversarial temporal coverage is still smaller than the future multi-slice replay target
- portfolio, review, and experiment guardrails remain local-filesystem-backed and dev-oriented

## Expected Next Step

The next serious extension is to make reviewed, evaluated, and red-team-sensitive eligibility matter operationally in stricter downstream workflows.
