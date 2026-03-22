# Signal Calibration And Arbitration

## Purpose

Day 19 adds a dedicated arbitration layer between raw `Signal` artifacts and downstream portfolio consumers.

This layer exists to make multiple same-company signals:

- comparable
- uncertainty-aware
- conflict-preserving
- inspectable in review, risk, and experiment records

It does not claim statistical calibration.
It does not synthesize a new canonical signal.
It does not replace the Week 3 reviewed-and-evaluated eligibility gate.

## Stored Artifacts

Signal arbitration persists local artifacts under `artifacts/signal_arbitration/`:

- `signal_calibrations/`
- `signal_conflicts/`
- `arbitration_decisions/`
- `signal_bundles/`

The core contracts are:

- `UncertaintyEstimate`
- `SignalCalibration`
- `ArbitrationRule`
- `SignalConflict`
- `RankingExplanation`
- `ArbitrationDecision`
- `SignalBundle`

## What Calibration Means Here

Calibration is deterministic normalization plus explicit context.

Current behavior:

- `normalized_score = clamp(primary_score, -1.0, 1.0)`
- `absolute_strength = abs(normalized_score)`
- `uncertainty_score` comes from `Signal.confidence.uncertainty` when present
- if signal confidence is missing, uncertainty falls back to `1.0` and that fallback is recorded explicitly
- freshness is derived from `effective_at` relative to `as_of_time`
- lineage completeness is evaluated structurally from the signal's feature and evidence lineage

This is not probability calibration.
This is not predicted error estimation.
This is a disciplined way to compare structurally different candidate signals without hiding uncertainty.

## Arbitration Inputs

The Day 19 arbitration service loads:

- same-company `Signal` artifacts
- linked `EvidenceAssessment` rows when available
- linked `ResearchBrief` context when available

Signals with these states are excluded before arbitration:

- `rejected`
- `expired`
- `invalidated`

All remaining signals stay visible inside the resulting `SignalBundle`, even when they are later suppressed during ranking.

## Current Conflict Types

The first pass records these explicit conflict families:

- `directional_disagreement`
- `score_support_mismatch`
- `freshness_mismatch`
- `duplicate_support_overlap`
- `maturity_mismatch`

### Directional disagreement

Recorded when same-company signals carry opposing non-monitor stances.

It becomes blocking when:

- both signals have `EvidenceAssessment.grade` in `{strong, moderate}`
- neither signal is rejected, expired, or invalidated

When the top opposing signals are in blocking disagreement, arbitration withholds primary selection entirely.

### Score-support mismatch

Recorded when score magnitude is high enough to look strong while the evidence grade is still weak:

- `abs(normalized_score) >= 0.50`
- evidence grade is `weak` or `insufficient`

### Freshness mismatch

Recorded when otherwise comparable signals differ materially in freshness state and timing context should remain visible.

### Duplicate support overlap

Recorded when different signals reuse the same supporting evidence-link identifiers.

When the stance also agrees and the duplicate is lower ranked, the lower-ranked duplicate is suppressed rather than treated as an independent primary input.

### Maturity mismatch

Recorded when comparable signals differ in review readiness, such as:

- validated vs unvalidated
- approved vs candidate

## Ranking Rules

Ranking is deterministic and inspectable.

Signals are ranked lexicographically by:

1. validation status
2. signal status
3. evidence grade
4. lower uncertainty
5. fresher timing state
6. higher absolute strength
7. newer `effective_at`
8. `signal_id`

The service also records `RankingExplanation` rows so reviewers can see:

- which rules were applied
- why one signal ranked above another
- why a signal was suppressed or not selected

There are no hidden weights and no undocumented tie-breaks.

## Arbitration Outcomes

The arbitration workflow persists:

- one `SignalCalibration` per surviving candidate signal
- zero or more `SignalConflict` rows
- one `ArbitrationDecision`
- one `SignalBundle`

Important behaviors:

- arbitration never creates a new synthesized `Signal`
- calibrated does not mean validated
- if blocking directional disagreement exists at the top of the ranking, `selected_primary_signal_id` is left empty
- a bundle with no selected primary signal is a real output, not an error disguised as success

## Downstream Consumption

Portfolio workflows now prefer arbitration outputs when available.

Current behavior:

- if a bundle exists and a primary signal is selected, portfolio construction uses only that selected signal
- if a bundle exists but no primary signal is selected, portfolio construction produces no `PositionIdea`
- if no bundle exists, portfolio construction falls back to raw signals and emits an explicit note

`PositionIdea` and `PortfolioProposal` now preserve:

- `signal_bundle_id`
- `arbitration_decision_id`

Risk review also keeps arbitration visible through non-blocking warnings:

- `signal_arbitration_missing`
- `signal_arbitration_conflicts_present`

## Experiment Tracking

When a same-company signal bundle exists, experiment recording can attach arbitration context as metadata:

- `SignalBundle` as `INPUT_SNAPSHOT`
- `ArbitrationDecision` as `SUMMARY`
- `SignalCalibration` and `SignalConflict` as `DIAGNOSTIC`

This records arbitration context without pretending it changes exploratory backtest mechanics yet.

## Limitations

- Day 19 does not provide statistical calibration.
- Day 19 does not validate or approve signals.
- Current ranking is deterministic and heuristic, not learned.
- The portfolio layer can still fall back to raw signals when no arbitration bundle exists.
- Arbitration is not yet the actual downstream eligibility gate.
- The current repo still has only one real text-derived signal family in the main flow, so many multi-signal cases are synthetic or conflict-injection test cases.

## Safe Use

Use arbitration as a visibility and comparison layer.

Do not use it as evidence that a signal is correct.
Do not treat a selected primary signal as downstream-approved by itself.
Do not hide conflicts behind bundle summaries.
