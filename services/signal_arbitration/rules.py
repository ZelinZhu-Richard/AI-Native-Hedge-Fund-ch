from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from itertools import combinations

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    ArbitrationDecision,
    ArbitrationRule,
    DerivedArtifactValidationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    ExcludedSignal,
    FreshnessState,
    RankingExplanation,
    ResearchStance,
    Signal,
    SignalBundle,
    SignalCalibration,
    SignalConflict,
    SignalConflictKind,
    SignalExclusionReason,
    SignalStatus,
    StrictModel,
    UncertaintyEstimate,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id


class ArbitrationCandidate(StrictModel):
    """Internal deterministic signal context used during arbitration."""

    signal: Signal = Field(description="Source signal under arbitration.")
    calibration: SignalCalibration = Field(description="Derived calibration row.")
    evidence_assessment: EvidenceAssessment | None = Field(
        default=None,
        description="Associated evidence assessment when available.",
    )

    @property
    def evidence_grade(self) -> EvidenceGrade | None:
        """Expose the associated evidence grade when present."""

        return (
            self.evidence_assessment.grade
            if self.evidence_assessment is not None
            else self.calibration.uncertainty_estimate.evidence_grade
        )


def default_arbitration_rules() -> list[ArbitrationRule]:
    """Return the stable deterministic arbitration rules used by Day 19."""

    definitions = [
        (
            "exclude_ineligible_signals",
            "Exclude rejected, expired, invalidated, and future-effective signals from arbitration candidates.",
            1,
            False,
        ),
        (
            "calibrate_signal_scores",
            "Clamp raw primary scores and derive explicit uncertainty and freshness context.",
            2,
            False,
        ),
        (
            "detect_signal_conflicts",
            "Record directional, maturity, freshness, support, and duplicate-support conflicts.",
            3,
            False,
        ),
        (
            "rank_remaining_candidates",
            "Rank candidates lexicographically by maturity, support, uncertainty, freshness, strength, recency, and identifier.",
            4,
            False,
        ),
        (
            "suppress_duplicate_support",
            "Suppress lower-ranked duplicates when the same support backs the same stance.",
            5,
            False,
        ),
        (
            "block_on_top_level_directional_disagreement",
            "Withhold a primary selection when the top opposing signals disagree under strong enough support.",
            6,
            True,
        ),
        (
            "select_primary_signal",
            "Select the top-ranked remaining signal when no blocking conflict prevents it.",
            7,
            False,
        ),
    ]
    return [
        ArbitrationRule(
            arbitration_rule_id=make_canonical_id("arule", str(priority), rule_name),
            rule_name=rule_name,
            description=description,
            priority=priority,
            blocking=blocking,
            notes=[],
        )
        for rule_name, description, priority, blocking in definitions
    ]


