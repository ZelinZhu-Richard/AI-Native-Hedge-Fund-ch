# Data Quality And Validation Gates

## Purpose

The Day 23 quality layer is a small admission-control system for real workflow boundaries.

It does not try to be a generic data-quality platform. It exists to stop structurally bad inputs from flowing quietly into downstream research, signals, proposals, and paper trades.

## Core Artifacts

Quality artifacts persist under `artifacts/data_quality/`:

- `validation_gates/`
- `data_quality_checks/`
- `data_quality_issues/`
- `contract_violations/`
- `input_completeness_reports/`

The main contracts are:

- `ValidationGate`
- `DataQualityCheck`
- `DataQualityIssue`
- `ContractViolation`
- `InputCompletenessReport`

## Decision Model

The quality layer uses four explicit decisions:

- `pass`
  - no material issues were found
- `warn`
  - non-blocking issues were found
- `refuse`
  - the workflow boundary is blocked before downstream use or emission
- `quarantine`
  - the artifact output is structurally invalid and is not admitted into the normal stage category

Severity is explicit on every issue and violation:

- `low`
- `medium`
- `high`
- `critical`

## Refusal Reasons

Current refusal reasons include:

- `missing_required_timestamp`
- `missing_provenance`
- `missing_entity_linkage`
- `invalid_review_state`
- `broken_signal_lineage`
- `incomplete_experiment_metadata`
- `missing_required_artifact`
- `structurally_invalid_output`

## What Gets Validated Today

Current boundary-specific gates:

- `ingestion_normalization`
  - validates normalized `SourceReference`, `Company`, and document outputs before normalized persistence
- `parsing_inputs`
  - validates explicit document and source-reference inputs before evidence extraction
- `evidence_bundle`
  - validates the final `DocumentEvidenceBundle` before parsing persistence
- `feature_mapping_inputs`
  - validates hypotheses, critiques, evidence assessments, and briefs before feature mapping
- `feature_output`
  - validates emitted features before persistence
- `signal_generation_output`
  - validates emitted signals and signal scores before persistence
- `portfolio_proposal`
  - validates loaded signals, generated position ideas, and the final proposal before proposal persistence
- `paper_trade_request`
  - validates both the pre-materialization request and the generated paper-trade candidates
- `experiment_metadata`
  - validates experiment config and dataset references before experiment creation

## Warning Vs Refusal Vs Quarantine

Current `warn` cases:

- missing or thin optional output where the workflow can still proceed honestly
- empty signal emission in non-applicable cases
- completeness gaps that are reviewable but not structurally corrupt

Current `refuse` cases:

- invalid review state on research artifacts entering feature mapping
- missing required linked artifacts for feature mapping, portfolio assembly, or paper-trade creation
- broken signal lineage at proposal time
- unapproved proposals or blocking proposal state at paper-trade creation
- incomplete experiment metadata

Current `quarantine` cases:

- normalized ingestion outputs with missing timing anchors
- structurally invalid parsing outputs
- broken or invalid emitted feature and signal outputs

Quarantine is bookkeeping plus admission control. It is not a file relocation system.

## Tracking And Visibility

A blocked boundary always writes a `ValidationGate` plus child artifacts.

The system does not hide these outcomes in logs only:

- touched workflow responses now expose:
  - `validation_gate`
  - `quality_decision`
  - `refusal_reason`
- monitoring notes include gate IDs, decisions, and refusal reasons on failure or stop states where that workflow already records summaries

## What This Layer Does Not Do

This layer does not:

- auto-repair invalid artifacts
- downgrade bad artifacts into silently coerced valid ones
- treat weak evidence or candidate status by themselves as data-quality failures
- replace schema validation
- replace the future reviewed-and-evaluated eligibility gate

Weak support, uncertainty, and exploratory status remain domain outcomes unless they cross a structural contract boundary.

## Operator Interpretation

Use the quality artifacts this way:

- `warn`
  - inspect, but the artifact may still be usable
- `refuse`
  - downstream transition was blocked cleanly; inspect the gate and violation rows
- `quarantine`
  - the produced artifact output is structurally invalid; treat the stage as unusable until fixed

The most important distinction is:

- structural corruption or missing linkage -> quality failure
- normal research disagreement, weak support, or candidate state -> not automatically a quality failure
