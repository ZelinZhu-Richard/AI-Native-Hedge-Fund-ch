from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    AblationView,
    ConfidenceAssessment,
    CounterHypothesis,
    DerivedArtifactValidationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    Feature,
    FeatureDefinition,
    FeatureFamily,
    FeatureLineage,
    FeatureStatus,
    FeatureValue,
    FeatureValueType,
    GuidanceDirection,
    ResearchReviewStatus,
    ResearchValidationStatus,
    StrictModel,
    TimingAnomaly,
    ToneMarkerType,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.feature_store.loaders import LoadedFeatureMappingInputs
from services.timing import TimingService

SUPPORT_GRADE_MAP = {
    EvidenceGrade.STRONG: 1.0,
    EvidenceGrade.MODERATE: 0.66,
    EvidenceGrade.WEAK: 0.33,
    EvidenceGrade.INSUFFICIENT: 0.0,
}

GUIDANCE_SCORE_MAP = {
    GuidanceDirection.RAISED: 1.0,
    GuidanceDirection.MAINTAINED: 0.5,
    GuidanceDirection.INITIATED: 0.5,
    GuidanceDirection.LOWERED: -1.0,
    GuidanceDirection.WITHDREW: -1.0,
}


class FeatureMappingResult(StrictModel):
    """Structured output of deterministic Day 5 feature mapping."""

    feature_definitions: list[FeatureDefinition] = Field(
        default_factory=list,
        description="Feature definitions materialized for the current workflow.",
    )
    feature_values: list[FeatureValue] = Field(
        default_factory=list,
        description="Feature values materialized for the current workflow.",
    )
    features: list[Feature] = Field(
        default_factory=list,
        description="Primary candidate feature artifacts.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work, assumptions, or gaps.",
    )
    timing_anomalies: list[TimingAnomaly] = Field(
        default_factory=list,
        description="Structured timing anomalies observed while deriving feature availability.",
    )


