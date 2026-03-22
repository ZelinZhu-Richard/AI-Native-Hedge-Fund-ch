# Day 23 Plan: Data Quality Gates And Contract Enforcement

## Goal

Make the system reject structurally bad inputs cleanly and visibly instead of quietly degrading into nonsense.

## What Day 23 Added

- `DataQualityCheck`
- `DataQualityIssue`
- `ContractViolation`
- `ValidationGate`
- `RefusalReason`
- `InputCompletenessReport`
- `QualitySeverity`
- `QualityDecision`
- `DataQualityService`
- persisted quality artifacts under `artifacts/data_quality/`

## Implemented Gates

Current gate methods:

- `validate_ingestion_normalization`
- `validate_parsing_inputs`
- `validate_evidence_bundle`
- `validate_feature_mapping_inputs`
- `validate_feature_output`
- `validate_signal_generation`
- `validate_portfolio_proposal`
- `validate_paper_trade_request`
- `validate_experiment_metadata`

## Workflow Boundaries Hardened

Day 23 directly hardened:

- ingestion -> normalization
- normalization -> parsing inputs
- parsing output -> reusable evidence bundle
- research -> feature mapping
- feature mapping -> feature persistence
- signal generation -> signal persistence
- signal -> portfolio proposal
- portfolio proposal -> paper-trade candidate creation
- experiment creation metadata

## Current Design Choices

- small synchronous gate layer, not a generic quality platform
- explicit `pass | warn | refuse | quarantine` decisions
- refusal decisions are persisted, not buried in logs
- quarantine blocks normal stage persistence instead of silently coercing bad outputs
- weak support or candidate state alone are not treated as structural quality failures

## Current Limits

- not every repo workflow is gated yet
- quarantine is admission control, not a separate storage location
- this layer does not replace the future reviewed-and-evaluated eligibility gate
- some convenience latest-artifact development paths still exist outside strict snapshot-native selection

## Best Next Step After Day 23

Thread `ValidationGate` results into the real Week 4 downstream eligibility boundary, so promotion depends on both:

- structural contract quality
- explicit review and evaluation policy