def build_signal_calibrations(
    *,
    signals: Iterable[Signal],
    evidence_assessments_by_hypothesis_id: dict[str, EvidenceAssessment],
    as_of_time: datetime | None,
    clock: Clock,
    workflow_run_id: str,
) -> tuple[list[ArbitrationCandidate], list[ExcludedSignal]]:
    """Build deterministic calibration rows for all non-excluded candidate signals."""

    now = clock.now()
    candidates: list[ArbitrationCandidate] = []
    excluded_signals: list[ExcludedSignal] = []
    for signal in signals:
        if signal.status in {SignalStatus.REJECTED, SignalStatus.EXPIRED}:
            excluded_signals.append(
                _build_excluded_signal(
                    signal=signal,
                    reason=(
                        SignalExclusionReason.REJECTED
                        if signal.status is SignalStatus.REJECTED
                        else SignalExclusionReason.EXPIRED
                    ),
                    message=(
                        f"Signal was excluded before arbitration because status `{signal.status.value}` is not eligible."
                    ),
                )
            )
            continue
        if signal.validation_status is DerivedArtifactValidationStatus.INVALIDATED:
            excluded_signals.append(
                _build_excluded_signal(
                    signal=signal,
                    reason=SignalExclusionReason.INVALIDATED,
                    message=(
                        "Signal was excluded before arbitration because validation_status "
                        "`invalidated` is not eligible."
                    ),
                )
            )
            continue
        if as_of_time is not None and signal.effective_at.astimezone(UTC) > as_of_time.astimezone(UTC):
            excluded_signals.append(
                _build_excluded_signal(
                    signal=signal,
                    reason=SignalExclusionReason.FUTURE_EFFECTIVE_AT_AS_OF_TIME,
                    message=(
                        "Signal was excluded before arbitration because effective_at is after "
                        "the requested as_of_time."
                    ),
                )
            )
            continue

        evidence_assessment = evidence_assessments_by_hypothesis_id.get(signal.hypothesis_id)
        lineage_complete = bool(
            signal.feature_ids
            and signal.lineage.feature_ids
            and signal.lineage.supporting_evidence_link_ids
            and signal.lineage.input_families
        )
        freshness_state = _freshness_state(signal=signal, as_of_time=as_of_time)
        uncertainty_score = (
            signal.confidence.uncertainty if signal.confidence is not None else 1.0
        )
        factors = [f"validation_status={signal.validation_status.value}"]
        if not lineage_complete:
            factors.append("lineage_incomplete")
        if not signal.uncertainties:
            factors.append("signal_uncertainties_missing")
        if evidence_assessment is not None:
            factors.append(f"evidence_grade={evidence_assessment.grade.value}")
        if signal.confidence is None:
            factors.append("missing_confidence_fallback")
        uncertainty_estimate = UncertaintyEstimate(
            uncertainty_estimate_id=make_canonical_id(
                "uest",
                signal.signal_id,
                as_of_time.isoformat() if as_of_time is not None else "latest",
            ),
            signal_id=signal.signal_id,
            uncertainty_score=uncertainty_score,
            base_uncertainty_source=(
                "signal_confidence"
                if signal.confidence is not None
                else "missing_confidence_fallback"
            ),
            lineage_complete=lineage_complete,
            validation_status=signal.validation_status,
            evidence_grade=evidence_assessment.grade if evidence_assessment is not None else None,
            freshness_state=freshness_state,
            factors=factors,
            method_name="day19_structural_signal_uncertainty",
            provenance=build_provenance(
                clock=clock,
                transformation_name="day19_structural_signal_uncertainty",
                source_reference_ids=signal.provenance.source_reference_ids,
                upstream_artifact_ids=[
                    signal.signal_id,
                    *(
                        [evidence_assessment.evidence_assessment_id]
                        if evidence_assessment is not None
                        else []
                    ),
                ],
                workflow_run_id=workflow_run_id,
            ),
        )
        normalized_score = max(-1.0, min(1.0, signal.primary_score))
        calibration_notes = []
        if signal.primary_score != normalized_score:
            calibration_notes.append("primary_score_clamped_to_unit_interval")
        calibration = SignalCalibration(
            signal_calibration_id=make_canonical_id(
                "scal",
                signal.signal_id,
                as_of_time.isoformat() if as_of_time is not None else "latest",
            ),
            signal_id=signal.signal_id,
            company_id=signal.company_id,
            raw_primary_score=signal.primary_score,
            normalized_score=normalized_score,
            absolute_strength=abs(normalized_score),
            calibration_method="day19_clamped_primary_score",
            uncertainty_estimate=uncertainty_estimate,
            notes=calibration_notes,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day19_signal_calibration",
                source_reference_ids=signal.provenance.source_reference_ids,
                upstream_artifact_ids=[signal.signal_id],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )
        candidates.append(
            ArbitrationCandidate(
                signal=signal,
                calibration=calibration,
                evidence_assessment=evidence_assessment,
            )
        )
    return candidates, excluded_signals


