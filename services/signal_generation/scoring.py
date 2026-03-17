from __future__ import annotations

from datetime import UTC

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    AblationView,
    ConfidenceAssessment,
    DerivedArtifactValidationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    Feature,
    FeatureFamily,
    ResearchStance,
    Signal,
    SignalLineage,
    SignalScore,
    SignalStatus,
    StrictModel,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.signal_generation.loaders import LoadedSignalGenerationInputs


class SignalGenerationResult(StrictModel):
    """Structured output of deterministic Day 5 signal generation."""

    signals: list[Signal] = Field(
        default_factory=list,
        description="Candidate signals emitted by the workflow.",
    )
    signal_scores: list[SignalScore] = Field(
        default_factory=list,
        description="Score components emitted by the workflow.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work, assumptions, or gaps.",
    )


def build_candidate_signals(
    *,
    inputs: LoadedSignalGenerationInputs,
    ablation_view: AblationView,
    clock: Clock,
    workflow_run_id: str,
) -> SignalGenerationResult:
    """Build one deterministic Day 5 candidate signal from eligible candidate features."""

    notes: list[str] = []
    eligible_features = _eligible_features(inputs.features, ablation_view=ablation_view)
    if not eligible_features:
        notes.append(
            f"No eligible features were found for ablation view `{ablation_view.value}`."
        )
        return SignalGenerationResult(notes=notes)

    feature_values = {
        feature.feature_definition.name: float(feature.feature_value.numeric_value)
        for feature in eligible_features
        if feature.feature_value.numeric_value is not None
    }
    required_feature_names = {
        "support_grade_score",
        "support_document_count",
        "guidance_change_score",
        "risk_factor_count",
        "tone_balance_score",
        "counterargument_pressure_score",
    }
    missing_feature_names = sorted(required_feature_names - feature_values.keys())
    if missing_feature_names:
        notes.append(
            "Signal generation skipped because required feature values are missing: "
            + ", ".join(missing_feature_names)
        )
        return SignalGenerationResult(notes=notes)

    support_grade_component = feature_values["support_grade_score"]
    breadth_component = min(feature_values["support_document_count"] / 3.0, 1.0)
    guidance_component = feature_values["guidance_change_score"]
    tone_component = feature_values["tone_balance_score"]
    risk_component = -min(feature_values["risk_factor_count"] / 3.0, 1.0)
    critique_component = -feature_values["counterargument_pressure_score"]
    primary_score = (
        0.30 * support_grade_component
        + 0.20 * breadth_component
        + 0.20 * guidance_component
        + 0.10 * tone_component
        + 0.10 * risk_component
        + 0.10 * critique_component
    )
    stance = _stance_from_score(primary_score)

    effective_at = max(
        feature.feature_value.available_at.astimezone(UTC) for feature in eligible_features
    )
    source_reference_ids = sorted(
        {
            source_reference_id
            for feature in eligible_features
            for source_reference_id in feature.provenance.source_reference_ids
        }
    )
    research_artifact_ids = sorted(
        {
            feature.lineage.hypothesis_id
            for feature in eligible_features
        }
        | {
            feature.lineage.counter_hypothesis_id
            for feature in eligible_features
        }
        | {
            feature.lineage.evidence_assessment_id
            for feature in eligible_features
        }
        | {
            feature.lineage.research_brief_id
            for feature in eligible_features
        }
    )
    supporting_evidence_link_ids = sorted(
        {
            supporting_evidence_link_id
            for feature in eligible_features
            for supporting_evidence_link_id in feature.lineage.supporting_evidence_link_ids
        }
    )
    feature_ids = [feature.feature_id for feature in eligible_features]
    feature_definition_ids = [
        feature.feature_definition.feature_definition_id for feature in eligible_features
    ]
    feature_value_ids = [feature.feature_value.feature_value_id for feature in eligible_features]
    input_families = sorted(
        {feature.feature_definition.family for feature in eligible_features},
        key=lambda family: family.value,
    )
    created_at = clock.now()
    signal_lineage = SignalLineage(
        signal_lineage_id=make_canonical_id(
            "slin", inputs.company_id, ablation_view.value, effective_at.isoformat()
        ),
        feature_ids=feature_ids,
        feature_definition_ids=feature_definition_ids,
        feature_value_ids=feature_value_ids,
        research_artifact_ids=research_artifact_ids,
        supporting_evidence_link_ids=supporting_evidence_link_ids,
        input_families=input_families,
        created_at=created_at,
        updated_at=created_at,
    )
    signal_id = make_canonical_id(
        "sig", inputs.company_id, ablation_view.value, effective_at.isoformat()
    )

    signal_scores = [
        _build_signal_score(
            signal_id=signal_id,
            metric_name="support_grade_component",
            value=support_grade_component,
            scale_min=0.0,
            scale_max=1.0,
            source_feature_ids=[_feature_id_by_name(eligible_features, "support_grade_score")],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _build_signal_score(
            signal_id=signal_id,
            metric_name="breadth_component",
            value=breadth_component,
            scale_min=0.0,
            scale_max=1.0,
            source_feature_ids=[_feature_id_by_name(eligible_features, "support_document_count")],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _build_signal_score(
            signal_id=signal_id,
            metric_name="guidance_component",
            value=guidance_component,
            scale_min=-1.0,
            scale_max=1.0,
            source_feature_ids=[_feature_id_by_name(eligible_features, "guidance_change_score")],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _build_signal_score(
            signal_id=signal_id,
            metric_name="tone_component",
            value=tone_component,
            scale_min=-1.0,
            scale_max=1.0,
            source_feature_ids=[_feature_id_by_name(eligible_features, "tone_balance_score")],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _build_signal_score(
            signal_id=signal_id,
            metric_name="risk_component",
            value=risk_component,
            scale_min=-1.0,
            scale_max=0.0,
            source_feature_ids=[_feature_id_by_name(eligible_features, "risk_factor_count")],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _build_signal_score(
            signal_id=signal_id,
            metric_name="critique_component",
            value=critique_component,
            scale_min=-1.0,
            scale_max=0.0,
            source_feature_ids=[_feature_id_by_name(eligible_features, "counterargument_pressure_score")],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
    ]

    assumptions = sorted(
        {
            assumption
            for feature in eligible_features
            for assumption in feature.assumptions
        }
    )
    uncertainties = [
        "Signal is candidate-only and has not been validated out of sample.",
        "Current Day 5 build uses only text-derived features; price, fundamentals, and macro remain absent.",
    ]
    if inputs.evidence_assessment is not None:
        uncertainties.extend(inputs.evidence_assessment.key_gaps)

    thesis_summary = (
        inputs.hypothesis.thesis
        if inputs.hypothesis is not None
        else "Candidate signal built from Day 5 research-derived features."
    )
    confidence = _signal_confidence(
        evidence_assessment=inputs.evidence_assessment,
        risk_factor_count=feature_values["risk_factor_count"],
        counterargument_pressure_score=feature_values["counterargument_pressure_score"],
    )
    signal = Signal(
        signal_id=signal_id,
        company_id=inputs.company_id,
        hypothesis_id=(
            inputs.hypothesis.hypothesis_id
            if inputs.hypothesis is not None
            else eligible_features[0].lineage.hypothesis_id
        ),
        signal_family=f"{ablation_view.value}_candidate_signal",
        stance=stance,
        ablation_view=ablation_view,
        thesis_summary=thesis_summary,
        feature_ids=feature_ids,
        component_scores=signal_scores,
        primary_score=primary_score,
        effective_at=effective_at,
        expires_at=None,
        status=SignalStatus.CANDIDATE,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        lineage=signal_lineage,
        assumptions=assumptions,
        uncertainties=uncertainties,
        confidence=confidence,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day5_signal_generation",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[*research_artifact_ids, *feature_ids],
            workflow_run_id=workflow_run_id,
            notes=[f"ablation_view={ablation_view.value}"],
        ),
        created_at=created_at,
        updated_at=created_at,
    )
    return SignalGenerationResult(signals=[signal], signal_scores=signal_scores, notes=notes)


def _eligible_features(features: list[Feature], *, ablation_view: AblationView) -> list[Feature]:
    """Filter candidate features down to the requested ablation slice."""

    if ablation_view is AblationView.TEXT_ONLY:
        return [
            feature
            for feature in features
            if feature.feature_definition.family is FeatureFamily.TEXT_DERIVED
            and ablation_view in feature.feature_definition.ablation_views
        ]
    if ablation_view is AblationView.COMBINED:
        return [
            feature for feature in features if ablation_view in feature.feature_definition.ablation_views
        ]
    target_family = {
        AblationView.PRICE_ONLY: FeatureFamily.PRICE,
        AblationView.FUNDAMENTALS_ONLY: FeatureFamily.FUNDAMENTALS,
    }.get(ablation_view)
    if target_family is None:
        return []
    return [
        feature
        for feature in features
        if feature.feature_definition.family is target_family
        and ablation_view in feature.feature_definition.ablation_views
    ]


def _build_signal_score(
    *,
    signal_id: str,
    metric_name: str,
    value: float,
    scale_min: float,
    scale_max: float,
    source_feature_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> SignalScore:
    """Build one deterministic signal-score component."""

    now = clock.now()
    return SignalScore(
        signal_score_id=make_canonical_id("sscore", signal_id, metric_name),
        metric_name=metric_name,
        value=value,
        scale_min=scale_min,
        scale_max=scale_max,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        source_feature_ids=source_feature_ids,
        assumptions=["Component score is rule-based and not empirically validated."],
        calibrated_probability=None,
        confidence=ConfidenceAssessment(
            confidence=0.50,
            uncertainty=0.50,
            method="day5_rule_based_signal_scoring",
            rationale="Component scores are deterministic placeholders, not calibrated probabilities.",
        ),
        rationale=f"Derived from {metric_name} in the deterministic Day 5 scoring formula.",
        provenance=build_provenance(
            clock=clock,
            transformation_name="day5_signal_score_generation",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=source_feature_ids,
            workflow_run_id=workflow_run_id,
            notes=[f"metric_name={metric_name}"],
        ),
        created_at=now,
        updated_at=now,
    )


def _feature_id_by_name(features: list[Feature], name: str) -> str:
    """Resolve one feature identifier by its stable feature-definition name."""

    for feature in features:
        if feature.feature_definition.name == name:
            return feature.feature_id
    raise ValueError(f"Required feature `{name}` was not found.")


def _stance_from_score(primary_score: float) -> ResearchStance:
    """Map the deterministic score into a research-layer stance."""

    if primary_score >= 0.25:
        return ResearchStance.POSITIVE
    if primary_score <= -0.25:
        return ResearchStance.NEGATIVE
    return ResearchStance.MONITOR


def _signal_confidence(
    *,
    evidence_assessment: EvidenceAssessment | None,
    risk_factor_count: float,
    counterargument_pressure_score: float,
) -> ConfidenceAssessment:
    """Build a conservative signal confidence payload capped at moderate confidence."""

    grade = evidence_assessment.grade if evidence_assessment is not None else EvidenceGrade.WEAK
    base_confidence = {
        EvidenceGrade.STRONG: 0.58,
        EvidenceGrade.MODERATE: 0.50,
        EvidenceGrade.WEAK: 0.40,
        EvidenceGrade.INSUFFICIENT: 0.25,
    }[grade]
    penalty = min(0.15, counterargument_pressure_score * 0.10 + min(risk_factor_count / 10.0, 0.05))
    confidence = max(0.20, min(0.60, base_confidence - penalty))
    uncertainty = max(0.40, 1.0 - confidence)
    return ConfidenceAssessment(
        confidence=confidence,
        uncertainty=uncertainty,
        method="day5_rule_based_signal_scoring",
        rationale="Confidence is capped conservatively because the signal is candidate-only and unvalidated.",
    )