def build_feature_candidates(
    *,
    inputs: LoadedFeatureMappingInputs,
    ablation_view: AblationView,
    clock: Clock,
    workflow_run_id: str,
) -> FeatureMappingResult:
    """Build the Day 5 deterministic feature set from research and parsing artifacts."""

    notes: list[str] = []
    timing_service = TimingService(clock=clock)
    if ablation_view is not AblationView.TEXT_ONLY:
        notes.append(
            f"Ablation view `{ablation_view.value}` is not populated on Day 5 because only "
            "text-derived features exist."
        )
        return FeatureMappingResult(notes=notes)

    if inputs.evidence_assessment.grade is EvidenceGrade.INSUFFICIENT:
        notes.append("Feature mapping skipped because evidence support is insufficient.")
        return FeatureMappingResult(notes=notes)

    if inputs.hypothesis is None or inputs.counter_hypothesis is None or inputs.research_brief is None:
        notes.append("Feature mapping requires a completed research workflow with hypothesis and critique.")
        return FeatureMappingResult(notes=notes)

    if _artifact_blocked(inputs.evidence_assessment.review_status, inputs.evidence_assessment.validation_status):
        notes.append("Feature mapping skipped because the evidence assessment is rejected or invalidated.")
        return FeatureMappingResult(notes=notes)
    if _artifact_blocked(inputs.hypothesis.review_status, inputs.hypothesis.validation_status):
        notes.append("Feature mapping skipped because the hypothesis is rejected or invalidated.")
        return FeatureMappingResult(notes=notes)
    if _artifact_blocked(
        inputs.counter_hypothesis.review_status, inputs.counter_hypothesis.validation_status
    ):
        notes.append("Feature mapping skipped because the counter-hypothesis is rejected or invalidated.")
        return FeatureMappingResult(notes=notes)
    if _artifact_blocked(inputs.research_brief.review_status, inputs.research_brief.validation_status):
        notes.append("Feature mapping skipped because the research brief is rejected or invalidated.")
        return FeatureMappingResult(notes=notes)

    if not inputs.guidance_changes:
        notes.append("No parsing guidance artifacts were available; guidance_change_score defaults to 0.0.")
    if not inputs.risk_factors:
        notes.append("No parsing risk-factor artifacts were available; risk_factor_count defaults to 0.")
    if not inputs.tone_markers:
        notes.append("No parsing tone-marker artifacts were available; tone_balance_score defaults to 0.0.")
    if inputs.research_brief.review_status is not ResearchReviewStatus.APPROVED_FOR_FEATURE_WORK:
        notes.append("Features remain candidate-only because research artifacts are not yet approved for feature work.")

    as_of_date = inputs.research_brief.created_at.date()
    fallback_available_at = _max_timestamp(
        [
            inputs.hypothesis.updated_at,
            inputs.counter_hypothesis.updated_at,
            inputs.evidence_assessment.updated_at,
            inputs.research_brief.updated_at,
            *[artifact.updated_at for artifact in inputs.guidance_changes],
            *[artifact.updated_at for artifact in inputs.risk_factors],
            *[artifact.updated_at for artifact in inputs.tone_markers],
        ]
    )
    lineage = FeatureLineage(
        feature_lineage_id=make_canonical_id(
            "flin",
            inputs.company_id,
            inputs.hypothesis.hypothesis_id,
            inputs.research_brief.research_brief_id,
        ),
        hypothesis_id=inputs.hypothesis.hypothesis_id,
        counter_hypothesis_id=inputs.counter_hypothesis.counter_hypothesis_id,
        evidence_assessment_id=inputs.evidence_assessment.evidence_assessment_id,
        research_brief_id=inputs.research_brief.research_brief_id,
        supporting_evidence_link_ids=[
            link.supporting_evidence_link_id for link in inputs.hypothesis.supporting_evidence_links
        ],
        source_document_ids=sorted(
            {link.document_id for link in inputs.hypothesis.supporting_evidence_links}
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )

    source_reference_ids = sorted(
        {
            *inputs.hypothesis.provenance.source_reference_ids,
            *inputs.counter_hypothesis.provenance.source_reference_ids,
            *inputs.evidence_assessment.provenance.source_reference_ids,
            *inputs.research_brief.provenance.source_reference_ids,
            *[source_reference_id for artifact in inputs.guidance_changes for source_reference_id in artifact.provenance.source_reference_ids],
            *[source_reference_id for artifact in inputs.risk_factors for source_reference_id in artifact.provenance.source_reference_ids],
            *[source_reference_id for artifact in inputs.tone_markers for source_reference_id in artifact.provenance.source_reference_ids],
        }
    )
    upstream_artifact_ids = [
        inputs.hypothesis.hypothesis_id,
        inputs.counter_hypothesis.counter_hypothesis_id,
        inputs.evidence_assessment.evidence_assessment_id,
        inputs.research_brief.research_brief_id,
        *[artifact.guidance_change_id for artifact in inputs.guidance_changes],
        *[artifact.risk_factor_id for artifact in inputs.risk_factors],
        *[artifact.tone_marker_id for artifact in inputs.tone_markers],
    ]
    common_assumptions = [
        "Day 5 features are candidate-only and must not be treated as validated alpha.",
    ]
    availability_window, timing_anomalies = timing_service.derive_feature_availability(
        target_id=make_canonical_id(
            "fval",
            inputs.company_id,
            "shared",
            as_of_date.isoformat(),
            inputs.research_brief.research_brief_id,
        ),
        source_reference_ids=source_reference_ids,
        upstream_windows=inputs.document_availability_windows,
        fallback_time=fallback_available_at,
    )
    available_at = availability_window.available_from
    if timing_anomalies:
        notes.append(
            "Feature availability used a compatibility fallback because upstream document timing metadata was incomplete."
        )

    feature_specs = [
        (
            "support_grade_score",
            "Map the current evidence grade into a numeric support score.",
            SUPPORT_GRADE_MAP[inputs.evidence_assessment.grade],
        ),
        (
            "support_document_count",
            "Count distinct supporting documents cited by the active hypothesis.",
            float(len({link.document_id for link in inputs.hypothesis.supporting_evidence_links})),
        ),
        (
            "guidance_change_score",
            "Map explicit guidance or outlook direction into a numeric marker.",
            _guidance_change_score(inputs.guidance_changes),
        ),
        (
            "risk_factor_count",
            "Count extracted risk-factor artifacts referenced by the current research slice.",
            float(len(inputs.risk_factors)),
        ),
        (
            "tone_balance_score",
            "Balance confidence and improvement tone markers against caution and uncertainty markers.",
            _tone_balance_score(inputs.tone_markers),
        ),
        (
            "counterargument_pressure_score",
            "Quantify critique pressure from the counter-hypothesis structure.",
            _counterargument_pressure_score(inputs.counter_hypothesis),
        ),
    ]

    created_at = clock.now()
    confidence = _feature_confidence(inputs.evidence_assessment)
    feature_definitions: list[FeatureDefinition] = []
    feature_values: list[FeatureValue] = []
    features: list[Feature] = []
    for name, description, numeric_value in feature_specs:
        feature_definition = FeatureDefinition(
            feature_definition_id=make_canonical_id("fdef", name),
            name=name,
            family=FeatureFamily.TEXT_DERIVED,
            value_type=FeatureValueType.NUMERIC,
            description=description,
            unit=None,
            ablation_views=[AblationView.TEXT_ONLY, AblationView.COMBINED],
            status=FeatureStatus.PROVISIONAL,
            validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day5_feature_definition_registry",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=upstream_artifact_ids,
                workflow_run_id=workflow_run_id,
                notes=[f"feature_name={name}", f"ablation_view={ablation_view.value}"],
            ),
            created_at=created_at,
            updated_at=created_at,
        )
        feature_value = FeatureValue(
            feature_value_id=make_canonical_id(
                "fval",
                inputs.company_id,
                name,
                as_of_date.isoformat(),
                inputs.research_brief.research_brief_id,
            ),
            feature_definition_id=feature_definition.feature_definition_id,
            as_of_date=as_of_date,
            available_at=available_at,
            availability_window=availability_window.model_copy(),
            numeric_value=numeric_value,
            confidence=confidence,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day5_feature_value_materialization",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=upstream_artifact_ids,
                workflow_run_id=workflow_run_id,
                notes=[f"feature_name={name}"],
            ),
            created_at=created_at,
            updated_at=created_at,
        )
        feature = Feature(
            feature_id=make_canonical_id(
                "feat",
                inputs.company_id,
                name,
                as_of_date.isoformat(),
                ablation_view.value,
            ),
            entity_id=inputs.company_id,
            company_id=inputs.company_id,
            feature_definition=feature_definition,
            feature_value=feature_value,
            status=FeatureStatus.PROVISIONAL,
            validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
            lineage=lineage,
            assumptions=common_assumptions,
            confidence=confidence,
            provenance=build_provenance(
                clock=clock,
                transformation_name="day5_feature_mapping",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=upstream_artifact_ids,
                workflow_run_id=workflow_run_id,
                notes=[f"feature_name={name}", f"ablation_view={ablation_view.value}", *notes],
            ),
            created_at=created_at,
            updated_at=created_at,
        )
        feature_definitions.append(feature_definition)
        feature_values.append(feature_value)
        features.append(feature)

    return FeatureMappingResult(
        feature_definitions=feature_definitions,
        feature_values=feature_values,
        features=features,
        notes=notes,
        timing_anomalies=timing_anomalies,
    )


