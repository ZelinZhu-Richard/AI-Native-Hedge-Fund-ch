# Feature And Signal Pipeline

## Purpose

Day 5 turns structured research artifacts into typed candidate features and then into typed candidate signals.

This layer exists to create measurable, reviewable downstream objects from evidence-backed research. It does not claim alpha, and it does not decide positions or portfolio weights.

## Input Boundary

The Day 5 feature mapper consumes:

- `Hypothesis`
- `CounterHypothesis`
- `EvidenceAssessment`
- `ResearchBrief`

It may also reload exact parsing artifacts from `artifacts/parsing/` when needed for deterministic feature construction:

- `GuidanceChange`
- `ExtractedRiskFactor`
- `ToneMarker`

This keeps the research layer upstream of features while still allowing the feature layer to use exact extracted context instead of memo prose.

## Current Selection Semantics

Week 1 hardening added optional `as_of_time` cutoffs to both feature mapping and signal generation workflows.

- feature mapping may filter research and parsing artifacts by `created_at <= as_of_time`
- signal generation may filter features by `FeatureValue.available_at <= as_of_time`

When `as_of_time` is omitted, latest-artifact loading is still allowed for local development. That path is explicitly noted in workflow outputs as not replay-safe.

## Day 5 Feature Artifacts

The feature layer now uses three typed objects:

- `FeatureDefinition`: stable meaning, family, value type, and ablation tags
- `FeatureValue`: point-in-time value and availability timestamp
- `Feature`: primary stored candidate feature artifact with embedded definition, value, lineage, assumptions, and provenance

Every Day 5 feature:

- is `FeatureStatus.PROVISIONAL`
- is `validation_status = unvalidated`
- carries exact lineage back to `Hypothesis`, `CounterHypothesis`, `EvidenceAssessment`, `ResearchBrief`, and supporting evidence-link IDs

## Initial Deterministic Feature Set

Day 5 materializes exactly six text-derived features:

1. `support_grade_score`
2. `support_document_count`
3. `guidance_change_score`
4. `risk_factor_count`
5. `tone_balance_score`
6. `counterargument_pressure_score`

These are deliberately narrow. They are intended to be testable and inspectable, not comprehensive.

Current limitations:

- only `FeatureFamily.TEXT_DERIVED` is instantiated
- there are no Day 5 price, fundamentals, or macro features yet
- `price_only`, `fundamentals_only`, and `combined` are still not Day 5 feature families
- Day 9 now adds downstream baseline comparisons through `StrategyVariantSignal`, not through new Day 5 feature families

## Candidate Signal Construction

Day 5 signal generation consumes candidate features and emits candidate signals.

Current rules:

- one candidate signal per company and ablation slice
- only `AblationView.TEXT_ONLY` produces a signal today
- non-text ablation requests return empty output with explicit notes
- `Signal.status = candidate`
- `Signal.validation_status = unvalidated`
- `Signal.stance` is research-layer (`positive`, `negative`, `monitor`), not a trade direction

The first-pass score is deterministic and intentionally simple. It combines:

- support grade
- support breadth
- guidance marker
- tone balance
- risk penalty
- critique pressure penalty

This score is an architecture placeholder, not a validated trading model.

## Day 19 Arbitration Layer

Day 19 adds a separate arbitration layer after raw signal generation.

That layer persists:

- `SignalCalibration`
- `SignalConflict`
- `ArbitrationDecision`
- `SignalBundle`

Current behavior:

- raw `Signal` artifacts remain the Day 5 output surface
- arbitration does not overwrite or replace those signals
- arbitration compares same-company candidate signals when more than one is present
- arbitration can withhold a primary selection instead of hiding a conflict

This keeps generation separate from comparison.

## Current Uncertainty And Conflict Visibility

Signal arbitration now makes these review-facing facts explicit:

- missing or present confidence payloads
- completeness of signal lineage
- freshness relative to `as_of_time`
- evidence-grade mismatches against strong-looking scores
- directional disagreement across signal families
- duplicated support overlap across otherwise separate signals

This uncertainty layer is structural and deterministic.
It is not statistical calibration and it does not imply correctness.

## Lineage Rules

Day 5 must preserve:

- upstream research artifact IDs
- supporting evidence-link IDs
- source reference IDs through provenance
- feature definition IDs
- feature value IDs
- feature family mix for future ablations

If lineage is incomplete, the feature or signal should fail validation or no-op rather than emit a vague artifact.

Day 19 extends that discipline by preserving arbitration linkage on downstream consumers through:

- `signal_bundle_id`
- `arbitration_decision_id`

## What Day 5 Does Not Support Yet

Day 5 still does not provide:

- validated signals
- promotion gates from review decisions
- price-only or fundamentals-only feature sets
- snapshot-native replay selection across the full chain

Day 9 now adds baseline strategy and ablation reporting downstream of this layer, but those comparisons remain exploratory and do not validate the Day 5 text-derived signals by default.

Day 19 now adds deterministic comparison and conflict visibility, but it still does not create a downstream-eligible signal class.

Backtesting, ablations, portfolio proposals, and paper-trade candidates now exist downstream, but they still consume candidate-only artifacts and remain explicitly review-bound until the Week 3 reviewed-and-evaluated gate exists.