def detect_signal_conflicts(
    *,
    candidates: list[ArbitrationCandidate],
    as_of_time: datetime | None,
    clock: Clock,
    workflow_run_id: str,
) -> list[SignalConflict]:
    """Detect deterministic cross-signal conflicts and support mismatches."""

    now = clock.now()
    conflicts: list[SignalConflict] = []
    for candidate in candidates:
        evidence_grade = candidate.evidence_grade
        if (
            candidate.calibration.absolute_strength >= 0.50
            and evidence_grade in {EvidenceGrade.WEAK, EvidenceGrade.INSUFFICIENT}
        ):
            conflicts.append(
                SignalConflict(
                    signal_conflict_id=make_canonical_id(
                        "sconf",
                        candidate.signal.signal_id,
                        SignalConflictKind.SCORE_SUPPORT_MISMATCH.value,
                    ),
                    company_id=candidate.signal.company_id,
                    conflict_kind=SignalConflictKind.SCORE_SUPPORT_MISMATCH,
                    signal_ids=[candidate.signal.signal_id],
                    blocking=False,
                    message=(
                        f"Signal score magnitude {candidate.calibration.absolute_strength:.2f} is high "
                        f"relative to evidence grade `{evidence_grade.value}`."
                    ),
                    related_artifact_ids=[
                        candidate.signal.signal_id,
                        *(
                            [candidate.evidence_assessment.evidence_assessment_id]
                            if candidate.evidence_assessment is not None
                            else []
                        ),
                    ],
                    provenance=build_provenance(
                        clock=clock,
                        transformation_name="day19_signal_conflict_detection",
                        source_reference_ids=candidate.signal.provenance.source_reference_ids,
                        upstream_artifact_ids=[candidate.signal.signal_id],
                        workflow_run_id=workflow_run_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )

    for left, right in combinations(candidates, 2):
        signal_pair = sorted([left.signal.signal_id, right.signal.signal_id])
        shared_source_reference_ids = sorted(
            {
                *left.signal.provenance.source_reference_ids,
                *right.signal.provenance.source_reference_ids,
            }
        )
        provenance = build_provenance(
            clock=clock,
            transformation_name="day19_signal_conflict_detection",
            source_reference_ids=shared_source_reference_ids,
            upstream_artifact_ids=signal_pair,
            workflow_run_id=workflow_run_id,
        )
        if _stances_oppose(left.signal.stance, right.signal.stance):
            blocking = (
                left.evidence_grade in {EvidenceGrade.STRONG, EvidenceGrade.MODERATE}
                and right.evidence_grade in {EvidenceGrade.STRONG, EvidenceGrade.MODERATE}
            )
            conflicts.append(
                SignalConflict(
                    signal_conflict_id=make_canonical_id(
                        "sconf",
                        *signal_pair,
                        SignalConflictKind.DIRECTIONAL_DISAGREEMENT.value,
                    ),
                    conflict_kind=SignalConflictKind.DIRECTIONAL_DISAGREEMENT,
                    blocking=blocking,
                    message=(
                        f"Signals disagree directionally: `{left.signal.stance.value}` versus "
                        f"`{right.signal.stance.value}`."
                    ),
                    related_artifact_ids=signal_pair,
                    company_id=left.signal.company_id,
                    signal_ids=signal_pair,
                    provenance=provenance,
                    created_at=now,
                    updated_at=now,
                )
            )
        if (
            as_of_time is not None
            and left.calibration.uncertainty_estimate.freshness_state
            != right.calibration.uncertainty_estimate.freshness_state
            and FreshnessState.UNKNOWN
            not in {
                left.calibration.uncertainty_estimate.freshness_state,
                right.calibration.uncertainty_estimate.freshness_state,
            }
            and (
                left.signal.signal_family == right.signal.signal_family
                or _stances_oppose(left.signal.stance, right.signal.stance)
            )
        ):
            conflicts.append(
                SignalConflict(
                    signal_conflict_id=make_canonical_id(
                        "sconf",
                        *signal_pair,
                        SignalConflictKind.FRESHNESS_MISMATCH.value,
                    ),
                    conflict_kind=SignalConflictKind.FRESHNESS_MISMATCH,
                    blocking=False,
                    message=(
                        f"Signals differ in freshness: "
                        f"`{left.calibration.uncertainty_estimate.freshness_state.value}` versus "
                        f"`{right.calibration.uncertainty_estimate.freshness_state.value}`."
                    ),
                    related_artifact_ids=signal_pair,
                    company_id=left.signal.company_id,
                    signal_ids=signal_pair,
                    provenance=provenance,
                    created_at=now,
                    updated_at=now,
                )
            )
        left_support = set(left.signal.lineage.supporting_evidence_link_ids)
        right_support = set(right.signal.lineage.supporting_evidence_link_ids)
        overlap = sorted(left_support & right_support)
        if overlap:
            conflicts.append(
                SignalConflict(
                    signal_conflict_id=make_canonical_id(
                        "sconf",
                        *signal_pair,
                        SignalConflictKind.DUPLICATE_SUPPORT_OVERLAP.value,
                    ),
                    conflict_kind=SignalConflictKind.DUPLICATE_SUPPORT_OVERLAP,
                    blocking=False,
                    message=(
                        f"Signals share {len(overlap)} supporting evidence links and may duplicate support."
                    ),
                    related_artifact_ids=[*signal_pair, *overlap],
                    company_id=left.signal.company_id,
                    signal_ids=signal_pair,
                    provenance=provenance,
                    created_at=now,
                    updated_at=now,
                )
            )
        if (
            left.signal.status != right.signal.status
            or left.signal.validation_status != right.signal.validation_status
        ):
            conflicts.append(
                SignalConflict(
                    signal_conflict_id=make_canonical_id(
                        "sconf",
                        *signal_pair,
                        SignalConflictKind.MATURITY_MISMATCH.value,
                    ),
                    conflict_kind=SignalConflictKind.MATURITY_MISMATCH,
                    blocking=False,
                    message=(
                        f"Signals differ in maturity: "
                        f"`{left.signal.status.value}/{left.signal.validation_status.value}` versus "
                        f"`{right.signal.status.value}/{right.signal.validation_status.value}`."
                    ),
                    related_artifact_ids=signal_pair,
                    company_id=left.signal.company_id,
                    signal_ids=signal_pair,
                    provenance=provenance,
                    created_at=now,
                    updated_at=now,
                )
            )
    return conflicts


def build_arbitration_decision(
    *,
    company_id: str,
    component_signals: list[Signal],
    candidates: list[ArbitrationCandidate],
    excluded_signals: list[ExcludedSignal],
    conflicts: list[SignalConflict],
    as_of_time: datetime | None,
    clock: Clock,
    workflow_run_id: str,
) -> tuple[ArbitrationDecision, SignalBundle]:
    """Build the final arbitration decision and persisted bundle."""

    now = clock.now()
    applied_rules = default_arbitration_rules()
    ranked_candidates = sorted(candidates, key=_candidate_sort_key)
    suppressed_signal_ids = _suppressed_duplicate_signal_ids(ranked_candidates)
    prioritized_candidates = [
        candidate
        for candidate in ranked_candidates
        if candidate.signal.signal_id not in suppressed_signal_ids
    ]
    prioritized_signal_ids = [candidate.signal.signal_id for candidate in prioritized_candidates]

    selected_primary_signal_id: str | None = None
    review_required = True
    if prioritized_candidates:
        top_candidate = prioritized_candidates[0]
        blocking_directional = next(
            (
                conflict
                for conflict in conflicts
                if conflict.conflict_kind is SignalConflictKind.DIRECTIONAL_DISAGREEMENT
                and conflict.blocking
                and top_candidate.signal.signal_id in conflict.signal_ids
            ),
            None,
        )
        if blocking_directional is None:
            selected_primary_signal_id = top_candidate.signal.signal_id

    blocking_directional_conflict_ids = {
        conflict.signal_conflict_id
        for conflict in conflicts
        if conflict.conflict_kind is SignalConflictKind.DIRECTIONAL_DISAGREEMENT
        and conflict.blocking
    }
    ranking_explanations = []
    for rank, candidate in enumerate(ranked_candidates, start=1):
        warnings = [
            conflict.message
            for conflict in conflicts
            if candidate.signal.signal_id in conflict.signal_ids
        ]
        why_not_selected = None
        if selected_primary_signal_id != candidate.signal.signal_id:
            if candidate.signal.signal_id in suppressed_signal_ids:
                why_not_selected = "Suppressed due to duplicate support with a higher-ranked signal."
            elif selected_primary_signal_id is None and prioritized_candidates and blocking_directional_conflict_ids:
                why_not_selected = (
                    "No primary signal was selected because the top-ranked candidates remain in blocking disagreement."
                )
            else:
                why_not_selected = "Lower deterministic rank than the selected primary signal."
        ranking_explanations.append(
            build_ranking_explanation(
                candidate=candidate,
                rank=rank,
                warnings=warnings,
                why_not_selected=why_not_selected,
            )
        )

    candidate_signal_ids = [candidate.signal.signal_id for candidate in ranked_candidates]
    decision_summary = (
        "No primary signal was selected because arbitration observed unresolved top-level disagreement."
        if selected_primary_signal_id is None and prioritized_signal_ids
        else (
            f"Selected primary signal `{selected_primary_signal_id}` after deterministic ranking."
            if selected_primary_signal_id is not None
            else "No eligible signals remained after exclusion rules."
        )
    )
    decision = ArbitrationDecision(
        arbitration_decision_id=make_canonical_id(
            "adec",
            company_id,
            as_of_time.isoformat() if as_of_time is not None else "latest",
        ),
        company_id=company_id,
        candidate_signal_ids=candidate_signal_ids,
        selected_primary_signal_id=selected_primary_signal_id,
        excluded_signals=excluded_signals,
        prioritized_signal_ids=prioritized_signal_ids,
        suppressed_signal_ids=suppressed_signal_ids,
        applied_rules=applied_rules,
        conflict_ids=[conflict.signal_conflict_id for conflict in conflicts],
        ranking_explanations=ranking_explanations,
        review_required=review_required,
        summary=decision_summary,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day19_signal_arbitration_decision",
            source_reference_ids=sorted(
                {
                    source_reference_id
                    for signal in component_signals
                    for source_reference_id in signal.provenance.source_reference_ids
                }
            ),
            upstream_artifact_ids=[
                *[signal.signal_id for signal in component_signals],
                *[conflict.signal_conflict_id for conflict in conflicts],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )
    bundle = SignalBundle(
        signal_bundle_id=make_canonical_id(
            "sbundle",
            company_id,
            as_of_time.isoformat() if as_of_time is not None else "latest",
        ),
        company_id=company_id,
        as_of_time=as_of_time,
        component_signal_ids=[signal.signal_id for signal in component_signals],
        signal_calibration_ids=[
            candidate.calibration.signal_calibration_id for candidate in candidates
        ],
        signal_conflict_ids=[conflict.signal_conflict_id for conflict in conflicts],
        arbitration_decision_id=decision.arbitration_decision_id,
        bundle_summary=decision.summary,
        review_required=decision.review_required,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day19_signal_bundle",
            source_reference_ids=decision.provenance.source_reference_ids,
            upstream_artifact_ids=[
                *[signal.signal_id for signal in component_signals],
                decision.arbitration_decision_id,
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )
    return decision, bundle


def build_ranking_explanation(
    *,
    candidate: ArbitrationCandidate,
    rank: int,
    warnings: list[str],
    why_not_selected: str | None,
) -> RankingExplanation:
    """Build one deterministic ranking explanation row."""

    evidence_grade = candidate.evidence_grade.value if candidate.evidence_grade is not None else "unknown"
    return RankingExplanation(
        signal_id=candidate.signal.signal_id,
        rank=rank,
        rule_trace=[
            f"validation_status={candidate.signal.validation_status.value}",
            f"signal_status={candidate.signal.status.value}",
            f"evidence_grade={evidence_grade}",
            f"uncertainty_score={candidate.calibration.uncertainty_estimate.uncertainty_score:.2f}",
            f"freshness_state={candidate.calibration.uncertainty_estimate.freshness_state.value}",
            f"absolute_strength={candidate.calibration.absolute_strength:.2f}",
        ],
        warnings=warnings,
        why_not_selected=why_not_selected,
    )


def _freshness_state(*, signal: Signal, as_of_time: datetime | None) -> FreshnessState:
    """Return a simple freshness label for one signal."""

    if as_of_time is None:
        return FreshnessState.UNKNOWN
    age = as_of_time.astimezone(UTC) - signal.effective_at.astimezone(UTC)
    if age.total_seconds() < 0:
        return FreshnessState.UNKNOWN
    if age.days <= 1:
        return FreshnessState.FRESH
    if age.days <= 5:
        return FreshnessState.AGING
    return FreshnessState.STALE


def _build_excluded_signal(
    *,
    signal: Signal,
    reason: SignalExclusionReason,
    message: str,
) -> ExcludedSignal:
    """Build one explicit exclusion row for a signal removed before ranking."""

    return ExcludedSignal(signal_id=signal.signal_id, reason=reason, message=message)


def _candidate_sort_key(candidate: ArbitrationCandidate) -> tuple[object, ...]:
    """Return the deterministic lexicographic sort key for one candidate signal."""

    evidence_grade = candidate.evidence_grade
    effective_timestamp = candidate.signal.effective_at.astimezone(UTC).timestamp()
    return (
        _validation_rank(candidate.signal.validation_status),
        _signal_status_rank(candidate.signal.status),
        _evidence_grade_rank(evidence_grade),
        candidate.calibration.uncertainty_estimate.uncertainty_score,
        _freshness_rank(candidate.calibration.uncertainty_estimate.freshness_state),
        -candidate.calibration.absolute_strength,
        -effective_timestamp,
        candidate.signal.signal_id,
    )


def _suppressed_duplicate_signal_ids(candidates: list[ArbitrationCandidate]) -> list[str]:
    """Return lower-ranked duplicate-support signal identifiers to suppress."""

    suppressed: list[str] = []
    for index, candidate in enumerate(candidates):
        if candidate.signal.signal_id in suppressed:
            continue
        candidate_support = set(candidate.signal.lineage.supporting_evidence_link_ids)
        for lower_ranked in candidates[index + 1 :]:
            if lower_ranked.signal.signal_id in suppressed:
                continue
            lower_support = set(lower_ranked.signal.lineage.supporting_evidence_link_ids)
            if (
                candidate.signal.stance == lower_ranked.signal.stance
                and candidate_support
                and candidate_support == lower_support
            ):
                suppressed.append(lower_ranked.signal.signal_id)
    return suppressed


def _validation_rank(status: DerivedArtifactValidationStatus) -> int:
    order = {
        DerivedArtifactValidationStatus.VALIDATED: 0,
        DerivedArtifactValidationStatus.PARTIALLY_VALIDATED: 1,
        DerivedArtifactValidationStatus.PENDING_VALIDATION: 2,
        DerivedArtifactValidationStatus.UNVALIDATED: 3,
        DerivedArtifactValidationStatus.INVALIDATED: 4,
    }
    return order[status]


def _signal_status_rank(status: SignalStatus) -> int:
    order = {
        SignalStatus.APPROVED: 0,
        SignalStatus.CANDIDATE: 1,
        SignalStatus.REJECTED: 2,
        SignalStatus.EXPIRED: 3,
    }
    return order[status]


def _evidence_grade_rank(grade: EvidenceGrade | None) -> int:
    order = {
        EvidenceGrade.STRONG: 0,
        EvidenceGrade.MODERATE: 1,
        EvidenceGrade.WEAK: 2,
        EvidenceGrade.INSUFFICIENT: 3,
        None: 4,
    }
    return order[grade]


def _freshness_rank(state: FreshnessState) -> int:
    order = {
        FreshnessState.FRESH: 0,
        FreshnessState.AGING: 1,
        FreshnessState.STALE: 2,
        FreshnessState.UNKNOWN: 3,
    }
    return order[state]


def _stances_oppose(left: ResearchStance, right: ResearchStance) -> bool:
    """Return whether two stances express an opposing directional view."""

    return {
        left,
        right,
    } == {ResearchStance.POSITIVE, ResearchStance.NEGATIVE}