def _artifact_blocked(
    review_status: ResearchReviewStatus,
    validation_status: ResearchValidationStatus,
) -> bool:
    """Return whether an upstream research artifact should block feature generation."""

    return (
        review_status is ResearchReviewStatus.REJECTED
        or validation_status is ResearchValidationStatus.INVALIDATED
    )


def _guidance_change_score(guidance_changes: list) -> float:
    """Return the strongest current guidance marker for the research slice."""

    if not guidance_changes:
        return 0.0
    return max(GUIDANCE_SCORE_MAP[change.direction] for change in guidance_changes)


def _tone_balance_score(tone_markers: list) -> float:
    """Return a bounded tone-balance score from exact lexical markers."""

    positive_markers = sum(
        1
        for marker in tone_markers
        if marker.marker_type in {ToneMarkerType.CONFIDENCE, ToneMarkerType.IMPROVEMENT}
    )
    caution_markers = sum(
        1
        for marker in tone_markers
        if marker.marker_type in {ToneMarkerType.CAUTION, ToneMarkerType.UNCERTAINTY}
    )
    return _clamp((positive_markers - caution_markers) / 3.0, lower=-1.0, upper=1.0)


def _counterargument_pressure_score(counter_hypothesis: CounterHypothesis) -> float:
    """Return a bounded critique-pressure score from the counter-hypothesis structure."""

    raw_value = (
        len(counter_hypothesis.critique_kinds)
        + len(counter_hypothesis.missing_evidence)
        + len(counter_hypothesis.causal_gaps)
    ) / 6.0
    return _clamp(raw_value, lower=0.0, upper=1.0)


def _feature_confidence(evidence_assessment: EvidenceAssessment) -> ConfidenceAssessment:
    """Build a conservative confidence payload for Day 5 features."""

    base_confidence = {
        EvidenceGrade.STRONG: 0.60,
        EvidenceGrade.MODERATE: 0.52,
        EvidenceGrade.WEAK: 0.40,
        EvidenceGrade.INSUFFICIENT: 0.25,
    }[evidence_assessment.grade]
    confidence = min(base_confidence, 0.60)
    uncertainty = max(0.40, 1.0 - confidence)
    return ConfidenceAssessment(
        confidence=confidence,
        uncertainty=uncertainty,
        method="day5_rule_based_feature_mapping",
        rationale="Confidence is capped conservatively because Day 5 features are candidate-only.",
    )


def _max_timestamp(values: Iterable[datetime]) -> datetime:
    """Return the latest timestamp from a non-empty iterable."""

    filtered = [value.astimezone(UTC) for value in values]
    return max(filtered)


def _clamp(value: float, *, lower: float, upper: float) -> float:
    """Clamp a floating-point value into a closed interval."""

    return max(lower, min(upper, value))
