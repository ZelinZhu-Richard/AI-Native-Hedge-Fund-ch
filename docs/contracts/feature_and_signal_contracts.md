# Feature And Signal Contracts

## Purpose

This document defines the Day 5 contract for candidate features and candidate signals.

The goal is to make downstream artifacts measurable, typed, point-in-time aware, and traceable back to structured research and exact evidence links.

## Canonical IDs

Day 5 introduces:

- `fdef_...` for `FeatureDefinition`
- `fval_...` for `FeatureValue`
- `feat_...` for `Feature`
- `flin_...` for `FeatureLineage`
- `sscore_...` for `SignalScore`
- `sig_...` for `Signal`
- `slin_...` for `SignalLineage`

These IDs are immutable once assigned.

## Core Objects

### `FeatureDefinition`

Defines the stable meaning of a candidate feature.

Required fields:

- stable `name`
- `family`
- `value_type`
- `description`
- `ablation_views`
- `status`
- `validation_status`
- provenance

### `FeatureValue`

Defines the point-in-time realized value of a feature.

Required fields:

- `feature_definition_id`
- `as_of_date`
- `available_at`
- exactly one of `numeric_value`, `text_value`, or `boolean_value`
- provenance

### `Feature`

This is the primary stored Day 5 feature artifact.

Required fields:

- `feature_definition`
- `feature_value`
- `entity_id`
- optional `company_id`
- `status`
- `validation_status`
- `lineage`
- `assumptions`
- provenance

### `SignalScore`

Defines one component of a candidate signal score.

Required fields:

- `metric_name`
- `value`
- `validation_status`
- `source_feature_ids`
- `assumptions`
- provenance

### `Signal`

Defines the candidate signal artifact.

Required fields:

- `signal_family`
- `stance`
- `ablation_view`
- `feature_ids`
- `component_scores`
- `primary_score`
- `effective_at`
- `status`
- `validation_status`
- `lineage`
- `assumptions`
- `uncertainties`
- provenance

## Timestamp Semantics

Day 5 uses:

- `FeatureValue.as_of_date`: business date the value describes
- `FeatureValue.available_at`: first time the feature may be used downstream
- `Signal.effective_at`: first time the signal may be considered active
- `created_at` / `updated_at`: record lifecycle metadata

All timestamps must be timezone-aware UTC at rest, except `as_of_date`, which is a logical date.

## Validation Semantics

Day 5 feature and signal artifacts use `DerivedArtifactValidationStatus`:

- `unvalidated`
- `pending_validation`
- `partially_validated`
- `validated`
- `invalidated`

Current Day 5 behavior:

- all emitted features are `unvalidated`
- all emitted signals are `unvalidated`
- candidate generation is allowed before the formal review gate exists
- no Day 5 artifact is promotable by default

## Candidate-Only Signal Semantics

Day 5 signals are:

- candidate-only
- non-portfolio-facing
- not backtest-validated
- not approved for live or paper execution

`Signal.stance` is a research-layer view classification. It is not a position instruction.

## Ablation Views

Supported ablation enums:

- `price_only`
- `fundamentals_only`
- `text_only`
- `combined`

Current Day 5 behavior:

- only `text_only` emits real artifacts
- the other views are intentionally empty because their feature families are not built yet

## Lineage Requirements

Every feature must carry:

- upstream research artifact IDs
- supporting evidence-link IDs
- source document IDs

Every signal must carry:

- feature IDs
- feature definition IDs
- feature value IDs
- upstream research artifact IDs
- supporting evidence-link IDs
- input feature families

If lineage is incomplete, the contract should fail rather than silently emit an ambiguous artifact.
