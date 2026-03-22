# Refusal And Quarantine Behavior

## Purpose

The Day 23 layer makes bad inputs fail visibly at workflow boundaries.

It introduces two different stop behaviors:

- `refuse`
- `quarantine`

They are related, but not interchangeable.

## Refuse

`refuse` means the workflow boundary is blocked before downstream use or promotion.

Typical Day 23 refusal examples:

- rejected or invalidated research artifacts entering feature mapping
- missing linked artifacts for feature mapping or proposal assembly
- broken signal lineage at proposal time
- unapproved proposals at paper-trade creation
- incomplete experiment metadata

Current refusal behavior:

- a `ValidationGate` is persisted
- child `DataQualityCheck`, `ContractViolation`, and optional `InputCompletenessReport` artifacts are persisted
- the caller receives either:
  - a typed `DataQualityRefusalError`, or
  - a structured zero-output response with `validation_gate`, `quality_decision`, and `refusal_reason`
- monitoring and run-summary notes include the gate ID and refusal metadata when that workflow already emits them

## Quarantine

`quarantine` means the produced artifact output is structurally invalid and is not admitted into the normal stage category.

Typical Day 23 quarantine examples:

- normalized ingestion outputs with no usable timing anchor
- evidence bundles that fail structural integrity
- broken emitted feature or signal outputs

Current quarantine behavior:

- quality artifacts are persisted under `artifacts/data_quality/`
- the invalid produced artifact is not persisted into the normal output category for that stage
- no automatic repair or fallback conversion is attempted

Quarantine is currently an admission-control result, not a separate storage namespace.

## Workflow-Specific Behavior

### Ingestion

- raw fixture payloads may still persist
- normalized artifacts do not persist when the normalized output gate blocks
- the run is recorded as failed with quality metadata

### Parsing

- explicit parsing inputs are validated before extraction
- invalid final evidence bundles do not persist into parsing output categories
- the run is recorded with the blocking gate

### Feature And Signal Generation

- invalid research inputs refuse feature mapping
- invalid emitted features or signals are blocked before persistence

### Portfolio Proposal

- invalid signals or broken lineage block proposal creation before normal persistence
- raw-signal fallback and arbitration-withheld no-input remain explicit notes, not quality failures by themselves

### Paper Trade Creation

- invalid or unapproved proposals return zero trades with a persisted refusal gate
- malformed generated trade candidates are also blocked before return
- this is a review-facing stop, not a silent empty output

### Experiment Creation

- incomplete dataset metadata is converted into a structured refusal instead of a plain untyped error

## Monitoring And Audit

When a touched workflow already emits monitoring, Day 23 now threads through:

- `validation_gate_id`
- `quality_decision`
- `refusal_reason`

This makes blocked transitions inspectable in:

- run summaries
- pipeline events
- downstream workflow notes

## Current Limits

- quarantine does not move files into a dedicated quarantine folder
- the quality layer is synchronous and local only
- not every repository workflow is gated yet
- structural quality gates still need to be combined with the future reviewed-and-evaluated eligibility gate
